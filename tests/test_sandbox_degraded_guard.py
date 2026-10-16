# -*- coding: utf-8 -*-
"""降级沙箱的词法路径守卫 + exec_gate 拒绝原因透传。

为什么单独一个文件：这些用例守的是「**降级时不许假装安全**」这条红线，
和 test_sandbox.py 里那些「沙箱功能是否可用」的用例是两回事。

背景（实测，不是推测）：本机内核 5.10，Landlock 探测失败，
run_sandboxed 走的是 `rlimit+chdir` 分支 —— 只 chdir，不做任何路径限制。
修复前 `run_sandboxed('cat ../../../../etc/passwd')` 返回 ok=True 并真的
读到了内容。
"""

import sys

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / 'backend')):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.core import sandbox as sb          # noqa: E402


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """把沙箱各目录指到 tmp，避免污染真实工作区。"""
    ws = tmp_path / 'workspace'
    ws.mkdir()
    monkeypatch.setattr(sb, 'root', lambda: tmp_path)
    monkeypatch.setattr(sb, 'workspace_dir', lambda: ws)
    monkeypatch.setattr(sb, 'tmp_dir', lambda: tmp_path / 'tmp')
    monkeypatch.setattr(sb, 'models_dir', lambda: tmp_path / 'models')
    sb.ensure()
    return ws


# ---------------------------------------------------------------- 词法守卫本体
def test_guard_blocks_relative_escape(home):
    r = sb.lexical_escape_check('cat ../../../../etc/shadow', str(home),
                                sb.PERM_DEFAULT)
    assert r['ok'] is False
    assert r['offending'] == ['../../../../etc/shadow']
    assert r['guard'] == 'lexical'
    # 降级说明必须在 note 里，不许只给一个布尔
    assert '不是安全边界' in r['note']


def test_guard_blocks_home_dir_read(home):
    r = sb.lexical_escape_check('cat ~/.ssh/id_rsa', str(home), sb.PERM_DEFAULT)
    assert r['ok'] is False
    assert any('id_rsa' in x for x in r['offending'])


def test_guard_blocks_other_users_home(home):
    r = sb.lexical_escape_check('rm -rf /home/someone/proj', str(home),
                                sb.PERM_DEFAULT)
    assert r['ok'] is False
    assert '/home/someone/proj' in r['offending']


def test_guard_blocks_windows_style_escape(home):
    r = sb.lexical_escape_check('type ..\\..\\Windows\\win.ini', str(home),
                                sb.PERM_DEFAULT)
    assert r['ok'] is False, 'Windows 分隔符的相对逃逸同样要拦'


def test_guard_allows_workspace_relative(home):
    (home / 'a.txt').write_text('x')
    for cmd in ('echo hi', 'ls', 'cat a.txt', 'cat ./a.txt', 'df -h'):
        r = sb.lexical_escape_check(cmd, str(home), sb.PERM_DEFAULT)
        assert r['ok'] is True, cmd


def test_guard_allows_inside_absolute_paths(home):
    r = sb.lexical_escape_check(f'cat {home / "a.txt"}', str(home),
                                sb.PERM_DEFAULT)
    assert r['ok'] is True


def test_guard_does_not_make_degraded_stricter_than_landlock(home):
    """系统只读目录必须放行 —— 它在 Landlock 下本来就是允许的。

    若这里改成拦，降级模式就比真隔离更严，同一份命令换台机器就跑不动，
    用户会认为沙箱在乱拦活。
    """
    for cmd in ('cat /etc/passwd', 'ls /usr/lib', 'cat /bin/sh'):
        r = sb.lexical_escape_check(cmd, str(home), sb.PERM_DEFAULT)
        assert r['ok'] is True, cmd


def test_guard_full_permission_skips_check(home):
    """full 档是用户显式授权的「不做隔离」，不该被词法守卫偷偷加限制。"""
    r = sb.lexical_escape_check('cat ~/.ssh/id_rsa', str(home), sb.PERM_FULL)
    assert r['ok'] is True


