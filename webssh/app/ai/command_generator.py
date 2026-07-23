"""
Command safety checker and risk evaluator.
Validates AI-generated commands before execution.
"""

import re
import logging

logger = logging.getLogger('webssh')

# Danger patterns — these commands can cause irreversible damage
DANGER_PATTERNS = [
    r'rm\s+(-rf|--force)\s+/',
    r'rm\s+(-rf|--force)\s+\*',
    r'mkfs\w*',
    r'dd\s+.*if=/dev/zero',
    r'dd\s+.*of=/dev/sd',
    r'dd\s+.*of=/dev/nvme',
    r'shutdown',
    r'reboot',
    r'init\s+[06]',
    r'halt',
    r'poweroff',
    r':\(\)\s*\{\s*:|:\&\s*\};',  # fork bomb
    r'>\s*/dev/sda',
    r'chmod\s+-R\s+777\s+/',
    r'chown\s+-R\s+.*\s+/',
    r'iptables\s+-F\s*$',  # flush all firewall rules
    r'ip\s+route\s+del\s+default',
    r'\bsystemctl\s+(stop|disable)\s+(ssh|sshd|networking)\b',
    r'\biptables\s+-P\s+(INPUT|OUTPUT|FORWARD)\s+DROP',
    r'wipefs',
    r'shred\s+/dev/sd',
]

# Warning patterns — these commands modify system state
WARNING_PATTERNS = [
    r'^\s*iptables\b',
    r'^\s*systemctl\s+(stop|disable|restart)\b',
    r'^\s*service\s+\w+\s+(stop|restart)\b',
    r'^\s*(yum|apt|dnf)\s+(install|remove|upgrade|update)\b',
    r'^\s*pip\s+install\b',
    r'^\s*kill\b',
    r'^\s*pkill\b',
    r'^\s*killall\b',
    r'^\s*usermod\b',
    r'^\s*userdel\b',
    r'^\s*groupdel\b',
    r'^\s*chmod\b',
    r'^\s*chown\b',
    r'^\s*mount\b',
    r'^\s*umount\b',
    r'^\s*fdisk\b',
    r'^\s*parted\b',
    r'^\s*lvremove\b',
    r'^\s*vgremove\b',
    r'^\s*crontab\b',
    r'^\s*visudo\b',
    r'^\s*echo.*>>\s*/etc/',
    r'^\s*sed\s+-i\b',
    r'^\s*cp\s+.*\s+/etc/',
    r'^\s*mv\s+.*\s+/etc/',
]

# Safe patterns — these commands only read system state
SAFE_PATTERNS = [
    r'^\s*ls\b',
    r'^\s*cat\b',
    r'^\s*head\b',
    r'^\s*tail\b',
    r'^\s*less\b',
    r'^\s*more\b',
    r'^\s*grep\b',
    r'^\s*find\b',
    r'^\s*df\b',
    r'^\s*du\b',
    r'^\s*free\b',
    r'^\s*top\b',
    r'^\s*htop\b',
    r'^\s*ps\b',
    r'^\s*uname\b',
    r'^\s*uptime\b',
    r'^\s*who\b',
    r'^\s*w\b',
    r'^\s*id\b',
    r'^\s*date\b',
    r'^\s*cal\b',
    r'^\s*echo\b(?!\s*.*>>)',  # echo without redirect
    r'^\s*pwd\b',
    r'^\s*which\b',
    r'^\s*whereis\b',
    r'^\s*stat\b',
    r'^\s*file\b',
    r'^\s*wc\b',
    r'^\s*sort\b',
    r'^\s*uniq\b',
    r'^\s*cut\b',
    r'^\s*awk\b(?!\s+.*-i)',  # awk without in-place edit
    r'^\s*sed\b(?!\s+.*-i)',  # sed without -i flag
    r'^\s*ip\b(?!\s+.*(add|del|set|route\s+(add|del)))',  # ip show commands
    r'^\s*ifconfig\b(?!\s+.*\d+\s)',  # ifconfig without setting IP
    r'^\s*netstat\b',
    r'^\s*ss\b',
    r'^\s*lsof\b',
    r'^\s*dmidecode\b',
    r'^\s*lscpu\b',
    r'^\s*lsmem\b',
    r'^\s*lsblk\b',
    r'^\s*lspci\b',
    r'^\s*lsusb\b',
    r'^\s*dmesg\b',
    r'^\s*journalctl\b',
    r'^\s*systemctl\s+(status|list-units|list-unit-files|show|cat)\b',
    r'^\s*docker\s+(ps|images|logs|inspect|stats|top)\b',
    r'^\s*display\b',  # Huawei VRP show equivalent
    r'^\s*show\b',  # Cisco IOS show
    r'^\s*ping\b',
    r'^\s*traceroute\b',
    r'^\s*nslookup\b',
    r'^\s*dig\b',
    r'^\s*host\b',
]

