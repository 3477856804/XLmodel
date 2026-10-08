#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""沙箱（backend/core/sandbox.py）单元测试。

覆盖：
  1. 基本命令执行（echo / ls / pwd）
  2. 超时限制
  3. 权限三档（readonly / default / full）上报
  4. 危险命令黑名单 / 空命令拦截
  5. 路径白名单 + 隔离报告字段

所有用例都把沙箱根指向 pytest 的 tmp_path（XIAOLING_SANDBOX_ROOT），
绝不污染真实用户数据目录；不需要网络 / 模型权重。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


@pytest.fixture
def sb(tmp_path, monkeypatch):
    """把沙箱根重定向到临时目录并完成初始化，返回 sandbox 模块。"""
    monkeypatch.setenv("XIAOLING_SANDBOX_ROOT", str(tmp_path))
    from backend.core import sandbox
    sandbox.ensure()
    return sandbox


# ---------------------------------------------------------------------------
# 1. 基本命令执行
# ---------------------------------------------------------------------------
def test_sandbox_echo(sb):
    r = sb.run_sandboxed("echo hello_xl")
    assert r["ok"] is True
    assert "hello_xl" in r["stdout"]


def test_sandbox_lists_workspace(sb):
    """pwd 应落在临时 workspace 内。"""
    r = sb.run_sandboxed("pwd")
    assert r["ok"] is True
    assert "workspace" in r["stdout"]


def test_sandbox_default_entry_runs(sb):
    """向后兼容入口 run() 等价于 default 权限。"""
    r = sb.run("echo via_run")
    assert r["ok"] is True
    assert "via_run" in r["stdout"]


# ---------------------------------------------------------------------------
# 2. 超时限制
# ---------------------------------------------------------------------------
def test_sandbox_timeout_kills_slow_command(sb):
    r = sb.run_sandboxed("sleep 10", timeout=1)
    assert r["ok"] is False
    assert "超时" in r["error"]


# ---------------------------------------------------------------------------
# 3. 权限三档
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("level", ["readonly", "default", "full"])
def test_sandbox_permission_levels_report(sb, level):
    """三档权限都能跑无害命令，并如实上报 permission 字段。"""
    r = sb.run_sandboxed("echo ok", permission_level=level)
    assert r["ok"] is True, f"{level} 下 echo 应成功：{r}"
    assert r["permission"] == level


def test_sandbox_invalid_permission_falls_back_to_default(sb):
    """非法权限级别 -> 回退 default。"""
    r = sb.run_sandboxed("echo ok", permission_level="bogus")
    assert r["permission"] == "default"


# ---------------------------------------------------------------------------
# 4. 黑名单 / 空命令
# ---------------------------------------------------------------------------
def test_sandbox_blocks_dangerous_command(sb):
    r = sb.run_sandboxed("rm -rf /")
    assert r["ok"] is False
    assert "危险命令" in r["error"]


def test_sandbox_rejects_empty_command(sb):
    r = sb.run_sandboxed("   ")
    assert r["ok"] is False
    assert "空" in r["error"]


# ---------------------------------------------------------------------------
# 5. 路径白名单 + 隔离报告字段
# ---------------------------------------------------------------------------
def test_sandbox_isolation_fields_present(sb):
    r = sb.run_sandboxed("echo field")
    assert "isolation" in r and "permission" in r
    assert r["isolation"] in (
        "landlock", "rlimit+chdir", "rlimit-only",
        "seatbelt", "job-object", "subprocess",
        "path-whitelist", "unrestricted",
    )


def test_sandbox_platform_field_present(sb):
    """返回值必须包含 platform 字段。"""
    r = sb.run_sandboxed("echo platform")
    assert "platform" in r
    assert r["platform"]  # 非空字符串


def test_get_platform_isolation_returns_valid(sb):
    """get_platform_isolation 返回合法的隔离类型。"""
    iso = sb.get_platform_isolation()
    valid = (
        "landlock", "rlimit+chdir",
        "seatbelt", "rlimit-only",
        "job-object", "subprocess",
        "unknown",
    )
    assert iso in valid, f"未知隔离类型: {iso}"


def test_seatbelt_profile_builder_readonly(sb, tmp_path):
    """Seatbelt profile 生成：readonly 档应 deny default + 仅读。"""
    ws = str(tmp_path / "workspace")
    profile = sb._build_seatbelt_profile(ws, sb.PERM_READONLY)
    assert "(deny default)" in profile
    assert "(version 1)" in profile
    # 不应出现 file* 全权限放行（readonly）
    assert f'(allow file* (subpath "{ws}"))' not in profile
    # 应出现只读放行
    assert f'(allow file-read* file-read-metadata (subpath "{ws}"))' in profile


def test_seatbelt_profile_builder_default(sb, tmp_path):
    """Seatbelt profile 生成：default 档 workspace 可读写。"""
    ws = str(tmp_path / "workspace")
    profile = sb._build_seatbelt_profile(ws, sb.PERM_DEFAULT)
    assert "(deny default)" in profile
    # default 档 workspace 全权限
    assert f'(allow file* (subpath "{ws}"))' in profile


def test_seatbelt_profile_builder_full(sb, tmp_path):
    """Seatbelt profile 生成：full 档应 allow default。"""
    ws = str(tmp_path / "workspace")
    profile = sb._build_seatbelt_profile(ws, sb.PERM_FULL)
    assert "(allow default)" in profile


def test_seatbelt_available_returns_bool(sb):
    """_seatbelt_available 返回布尔值（非 macOS 上为 False）。"""
    result = sb._seatbelt_available()
    assert isinstance(result, bool)


def test_jobobject_available_returns_bool(sb):
    """_jobobject_available 返回布尔值（非 Windows 上为 False）。"""
    result = sb._jobobject_available()
    assert isinstance(result, bool)


def test_sandbox_path_whitelist_allows_workspace(sb):
    ws = str(sb.workspace_dir())
    assert sb.is_path_allowed(ws) is True
    assert sb.is_path_allowed(".") is True  # 相对路径相对 workspace


def test_sandbox_path_whitelist_blocks_escape(sb):
    assert sb.is_path_allowed("/etc/shadow") is False
    assert sb.is_path_allowed("/tmp") is False


def test_sandbox_guard_path_raises_on_escape(sb):
    with pytest.raises(PermissionError):
        sb.guard_path("/etc/passwd")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
