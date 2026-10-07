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
import uuid
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

# 项目根目录：server.py 位于 backend/rpc/，向上三级即 xl_project/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Terminal / File 单例（懒加载 + 线程锁）
_terminal_manager = None
_terminal_manager_lock = threading.Lock()

_file_manager = None
_file_manager_lock = threading.Lock()


def _get_terminal_manager():
    """懒加载 TerminalManager 单例。"""
    global _terminal_manager
    if _terminal_manager is not None:
        return _terminal_manager
    with _terminal_manager_lock:
        if _terminal_manager is not None:
            return _terminal_manager
        from core.terminal import TerminalManager
        _terminal_manager = TerminalManager()
    return _terminal_manager


def _get_file_manager():
    """懒加载 FileManager 单例（以项目根路径初始化）。"""
    global _file_manager
    if _file_manager is not None:
        return _file_manager
    with _file_manager_lock:
        if _file_manager is not None:
            return _file_manager
        from core.fileops import FileManager
        _file_manager = FileManager(_PROJECT_ROOT)
    return _file_manager


def _get_project_context():
    """懒加载 ProjectContext（每次基于最新根路径新建，轻量）。"""
    from core.context import ProjectContext
    return ProjectContext(_PROJECT_ROOT)


_security_center = None
_security_center_lock = threading.Lock()
_mcp_manager = None
_mcp_manager_lock = threading.Lock()
_workflow_engine = None
_workflow_engine_lock = threading.Lock()


def _get_security_center():
    global _security_center
    if _security_center is not None:
        return _security_center
    with _security_center_lock:
        if _security_center is None:
            from core.security_center import SecurityCenter
            _security_center = SecurityCenter()
    return _security_center


def _get_mcp_manager():
    global _mcp_manager
    if _mcp_manager is not None:
        return _mcp_manager
    with _mcp_manager_lock:
        if _mcp_manager is None:
            from core.mcp_client import MCPManager
            _mcp_manager = MCPManager()
    return _mcp_manager


def _get_workflow_engine():
    global _workflow_engine
    if _workflow_engine is not None:
        return _workflow_engine
    with _workflow_engine_lock:
        if _workflow_engine is None:
            from core.workflow_engine import WorkflowEngine
            _workflow_engine = WorkflowEngine()
    return _workflow_engine