# Commands that require interactive input — block these
INTERACTIVE_PATTERNS = [
    r'^\s*vim\b',
    r'^\s*vi\b',
    r'^\s*nano\b',
    r'^\s*emacs\b',
    r'^\s*top\b',  # top runs interactively
    r'^\s*htop\b',
    r'^\s*less\b',
    r'^\s*more\b',
    r'^\s*man\b',
    r'^\s*passwd\b',  # requires interactive input
    r'^\s*sudo\s+passwd\b',
    r'^\s*mysql\b(?!\s+.*-e)',  # mysql without -e flag
    r'^\s*psql\b(?!\s+.*-c)',  # psql without -c flag
]


def check_danger(command):
    """
    Check if a command is dangerous.

    Returns:
        (is_dangerous: bool, reason: str)
    """
    cmd_stripped = command.strip()

    for pattern in DANGER_PATTERNS:
        if re.search(pattern, cmd_stripped, re.IGNORECASE):
            return True, f'检测到危险命令模式：{pattern}'

    return False, ''


def get_risk_level(command):
    """
    Evaluate the risk level of a command.

    Returns:
        str: 'safe', 'warning', or 'danger'
    """
    cmd_stripped = command.strip()
    if not cmd_stripped:
        return 'safe'

    # Check danger first
    is_danger, _ = check_danger(cmd_stripped)
    if is_danger:
        return 'danger'

    # Check safe patterns
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, cmd_stripped, re.IGNORECASE):
            return 'safe'

    # Check warning patterns
    for pattern in WARNING_PATTERNS:
        if re.search(pattern, cmd_stripped, re.IGNORECASE):
            return 'warning'

    # Unknown command — default to warning
    return 'warning'


def check_interactive(command):
    """
    Check if a command requires interactive input (not suitable for exec_command).

    Returns:
        (is_interactive: bool, reason: str)
    """
    cmd_stripped = command.strip()

    for pattern in INTERACTIVE_PATTERNS:
        if re.search(pattern, cmd_stripped, re.IGNORECASE):
            return True, f'该命令需要交互式输入，请在终端中手动执行'

    return False, ''


def validate_command(command_info):
    """
    Validate an AI-generated command info dict.

    Args:
        command_info: dict with 'command', 'description', 'risk_level'

    Returns:
        (is_valid: bool, error: str, risk_level: str)
    """
    if not command_info or 'command' not in command_info:
        return False, 'AI返回格式错误：缺少command字段', 'warning'

    command = command_info['command'].strip()
    if not command:
        return False, 'AI生成的命令为空', 'warning'

    # Check for interactive commands
    is_interactive, reason = check_interactive(command)
    if is_interactive:
        return False, reason, 'warning'

    # Re-evaluate risk level (override AI's assessment)
    actual_risk = get_risk_level(command)

    # If AI says safe but we detect danger, override
    if actual_risk == 'danger':
        return False, f'检测到危险命令，已拦截：{command}', 'danger'

    return True, '', actual_risk


def get_danger_commands_list():
    """Return list of danger command patterns for display in UI."""
    return [
        'rm -rf /',
        'mkfs (格式化磁盘)',
        'dd if=/dev/zero (覆写磁盘)',
        'shutdown / reboot / halt',
        'fork bomb',
        'iptables -F (清空防火墙)',
        'iptables -P ... DROP (封锁所有流量)',
        'chmod -R 777 / (全盘权限)',
        'wipefs / shred (擦除磁盘)',
    ]
