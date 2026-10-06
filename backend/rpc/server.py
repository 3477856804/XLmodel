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
            from core.engine import XiaoLing
            _engine = XiaoLing()
            if not _engine_logged:
                log('  [gRPC] XiaoLing 引擎就绪')
                _engine_logged = True
        except Exception as e:                                          # noqa: BLE001
            log(f'  [gRPC] 引擎初始化失败（降级为规则回复）：{type(e).__name__}: {e}')
            _engine = None
    return _engine


def _get_renderer(log=print):
    """3D渲染已移至Flutter端，后端不再渲染。"""
    return None


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


def _parse_size_mb(hint: str) -> float:
    """把 '~2GB' / '512MB' 这类提示解析成 MB 数。"""
    import re
    m = re.search(r'([\d.]+)\s*(GB|MB)', (hint or '').upper())
    if not m:
        return 0.0
    val = float(m.group(1))
    return val * 1024.0 if m.group(2) == 'GB' else val


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
                out = engine.chat(text)
                # engine.chat 返回 (reply, meta)，兼容只返回字符串的旧路径
                reply = out[0] if isinstance(out, (tuple, list)) else out
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
            from core.paths import resource
            from pathlib import Path
            d = resource('models')
            out = []
            if Path(d).exists():
                for p in sorted(Path(d).iterdir()):
                    if p.suffix.lower() in ('.vrm', '.fbx', '.glb', '.gltf'):
                        out.append(pb.ModelInfo(name=p.stem, path=str(p)))
            return pb.ModelList(models=out)
        except Exception as e:
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
            try:
                from core import fusion as _fusion
            except Exception:                                              # noqa: BLE001
                return pb.CommandReply(output=f'指令「{cmd}」：指令解析模块已下线，暂不支持。')
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

    # ---------------- GetGrowthStatus（Flutter 成长可视化） ----------------
    def GetGrowthStatus(self, request, context):
        try:
            from core.growth import GrowthEngine
            from core.paths import APP_DIR
            eng = GrowthEngine(base_dir=APP_DIR, log=lambda *a: None)
            st = eng.status()
            rank = '青铜'
            try:
                rank = str(eng.rank_status().get('rank', '青铜'))
            except Exception:
                pass
            return pb.GrowthStatusReply(
                stage=str(st.get('stage', '初始化')),
                progress_percent=float(st.get('progress_percent', 0.0)),
                total_interactions=int(st.get('total_interactions', 0)),
                current_generation=int(st.get('current_generation', 1)),
                total_generations=int(st.get('total_generations', 1)),
                current_rank=rank,
                emotion=str(st.get('emotion', '平静')),
                training_paused=bool(st.get('paused', False)),
            )
        except Exception as e:
            return pb.GrowthStatusReply(stage='未知', status_text=f'{type(e).__name__}: {e}')

    # ---------------- GetTrainingStatus（Flutter 训练五维可视化） ----------------
    def GetTrainingStatus(self, request, context):
        try:
            from core.growth import GrowthEngine
            from core.paths import APP_DIR
            eng = GrowthEngine(base_dir=APP_DIR, log=lambda *a: None)
            st = eng.status()
            prog = float(st.get('progress_percent', 0.0))
            dims = [
                pb.TrainingDimension(name='感知', value=min(100.0, prog * 1.1), label='环境感知'),
                pb.TrainingDimension(name='理解', value=min(100.0, prog * 0.95), label='语义理解'),
                pb.TrainingDimension(name='决策', value=min(100.0, prog * 0.85), label='行为决策'),
                pb.TrainingDimension(name='进化', value=min(100.0, prog * 0.7), label='自我进化'),
                pb.TrainingDimension(name='守护', value=min(100.0, prog * 0.6), label='安全守护'),
            ]
            return pb.TrainingStatusReply(
                is_training=False,
                current_epoch=0,
                total_epochs=0,
                loss=0.0,
                dimensions=dims,
                status_text=f"成长进度 {prog:.1f}% · {st.get('stage', '初始化')}",
            )
        except Exception as e:
            return pb.TrainingStatusReply(status_text=f'{type(e).__name__}: {e}')

    # ---------------- ListPlugins（Flutter 插件管理） ----------------
    def ListPlugins(self, request, context):
        try:
            from core.plugin_manager import PluginManager
            pm = PluginManager()
            out = []
            for p in pm.list_plugins():
                out.append(pb.PluginInfo(
                    name=str(p.get('name', '')),
                    description=str(p.get('description', '')),
                    version=str(p.get('version', '0.0.1')),
                    enabled=bool(p.get('enabled', True)),
                    category=str(p.get('category', '通用')),
                ))
            return pb.PluginList(plugins=out)
        except Exception as e:
            return pb.PluginList()

    # ---------------- StartTraining（LoRA 微调） ----------------
    def StartTraining(self, request, context):
        try:
            eng = _get_engine()
            local = eng.model_replace.get_model()
            if local is None or local.model is None:
                yield pb.TrainingProgress(status='failed: 模型未加载，请先聊天加载模型')
                return

            steps = max(1, request.steps or 10)
            conversations = [
                {"user": "你好", "assistant": "你好呀～我是小凌，今天想聊什么？"},
                {"user": "你是谁", "assistant": "我是小凌，住在你电脑里的AI女孩。"},
                {"user": "谢谢", "assistant": "不客气～有什么需要随时叫我。"},
            ]

            yield pb.TrainingProgress(step=0, total_steps=steps, status='准备训练...')
            import torch
            from peft import LoraConfig, get_peft_model, TaskType
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM, r=4, lora_alpha=8,
                lora_dropout=0.05, target_modules=["q_proj", "v_proj"],
            )
            model = get_peft_model(local.model, lora_config)
            optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
            model.train()

            step = 0
            for epoch in range(3):
                for conv in conversations:
                    if step >= steps:
                        break
                    messages = [
                        {"role": "system", "content": "你是小凌，住在用户电脑里的AI女孩。"},
                        {"role": "user", "content": conv["user"]},
                        {"role": "assistant", "content": conv["assistant"]},
                    ]
                    text = local.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
                    enc = local.tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
                    ids = enc["input_ids"]
                    labels = ids.clone()
                    optimizer.zero_grad()
                    out = model(input_ids=ids, labels=labels)
                    out.loss.backward()
                    optimizer.step()
                    step += 1
                    yield pb.TrainingProgress(
                        step=step, total_steps=steps,
                        loss=float(out.loss.item()),
                        status=f'training step {step}/{steps}',
                    )
                if step >= steps:
                    break

            save_dir = "adapters/lora_latest"
            model.save_pretrained(save_dir)
            local.tokenizer.save_pretrained(save_dir)
            yield pb.TrainingProgress(step=steps, total_steps=steps,
                status=f'done: 适配器已保存到 {save_dir}')
        except Exception as e:
            yield pb.TrainingProgress(status=f'failed: {e}')

    # ==================== v0.0.1 新增 ====================

    # ---------------- DetectHardware ----------------
    def DetectHardware(self, request, context):
        try:
            import platform as _pl
            from core.system import get_system_info, detect_best_device
            info = get_system_info()
            mem = info.get('memory', {}) or {}
            device = detect_best_device()
            return pb.HardwareInfo(
                ram_gb=float(mem.get('total_gb', 0.0) or 0.0),
                cpu_cores=int(os.cpu_count() or 0),
                gpu_name=str(info.get('gpu', '')),
                platform=info.get('os', _pl.system()),
                has_cuda=(device == 'cuda'),
                has_metal=(device == 'mps'),
            )
        except Exception as e:
            context.set_details(f'硬件检测失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.HardwareInfo()

    # ---------------- ListRecommendedModels ----------------
    def ListRecommendedModels(self, request, context):
        try:
            from core.model import MODEL_PRESETS, list_recommended
            # 先检测硬件
            hw = self.DetectHardware(pb.Empty(), context)
            ram = hw.ram_gb or 8.0
            out = []
            for item in list_recommended():
                need_gb = item["size_mb"] / 1024.0 * 1.5  # 加载需要1.5倍大小
                can_run = ram >= need_gb
                out.append(pb.RecommendedModel(
                    name=item["name"],
                    params = f'{int(item["size_mb"]//1024)}B' if item["size_mb"] >= 1024 else f'{item["size_mb"]}MB',
                    size_mb=item["size_mb"],
                    ram_gb=round(need_gb, 1),
                    quality=int(item["score"]),
                    context="32K",
                    can_run=can_run,
                    recommended=(can_run and item["ratio"] >= 30),
                ))
            return pb.RecommendedModelList(models=out)
        except Exception as e:
            context.set_details(f'获取推荐模型失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.RecommendedModelList()

    # ---------------- DownloadModel（流式） ----------------
    def DownloadModel(self, request, context):
        try:
            from core.model import ModelStore, MODEL_PRESETS
            store = ModelStore()
            model_name = request.model_name
            preset = MODEL_PRESETS.get(model_name)
            if not preset:
                yield pb.DownloadProgress(status=f'failed: 未知模型 {model_name}')
                return
            total_mb = float(preset["size_mb"])
            yield pb.DownloadProgress(percent=0.0, downloaded_mb=0.0,
                total_mb=total_mb, status=f'downloading: {model_name}')
            ok = store.download(model_name)
            if ok:
                yield pb.DownloadProgress(percent=100.0, downloaded_mb=total_mb,
                    total_mb=total_mb, status='done')
            else:
                yield pb.DownloadProgress(status='failed: 下载失败')
        except Exception as e:
            yield pb.DownloadProgress(status=f'failed: {e}')

    # ---------------- ListInstalledModels ----------------
    def ListInstalledModels(self, request, context):
        try:
            from core.model import ModelStore
            store = ModelStore()
            installed = store.list_models()
            out = [pb.ModelInfo(name=n, path=str(store.store_dir / n)) for n in installed]
            return pb.ModelList(models=out)
        except Exception as e:
            context.set_details(f'列出已安装模型失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.ModelList()

    # ---------------- DeleteModel ----------------
    def DeleteModel(self, request, context):
        try:
            import shutil
            from core.model import ModelStore
            store = ModelStore()
            target = store.store_dir / request.name
            if target.exists() and target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
                return pb.StatusReply(ok=True, message=f'已删除 {request.name}')
            return pb.StatusReply(ok=False, message='未找到该模型')
        except Exception as e:
            return pb.StatusReply(ok=False, message=str(e))

    # ---------------- ListVoices ----------------
    def ListVoices(self, request, context):
        try:
            from core.multimodal import VOICE_MAP
            out = [pb.VoiceInfo(id=v, name=k, lang='zh-CN') for k, v in VOICE_MAP.items()]
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
            from core.multimodal import TTS
            audio = TTS().synthesize(request.text) or b''
            # 分块发送
            chunk_size = 4096
            for i in range(0, len(audio), chunk_size):
                yield pb.AudioChunk(data=audio[i:i+chunk_size])
            yield pb.AudioChunk(done=True)
        except Exception:
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


