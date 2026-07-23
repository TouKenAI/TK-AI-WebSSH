"""
AI API routes for TKAI SSH.
Provides endpoints for AI-powered command generation, execution, and analysis.
"""

from flask import request, jsonify
from flask_login import login_required, current_user
from ..ssh_manager import sessions, sessions_lock
from ..socket_events import verify_session_ownership
from ..audit_logger import log_info, log_warning, log_error
from .stepfun_provider import generate_command, analyze_result, explain_command, _clear_context
from .command_generator import validate_command, get_risk_level, get_danger_commands_list
import paramiko
import time


def register_ai_routes(app):
    """Register AI API routes on the Flask app."""

    # Exempt AI API endpoints from CSRF (they use their own auth via login_required)
    @app.route('/api/ai/chat', methods=['POST'])
    @login_required
    def ai_chat():
        """Generate an SSH command from natural language."""
        data = request.get_json(silent=True) or {}
        user_input = (data.get('message') or '').strip()
        device_type = data.get('device_type', 'linux')
        session_id = data.get('session_id')

        if not user_input:
            return jsonify({'success': False, 'error': '请输入您的需求描述'}), 400

        if len(user_input) > 500:
            return jsonify({'success': False, 'error': '输入过长，请控制在500字以内'}), 400

        result = generate_command(user_input, device_type, session_id)

        if 'error' in result:
            return jsonify({'success': False, 'error': result['error']}), 500

        # Validate the generated command
        is_valid, error_msg, risk_level = validate_command(result)
        if not is_valid and risk_level == 'danger':
            log_warning(
                'AI command blocked (danger)',
                user=current_user.username,
                command=result.get('command', ''),
            )
            return jsonify({
                'success': False,
                'error': error_msg,
                'blocked': True,
            }), 403

        if not is_valid:
            return jsonify({'success': False, 'error': error_msg}), 400

        # Override risk level with our assessment
        result['risk_level'] = risk_level

        log_info(
            'AI generated command',
            user=current_user.username,
            command=result['command'],
            risk=risk_level,
        )

        return jsonify({'success': True, 'data': result})

    @app.route('/api/ai/execute', methods=['POST'])
    @login_required
    def ai_execute():
        """Execute a command via SSH and return the result."""
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        command = (data.get('command') or '').strip()

        if not session_id or not command:
            return jsonify({'success': False, 'error': '缺少session_id或command参数'}), 400

        # Verify session ownership
        if not verify_session_ownership(session_id, current_user.id):
            return jsonify({'success': False, 'error': '无权操作此会话或会话已断开'}), 403

        # Final safety check before execution
        risk = get_risk_level(command)
        if risk == 'danger':
            log_warning(
                'Command execution blocked (danger)',
                user=current_user.username,
                command=command,
            )
            return jsonify({
                'success': False,
                'error': '危险命令已被拦截，如确需执行请在终端中手动操作',
                'blocked': True,
            }), 403

        # Get SSH client from session
        with sessions_lock:
            session = sessions.get(session_id)
            if not session or not session.get('connected'):
                return jsonify({'success': False, 'error': 'SSH连接已断开，请重新连接'}), 503
            client = session['client']
            host = session['host']
            session['last_activity'] = time.time()

        # Execute command via SSH
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=30)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8', errors='replace')
            error_output = stderr.read().decode('utf-8', errors='replace')

            # Combine stdout and stderr
            if error_output and not output:
                result_text = error_output
            elif error_output:
                result_text = output + '\n' + error_output
            else:
                result_text = output

            # Truncate very long output
            if len(result_text) > 10000:
                result_text = result_text[:10000] + '\n...(输出已截断)'

            log_info(
                'AI command executed',
                user=current_user.username,
                host=host,
                command=command,
                exit_code=exit_code,
            )

            return jsonify({
                'success': True,
                'data': {
                    'result': result_text,
                    'exit_code': exit_code,
                    'risk_level': risk,
                },
            })

        except paramiko.SSHException as e:
            log_error('SSH command execution failed', error=str(e), command=command)
            return jsonify({'success': False, 'error': f'SSH执行失败: {str(e)}'}), 500
        except Exception as e:
            log_error('Command execution error', error=str(e), command=command)
            return jsonify({'success': False, 'error': f'执行出错: {str(e)}'}), 500

    @app.route('/api/ai/analyze', methods=['POST'])
    @login_required
    def ai_analyze():
        """Analyze command execution result in natural language."""
        data = request.get_json(silent=True) or {}
        command = data.get('command', '')
        result = data.get('result', '')
        device_type = data.get('device_type', 'linux')

        if not command or not result:
            return jsonify({'success': False, 'error': '缺少command或result参数'}), 400

        analysis = analyze_result(command, result, device_type)

        return jsonify({'success': True, 'data': {'analysis': analysis}})

    @app.route('/api/ai/explain', methods=['POST'])
    @login_required
    def ai_explain():
        """Explain a command in plain Chinese."""
        data = request.get_json(silent=True) or {}
        command = data.get('command', '')
        device_type = data.get('device_type', 'linux')

        if not command:
            return jsonify({'success': False, 'error': '缺少command参数'}), 400

        explanation = explain_command(command, device_type)

        return jsonify({'success': True, 'data': {'explanation': explanation}})

    @app.route('/api/ai/clear', methods=['POST'])
    @login_required
    def ai_clear():
        """Clear conversation context for a session."""
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')

        if session_id:
            _clear_context(session_id)

        return jsonify({'success': True})

    @app.route('/api/ai/danger-list', methods=['GET'])
    @login_required
    def ai_danger_list():
        """Get list of blocked danger commands (for UI display)."""
        return jsonify({
            'success': True,
            'data': {'commands': get_danger_commands_list()},
        })

    @app.route('/api/ai/status', methods=['GET'])
    @login_required
    def ai_status():
        """Check if AI service is configured."""
        from .stepfun_provider import API_KEY, MODEL
        return jsonify({
            'success': True,
            'data': {
                'configured': bool(API_KEY),
                'model': MODEL,
            },
        })
