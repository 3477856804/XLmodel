# -*- coding: utf-8 -*-
"""小凌 · 统一执行入口（exec_gate）。

为什么要有这个模块
==================
修复 P0 安全漏洞：tools.py 的 run_command 工具直接 ``subprocess.run(cmd, shell=True)``
在宿主机裸跑任意命令——Agent 自主决策调用的工具完全绕过了沙箱。

本模块是**唯一的命令执行入口**，所有需要执行外部命令的地方一律调用
``exec_gate.execute()``。内部按平台分派：

    * 桌面（Linux / macOS / Windows）-> sandbox.run_sandboxed
    * 移动（iOS / Android）-> sandbox_mobile.execute_mobile
    * 两者都不可用 -> 如实返回 isolation="none" 且默认拒绝执行

策略层
======
    * 黑名单：rm -rf /、mkfs、dd of=/dev/、fork 炸弹等
    * 路径白名单：cwd 必须落在 guard_path 允许范围
    * 联网命令（curl/wget/pip/git push）按 permission 级别判定
    * 所有判定写日志（logging 到 'xiaoling.exec'）

返回 dict 字段清单（供前端与 server.py 对接）
=============================================
    ok              : bool    执行是否成功
    stdout          : str     标准输出
    stderr          : str     标准错误
    code            : int     退出码（失败时为 -1）
    cwd             : str     实际工作目录
    isolation       : str     实际使用的隔离级别
                                'landlock' / 'rlimit+chdir' / 'seatbelt' /
                                'job-object' / 'subprocess' / 'unrestricted' /
                                'in-app' / 'none'
    permission      : str     权限级别 'readonly' / 'default' / 'full' / 'denied'
    blocked_reason  : str     被拒绝的原因（空字符串表示未被拒绝）
    platform        : str     当前平台 'linux' / 'darwin' / 'windows' / 'ios' / 'android' / ''
    intent          : str     调用方传入的意图标签（透传，供前端展示）
    error           : str     （可选）异常时的错误信息
"""
from __future__ import annotations

import logging
import os
import platform
import re
from pathlib import Path

logger = logging.getLogger('xiaoling.exec')

# ---- 命令黑名单 ----
# 比 sandbox.py 的 _DENY_TOKENS 更全面：覆盖更多危险模式。
# 注意：黑名单是「提示性闸门」，真正的隔离靠 OS 级机制（Landlock 等）。
_BLACKLIST_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 破坏性删除
    (re.compile(r'rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|(-[a-zA-Z]*f[a-zA-Z]*r))\s+(/|~|\.\.)', re.I),
     '递归删除根目录/家目录'),
    (re.compile(r'rm\s+(-[a-zA-Z]+\s+)*(/\s*$|/\*)', re.I),
     '删除根目录'),
    (re.compile(r'del\s+/[fqs]\s+/', re.I), 'Windows 强制删除'),
    # 格式化/覆写磁盘
    (re.compile(r'mkfs\.', re.I), '格式化文件系统'),
    (re.compile(r'dd\s+.*of=/dev/', re.I), 'dd 写入设备'),
    (re.compile(r'dd\s+.*if=/dev/zero.*of=/dev/', re.I), 'dd 清零设备'),
    (re.compile(r'format\s+[a-zA-Z]:', re.I), 'Windows 格式化'),
    (re.compile(r'diskpart', re.I), 'Windows 磁盘分区'),
    # Fork 炸弹
    (re.compile(r':\(\)\s*\{'), 'fork 炸弹'),
    (re.compile(r'fork\s*bomb', re.I), 'fork 炸弹'),
    # 系统关机/重启
    (re.compile(r'\bshutdown\b', re.I), '关机命令'),
    (re.compile(r'\breboot\b', re.I), '重启命令'),
    (re.compile(r'\bhalt\b\s*$', re.I), '停机命令'),
    # 危险权限
    (re.compile(r'chmod\s+(-[Rr]\s+)?777\s+/', re.I), '全局 777 权限'),
    (re.compile(r'chmod\s+-[Rr]\s+777', re.I), '递归 777 权限'),
]

