#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""插件系统（backend/core/plugin_system.py）单元测试。

覆盖：
  1. PluginManager 初始化与内置插件注册
  2. 内置插件列表完整性
  3. enable / disable / 状态持久化
  4. 外部插件动态加载（plugin.json + main.py）
  5. 依赖检查 / 统计

插件目录指向 pytest tmp_path，绝不碰真实 plugins/。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.core.plugin_system import (
    PluginManager, BUILTIN_PLUGINS, PluginBase,
)


@pytest.fixture
def pm(tmp_path):
    """独立插件目录的 PluginManager。"""
    return PluginManager(plugins_dir=tmp_path, enable_builtin=True)


# ---------------------------------------------------------------------------
# 1/2. 初始化与内置插件列表
# ---------------------------------------------------------------------------
def test_plugin_manager_builtin_count(pm):
    listed = pm.list_plugins()
    assert len(listed) == len(BUILTIN_PLUGINS)
    assert all(p["builtin"] for p in listed)


def test_builtin_plugin_names_match(pm):
    expected = {p["name"] for p in BUILTIN_PLUGINS}
    actual = {p["name"] for p in pm.list_plugins()}
    assert expected == actual


def test_builtin_plugins_default_disabled(pm):
    """内置插件默认全部关闭。"""
    assert pm.list_enabled() == []


# ---------------------------------------------------------------------------
# 3. enable / disable / 持久化
# ---------------------------------------------------------------------------
def test_enable_disable_toggle(pm):
    assert pm.enable("deep_chat") is True
    assert pm.is_enabled("deep_chat") is True
    assert pm.disable("deep_chat") is True
    assert pm.is_enabled("deep_chat") is False


def test_enable_unknown_returns_false(pm):
    assert pm.enable("no_such_plugin") is False
    assert pm.disable("no_such_plugin") is False


def test_state_persisted_to_disk(pm, tmp_path):
    pm.enable("reminder")
    state_file = tmp_path / "state.json"
    assert state_file.is_file()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data["enabled"]["reminder"] is True


# ---------------------------------------------------------------------------
# 4. 外部插件动态加载
# ---------------------------------------------------------------------------
def _write_sample_plugin(dir_path: Path):
    (dir_path / "plugin.json").write_text(json.dumps({
        "name": "sample_echo", "version": "1.0.0",
        "description": "示例插件", "entry": "main.py",
        "permissions": [], "enabled": False,
    }, ensure_ascii=False), encoding="utf-8")
    (dir_path / "main.py").write_text(
        "from backend.core.plugin_system import PluginBase\n"
        "class MyPlugin(PluginBase):\n"
        "    name = 'sample_echo'\n"
        "    def init(self):\n"
        "        self.inited = True\n"
        "    def on_message(self, text, context=None):\n"
        "        return '[echo] ' + text\n",
        encoding="utf-8")


def test_load_external_plugin(pm, tmp_path):
    plug = tmp_path / "sample_echo"
    plug.mkdir()
    _write_sample_plugin(plug)
    assert pm.load_plugin(plug) is True
    p = pm.get("sample_echo")
    assert p is not None and p.is_builtin is False
    # enable 后 on_message 钩子真正改写消息
    pm.enable("sample_echo")
    assert pm.process_message("hi") == "[echo] hi"


def test_create_plugin_then_enable(pm):
    r = pm.create_plugin("my_demo", description="测试创建")
    assert r["ok"] is True
    assert r["enabled"] is False, "新建插件默认关闭"
    assert pm.enable("my_demo") is True


# ---------------------------------------------------------------------------
# 5. 依赖检查 / 统计
# ---------------------------------------------------------------------------
def test_check_dependencies_ok(pm):
    ok, err = pm.check_dependencies({"dependencies": []})
    assert ok and err == ""


def test_check_dependencies_missing(pm):
    ok, err = pm.check_dependencies({"dependencies": ["not_installed_xxx"]})
    assert ok is False and "缺少依赖" in err


def test_stats_fields(pm):
    s = pm.stats()
    assert s["total"] == len(BUILTIN_PLUGINS)
    assert s["builtin"] == len(BUILTIN_PLUGINS)
    for k in ("total", "enabled", "external", "categories"):
        assert k in s


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
