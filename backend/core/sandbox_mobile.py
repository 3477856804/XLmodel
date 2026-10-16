# -*- coding: utf-8 -*-
"""小凌 · 移动端应用内沙箱。

为什么需要这个模块
==================
iOS 上 ``subprocess`` / shell 根本不可用（Apple 沙箱禁止 fork+exec 任意二进制）。
Android 上 Landlock / Seatbelt / Job Object 三种桌面隔离机制全部不可用。
当前代码（tools.py 的 run_command、multimodal.py 的 screencapture/scrot）在 iOS
会直接抛异常崩溃——这不是「降级」，是「炸了」。

本模块提供「应用内沙箱」——不 fork shell，而是把命令**解释**为受控动作：

    * 路径白名单（限制在沙箱 workspace 内）
    * 命令解析为白名单动作：列目录 / 读文件 / 写文件 / 移动 / 复制 / 搜索
    * 无法映射为白名单动作的任意 shell 命令一律拒绝

**绝不假装能执行任意 shell**——这是项目「降级要明说」的核心原则。
"""
from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
from pathlib import Path

logger = logging.getLogger('xiaoling.exec')

# ---- 平台检测 ----
def _detect_mobile_platform() -> str:
    """返回 'ios' / 'android' / ''（非移动平台返回空字符串）。"""
    # iOS: sys.platform == 'iphone' 或 'ipados'（Pythonista / pyto）
    # Android: sys.platform == 'android'（Termux / Chaquopy）
    import sys
    plat = getattr(sys, 'platform', '')
    if plat in ('iphone', 'ipados'):
        return 'ios'
    if plat == 'android':
        return 'android'
    # 环境变量兜底（Flutter 嵌入场景）
    if os.environ.get('XIAOLING_MOBILE_PLATFORM', '').lower() in ('ios', 'iphone'):
        return 'ios'
    if os.environ.get('XIAOLING_MOBILE_PLATFORM', '').lower() == 'android':
        return 'android'
    return ''


def is_mobile() -> bool:
    """当前是否运行在移动平台。"""
    return bool(_detect_mobile_platform())


# ---- 能力矩阵 ----
def get_mobile_info() -> dict:
    """返回移动平台信息与能力矩阵。

    非移动平台返回 ``platform=''`` 且 ``available=False``。
    """
    plat = _detect_mobile_platform()
    if not plat:
        return {
            'platform': '',
            'available': False,
            'capabilities': {
                'shell': False,
                'file_read': False,
                'file_write': False,
                'list_dir': False,
                'search': False,
                'move': False,
                'copy': False,
            },
            'reason': '非移动平台，不适用',
        }
    return {
        'platform': plat,
        'available': True,
        'capabilities': {
            'shell': False,        # 移动端不 fork shell
            'file_read': True,     # 白名单内路径可读
            'file_write': True,    # 白名单内路径可写
            'list_dir': True,      # 白名单内目录可列
            'search': True,        # 文件名搜索
            'move': True,          # 白名单内移动
            'copy': True,          # 白名单内复制
        },
        'reason': f'{plat} 应用内沙箱：不执行任意 shell，仅白名单动作',
    }


# ---- 白名单动作解析 ----
# 支持的命令模式（正则匹配）：
#   ls [path]          -> list_dir
#   cat path           -> read_file
#   echo "..." > path  -> write_file
#   mv src dst         -> move
#   cp src dst         -> copy
#   find path -name X  -> search
#   grep pattern path  -> search_content (简化为文件内搜索)