# ---- 联网命令检测 ----
# 这些命令会发起网络请求，readonly 档一律拒绝，default 档也拒绝（仅 full 放行）
_NETWORK_COMMANDS = re.compile(
    r'\b(curl|wget|pip3?\s+install|pip3?\s+download|npm\s+install|'
    r'git\s+push|git\s+clone|git\s+fetch|git\s+pull|'
    r'apt(-get)?\s+install|yum\s+install|brew\s+install|'
    r'cargo\s+install|gem\s+install)\b',
    re.I,
)


def _check_blacklist(command: str) -> str:
    """检查命令是否命中黑名单。返回拒绝原因，空字符串表示通过。"""
    cmd = command.strip()
    for pattern, reason in _BLACKLIST_PATTERNS:
        if pattern.search(cmd):
            return f'黑名单拦截（{reason}）：{cmd[:80]}'
    return ''


def _check_network(command: str, permission: str) -> str:
    """检查联网命令是否被允许。返回拒绝原因，空字符串表示通过。"""
    if permission == 'full':
        return ''
    if _NETWORK_COMMANDS.search(command):
        return (f'联网命令需要 full 权限（当前为 {permission}）。'
                f'如需执行，请在设置中提升权限级别或经用户确认。')
    return ''


def _check_security_policy(command: str) -> str:
    """按「安全中心」的权限配置判定本次执行。返回拒绝原因，空串表示放行。

    为什么需要：安全中心（core/security_center.py）此前能改开关、能存盘，
    但**没有任何执行路径读它** —— 设置页里把「terminal」关掉，命令照样跑。
    这里把判定接到唯一执行闸门上，开关才真正生效。

    兼容性：安全中心不可用（拿不到配置 / 未初始化）时一律放行，
    绝不因为"读不到安全配置"就把所有执行挡死。
    """
    try:
        try:
            from .security_center import get_security_center
        except Exception:                                        # noqa: BLE001
            from security_center import get_security_center      # type: ignore
        sc = get_security_center()
    except Exception as e:                                       # noqa: BLE001
        logger.debug('exec_gate: 安全中心不可用，跳过策略判定（%s）', e)
        return ''

    # 命令归类到安全中心的权限组
    lowered = command.lower()
    if _NETWORK_COMMANDS.search(command):
        group = 'network'
    elif lowered.startswith('git ') or lowered.startswith('git.exe '):
        group = 'git'
    else:
        group = 'terminal'

    try:
        verdict = sc.check_permission(group)
    except Exception as e:                                       # noqa: BLE001
        logger.debug('exec_gate: 安全中心判定异常，放行（%s）', e)
        return ''
    if not verdict.get('allowed', True):
        return (f'安全中心已关闭「{group}」权限（设置 → 安全中心可重新开启）。'
                f'已拒绝执行：{command[:80]}')
    return ''


def _check_cwd(cwd: str | None) -> tuple[str | None, str]:
    """检查 cwd 是否在沙箱白名单内。返回 (resolved_cwd, 拒绝原因)。"""
    if cwd is None:
        return None, ''
    try:
        from . import sandbox as _sb
        resolved = _sb.guard_path(cwd)
        return str(resolved), ''
    except PermissionError as e:
        return None, f'cwd 路径越界：{e}'
    except Exception as e:
        return None, f'cwd 检查异常：{e}'


def _is_desktop() -> bool:
    """当前是否为桌面平台（能跑 subprocess + OS 级沙箱）。"""
    return platform.system() in ('Linux', 'Darwin', 'Windows')


def _is_mobile() -> bool:
    """当前是否为移动平台。"""
    try:
        from . import sandbox_mobile as _sm
        return _sm.is_mobile()
    except Exception:
        return False


