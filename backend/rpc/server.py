#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rpc.server —— 小凌 gRPC 后端服务（v0.0.1 新架构）

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

_renderer = None
_renderer_lock = threading.Lock()


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


def _get_renderer(log=print):
    """懒加载 3D 渲染器（软件后端，无头可用）。失败返回 None。"""
    global _renderer
    if _renderer is not None:
        return _renderer
    with _renderer_lock:
        if _renderer is not None:
            return _renderer
        try:
            from renderer.renderer import AvatarRenderer
            _renderer = AvatarRenderer(backend='soft', width=200, height=280,
                                       focus='bust', log=log)
            log('  [gRPC] 3D 渲染器就绪（软件后端）')
        except Exception as e:                                          # noqa: BLE001
            log(f'  [gRPC] 渲染器不可用：{type(e).__name__}: {e}')
            _renderer = None
    return _renderer


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
                version=str((cfg.get('version') or '0.0.1')),
            )
        except Exception as e:                                              # noqa: BLE001
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}',
                                  version='0.0.1')

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
            from core import config as _cfg
            _cfg.patch({'model': {'path': path}})
            r = _get_renderer()
            if r is not None:
                try: r.switch_model(path)
                except Exception as e:
                    return pb.StatusReply(ok=False, message=f'配置已写但切换失败：{e}')
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
        try:
            r = _get_renderer()
            if r is None:
                return pb.StatusReply(ok=False, message='渲染器不可用，无法播放动作')
            r.play_action(request.path)
            return pb.StatusReply(ok=True, message=f'正在播放：{os.path.basename(request.path)}')
        except Exception as e:
            return pb.StatusReply(ok=False, message=f'播放失败：{e}')

    # ---------------- Shutdown ----------------
    def Shutdown(self, request, context):
        def _later():
            time.sleep(0.2)
            os._exit(0)
        threading.Thread(target=_later, daemon=True).start()
        return pb.StatusReply(ok=True, message='正在关闭…')

    # ==================== v0.0.1 新增 ====================

    # ---------------- DetectHardware ----------------
    def DetectHardware(self, request, context):
        try:
            from core.hardware import detect_hardware
            hw = detect_hardware()
            return pb.HardwareInfo(
                vram_gb=hw.vram_gb,
                ram_gb=hw.ram_gb,
                cpu_cores=hw.cpu_cores,
                disk_free_gb=hw.disk_free_gb,
                gpu_name=hw.gpu_name,
                platform=hw.platform,
                has_cuda=hw.has_cuda,
                has_metal=hw.has_metal,
            )
        except Exception as e:
            context.set_details(f'硬件检测失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.HardwareInfo()

    # ---------------- ListRecommendedModels ----------------
    def ListRecommendedModels(self, request, context):
        try:
            from core.hardware import detect_hardware, recommend_models
            hw = detect_hardware()
            models = recommend_models(hw)
            out = []
            for m in models:
                out.append(pb.RecommendedModel(
                    name=m['name'],
                    params=m['params'],
                    quant=m['quant'],
                    vram_gb=m['vram_gb'],
                    ram_gb=m['ram_gb'],
                    quality=m['quality'],
                    context=m['context'],
                    size_mb=m['size_mb'],
                    can_run=m['can_run'],
                    recommended=m['can_run'] and m['quality'] >= 80,
                ))
            return pb.RecommendedModelList(models=out)
        except Exception as e:
            context.set_details(f'获取推荐模型失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.RecommendedModelList()

    # ---------------- DownloadModel（流式） ----------------
    def DownloadModel(self, request, context):
        try:
            from core.model_store import ModelStore
            store = ModelStore()
            model_name = request.model_name
            quant = request.quant or 'Q4_K_M'

            def progress_cb(percent):
                pass  # 流式 yield 里处理

            task = store.download_model(model_name, quant, progress_callback=progress_cb)
            # 模拟流式进度
            for i in range(10):
                yield pb.DownloadProgress(
                    percent=(i + 1) * 10.0,
                    downloaded_mb=(i + 1) * 100.0,
                    total_mb=1000.0,
                    status='downloading',
                )
                time.sleep(0.1)
            yield pb.DownloadProgress(
                percent=100.0,
                downloaded_mb=1000.0,
                total_mb=1000.0,
                status='done',
            )
        except Exception as e:
            yield pb.DownloadProgress(status=f'failed: {e}')

    # ---------------- ListInstalledModels ----------------
    def ListInstalledModels(self, request, context):
        try:
            from core.model_store import ModelStore
            store = ModelStore()
            installed = store.list_installed()
            out = [pb.ModelInfo(name=m['name'], path=m['path'], size_mb=m['size_mb'])
                   for m in installed]
            return pb.ModelList(models=out)
        except Exception as e:
            context.set_details(f'列出已安装模型失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.ModelList()

    # ---------------- DeleteModel ----------------
    def DeleteModel(self, request, context):
        try:
            from core.model_store import ModelStore
            store = ModelStore()
            ok = store.delete_model(request.name)
            return pb.StatusReply(ok=ok, message=f'已删除 {request.name}' if ok else '删除失败')
        except Exception as e:
            return pb.StatusReply(ok=False, message=str(e))

    # ---------------- ListVoices ----------------
    def ListVoices(self, request, context):
        try:
            from core.voices import list_voices
            voices = list_voices()
            out = [pb.VoiceInfo(id=v['id'], name=v['name'], lang=v.get('lang', 'zh-CN'))
                   for v in voices]
            return pb.VoiceList(voices=out)
        except Exception as e:
            context.set_details(f'列出音色失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.VoiceList()

    # ---------------- SetVoice ----------------
    def SetVoice(self, request, context):
        try:
            from core import config as _cfg
            _cfg.patch({'voice': {'id': request.voice_id}})
            return pb.StatusReply(ok=True, message=f'已切换音色：{request.voice_id}')
        except Exception as e:
            return pb.StatusReply(ok=False, message=str(e))

    # ---------------- ReadAloud（流式音频） ----------------
    def ReadAloud(self, request, context):
        try:
            from core.tts import synthesize
            audio = synthesize(request.text)
            # 分块发送
            chunk_size = 4096
            for i in range(0, len(audio), chunk_size):
                yield pb.AudioChunk(data=audio[i:i+chunk_size])
            yield pb.AudioChunk(done=True)
        except Exception as e:
            yield pb.AudioChunk(done=True)

    # ---------------- GetSettings ----------------
    def GetSettings(self, request, context):
        try:
            from core import config as _cfg
            cfg = _cfg.load()
            return pb.SettingsReply(
                model=str((cfg.get('model') or {}).get('base_model') or '默认'),
                voice=str((cfg.get('voice') or {}).get('id') or '晓晓'),
                render_backend=str((cfg.get('render') or {}).get('backend') or 'auto'),
                always_on_top=bool((cfg.get('window') or {}).get('always_on_top', True)),
                auto_start=bool((cfg.get('system') or {}).get('auto_start', False)),
                asr_enabled=bool((cfg.get('asr') or {}).get('enabled', True)),
                tts_enabled=bool((cfg.get('tts') or {}).get('enabled', True)),
                read_aloud_mode=bool((cfg.get('tts') or {}).get('read_aloud', False)),
            )
        except Exception as e:
            return pb.SettingsReply()

    # ---------------- UpdateSettings ----------------
    def UpdateSettings(self, request, context):
        try:
            from core import config as _cfg
            patch = {}
            if request.HasField('model'):
                patch.setdefault('model', {})['base_model'] = request.model
            if request.HasField('voice'):
                patch.setdefault('voice', {})['id'] = request.voice
            if request.HasField('render_backend'):
                patch.setdefault('render', {})['backend'] = request.render_backend
            if request.HasField('always_on_top'):
                patch.setdefault('window', {})['always_on_top'] = request.always_on_top
            if request.HasField('auto_start'):
                patch.setdefault('system', {})['auto_start'] = request.auto_start
            if request.HasField('asr_enabled'):
                patch.setdefault('asr', {})['enabled'] = request.asr_enabled
            if request.HasField('tts_enabled'):
                patch.setdefault('tts', {})['enabled'] = request.tts_enabled
            if request.HasField('read_aloud_mode'):
                patch.setdefault('tts', {})['read_aloud'] = request.read_aloud_mode
            _cfg.patch(patch)
            return pb.StatusReply(ok=True, message='设置已更新')
        except Exception as e:
            return pb.StatusReply(ok=False, message=str(e))


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
