"""
StepFun API Provider.
Calls StepFun (阶跃星辰) API to generate SSH commands from natural language.

Phase 1: Returns JSON format {command, description, risk_level} — no function calling.
"""

import os
import json
import logging
import requests

logger = logging.getLogger('webssh')

# Configuration from environment variables
API_KEY = os.environ.get('STEPFUN_API_KEY', '')
API_URL = os.environ.get('STEPFUN_API_URL', 'https://api.stepfun.com/step_plan/v1')
MODEL = os.environ.get('STEPFUN_MODEL', 'step-3.5-flash-2603')

# System prompts per device type
DEVICE_PROMPTS = {
    'linux': (
        '你是一个Linux系统运维专家。用户不懂命令行，你需要根据用户的自然语言描述，'
        '生成准确的Linux命令。必须用JSON格式返回，包含三个字段：\n'
        'command: 要执行的命令（字符串）\n'
        'description: 命令的中文说明（字符串）\n'
        'risk_level: 风险等级，只能是 safe/warning/danger 之一\n'
        'safe=查看类命令，warning=修改配置类，danger=破坏性操作'
    ),
    'huawei_vrp': (
        '你是一个华为VRP系统运维专家。用户不懂命令行，你需要根据用户的自然语言描述，'
        '生成准确的华为VRP命令（如display而不是show）。必须用JSON格式返回，'
        '包含command、description、risk_level三个字段。'
    ),
    'cisco_ios': (
        '你是一个Cisco IOS系统运维专家。用户不懂命令行，你需要根据用户的自然语言描述，'
        '生成准确的Cisco IOS命令。必须用JSON格式返回，'
        '包含command、description、risk_level三个字段。'
    ),
    'generic': (
        '你是一个网络设备运维专家。请根据设备类型生成正确的命令。'
        '必须用JSON格式返回，包含command、description、risk_level三个字段。'
    ),
}

# Analysis system prompt
ANALYSIS_PROMPT = (
    '你是一个系统运维专家。请用简洁的中文分析以下命令执行结果，'
    '指出关键信息和需要关注的问题。如果一切正常就说正常。'
    '回复限制在200字以内。'
)

# Conversation context: store recent Q&A per session (in-memory, Phase 1)
# Key: session_id, Value: list of {role, content}
_session_context = {}
MAX_CONTEXT_MESSAGES = 10


def _get_context(session_id):
    """Get conversation context for a session."""
    return _session_context.get(session_id, [])


def _add_context(session_id, role, content):
    """Add a message to session context, keeping only recent messages."""
    if session_id not in _session_context:
        _session_context[session_id] = []
    _session_context[session_id].append({'role': role, 'content': content})
    # Keep only last N messages
    if len(_session_context[session_id]) > MAX_CONTEXT_MESSAGES:
        _session_context[session_id] = _session_context[session_id][-MAX_CONTEXT_MESSAGES:]


def _clear_context(session_id):
    """Clear conversation context for a session."""
    _session_context.pop(session_id, None)


