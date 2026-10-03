#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rpc.server —— 小凌 gRPC 后端服务（v0.0.3 新架构）

架构：
    Flutter(UI)  ──gRPC/localhost:50051──>  rpc.server  ──>  xl.XiaoLing(AI)

启动方式：
    python3 -m rpc.server              # 前台跑
    python3 -m rpc.server --port 50051  # 指定端口

设计原则：
    · 引擎懒加载：gRPC 服务先起来，Flutter UI 立刻能连；
      第一次调 Chat 时才真正初始化 XiaoLing（可能要几秒）。
    · 任何业务异常都包成 gRPC status message，绝不让进程崩。
"""
from __future__ import annotations

import os
import sys
import threading
import time
from concurrent import futures

# 让 rpc/ 目录里生成的 pb2 能被 import
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import grpc                                                         # noqa: E402

import xiaoling_pb2 as pb                                           # noqa: E402
import xiaoling_pb2_grpc as pb_grpc                                 # noqa: E402


# --------------------------------------------------------------------------- #
#  引擎单例（懒加载 + 线程锁）
# --------------------------------------------------------------------------- #
_engine = None
_engine_lock = threading.Lock()
_engine_logged = False


def _get_engine(log=print):
    """懒加载 XiaoLing 引擎。任何异常都吞掉并返回 None，由调用方降级。"""
    global _engine, _engine_logged
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            import xl as _xl
            _engine = _xl.XiaoLing()
            if not _engine_logged:
                log('  [gRPC] XiaoLing 引擎就绪')
                _engine_logged = True
        except Exception as e:                                          # noqa: BLE001
            log(f'  [gRPC] 引擎初始化失败（降级为规则回复）：{type(e).__name__}: {e}')
            _engine = None
    return _engine


def _quick_reply(text: str) -> str:
    """引擎不可用时的兜底规则回复。"""
    t = (text or '').strip()
    if any(k in t for k in ('你好', 'hi', 'hello', '在吗')):
        return '你好呀～我在呢。'
    if any(k in t for k in ('你是谁', '名字')):
        return '我是小凌，一个住在你电脑里的女孩。'
    if not t:
        return '嗯？你想说什么呀～'
    return f'你说「{t}」——我记住啦。（AI 引擎还没连上，这是兜底回复）'


# --------------------------------------------------------------------------- #
#  gRPC Servicer
# --------------------------------------------------------------------------- #
class XiaoLingServicer(pb_grpc.XiaoLingServicer):

    # ---------------- Chat（流式） ----------------
    def Chat(self, request, context):
        text = (request.text or '').strip()
        if not text:
            yield pb.ChatChunk(done=True, error='空消息')
            return
        try:
            engine = _get_engine()
            if engine is None:
                reply = _quick_reply(text)
            else:
                reply = str(engine.chat(text))
            # 模拟打字机：按 8 字一块流式吐出
            for i in range(0, len(reply), 8):
                yield pb.ChatChunk(delta=reply[i:i+8])
                time.sleep(0.02)
            yield pb.ChatChunk(done=True)
        except Exception as e:                                              # noqa: BLE001
            yield pb.ChatChunk(done=True, error=f'{type(e).__name__}: {e}')

    # ---------------- GetStatus ----------------
    def GetStatus(self, request, context):
        try:
            from core import config as _cfg
            from core.growth import GrowthEngine
            from core.paths import APP_DIR
            cfg = _cfg.load()
            st = GrowthEngine(base_dir=APP_DIR, log=lambda *a: None).status()
            return pb.StatusReply(
                ok=True,
                stage=str(st.get('stage', '初始化')),
                model=str((cfg.get('model') or {}).get('base_model') or '默认'),
                backend=str((cfg.get('render') or {}).get('backend') or 'auto'),
                progress=float(st.get('progress_percent', 0.0)),
                version=str((cfg.get('version') or '0.0.3')),
            )
        except Exception as e:                                              # noqa: BLE001
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}',
                                  version='0.0.3')

    # ---------------- ListModels ----------------
    def ListModels(self, request, context):
        try:
            from renderer.fbx_loader import list_model_files
            from core.paths import resource
            d = resource('models')
            out = [pb.ModelInfo(name=p.stem, path=str(p)) for p in list_model_files(d)]
            return pb.ModelList(models=out)
        except Exception as e:                                              # noqa: BLE001
            context.set_details(f'列出模型失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.ModelList()

    # ---------------- SwitchModel ----------------
    def SwitchModel(self, request, context):
        try:
            path = request.path
            # 这里只改配置，真正切换由桌宠渲染进程读配置完成
            from core import config as _cfg
            _cfg.patch({'model': {'path': path}})
            return pb.StatusReply(ok=True, message=f'已切换到 {os.path.basename(path)}')
        except Exception as e:                                              # noqa: BLE001
            return pb.StatusReply(ok=False, message=str(e))

    # ---------------- ExecuteCommand ----------------
    def ExecuteCommand(self, request, context):
        cmd = (request.command or '').strip()
        try:
            engine = _get_engine()
            if engine is None:
                return pb.CommandReply(output='引擎未就绪，无法执行指令。')
            from core import fusion as _fusion
            out = _fusion.try_command(engine, cmd)
            return pb.CommandReply(output=str(out) if out is not None else f'未知指令：{cmd}')
        except Exception as e:                                              # noqa: BLE001
            return pb.CommandReply(output=f'指令错误：{type(e).__name__}: {e}')

    # ---------------- ListActions ----------------
    def ListActions(self, request, context):
        try:
            import glob as _glob
            from core.paths import resource
            d = resource('animations')
            out = []
            for p in sorted(_glob.glob(os.path.join(str(d), '*.vrma'))):
                name = os.path.basename(p)
                out.append(pb.ActionInfo(name=name, path=p,
                                         dance='dance' in name.lower(),
                                         idle=('待机' in name) or ('idle' in name.lower())))
            return pb.ActionList(actions=out)
        except Exception as e:                                              # noqa: BLE001
            context.set_details(f'列出动作失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.ActionList()

    # ---------------- PlayAction ----------------
    def PlayAction(self, request, context):
        return pb.StatusReply(ok=True, message=f'播放动作：{os.path.basename(request.path)}')

    # ---------------- Shutdown ----------------
    def Shutdown(self, request, context):
        def _later():
            time.sleep(0.2)
            os._exit(0)
        threading.Thread(target=_later, daemon=True).start()
        return pb.StatusReply(ok=True, message='正在关闭…')


# --------------------------------------------------------------------------- #
#  入口
# --------------------------------------------------------------------------- #
def serve(port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb_grpc.add_XiaoLingServicer_to_server(XiaoLingServicer(), server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f'  [gRPC] 小凌后端已启动：localhost:{port}')
    print(f'  [gRPC] 等待 Flutter 前端连接…')
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(5)


if __name__ == '__main__':
    port = 50051
    if '--port' in sys.argv:
        i = sys.argv.index('--port')
        port = int(sys.argv[i + 1])
    serve(port)