def _handle_ext_command(cmd: str) -> str:
    """轻量扩展命令路由：插件 / 工作流 / 安全 / MCP。返回 JSON 字符串。"""
    import json as _json

    def _ok(**kw):
        d = {"ok": True}
        d.update(kw)
        return _json.dumps(d, ensure_ascii=False)

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    try:
        if cmd.startswith("plugin:"):
            rest = cmd[len("plugin:"):].strip()
            op, _, arg = (rest + " ").partition(" ")
            arg = arg.strip()
            from core.config import PluginManager
            pmgr = PluginManager()
            if op == "list":
                return _ok(plugins=pmgr.list_plugins())
            if op == "enable":
                return _ok(message=f"已启用 {arg}") if pmgr.enable(arg) else _err(f"未找到插件 {arg}")
            if op == "disable":
                return _ok(message=f"已禁用 {arg}") if pmgr.disable(arg) else _err(f"未找到插件 {arg}")
            if op == "install":
                name = arg
                if not name:
                    return _err("插件名不能为空")
                import os as _os
                pdir = _os.path.join(str(pmgr.plugins_dir), name)
                _os.makedirs(pdir, exist_ok=True)
                manifest = {
                    "name": name,
                    "version": "1.0.0",
                    "description": f"社区插件 {name}",
                    "category": "community",
                    "enabled": True,
                }
                with open(_os.path.join(pdir, "manifest.json"), "w", encoding="utf-8") as f:
                    _json.dump(manifest, f, ensure_ascii=False, indent=2)
                pmgr._load_external()  # noqa: SLF001
                pmgr.enable(name)
                return _ok(message=f"插件 {name} 已安装并启用")
            return _err(f"未知插件操作: {op}")

        if cmd.startswith("workflow:"):
            rest = cmd[len("workflow:"):].strip()
            op, _, payload = rest.partition(" ")
            payload = payload.strip()
            eng = _get_workflow_engine()
            if op == "list":
                return _ok(workflows=eng.list_workflows())
            if op == "run":
                spec = _json.loads(payload) if payload else {}
                wf_name = spec.get("name") or "ui_workflow"
                nodes = spec.get("nodes") or []
                wf = eng.create_workflow(wf_name, spec.get("description", ""))
                from core.workflow_engine import WorkflowNode
                id_map = {}
                for n in nodes:
                    node = WorkflowNode(
                        n.get("id"), n.get("type", "action"),
                        config=dict(n.get("config") or {}),
                    )
                    wf.add_node(node)
                    id_map[n.get("id")] = node
                for n in nodes:
                    node = id_map.get(n.get("id"))
                    nxt = n.get("next")
                    if node is not None and nxt and nxt in id_map:
                        wf.connect(node.id, id_map[nxt].id)
                result = eng.execute(wf_name, context=dict(spec.get("context") or {}))
                return _json.dumps(result, ensure_ascii=False)
            return _err(f"未知工作流操作: {op}")

        if cmd.startswith("security:"):
            rest = cmd[len("security:"):].strip()
            op, _, arg = (rest + " ").partition(" ")
            arg = arg.strip()
            sc = _get_security_center()
            if op == "config":
                cfg = sc.get_config()
                return _ok(
                    permissions=cfg.get("tool_permissions", {}),
                    require_approval=list(cfg.get("require_approval", [])),
                    protected_dirs=list(cfg.get("protected_dirs", [])),
                    audit_log=sc.get_audit_log(limit=50),
                )
            if op == "set":
                tool, _, val = arg.partition(" ")
                sc.set_permission(tool.strip(), val.strip().lower() == "true")
                sc.audit("set_permission", f"{tool}={val}")
                return _ok(message=f"{tool} 权限已更新")
            if op == "add_dir":
                sc.add_protected_dir(arg)
                sc.audit("add_protected_dir", arg)
                return _ok(message=f"已保护 {arg}")
            if op == "remove_dir":
                sc.remove_protected_dir(arg)
                sc.audit("remove_protected_dir", arg)
                return _ok(message=f"已移除保护 {arg}")
            return _err(f"未知安全操作: {op}")

        if cmd.startswith("mcp:"):
            rest = cmd[len("mcp:"):].strip()
            op, _, payload = rest.partition(" ")
            payload = payload.strip()
            mgr = _get_mcp_manager()
            if op == "list":
                return _ok(servers=mgr.list_servers())
            if op == "tools":
                return _ok(tools=mgr.get_all_tools())
            if op == "add":
                spec = _json.loads(payload) if payload else {}
                name = (spec.get("name") or "").strip()
                if not name:
                    return _err("服务器名不能为空")
                cfg = {
                    "type": spec.get("type", "stdio"),
                    "command": spec.get("command", ""),
                    "url": spec.get("url", ""),
                    "args": spec.get("args", []),
                }
                ok = mgr.add_server(name, cfg)
                return _ok(message=f"已添加 {name}") if ok else _err(f"添加 {name} 失败")
            if op == "remove":
                ok = mgr.remove_server(payload)
                return _ok(message=f"已删除 {payload}") if ok else _err(f"未找到 {payload}")
            if op == "connect":
                ok = mgr.connect_server(payload)
                return _ok(message=f"已连接 {payload}") if ok else _err(f"连接 {payload} 失败")
            if op == "disconnect":
                mgr.disconnect_server(payload)
                return _ok(message=f"已断开 {payload}")
            return _err(f"未知 MCP 操作: {op}")
    except Exception as e:  # noqa: BLE001
        logger.exception("ext command failed: %s", cmd)
        return _err(f"{type(e).__name__}: {e}")

    return _err(f"未知命令: {cmd}")


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
#  请求统计（中间件：累计每个 RPC 的调用次数与平均耗时）
# --------------------------------------------------------------------------- #
_request_stats: dict = {}        # method_name -> {"count": int, "total_ms": float, "errors": int}
_server_started_at: float = time.time()
_STREAM_IDLE_TIMEOUT = 60.0     # 流式方法 60 秒无新数据则视为客户端断开


def _log_request(method_name: str, duration_ms: float, ok: bool) -> None:
    """在每个 RPC 方法的 finally 块中记录请求方法、耗时、成功/失败。"""
    st = _request_stats.setdefault(method_name,
                                   {"count": 0, "total_ms": 0.0, "errors": 0})
    st["count"] += 1
    st["total_ms"] += duration_ms
    if not ok:
        st["errors"] += 1
    logger.info('RPC %s took %.1fms (%s)', method_name, duration_ms,
                'ok' if ok else 'error')


def _avg_request_ms() -> float:
    total = sum(s["count"] for s in _request_stats.values())
    if not total:
        return 0.0
    return sum(s["total_ms"] for s in _request_stats.values()) / total


# --------------------------------------------------------------------------- #
#  训练实时状态跟踪（server 层维护，供 GetTrainingStatus 轮询）
#  XiaoLing.train_stream 是纯生成器，不在自身实例上记录运行状态；
#  由于只能改动本文件，这里在 gRPC 层维护一份实时训练快照，
#  StartTraining 流式过程中持续更新，GetTrainingStatus 读取真实值。
# --------------------------------------------------------------------------- #
_train_state: dict = {
    "active": False,     # 当前是否有训练任务在跑
    "step": 0,           # 当前步数（epoch）
    "total_steps": 0,    # 总步数
    "loss": 0.0,         # 最近一步 loss
    "final_loss": 0.0,   # 最近一次训练的最终 loss
    "real": False,       # 是否为真实权重训练（否则为模拟曲线）
    "status": "",        # 人类可读状态
    "started_at": 0.0,
}
_train_state_lock = threading.Lock()


def _train_state_update(**kw) -> None:
    """线程安全地更新训练实时快照；任何异常都被吞掉，绝不影响训练流。"""
    try:
        with _train_state_lock:
            _train_state.update(kw)
    except Exception:                                                          # noqa: BLE001
        pass


