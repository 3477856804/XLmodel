#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模块导入测试 - 验证所有后端模块可正常导入"""
import sys
import traceback
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def test_import(module_name: str) -> tuple[bool, str]:
    """测试模块导入"""
    try:
        __import__(module_name)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    modules = [
        # core 基础设施
        "core.platform",
        "core.paths",
        "core.config",
        "core.hardware",

        # 记忆系统
        "core.memory_short",
        "core.memory_long",

        # 人格系统
        "core.persona_emotion",
        "core.persona_relationship",

        # 插件系统
        "core.plugin_manager",

        # 通信通道
        "core.channel_base",
        "core.channel_webhook",
        "core.channel_telegram",
        "core.channel_discord",
        "core.channel_feishu",
        "core.channel_email",
        "core.channel_manager",

        # 自动更新
        "core.updater",

        # 模型商店
        "core.model_store",
    ]

    passed = 0
    failed = 0
    failures = []

    print("=" * 60)
    print("小凌 v0.0.4 模块导入测试")
    print("=" * 60)

    for mod in modules:
        ok, err = test_import(mod)
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
