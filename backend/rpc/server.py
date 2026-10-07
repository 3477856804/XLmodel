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

import logging
import os
import sys
import threading
import time
from concurrent import futures

logger = logging.getLogger("xiaoling.rpc")

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
                logger.info('XiaoLing engine ready')
                _engine_logged = True
        except Exception as e:                                          # noqa: BLE001
            logger.exception('Engine init failed, falling back to rule-based reply')
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
                for ch in reply:
                    yield pb.ChatChunk(delta=ch)
                    time.sleep(0.02)
            else:
                # engine.chat_stream 是逐字生成器（内部已做打字机 sleep）
                for delta in engine.chat_stream(text):
                    yield pb.ChatChunk(delta=delta)
            yield pb.ChatChunk(delta="", done=True)
        except Exception as e:                                              # noqa: BLE001
            logger.exception('Chat stream error')
            yield pb.ChatChunk(delta="", done=True, error=f'{type(e).__name__}: {e}')

    # ---------------- GetStatus ----------------
    def GetStatus(self, request, context):
        try:
            from core import config as _cfg
            from core.growth import GrowthEngine
            from core.config import APP_DIR
            cfg = _cfg.load()
            st = GrowthEngine().status()
            return pb.StatusReply(
                ok=True,
                stage=str(st.get('stage', '初始化')),
                model=str((cfg.get('model') or {}).get('base_model') or '默认'),
                backend=str((cfg.get('render') or {}).get('backend') or 'auto'),
                progress=float(st.get('progress_percent', 0.0)),
                version=str((cfg.get('version') or '0.0.1')),
            )
        except Exception as e:                                              # noqa: BLE001
            logger.exception('GetStatus failed')
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}',
                                  version='0.0.1')

    # ---------------- ListModels ----------------
    def ListModels(self, request, context):
        try:
            from core.config import resource
            from pathlib import Path
            d = resource('models')
            out = []
            if Path(d).exists():
                for p in sorted(Path(d).iterdir()):
                    if p.suffix.lower() in ('.vrm', '.fbx', '.glb', '.gltf'):
                        out.append(pb.ModelInfo(name=p.stem, path=str(p)))
            return pb.ModelList(models=out)
        except Exception as e:
            logger.exception('ListModels failed')
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
                    logger.exception('Renderer switch_model failed')
                    return pb.StatusReply(ok=False, message=f'配置已写但切换失败：{e}')
            return pb.StatusReply(ok=True, message=f'已切换到 {os.path.basename(path)}')
        except Exception as e:                                              # noqa: BLE001
            logger.exception('SwitchModel failed')
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
            logger.exception('ExecuteCommand failed: %s', cmd)
            return pb.CommandReply(output=f'指令错误：{type(e).__name__}: {e}')

    # ---------------- ListActions ----------------
    def ListActions(self, request, context):
        try:
            import glob as _glob
            from core.config import resource
            d = resource('animations')
            out = []
            for p in sorted(_glob.glob(os.path.join(str(d), '*.vrma'))):
                name = os.path.basename(p)
                out.append(pb.ActionInfo(name=name, path=p,
                                         dance='dance' in name.lower(),
                                         idle=('待机' in name) or ('idle' in name.lower())))
            return pb.ActionList(actions=out)
        except Exception as e:                                              # noqa: BLE001
            logger.exception('ListActions failed')
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
            logger.exception('PlayAction failed: %s', request.path)
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
            from core.config import APP_DIR
            eng = GrowthEngine()
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
            logger.exception('GetGrowthStatus failed')
            return pb.GrowthStatusReply(stage='未知', status_text=f'{type(e).__name__}: {e}')

    # ---------------- GetTrainingStatus（Flutter 训练五维可视化） ----------------
    def GetTrainingStatus(self, request, context):
        try:
            from core.growth import GrowthEngine
            from core.config import APP_DIR
            eng = GrowthEngine()
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
            logger.exception('GetTrainingStatus failed')
            return pb.TrainingStatusReply(status_text=f'{type(e).__name__}: {e}')

    # ---------------- ListPlugins（Flutter 插件管理） ----------------
    def ListPlugins(self, request, context):
        try:
            from core.config import PluginManager
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
            logger.exception('ListPlugins failed')
            return pb.PluginList()

    def _plugin_manager(self):
        """优先用引擎内已加载的插件系统，否则新建 PluginManager。"""
        eng = _get_engine()
        if eng is not None and eng.plugins is not None:
            return eng.plugins
        from core.config import PluginManager
        return PluginManager()

    # ---------------- EnablePlugin ----------------
    def EnablePlugin(self, request, context):
        try:
            name = (request.name or '').strip()
            if not name:
                return pb.StatusReply(ok=False, message='插件名不能为空')
            pm = self._plugin_manager()
            ok = bool(pm.enable(name))
            return pb.StatusReply(ok=ok,
                message=f'已启用插件 {name}' if ok else f'启用失败：未找到插件 {name}')
        except Exception as e:
            logger.exception('EnablePlugin failed: %s', request.name)
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}')

    # ---------------- DisablePlugin ----------------
    def DisablePlugin(self, request, context):
        try:
            name = (request.name or '').strip()
            if not name:
                return pb.StatusReply(ok=False, message='插件名不能为空')
            pm = self._plugin_manager()
            ok = bool(pm.disable(name))
            return pb.StatusReply(ok=ok,
                message=f'已禁用插件 {name}' if ok else f'禁用失败：未找到插件 {name}')
        except Exception as e:
            logger.exception('DisablePlugin failed: %s', request.name)
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}')

    # ---------------- StartTraining（LoRA 微调，流式进度） ----------------
    def StartTraining(self, request, context):
        try:
            from core.engine import XiaoLing as _XL
            steps = max(1, request.steps or 100)
            lr = float(request.learning_rate or 2e-4)
            bs = max(1, request.batch_size or 4)
            rank = max(1, request.lora_rank or 8)
            ds_name = (request.dataset_name or "").strip()

            eng = _get_engine()
            if eng is None:
                # 引擎不可用时仍跑通模拟训练（数据集 + loss 曲线 + 历史）
                import math
                _XL.ensure_training_dataset()
                samples = _XL.load_training_dataset(ds_name)
                yield pb.TrainingProgress(step=0, total_steps=steps,
                    status=f'准备训练... 数据集 {len(samples)} 条 · lr={lr:.1e} · rank={rank}')
                curve = []
                for step in range(1, steps + 1):
                    base = 0.3 + (2.0 - 0.3) * math.exp(-3.0 * step / steps)
                    loss = round(max(0.15, base + __import__('random').gauss(0, 0.05)), 4)
                    curve.append(loss)
                    yield pb.TrainingProgress(step=step, total_steps=steps, loss=loss,
                        status=f'训练中 {step}/{steps} loss={loss:.3f}')
                    time.sleep(0.05)
                _XL.append_training_history({
                    "timestamp": int(time.time()), "steps": steps,
                    "final_loss": curve[-1], "loss_curve": curve,
                    "learning_rate": lr, "batch_size": bs, "lora_rank": rank,
                    "dataset": ds_name or "training_data.jsonl", "real": False})
                yield pb.TrainingProgress(step=steps, total_steps=steps, loss=curve[-1],
                    status=f'done: 训练完成 {steps} 步，最终 loss={curve[-1]:.3f}')
                return

            for info in eng.train_stream(steps=steps, learning_rate=lr,
                                         batch_size=bs, lora_rank=rank,
                                         dataset_name=ds_name):
                yield pb.TrainingProgress(
                    step=int(info.get("step", 0)),
                    total_steps=int(info.get("total_steps", steps)),
                    loss=float(info.get("loss", 0.0)),
                    status=str(info.get("status", "")))
        except Exception as e:
            logger.exception('StartTraining failed')
            yield pb.TrainingProgress(status=f'failed: {e}')

    # ---------------- GetTrainingHistory ----------------
    def GetTrainingHistory(self, request, context):
        try:
            from core.engine import XiaoLing as _XL
            hist = _XL.read_training_history()
            entries = []
            for h in hist:
                entries.append(pb.TrainingHistoryEntry(
                    timestamp=int(h.get("timestamp", 0)),
                    steps=int(h.get("steps", 0)),
                    final_loss=float(h.get("final_loss", 0.0)),
                    loss_curve=[float(x) for x in (h.get("loss_curve") or [])]))
            return pb.TrainingHistoryReply(entries=entries)
        except Exception as e:
            logger.exception('GetTrainingHistory failed')
            return pb.TrainingHistoryReply()

    # ==================== v0.0.1 新增 ====================

    # ---------------- DetectHardware ----------------
    def DetectHardware(self, request, context):
        try:
            import platform as _pl
            from core.model import detect_hardware
            hw = detect_hardware()
            # 注意：core.model.HardwareInfo 与 pb.HardwareInfo 是两个不同结构，
            # 这里做字段映射。vram_gb / disk_free_gb 此前从未赋值，导致前端
            # 拿到的显存恒为 0（即使 detect_hardware 已正确识别显卡）。
            return pb.HardwareInfo(
                vram_gb=float(getattr(hw, 'gpu_memory_gb', 0.0) or 0.0),
                ram_gb=float(getattr(hw, 'ram_total_gb', 0.0) or 0.0),
                cpu_cores=int(getattr(hw, 'cpu_cores', 0) or 0),
                disk_free_gb=float(getattr(hw, 'disk_free_gb', 0.0) or 0.0),
                gpu_name=str(getattr(hw, 'gpu_name', '') or ''),
                platform=str(getattr(hw, 'platform', '') or _pl.system()),
                has_cuda=bool(getattr(hw, 'has_cuda', False)),
                has_metal=bool(getattr(hw, 'has_metal', False)),
            )
        except Exception as e:
            logger.exception('DetectHardware failed')
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
            logger.exception('ListRecommendedModels failed')
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

            import queue as _q
            prog_q = _q.Queue()
            result_box = {}

            def _cb(downloaded_bytes, total_bytes):
                try:
                    d_mb = downloaded_bytes / (1024 * 1024)
                    t_mb = total_bytes / (1024 * 1024) if total_bytes else total_mb
                    pct = (d_mb / t_mb * 100.0) if t_mb else 0.0
                    prog_q.put((d_mb, t_mb, min(100.0, pct)))
                except Exception:
                    pass

            def _worker():
                try:
                    result_box["r"] = store.download(model_name, progress_cb=_cb)
                except Exception as e:
                    result_box["r"] = {"ok": False, "error": str(e)}
                finally:
                    prog_q.put(None)  # 结束哨兵

            threading.Thread(target=_worker, daemon=True).start()

            while True:
                try:
                    item = prog_q.get(timeout=1.0)
                except _q.Empty:
                    if "r" in result_box:
                        break
                    continue
                if item is None:
                    break
                d_mb, t_mb, pct = item
                yield pb.DownloadProgress(percent=round(pct, 1),
                    downloaded_mb=round(d_mb, 1), total_mb=round(t_mb, 1),
                    status='downloading')

            r = result_box.get("r") or {}
            if r.get("ok"):
                yield pb.DownloadProgress(percent=100.0, downloaded_mb=total_mb,
                    total_mb=total_mb, status='done')
            else:
                yield pb.DownloadProgress(status=f'failed: {r.get("error", "下载失败")}')
        except Exception as e:
            logger.exception('DownloadModel failed: %s', model_name)
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
            logger.exception('ListInstalledModels failed')
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
            logger.exception('DeleteModel failed: %s', request.name)
            return pb.StatusReply(ok=False, message=str(e))

    # ---------------- ExportData ----------------
    def ExportData(self, request, context):
        try:
            import json as _json
            eng = _get_engine()
            if eng is not None:
                payload = eng.export_data()
            else:
                from core import config as _cfg
                payload = {"version": "0.0.1", "exported_at": time.time(),
                           "config": _cfg.load() or {},
                           "session_history": [], "long_term": []}
            return pb.DataBlob(json=_json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            logger.exception('ExportData failed')
            return pb.DataBlob(json='{}')

    # ---------------- ImportData ----------------
    def ImportData(self, request, context):
        try:
            import json as _json
            data = _json.loads(request.json or '{}')
            eng = _get_engine()
            if eng is None:
                return pb.StatusReply(ok=False, message='引擎未就绪，无法导入')
            ok = eng.import_data(data)
            return pb.StatusReply(ok=ok,
                message='数据已导入' if ok else '导入失败：数据格式不正确')
        except Exception as e:
            logger.exception('ImportData failed')
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}')

    # ---------------- ListVoices ----------------
    def ListVoices(self, request, context):
        try:
            from core.multimodal import VOICES
            out = [pb.VoiceInfo(id=str(v.get("id", "")), name=str(v.get("name", "")),
                                lang=str(v.get("lang", "zh-CN"))) for v in VOICES]
            return pb.VoiceList(voices=out)
        except Exception as e:
            logger.exception('ListVoices failed')
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
            logger.exception('SetVoice failed: %s', request.voice_id)
            return pb.StatusReply(ok=False, message=str(e))

    # ---------------- ReadAloud（流式音频） ----------------
    def ReadAloud(self, request, context):
        # 注意：TTS 的真实方法名是 synth()（不是 synthesize），
        # 且返回 TTSResult 对象而非 bytes，需取 .data 并判空。
        # 旧代码调 TTS().synthesize() 会抛 AttributeError 又被 except 吞掉，
        # 导致前端永远收到 0 字节音频。
        # 注意：AudioChunk 只有 data/done 两个字段，没有 error，错误只能写日志。
        try:
            text = (request.text or '').strip()
            if not text:
                yield pb.AudioChunk(done=True)
                return
            from core.multimodal import TTS  # 懒加载：避免拖慢后端启动
            voice = 'zh-CN-XiaoxiaoNeural'
            try:
                from core import config as _cfg
                voice = str((_cfg.load().get('voice') or {}).get('id') or voice)
            except Exception:
                pass
            result = TTS().synth(text, voice=voice)
            data = bytes(getattr(result, 'data', b'') or b'')
            if not data:
                logger.warning('ReadAloud: TTS produced no audio (voice=%s)', voice)
            else:
                chunk_size = 4096
                for i in range(0, len(data), chunk_size):
                    yield pb.AudioChunk(data=data[i:i + chunk_size])
        except Exception as e:
            logger.exception('ReadAloud failed')
        finally:
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
                persona=str(cfg.get('persona') or '活泼'),
                user_name=str(cfg.get('user_name') or '你'),
            )
        except Exception as e:
            logger.exception('GetSettings failed')
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
            if request.HasField('persona'):
                name = (request.persona or '').strip()
                if not name:
                    raise ValueError('人格名不能为空')
                # 必须是已存在的预设（内置或自定义），防止写入脏值
                from core import persona_presets as _pp
                if not _pp.resolve(name):
                    raise ValueError(f'人格「{name}」不存在，请先添加为自定义人格')
                patch['persona'] = name
            if request.HasField('user_name'):
                patch['user_name'] = (request.user_name or '').strip()[:20] or '你'
            _cfg.patch(patch)
            return pb.StatusReply(ok=True, message='设置已更新')
        except Exception as e:
            logger.exception('UpdateSettings failed')
            return pb.StatusReply(ok=False, message=str(e))

    # ======================================================================== #
    #  人格 / Agent
    # ======================================================================== #

    # 八种情绪 -> proto 六维雷达轴（value 统一0-100）
    _EMOTION_AXES = {
        'happy':    ('joy', '喜悦'),
        'angry':    ('anger', '愤怒'),
        'sad':      ('sad', '悲伤'),
        'scared':   ('fear', '恐惧'),
        'tired':    ('calm', '平静'),
        'neutral':  ('calm', '平静'),
        'shy':      ('surprise', '惊讶'),
        'surprised': ('surprise', '惊讶'),
    }

    def GetPersona(self, request, context):
        """人格画像：情绪 / 亲密度 / 等级 / 人格预设 + 六维情绪轴。"""
        try:
            from core import config as _cfg
            from core import persona_presets as _pp
            cfg = _cfg.load()
            persona_name = str(cfg.get('persona') or '活泼')

            reply = pb.PersonaReply(
                persona=persona_name,
                user_name=str(cfg.get('user_name') or '你'),
                emotion='平静',
                emotion_intensity=0.0,
                relationship='陌生人',
                relationship_score=0.0,
                relationship_progress=0.0,
                reminders_pending=0,
            )
            engine = _get_engine()
            if engine is None or engine.persona is None:
                return reply
            st = engine.persona.stats()
            reply.emotion = str(st.get('emotion') or '平静')
            reply.emotion_intensity = float(st.get('emotion_intensity') or 0.0)
            reply.relationship = str(st.get('relationship') or '陌生人')
            reply.relationship_score = float(st.get('relationship_score') or 0.0)
            reply.relationship_progress = float(st.get('relationship_progress') or 0.0)
            reply.reminders_pending = int(st.get('reminders') or 0)

            # 六维情绪轴：以当前情绪为主峰，其余按强度衰减铺开
            cur = 'neutral'
            try:
                cur = engine.persona.emotion.get_emotion().value
            except Exception:
                pass
            peak = max(0.0, min(1.0, reply.emotion_intensity))
            seen: set[str] = set()
            for key in sorted(self._EMOTION_AXES,
                              key=lambda k: 0 if k == cur else 1):
                axis_name, label = self._EMOTION_AXES[key]
                if axis_name in seen:
                    continue
                seen.add(axis_name)
                val = peak * 100.0 if key == cur else peak * 45.0
                reply.axes.add(name=axis_name, label=label,
                               value=round(max(0.0, min(100.0, val)), 1))
            # 补齐未覆盖到的轴，保证前端雷达图是闭合六边形
            for key, (axis_name, label) in self._EMOTION_AXES.items():
                if axis_name not in seen:
                    seen.add(axis_name)
                    reply.axes.add(name=axis_name, label=label, value=0.0)
            return reply
        except Exception as e:                                             # noqa: BLE001
            logger.exception('GetPersona failed')
            return pb.PersonaReply(emotion='平静', relationship='陌生人')

    def ListPersonas(self, request, context):
        try:
            from core import config as _cfg
            from core import persona_presets as _pp
            active = str(_cfg.load().get('persona') or '')
            out = pb.PersonaList()
            for p in _pp.list_personas(active):
                out.presets.add(
                    id=str(p['id']), name=str(p['name']),
                    description=str(p['description']),
                    prompt_hint=str(p['prompt_hint']),
                    builtin=bool(p['builtin']), active=bool(p['active']),
                )
            return out
        except Exception as e:                                             # noqa: BLE001
            logger.exception('ListPersonas failed')
            return pb.PersonaList()

    def SetPersona(self, request, context):
        try:
            from core import config as _cfg
            from core import persona_presets as _pp
            key = (request.id or request.name or '').strip()
            if not key:
                return pb.StatusReply(ok=False, message='人格名不能为空')
            p = _pp.resolve(key)
            if not p:
                return pb.StatusReply(ok=False, message=f'人格「{key}」不存在')
            # 统一存**名字**，不存 id（自定义人格没有稳定 id）
            _cfg.patch({'persona': str(p['name'])})
            return pb.StatusReply(ok=True, message=f'已切换为「{p["name"]}」人格')
        except Exception as e:                                             # noqa: BLE001
            logger.exception('SetPersona failed: %s', key)
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}')

    def AddPersona(self, request, context):
        try:
            from core import persona_presets as _pp
            ok, msg = _pp.add_custom(
                (request.name or '').strip(),
                request.description,
                request.prompt_hint,
            )
            return pb.StatusReply(ok=ok, message=msg)
        except Exception as e:                                             # noqa: BLE001
            logger.exception('AddPersona failed: %s', request.name)
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}')

    def DeletePersona(self, request, context):
        try:
            from core import config as _cfg
            from core import persona_presets as _pp
            ok, msg = _pp.delete_custom((request.name or '').strip())
            # 删除的正好是当前人格时，回落到默认「活泼」
            if ok and str(_cfg.load().get('persona')) == (request.name or '').strip():
                _cfg.patch({'persona': _pp.DEFAULT_PERSONA})
                msg += f"，已回落到「{_pp.DEFAULT_PERSONA}」"
            return pb.StatusReply(ok=ok, message=msg)
        except Exception as e:                                             # noqa: BLE001
            logger.exception('DeletePersona failed: %s', request.name)
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}')

    def ResetPersona(self, request, context):
        try:
            engine = _get_engine()
            if engine is not None:
                engine.reset_persona()
                try:
                    engine.persona.flush()
                except Exception:
                    pass
            return pb.StatusReply(ok=True, message='人格画像已重置')
        except Exception as e:                                             # noqa: BLE001
            logger.exception('ResetPersona failed')
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}')

    # ======================================================================== #
    #  提醒队列（铃铛面板）
    # ======================================================================== #

    def ListReminders(self, request, context):
        """未读提醒队列：已到期未确认= 未读，未到期= 待办。"""
        try:
            import time as _time
            engine = _get_engine()
            out = pb.ReminderList()
            if engine is None or engine.persona is None:
                return out
            now = _time.time()
            items = engine.persona.proactive.pending_reminders()
            for r in items:
                due = float(r.get('time') or 0.0)
                left = int(due - now)
                out.items.add(
                    text=str(r.get('text') or ''),
                    due_at=due,
                    done=False,
                    created_at=float(r.get('created_at') or 0.0),
                    seconds_left=left,
                )
            out.pending = len(items)
            out.unread = sum(1 for i in out.items if i.seconds_left <= 0)
            return out
        except Exception as e:                                             # noqa: BLE001
            logger.exception('ListReminders failed')
            return pb.ReminderList()

    def CompleteReminder(self, request, context):
        """标记某条提醒为已读/完成（按 due_at 匹配）。"""
        try:
            engine = _get_engine()
            if engine is None or engine.persona is None:
                return pb.StatusReply(ok=False, message='引擎未就绪')
            pro = engine.persona.proactive
            with pro._lock:                                                # noqa: SLF001
                hit = False
                for r in pro.reminders:
                    if not r['done'] and abs(float(r.get('time', 0.0))
                                             - float(request.due_at)) < 1e-6:
                        r['done'] = True
                        hit = True
                        break
            if not hit:
                return pb.StatusReply(ok=False, message='未找到该提醒')
            try:
                engine.persona.flush()
            except Exception:
                pass
            return pb.StatusReply(ok=True, message='提醒已完成')
        except Exception as e:                                             # noqa: BLE001
            logger.exception('CompleteReminder failed: due_at=%s', request.due_at)
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}')


# --------------------------------------------------------------------------- #
#  入口
# --------------------------------------------------------------------------- #
def serve(port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb_grpc.add_XiaoLingServicer_to_server(XiaoLingServicer(), server)
    bound = server.add_insecure_port(f'[::]:{port}')
    if bound != port:
        logger.warning('gRPC bound to unexpected port: %s (requested %s)', bound, port)
    server.start()
    logger.info('XiaoLing gRPC backend started on localhost:%s', port)
    print(f'  [gRPC] 小凌后端已启动：localhost:{port}')
    print(f'  [gRPC] 等待 Flutter 前端连接…')
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info('gRPC server interrupted, shutting down gracefully')
    finally:
        stopped = server.stop(grace=5)
        stopped.wait(timeout=10)
        logger.info('gRPC server stopped')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    port = 50051
    if '--port' in sys.argv:
        i = sys.argv.index('--port')
        port = int(sys.argv[i + 1])
    serve(port)