def execute(command: str, *,
            permission: str = 'default',
            timeout: int = 30,
            cwd: str | None = None,
            intent: str = '') -> dict:
    """统一执行入口。

    Parameters
    ----------
    command : str
        要执行的命令。
    permission : str
        权限级别：'readonly' / 'default' / 'full'。
        对应 sandbox.PERM_* 常量。
    timeout : int
        超时秒数。
    cwd : str or None
        工作目录。None 时使用沙箱 workspace。
    intent : str
        调用意图标签（透传到返回值，供前端展示）。

    Returns
    -------
    dict
        字段清单见模块文档字符串。
    """
    cmd = (command or '').strip()
    if not cmd:
        return _result(ok=False, error='命令为空', permission=permission,
                       intent=intent)

    # 规范化 permission
    if permission not in ('readonly', 'default', 'full'):
        permission = 'default'

    # 1) 黑名单检查
    block_reason = _check_blacklist(cmd)
    if block_reason:
        logger.warning('exec_gate: 黑名单拒绝 intent=%s cmd=%s reason=%s',
                       intent, cmd[:80], block_reason)
        return _result(ok=False, blocked_reason=block_reason,
                       permission='denied', intent=intent)

    # 2) 安全中心策略（设置页的权限开关在这里真正生效）
    policy_reason = _check_security_policy(cmd)
    if policy_reason:
        logger.warning('exec_gate: 安全中心拒绝 intent=%s cmd=%s reason=%s',
                       intent, cmd[:80], policy_reason)
        return _result(ok=False, blocked_reason=policy_reason,
                       permission='denied', intent=intent)

    # 3) 联网命令检查
    net_reason = _check_network(cmd, permission)
    if net_reason:
        logger.info('exec_gate: 联网命令拒绝 intent=%s cmd=%s reason=%s',
                    intent, cmd[:80], net_reason)
        return _result(ok=False, blocked_reason=net_reason,
                       permission=permission, intent=intent)

    # 4) cwd 路径检查
    resolved_cwd, cwd_reason = _check_cwd(cwd)
    if cwd_reason:
        logger.warning('exec_gate: cwd 拒绝 intent=%s cwd=%s reason=%s',
                       intent, cwd, cwd_reason)
        return _result(ok=False, blocked_reason=cwd_reason,
                       permission=permission, intent=intent)

    # 5) 按平台分派
    if _is_mobile():
        return _execute_mobile(cmd, permission=permission, timeout=timeout,
                               cwd=resolved_cwd, intent=intent)
    if _is_desktop():
        return _execute_desktop(cmd, permission=permission, timeout=timeout,
                                cwd=resolved_cwd, intent=intent)

    # 6) 未知平台：默认拒绝
    logger.error('exec_gate: 未知平台，拒绝执行 intent=%s cmd=%s', intent, cmd[:80])
    return _result(
        ok=False,
        blocked_reason=(
            f'未知平台（{platform.system()}），无法确定安全隔离方式，'
            f'默认拒绝执行。如需支持，请联系开发者添加该平台的沙箱实现。'
        ),
        permission='denied',
        isolation='none',
        intent=intent,
    )