_ACTION_PATTERNS = [
    # ls [path]
    (re.compile(r'^ls(?:\s+(.+))?$'), 'list_dir'),
    # cat / head / tail path
    (re.compile(r'^(?:cat|head|tail)\s+(.+)$'), 'read_file'),
    # echo "content" > path  /  echo content > path
    (re.compile(r'^echo\s+(.+?)\s*>\s*(\S+)$'), 'write_file'),
    # mv src dst
    (re.compile(r'^mv\s+(\S+)\s+(\S+)$'), 'move'),
    # cp src dst
    (re.compile(r'^cp\s+(\S+)\s+(\S+)$'), 'copy'),
    # find path -name pattern
    (re.compile(r'^find\s+(\S+)\s+(?:.*-name\s+["\']?([^"\';\s]+)["\']?)'), 'search'),
    # grep pattern path
    (re.compile(r'^grep\s+["\']?([^"\';\s]+)["\']?\s+(\S+)'), 'search_content'),
    # pwd
    (re.compile(r'^pwd$'), 'pwd'),
]


def _resolve_in_workspace(rel_or_abs: str, workspace: Path) -> Path | None:
    """将路径解析到 workspace 内，越界返回 None。"""
    p = Path(rel_or_abs).expanduser()
    if not p.is_absolute():
        p = workspace / p
    try:
        p = p.resolve()
    except (OSError, ValueError):
        return None
    # 必须在 workspace 内
    ws_resolved = workspace.resolve()
    if p == ws_resolved or ws_resolved in p.parents:
        return p
    return None