# ---------------------------------------------------------------- run_sandboxed
def test_run_sandboxed_degraded_blocks_escape(home, monkeypatch):
    monkeypatch.setattr(sb, '_landlock_supported', lambda: False)
    res = sb.run_sandboxed(f'cat {Path.home() / ".ssh" / "id_rsa"}',
                           permission_level=sb.PERM_DEFAULT)
    assert res['ok'] is False
    assert res.get('guard') == 'lexical'
    assert 'id_rsa' in res['error']
    # 关键：真的没读到内容
    assert 'BEGIN' not in (res.get('stdout') or '')
    assert res['isolation'] == 'rlimit+chdir'


def test_run_sandboxed_degraded_still_runs_normal(home, monkeypatch):
    monkeypatch.setattr(sb, '_landlock_supported', lambda: False)
    (home / 'ok.txt').write_text('payload-42')
    res = sb.run_sandboxed('cat ok.txt', permission_level=sb.PERM_DEFAULT)
    assert res['ok'] is True, res
    assert 'payload-42' in res['stdout']
    assert 'guard' not in res


def test_run_sandboxed_real_isolation_does_not_use_lexical(home, monkeypatch):
    """Landlock 可用时不该走词法守卫（真隔离更强，也不该多此一举）。"""
    called = {'n': 0}
    real = sb.lexical_escape_check

    def spy(*a, **k):
        called['n'] += 1
        return real(*a, **k)

    monkeypatch.setattr(sb, 'lexical_escape_check', spy)
    monkeypatch.setattr(sb, '_landlock_supported', lambda: True)
    monkeypatch.setattr(sb, '_apply_landlock', lambda w, p: True)
    res = sb.run_sandboxed('echo alive', permission_level=sb.PERM_DEFAULT)
    assert called['n'] == 0, '真隔离可用时不应启用词法守卫'
    assert res['isolation'] == 'landlock'


def test_run_sandboxed_full_reports_unrestricted(home, monkeypatch):
    monkeypatch.setattr(sb, '_landlock_supported', lambda: False)
    res = sb.run_sandboxed('echo x', permission_level=sb.PERM_FULL)
    assert res['isolation'] == 'unrestricted'
    assert 'guard' not in res


# ---------------------------------------------------------------- capability
def test_capability_reports_degradation_honestly(home, monkeypatch):
    monkeypatch.setattr(sb, '_landlock_supported', lambda: False)
    cap = sb.capability()
    assert cap['path_isolation'] is False, '词法守卫不得冒充路径隔离'
    assert cap['lexical_guard'] is True
    assert '非完整路径隔离' in cap['notes']


def test_capability_with_real_isolation(home, monkeypatch):
    monkeypatch.setattr(sb, '_landlock_supported', lambda: True)
    cap = sb.capability()
    assert cap['path_isolation'] is True
    assert cap['lexical_guard'] is False
    assert cap['notes'] == ''


# ---------------------------------------------------------------- exec_gate
def test_exec_gate_keeps_blocked_reason_even_with_stdout(monkeypatch):
    """沙箱返回 ok=False 且带 stdout 时，拒绝原因此前会被整个丢掉。"""
    from backend.core import exec_gate as eg

    def _fake(command, permission_level=None, cwd=None, timeout=None):
        return {'ok': False, 'error': '路径逃逸被拒绝（词法守卫）',
                'stdout': 'partial', 'stderr': '', 'code': -1,
                'isolation': 'rlimit+chdir', 'permission': permission_level,
                'platform': 'linux', 'guard': 'lexical'}

    monkeypatch.setattr(sb, 'run_sandboxed', _fake)
    out = eg._execute_desktop('cat /etc/shadow', permission='default',
                              timeout=5, cwd=None, intent='tool')
    assert out['ok'] is False
    assert '词法守卫' in out['blocked_reason'], out
    assert '词法守卫' in out['error'], out


