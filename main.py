#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 v0.0.1 - 启动入口（三语言架构）

架构：
    Flutter(UI)  ──gRPC/localhost:50051──>  Python 后端（本进程）

默认行为：启动 gRPC 后端服务，等待 Flutter 前端连接。
开发调试：
    python main.py --status     # 打印引擎状态
    python main.py --selftest   # 运行自检
"""
import sys
import os

# 添加 backend 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="小凌 v0.0.1 后端服务")
    parser.add_argument("--status", action="store_true", help="打印引擎状态后退出")
    parser.add_argument("--selftest", action="store_true", help="运行自检后退出")
    parser.add_argument("--port", type=int, default=50051, help="gRPC 监听端口（默认 50051）")
    args = parser.parse_args()

    try:
        if args.status:
            from backend.core.engine import XiaoLing
            app = XiaoLing()
            print(app.show_status())
            return

        if args.selftest:
            from backend.core import system
            result = system.selftest()
            print(result)
            return

        # 默认：启动 gRPC 后端服务（Flutter 前端通过 localhost:50051 连接）
        from backend.rpc.server import serve
        serve(port=args.port)

    except KeyboardInterrupt:
        print("\n已退出。")
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
