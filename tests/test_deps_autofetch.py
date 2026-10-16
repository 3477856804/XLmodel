# -*- coding: utf-8 -*-
"""core.deps 依赖自愈：白名单、注入防护、train 档护栏、如实失败、RPC 接线。

不真的联网安装：subprocess / pip 探测 / 网络探测 / find_spec 全部桩掉。
"""
import json
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / 'backend')):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.core import deps     # noqa: E402


@pytest.fixture(autouse=True)
def no_frozen(monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.setattr(deps, '_pip_available', lambda: True)
    monkeypatch.setattr(deps, '_has_network', lambda: True)


class _CP:
    def __init__(self, returncode=0, stdout='ok', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ---------------------------------------------------------------- 白名单与注入
def test_unknown_package_rejected_not_passed_to_pip(monkeypatch):
    calls = []
    monkeypatch.setattr(deps.subprocess, 'run',
                        lambda *a, **k: calls.append(a) or _CP())
    r = deps.install(['evil; rm -rf /'])
    assert r['ok'] is False and '白名单' in r['error']
    assert calls == []


def test_sqlish_names_rejected():
    for bad in ('../os', 'torch --index-url=http://evil', '-e', ''):
        r = deps.install([bad]) if bad else deps.install([])
        assert r['ok'] is False


def test_pip_cmd_is_list_not_shell():
    cmd = deps._pip_cmd(['jieba'], user=True)
    assert isinstance(cmd, list) and '--user' in cmd and 'jieba' in cmd[-1]
    assert all(';' not in c and '&' not in c for c in cmd)


# ---------------------------------------------------------------- train 档护栏
def test_train_tier_requires_force(monkeypatch):
    monkeypatch.setattr(deps, 'is_installed', lambda name: False)
    calls = []
    monkeypatch.setattr(deps.subprocess, 'run',
                        lambda *a, **k: calls.append(a) or _CP())
    r = deps.install(['torch'])
    assert r['ok'] is False and 'force' in r['error']
    assert calls == []
    assert '极多GB' in next(s['size'] for s in deps.status()['missing']
                            if s['package'] == 'torch')


def test_train_force_then_honest_verify(monkeypatch):
    monkeypatch.setattr(deps, 'is_installed', lambda name: False)
    monkeypatch.setattr(deps.subprocess, 'run', lambda *a, **k: _CP(0))
    r = deps.install(['torch'], force_train=True)
    assert r['ok'] is False and r['failed'] == ['torch']
    assert 'pip 安装成功但未验证' not in json.dumps(r, ensure_ascii=False)


# ---------------------------------------------------------------- 如实失败
def test_offline_honest(monkeypatch):
    monkeypatch.setattr(deps, 'is_installed', lambda name: False)
    monkeypatch.setattr(deps, '_has_network', lambda: False)
    r = deps.install(['jieba'])
    assert r['ok'] is False and '网络' in r['error']


def test_no_pip_honest(monkeypatch):
    monkeypatch.setattr(deps, 'is_installed', lambda name: False)
    monkeypatch.setattr(deps, '_pip_available', lambda: False)
    r = deps.install(['jieba'])
    assert r['ok'] is False and 'pip' in r['error']


def test_frozen_honest(monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(deps, 'is_installed', lambda name: False)
    calls = []
    monkeypatch.setattr(deps.subprocess, 'run',
                        lambda *a, **k: calls.append(a) or _CP())
    r = deps.install(['jieba'])
    assert r['ok'] is False and '打包态' in r['error']
    assert calls == []


def test_pip_failure_carries_tail(monkeypatch):
    monkeypatch.setattr(deps, 'is_installed', lambda name: False)
    monkeypatch.setattr(deps.subprocess, 'run',
                        lambda *a, **k: _CP(2, stdout='', stderr='no matching distribution'))
    r = deps.install(['jieba'])
    assert r['ok'] is False and 'no matching distribution' in r['tail']


def test_retry_with_user_flag_on_permission_error(monkeypatch):
    seen = []

    def fake_run(cmd, **k):
        seen.append(cmd)
        if '--user' in cmd:
            return _CP(0)
        return _CP(1, stderr='Permission denied')
    monkeypatch.setattr(deps.subprocess, 'run', fake_run)
    state = {'installed': False}

    def fake_is_installed(name):
        return state['installed']
    # 首检未装 → 进 _run_install；--user 成功后复查为已装。
    def run_then_mark(*a, **k):
        r = fake_run(*a, **k)
        if r.returncode == 0:
            state['installed'] = True
        return r
    monkeypatch.setattr(deps.subprocess, 'run', run_then_mark)
    monkeypatch.setattr(deps, 'is_installed', fake_is_installed)
    r = deps.install(['jieba'])
    assert r['ok'] is True and r.get('user_mode') is True and len(seen) == 2


# ---------------------------------------------------------------- 就绪/幂等
def test_already_installed_skips(monkeypatch):
    monkeypatch.setattr(deps, 'is_installed', lambda name: True)
    calls = []
    monkeypatch.setattr(deps.subprocess, 'run',
                        lambda *a, **k: calls.append(a) or _CP())
    r = deps.install(['psutil'])
    assert r['ok'] is True and r['installed'] == [] and 'note' in r
    assert calls == []


def test_autofetch_light_only_light_tier(monkeypatch):
    asked = []
    monkeypatch.setattr(deps, 'is_installed', lambda name: False)

    def fake_install(names, force_train=False, output=None):
        asked.extend(names)
        return {'ok': True, 'installed': list(names)}
    monkeypatch.setattr(deps, 'install', fake_install)
    r = deps.autofetch_light()
    assert r['ok'] is True
    assert set(asked) <= {'psutil', 'jieba', 'requests', 'aiohttp'}
    assert 'torch' not in asked


def test_autofetch_honors_config_off(monkeypatch):
    monkeypatch.setattr(deps, '_auto_enabled', lambda: False)
    r = deps.autofetch_light()
    assert r['ok'] is True and 'skipped' in r


def test_autofetch_requires_pip_network(monkeypatch):
    monkeypatch.setattr(deps, '_has_network', lambda: False)
    r = deps.autofetch_light()
    assert r['ok'] is False and 'note' in r


# ---------------------------------------------------------------- status/handle
def test_status_shape():
    s = deps.status()
    assert s['ok'] and {'installed', 'missing', 'python', 'pip_available',
                        'network', 'train_guard'} <= set(s)
    pkgs = {x['package'] for x in s['installed']} | {x['package'] for x in s['missing']}
    assert pkgs == {p for p, _, _, _, _ in deps.CATALOG}


def test_handle_rpc_shapes():
    assert json.loads(deps.handle(''))['ok'] is True
    bad = json.loads(deps.handle('install nope'))
    assert bad['ok'] is False and '白名单' in bad['error']
    assert json.loads(deps.handle('bogus'))['ok'] is False


def test_handle_install_ready_short_circuit():
    out = json.loads(deps.handle('install ' + ' '.join(
        p for p, m, *_ in deps.CATALOG if deps.is_installed(m))))
    if out.get('installed') is not None and out.get('skipped') is not None:
        assert out['ok'] is True


# ---------------------------------------------------------------- server 路由
def test_server_deps_cmd(monkeypatch):
    from backend.rpc import server
    j = json.loads(server._handle_deps_cmd('status'))
    assert j['ok'] is True
    j = json.loads(server._handle_deps_cmd('install evil'))
    assert j['ok'] is False and '白名单' in j['error']
    j = json.loads(server._handle_deps_cmd('install torch'))
    assert j['ok'] is False and 'force' in j['error']
    j = json.loads(server._handle_deps_cmd('nonsense'))
    assert j['ok'] is False
    # 路由表存在 deps: 分支
    src = (ROOT / 'backend' / 'rpc' / 'server.py').read_text(encoding='utf-8')
    assert "cmd.startswith('deps:')" in src


def test_server_install_never_runs_pip_synchronously(monkeypatch):
    """RPC 处理器里绝不能同步跑 pip —— 会堵死对话线程几分钟。"""
    from backend.rpc import server
    runs = []
    monkeypatch.setattr(deps, '_pip_available', lambda: True)
    monkeypatch.setattr(deps, '_has_network', lambda: True)
    monkeypatch.setattr(sys, 'frozen', False, raising=False)
    monkeypatch.setattr(deps.subprocess, 'run',
                        lambda *a, **k: runs.append(a))
    monkeypatch.setattr(deps, 'is_installed', lambda name: False)
    started = []
    monkeypatch.setattr(server, '_bg_start',
                        lambda name, job: started.append(name) or
                        {'ok': True, 'task_id': 't1', 'poll': 'agent:task status t1'})
    j = json.loads(server._handle_deps_cmd('install jieba'))
    assert j['ok'] is True and j.get('task_id') == 't1'
    assert runs == []          # 同步路径零 pip
    assert started == ['deps:install jieba']


def test_validate_pure_no_execution(monkeypatch):
    monkeypatch.setattr(deps, 'is_installed', lambda name: False)
    calls = []
    monkeypatch.setattr(deps.subprocess, 'run',
                        lambda *a, **k: calls.append(a) or _CP())
    v = deps.validate(['jieba', 'psutil'])
    assert v['ok'] and v['todo'] == ['jieba', 'psutil'] and calls == []
    v = deps.validate(['requests'], force_train=True)   # 非 train 档，force 无副作用
    assert v['ok']


# ---------------------------------------------------------------- 无 shell=True
def test_no_shell_true_in_deps():
    path = ROOT / 'backend' / 'core' / 'deps.py'
    src = path.read_text(encoding='utf-8')
    assert 'shell=True' not in src
    with open(path, 'rb') as fh:
        toks = list(tokenize.tokenize(fh.readline))
    ran = [t for t in toks if t.type == tokenize.NAME and t.string == 'run']
    assert ran, '应存在 subprocess.run 调用'
    for t in ran:
        line = src.splitlines()[t.start[0] - 1]
        assert 'subprocess.run' in line or 'run(' in line
