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

# 环境自愈：修复某些环境里 dry_attr 把标准 attrs 遮蔽成残缺 attr.py 的问题
# （否则 aiohttp 内部 @attr.s 直接 AttributeError，channels 等模块全挂）。
# 必须在任何会 import aiohttp / channels 的代码之前执行；干净环境下本调用零开销。
try:
    from backend.core._env_shim import fix_attr_shadow as _fix_attr_shadow
    _fix_attr_shadow()
except Exception:
    pass


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
    import importlib.util
    from importlib.abc import MetaPathFinder, Loader

    class _AliasLoader(Loader):
        """把 `core.xxx` 别名模块指向真实 `backend.core.xxx` 模块对象，
        两者共用同一对象（单例一致）。关键：不在 find_spec 阶段执行任何
        模块，否则会在 import 锁持有期间再次 import_module 造成重入死锁——
        那正是 gRPC handler 线程并发 `from core.xxx import` 时整个后端卡死、
        RPC 全部超时、前端 runApp 永不执行的「打不开」根因。"""
        def __init__(self, realname):
            self._real = realname

        def create_module(self, spec):
            return None              # 让默认机制先建一个占位模块

        def exec_module(self, module):
            # 此时由正常 import 机制加载真实模块（可重入安全，非 find_spec 重入）
            real = importlib.import_module(self._real)
            module.__dict__.update(real.__dict__)
            module.__path__ = getattr(real, '__path__', None)
            sys.modules[module.__name__] = real   # 别名与真实共用同一对象

    class _CoreAliasFinder(MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != 'core' and not fullname.startswith('core.'):
                return None
            real = 'backend.' + fullname
            # 只读式查找真实模块规格，绝不在此执行模块（避免 import 锁重入死锁）
            try:
                spec = importlib.util.find_spec(real)
            except (ImportError, ValueError, ModuleNotFoundError):
                return None
            if spec is None or spec.origin in (None, 'namespace'):
                return None
            spec.name = fullname          # 以别名名登记
            spec.loader = _AliasLoader(real)
            spec.has_location = True
            return spec

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
    parser.add_argument("--install-deps", nargs='*', default=None,
                        metavar="PKG",
                        help="按需安装可选依赖（白名单，前台执行后退出）。"
                             "不带 PKG 则打印 deps:status 报告后退出。"
                             "torch 等数 GB 栈需要额外 'force'。")
    parser.add_argument("--no-deps-autofetch", action="store_true",
                        help="禁用首启后台自动拉取轻量依赖（默认在源码态且"
                             "有 pip+网络时开）")
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
        # 修正：原先 import server 后从未使用（死 import，伪装成有清理动作）。
        # gRPC serve() 自身的 finally（server.stop + 活动日志）由解释器退出时
        # 触发；这里保持轻量，避免在信号处理器里做不可靠的重活。
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

        if args.install_deps is not None:
            from backend.core import deps as _deps
            names = list(args.install_deps or [])
            force = 'force' in names
            names = [n for n in names if n != 'force']
            if names:
                r = _deps.install(names, force_train=force, output=lambda t: print(t))
                print(r)
                import sys as _sys
                _sys.exit(0 if r.get('ok') else 1)
            st = _deps.status()
            print('python:', st.get('python'),
                  'frozen:', st.get('frozen'),
                  'pip:', st.get('pip_available'),
                  'network:', st.get('network'))
            print('installed:', [x['package'] for x in st.get('installed', [])])
            print('missing :', [x['package'] for x in st.get('missing', [])])
            print('提示：deps:install <包...> 只装白名单；torch 档要额外带 force')
            return

        # ---- 首启后台自动拉取轻量依赖（源码态 + 有 pip + 有网络才动）----
        # 如实：--user 装进来的包多数要重启进程才进 sys.path（site 已初始化），
        # 所以这里只在真装了东西时提示「下次启动生效」，不假装当场可用。
        if not args.no_deps_autofetch:
            import threading as _th

            def _autofetch():
                try:
                    from backend.core import deps as _deps
                    r = _deps.autofetch_light()
                    got = r.get('installed') or []
                    if got:
                        log.info('已自动获取轻量依赖：%s（下次启动完全生效）',
                                 '、'.join(got))
                    elif r.get('ok'):
                        log.debug('依赖检查：%s', r.get('note') or r.get('skipped') or '无需安装')
                    else:
                        log.info('自动获取依赖未执行：%s',
                                 r.get('note') or r.get('error') or '原因未知')
                except Exception as _e:
                    log.info('自动获取依赖跳过（不影响启动）：%s', _e)

            _th.Thread(target=_autofetch, daemon=True,
                       name='deps-autofetch').start()

        # ---- gRPC 后端（后台线程，Flutter 前端连它）----
        if not args.no_grpc:
            import threading

            _ready = threading.Event()
            _box = {}

            def _grpc_worker():
                try:
                    from backend.rpc.server import serve
                    serve(port=args.port, ready_event=_ready)
                except Exception as e:
                    _box['err'] = e
                    _ready.set()      # 失败了也要放行主线程，否则它一直等
                    log.exception('gRPC server failed to start')

            # 注意：gRPC 服务必须在「非 daemon」线程（或主线程）里跑。
            # 经验证，grpcio 的 server 若由 daemon 线程 start()，会出现
            # 「端口在监听、TCP 已 ESTABLISHED，但任何 RPC 全部 DEADLINE_EXCEEDED
            # 永久死锁」的现象——前端 commandOutput('sandbox:status') 等 await 永远
            # 不返回，runApp() 永不执行 → 主窗口永远不创建（用户视角的「打不开」）。
            # 改为 daemon=False 后，服务端正常 dispatch（0.02s 响应）。
            threading.Thread(target=_grpc_worker, daemon=False).start()
            # 等**真实**的绑定结果再宣布启动 —— 以前是线程一 spawn 就打印
            # 「后端已启动」，可端口被旧进程占住时线程里抛的是 RuntimeError，
            # 用户看到的却是启动成功，然后前端永远连不上（表现为「后端连接
            # 有问题」，但日志里一句错都没有）。
            _ready.wait(timeout=20)
            if _box.get('err') is not None:
                e = _box['err']
                print(f"  [gRPC] 启动失败：{type(e).__name__}: {e}")
                print("  [gRPC] 前端将连不上后端。先确认没有别的 backend 进程"
                      "占着该端口，或改用 --port 换一个。")
            else:
                print(f"  [gRPC] 后端已启动：localhost:{args.port}"
                      "（等待 Flutter 前端连接）")

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
        # gRPC worker 已改为非 daemon 线程（避免 grpcio 在 daemon 线程下不 dispatch
        # 导致前端永久卡在初始化）。非 daemon 线程会阻止 Python 在解释器退出时自动
        # 回收，故这里强制退出，确保 Ctrl+C 能干净结束整个进程。
        os._exit(0)
    except Exception as e:
        log.exception('Fatal error in main')
        print(f"\n错误：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
