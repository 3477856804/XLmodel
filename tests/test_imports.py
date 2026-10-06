#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模块导入测试 - 验证所有后端模块可正常导入"""
import sys
import traceback
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def _import_module(module_name: str) -> tuple[bool, str]:
    """测试模块导入"""
    try:
        __import__(module_name)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    modules = [
        # core 基础设施
        "core.paths",
        "core.config",
        "core.system",
        "core.throttle",

        # 记忆 / 人格 / 知识
        "core.memory",
        "core.persona",
        "core.knowledge",

        # 成长 / 训练
        "core.growth",
        "core.growth_store",
        "core.training",

        # 模型 / 引擎 / 会话
        "core.model",
        "core.engine",
        "core.session",

        # 插件 / 工具 / 目标 / 守卫
        "core.plugin_manager",
        "core.tools",
        "core.goal_manager",
        "core.guards",

        # 多 Agent / 定时 / 通信 / 搜索
        "core.multi_agent",
        "core.scheduler",
        "core.channels",
        "core.search",

        # 语音 / 视觉 / 文件箱 / 头像 / 更新
        "core.voice",
        "core.vision",
        "core.filebox",
        "core.avatar",
        "core.updater",
    ]

    passed = 0
    failed = 0
    failures = []

    print("=" * 60)
    print("小凌 v0.0.1 模块导入测试")
    print("=" * 60)

    for mod in modules:
        ok, err = _import_module(mod)
        if ok:
            print(f"  [OK] {mod}")
            passed += 1
        else:
            print(f"  [FAIL] {mod}: {err}")
            failed += 1
            failures.append((mod, err))

    print("-" * 60)
    print(f"结果: {passed} 通过, {failed} 失败, 共 {len(modules)} 个模块")
    print("=" * 60)

    if failures:
        print("\n失败详情:")
        for mod, err in failures:
            print(f"  - {mod}: {err}")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
