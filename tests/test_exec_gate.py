# -*- coding: utf-8 -*-
"""exec_gate 统一执行入口测试

覆盖场景：
1. 桌面平台路径分派（验证调用 sandbox.run_sandboxed）
2. 黑名单拦截（危险命令）
3. 路径越界拒绝（cwd 不在 workspace 内）
4. 移动平台分支（验证不 fork shell）
5. 未知平台默认拒绝
6. 联网命令权限检查
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# 确保 backend 在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / 'backend'
for p in (ROOT, BACKEND):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pytest


@pytest.fixture
def exec_gate():
    """导入 exec_gate 模块"""
    from backend.core import exec_gate
    return exec_gate


@pytest.fixture
def mock_sandbox(tmp_path):
    """模拟 sandbox 模块"""
    with patch.dict(os.environ, {'XIAOLING_SANDBOX_ROOT': str(tmp_path)}):
        from backend.core import sandbox
        sandbox.ensure()
        yield sandbox


class TestExecGateDesktop:
    """桌面平台测试"""

    def test_execute_calls_sandbox_on_desktop(self, exec_gate, mock_sandbox):
        """验证桌面平台调用 sandbox.run_sandboxed"""
        with patch.object(mock_sandbox, 'run_sandboxed') as mock_run:
            mock_run.return_value = {
                'ok': True,
                'stdout': 'hello',
                'stderr': '',
                'code': 0,
                'cwd': str(mock_sandbox.workspace_dir()),
                'isolation': 'landlock',
                'permission': 'default',
                'platform': 'linux'
            }

            # 模拟桌面平台
            with patch('platform.system', return_value='Linux'):
                result = exec_gate.execute('echo hello', permission='default')

            assert result['ok'] is True
            assert result['stdout'] == 'hello'
            assert result['isolation'] == 'landlock'
            mock_run.assert_called_once()

    def test_execute_returns_correct_fields(self, exec_gate, mock_sandbox):
        """验证返回字段完整性"""
        with patch.object(mock_sandbox, 'run_sandboxed') as mock_run:
            mock_run.return_value = {
                'ok': True,
                'stdout': 'test',
                'stderr': '',
                'code': 0,
                'cwd': '/tmp/workspace',
                'isolation': 'landlock',
                'permission': 'default',
                'platform': 'linux'
            }

            with patch('platform.system', return_value='Linux'):
                result = exec_gate.execute('echo test', permission='default', intent='test')

            # 验证所有必需字段存在
            assert 'ok' in result
            assert 'stdout' in result
            assert 'stderr' in result
            assert 'code' in result
            assert 'cwd' in result
            assert 'isolation' in result
            assert 'permission' in result
            assert 'blocked_reason' in result
            assert 'platform' in result
            assert 'intent' in result
            assert result['intent'] == 'test'


class TestExecGateBlacklist:
    """黑名单测试"""

    def test_blacklist_blocks_rm_rf(self, exec_gate):
        """验证 rm -rf / 被拦截"""
        result = exec_gate.execute('rm -rf /', permission='default')
        assert result['ok'] is False
        assert result['blocked_reason'] != ''
        assert '黑名单' in result['blocked_reason'] or 'rm' in result['blocked_reason'].lower()

    def test_blacklist_blocks_mkfs(self, exec_gate):
        """验证 mkfs 被拦截"""
        result = exec_gate.execute('mkfs.ext4 /dev/sda1', permission='default')
        assert result['ok'] is False
        assert result['blocked_reason'] != ''

    def test_blacklist_blocks_dd_dev(self, exec_gate):
        """验证 dd of=/dev/ 被拦截"""
        result = exec_gate.execute('dd if=/dev/zero of=/dev/sda', permission='default')
        assert result['ok'] is False
        assert result['blocked_reason'] != ''

    def test_blacklist_blocks_fork_bomb(self, exec_gate):
        """验证 fork 炸弹被拦截"""
        result = exec_gate.execute(':(){:|:&};:', permission='default')
        assert result['ok'] is False
        assert result['blocked_reason'] != ''

    def test_blacklist_blocks_shutdown(self, exec_gate):
        """验证 shutdown 被拦截"""
        result = exec_gate.execute('shutdown -h now', permission='default')
        assert result['ok'] is False
        assert result['blocked_reason'] != ''


class TestExecGatePathCheck:
    """路径检查测试"""

    def test_cwd_outside_workspace_rejected(self, exec_gate, mock_sandbox):
        """验证 cwd 在 workspace 外被拒绝"""
        result = exec_gate.execute('ls', permission='default', cwd='/etc')
        assert result['ok'] is False
        assert '越界' in result['blocked_reason'] or 'cwd' in result['blocked_reason'].lower()

    def test_cwd_inside_workspace_accepted(self, exec_gate, mock_sandbox):
        """验证 cwd 在 workspace 内被接受"""
        ws = str(mock_sandbox.workspace_dir())
        with patch.object(mock_sandbox, 'run_sandboxed') as mock_run:
            mock_run.return_value = {
                'ok': True,
                'stdout': '',
                'stderr': '',
                'code': 0,
                'cwd': ws,
                'isolation': 'landlock',
                'permission': 'default',
                'platform': 'linux'
            }

            with patch('platform.system', return_value='Linux'):
                result = exec_gate.execute('ls', permission='default', cwd=ws)

            assert result['ok'] is True


class TestExecGateMobile:
    """移动平台测试"""

    def test_mobile_does_not_fork_shell(self, exec_gate, tmp_path):
        """验证移动平台不 fork shell"""
        # 模拟移动平台
        with patch('backend.core.sandbox_mobile.is_mobile', return_value=True):
            with patch('backend.core.sandbox_mobile.execute_mobile') as mock_mobile:
                mock_mobile.return_value = {
                    'ok': True,
                    'stdout': 'mobile result',
                    'stderr': '',
                    'code': 0,
                    'isolation': 'in-app',
                    'permission': 'default',
                    'blocked_reason': '',
                    'platform': 'ios'
                }

                result = exec_gate.execute('ls', permission='default')

                assert result['ok'] is True
                assert result['isolation'] == 'in-app'
                mock_mobile.assert_called_once()
                # 验证没有调用 sandbox.run_sandboxed
                # （通过检查 mock_mobile 被调用而非 sandbox 来间接验证）

    def test_mobile_rejects_arbitrary_shell(self, exec_gate, tmp_path):
        """验证移动平台拒绝任意 shell 命令"""
        from backend.core import sandbox_mobile

        # 模拟 iOS 平台
        with patch.object(sandbox_mobile, '_detect_mobile_platform', return_value='ios'):
            result = sandbox_mobile.execute_mobile('rm -rf /', workspace=str(tmp_path))

            assert result['ok'] is False
            assert result['isolation'] == 'in-app'
            assert result['permission'] == 'denied'
            assert result['blocked_reason'] != ''

    def test_mobile_allows_whitelist_actions(self, exec_gate, tmp_path):
        """验证移动平台允许白名单动作"""
        from backend.core import sandbox_mobile

        # 创建测试文件
        test_file = tmp_path / 'test.txt'
        test_file.write_text('hello')

        # 模拟 iOS 平台
        with patch.object(sandbox_mobile, '_detect_mobile_platform', return_value='ios'):
            # ls 命令应该被允许
            result = sandbox_mobile.execute_mobile('ls', workspace=str(tmp_path))
            assert result['ok'] is True
            assert result['isolation'] == 'in-app'

            # cat 命令应该被允许
            result = sandbox_mobile.execute_mobile('cat test.txt', workspace=str(tmp_path))
            assert result['ok'] is True
            assert 'hello' in result['stdout']


class TestExecGateUnknownPlatform:
    """未知平台测试"""

    def test_unknown_platform_rejected(self, exec_gate):
        """验证未知平台默认拒绝"""
        # 模拟既不是桌面也不是移动的平台
        with patch('platform.system', return_value='UnknownOS'):
            with patch('backend.core.sandbox_mobile.is_mobile', return_value=False):
                result = exec_gate.execute('echo test', permission='default')

                assert result['ok'] is False
                assert result['isolation'] == 'none'
                assert result['permission'] == 'denied'
                assert '未知平台' in result['blocked_reason']


class TestExecGateNetworkCommands:
    """联网命令测试"""

    def test_network_command_requires_full_permission(self, exec_gate, mock_sandbox):
        """验证联网命令需要 full 权限"""
        # default 权限应该拒绝 curl
        result = exec_gate.execute('curl http://example.com', permission='default')
        assert result['ok'] is False
        assert '联网' in result['blocked_reason'] or 'full' in result['blocked_reason']

        # full 权限应该允许（但这里我们只验证权限检查通过）
        with patch.object(mock_sandbox, 'run_sandboxed') as mock_run:
            mock_run.return_value = {
                'ok': True,
                'stdout': '',
                'stderr': '',
                'code': 0,
                'cwd': str(mock_sandbox.workspace_dir()),
                'isolation': 'unrestricted',
                'permission': 'full',
                'platform': 'linux'
            }

            with patch('platform.system', return_value='Linux'):
                result = exec_gate.execute('curl http://example.com', permission='full')

            # 验证权限检查通过，调用了 sandbox
            mock_run.assert_called_once()

    def test_git_clone_requires_full_permission(self, exec_gate):
        """验证 git clone 需要 full 权限"""
        result = exec_gate.execute('git clone https://github.com/test/repo', permission='default')
        assert result['ok'] is False
        assert '联网' in result['blocked_reason'] or 'full' in result['blocked_reason']

    def test_pip_install_requires_full_permission(self, exec_gate):
        """验证 pip install 需要 full 权限"""
        result = exec_gate.execute('pip install requests', permission='default')
        assert result['ok'] is False
        assert '联网' in result['blocked_reason'] or 'full' in result['blocked_reason']


class TestExecGateEdgeCases:
    """边界情况测试"""

    def test_empty_command_rejected(self, exec_gate):
        """验证空命令被拒绝"""
        result = exec_gate.execute('', permission='default')
        assert result['ok'] is False
        assert '空' in result['blocked_reason'] or 'empty' in result['blocked_reason'].lower()

    def test_whitespace_command_rejected(self, exec_gate):
        """验证纯空白命令被拒绝"""
        result = exec_gate.execute('   ', permission='default')
        assert result['ok'] is False

    def test_invalid_permission_falls_back_to_default(self, exec_gate, mock_sandbox):
        """验证无效权限级别回退到 default"""
        with patch.object(mock_sandbox, 'run_sandboxed') as mock_run:
            mock_run.return_value = {
                'ok': True,
                'stdout': '',
                'stderr': '',
                'code': 0,
                'cwd': str(mock_sandbox.workspace_dir()),
                'isolation': 'landlock',
                'permission': 'default',
                'platform': 'linux'
            }

            with patch('platform.system', return_value='Linux'):
                result = exec_gate.execute('echo test', permission='invalid_perm')

            # 验证调用时使用了 default 权限
            call_args = mock_run.call_args
            assert call_args[1]['permission_level'] == 'default'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