def _execute_desktop(command: str, *, permission: str, timeout: int,
                     cwd: str | None, intent: str) -> dict:
    """桌面平台：走 sandbox.run_sandboxed。"""
    try:
        from . import sandbox as _sb
    except ImportError:
        logger.error('exec_gate: sandbox 模块不可用，拒绝执行')
        return _result(
            ok=False,
            blocked_reason='sandbox 模块不可用，无法提供安全执行环境。'
                           '请确认安装完整。',
            permission='denied', isolation='none', intent=intent,
        )

    perm_map = {
        'readonly': _sb.PERM_READONLY,
        'default': _sb.PERM_DEFAULT,
        'full': _sb.PERM_FULL,
    }
    sb_perm = perm_map.get(permission, _sb.PERM_DEFAULT)

    logger.info('exec_gate: 桌面执行 intent=%s perm=%s cmd=%s',
                intent, permission, command[:80])

    try:
        res = _sb.run_sandboxed(command, permission_level=sb_perm,
                                cwd=cwd, timeout=timeout)
    except Exception as e:
        logger.error('exec_gate: sandbox.run_sandboxed 异常: %s', e)
        return _result(ok=False, error=f'sandbox 执行异常：{e}',
                       permission=permission, isolation='none', intent=intent)

    # 透传 sandbox 返回字段，补充 exec_gate 额外字段
    out = res.get('stdout', '') or ''
    err = res.get('stderr', '') or ''
    # 拒绝原因：只要 ok 为假就要带出去。旧写法额外要求
    # `'stdout' not in res`，可沙箱在「执行了一半又被拒」时会同时带
    # ok=False 与 stdout —— 那种情况下原因被整个丢掉，前端只能显示
    # 「失败」两个字，用户不知道是被黑名单拦了还是超时。
    reason = '' if res.get('ok') else (res.get('error')
                                       or res.get('blocked_reason') or '')
    ret = {
        'ok': res.get('ok', False),
        'stdout': out,
        'stderr': err,
        'code': res.get('code', -1 if not res.get('ok') else 0),
        'cwd': res.get('cwd', cwd or ''),
        'isolation': res.get('isolation', 'unknown'),
        'permission': res.get('permission', permission),
        'blocked_reason': reason,
        'platform': res.get('platform', platform.system().lower()),
        'intent': intent,
        'error': reason,
    }
    # 降级守卫的标记要一路带到前端：界面得能说清「这次拦下你的是词法检查，
    # 不是 OS 级隔离」，否则用户以为沙箱有多强。
    # shell 同理：Windows 上到底走的是 bash 还是 cmd，直接决定 ls 能不能用，
    # 前端要能据此告诉用户「这台机器没装 Git Bash，POSIX 命令跑不了」。
    for k in ('guard', 'note', 'offending', 'shell'):
        if k in res:
            ret[k] = res[k]
    return ret


def _execute_mobile(command: str, *, permission: str, timeout: int,
                    cwd: str | None, intent: str) -> dict:
    """移动平台：走 sandbox_mobile.execute_mobile。"""
    try:
        from . import sandbox_mobile as _sm
    except ImportError:
        logger.error('exec_gate: sandbox_mobile 模块不可用')
        return _result(
            ok=False,
            blocked_reason='sandbox_mobile 模块不可用，移动端无法执行命令。',
            permission='denied', isolation='none', intent=intent,
        )

    logger.info('exec_gate: 移动端执行 intent=%s perm=%s cmd=%s',
                intent, permission, command[:80])

    res = _sm.execute_mobile(command, workspace=cwd, timeout=timeout)

    return {
        'ok': res.get('ok', False),
        'stdout': res.get('stdout', ''),
        'stderr': res.get('stderr', ''),
        'code': res.get('code', -1),
        'cwd': cwd or '',
        'isolation': res.get('isolation', 'in-app'),
        'permission': res.get('permission', permission),
        'blocked_reason': res.get('blocked_reason', ''),
        'platform': res.get('platform', ''),
        'intent': intent,
    }


def _result(*, ok: bool, error: str = '', blocked_reason: str = '',
            permission: str = 'default', isolation: str = 'none',
            intent: str = '') -> dict:
    """构造一个拒绝/错误的返回 dict。"""
    plat = platform.system().lower() if platform.system() in (
        'Linux', 'Darwin', 'Windows') else ''
    return {
        'ok': ok,
        'stdout': '',
        'stderr': error or blocked_reason,
        'code': -1,
        'cwd': '',
        'isolation': isolation,
        'permission': permission,
        'blocked_reason': blocked_reason or error,
        'platform': plat,
        'intent': intent,
        'error': error or blocked_reason,
    }
