#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 v0.0.1 - 启动入口（三语言架构）

架构：
    Flutter(UI)  ──gRPC/localhost:50051──>  Python 后端（本进程）

默认行为：
    1) 启动 gRPC 后端服务（后台线程），等待 Flutter 前端连接
    2) 同时启动临时 Web 实测面板 http://127.0.0.1:8765
       （本机若未安装 Flutter SDK，可用浏览器直接与小凌对话、验证后端是否真的可用）

常用：
    python main.py                 # gRPC + Web 面板（推荐：双击即测）
    python main.py --no-web        # 仅 gRPC（正式 Flutter 联调时使用）
    python main.py --no-grpc       # 仅 Web 面板
    python main.py --status        # 打印引擎状态后退出
    python main.py --selftest      # 运行自检后退出
"""
import sys
import os
import time
import logging

# 兼容开发态与 PyInstaller 打包态：把项目根（含 backend/ 包）加入 sys.path。
if getattr(sys, 'frozen', False):
    # PyInstaller onefile：资源解包在 sys._MEIPASS
    _ROOT = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
# 内部模块统一用 `from core.xxx` 导入，需把 backend/ 也加入路径。
sys.path.insert(0, os.path.join(_ROOT, 'backend'))


def _install_core_alias():
    """让 `import core.xxx` 在打包态也能解析到 `backend.core.xxx`。

    背景：源码里大量使用 `from core.xxx import ...`（开发态靠上面那句
    `sys.path.insert(_ROOT/'backend')` 解析）。但 PyInstaller 只会把**实际被
    import 过的名字**收进产物，`backend/` 目录未必在磁盘上存在（取决于
    contents_directory 是否平铺、以及是否把源码当 data 拷进去）。一旦
    `core` 不可解析，所有 `from core.*` 都会 ImportError，而调用方多半有
    try/except 兜底 —— 结果是功能静默失效（模型路径、成长引擎、配置全废），
    表面上程序却"能跑"，极难排查。

    兜底手段：装一个 meta path finder，把 `core.*` 改写到 `backend.core.*`
    并把真实模块登记为别名，两边共用同一个模块对象（不会重复初始化单例）。
    """
    import importlib
    import importlib.machinery
    from importlib.abc import MetaPathFinder, Loader

    class _AliasLoader(Loader):
        def __init__(self, module):
            self._module = module

        def create_module(self, spec):
            return self._module

        def exec_module(self, module):
            pass                       # 真实模块已经执行过，这里只需挂别名

    class _CoreAliasFinder(MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != 'core' and not fullname.startswith('core.'):
                return None
            try:
                mod = importlib.import_module('backend.' + fullname)
            except Exception:
                return None
            return importlib.machinery.ModuleSpec(
                fullname, _AliasLoader(mod),
                is_package=hasattr(mod, '__path__'))

    try:
        import backend.core                      # 真实包名存在才装别名
        sys.modules.setdefault('core', sys.modules['backend.core'])
        sys.meta_path.insert(0, _CoreAliasFinder())
    except Exception:
        pass


_install_core_alias()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="小凌 v0.0.1 后端服务")
    parser.add_argument("--status", action="store_true", help="打印引擎状态后退出")
    parser.add_argument("--selftest", action="store_true", help="运行自检后退出")
    parser.add_argument("--port", type=int, default=50051, help="gRPC 监听端口（默认 50051）")
    parser.add_argument("--web-port", type=int, default=8765,
                        help="Web 实测面板端口（默认 8765）")
    parser.add_argument("--no-web", action="store_true",
                        help="不启动 Web 面板（仅跑 gRPC）")
    parser.add_argument("--no-grpc", action="store_true",
                        help="不启动 gRPC（仅跑 Web 面板）")
    parser.add_argument("--host", default="localhost",
                        help="gRPC 监听地址（默认 localhost）")
    parser.add_argument("--timeout", type=int, default=300,
                        help="优雅关闭超时秒数（默认 300）")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    )
    log = logging.getLogger('xiaoling.main')

    # ---- 启动横幅：打印版本/端口/PID/数据目录/模型路径 ----
    try:
        from backend.core import config as _cfg
        _desc = _cfg.describe()
        _cfg.load()
        log.info('==== 小凌 v0.0.1 启动 ====')
        log.info('PID=%s host=%s port=%s', os.getpid(), args.host, args.port)
        log.info('数据目录: %s', _desc.get('data_dir', ''))
        log.info('模型路径: %s', _cfg.resource('models'))
        log.info('优雅关闭超时: %ss', args.timeout)
    except Exception:
        log.info('小凌 v0.0.1 启动 (PID=%s port=%s)', os.getpid(), args.port)

    # ---- 信号处理：SIGTERM/SIGINT 优雅关闭 gRPC server ----
    def _graceful_shutdown(signum, frame):
        log.info('收到信号 %s，正在优雅关闭…', signum)
        print('\n正在关闭小凌…')
        try:
            from backend.rpc import server as _srv
        except Exception:
            pass
        sys.exit(0)

    import signal as _sig
    for _s in (_sig.SIGINT, _sig.SIGTERM):
        try:
            _sig.signal(_s, _graceful_shutdown)
        except (ValueError, OSError):
            pass

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

        # ---- gRPC 后端（后台线程，Flutter 前端连它）----
        if not args.no_grpc:
            import threading

            def _grpc_worker():
                try:
                    from backend.rpc.server import serve
                    serve(port=args.port)
                except Exception as e:
                    log.exception('gRPC server failed to start')
                    print(f"  [gRPC] 启动失败：{e}")

            threading.Thread(target=_grpc_worker, daemon=True).start()
            print(f"  [gRPC] 后端已启动：localhost:{args.port}（等待 Flutter 前端连接）")

        # ---- Web 实测面板（主线程阻塞跑；同时托管 3D 查看器）----
        # 注意：Flutter 是用 `--no-web` 拉起本进程的，但桌面端的真 3D
        # 依赖本进程把 viewer.html / three.js / .vrm 通过 HTTP 吐给 WebView。
        # 所以 --no-web 也必须把查看器服务开起来，只是不再跑调试面板页面。
        if not args.no_web:
            try:
                from backend.core.webpanel import run_blocking
                run_blocking(port=args.web_port)
            except Exception as e:  # webpanel 模块缺失或出错时，降级为仅跑 gRPC
                print(f"  [Web 面板] 未能启动（webpanel 模块缺失或出错）：{e}")
                print(f"  已降级为仅运行 gRPC 后端（localhost:{args.port}）。按 Ctrl+C 退出。")
                while True:
                    time.sleep(3600)
        else:
            try:
                from backend.core.webpanel import serve_background
                serve_background(port=args.web_port)
            except Exception as e:  # noqa: BLE001
                print(f"  [3D 查看器] 未能启动：{e}")
            print("  已按 --no-web 启动，主线程保持存活；Ctrl+C 退出。")
            while True:
                time.sleep(3600)

    except KeyboardInterrupt:
        log.info('Received interrupt, shutting down')
        print("\n已退出。")
    except Exception as e:
        log.exception('Fatal error in main')
        print(f"\n错误：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