def _train_state_snapshot() -> dict:
    """返回训练实时快照的副本；失败时返回一份安全默认值。"""
    try:
        with _train_state_lock:
            return dict(_train_state)
    except Exception:                                                          # noqa: BLE001
        return {"active": False, "step": 0, "total_steps": 0, "loss": 0.0,
                "final_loss": 0.0, "real": False, "status": "", "started_at": 0.0}


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
        _t0 = time.time()
        _last_yield = time.time()   # 心跳：记录最后一次 yield 时间
        _ok = False
        try:
            engine = _get_engine()
            if engine is None:
                reply = _quick_reply(text)
                for ch in reply:
                    if time.time() - _last_yield > _STREAM_IDLE_TIMEOUT:
                        logger.warning('Chat stream idle timeout, client gone')
                        break
                    yield pb.ChatChunk(delta=ch)
                    _last_yield = time.time()
                    time.sleep(0.02)
            else:
                # engine.chat_stream 是逐字生成器（内部已做打字机 sleep）
                for delta in engine.chat_stream(text):
                    if time.time() - _last_yield > _STREAM_IDLE_TIMEOUT:
                        logger.warning('Chat stream idle timeout, client gone')
                        break
                    yield pb.ChatChunk(delta=delta)
                    _last_yield = time.time()
            _ok = True
            yield pb.ChatChunk(delta="", done=True)
        except Exception as e:                                              # noqa: BLE001
            logger.exception('Chat stream error')
            yield pb.ChatChunk(delta="", done=True, error=f'{type(e).__name__}: {e}')
        finally:
            _log_request('Chat', (time.time() - _t0) * 1000.0, _ok)

    # ---------------- GetStatus ----------------
    def GetStatus(self, request, context):
        _t0 = time.time()
        _ok = False
        try:
            from core import config as _cfg
            from core.growth import GrowthEngine
            from core.config import APP_DIR
            cfg = _cfg.load()
            st = GrowthEngine().status()
            # 运行时统计：运行时长、总请求数、平均响应时间，写入 message 字段
            uptime = int(time.time() - _server_started_at)
            total_req = sum(s["count"] for s in _request_stats.values())
            info = (f"uptime={uptime}s requests={total_req} "
                    f"avg_ms={_avg_request_ms():.1f}")
            _ok = True
            return pb.StatusReply(
                ok=True,
                stage=str(st.get('stage', '初始化')),
                model=str((cfg.get('model') or {}).get('base_model') or '默认'),
                backend=str((cfg.get('render') or {}).get('backend') or 'auto'),
                progress=float(st.get('progress_percent', 0.0)),
                version=str((cfg.get('version') or '0.0.1')),
                message=info,
            )
        except Exception as e:                                              # noqa: BLE001
            logger.exception('GetStatus failed')
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}',
                                  version='0.0.1')
        finally:
            _log_request('GetStatus', (time.time() - _t0) * 1000.0, _ok)

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
            if cmd.startswith(('plugin:', 'workflow:', 'security:', 'mcp:')):
                return pb.CommandReply(output=_handle_ext_command(cmd))
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
            eng = GrowthEngine()
            st = eng.status()
            prog = float(st.get('progress_percent', 0.0) or 0.0)
            stage = str(st.get('stage', '初始化'))

            # rank：GrowthEngine.rank 是 RankManager，正确方法是 .status()（返回 dict），
            # 不存在 eng.rank_status()。LoRA r 值映射为段位名。
            rank_name = '青铜'
            try:
                rinfo = eng.rank.status() or {}
                r = int(rinfo.get('rank', 0) or 0)
                tier_map = [(0, '青铜'), (8, '黑铁'), (16, '白银'), (32, '黄金'),
                            (64, '铂金'), (128, '钻石'), (256, '王者')]
                for threshold, name in tier_map:
                    if r >= threshold:
                        rank_name = name
            except Exception:                                                   # noqa: BLE001
                pass

            # 总互动数：优先取引擎累计对话轮次，回落到成长数据仓库记录数
            total_inter = 0
            try:
                e = _get_engine()
                if e is not None:
                    total_inter = int(getattr(e, 'interaction_count', 0) or 0)
            except Exception:                                                   # noqa: BLE001
                total_inter = 0
            if total_inter <= 0:
                try:
                    total_inter = int(eng.store.stats().get('total', 0) or 0)
                except Exception:                                               # noqa: BLE001
                    total_inter = int(st.get('rounds', 0) or 0)

            # 代数：生命周期注册表中的代次
            cur_gen, max_gen = 1, 1
            try:
                gens = eng.lifecycle.generations() or []
                if gens:
                    cur_gen = max(int(g.get('gen', 1) or 1) for g in gens)
                try:
                    max_gen = int(eng.cfg('max_generations', 5) or 5)
                except Exception:                                               # noqa: BLE001
                    max_gen = max(len(gens), 1)
            except Exception:                                                   # noqa: BLE001
                pass

            # 情绪：来自人格引擎（GrowthEngine 本身不含情绪）
            emotion = '平静'
            try:
                e = _get_engine()
                if e is not None and getattr(e, 'persona', None) is not None:
                    emotion = str(e.persona.emotion.get_emotion_label() or '平静')
            except Exception:                                                   # noqa: BLE001
                pass

            return pb.GrowthStatusReply(
                stage=stage,
                progress_percent=prog,
                total_interactions=int(total_inter),
                current_generation=int(cur_gen),
                total_generations=int(max_gen),
                current_rank=rank_name,
                emotion=emotion,
                training_paused=bool(st.get('paused', False)),
                status_text=f'{stage} · 段位 {rank_name} · {prog:.1f}%',
            )
        except Exception as e:
            logger.exception('GetGrowthStatus failed')
            return pb.GrowthStatusReply(stage='未知', status_text=f'{type(e).__name__}: {e}')

    # ---------------- GetTrainingStatus（Flutter 训练五维可视化） ----------------
    def GetTrainingStatus(self, request, context):
        try:
            snap = _train_state_snapshot()
            is_training = bool(snap.get('active', False))
            cur_step = int(snap.get('step', 0) or 0)
            total_steps = int(snap.get('total_steps', 0) or 0)
            loss = float(snap.get('loss', 0.0) or 0.0)

            # 五维雷达：基于真实子系统统计量（数据仓库总量 / 已消化样本 /
            # 平均质量分 / 成长进度 / 训练轮次），不再是 progress_percent 乘固定系数。
            dims = []
            status_text = str(snap.get('status') or '暂无训练数据')
            try:
                from core.growth import GrowthEngine
                eng = GrowthEngine()
                st = eng.status()
                prog = float(st.get('progress_percent', 0.0) or 0.0)
                rounds = int(st.get('rounds', 0) or 0)
                try:
                    ds = eng.store.stats() or {}
                except Exception:                                               # noqa: BLE001
                    ds = {}
                total_data = int(ds.get('total', 0) or 0)
                trained = int(ds.get('used_in_training', 0) or 0)
                avg_q = float(ds.get('avg_quality', 0.0) or 0.0)
                # 感知：观察到的对话/数据量（平方根封顶到 100，避免早期为 0）
                percept = min(100.0, (max(0, total_data) ** 0.5) * 2.0)
                # 理解：已进入训练消化的样本占比
                understand = (trained / total_data * 100.0) if total_data > 0 else 0.0
                # 决策：样本平均质量分（0-1 -> 0-100）
                decide = max(0.0, min(100.0, avg_q * 100.0))
                # 进化：成长进度
                evolve = min(100.0, prog)
                # 守护：训练轮次积累带来的成熟度（初始 10，每轮 +8 封顶）
                guard = min(100.0, 10.0 + rounds * 8.0)
                dims = [
                    pb.TrainingDimension(name='感知', value=round(percept, 1), label='环境感知'),
                    pb.TrainingDimension(name='理解', value=round(understand, 1), label='语义理解'),
                    pb.TrainingDimension(name='决策', value=round(decide, 1), label='行为决策'),
                    pb.TrainingDimension(name='进化', value=round(evolve, 1), label='自我进化'),
                    pb.TrainingDimension(name='守护', value=round(guard, 1), label='安全守护'),
                ]
                status_text = (f"成长进度 {prog:.1f}% · {st.get('stage', '初始化')}"
                               + (f" · 训练中 {cur_step}/{total_steps}" if is_training else ""))
            except Exception:                                                   # noqa: BLE001
                dims = [
                    pb.TrainingDimension(name='感知', value=0.0, label='环境感知'),
                    pb.TrainingDimension(name='理解', value=0.0, label='语义理解'),
                    pb.TrainingDimension(name='决策', value=0.0, label='行为决策'),
                    pb.TrainingDimension(name='进化', value=0.0, label='自我进化'),
                    pb.TrainingDimension(name='守护', value=0.0, label='安全守护'),
                ]
            return pb.TrainingStatusReply(
                is_training=is_training,
                current_epoch=cur_step,
                total_epochs=total_steps,
                loss=loss,
                dimensions=dims,
                status_text=str(status_text),
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

            # 标记训练开始，实时快照供 GetTrainingStatus 轮询
            _train_state_update(active=True, step=0, total_steps=steps,
                                loss=0.0, final_loss=0.0, real=False,
                                status='准备训练...', started_at=time.time())
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
                    _train_state_update(active=True, step=step, total_steps=steps,
                                        loss=loss, status=f'训练中 {step}/{steps} loss={loss:.3f}')
                    yield pb.TrainingProgress(step=step, total_steps=steps, loss=loss,
                        status=f'训练中 {step}/{steps} loss={loss:.3f}')
                    time.sleep(0.05)
                _XL.append_training_history({
                    "timestamp": int(time.time()), "steps": steps,
                    "final_loss": curve[-1], "loss_curve": curve,
                    "learning_rate": lr, "batch_size": bs, "lora_rank": rank,
                    "dataset": ds_name or "training_data.jsonl", "real": False})
                _train_state_update(active=False, step=steps, total_steps=steps,
                                    loss=curve[-1], final_loss=curve[-1], real=False,
                                    status=f'done: 训练完成 {steps} 步，最终 loss={curve[-1]:.3f}')
                yield pb.TrainingProgress(step=steps, total_steps=steps, loss=curve[-1],
                    status=f'done: 训练完成 {steps} 步，最终 loss={curve[-1]:.3f}')
                return

            for info in eng.train_stream(steps=steps, learning_rate=lr,
                                         batch_size=bs, lora_rank=rank,
                                         dataset_name=ds_name):
                s = int(info.get("step", 0))
                t = int(info.get("total_steps", steps))
                l = float(info.get("loss", 0.0))
                _train_state_update(active=(s < t), step=s, total_steps=t, loss=l,
                                    real=True, status=str(info.get("status", "")))
                yield pb.TrainingProgress(
                    step=s, total_steps=t, loss=l,
                    status=str(info.get("status", "")))
        except Exception as e:
            logger.exception('StartTraining failed')
            _train_state_update(active=False, status=f'failed: {e}')
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

    # ======================================================================== #
    #  v0.0.1 新增：Agent / Terminal / File / Search / ProjectContext
    # ======================================================================== #

    # ---------------- AgentStart（流式） ----------------
    def AgentStart(self, request, context):
        try:
            from core.agent import AgentEngine
            engine = _get_engine()
            agent = AgentEngine(engine)
            task = request.task or ''
            ctx = request.context or ''
            autonomous = bool(request.autonomous)
            max_steps = int(request.max_steps or 20)
            for event in agent.run(task, ctx, autonomous, max_steps):
                yield pb.AgentEvent(
                    type=event.get("type", ""),
                    content=event.get("content", ""),
                    tool_name=event.get("tool_name", ""),
                    tool_args=event.get("tool_args", ""),
                    tool_result=event.get("tool_result", ""),
                    step=int(event.get("step", 0)),
                    total_steps=int(event.get("total_steps", 0)),
                    done=bool(event.get("done", False)),
                    error=event.get("error", ""),
                )
        except Exception as e:                                              # noqa: BLE001
            logger.exception("AgentStart failed")
            yield pb.AgentEvent(type="error", error=str(e), done=True)

    # ---------------- TerminalCreate ----------------
    def TerminalCreate(self, request, context):
        try:
            tm = _get_terminal_manager()
            session_id = tm.create()
            return pb.TerminalSession(id=str(session_id))
        except Exception as e:                                              # noqa: BLE001
            logger.exception('TerminalCreate failed')
            context.set_details(f'创建终端失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.TerminalSession()

    # ---------------- TerminalWrite ----------------
    def TerminalWrite(self, request, context):
        try:
            tm = _get_terminal_manager()
            tm.write(request.session_id, request.data or '')
            return pb.Empty()
        except Exception as e:                                              # noqa: BLE001
            logger.exception('TerminalWrite failed: %s', request.session_id)
            context.set_details(f'写入终端失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.Empty()

    # ---------------- TerminalRead（流式） ----------------
    def TerminalRead(self, request, context):
        try:
            tm = _get_terminal_manager()
            for chunk in tm.read(request.id):
                yield pb.TerminalOutput(data=str(chunk), closed=False)
            yield pb.TerminalOutput(data="", closed=True)
        except Exception as e:                                              # noqa: BLE001
            logger.exception('TerminalRead failed: %s', request.id)
            yield pb.TerminalOutput(data=f'error: {e}', closed=True)

    # ---------------- TerminalClose ----------------
    def TerminalClose(self, request, context):
        try:
            tm = _get_terminal_manager()
            tm.close(request.id)
            return pb.Empty()
        except Exception as e:                                              # noqa: BLE001
            logger.exception('TerminalClose failed: %s', request.id)
            context.set_details(f'关闭终端失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.Empty()

    # ---------------- FileList ----------------
    def FileList(self, request, context):
        try:
            fm = _get_file_manager()
            result = fm.list_dir(request.path or '.')
            items = []
            for it in (result.get('items') or []):
                items.append(pb.FileItem(
                    name=str(it.get('name', '')),
                    path=str(it.get('path', '')),
                    is_dir=bool(it.get('is_dir', False)),
                    size=int(it.get('size', 0) or 0),
                    modified=str(it.get('modified', '')),
                    extension=str(it.get('extension', '')),
                ))
            return pb.FileListReply(
                items=items,
                current_path=str(result.get('current_path', '')),
                parent_path=str(result.get('parent_path', '')),
            )
        except Exception as e:                                              # noqa: BLE001
            logger.exception('FileList failed: %s', request.path)
            return pb.FileListReply()

    # ---------------- FileRead ----------------
    def FileRead(self, request, context):
        try:
            fm = _get_file_manager()
            result = fm.read_file(request.path)
            return pb.FileContent(
                path=str(result.get('path', request.path)),
                content=str(result.get('content', '')),
                language=str(result.get('language', '')),
                lines=int(result.get('lines', 0) or 0),
                size=int(result.get('size', 0) or 0),
            )
        except Exception as e:                                              # noqa: BLE001
            logger.exception('FileRead failed: %s', request.path)
            return pb.FileContent(path=request.path)

    # ---------------- FileWrite ----------------
    def FileWrite(self, request, context):
        try:
            fm = _get_file_manager()
            ok = bool(fm.write_file(request.path, request.content or '',
                                    bool(request.append)))
            return pb.StatusReply(ok=ok,
                message='写入成功' if ok else '写入失败')
        except Exception as e:                                              # noqa: BLE001
            logger.exception('FileWrite failed: %s', request.path)
            return pb.StatusReply(ok=False, message=f'{type(e).__name__}: {e}')

    # ---------------- CodeSearch ----------------
    def CodeSearch(self, request, context):
        _t0 = time.time()
        try:
            from core.search import search_code
            matches = search_code(
                request.query or '',
                request.path or _PROJECT_ROOT,
                int(request.max_results or 50),
            ) or []
            code_matches = [
                pb.CodeMatch(
                    file=str(m.get('file', '')),
                    line=int(m.get('line', 0) or 0),
                    column=int(m.get('column', 0) or 0),
                    text=str(m.get('text', '')),
                    symbol=str(m.get('symbol', '')),
                    kind=str(m.get('kind', '')),
                ) for m in matches
            ]
            return pb.CodeSearchReply(
                matches=code_matches,
                total=len(code_matches),
                elapsed_ms=(time.time() - _t0) * 1000.0,
            )
        except Exception as e:                                              # noqa: BLE001
            logger.exception('CodeSearch failed: %s', request.query)
            return pb.CodeSearchReply(total=0, elapsed_ms=(time.time() - _t0) * 1000.0)

    # ---------------- ProjectContext ----------------
    def ProjectContext(self, request, context):
        try:
            pc = _get_project_context()
            result = pc.collect() or {}
            files = [
                pb.ProjectFile(
                    path=str(f.get('path', '')),
                    language=str(f.get('language', '')),
                    lines=int(f.get('lines', 0) or 0),
                ) for f in (result.get('files') or [])
            ]
            return pb.ProjectContextReply(
                root_path=str(result.get('root_path', _PROJECT_ROOT)),
                project_name=str(result.get('project_name', '')),
                files=files,
                total_files=int(result.get('total_files', len(files)) or 0),
                total_lines=int(result.get('total_lines', 0) or 0),
                languages=[str(x) for x in (result.get('languages') or [])],
                readme=str(result.get('readme', '')),
            )
        except Exception as e:                                              # noqa: BLE001
            logger.exception('ProjectContext failed')
            return pb.ProjectContextReply(root_path=_PROJECT_ROOT)


# --------------------------------------------------------------------------- #
#  增量完善（v0.0.1）：请求限流 / 服务端指标 / 优雅关闭跟踪 / 子系统健康
#  说明：以下均为独立新增工具类与函数，不改动上方既有 servicer 方法签名与行为。
# --------------------------------------------------------------------------- #
import collections as _collections                                  # noqa: E402
import contextlib as _contextlib                                    # noqa: E402


class RateLimiter:
    """固定窗口限流器：按 (client_ip, method) 维度限速。

    每个时间窗口内同一 key 的请求数超过 max_per_window 时拒绝后续请求。
    所有内部操作均带 try-except，限流本身异常绝不影响业务主流程。
    """

    def __init__(self, max_per_window: int = 60, window_sec: float = 10.0):
        self.max_per_window = max(1, int(max_per_window))
        self.window_sec = max(1.0, float(window_sec))
        self._buckets: dict = {}
        self._lock = threading.Lock()

    def allow(self, client_ip: str, method: str) -> bool:
        """判断该 (ip, method) 请求是否放行；超限返回 False。"""
        try:
            now = time.time()
            bucket_start = (now // self.window_sec) * self.window_sec
            key = f"{client_ip or 'unknown'}|{method or '*'}"
            with self._lock:
                start, count = self._buckets.get(key, (bucket_start, 0))
                if start < bucket_start:
                    start, count = bucket_start, 0
                count += 1
                self._buckets[key] = (start, count)
                # 顺带清理过期桶，防止内存膨胀
                if len(self._buckets) > 4096:
                    stale = [k for k, (s, _) in self._buckets.items()
                             if s < bucket_start]
                    for k in stale:
                        self._buckets.pop(k, None)
                return count <= self.max_per_window
        except Exception:                                              # noqa: BLE001
            return True

    def snapshot(self) -> dict:
        """返回当前限流桶快照（用于状态面板展示）。"""
        try:
            with self._lock:
                return {"keys": len(self._buckets),
                        "max_per_window": self.max_per_window,
                        "window_sec": self.window_sec}
        except Exception:                                              # noqa: BLE001
            return {}


class ServerMetrics:
    """进程内服务端指标收集：QPS / 错误率 / 延迟直方图。

    与既有 _request_stats 并存，本类额外提供分位数延迟与直方图分布，
    线程安全；任何异常都被吞掉，指标采集不影响请求处理。
    """

    _BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)

    def __init__(self):
        # 用可重入锁：snapshot() 持锁后会调用 qps()/error_rate()/latency_percentile()，
        # 这些方法内部也会再次加锁；普通 Lock 会死锁。
        self._lock = threading.RLock()
        self._total = 0
        self._errors = 0
        self._hist = {b: 0 for b in self._BUCKETS_MS}
        self._samples: "_collections.deque" = _collections.deque(maxlen=1024)

    def observe(self, method: str, duration_ms: float, ok: bool) -> None:
        """记录一次 RPC：方法名、耗时（毫秒）、成功与否。"""
        try:
            dur = max(0.0, float(duration_ms or 0.0))
            with self._lock:
                self._total += 1
                if not ok:
                    self._errors += 1
                self._samples.append(dur)
                placed = False
                for b in self._BUCKETS_MS:
                    if dur <= b:
                        self._hist[b] += 1
                        placed = True
                        break
                if not placed:
                    self._hist[self._BUCKETS_MS[-1]] += 1
        except Exception:                                              # noqa: BLE001
            pass

    def qps(self) -> float:
        """基于最近样本平均耗时估算的瞬时 QPS。"""
        try:
            with self._lock:
                n = len(self._samples)
                if n < 2:
                    return 0.0
                avg_s = sum(self._samples) / n / 1000.0
                return round(1.0 / avg_s, 2) if avg_s > 0 else 0.0
        except Exception:                                              # noqa: BLE001
            return 0.0

    def error_rate(self) -> float:
        """累计错误率（0-1）。"""
        try:
            with self._lock:
                return round(self._errors / self._total, 4) if self._total else 0.0
        except Exception:                                              # noqa: BLE001
            return 0.0

    def latency_percentile(self, pct: float = 95.0) -> float:
        """返回延迟分位数（毫秒），pct 取 0-100。"""
        try:
            with self._lock:
                if not self._samples:
                    return 0.0
                data = sorted(self._samples)
                k = max(0, min(len(data) - 1,
                               int(round(pct / 100.0 * (len(data) - 1)))))
                return round(data[k], 1)
        except Exception:                                              # noqa: BLE001
            return 0.0

    def snapshot(self) -> dict:
        """汇总全部指标为字典。"""
        try:
            with self._lock:
                return {
                    "total": self._total,
                    "errors": self._errors,
                    "qps": self.qps(),
                    "error_rate": self.error_rate(),
                    "p50_ms": self.latency_percentile(50),
                    "p95_ms": self.latency_percentile(95),
                    "histogram": dict(self._hist),
                }
        except Exception:                                              # noqa: BLE001
            return {}


class InFlightTracker:
    """跟踪正在处理的 RPC 数量，支持优雅关闭时等待进行中请求排空。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._active = 0
        self._done = threading.Event()
        self._done.set()

    @_contextlib.contextmanager
    def track(self, method: str = ""):
        """上下文管理器：进入 +1，退出 -1；归零时置位 done 事件。"""
        try:
            with self._lock:
                self._active += 1
                self._done.clear()
        except Exception:                                              # noqa: BLE001
            pass
        try:
            yield
        finally:
            try:
                with self._lock:
                    self._active = max(0, self._active - 1)
                    if self._active == 0:
                        self._done.set()
            except Exception:                                          # noqa: BLE001
                pass

    def count(self) -> int:
        try:
            with self._lock:
                return self._active
        except Exception:                                              # noqa: BLE001
            return 0

    def wait_idle(self, timeout: float = 10.0) -> bool:
        """等待进行中请求排空；超时返回 False。"""
        try:
            return self._done.wait(timeout=timeout)
        except Exception:                                              # noqa: BLE001
            return False


# 全局单例（供未来中间件 / 健康检查挂载使用）
_rate_limiter = RateLimiter()
_server_metrics = ServerMetrics()
_inflight_tracker = InFlightTracker()


# --------------------------------------------------------------------------- #
#  RPC 自动埋点：限流 / 指标 / 在途跟踪（统一包装 XiaoLingServicer 全部 RPC 方法）
#  - 入口：_rate_limiter.allow(client_ip, method)，超限 context.abort(PERMISSION_DENIED)
#  - finally：_server_metrics.observe(method, duration_ms, ok)
#  - 流式方法：_inflight_tracker.track() 包裹整个生成器
#  - client IP 从 context.peer() 解析；限流/指标自身异常一律不影响业务
# --------------------------------------------------------------------------- #
import functools as _functools                                  # noqa: E402
import inspect as _inspect                                      # noqa: E402


def _client_ip(context) -> str:
    """从 gRPC context.peer() 解析客户端 IP；失败返回 'unknown'。"""
    try:
        peer = ''
        try:
            peer = str(context.peer() or '')
        except Exception:                                           # noqa: BLE001
            peer = ''
        # peer 形如 "ipv4:127.0.0.1:54321" / "ipv6:[::1]:12345" / "unix:/path"
        if ':' in peer:
            host = peer.rsplit(':', 1)[0]
            if host.startswith('ipv4:'):
                host = host[len('ipv4:'):]
            elif host.startswith('ipv6:'):
                host = host[len('ipv6:'):].strip('[]')
            return host or 'unknown'
        return peer or 'unknown'
    except Exception:                                                  # noqa: BLE001
        return 'unknown'


def _enforce_rate_limit(method_name: str, context) -> None:
    """超限则 context.abort 抛出 PERMISSION_DENIED（gRPC 据此回错，无需构造返回值）。
    限流判断自身任何异常都视为放行（fail-open），绝不误伤正常请求。"""
    allowed = True
    try:
        allowed = bool(_rate_limiter.allow(_client_ip(context), method_name))
    except Exception:                                                  # noqa: BLE001
        allowed = True
    if not allowed:
        try:
            context.abort(grpc.StatusCode.PERMISSION_DENIED,
                          f'请求过于频繁：{method_name}，请稍后再试')
        except Exception:                                              # noqa: BLE001
            raise  # abort 必然抛异常以中断本次 RPC；其余异常继续上抛


def _wrap_unary_rpc(method_name: str, fn):
    """一元 RPC 包装：限流 -> 在途跟踪 -> finally 指标采集。"""
    @_functools.wraps(fn)
    def wrapper(self, request, context):
        t0 = time.time()
        ok = False
        try:
            _enforce_rate_limit(method_name, context)
            with _inflight_tracker.track(method_name):
                result = fn(self, request, context)
            ok = True
            return result
        finally:
            try:
                _server_metrics.observe(method_name,
                                        (time.time() - t0) * 1000.0, ok)
            except Exception:                                          # noqa: BLE001
                pass
    return wrapper


def _wrap_stream_rpc(method_name: str, fn):
    """流式 RPC 包装：限流 -> 在途跟踪包裹整个生成器 -> finally 指标采集。"""
    @_functools.wraps(fn)
    def wrapper(self, request, context):
        t0 = time.time()
        ok = False
        try:
            _enforce_rate_limit(method_name, context)
            with _inflight_tracker.track(method_name):
                for item in fn(self, request, context):
                    yield item
                ok = True
        finally:
            try:
                _server_metrics.observe(method_name,
                                        (time.time() - t0) * 1000.0, ok)
            except Exception:                                          # noqa: BLE001
                pass
    return wrapper


# 统一包装：遍历 XiaoLingServicer 自定义的公开方法，按是否为生成器区分一元/流式。
# 只包装本类定义的方法（__qualname__ 以 XiaoLingServicer. 开头），
# 避免误包装继承自 grpc 基类 / object 的内容；_plugin_manager 以下划线开头自动跳过。
for _m_name in dir(XiaoLingServicer):
    if _m_name.startswith('_'):
        continue
    try:
        _orig = getattr(XiaoLingServicer, _m_name)
    except Exception:                                                  # noqa: BLE001
        continue
    if not callable(_orig):
        continue
    if not (getattr(_orig, '__qualname__', '') or '').startswith('XiaoLingServicer.'):
        continue
    try:
        if _inspect.isgeneratorfunction(_orig):
            setattr(XiaoLingServicer, _m_name, _wrap_stream_rpc(_m_name, _orig))
        else:
            setattr(XiaoLingServicer, _m_name, _wrap_unary_rpc(_m_name, _orig))
    except Exception:                                                  # noqa: BLE001
        continue


def _disk_free_gb(path: str) -> float:
    """返回路径所在磁盘剩余空间（GB），失败返回 0.0。"""
    try:
        st = os.statvfs(path)
        return float(st.f_bavail) * float(st.f_frsize) / (1024 ** 3)
    except Exception:                                                  # noqa: BLE001
        return 0.0


def subsystem_health() -> dict:
    """汇总各子系统健康状态：引擎 / 终端 / 文件 / 磁盘 / 指标。

    每个子系统单独 try-except，任一异常只标记该子系统为 unknown，
    绝不影响整体健康检查返回。
    """
    out: dict = {"overall": "ok", "checks": {}, "ts": time.time()}

    def _mark(name: str, fn):
        try:
            out["checks"][name] = fn()
        except Exception as e:                                          # noqa: BLE001
            out["checks"][name] = {"status": "unknown",
                                   "error": f"{type(e).__name__}: {e}"}

    _mark("engine", lambda: {
        "status": "ready" if _get_engine() is not None else "degraded",
    })
    _mark("terminal", lambda: {
        "status": "ready" if _get_terminal_manager() is not None else "stopped",
    })
    _mark("file_manager", lambda: {
        "status": "ready" if _get_file_manager() is not None else "stopped",
    })
    _mark("disk", lambda: {"free_gb": round(_disk_free_gb(_PROJECT_ROOT), 2)})
    _mark("metrics", lambda: _server_metrics.snapshot())
    # 聚合：任一子系统 degraded/unknown 则整体降级
    try:
        for c in out["checks"].values():
            st = str(c.get("status", "ok"))
            if st in ("degraded", "unknown", "stopped"):
                out["overall"] = "degraded"
                break
    except Exception:                                                  # noqa: BLE001
        out["overall"] = "degraded"
    return out


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