def execute_mobile(command: str, workspace: str | None = None,
                   timeout: int = 30) -> dict:
    """在移动端应用内沙箱执行命令。

    **绝不 fork shell**。命令被解析为白名单动作，无法映射的一律拒绝。

    返回 dict 字段与 exec_gate.execute() 保持一致：
      ok, stdout, stderr, code, isolation, permission, blocked_reason, platform
    """
    plat = _detect_mobile_platform()
    if not plat:
        return {
            'ok': False,
            'stdout': '',
            'stderr': '非移动平台',
            'code': -1,
            'isolation': 'none',
            'permission': 'denied',
            'blocked_reason': 'sandbox_mobile 仅用于移动平台',
            'platform': '',
        }

    cmd = (command or '').strip()
    if not cmd:
        return {
            'ok': False, 'stdout': '', 'stderr': '命令为空', 'code': -1,
            'isolation': 'in-app', 'permission': 'denied',
            'blocked_reason': '命令为空',
            'platform': plat,
        }

    # 确定 workspace
    if workspace:
        ws = Path(workspace)
    else:
        try:
            from . import sandbox as _sb
            ws = _sb.workspace_dir()
        except Exception:
            ws = Path.cwd() / 'workspace'
    try:
        ws.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    # 匹配白名单动作
    action = None
    match = None
    for pattern, act in _ACTION_PATTERNS:
        m = pattern.match(cmd)
        if m:
            action = act
            match = m
            break

    if action is None:
        return {
            'ok': False,
            'stdout': '',
            'stderr': (f'命令无法映射为受控动作：{cmd[:80]}\n'
                       f'{plat} 应用内沙箱仅支持：ls / cat / echo> / mv / cp / find / grep / pwd\n'
                       f'不支持任意 shell 命令——这是平台安全限制，不是 bug。'),
            'code': -1,
            'isolation': 'in-app',
            'permission': 'denied',
            'blocked_reason': f'命令不在白名单内：{cmd[:60]}',
            'platform': plat,
        }

    # 执行白名单动作
    try:
        if action == 'pwd':
            return _ok_result(str(ws), plat)

        if action == 'list_dir':
            target = match.group(1) or '.'
            resolved = _resolve_in_workspace(target.strip(), ws)
            if resolved is None:
                return _denied(f'路径越界：{target}', plat)
            if not resolved.is_dir():
                return _err(f'不是目录：{resolved}', plat)
            items = []
            for p in sorted(resolved.iterdir(), key=lambda x: x.name)[:200]:
                prefix = 'd ' if p.is_dir() else '  '
                items.append(f'{prefix}{p.name}')
            return _ok_result('\n'.join(items), plat)

        if action == 'read_file':
            target = match.group(1).strip()
            resolved = _resolve_in_workspace(target, ws)
            if resolved is None:
                return _denied(f'路径越界：{target}', plat)
            if not resolved.is_file():
                return _err(f'不是文件或不存在：{resolved}', plat)
            content = resolved.read_text(encoding='utf-8', errors='replace')
            return _ok_result(content[:50000], plat)

        if action == 'write_file':
            content = match.group(1).strip().strip('"').strip("'")
            target = match.group(2).strip()
            resolved = _resolve_in_workspace(target, ws)
            if resolved is None:
                return _denied(f'路径越界：{target}', plat)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding='utf-8')
            return _ok_result(f'已写入 {resolved}', plat)

        if action == 'move':
            src_s = match.group(1).strip()
            dst_s = match.group(2).strip()
            src = _resolve_in_workspace(src_s, ws)
            dst = _resolve_in_workspace(dst_s, ws)
            if src is None:
                return _denied(f'源路径越界：{src_s}', plat)
            if dst is None:
                return _denied(f'目标路径越界：{dst_s}', plat)
            shutil.move(str(src), str(dst))
            return _ok_result(f'已移动 {src} -> {dst}', plat)

        if action == 'copy':
            src_s = match.group(1).strip()
            dst_s = match.group(2).strip()
            src = _resolve_in_workspace(src_s, ws)
            dst = _resolve_in_workspace(dst_s, ws)
            if src is None:
                return _denied(f'源路径越界：{src_s}', plat)
            if dst is None:
                return _denied(f'目标路径越界：{dst_s}', plat)
            if src.is_dir():
                shutil.copytree(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))
            return _ok_result(f'已复制 {src} -> {dst}', plat)

        if action == 'search':
            base_s = match.group(1).strip()
            pattern_s = match.group(2).strip().strip('"').strip("'")
            base = _resolve_in_workspace(base_s, ws)
            if base is None:
                return _denied(f'路径越界：{base_s}', plat)
            if not base.is_dir():
                return _err(f'不是目录：{base}', plat)
            results = []
            for p in base.rglob(f'*{pattern_s}*'):
                results.append(str(p.relative_to(ws)))
                if len(results) >= 100:
                    break
            return _ok_result('\n'.join(results) or '无匹配', plat)

        if action == 'search_content':
            pattern_s = match.group(1).strip()
            target_s = match.group(2).strip()
            resolved = _resolve_in_workspace(target_s, ws)
            if resolved is None:
                return _denied(f'路径越界：{target_s}', plat)
            if resolved.is_file():
                files = [resolved]
            elif resolved.is_dir():
                files = list(resolved.rglob('*'))[:200]
            else:
                return _err(f'不存在：{resolved}', plat)
            results = []
            for f in files:
                if not f.is_file():
                    continue
                try:
                    text = f.read_text(encoding='utf-8', errors='replace')
                    for i, line in enumerate(text.splitlines(), 1):
                        if pattern_s in line:
                            results.append(f'{f.relative_to(ws)}:{i}: {line[:100]}')
                            if len(results) >= 100:
                                break
                except OSError:
                    continue
                if len(results) >= 100:
                    break
            return _ok_result('\n'.join(results) or '无匹配', plat)

    except PermissionError as e:
        return _denied(str(e), plat)
    except Exception as e:
        return _err(f'{type(e).__name__}: {e}', plat)

    return _denied(f'未实现的动作：{action}', plat)


def _ok_result(stdout: str, plat: str) -> dict:
    return {
        'ok': True, 'stdout': stdout, 'stderr': '', 'code': 0,
        'isolation': 'in-app', 'permission': 'default',
        'blocked_reason': '',
        'platform': plat,
    }


def _denied(reason: str, plat: str) -> dict:
    logger.info('sandbox_mobile: 拒绝 - %s', reason)
    return {
        'ok': False, 'stdout': '', 'stderr': reason, 'code': -1,
        'isolation': 'in-app', 'permission': 'denied',
        'blocked_reason': reason,
        'platform': plat,
    }


def _err(msg: str, plat: str) -> dict:
    return {
        'ok': False, 'stdout': '', 'stderr': msg, 'code': -1,
        'isolation': 'in-app', 'permission': 'default',
        'blocked_reason': '',
        'platform': plat,
    }