def test_exec_gate_passes_through_guard_field(monkeypatch):
    from backend.core import exec_gate as eg

    def _fake(command, permission_level=None, cwd=None, timeout=None):
        return {'ok': False, 'error': '逃逸', 'stdout': '', 'stderr': '',
                'code': -1, 'isolation': 'rlimit+chdir',
                'permission': permission_level, 'platform': 'linux',
                'guard': 'lexical', 'note': '不是安全边界',
                'offending': ['/home/x']}

    monkeypatch.setattr(sb, 'run_sandboxed', _fake)
    out = eg._execute_desktop('cat /x', permission='default', timeout=5,
                              cwd=None, intent='tool')
    assert out.get('guard') == 'lexical', '降级级别要能一路透传到前端'
    assert out.get('offending') == ['/home/x']


# ---------------------------------------------------------------- Windows shell 选择
# 根因：subprocess.run(cmd, shell=True) 在 Windows 上走 cmd.exe，那里没有
# ls/cat/pwd —— 用户实测「ls 等基础命令都用不了」。修法：Windows 优先用
# Git Bash 解释 POSIX 命令，找不到才退回 cmd.exe，并如实标注用的哪个 shell。
def test_posix_platforms_use_plain_shell():
    for plat in ('Linux', 'Darwin'):
        cmd, shell, kind = sb._posix_run_args('ls -la', plat)
        assert cmd == 'ls -la'
        assert shell is True, 'POSIX 上 shell=True 就能跑 ls，不该改动行为'
        assert kind == 'sh'


def test_windows_with_bash_routes_through_bash(monkeypatch):
    monkeypatch.setattr(sb, '_find_windows_bash',
                        lambda: r'C:\Git\bin\bash.exe')
    cmd, shell, kind = sb._posix_run_args('ls -la', 'Windows')
    assert cmd == [r'C:\Git\bin\bash.exe', '-c', 'ls -la']
    assert shell is False, '显式传 bash 可执行文件时不能再开 shell=True'
    assert kind == 'bash'


def test_windows_without_bash_degrades_to_cmd(monkeypatch):
    monkeypatch.setattr(sb, '_find_windows_bash', lambda: None)
    cmd, shell, kind = sb._posix_run_args('ls -la', 'Windows')
    assert cmd == 'ls -la'
    assert shell is True
    assert kind == 'cmd', '没装 bash 时如实标 cmd —— ls 会失败，但不假装能跑'


def test_find_windows_bash_is_cached(monkeypatch):
    # 复位缓存，注入一次命中，再调用多次只应探测一次。
    monkeypatch.setattr(sb, '_win_bash_cache', None)
    monkeypatch.setattr(sb, '_win_bash_resolved', False)
    calls = {'n': 0}

    def _which(_name):
        calls['n'] += 1
        return '/usr/bin/bash'

    monkeypatch.setattr(sb.shutil, 'which', _which)
    first = sb._find_windows_bash()
    second = sb._find_windows_bash()
    assert first == '/usr/bin/bash'
    assert second == first
    assert calls['n'] == 1, '探测结果要缓存，不能每条命令都重新 which'


def test_exec_gate_passes_through_shell_field(monkeypatch):
    from backend.core import exec_gate as eg

    def _fake(command, permission_level=None, cwd=None, timeout=None):
        return {'ok': True, 'stdout': 'a.txt', 'stderr': '', 'code': 0,
                'cwd': '/w', 'isolation': 'job-object',
                'permission': permission_level, 'platform': 'windows',
                'shell': 'bash'}

    monkeypatch.setattr(sb, 'run_sandboxed', _fake)
    out = eg._execute_desktop('ls', permission='default', timeout=5,
                              cwd=None, intent='tool')
    assert out['ok'] is True
    # shell 字段要透传到前端，界面才能说清「这次是走 bash 跑的 ls」
    assert out.get('shell') == 'bash'