def generate_command(user_input, device_type='linux', session_id=None):
    """
    Generate an SSH command from natural language input.

    Args:
        user_input: User's natural language description (string)
        device_type: Device type — linux/huawei_vrp/cisco_ios/generic
        session_id: Optional session ID for conversation context

    Returns:
        dict: {
            'command': 'df -h',
            'description': '查看磁盘使用情况',
            'risk_level': 'safe'
        }
        On error: {'error': 'error message'}
    """
    if not API_KEY:
        logger.error('STEPFUN_API_KEY not configured')
        return {'error': 'AI服务未配置，请联系管理员设置API Key'}

    system_prompt = DEVICE_PROMPTS.get(device_type, DEVICE_PROMPTS['generic'])

    # Build messages with optional conversation context
    messages = [{'role': 'system', 'content': system_prompt}]

    if session_id:
        context = _get_context(session_id)
        messages.extend(context)

    messages.append({'role': 'user', 'content': user_input})

    try:
        response = requests.post(
            f'{API_URL}/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}',
            },
            json={
                'model': MODEL,
                'messages': messages,
                'response_format': {'type': 'json_object'},
                'max_tokens': 500,
                'temperature': 0.3,  # Low temperature for precise commands
            },
            timeout=30,
        )
        response.raise_for_status()

        content = response.json()['choices'][0]['message']['content']
        command_info = json.loads(content)

        # Validate required fields
        if 'command' not in command_info:
            logger.warning('AI response missing command field: %s', content)
            return {'error': 'AI返回格式异常，缺少command字段'}

        # Ensure risk_level has a valid value
        risk = command_info.get('risk_level', 'safe')
        if risk not in ('safe', 'warning', 'danger'):
            risk = 'warning'
            command_info['risk_level'] = risk

        # Store context for conversation continuity
        if session_id:
            _add_context(session_id, 'user', user_input)
            _add_context(session_id, 'assistant', content)

        logger.info(
            'AI generated command: %s (risk=%s) for input: %s',
            command_info.get('command', ''),
            risk,
            user_input[:80],
        )
        return command_info

    except requests.exceptions.Timeout:
        logger.error('StepFun API timeout')
        return {'error': 'AI响应超时，请稍后重试'}
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else 'unknown'
        logger.error('StepFun API HTTP error %s: %s', status, str(e))
        return {'error': f'AI服务返回错误({status})，请稍后重试'}
    except json.JSONDecodeError:
        logger.error('StepFun API returned non-JSON: %s', content[:200])
        return {'error': 'AI返回格式异常，请重新描述您的需求'}
    except Exception as e:
        logger.error('StepFun API unexpected error: %s', str(e))
        return {'error': f'AI服务暂时不可用: {str(e)}'}


def analyze_result(command, result, device_type='linux'):
    """
    Analyze command execution result in natural language.

    Args:
        command: The executed command (string)
        result: Command output (string)
        device_type: Device type for context

    Returns:
        str: Chinese analysis of the result
    """
    if not API_KEY:
        return 'AI服务未配置，无法分析结果'

    # Truncate very long results
    truncated = result[:2000] if len(result) > 2000 else result

    user_prompt = (
        f'设备类型：{device_type}\n'
        f'执行的命令：{command}\n'
        f'执行结果：\n{truncated}\n\n'
        f'请用简洁的中文分析以上结果。'
    )

    try:
        response = requests.post(
            f'{API_URL}/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}',
            },
            json={
                'model': MODEL,
                'messages': [
                    {'role': 'system', 'content': ANALYSIS_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                'max_tokens': 300,
                'temperature': 0.3,
            },
            timeout=20,
        )
        response.raise_for_status()

        analysis = response.json()['choices'][0]['message']['content']
        logger.info('AI analyzed result for command: %s', command[:80])
        return analysis.strip()

    except Exception as e:
        logger.error('AI analyze error: %s', str(e))
        return '分析结果时发生错误，请自行查看命令输出'


def explain_command(command, device_type='linux'):
    """
    Explain a command in plain Chinese (for "解释命令" feature).

    Args:
        command: The command to explain (string)
        device_type: Device type for context

    Returns:
        str: Chinese explanation
    """
    if not API_KEY:
        return 'AI服务未配置'

    try:
        response = requests.post(
            f'{API_URL}/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}',
            },
            json={
                'model': MODEL,
                'messages': [
                    {
                        'role': 'system',
                        'content': '你是一个运维专家。请用简洁的中文解释以下命令的作用、参数含义和注意事项。回复限制在150字以内。',
                    },
                    {'role': 'user', 'content': f'设备类型：{device_type}\n命令：{command}'},
                ],
                'max_tokens': 300,
                'temperature': 0.3,
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()

    except Exception as e:
        logger.error('AI explain error: %s', str(e))
        return '解释命令时发生错误'
