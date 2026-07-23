/**
 * AI Assistant for TKAI SSH.
 * Provides natural language to SSH command conversion via sidebar UI.
 */

const AIAssistant = (function () {
    let sidebar = null;
    let chatArea = null;
    let input = null;
    let sendBtn = null;
    let deviceSelect = null;
    let isOpen = false;
    let isWaiting = false;

    const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const APP_ROOT = document.querySelector('meta[name="app-root"]')?.content || '';

    function init() {
        createSidebar();
        createToggleButton();
        bindEvents();
        checkStatus();
    }

    function createSidebar() {
        sidebar = document.createElement('div');
        sidebar.className = 'ai-sidebar';
        sidebar.id = 'aiSidebar';
        sidebar.innerHTML = `
            <div class="ai-sidebar-header">
                <h3 class="ai-sidebar-title">AI 助手</h3>
                <div class="ai-sidebar-actions">
                    <button class="ai-btn-icon" id="aiClearBtn" title="清除对话">↺</button>
                    <button class="ai-btn-icon" id="aiCloseBtn" title="收起">✕</button>
                </div>
            </div>
            <div class="ai-chat-area" id="aiChatArea"></div>
            <div class="ai-input-area">
                <select class="ai-device-select" id="aiDeviceSelect">
                    <option value="linux">Linux 服务器</option>
                    <option value="huawei_vrp">华为设备 (VRP)</option>
                    <option value="cisco_ios">思科设备 (IOS)</option>
                    <option value="generic">通用网络设备</option>
                </select>
                <div class="ai-input-wrapper">
                    <textarea class="ai-input" id="aiInput" placeholder="用自然语言描述你想做什么..."
                        rows="1" maxlength="500"></textarea>
                    <button class="ai-send-btn" id="aiSendBtn" title="发送">➤</button>
                </div>
            </div>
        `;
        document.body.appendChild(sidebar);

        chatArea = document.getElementById('aiChatArea');
        input = document.getElementById('aiInput');
        sendBtn = document.getElementById('aiSendBtn');
        deviceSelect = document.getElementById('aiDeviceSelect');
    }

    function createToggleButton() {
        const btn = document.createElement('button');
        btn.className = 'ai-toggle-btn';
        btn.id = 'aiToggleBtn';
        btn.title = 'AI 助手';
        btn.innerHTML = '<span>AI</span><span class="ai-toggle-label">助手</span>';
        btn.onclick = toggle;
        document.body.appendChild(btn);
    }

    function bindEvents() {
        document.getElementById('aiCloseBtn').onclick = close;
        document.getElementById('aiClearBtn').onclick = clearChat;
        sendBtn.onclick = sendMessage;

        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        input.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 100) + 'px';
        });
    }

    function toggle() {
        isOpen ? close() : open();
    }

    function open() {
        sidebar.classList.add('open');
        isOpen = true;
        setTimeout(() => input.focus(), 300);
    }

    function close() {
        sidebar.classList.remove('open');
        isOpen = false;
    }

    function getActiveSessionId() {
        if (typeof SessionManager !== 'undefined' && SessionManager.getActiveSession) {
            return SessionManager.getActiveSession();
        }
        return null;
    }

    function checkStatus() {
        fetch(`${APP_ROOT}/api/ai/status`)
            .then(r => r.json())
            .then(data => {
                if (data.success && data.data.configured) {
                    addSystemMessage('AI 助手已就绪（模型：' + data.data.model + '）');
                } else {
                    addSystemMessage('AI 助手未配置，请联系管理员设置 API Key');
                    sendBtn.disabled = true;
                    input.disabled = true;
                    input.placeholder = 'AI 服务未配置';
                }
            })
            .catch(() => {
                addSystemMessage('AI 助手状态检查失败');
            });
    }

    function sendMessage() {
        const message = input.value.trim();
        if (!message || isWaiting) return;

        const sessionId = getActiveSessionId();
        if (!sessionId) {
            addErrorMessage('请先连接一台 SSH 设备，然后才能使用 AI 助手');
            return;
        }

        addUserMessage(message);
        input.value = '';
        input.style.height = 'auto';
        setWaiting(true);

        const deviceType = deviceSelect.value;

        fetch(`${APP_ROOT}/api/ai/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF,
            },
            body: JSON.stringify({
                message: message,
                device_type: deviceType,
                session_id: sessionId,
            }),
        })
            .then(r => r.json())
            .then(data => {
                setWaiting(false);
                if (data.success) {
                    showCommandCard(data.data, sessionId, deviceType);
                } else if (data.blocked) {
                    addErrorMessage('已拦截：' + data.error);
                } else {
                    addErrorMessage(data.error || 'AI 生成命令失败');
                }
            })
            .catch(err => {
                setWaiting(false);
                addErrorMessage('网络错误：' + err.message);
            });
    }

    function showCommandCard(cmdInfo, sessionId, deviceType) {
        const card = document.createElement('div');
        card.className = `ai-command-card risk-${cmdInfo.risk_level}`;

        const badgeText = {
            safe: '安全',
            warning: '警告',
            danger: '危险',
        };

        card.innerHTML = `
            <div class="ai-command-badge ${cmdInfo.risk_level}">${badgeText[cmdInfo.risk_level] || '未知'}</div>
            <div class="ai-command-code">${escapeHtml(cmdInfo.command)}</div>
            <div class="ai-command-desc">${escapeHtml(cmdInfo.description || '')}</div>
            <div class="ai-command-actions">
                <button class="ai-btn ai-btn-primary" data-action="execute">执行</button>
                <button class="ai-btn ai-btn-secondary" data-action="explain">解释</button>
                <button class="ai-btn ai-btn-secondary" data-action="cancel">取消</button>
            </div>
        `;

        chatArea.appendChild(card);
        scrollToBottom();

        const executeBtn = card.querySelector('[data-action="execute"]');
        const explainBtn = card.querySelector('[data-action="explain"]');
        const cancelBtn = card.querySelector('[data-action="cancel"]');

        executeBtn.onclick = () => executeCommand(cmdInfo.command, sessionId, deviceType, card);
        explainBtn.onclick = () => explainCmd(cmdInfo.command, deviceType, card);
        cancelBtn.onclick = () => {
            card.querySelector('.ai-command-actions').remove();
            addSystemMessage('已取消');
        };
    }

    function executeCommand(command, sessionId, deviceType, card) {
        const actions = card.querySelector('.ai-command-actions');
        if (actions) {
            actions.innerHTML = '<span style="color:#999;font-size:12px">执行中...</span>';
        }

        addSystemMessage('正在执行：' + command);

        fetch(`${APP_ROOT}/api/ai/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF,
            },
            body: JSON.stringify({
                session_id: sessionId,
                command: command,
            }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    showResult(data.data.result);
                    addSystemMessage('退出码：' + data.data.exit_code);

                    if (data.data.exit_code === 0 && data.data.result.trim()) {
                        analyzeCmdResult(command, data.data.result, deviceType);
                    }
                } else if (data.blocked) {
                    addErrorMessage('命令被拦截：' + data.error);
                } else {
                    addErrorMessage(data.error || '执行失败');
                }

                if (actions) {
                    actions.innerHTML = '<span style="color:#4caf50;font-size:12px">已完成</span>';
                }
            })
            .catch(err => {
                addErrorMessage('网络错误：' + err.message);
                if (actions) {
                    actions.innerHTML = '<span style="color:#f44336;font-size:12px">执行出错</span>';
                }
            });
    }

    function analyzeCmdResult(command, result, deviceType) {
        addTyping();

        fetch(`${APP_ROOT}/api/ai/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF,
            },
            body: JSON.stringify({
                command: command,
                result: result,
                device_type: deviceType,
            }),
        })
            .then(r => r.json())
            .then(data => {
                removeTyping();
                if (data.success) {
                    addAnalysisMessage(data.data.analysis);
                }
            })
            .catch(() => {
                removeTyping();
            });
    }

    function explainCmd(command, deviceType, card) {
        const explainBtn = card.querySelector('[data-action="explain"]');
        if (explainBtn) {
            explainBtn.disabled = true;
            explainBtn.textContent = '解释中...';
        }

        fetch(`${APP_ROOT}/api/ai/explain`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF,
            },
            body: JSON.stringify({
                command: command,
                device_type: deviceType,
            }),
        })
            .then(r => r.json())
            .then(data => {
                if (explainBtn) {
                    explainBtn.disabled = false;
                    explainBtn.textContent = '解释';
                }
                if (data.success) {
                    addAssistantMessage('命令解释：' + data.data.explanation);
                } else {
                    addErrorMessage(data.error || '解释失败');
                }
            })
            .catch(err => {
                if (explainBtn) {
                    explainBtn.disabled = false;
                    explainBtn.textContent = '解释';
                }
                addErrorMessage('网络错误：' + err.message);
            });
    }

    function clearChat() {
        const sessionId = getActiveSessionId();
        chatArea.innerHTML = '';

        if (sessionId) {
            fetch(`${APP_ROOT}/api/ai/clear`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF,
                },
                body: JSON.stringify({ session_id: sessionId }),
            }).catch(() => {});
        }

        addSystemMessage('对话已清除');
    }

    function setWaiting(waiting) {
        isWaiting = waiting;
        sendBtn.disabled = waiting;
        if (waiting) {
            addTyping();
        } else {
            removeTyping();
        }
    }

    function addUserMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'ai-message user';
        msg.textContent = text;
        chatArea.appendChild(msg);
        scrollToBottom();
    }

    function addAssistantMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'ai-message assistant';
        msg.textContent = text;
        chatArea.appendChild(msg);
        scrollToBottom();
    }

    function addSystemMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'ai-message system';
        msg.textContent = text;
        chatArea.appendChild(msg);
        scrollToBottom();
    }

    function addErrorMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'ai-message error';
        msg.textContent = text;
        chatArea.appendChild(msg);
        scrollToBottom();
    }

    function showResult(text) {
        const msg = document.createElement('div');
        msg.className = 'ai-message result';
        msg.textContent = text;
        chatArea.appendChild(msg);
        scrollToBottom();
    }

    function addAnalysisMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'ai-message analysis';
        msg.textContent = 'AI 分析：' + text;
        chatArea.appendChild(msg);
        scrollToBottom();
    }

    function addTyping() {
        const existing = document.getElementById('aiTyping');
        if (existing) return;
        const msg = document.createElement('div');
        msg.className = 'ai-typing';
        msg.id = 'aiTyping';
        msg.textContent = 'AI 正在思考';
        chatArea.appendChild(msg);
        scrollToBottom();
    }

    function removeTyping() {
        const existing = document.getElementById('aiTyping');
        if (existing) existing.remove();
    }

    function scrollToBottom() {
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Auto-init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return { open, close, toggle };
})();
