#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 v0.0.1 - 启动入口"""
import sys
import os

# 添加 backend 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="小凌 v0.0.1")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--no-pet", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    try:
        from backend.core.engine import XiaoLing
        app = XiaoLing()

        if args.status:
            print(app.show_status())
            return

        if args.selftest:
            print("自检通过")
            return

        # 命令行对话循环
        print("\n小凌已就绪（输入 quit 退出）")
        while True:
            try:
                text = input("\n你: ").strip()
                if not text:
                    continue
                if text.lower() in ("quit", "exit", "退出"):
                    break
                reply, _ = app.chat(text)
                print(f"小凌: {reply}")
            except KeyboardInterrupt:
                break

    except KeyboardInterrupt:
        print("\n已退出。")
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        try:
            input("\n按回车键关闭…")
        except Exception:
            pass
        sys.exit(1)


if __name__ == '__main__':
    main()
