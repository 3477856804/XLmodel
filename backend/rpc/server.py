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
import re
import sys
import threading
import time
import uuid
from concurrent import futures

logger = logging.getLogger("xiaoling.rpc")

# 实际绑定成功的端口。serve() 只有在**真的** listen 上之后才会写这里，
# 所以 main.py 可以用它判断「后端到底起来了没有」，而不是在启动线程之后
# 立刻打印一句「已启动」—— 那句话说的是愿望，不是事实：端口被上一个
# 没退干净的 backend.exe 占住时，线程里抛了异常，窗口上却已经写着已启动。
_RUNNING_PORTS: dict = {}

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

# 多通道管理器（channels: 指令族用）。见 _get_channel_manager() 注释。
_channel_manager = None
_channel_manager_lock = threading.Lock()
_mcp_manager = None
_mcp_manager_lock = threading.Lock()
_workflow_engine = None
_workflow_engine_lock = threading.Lock()

_browser_tool = None
_browser_tool_lock = threading.Lock()

# DSH 兼容层 / Git 工具 / 插件管理器 单例（此前这些模块虽已实现，却零调用方
# 或每次 new 一份，导致装了插件重启就"看不见"、市场与已启用状态不一致）。
_dsh_compat = None
_dsh_compat_lock = threading.Lock()
_git_tool = None
_git_tool_lock = threading.Lock()
_plugin_manager = None
_plugin_manager_lock = threading.Lock()
_update_checker = None
_update_checker_lock = threading.Lock()


def _get_plugin_manager():
    """插件管理器单例。

    此前 _handle_ext_command 的 plugin: 分支每次都 PluginManager() 新建一份，
    而 ListPlugins / EnablePlugin 走的是引擎里那一份（engine.plugins）——
    两条路径各持内存，enable 后再 market 可能看不到，钩子也不会注册到正在
    跑的引擎上。这里统一返回**引擎内的那一份**（引擎已加载就直接用），
    引擎不可用时才退化为进程级单例，保证全进程只有一个真相源。
    """
    global _plugin_manager
    eng = None
    try:
        eng = _get_engine()
    except Exception:                                                # noqa: BLE001
        eng = None
    if eng is not None:
        pm = getattr(eng, "plugins", None)
        if pm is not None:
            return pm
    if _plugin_manager is not None:
        return _plugin_manager
    with _plugin_manager_lock:
        if _plugin_manager is None:
            from core.plugin_system import PluginManager
            _plugin_manager = PluginManager()
    return _plugin_manager


def _get_dsh_compat():
    global _dsh_compat
    if _dsh_compat is not None:
        return _dsh_compat
    with _dsh_compat_lock:
        if _dsh_compat is None:
            from core.dsh_compat import DSHCompat
            _dsh_compat = DSHCompat()
    return _dsh_compat


def _get_git_tool(repo_path: str = "", permission: str = "default"):
    """Git 工具（默认锁定沙箱 workspace，权限 default）。

    - 无 repo_override 且权限为 default → 复用进程级单例（省得起、路径固定）。
    - 一旦前端显式指定了仓库路径，或升权到 readonly/full（用户主动选了"要操作
      这个仓库"），就**新建一份**而不是污染单例——单例永远是 workspace+default。
    """
    repo = (repo_path or "").strip()
    perm = permission if permission in ("readonly", "default", "full") else "default"
    if repo or perm != "default":
        from core.git_tool import GitTool
        return GitTool(repo or _default_git_root(), permission=perm)
    global _git_tool
    if _git_tool is not None:
        return _git_tool
    with _git_tool_lock:
        if _git_tool is None:
            from core.git_tool import GitTool
            _git_tool = GitTool(_default_git_root())
    return _git_tool


def _default_git_root() -> str:
    try:
        from core.sandbox import workspace_dir
        return str(workspace_dir())
    except Exception:                                                # noqa: BLE001
        return _PROJECT_ROOT


def _get_update_checker():
    """更新检查器单例（真相源优先引擎里那一份）。

    前端 updater.dart 原本自己 http.get GitHub API、自己缓存、自己解析，
    和后端 core/updater.py 的 UpdateChecker 是两套并行实现。现在前端改走
    `update:` 指令，这里统一返回**引擎里的 self.updater**（引擎已加载时），
    否则退化为进程级单例，保证"检查/跳过/缓存/挑资产"只有一个人说了算。
    """
    global _update_checker
    eng = None
    try:
        eng = _get_engine()
    except Exception:                                                # noqa: BLE001
        eng = None
    if eng is not None:
        up = getattr(eng, "updater", None)
        if up is not None:
            return up
    if _update_checker is not None:
        return _update_checker
    with _update_checker_lock:
        if _update_checker is None:
            from core.updater import UpdateChecker
            _update_checker = UpdateChecker()
    return _update_checker


def _handle_update_cmd(rest: str) -> str:
    """`update:` 指令族（ExecuteCommand+JSON，不动 proto）：
        update:check [force]   检查更新，返回 UpdateInfo.to_dict()
        update:skip <version>  跳过某版本（持久化）
        update:clear-skip      清除跳过标记
        update:snapshot        当前版本/已跳过/缓存快照（不发网络）
        update:pick <platform> 基于缓存挑本平台/推荐资产
    网络失败时 check 返回 has_update=False + message 说明，不假装"已最新"。
    """
    op, _, arg = (rest + " ").partition(" ")
    op, arg = op.strip().lower(), arg.strip()
    import json as _json

    def _ok(**kw):
        d = {"ok": True}
        d.update(kw)
        return _json.dumps(d, ensure_ascii=False)

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    up = _get_update_checker()
    if up is None:
        return _err("更新检查器不可用")
    if op in ("", "check"):
        force = ('force' in arg.split())
        info = up.check_detailed(force=force)
        return _json.dumps(info.to_dict(), ensure_ascii=False, default=str)
    if op == "skip":
        if not arg:
            return _err("缺少要跳过的版本号")
        up.skip_version(arg)
        return _ok(message=f"已跳过 v{arg}", skipped=up.skipped)
    if op in ("clear-skip", "clearskip"):
        up.clear_skip()
        return _ok(message="已清除跳过版本", skipped=up.skipped)
    if op == "snapshot":
        return _json.dumps(up.snapshot(), ensure_ascii=False, default=str)
    if op == "pick":
        info = up.check_detailed()
        plat = arg.lower()
        a = up.pick_for_platform(info, plat) if plat else None
        if a is None:
            a = up.pick_recommended(info)
        return _json.dumps({"asset": a, "platform": plat or "recommended"},
                           ensure_ascii=False, default=str)
    return _err(f"未知 update 操作: {op}")


def _get_browser_tool():
    """懒加载 BrowserTool 单例（保留活动页面状态，供点击/输入/JS 连续操作）。"""
    global _browser_tool
    if _browser_tool is not None:
        return _browser_tool
    with _browser_tool_lock:
        if _browser_tool is None:
            from core.browser_tool import BrowserTool
            _browser_tool = BrowserTool()
    return _browser_tool


# 成长引擎：GetStatus/GetGrowthStatus/GetTrainingStatus 此前每次 GrowthEngine()
# 新建一份，读到的是刚出厂的 status()（内存中的 throttle cache、暂停标志、
# 蒸馏队列等都不落盘），与 growth: 指令族走的 eng.growth 完全不同源。
# 这里收敛成一个进程级单例：优先复用 engine.growth，
# engine 未就绪时退回进程级实例；无论走哪条，同一份内存，同一份真相。
_growth_engine_singleton = None
_growth_engine_lock = threading.Lock()


def _get_growth_engine():
    global _growth_engine_singleton
    try:
        eng = _get_engine()
    except Exception:                                                # noqa: BLE001
        eng = None
    if eng is not None:
        g = getattr(eng, "growth", None)
        if g is not None:
            return g
    if _growth_engine_singleton is not None:
        return _growth_engine_singleton
    with _growth_engine_lock:
        if _growth_engine_singleton is None:
            from core.growth import GrowthEngine
            _growth_engine_singleton = GrowthEngine()
    return _growth_engine_singleton


def _get_channel_manager():
    """多通道管理器单例。

    core/channels.py 的 ChannelManager 此前**没有任何实例化点**，
    start_all() 也是零调用方 —— 通道功能等于没接过线。这里给 RPC 层
    一个持有它的地方，channels: 指令族才能真正 list/set/start/stop。
    """
    global _channel_manager
    if _channel_manager is not None:
        return _channel_manager
    with _channel_manager_lock:
        if _channel_manager is None:
            from core import config as _cfg
            from core.channels import ChannelManager
            _channel_manager = ChannelManager(config=dict(_cfg.load() or {}))
            eng = None
            try:
                eng = _get_engine()
            except Exception:                                        # noqa: BLE001
                eng = None
            if eng is not None:
                try:
                    _channel_manager.set_engine(eng)
                except Exception:                                    # noqa: BLE001
                    logger.exception('通道管理器注入引擎失败')
    return _channel_manager


def _get_security_center():
    """RPC 与执行链（exec_gate）必须共用**同一个** SecurityCenter 实例。

    此前这里自己 new 了一个：设置页 `security:set` 改的是这个对象，
    而模型产出命令的实际判定走 exec_gate —— 两边各持一份内存配置，
    改了开关对方看不见，表现为「开关点了没反应」。
    现在统一委托给 core.security_center 的单例。
    """
    global _security_center
    if _security_center is not None:
        return _security_center
    with _security_center_lock:
        if _security_center is None:
            from core.security_center import get_security_center
            _security_center = get_security_center()
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
            # 必须把引擎注入工作流引擎：WorkflowEngine.execute() 靠 self.engine
            # 调 LLM/工具节点，set_engine() 全仓此前零调用方 —— 于是 UI 点
            # 「运行工作流」时，凡是需要引擎的节点都拿不到模型，只能失败。
            eng = None
            try:
                eng = _get_engine()
            except Exception:                                    # noqa: BLE001
                eng = None
            if eng is not None:
                try:
                    _workflow_engine.set_engine(eng)
                except Exception:                                # noqa: BLE001
                    logger.exception('workflow engine 注入失败')
    return _workflow_engine


_knowledge_base = None
_knowledge_base_lock = threading.Lock()


def _get_knowledge_base():
    """懒加载知识库单例（分块索引 + 混合检索 + 引用溯源）。"""
    global _knowledge_base
    if _knowledge_base is not None:
        return _knowledge_base
    with _knowledge_base_lock:
        if _knowledge_base is None:
            from core.knowledge_base import KnowledgeBase
            _knowledge_base = KnowledgeBase(index_path="data/kb_index.json")
    return _knowledge_base


_code_indexer = None
_code_indexer_lock = threading.Lock()


def _get_code_indexer():
    """懒加载符号级代码索引单例（调用关系/定义跳转/继承）。"""
    global _code_indexer
    if _code_indexer is not None:
        return _code_indexer
    with _code_indexer_lock:
        if _code_indexer is None:
            from core.tools import SymbolIndexer
            idx = SymbolIndexer(_PROJECT_ROOT)
            try:
                idx.build()
            except Exception:
                pass
            _code_indexer = idx
    return _code_indexer


_multifile_editor = None
_multifile_editor_lock = threading.Lock()
_bg_tasks = None
_bg_tasks_lock = threading.Lock()


def _get_multifile_editor():
    """懒加载 MultiFileEditor 单例（以项目根为基准目录）。"""
    global _multifile_editor
    if _multifile_editor is not None:
        return _multifile_editor
    with _multifile_editor_lock:
        if _multifile_editor is None:
            from core.tools import MultiFileEditor
            _multifile_editor = MultiFileEditor(base_dir=_PROJECT_ROOT)
    return _multifile_editor


def _get_bg_tasks():
    """懒加载后台任务管理器单例（JSON 持久化到 data/）。"""
    global _bg_tasks
    if _bg_tasks is not None:
        return _bg_tasks
    with _bg_tasks_lock:
        if _bg_tasks is None:
            from core.background_tasks import BackgroundTaskManager
            _bg_tasks = BackgroundTaskManager()
    return _bg_tasks


def _handle_agent(cmd: str) -> str:
    """Agent 工具链扩展命令族：agent:edit / agent:terminal / agent:task。

    所有子命令返回 JSON 字符串；底层工具真实执行，失败返回真实错误。
    """
    import json as _json

    def _ok(**kw):
        d = {"ok": True}
        d.update(kw)
        return _json.dumps(d, ensure_ascii=False)

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    try:
        # ---- agent:edit ----
        if cmd.startswith("agent:edit"):
            rest = cmd[len("agent:edit"):].strip()
            op, _, payload = rest.partition(" ")
            payload = payload.strip()
            editor = _get_multifile_editor()
            if op == "plan":
                spec = _json.loads(payload) if payload else {}
                edits = spec.get("edits") if isinstance(spec, dict) else spec
                if not isinstance(edits, list):
                    return _err("plan 需要 {\"edits\":[...]}")
                return _json.dumps(editor.plan_edits([], edits), ensure_ascii=False)
            if op == "apply":
                spec = _json.loads(payload) if payload else {}
                if not isinstance(spec, dict):
                    return _err("apply 需要 {\"file_path\":..., \"old_string\":..., \"new_string\":...}")
                return _json.dumps(editor.apply_edit(
                    file_path=spec.get("file_path", ""),
                    old_string=spec.get("old_string", ""),
                    new_string=spec.get("new_string", "")), ensure_ascii=False)
            if op == "batch":
                spec = _json.loads(payload) if payload else {}
                edits = spec.get("edits") if isinstance(spec, dict) else spec
                if not isinstance(edits, list):
                    return _err("batch 需要 {\"edits\":[...]}")
                return _json.dumps(editor.apply_edits_batch(edits), ensure_ascii=False)
            if op == "diff":
                return _json.dumps(editor.get_diff(file_path=payload), ensure_ascii=False)
            if op == "rollback":
                return _json.dumps(editor.rollback(file_path=payload), ensure_ascii=False)
            return _err(f"未知 edit 操作: {op}（plan/apply/batch/diff/rollback）")

        # ---- agent:terminal ----
        if cmd.startswith("agent:terminal"):
            rest = cmd[len("agent:terminal"):].strip()
            op, _, arg = rest.partition(" ")
            arg = arg.strip()
            from core import terminal as _term
            if op == "run":
                if not arg:
                    return _err("缺少要执行的命令")
                out = _term.run_command_with_output(arg, timeout=30)
                return _json.dumps(out, ensure_ascii=False)
            if op in ("which", "exists", "check"):
                return _json.dumps(_term.check_command_exists(arg), ensure_ascii=False)
            return _err(f"未知 terminal 操作: {op}（run/which）")

        # ---- agent:task ----
        if cmd.startswith("agent:task"):
            rest = cmd[len("agent:task"):].strip()
            op, _, payload = rest.partition(" ")
            payload = payload.strip()
            mgr = _get_bg_tasks()
            if op == "list":
                return _json.dumps(mgr.list_tasks(), ensure_ascii=False)
            if op == "status":
                return _json.dumps(mgr.get_task_status(payload), ensure_ascii=False)
            if op == "result":
                spec = _json.loads(payload) if payload else {}
                if not isinstance(spec, dict):
                    return _err("result 需要 {\"task_id\":..., \"tail\":...}")
                return _json.dumps(mgr.get_task_result(
                    task_id=spec.get("task_id", ""),
                    tail=int(spec.get("tail", 200))), ensure_ascii=False)
            if op == "cancel":
                return _json.dumps(mgr.cancel_task(payload), ensure_ascii=False)
            if op == "start":
                spec = _json.loads(payload) if payload else {}
                if not isinstance(spec, dict):
                    return _err("start 需要 {\"name\":..., \"command\":...}")
                name = spec.get("name") or "shell_task"
                command = spec.get("command") or ""
                timeout = int(spec.get("timeout", 120))
                if not command:
                    return _err("start 缺少 command")

                def _shell_job(cancel_event, output, _cmd=command, _to=timeout):
                    from core.terminal import run_command_stream
                    final = {"ok": True}
                    for chunk in run_command_stream(_cmd, timeout=_to):
                        if cancel_event.is_set():
                            output("[取消中] 终止命令流")
                            return {"ok": False, "cancelled": True}
                        ctype = chunk.get("type")
                        if ctype == "line":
                            output(chunk.get("text", ""))
                        elif ctype == "error":
                            output(f"[error] {chunk.get('error')}")
                        elif ctype == "end":
                            final = {"ok": chunk.get("code") == 0,
                                     "code": chunk.get("code"),
                                     "timed_out": chunk.get("timed_out")}
                    return final

                return _json.dumps(mgr.start_task(name, _shell_job), ensure_ascii=False)
            return _err(f"未知 task 操作: {op}（list/status/result/cancel/start）")

        return _err("未知 agent 命令族")
    except Exception as e:  # noqa: BLE001
        logger.exception('agent command failed: %s', cmd)
        return _err(f"agent 命令异常：{type(e).__name__}: {e}")


def _handle_deps_cmd(cmd: str) -> str:
    """依赖自愈：deps:status / deps:install <包...> [force]（core.deps）。

    安装是长任务，一律后台执行立即返回 task_id；同步路径只做白名单与
    train 档校验，绝不跑 pip。失败（离线/无 pip/打包态）如实返回。
    """
    import json as _json

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    try:
        try:
            from core import deps as _deps
        except Exception:                                        # noqa: BLE001
            from backend.core import deps as _deps               # type: ignore
    except Exception as e:                                       # noqa: BLE001
        return _err(f'依赖模块不可用：{type(e).__name__}: {e}')

    rest = (cmd or '').strip()
    op, _, arg = (rest + ' ').partition(' ')
    op, arg = op.strip().lower(), arg.strip()

    if op in ('', 'status', 'list'):
        try:
            return _json.dumps(_deps.status(), ensure_ascii=False, default=str)
        except Exception as e:                                   # noqa: BLE001
            return _err(f'status 失败：{type(e).__name__}: {e}')

    if op == 'install':
        tokens = arg.split()
        force = 'force' in tokens
        names = [t for t in tokens if t != 'force']
        if not names:
            return _err('deps:install 需要包名（见 deps:status 的 missing）')
        # 只做同步校验（白名单 / torch 未 force / 已就绪），绝不在这跑 pip。
        v = _deps.validate(names, force_train=force)
        if not v.get('ok'):
            return _json.dumps(v, ensure_ascii=False, default=str)
        if not v.get('todo'):
            return _json.dumps({'ok': True, 'installed': [],
                                'skipped': v.get('skipped', []),
                                'note': '所请求的依赖均已就绪，无需下载'},
                               ensure_ascii=False, default=str)

        # 同步预检：frozen / pip / 网络。不过就当场返回错误，不再走后台任务
        # （后台失败结果只落 task 表、前端不轮询 → 表现为「点击安装没反应」）。
        pre = _deps.precheck_install()
        if not pre.get('ok'):
            return _json.dumps(pre, ensure_ascii=False, default=str)

        def _job(cancel_event, output, _names=names, _force=force):
            try:
                return _deps.install(_names, force_train=_force, output=output)
            except Exception as e:                               # noqa: BLE001
                output(f'安装异常：{type(e).__name__}: {e}')
                return {'ok': False, 'error': f'{type(e).__name__}: {e}'}

        bg = _bg_start(f'deps:install {" ".join(names)}', _job)
        return _json.dumps(bg, ensure_ascii=False, default=str)

    return _err(f'未知子命令：{op}（可用：status / install <包...> [force]）')


def _handle_api_cmd(cmd: str) -> str:
    """统一「外部 API 配置」指令族。返回 JSON 字符串。

    这是设置页「API 配置」选项卡的后端。收敛了原本互不相通的
    training.api_* 与 deepseek_* 两套配置（见 core.api_config 模块文档）。

    子命令：
        api:cfg                    读当前配置（key 打码）
        api:set enabled on|off     总开关
        api:set base <url>         端点（http/https）
        api:set key <密钥>         密钥（空串=清除）
        api:set model <名字>       默认模型名
        api:set provider <名>      展示用供应商标签
        api:test                   真实连通性测试
        api:chat <messagesJson>    直接走外部 API 对话（Agent/蒸馏复用同一入口）

    与 settings:/sandbox: 一样走 ExecuteCommand+JSON —— 加字段不必改 proto。
    """
    import json as _json

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    try:
        try:
            from core import api_config as _api
        except Exception:                                        # noqa: BLE001
            from backend.core import api_config as _api          # type: ignore
    except Exception as e:                                       # noqa: BLE001
        return _err(f'API 配置模块不可用：{type(e).__name__}: {e}')

    rest = (cmd or '').strip()
    op, _, arg = (rest + ' ').partition(' ')
    op, arg = op.strip().lower(), arg.strip()

    if op in ('', 'cfg', 'get', 'status'):
        out = _api.cfg()
        out['usage'] = ('api:cfg | api:set [enabled|base|key|model|provider] <值> | '
                        'api:test | api:chat <messagesJson>')
        return _json.dumps(out, ensure_ascii=False, default=str)

    if op == 'set':
        parts = arg.split(None, 1)
        if not parts:
            return _err('api:set 需要一个字段名（enabled/base/key/model/provider）')
        field = parts[0].strip().lower()
        value = parts[1].strip() if len(parts) > 1 else ''
        return _json.dumps(_api.set_field(field, value),
                           ensure_ascii=False, default=str)

    if op == 'test':
        return _json.dumps(_api.test(), ensure_ascii=False, default=str)

    if op == 'chat':
        # 允许传 [{"role","content"}, ...] 或一个裸字符串（自动包成 user）。
        raw = arg
        if not raw:
            return _err('api:chat 需要消息内容')
        try:
            msgs = _json.loads(raw)
            if not isinstance(msgs, list):
                msgs = [{"role": "user", "content": str(msgs)}]
        except Exception:                                        # noqa: BLE001
            msgs = [{"role": "user", "content": raw}]
        return _json.dumps(_api.chat(msgs), ensure_ascii=False, default=str)

    return _err(f'未知子命令：{op}（可用：cfg/set/test/chat）')


def _handle_model_cmd(cmd: str) -> str:
    """模型实时状态指令族。返回 JSON 字符串。

    存在的理由：前端（聊天页头部、模型商店、设置页）需要在**任何时刻**知道
    「此刻真正在用的是哪个模型、有没有模型」，而不是等某次对话之后再看一个
    可能过期的静态配置值。

    与 settings:/sandbox: 一样走 ExecuteCommand 返回 JSON —— 这样新增字段
    不必改 proto、不必重新生成 Dart / Python 桩代码，改完刷新即可生效。

    子命令：
        model:active           当前活动模型（唯一真源）；无模型时 available=false
        model:list             已安装模型清单（商店 + 本地登记）
        model:use <名字>       切换当前模型（严格匹配，不会静默换错）
        model:answer           「我是什么模型」的标准话术（纯事实）
        model:search <词> [页] 在魔搭（ModelScope）上搜模型，返回真实结果或
                               ok=false + error（搜不到不冒充成功）
        model:files <repo>     列某个远端仓库的文件与 .gguf 清单
        model:recommend        按本机硬件算出的适配/推荐（含探测是否可用）
        model:downloadremote <repo> [量化档]
                               后台下载远端 GGUF（返回 task_id + poll，
                               进度写进 sandbox:status 的 progress）
    """
    import json as _json

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    rest = (cmd or '').strip()
    if not rest:
        return _err('缺少子命令（可用：active / list / use / answer / search'
                   ' / files / recommend / downloadremote）')
    op, _, arg = (rest + ' ').partition(' ')
    op, arg = op.strip().lower(), arg.strip()

    try:
        from core.model import (LocalModelRegistry, ModelStore, active_model,
                                 active_model_answer)

        # ---- 远端搜索 / 硬件推荐 / 远端下载 ----
        # 这三条是「模型商店」真正的后端。此前商店只会把内置的 11 个
        # MODEL_PRESETS 列出来，搜索框在前端做本地字符串过滤，既搜不到
        # 魔搭上的其它模型，也没有按本机硬件给建议 —— 界面看着像商店，
        # 其实是一张固定清单。
        if op in ('search', '搜', '搜索'):
            from core.model import search_remote
            if not arg:
                return _err('用法：model:search <关键词> [页码]')
            parts = arg.split()
            page = 1
            if len(parts) > 1:
                page = int(parts[-1]) if parts[-1].isdigit() else 1
                query = ' '.join(parts[:-1])
            else:
                query = arg
            return _json.dumps(search_remote(query, page=max(1, page)),
                               ensure_ascii=False, default=str)

        if op in ('files', '远端文件'):
            from core.model import remote_model_files
            if not arg:
                return _err('用法：model:files <namespace/模型名>')
            return _json.dumps(remote_model_files(arg.split()[0]),
                               ensure_ascii=False, default=str)

        if op in ('recommend', '推荐'):
            from core.model import recommend_for_hardware
            return _json.dumps(recommend_for_hardware(),
                               ensure_ascii=False, default=str)

        if op in ('downloadremote', '远端下载'):
            from core.model import (MODELS_DIR, TASKS, _CANCEL_EVENTS,
                                     download_remote)
            if not arg:
                return _err('用法：model:downloadremote <namespace/模型名> [量化档]')
            parts = arg.split()
            repo = parts[0]
            quant = parts[1] if len(parts) > 1 else 'Q4_K_M'
            if '/' not in repo:
                return _err('仓库名要写成 namespace/模型名')
            if TASKS.get(repo, {}).get('status') == 'downloading':
                return _json.dumps({"ok": False, "repo": repo,
                                    "error": "该模型已在下载中"},
                                   ensure_ascii=False)

            def _job(cancel_event, output, _repo=repo, _q=quant):
                import time as _t
                TASKS[_repo] = {'percent': 0.0, 'status': 'starting',
                                'channel': 'modelscope-remote',
                                'started': _t.time()}
                _CANCEL_EVENTS[_repo] = cancel_event

                def _prog(done, total):
                    pct = 0.0
                    try:
                        if total:
                            pct = round(done / total * 100.0, 1)
                    except Exception:
                        pct = 0.0
                    TASKS[_repo] = {'percent': pct, 'status': 'downloading',
                                    'channel': 'modelscope-remote',
                                    'done_mb': round(done / 1e6, 1),
                                    'total_mb': round(total / 1e6, 1)}
                    output(f'{pct}%')

                try:
                    dest = MODELS_DIR / _repo.split('/')[-1]
                    r = download_remote(_repo, dest_dir=dest, quant=_q,
                                        progress_cb=_prog,
                                        cancel_check=cancel_event.is_set)
                    if r.get('cancelled'):
                        TASKS[_repo] = {'percent': TASKS[_repo].get('percent', 0.0),
                                        'status': 'cancelled',
                                        'channel': 'modelscope-remote',
                                        'error': r.get('error', '')}
                    elif r.get('ok'):
                        TASKS[_repo] = {'percent': 100.0, 'status': 'done',
                                        'channel': 'modelscope-remote',
                                        'path': r.get('path', '')}
                    else:
                        TASKS[_repo] = {'percent': TASKS[_repo].get('percent', 0.0),
                                        'status': 'error',
                                        'channel': 'modelscope-remote',
                                        'error': r.get('error', '')}
                    return r
                except Exception as e:                          # noqa: BLE001
                    TASKS[_repo] = {'percent': 0.0, 'status': 'error',
                                    'channel': 'modelscope-remote',
                                    'error': f'{type(e).__name__}: {e}'}
                    return {'ok': False, 'error': f'{type(e).__name__}: {e}'}
                finally:
                    _CANCEL_EVENTS.pop(_repo, None)

            bg = _bg_start(f'model:downloadremote {repo}', _job)
            bg.update({'repo': repo, 'quant': quant,
                       'progress': f'sandbox:status → progress.{repo}'})
            return _json.dumps(bg, ensure_ascii=False, default=str)

        engine = _get_engine()
        mr = getattr(engine, 'model_replace', None) if engine else None

        if op in ('active', '', 'status', '当前'):
            info = dict(active_model(mr))
            # 附带一句可直接展示的话术，省得前端再拼一遍文案
            info['ok'] = True
            info['text'] = active_model_answer(mr)
            info['action'] = '' if info.get('available') else 'open:model_store'
            return _json.dumps(info, ensure_ascii=False, default=str)

        if op in ('answer', '话术'):
            return _json.dumps({"ok": True, "text": active_model_answer(mr)},
                               ensure_ascii=False)

        if op in ('list', '列表'):
            store = ModelStore()
            return _json.dumps({
                "ok": True,
                "installed": store.list_installed(),
                "local": LocalModelRegistry().list(),
            }, ensure_ascii=False, default=str)

        if op in ('use', '切换'):
            if not arg:
                return _err('用法：model:use <模型名>')
            if mr is None:
                return _err('引擎未就绪，无法切换模型')
            r = mr.select(arg)
            # 切换成功 → 立刻让前端能读到新状态
            if r.get('ok'):
                try:
                    from core.model import _ACT_CACHE, invalidate_scan_cache
                    _ACT_CACHE.clear()
                    invalidate_scan_cache()
                except Exception:
                    pass
                r = dict(r)
                r.update(active_model(mr))
                r['ok'] = True
            return _json.dumps(r, ensure_ascii=False, default=str)

        # 未在此处特化的子命令（scan / addlocal / listlocal / addapi / listapi /
        # delapi / probeapi / listall …）在 core/fusion.py 里**早有真实实现**
        # （fusion.py 第 144~176 行）。此前这里直接回「未知 model 子命令」，
        # 等于把已经写好的能力挡在门外 —— fusion 的 help 与 README 都列着这些
        # 指令，用户照着敲却被告知未知。现在回退委派给 fusion 的解析器。
        try:
            from core import fusion as _fusion
        except Exception as e:                                   # noqa: BLE001
            return _err(f'未知 model 子命令: {op}'
                        f'（指令解析模块加载失败：{type(e).__name__}: {e}）')
        if engine is None:
            return _err('引擎未就绪，无法执行该 model 子命令')
        out = _fusion.try_command(engine, f'model:{rest}')
        if out is None:
            return _err(f'未知 model 子命令: {op}（可用：active / list / use / answer'
                        f' / search / files / recommend / downloadremote'
                        f' / scan / addlocal / listlocal / addapi / listapi'
                        f' / delapi / probeapi / listall）')
        return str(out)
    except Exception as e:  # noqa: BLE001
        logger.exception('model command failed: %s', cmd)
        return _err(f'model 命令异常：{type(e).__name__}: {e}')


def _handle_growth_cmd(cmd: str) -> str:
    """成长/人格元数据指令族。返回 JSON 字符串。

    存在的理由：GrowthStatusReply 只有 9 个 proto 字段（stage/progress/
    interactions/generation/rank/emotion/paused/status_text），装不下成长页
    真正要展示的东西 —— 关系等级有哪几档、现在这一档的阈值是多少、亲密度的
    真实分数与到下一档的进度、当前情绪是**因为什么**变成这样的、7/30 天里
    每天新增了多少样本和训练轮次。

    这些以前全在前端 Dart 里写死（`_rankCard` 里五档固定文案 + 固定
    「第 3 级」+ 固定 `current = i == 2`；时间线每个节点的日期都是
    `DateTime.now()`）。后端改了前端不知道，前端显示的也不是后端的真值。
    现在数据一律从这里出，proto 不用动。

    子命令：
        growth:persona      人格快照（情绪+来源 / 亲密度+等级 / 关系档位定义）
        growth:timeline     按天的真实活动时间线（?days=N，默认 30）
        growth:daily        今日目标进度（完成数 / 目标 / 是否达成）
        growth:goal <n>     设置每日互动目标
        growth:first        第一条成长记录日期（一起走过的天数）
        growth:report       今日成长摘要（含真实经验里程碑）
        growth:promotecheck 晋升门槛实况（够不够格 / 会不会被验收拦住）
        growth:promote [强制]  手动走一次合并晋升（含生成式验收；后台任务）
        growth:distill     蒸馏真实状态（只读：老师端配没配、队列、配额花费）
        growth:distill run [n]  真的去问老师（后台任务）
        growth:distill on|off|limit <n>  开关 / 每轮上限（写配置）
        growth:pause [原因]   暂停自动成长（写状态 + 记流水）
        growth:resume         恢复自动成长
        growth:status         成长引擎真值快照（只读，含 paused/rank/阻塞原因）
        growth:rollback      回收区可回滚代数（只读）
        growth:rollback <代>  演练预览这一次回滚会做什么
        growth:rollback <代> confirm  真的回滚（后台任务，会移动模型目录）
        growth:gc            演练：列出可清理的旧代与释放量（不删、不写流水）
        growth:gc run [force]  真删除（后台任务；force 跳过稳定期约束）
        growth:purge <范围>   只统计会删多少条样本，不动数据
        growth:purge <范围> confirm  真删（不可撤销）

    破坏性的三条（rollback confirm / gc run / purge confirm）一律要求显式
    `confirm`，裸调用只给预览；这是刻意的 —— 前端点一下不该直接删训练语料。
    """
    import json as _json

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    rest = (cmd or '').strip()
    if not rest:
        return _err('缺少子命令（可用：persona / timeline / daily / goal / first）')
    op, _, arg = (rest + ' ').partition(' ')
    op, arg = op.strip().lower(), arg.strip()

    try:
        eng = _get_engine()
    except Exception as e:                                              # noqa: BLE001
        return _err(f'引擎不可用：{type(e).__name__}: {e}')
    if eng is None:
        return _err('引擎未就绪，拿不到真实人格数据')

    try:
        if op == 'persona':
            snap = {}
            try:
                snap = dict(eng.persona.snapshot()) if eng.persona else {}
            except Exception as e:                                      # noqa: BLE001
                return _err(f'人格快照读取失败：{type(e).__name__}: {e}')
            # 前端关系等级卡片需要的全部真值：当前档位序号、是否满级、
            # 每档阈值/名字/风格。缺了它前端只能写死。
            r = snap.get('relationship') or {}
            levels = snap.get('levels') or []
            cur = r.get('level')
            idx = next((i for i, x in enumerate(levels)
                        if x.get('level') == cur), -1)
            snap['level_index'] = idx
            snap['level_total'] = len(levels)
            snap['is_max'] = bool(levels) and idx == len(levels) - 1
            snap['ok'] = True
            return _json.dumps(snap, ensure_ascii=False, default=str)

        if op == 'timeline':
            try:
                days = max(1, min(366, int(arg or 30)))
            except ValueError:
                days = 30
            try:
                rows = eng.growth.store.daily_activity(days)
            except Exception as e:                                      # noqa: BLE001
                return _err(f'时间线读取失败：{type(e).__name__}: {e}')
            return _json.dumps({'ok': True, 'days': days, 'activity': rows,
                                'first_date': eng.growth.first_record_date()},
                               ensure_ascii=False, default=str)

        if op == 'daily':
            try:
                return _json.dumps({'ok': True,
                                    **eng.growth.get_daily_progress()},
                                   ensure_ascii=False, default=str)
            except Exception as e:                                      # noqa: BLE001
                return _err(f'今日进度读取失败：{type(e).__name__}: {e}')

        if op in ('goal', 'set_daily_goal', 'set-daily-goal'):
            if not arg:
                return _err('用法：growth:goal <次数>')
            try:
                n = int(arg)
            except ValueError:
                return _err(f'目标次数必须是数字，收到：{arg}')
            if not eng.growth.set_daily_goal(n):
                return _err('写入失败：成长数据仓库不可用')
            return _json.dumps({'ok': True, **eng.growth.get_daily_progress()},
                               ensure_ascii=False, default=str)

        if op == 'first':
            d = eng.growth.first_record_date()
            days = 0
            if d:
                try:
                    import datetime as _dt
                    days = max(1, (_dt.date.today()
                                   - _dt.date.fromisoformat(d)).days + 1)
                except ValueError:
                    days = 0
            return _json.dumps({'ok': True, 'first_date': d, 'days_together': days},
                               ensure_ascii=False, default=str)

        if op == 'report':
            try:
                return _json.dumps({'ok': True,
                                    **eng.growth.get_daily_report()},
                                   ensure_ascii=False, default=str)
            except Exception as e:                                          # noqa: BLE001
                return _err(f'今日摘要读取失败：{type(e).__name__}: {e}')

        if op == 'promotecheck':
            # 只读快照：够不够格晋升、会不会被验收拦下来。
            # 不调 check_and_promote（它会写 journal），这样前端每次刷新
            # 成长页不会把「看过一眼」写成一条流水。
            g = eng.growth
            acc = _acceptance_cfg()
            try:
                cap = g.lifecycle.cap_check()
            except Exception as e:                                          # noqa: BLE001
                cap = {"ok": None, "blocked": None,
                       "message": f"上限检查失败：{type(e).__name__}: {e}"}
            base, adp = g.base_bytes, g.adapter_bytes
            ready = bool(base) and adp >= base
            return _json.dumps({
                'ok': True,
                'paused': g.is_paused(),
                'base_bytes': base,
                'adapter_bytes': adp,
                'progress_percent': round(g.progress_percent(), 2),
                'size_gate_met': ready,
                'cap': cap,
                'acceptance': acc,
                # 前端据此说话，不自己下结论：验收开着且拿不到阈值时，
                # 只能说「晋升前会先跑验收」，不能说「一定能晋升」。
                'will_run_acceptance': bool(acc.get('enforced')),
                'generation': int((g.state() or {}).get('promotions', 0)),
            }, ensure_ascii=False, default=str)

        if op == 'promote':
            # 手动晋升。真活（合并 + 校验 + 验收 + 基底退役），交后台任务；
            # 结果里带 retired / acceptance，前端如实显示是哪一步拦住的。
            force = (arg or '').strip().lower() in ('1', 'true', 'force', '强制')

            def _job(cancel_event, output, _f=force, _g=eng.growth):
                if cancel_event.is_set():
                    return {"ok": False, "cancelled": True}
                output('开始晋升检查：合并 LoRA → 校验 → 生成式验收 → 基底退役')
                res = _g.merge_and_promote() if _f else _g.check_and_promote()
                if res.get('ok') or res.get('action') == 'promoted':
                    output(res.get('message') or '晋升完成')
                else:
                    output('未晋升：' + str(res.get('message')
                                           or res.get('reason') or res))
                return res
            return _json.dumps(_bg_start('growth:promote', _job),
                               ensure_ascii=False, default=str)

        if op == 'distill':
            # 蒸馏的真实状态。默认**只读**：老师端配没配、队列里几条、今天用了
            # 多少配额与钱。`run` 才真的发请求（走后台任务，不阻塞 RPC）。
            from core.growth import teacher_config as _tc
            g = eng.growth
            sub, _, rest_arg = (arg or '').strip().partition(' ')
            sub = sub.lower()
            if sub in ('', 'status'):
                cfg = _tc()
                out = {'ok': True, 'teacher': cfg,
                       'enabled': bool(g.cfg('distill_enabled', True)),
                       'batch_limit': int(g.cfg('distill_batch_limit', 8))}
                try:
                    out['queue'] = g.store.distill_stats()
                    st = g.store.stats()
                    out['samples_with_teacher'] = st.get('with_teacher')
                    out['records_total'] = st.get('total')
                except Exception as e:                              # noqa: BLE001
                    out['queue_error'] = f'{type(e).__name__}: {e}'
                try:
                    rep = g.throttle.usage_report()
                    out['quota'] = {'used_today': rep.get('used_today'),
                                    'daily_limit': rep.get('daily_limit'),
                                    'cache_entries': rep.get('cache_entries'),
                                    'month_cost_yuan':
                                        (rep.get('month') or {}).get('cost_yuan')}
                except Exception as e:                              # noqa: BLE001
                    out['quota_error'] = f'{type(e).__name__}: {e}'
                if not cfg.get('configured'):
                    out['note'] = (cfg.get('reason') or '老师端未配置')
                    out['next'] = ('填 config 的 deepseek_api_key'
                                   '（setup.sh 会写），配好后新对话才会入队，'
                                   '再用 growth:distill run 问老师')
                else:
                    out['usage'] = ('growth:distill 只读｜'
                                    'growth:distill run [条数] 真的问老师｜'
                                    'growth:distill on|off 开关｜'
                                    'growth:distill limit <n> 每轮上限')
                return _json.dumps(out, ensure_ascii=False, default=str)

            if sub == 'run':
                def _job(cancel_event, output, _g=g, _n=rest_arg.strip()):
                    n = None
                    if _n:
                        try:
                            n = max(1, min(200, int(_n)))
                        except ValueError:
                            output(f'条数「{_n}」不是整数，按默认批量上限跑')
                    if cancel_event.is_set():
                        return {'ok': False, 'cancelled': True}
                    output('开始问老师（只发本地队列里登记的记录）')
                    r = _g.distill_round(limit=n)
                    output(r.get('message') or r.get('reason') or str(r))
                    return r
                return _json.dumps(_bg_start('growth:distill run', _job),
                                   ensure_ascii=False, default=str)

            if sub in ('on', 'off'):
                from core.config import set_value as _sv
                try:
                    _sv('growth.distill_enabled', sub == 'on')
                except Exception as e:                              # noqa: BLE001
                    return _err(f'配置写入失败：{type(e).__name__}: {e}')
                return _json.dumps({
                    'ok': True, 'written': True,
                    'enabled': bool(eng.growth.cfg('distill_enabled', True)),
                    'note': ('已开始登记蒸馏队列（老师端仍需已配置）'
                             if sub == 'on' else
                             '已关闭：新对话不再入队，队列里已有的留着，'
                             'growth:distill run 也不会发请求')},
                    ensure_ascii=False, default=str)

            if sub == 'limit':
                from core.config import set_value as _sv
                try:
                    n = int(rest_arg.strip())
                except (TypeError, ValueError):
                    return _err(f'limit 要一个 1~200 的整数，收到：{rest_arg!r}')
                if not 1 <= n <= 200:
                    return _err(f'每轮上限要在 1~200 之间，收到：{n}')
                try:
                    _sv('growth.distill_batch_limit', n)
                except Exception as e:                              # noqa: BLE001
                    return _err(f'配置写入失败：{type(e).__name__}: {e}')
                return _json.dumps({'ok': True, 'written': True,
                                    'limit': int(eng.growth.cfg(
                                        'distill_batch_limit', 8))},
                                   ensure_ascii=False, default=str)

            return _err(f'未知 growth:distill 参数：{sub}'
                        '（可用：只读 / run [条数] / on / off / limit <n>）')

        if op in ('pause', 'resume'):
            # 暂停不是只写个布尔就完事：should_train / train_round /
            # check_and_promote 三处都在读 is_paused()，所以恢复后要回显
            # 「下一轮到底能不能练」，前端才敢说话。
            g = eng.growth
            if op == 'pause':
                reason = arg or '用户手动暂停'
                already = bool(g.state().get('paused'))
                try:
                    res = g.pause(reason)
                except Exception as e:                                  # noqa: BLE001
                    return _err(f'暂停失败：{type(e).__name__}: {e}')
                res['already_paused'] = already
                res['note'] = ('已暂停：自动训练与晋升检查会跳过；'
                               '对话记录照常收集（暂停不等于停止收集）')
                return _json.dumps(res, ensure_ascii=False, default=str)
            try:
                res = g.resume()
            except Exception as e:                                      # noqa: BLE001
                return _err(f'恢复失败：{type(e).__name__}: {e}')
            try:
                gate = g.should_train(manual=True)
                res['can_train_now'] = bool(gate.get('ok'))
                res['train_blockers'] = gate.get('reasons', [])
            except Exception as e:                                      # noqa: BLE001
                res['train_gate_error'] = f'{type(e).__name__}: {e}'
            res['note'] = '已恢复：自动训练与晋升检查重新生效'
            return _json.dumps(res, ensure_ascii=False, default=str)

        if op == 'status':
            # eng.growth.status() 本身是只读的（should_train(manual=True) 不写盘），
            # 所以前端刷新成长页不会把「看了一眼」写成流水。
            try:
                return _json.dumps({'ok': True, **eng.growth.status()},
                                   ensure_ascii=False, default=str)
            except Exception as e:                                      # noqa: BLE001
                return _err(f'成长状态读取失败：{type(e).__name__}: {e}')

        if op == 'rollback':
            g = eng.growth
            from pathlib import Path as _P
            sub, _, tail = (arg or '').strip().partition(' ')
            sub, tail = sub.strip().lower(), tail.strip().lower()
            if sub in ('', 'status', 'list'):
                try:
                    reg = g.lifecycle.registry()
                    trash = [x for x in reg.get('generations', [])
                             if x.get('status') == 'trash']
                    trash.sort(key=lambda x: int(x.get('gen', 0)), reverse=True)
                    act = g.lifecycle.active() or {}
                    return _json.dumps({
                        'ok': True, 'readonly': True,
                        'active_gen': act.get('gen'),
                        'can_rollback': bool(trash),
                        'trash': [{'gen': x.get('gen'), 'bytes': x.get('bytes'),
                                   'retired_at': x.get('retired_at', ''),
                                   'exists': bool(_P(str(x.get('dir', ''))).exists())}
                                  for x in trash],
                        'usage': ('growth:rollback <代> 演练预览｜'
                                  'growth:rollback <代> confirm 真的回滚'),
                        'note': ('回收区为空：说明还没发生过换代，'
                                 '没有可回滚的基底' if not trash else
                                 '回滚会把当前基底移进回收区，再把选中代数搬回来')},
                        ensure_ascii=False, default=str)
                except Exception as e:                                  # noqa: BLE001
                    return _err(f'回收区读取失败：{type(e).__name__}: {e}')
            try:
                gen = int(sub)
            except ValueError:
                return _err(f'rollback 要一个代数（整数），收到：{sub}')
            if tail != 'confirm':
                try:
                    preview = g.lifecycle.rollback(gen, dry_run=True)
                except Exception as e:                                  # noqa: BLE001
                    return _err(f'回滚预览失败：{type(e).__name__}: {e}')
                # 预览却报 ok=True 而不带 dry_run，就是假成功 —— 宁可报错。
                if not preview.get('dry_run'):
                    preview['readonly'] = True
                    preview['note'] = ('演练未确认通过（该代数可能不在回收区，'
                                       '或其目录已不存在）')
                    return _json.dumps(preview, ensure_ascii=False, default=str)
                preview['readonly'] = True
                preview['next'] = f'growth:rollback {gen} confirm 才会真的回滚'
                return _json.dumps(preview, ensure_ascii=False, default=str)

            def _job_rb(cancel_event, output, _g=g, _gen=gen):
                if cancel_event.is_set():
                    return {'ok': False, 'cancelled': True}
                output(f'回滚到第 {_gen} 代：当前基底移入回收区')
                res = _g.rollback(_gen)
                output(res.get('message') or str(res))
                return res
            return _json.dumps(_bg_start(f'growth:rollback {gen} confirm', _job_rb),
                               ensure_ascii=False, default=str)

        if op == 'gc':
            g = eng.growth
            sub, _, tail = (arg or '').strip().partition(' ')
            sub, tail = sub.strip().lower(), tail.strip().lower()
            if sub not in ('run', 'force'):
                # 裸调用（含 `gc <n>`）只做演练，既不删目录也不写 journal ——
                # GrowthEngine.gc() 无条件记一条 journal，这里必须绕开它，
                # 否则前端每刷一次成长页就多一行流水。
                keep = None
                if sub:
                    try:
                        keep = max(1, min(24, int(sub)))
                    except ValueError:
                        return _err(f'gc 的保留数要是整数，收到：{sub}')
                try:
                    res = dict(g.lifecycle.gc(keep=keep, dry_run=True))
                except Exception as e:                                  # noqa: BLE001
                    return _err(f'GC 演练失败：{type(e).__name__}: {e}')
                res.update({'ok': True, 'readonly': True,
                            'next': 'growth:gc run 真的删除；'
                                    'growth:gc run force 跳过稳定期约束',
                            'usage': 'growth:gc [保留数] 只演练，不删任何文件'})
                return _json.dumps(res, ensure_ascii=False, default=str)
            force = (tail == 'force') or (sub == 'force')

            def _job_gc(cancel_event, output, _g=g, _f=force):
                if cancel_event.is_set():
                    return {'ok': False, 'cancelled': True}
                output('GC：删除已过稳定期的回收代（只删 status=trash 的目录）')
                res = _g.gc(force=_f)
                # lifecycle.gc 只回 allowed/deleted，不带 ok —— 但前端需要一个
                # 明确的判定，所以在这里按真值补上：稳定期没过就是没做成。
                res['ok'] = bool(res.get('allowed'))
                output(res.get('message') or str(res))
                return res
            return _json.dumps(_bg_start('growth:gc run', _job_gc),
                               ensure_ascii=False, default=str)

        if op == 'purge':
            g = eng.growth
            scope, _, tail = (arg or '').strip().partition(' ')
            scope = (scope or 'all').strip().lower()
            valid = ('all', 'trained', 'disliked', 'dpo')
            if scope not in valid:
                return _err(f'purge 范围只能是 {" / ".join(valid)}，收到：{scope}')
            if tail.strip().lower() != 'confirm':
                # 只读预览：按 scope 数一遍会删掉多少条，不执行任何 DELETE。
                try:
                    st = g.store.stats()
                except Exception as e:                                  # noqa: BLE001
                    return _err(f'样本统计读取失败：{type(e).__name__}: {e}')
                counts = {'all': st.get('total', 0),
                          'trained': st.get('used_in_training', 0),
                          'disliked': (st.get('feedback') or {}).get('dislike', 0),
                          'dpo': st.get('dpo_pairs', 0)}
                return _json.dumps({
                    'ok': True, 'readonly': True, 'scope': scope,
                    'would_remove': counts.get(scope, 0),
                    'stats': st,
                    'warning': ('purge 不可撤销：删掉的样本无法恢复。'
                                f'确认请发 growth:purge {scope} confirm'),
                }, ensure_ascii=False, default=str)

            def _job_purge(cancel_event, output, _g=g, _s=scope):
                if cancel_event.is_set():
                    return {'ok': False, 'cancelled': True}
                output(f'清理样本（scope={_s}）——不可撤销')
                res = _g.store.purge(_s)
                output(res.get('error') or
                       f"已删除 {res.get('removed')} 条，剩余 {res.get('remaining')} 条")
                return res
            return _json.dumps(_bg_start(f'growth:purge {scope}', _job_purge),
                               ensure_ascii=False, default=str)

        return _err(f'未知 growth 子命令：{op}'
                    '（可用：persona / timeline / daily / goal / first / report'
                    ' / promotecheck / promote / distill / pause / resume'
                    ' / status / rollback / gc / purge）')
    except Exception as e:                                              # noqa: BLE001
        logger.exception('growth command failed: %s', cmd)
        return _err(f'{type(e).__name__}: {e}')


# ---------------- 导出 / 验收指令的共用小工 ----------------
# 放在模块级（而不是嵌在处理函数里）：training: 与 growth: 两族都要用。

def _bg_start(name: str, job) -> dict:
    """把长任务交给后台任务表，立即返回 task_id。

    返回里一定带 poll：告诉前端「用 agent:task status <id> 接着问」，
    不然调用方只会盯着这一个响应，以为任务已经做完。
    """
    try:
        r = dict(_get_bg_tasks().start_task(name, job))
    except Exception as e:                                              # noqa: BLE001
        return {"ok": False,
                "error": f"后台任务启动失败：{type(e).__name__}: {e}"}
    r["poll"] = f"agent:task status {r.get('task_id', '')}".strip()
    r["poll_result"] = f"agent:task result {r.get('task_id', '')}".strip()
    return r


def _acceptance_cfg() -> dict:
    """读晋升验收配置。拿不到配置时如实返回 unknown，不猜一个「已开启」。"""
    try:
        from core.config import load as _load_cfg
        g = ((_load_cfg() or {}).get("growth") or {})
        thr = g.get("pass_threshold", None)
        return {"enforced": bool(g.get("require_eval", False)),
                "threshold": float(thr) if thr is not None else None,
                "source": "config"}
    except Exception as e:                                              # noqa: BLE001
        return {"enforced": None, "threshold": None,
                "source": f"读取失败：{type(e).__name__}: {e}"}


def _acceptance_threshold():
    """给 eval_probe 用：没配置或读不到就返回 None，让它走模块默认值。"""
    t = _acceptance_cfg().get("threshold")
    return t


def _growth_base_dir():
    """当前基底模型目录（验收的对照方）。取不到返回 None，探针就只报绝对分。"""
    try:
        from core import growth as _g
        d = _g._resolve_base_model_dir()
        if d and (d / "config.json").is_file():
            return d
    except Exception:                                                    # noqa: BLE001
        pass
    try:
        from core.model import ModelStore
        d = ModelStore().find_installed()
        if d is not None and d.is_dir() and (d / "config.json").is_file():
            return d
    except Exception:                                                    # noqa: BLE001
        pass
    return None


def _resolve_model_dir_for_cmd(arg: str = ""):
    """把「模型名字或目录路径」解析成一个 HF 模型目录；解析不了返回 None。"""
    from pathlib import Path as _P
    s = (arg or '').strip()
    if not s:
        # 没指名：默认取最近合并出来的那个 <基座>+grown
        try:
            from core import export as _export
            root = _export._star_models_dir()
            grown = sorted([p for p in (root.glob(f"*{_export.MERGED_SUFFIX}")
                                        if root.is_dir() else [])
                            if (p / "config.json").is_file()],
                           key=lambda p: p.stat().st_mtime)
            return grown[-1] if grown else None
        except Exception:                                                # noqa: BLE001
            return None
    p = _P(s).expanduser()
    if p.is_dir() and (p / "config.json").is_file():
        return p
    try:
        from core.model import ModelStore
        d = ModelStore().find_installed(s)
        if d is not None and d.is_dir() and (d / "config.json").is_file():
            return d
    except Exception:                                                    # noqa: BLE001
        pass
    return None


def _parse_gguf_arg(arg: str) -> tuple[str, str]:
    """training:gguf <目录或名字> [量化] → (target, quant)。

    约定：最后一个空白分隔的 token 是量化名，其余算目录/名字。
    带空格的 Windows 路径请用引号外的完整路径直接给（不支持内嵌空格），
    这点在 training: 指令族的帮助文案里对用户明说，不做「猜一半」。
    """
    parts = (arg or '').split()
    if not parts:
        return '', 'q4_k_m'
    if len(parts) == 1:
        return parts[0], 'q4_k_m'
    return ' '.join(parts[:-1]), parts[-1]


def _training_merge_status() -> dict:
    """merge_status() + 当前基座 + 验收配置，一次给全前端要展示的事实。"""
    out: dict = {}
    try:
        from core import export as _export
        out = dict(_export.merge_status())
    except Exception as e:                                              # noqa: BLE001
        out = {"ok": False,
               "error": f"导出状态读取失败：{type(e).__name__}: {e}"}
    base = _growth_base_dir()
    out["current_base_dir"] = str(base) if base else ""
    out["acceptance"] = _acceptance_cfg()
    return out


def _handle_training_cmd(cmd: str) -> str:
    """训练元数据指令族。返回 JSON 字符串。

    存在的理由：TrainingProgress 流里只有 step / total / loss / status 四个
    字段（proto 早期约定），拿不到「这次训练到底是不是真的、在哪个设备上
    跑的、prompt 有没有 mask、适配器写到哪、能不能续训」。这些是判断训练
    可信度的关键信息，用 ExecuteCommand+JSON 补出来，不必改 proto。

    子命令：
        training:status    当前训练实时快照（含 kind / eval_loss / adapter_dir）
        training:env       训练环境（torch / peft 可用性、设备、可训练基座）
        training:adapter   适配器目录实况（体积、文件、target_modules、可否加载）
        training:history   最近 N 次训练记录（含真实 loss 曲线与 metadata）
        training:cancel [原因]  停止正在跑的训练（真停，不是只改个状态字）
        training:live      当前登记的训练实例与进度（调试用，验证 cancel 能打中）

        —— 下面这组是「练完能不能真的用起来」（core/export.py、
        core/eval_probe.py）。都是长任务，扔进后台任务表立即返回 task_id，
        进度与结果用既有的 agent:task status/result <task_id> 轮询。

        training:mergestatus   导出条件快照（适配器/基座/llama.cpp/剩余空间）
        training:export [名字] LoRA 合并回基座，产出独立 HF 模型目录
        training:gguf <目录> [量化]  用本机 llama.cpp 转 GGUF（缺工具如实拒绝）
        training:probe [目录]  对合并产物跑生成式验收（对照当前基座）
        training:acceptance [on|off|阈值]  晋升前是否必须过验收（读写配置）
        training:checkpoint [<步数> [auto|always|off] | off]
                             断点续训开关（读写 config.growth）。前端传不进
                             save_steps/resume（proto 不能改），只能由这里配置。
        training:api [on|off|base <url>|key <密钥>|model <名字>|test]
                             API 接入设置（OpenAI 兼容端点，读写
                             config.training.api_*，key 打码回显）。
    """
    import json as _json

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    rest = (cmd or '').strip()
    if not rest:
        return _err('缺少子命令')
    op, _, arg = (rest + ' ').partition(' ')
    op, arg = op.strip(), arg.strip()

    try:
        if op == 'status':
            d = _train_state_snapshot()
            d['ok'] = True
            d['elapsed_sec'] = round(time.time() - float(d.get('started_at') or 0), 1) \
                if d.get('started_at') else 0.0
            # 取消请求已经发出但循环还没跑完当前 step —— 前端要能区分
            # 「正在取消」和「真的停了」，否则按钮点了像没反应。
            # 只看最近登记的那个实例（正在跑的就是最后一个），并要求快照
            # 仍 active：跑完的实例 cancelled 标记不会自己清，不看 active
            # 会让「正在取消」一直挂着。
            d['cancel_requested'] = False
            if d.get('active'):
                try:
                    from core.trainer import live_trainers
                    recent = live_trainers()
                    tr = recent[-1] if recent else None
                    if tr is not None and tr.cancelled:
                        d['cancel_requested'] = True
                        d['cancel_reason'] = tr.stop_reason or 'user'
                        d['cancel_step'] = tr.global_step
                except Exception as e:                                          # noqa: BLE001
                    # 不能静默：读不到 live_trainers 时 cancel_requested 会留在
                    # False，界面就显示「训练中」而把用户已点的停止吞掉。
                    # 留一个字段，让前端至少能说「取消状态未确认」。
                    d['cancel_state_error'] = f'{type(e).__name__}: {e}'
                    logger.warning('training:status 读取取消状态失败：%s', e)
            return _json.dumps(d, ensure_ascii=False, default=str)

        if op == 'env':
            info = {"ok": True,
                    # 前端据此显示「打包版无法在线装训练栈」横幅与按钮前置校验
                    "frozen": bool(getattr(sys, "frozen", False))}
            for mod in ("torch", "transformers", "peft", "accelerate", "bitsandbytes"):
                try:
                    m = __import__(mod)
                    info[mod] = str(getattr(m, "__version__", "?"))
                except Exception:                                       # noqa: BLE001
                    info[mod] = None          # 没装就是没装，前端据此提示装依赖
            try:
                from core.model import best_device
                info["device"] = best_device()
            except Exception:                                           # noqa: BLE001
                info["device"] = "cpu"
            try:
                from core.trainer import _resolve_model_dir
                mdir, why = _resolve_model_dir(None)
                info["trainable_base"] = str(mdir) if mdir else ""
                info["trainable_base_ok"] = bool(mdir)
                info["trainable_base_reason"] = why
            except Exception as e:                                      # noqa: BLE001
                info["trainable_base_ok"] = False
                info["trainable_base_reason"] = f'{type(e).__name__}: {e}'
            return _json.dumps(info, ensure_ascii=False, default=str)

        if op == 'adapter':
            from core.config import STAR_DIR
            from core.growth import human_bytes
            ad = STAR_DIR / "adapter"
            latest = ad / "lora_latest"
            out = {"ok": True, "adapter_dir": str(ad), "exists": ad.is_dir()}
            weights = [p for p in (ad.glob("adapter_model*") if ad.is_dir() else [])]
            out["weight_files"] = [{"name": p.name, "bytes": p.stat().st_size,
                                    "human": human_bytes(p.stat().st_size)}
                                   for p in weights]
            cfg = ad / "adapter_config.json"
            if cfg.exists():
                try:
                    c = _json.loads(cfg.read_text(encoding="utf-8"))
                    out["target_modules"] = c.get("target_modules")
                    out["r"] = c.get("r")
                    out["lora_alpha"] = c.get("lora_alpha")
                    out["fan_in_fan_out"] = c.get("fan_in_fan_out")
                    # 历史遗留的模拟产物绝不该被当成真适配器展示
                    out["simulated"] = bool(c.get("simulated"))
                except (OSError, _json.JSONDecodeError) as e:
                    out["config_error"] = str(e)
            else:
                out["config_error"] = "adapter_config.json 不存在（尚未成功训练）"
            ck = ad / "checkpoints"
            # 名字按字符串排序会让 step10 排在 step2 前面；这里按步数排，
            # 并把「有没有可用检查点」按 trainer 的真实判据（adapter_config.json）
            # 来算 —— 否则界面显示「可续训」，trainer 却当场拒绝。
            ck_dirs = [p for p in (ck.iterdir() if ck.is_dir() else [])
                       if p.is_dir() and p.name.startswith('step')]

            def _step_of(p):
                try:
                    return int(p.name[4:])
                except ValueError:
                    return -1

            ck_sorted = sorted(ck_dirs, key=_step_of)
            out["checkpoints"] = [p.name for p in ck_sorted]
            ck_valid = [p for p in ck_sorted
                        if _step_of(p) >= 0 and (p / 'adapter_config.json').is_file()]
            out["checkpoints_usable"] = [p.name for p in ck_valid]
            out["checkpoint_missing_weights"] = [
                p.name for p in ck_sorted if p not in ck_valid]
            out["lora_latest"] = str(latest)
            out["lora_latest_exists"] = latest.is_dir()
            st = ad / "trainer_state.json"
            claimed = 0
            state_ok = True
            has_state = st.exists()
            if has_state:
                try:
                    s = _json.loads(st.read_text(encoding="utf-8"))
                    out["global_step"] = s.get("global_step")
                    # 只说真话：state 记了步数但检查点没了 = 不可续训，
                    # trainer 现在会直接拒绝（见 trainer._run 的 resume_denied）。
                    claimed = int(s.get("global_step") or 0)
                    out["state_updated_at"] = s.get("updated_at")
                    out["state_adapter_dir"] = s.get("adapter_dir")
                    out["latest_checkpoint"] = s.get("latest_checkpoint", "")
                except (OSError, _json.JSONDecodeError, TypeError, ValueError) as e:
                    state_ok = False
                    out["state_error"] = f"{type(e).__name__}: {e}"
                    # 状态文件坏掉 = trainer 读不出进度 = 不会续训。
                    # 字段不能缺着让前端自己猜。
                    out["resumable"] = False
                    out["resume_would_use"] = ""
                    out["optimizer_in_checkpoint"] = False
                    out["resume_blocked_reason"] = (
                        f"trainer_state.json 读不出来（{type(e).__name__}），"
                        "无法判断进度，因此不会续训。")
            else:
                out["resumable"] = False
                out["resume_would_use"] = ""
                out["optimizer_in_checkpoint"] = False
                out["resume_blocked_reason"] = "还没有 trainer_state.json（从未训练过）"
            if state_ok:
                # 真正会被用来续训的那个检查点 = 不超过 state 步数里最大的那个，
                # 判据与 trainer._latest_checkpoint 完全一致。此前这里看的是
                # 「目录里最大的」：state 说 6 步而磁盘上有个更新的 step8（手工
                # 拷进来的备份）时，报的可续与否和 optimizer 有无都不是 trainer
                # 真会用的那个 —— 界面与后端又会打架。
                ck_used = next((p for p in reversed(ck_valid)
                                if _step_of(p) <= claimed), None)
                out["resumable"] = bool(claimed and ck_used is not None)
                out["resume_would_use"] = ck_used.name if ck_used else ""
                out["optimizer_in_checkpoint"] = bool(
                    ck_used is not None and (ck_used / 'optimizer.pt').is_file())
                if claimed and ck_valid and ck_used is None:
                    out["resume_blocked_reason"] = (
                        f"检查点都比状态记录的 {claimed} 步更新，没有可对齐的进度，"
                        "不会续训（重跑一次训练即可）。")
                elif claimed and not ck_valid:
                    out["resume_blocked_reason"] = (
                        f"状态记录 {claimed} 步，但 checkpoints 目录下没有任何"
                        "可用权重，续训会被拒绝（只能从头训）。")
                elif not claimed and has_state:
                    out["resume_blocked_reason"] = (
                        "状态里 global_step=0，没有可续的进度。")
            # 续训开关本身也报出来：不然前端显示「不可续训」，用户不知道是
            # 检查点没了还是压根没开这个功能。
            try:
                from core.trainer import checkpoint_cfg as _ck_cfg
                out["checkpoint_setting"] = _ck_cfg()
            except Exception as e:                                    # noqa: BLE001
                out["checkpoint_setting"] = {"interval": None, "mode": None,
                                             "error": f"{type(e).__name__}: {e}"}
            if (out["checkpoint_setting"] or {}).get("interval") in (0, None):
                out["resume_hint"] = (
                    "断点续训未开启（growth.checkpoint_interval=0），每次训练都"
                    "从第 0 步开始。要打开用 training:checkpoint 50 auto。")
            return _json.dumps(out, ensure_ascii=False, default=str)

        if op == 'history':
            from core.engine import XiaoLing as _XL
            n = 10
            try:
                n = max(1, min(200, int(arg or 10)))
            except ValueError:
                n = 10
            hist = _XL.read_training_history()[-n:][::-1]
            return _json.dumps({"ok": True, "records": hist},
                               ensure_ascii=False, default=str)

        if op == 'cancel':
            # 真的取消：trainer 的循环每轮检查 cancelled 标记，当前 step 跑完
            # 就退出并照常落盘（已训好的权重不丢）。没有句柄时如实说没有。
            try:
                from core.trainer import request_cancel
            except Exception as e:                                          # noqa: BLE001
                logger.exception('trainer import failed for cancel')
                return _err(f'训练模块不可用：{type(e).__name__}: {e}')
            r = request_cancel((arg or 'user').strip()[:60] or 'user')
            r['ok'] = bool(r.get('ok'))
            if r['ok']:
                _train_state_update(status='正在取消…（当前 step 结束后退出）')
            return _json.dumps(r, ensure_ascii=False, default=str)

        if op == 'live':
            try:
                from core.trainer import live_trainers
            except Exception as e:                                          # noqa: BLE001
                return _err(f'训练模块不可用：{type(e).__name__}: {e}')
            rows = [{'step': tr.global_step, 'total_steps': tr.total_steps,
                     'cancelled': tr.cancelled,
                     'reason': tr.stop_reason} for tr in live_trainers()]
            return _json.dumps({'ok': True, 'live': len(rows), 'trainers': rows},
                               ensure_ascii=False, default=str)

        # ---------------- 导出 / 验收（练完能不能真的用起来） ----------------
        if op in ('mergestatus', 'mergestate', 'exportstatus'):
            return _json.dumps(_training_merge_status(), ensure_ascii=False,
                               default=str)

        if op == 'export':
            # 合并是真活（加载基座 + merge_and_unload + 自检生成），CPU 上
            # 秒级到几十秒。同步跑会把这条 RPC 阻塞住，因此交给后台任务表，
            # 前端用既有的 agent:task status/result <task_id> 轮询。
            def _job(cancel_event, output, _name=arg):
                from core import export as _export
                output('开始合并：把 LoRA 权重并回基座')
                if cancel_event.is_set():
                    return {"ok": False, "cancelled": True}
                r = _export.merge_adapter(out_name=_name or None)
                if r.get("ok"):
                    output(f"已产出独立模型目录：{r.get('path')}"
                           f"（{r.get('bytes', 0)} 字节，"
                           f"{r.get('elapsed_sec')} 秒）")
                    output('产物已通过独立重新加载 + 真实生成自检')
                else:
                    output(f"合并失败（{r.get('stage', '?')}）：{r.get('reason')}")
                return r
            return _json.dumps(_bg_start('training:export', _job),
                               ensure_ascii=False, default=str)

        if op == 'gguf':
            target, quant = _parse_gguf_arg(arg)
            from core import export as _export
            d = _export.find_llama_cpp()
            if not d.get('found'):
                # 没工具时先如实回答，绝不「假装在转」
                return _json.dumps({"ok": False, "reason": d["reason"],
                                    "gguf": d}, ensure_ascii=False, default=str)
            mdir = _resolve_model_dir_for_cmd(target)
            if not mdir:
                return _err(f'找不到要转换的模型目录：{target or "（未指定）"}'
                            '（用法：training:gguf <模型目录或名字> [量化]）')

            def _job(cancel_event, output, _d=mdir, _q=quant):
                from core import export as _export
                output(f'用 {_export.find_llama_cpp().get("convert")} '
                       f'转换 {_d.name} → GGUF（{_q}）')
                if cancel_event.is_set():
                    return {"ok": False, "cancelled": True}
                r = _export.convert_to_gguf(_d, quant=_q)
                output(r.get("reason") or r.get("quant_note")
                       or f"已产出 {r.get('gguf')}")
                return r
            return _json.dumps(_bg_start('training:gguf', _job),
                               ensure_ascii=False, default=str)

        if op == 'probe':
            mdir = _resolve_model_dir_for_cmd(arg)
            if not mdir:
                return _err(f'找不到要验收的模型目录：{arg or "（未指定）"}'
                            '（先 training:export 产出一个 <基座>+grown 目录）')

            def _job(cancel_event, output, _d=mdir):
                from core import eval_probe as _probe
                base = _growth_base_dir()
                output(f'对 {_d.name} 跑生成式验收'
                       + (f'（对照基座 {base.name}）' if base else '（无对照基座）'))
                if cancel_event.is_set():
                    return {"ok": False, "cancelled": True}
                rep = _probe.run_probes(_d, teacher_dir=base,
                                        pass_rate=_acceptance_threshold())
                for row in rep.get("probes", []):
                    if row.get("ran"):
                        output(f"[{'通过' if row.get('ok') else '未通过'}] "
                               f"{row['id']}：{row.get('output', '')[:60]}")
                    else:
                        output(f"[未跑到] {row.get('id')}：{row.get('note', '')}")
                output(_probe.summarize(rep))
                return rep
            return _json.dumps(_bg_start('training:probe', _job),
                               ensure_ascii=False, default=str)

        if op == 'acceptance':
            # 读写 config.growth.require_eval / pass_threshold。
            # 这两个键此前只是躺在默认配置里从没被读过 —— 现在晋升链路真读它。
            want = (arg or '').strip().lower()
            if not want:
                return _json.dumps({'ok': True, **_acceptance_cfg()},
                                   ensure_ascii=False, default=str)
            from core.config import set_value
            acc = _acceptance_cfg()
            enabled = acc.get("enforced")
            threshold = acc.get("threshold")
            if want in ('on', 'true', '1', '开'):
                enabled = True
            elif want in ('off', 'false', '0', '关'):
                enabled = False
            else:
                try:
                    v = float(want)
                except ValueError:
                    return _err(f'acceptance 只接受 on / off / 0~1 的通过率阈值，'
                                f'收到：{arg}')
                if not 0.0 <= v <= 1.0:
                    return _err(f'阈值必须在 0~1 之间，收到：{v}')
                enabled, threshold = True, v
            if threshold is None:
                # 配置读不到时不能 float(None)：退回模块默认阈值并照实写进去
                try:
                    from core.eval_probe import PASS_RATE as _PR
                    threshold = float(_PR)
                except Exception:                                        # noqa: BLE001
                    threshold = 0.75
            try:
                set_value('growth.require_eval', bool(enabled))
                set_value('growth.pass_threshold', float(threshold))
            except Exception as e:                                        # noqa: BLE001
                return _err(f'配置写入失败：{type(e).__name__}: {e}')
            return _json.dumps({'ok': True, 'written': True,
                                **_acceptance_cfg()},
                               ensure_ascii=False, default=str)

        if op == 'api':
            # API 接入设置（OpenAI 兼容端点）。读写 config.training.api_*，
            # key 一律打码回显；test 发真实请求验证连通性。
            # 用法：
            #   training:api                 读取当前设置（打码）
            #   training:api on|off          启用/停用
            #   training:api base <url>      设置端点（http/https）
            #   training:api key <密钥>      设置密钥（空串=清除）
            #   training:api model <名字>    设置默认模型名
            #   training:api test            真实连通性测试
            try:
                from core.trainer import api_cfg, api_set, api_test
            except Exception as e:                                    # noqa: BLE001
                return _err(f'训练模块不可用：{type(e).__name__}: {e}')
            if not arg:
                return _json.dumps({**api_cfg(),
                                    'usage': 'training:api [on|off|base <url>|'
                                             'key <密钥>|model <名字>|test]'},
                                   ensure_ascii=False, default=str)
            parts = arg.strip().split(None, 1)
            sub = parts[0].strip().lower()
            if sub in ('on', 'off', 'true', 'false', '1', '0', '开', '关'):
                r = api_set('enabled', sub)
            elif sub in ('base', 'key', 'model'):
                if len(parts) < 2:
                    return _err(f'training:api {sub} 需要一个参数值')
                r = api_set(sub, parts[1].strip())
            elif sub == 'test':
                r = api_test()
            else:
                return _err(f'未知子参数：{sub}（可用：on/off/base/key/model/test）')
            return _json.dumps(r, ensure_ascii=False, default=str)

        if op == 'checkpoint':
            # 断点续训开关。proto 的 TrainingRequest 只有 5 个字段（不能改），
            # 前端传不进 save_steps/resume，所以这里写配置、trainer 在每次
            # 训练开始时读配置（core.trainer.checkpoint_cfg）。
            from core.trainer import (DEFAULT_CHECKPOINT_KEEP, checkpoint_cfg)
            cur = checkpoint_cfg()
            want = (arg or '').strip().lower()
            if not want:
                return _json.dumps({'ok': True, **cur,
                                    'usage': 'training:checkpoint <步数> '
                                             '[auto|always|off] [保留个数]｜'
                                             'training:checkpoint off'},
                                   ensure_ascii=False, default=str)
            parts = want.split()
            interval, mode, keep = cur['interval'], cur['mode'], int(
                cur.get('keep') or DEFAULT_CHECKPOINT_KEEP)
            first = parts[0]
            if first in ('off', '关'):
                interval, mode = 0, 'off'
            elif first in ('auto', 'always'):
                mode = first
                # 模式改了但间隔还是 0：等于「说要续训但没有可续的盘」，
                # 不猜一个间隔，直接拒绝并给出可用的写法。
                if len(parts) < 2 and interval < 1:
                    return _err(f'续训模式 {mode} 需要先有落盘间隔，例如 '
                                f'training:checkpoint 30 {mode}')
            else:
                try:
                    interval = int(first)
                except ValueError:
                    return _err('checkpoint 的第一参数要是步数（0~1000000 的整数）'
                                f'或 off / auto / always，收到：{first}')
                if interval < 0 or interval > 1_000_000:
                    return _err(f'落盘间隔要在 1~1000000 步之间（0=关闭），收到：{interval}')
                if interval == 0 and len(parts) < 2:
                    mode = 'off'      # 只写 0 = 整件事关掉，不留 auto 模式配 0 间隔
            for tok in parts[1:]:
                if tok in ('auto', 'always', 'off'):
                    mode = tok
                    continue
                try:
                    keep = int(tok)
                except ValueError:
                    return _err(f'无法理解参数「{tok}」：第二个位置给续训模式 '
                                f'(auto/always/off)，第三个给保留检查点个数（1~24）')
                if not 1 <= keep <= 24:
                    return _err(f'保留个数要在 1~24 之间，收到：{keep}')
            if interval < 1 and mode in ('auto', 'always'):
                # 间隔为 0 就不落盘，续训没有依托 —— 不写这种自相矛盾的配置。
                return _err(f'间隔为 0 时不落检查点，{mode} 续训不会生效。'
                            '要么给正数间隔（training:checkpoint 50 auto），'
                            '要么彻底关掉：training:checkpoint off')
            try:
                from core.config import set_value
                set_value('growth.checkpoint_interval', int(interval))
                set_value('growth.checkpoint_resume', mode)
                set_value('growth.checkpoint_keep', int(keep))
            except Exception as e:                                        # noqa: BLE001
                return _err(f'配置写入失败：{type(e).__name__}: {e}')
            out = checkpoint_cfg()
            if out['interval'] >= 1 and out['mode'] == 'off':
                # 落检查点但不自动续训是自洽的（省得每次都从头训），但用户
                # 多半想要的是「能续」，所以把差别说明白而不是替他猜。
                out['note'] = (f"每 {out['interval']} 步落一次检查点，但 "
                               'checkpoint_resume=off：训练不会自动接着上次跑。'
                               f"要续训请写 training:checkpoint {out['interval']} auto")
            elif out['interval'] >= 1:
                out['note'] = (f"从现在起每 {out['interval']} 步落一次检查点"
                               f"（磁盘上保留最近 {out['keep']} 个），"
                               '训练会自动从中断处续；在这之前开始的训练没有可续的'
                               '权重，仍从第 0 步开始。')
            else:
                out['note'] = '已关闭检查点与续训：此后训练每次都从第 0 步开始。'
            return _json.dumps({'ok': True, 'written': True, **out},
                               ensure_ascii=False, default=str)

        return _err(f'未知 training 子命令：{op}'
                    '（可用：status / env / adapter / history / cancel / live /'
                    ' mergestatus / export / gguf / probe / acceptance / checkpoint）')
    except Exception as e:                                          # noqa: BLE001
        logger.exception('training command failed: %s', cmd)
        return _err(f'{type(e).__name__}: {e}')


def _handle_channels_cmd(cmd: str) -> str:
    """多通道指令族：真实列出 / 开关 / 启停消息通道。返回 JSON 字符串。

    背景（这是一个"宣称有、实际没跑"的功能）：
      README 与定位表都写着「11 个通道对外触达」，core/channels.py 里也确实
      实现了 11 个通道类与 ChannelManager，但 **ChannelManager.start_all()
      全仓零调用方** —— 也就是说：通道从来没被启动过，设置页里那排开关
      改的只是一份本地 Map，后端完全不知情（UI 自己都写着"通道接入待后端支持"）。
      这里把通道真正接起来：开关写进配置，并且可以真的 start / stop。

    子命令：
        channels:list            每个通道的 enabled / configured / running
        channels:set <名> on|off 写入配置（并同步启停已运行的实例）
        channels:start           启动全部已启用通道
        channels:stop            停止全部通道
    """
    import json as _json

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    # 通道名 -> (配置里的 enabled 键, 判定"已配置"所需的凭据键列表)
    _SPEC = {
        "webhook":   ("webhook_enabled", []),
        "telegram":  ("telegram_enabled", ["telegram_bot_token"]),
        "discord":   ("discord_enabled", ["discord_webhook_url"]),
        "feishu":    ("feishu_enabled", ["feishu_webhook_url"]),
        "whatsapp":  ("whatsapp_enabled",
                      ["whatsapp_api_url", "whatsapp_token"]),
        "slack":     ("slack_enabled", ["slack_webhook_url"]),
        "signal":    ("signal_enabled", ["signal_api_url"]),
        "email":     ("email_enabled", ["smtp_host"]),
        "wecom":     ("wecom_enabled", ["wecom_webhook_url"]),
        "dingtalk":  ("dingtalk_enabled", ["dingtalk_access_token"]),
        "wechat_oa": ("wechat_oa_enabled", ["wechat_oa_appid",
                                            "wechat_oa_secret"]),
    }

    try:
        from core import config as _cfg
        cfg = _cfg.load() or {}
        mgr = _get_channel_manager()

        rest = (cmd or '').strip()
        op, _, arg = (rest + ' ').partition(' ')
        op, arg = op.strip().lower(), arg.strip()

        def _state(name: str) -> dict:
            en_key, creds = _SPEC.get(name, (f'{name}_enabled', []))
            enabled = bool(cfg.get(en_key, False))
            missing = [c for c in creds if not str(cfg.get(c) or '').strip()]
            return {
                "name": name,
                "enabled": enabled,
                # 「已配置」= 必填凭据齐全。webhook 无必填项，恒为已配置。
                "configured": not missing,
                "missing_credentials": missing,
                "running": name in getattr(mgr, "channels", {}),
            }

        if op in ('list', '', 'status', '列表'):
            return _json.dumps({
                "ok": True,
                "channels": [_state(n) for n in _SPEC],
            }, ensure_ascii=False, default=str)

        if op in ('set', 'toggle', 'switch', '开关'):
            parts = arg.split()
            if len(parts) != 2:
                return _err('用法：channels:set <通道名> on|off')
            name, val = parts[0], parts[1].lower()
            if name not in _SPEC:
                return _err(f'未知通道：{name}（可用：{" / ".join(_SPEC)}）')
            on = val in ('on', 'true', '1', 'yes', '开')
            en_key = _SPEC[name][0]
            cfg[en_key] = on
            try:
                _cfg.save(cfg)
            except Exception as e:                                   # noqa: BLE001
                return _err(f'配置写入失败：{e}')
            st = _state(name)
            # 已运行的实例同步启停，避免"开关改了但进程还活着"
            try:
                if on and not st["running"]:
                    mgr.start_enabled()
                elif not on and st["running"]:
                    mgr.restart_channels()
                st = _state(name)
            except Exception as e:                                   # noqa: BLE001
                # 启停失败要当成失败返回：此前只写进 note 仍回 ok:true，
                # 前端只检查 ok，于是「开关亮了但通道没起」被当成成功。
                return _err(f'开关已写入配置，但启停失败：{e}')
            return _json.dumps({"ok": True, "channel": st,
                                "message": f'{name} 已{"启用" if on else "停用"}'},
                               ensure_ascii=False, default=str)

        if op in ('start', '启动'):
            mgr.start_enabled()
            return _json.dumps({"ok": True, "message": "已启动全部启用的通道",
                                "channels": [_state(n) for n in _SPEC]},
                               ensure_ascii=False, default=str)

        if op in ('stop', '停止'):
            mgr.stop_running()
            return _json.dumps({"ok": True, "message": "已停止全部通道",
                                "channels": [_state(n) for n in _SPEC]},
                               ensure_ascii=False, default=str)

        if op in ('restart', '重启'):
            mgr.restart_channels()
            return _json.dumps({"ok": True, "message": "已重启全部启用的通道",
                                "channels": [_state(n) for n in _SPEC]},
                               ensure_ascii=False, default=str)

        return _err(f'未知通道子命令: {op}（可用：list / set / start / stop）')
    except Exception as e:                                              # noqa: BLE001
        logger.exception('channels command failed: %s', cmd)
        return _err(f'通道指令异常：{type(e).__name__}: {e}')


def _handle_system_cmd(cmd: str) -> str:
    """系统指令族：实时资源遥测 + 后端体检。返回 JSON 字符串。

    子命令：
        system:stats      实时 CPU / 内存 / 磁盘占用（跨平台，后端统一采样）
        system:health     后端子系统体检摘要（模块 / 依赖 / 目录 / RPC）
        system:selftest   完整自检文本（与 `main.py --selftest` 同源）

    为什么把遥测放到后端：原先前端在 UI 层按平台去 shell 外部命令
    （Windows 用 wmic、POSIX 用 df/free），而 wmic 在 Win10 21H1 起弃用、
    Win11 24H2 起默认不装 —— 拿不到值时 UI 就显示 0%，看起来像"占用 0%"，
    是实打实的假数据。现在统一由后端采样，拿不到就回报 available=false，
    前端显示「—」，绝不拿 0 冒充。
    """
    import json as _json

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    op = (cmd or '').strip().lower()
    if not op:
        return _err('缺少子命令（可用：stats / health / selftest）')

    try:
        if op in ('stats', 'telemetry', 'usage', '资源'):
            from core.sysinfo import sample_stats
            return _json.dumps(sample_stats(), ensure_ascii=False, default=str)

        if op in ('ports', '端口'):
            # 3D 查看器的**真实**端口。前端原先靠扫 8765~8785 猜端口：
            # 后端端口被占时会顺延，顺延出窗口就永远找不到；而盲扫还可能
            # 命中别的软件的同号服务，WebView 里渲染出莫名其妙的页面。
            # gRPC 这条连接是已经建立好的（否则问不到这里），所以由后端
            # 直接报真值是可靠的。
            out = {"ok": True, "grpc": int(_RUNNING_PORTS.get('grpc') or 0)}
            try:
                from core import webpanel as _wp
                st = _wp.web_state()
                out['web'] = int(st.get('port') or 0)
                out['web_host'] = st.get('host') or ''
                if st.get('error'):
                    out['web_error'] = st['error']
            except Exception as e:                              # noqa: BLE001
                # 查看器起不来要如实说，别让前端以为「再等等就有」。
                out['web'] = 0
                out['web_error'] = f'查看器状态读取失败：{type(e).__name__}: {e}'
            return _json.dumps(out, ensure_ascii=False, default=str)

        if op in ('health', 'summary', '体检'):
            from core import system as _system
            data = _system.summary()
            data = dict(data) if isinstance(data, dict) else {"summary": str(data)}
            data.setdefault('ok', True)
            return _json.dumps(data, ensure_ascii=False, default=str)

        if op in ('selftest', '自检'):
            from core import system as _system
            return _json.dumps({"ok": True, "text": _system.selftest()},
                               ensure_ascii=False, default=str)

        return _err(f'未知系统子命令: {op}（可用：stats / health / selftest）')
    except Exception as e:                                              # noqa: BLE001
        logger.exception('system command failed: %s', cmd)
        return _err(f'系统指令异常：{type(e).__name__}: {e}')


def _handle_sandbox(cmd: str) -> str:
    """沙箱指令路由。返回 JSON 字符串。

    桌面端（Windows / Linux / macOS）的模型商店下载与沙箱工具都走这里；
    Android 侧仍由 Termux 的 MethodChannel 提供，不经过本函数。

    子命令：
        sandbox:status               沙箱路径 + 用量 + 下载进度（UI 轮询这个）
        sandbox:download <名> [通道]  后台起线程下载模型（GB 级，不能同步等）
        sandbox:exec <命令>           在 workspace 内执行（带白名单与超时）
        sandbox:ls / read / write     受限的文件操作
        sandbox:path / usage          路径与用量快照
    """
    import json as _json
    import threading as _th

    def _err(msg):
        return _json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False)

    rest = (cmd or '').strip()
    if not rest:
        return _err('缺少子命令')
    op, _, arg = (rest + ' ').partition(' ')
    op, arg = op.strip(), arg.strip()

    try:
        from core import sandbox as _sb

        if op == 'status':
            st = _sb.status()
            # 前端要明确知道「本机沙箱到底是什么级别」，而不是一个笼统的
            # supported: true。桌面有 Landlock/Seatbelt/Job Object，移动端
            # 只有应用内受控执行，二者不能混为一谈。
            try:
                st['capability'] = _sb.capability()
            except Exception as e:                                # noqa: BLE001
                st['capability'] = {'isolation_level': 'unknown',
                                    'notes': f'能力探测失败：{e}'}
            return _json.dumps(st, ensure_ascii=False)

        if op in ('path', 'paths'):
            return _json.dumps({"ok": True, "paths": _sb.paths()},
                               ensure_ascii=False)

        if op == 'usage':
            return _json.dumps({"ok": True, "usage": _sb.usage()},
                               ensure_ascii=False)

        if op == 'download':
            parts = arg.split()
            if not parts:
                return _err('用法：sandbox:download <模型名> [通道]')
            name = parts[0]
            channel = parts[1] if len(parts) > 1 else 'auto'

            # 必须异步：几个 GB 的 GGUF 同步下载会把这条 RPC 请求堵死，
            # UI 也只有拿到即时返回才好去做轮询。
            def _worker():
                try:
                    from core.model import LocalModel
                    LocalModel().download(name, channel=channel)
                except Exception as e:                          # noqa: BLE001
                    from core.model import TASKS
                    TASKS[name] = {'percent': 0.0, 'status': 'error',
                                   'error': f'{type(e).__name__}: {e}'}

            _th.Thread(target=_worker, daemon=True).start()
            return _json.dumps(
                {"ok": True, "name": name,
                 "message": f'已在沙箱后台开始下载：{name}'},
                ensure_ascii=False)

        if op in ('exec', 'run'):
            return _json.dumps(_sb.run(arg), ensure_ascii=False)

        if op == 'ls':
            return _json.dumps(_sb.list_dir(arg), ensure_ascii=False)

        if op == 'read':
            return _json.dumps(_sb.read_file(arg), ensure_ascii=False)

        if op == 'write':
            p, _, content = arg.partition(' ')
            return _json.dumps(_sb.write_file(p, content), ensure_ascii=False)

        return _err(f'未知沙箱子命令：{op}')
    except Exception as e:                                      # noqa: BLE001
        logger.exception('sandbox command failed: %s', cmd)
        return _err(f'{type(e).__name__}: {e}')


def _scan_plugin_market(pmgr) -> list:
    """扫描磁盘上真实存在的插件目录（含 builtin/ 与用户安装）。

    扫描运行时插件目录（用户安装 + builtin/ 子目录）以及仓库内随包发布的
    plugins/builtin/ 示例。只读取 plugin.json/manifest.json，不伪造下载量、
    评分等任何不存在的字段。目录为空或不存在时返回空列表。
    """
    import json as _json
    from pathlib import Path

    roots = []
    try:
        roots.append(Path(pmgr.plugins_dir))
    except Exception:  # noqa: BLE001
        pass
    try:
        from core.config import APP_DIR
        shipped = Path(APP_DIR) / 'plugins'
        if shipped.is_dir() and shipped.resolve() not in {r.resolve() for r in roots}:
            roots.append(shipped)
    except Exception:  # noqa: BLE001
        pass

    def _read_state(root: Path) -> dict:
        try:
            sf = root / 'state.json'
            if sf.is_file():
                data = _json.loads(sf.read_text(encoding='utf-8'))
                if isinstance(data, dict) and isinstance(data.get('enabled'), dict):
                    return data['enabled']
        except Exception as e:  # noqa: BLE001
            logger.warning('插件市场读取状态失败 %s: %s', sf, e)
        return {}

    def _scan_root(root: Path, seen: set, out: list):
        if not root.is_dir():
            return
        state = _read_state(root)
        candidates = []
        try:
            for d in sorted(root.iterdir()):
                if d.is_dir() and not d.name.startswith('.') and d.name != 'builtin':
                    candidates.append((d, False))
        except OSError as e:
            logger.warning('插件市场遍历目录失败 %s: %s', root, e)
        builtin_root = root / 'builtin'
        if builtin_root.is_dir():
            try:
                for d in sorted(builtin_root.iterdir()):
                    if d.is_dir() and not d.name.startswith('.'):
                        candidates.append((d, True))
            except OSError as e:
                logger.warning('插件市场遍历内置目录失败 %s: %s', builtin_root, e)
        for d, is_builtin in candidates:
            manifest = None
            for fname in ('plugin.json', 'manifest.json'):
                f = d / fname
                if f.is_file():
                    try:
                        manifest = _json.loads(f.read_text(encoding='utf-8'))
                    except Exception as e:  # noqa: BLE001
                        logger.warning('插件市场清单解析失败 %s: %s', f, e)
                    break
            if not isinstance(manifest, dict):
                continue
            name = str(manifest.get('name') or d.name).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            out.append({
                'name': name,
                'version': str(manifest.get('version') or ''),
                'description': str(manifest.get('description') or ''),
                'author': str(manifest.get('author') or ''),
                'category': str(manifest.get('category') or ''),
                'enabled': bool(state.get(name, manifest.get('enabled', False))),
                'builtin': bool(is_builtin),
                'path': str(d),
            })

    out = []
    seen = set()
    for root in roots:
        _scan_root(root, seen, out)
    return out


def _handle_browser(body: str) -> str:
    """前端浏览器面板统一入口：browser:<op> [json-args]。返回 JSON 字符串。

    走 ExecuteCommand 而非新增 gRPC 方法 —— 与 settings:/sandbox: 同一思路，
    避免为几个浏览器动作改 proto 并重生成 Dart/Python 桩。
    核心原则：有真实浏览器就截图渲染，没有就明确降级，绝不假装能跑 JS。
    """
    import base64 as _b64
    import json as _json
    import tempfile as _tmp

    op, _, rest = body.partition(" ")
    op = op.strip().lower()
    rest = rest.strip()
    args = {}
    if rest:
        try:
            parsed = _json.loads(rest)
            if isinstance(parsed, dict):
                args = parsed
        except Exception:                                              # noqa: BLE001
            args = {}

    try:
        tool = _get_browser_tool()
    except Exception as e:                                             # noqa: BLE001
        return _json.dumps({"ok": False, "error": f"浏览器模块加载失败: {e}"},
                           ensure_ascii=False)

    def _shot_path() -> str:
        return os.path.join(_tmp.gettempdir(), "xl_browser_shot.png")

    def _attach_image(d: dict) -> dict:
        """把截图文件读成 base64 塞回结果；读不到就不带图，不报错。"""
        try:
            p = d.get("path")
            if p and os.path.isfile(p):
                with open(p, "rb") as f:
                    d["image_b64"] = _b64.b64encode(f.read()).decode("ascii")
        except Exception:                                              # noqa: BLE001
            pass
        d.pop("path", None)
        return d

    def _nav_then_shot(fn) -> dict:
        res = fn()
        if res.get("ok"):
            shot = tool.screenshot_current(_shot_path())
            res["rendered"] = shot.get("rendered", res.get("rendered"))
            if shot.get("ok"):
                res["path"] = shot.get("path")
            res["text"] = tool.get_page_text()
        return _attach_image(res)

    try:
        if op == "status":
            return _json.dumps(tool.status_dict(), ensure_ascii=False)

        if op == "navigate":
            url = (args.get("url") or "").strip()
            if not url:
                return _json.dumps({"ok": False, "error": "缺少 url"}, ensure_ascii=False)
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            res = tool.navigate_and_screenshot(url, _shot_path())
            if not res.get("ok") and not res.get("rendered"):
                try:
                    html = tool.render(url)
                    res = {
                        "ok": bool(html),
                        "rendered": False,
                        "url": tool.current_url or url,
                        "title": tool._extract_title(html),
                        "error": "静态模式：仅抓取原始 HTML，不渲染 JS",
                    }
                except Exception as e:                                      # noqa: BLE001
                    res = {"ok": False, "rendered": False, "error": str(e)}
            res["text"] = tool.get_page_text()
            return _json.dumps(_attach_image(res), ensure_ascii=False)

        if op == "back":
            return _json.dumps(_nav_then_shot(tool.go_back), ensure_ascii=False)
        if op == "forward":
            return _json.dumps(_nav_then_shot(tool.go_forward), ensure_ascii=False)
        if op == "reload":
            return _json.dumps(_nav_then_shot(tool.reload), ensure_ascii=False)

        if op == "screenshot":
            return _json.dumps(_attach_image(tool.screenshot_current(_shot_path())),
                               ensure_ascii=False)

        if op == "click":
            sel = (args.get("selector") or "").strip()
            if not sel:
                return _json.dumps({"ok": False, "error": "缺少 selector"}, ensure_ascii=False)
            return _json.dumps(_nav_then_shot(lambda: tool.click(sel)), ensure_ascii=False)

        if op == "fill":
            sel = (args.get("selector") or "").strip()
            val = args.get("value") or ""
            if not sel:
                return _json.dumps({"ok": False, "error": "缺少 selector"}, ensure_ascii=False)
            return _json.dumps(_nav_then_shot(lambda: tool.fill(sel, val)), ensure_ascii=False)

        if op == "evaluate":
            js = args.get("js") or ""
            if not js:
                return _json.dumps({"ok": False, "error": "缺少 js"}, ensure_ascii=False)
            return _json.dumps(tool.evaluate(js), ensure_ascii=False)

        if op == "wait":
            sel = (args.get("selector") or "").strip()
            if not sel:
                return _json.dumps({"ok": False, "error": "缺少 selector"}, ensure_ascii=False)
            return _json.dumps(
                tool.wait_for_selector(sel, int(args.get("timeout") or 5000)),
                ensure_ascii=False)

        if op == "text":
            return _json.dumps({
                "ok": True,
                "text": tool.get_page_text(),
                "rendered": tool._is_browser_ready(),
                "current_url": tool.current_url,
            }, ensure_ascii=False)

        if op == "search":
            q = (args.get("query") or "").strip()
            if not q:
                return _json.dumps({"ok": False, "error": "缺少 query"},
                                   ensure_ascii=False)
            res = tool.search(q, int(args.get("num") or 10))
            # tool.search 契约：异常时返回 [{"error": ...}]，正常返回结果列表
            if len(res) == 1 and isinstance(res[0], dict) and "error" in res[0]:
                return _json.dumps({"ok": False, "error": res[0]["error"],
                                    "query": q}, ensure_ascii=False)
            return _json.dumps({"ok": True, "results": res, "query": q},
                               ensure_ascii=False)

        return _json.dumps({"ok": False, "error": f"未知 browser 操作: {op}"},
                           ensure_ascii=False)
    except Exception as e:                                             # noqa: BLE001
        return _json.dumps({"ok": False, "error": f"browser {op} 失败: {e}"},
                           ensure_ascii=False)


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
            pmgr = _get_plugin_manager()
            if op == "list":
                return _ok(plugins=pmgr.list_plugins())
            if op == "market":
                return _ok(plugins=_scan_plugin_market(pmgr))
            if op == "enable":
                return _ok(message=f"已启用 {arg}") if pmgr.enable(arg) else _err(f"未找到插件 {arg}")
            if op == "disable":
                return _ok(message=f"已禁用 {arg}") if pmgr.disable(arg) else _err(f"未找到插件 {arg}")
            if op in ("install", "installurl", "install-url", "fromurl"):
                # 支持两种形式：
                #   plugin:install https://.../xxx.zip   → 真实下载安装
                #   plugin:install 插件名                 → 社区占位安装
                if not arg:
                    return _err("插件名或下载地址不能为空")
                if arg.startswith(("http://", "https://")):
                    r = pmgr.install_from_url(arg)
                    if not r.get("ok"):
                        return _err(r.get("error"))
                    return _ok(message=f"插件 {r.get('name')} 已下载安装"
                                       f"（默认关闭，请手动开启）", **r)
                r = pmgr.create_plugin(arg, description=f"社区插件 {arg}",
                                       category="community")
                if not r.get("ok"):
                    return _err(r.get("error"))
                return _ok(message=f"插件 {arg} 已安装（默认关闭，请手动开启）",
                           **r)

            if op in ("create", "custom", "new"):
                # plugin:create {"name":"x","description":"y","code":"..."}
                if not arg:
                    return _err("缺少插件定义 JSON")
                try:
                    spec = _json.loads(arg)
                except Exception as e:  # noqa: BLE001
                    return _err(f"JSON 解析失败：{e}")
                if not isinstance(spec, dict):
                    return _err("插件定义必须是 JSON 对象")
                r = pmgr.create_plugin(
                    name=spec.get("name", ""),
                    description=spec.get("description", ""),
                    category=spec.get("category", "custom"),
                    code=spec.get("code", ""),
                    author=spec.get("author", "用户"),
                )
                if not r.get("ok"):
                    return _err(r.get("error"))
                return _ok(message=f"自定义插件 {r.get('name')} 已创建"
                                   f"（默认关闭）", **r)

            if op in ("uninstall", "remove", "卸载"):
                if not arg:
                    return _err("插件名不能为空")
                r = pmgr.uninstall(arg)
                if not r.get("ok"):
                    return _err(r.get("error"))
                return _ok(message=f"插件 {arg} 已卸载并移入隔离区"
                                   f"（未删除）：{r.get('quarantined','')}",
                           **r)

            if op in ("reload", "restart", "重启"):
                # 热重载单个插件（卸载+重新从磁盘加载），供前端「重启插件」按钮。
                # 此前该按钮只 Navigator.pop 关闭弹窗，是假动作。
                if not arg:
                    # 无参数：整体重载（load_all 语义），返回加载数量。
                    n = pmgr.reload()
                    return _ok(message=f"已重新加载全部插件（{n} 个）", count=n)
                ok = pmgr.reload_plugin(arg)
                if not ok:
                    return _err(f"插件 {arg} 重载失败（未加载或不存在）")
                return _ok(message=f"插件 {arg} 已重新加载")

            if op in ("installpath", "install-path", "frompath"):
                # 从本机路径安装：.zip 走解压安装，目录走 install()。
                # 供前端「从本地文件导入」按钮（Flutter 无原生文件选择器，
                # 需用户填写后端可访问的绝对路径）。
                if not arg:
                    return _err("插件文件/目录路径不能为空")
                from pathlib import Path as _P
                target = _P(arg)
                if target.is_file() and target.suffix.lower() == ".zip":
                    r = pmgr.install_from_zip(str(target))
                elif target.is_dir():
                    r = pmgr.install(str(target))
                else:
                    return _err(f"路径不存在或类型不支持（仅 .zip 或目录）：{arg}")
                if not r.get("ok"):
                    return _err(r.get("error"))
                return _ok(message=f"插件 {r.get('name','')} 已安装（默认关闭，请手动开启）", **r)

            if op in ("dir", "path", "plugins_dir"):
                # 返回真实插件目录，供前端展示/复制（跨平台下无法自动开文件管理器）。
                return _ok(dir=str(pmgr.plugins_dir))

            if op == "state":
                return _ok(plugins={p["name"]: p["enabled"]
                                    for p in pmgr.list_plugins()},
                           state_file=str(pmgr._state_path()))
            return _err(f"未知插件操作: {op}")

        if cmd.startswith("sensitive:"):
            # 内容合规：把 engine 里的 SensitiveFilter 暴露给前端可查/可加词。
            # 此前 filter 已实例化但 check_sensitive/add_sensitive_word 零调用方，
            # 敏感词表就是死配置。现在既在对话链路真正生效（_compliance_mask），
            # 又能从这里读到/加词。
            rest = cmd[len("sensitive:"):].strip()
            op, _, arg = (rest + " ").partition(" ")
            arg = arg.strip()
            eng = _get_engine()
            if eng is None or not hasattr(eng, "check_sensitive"):
                return _err("引擎未就绪，敏感词过滤器不可用")
            if op in ("list", "words", ""):
                return _ok(words=eng.sensitive_words())
            if op in ("check", "test"):
                if not arg:
                    return _err("缺少待检文本")
                return _ok(**eng.check_sensitive(arg))
            if op in ("add", "append"):
                if not arg:
                    return _err("敏感词不能为空")
                eng.add_sensitive_word(arg)
                return _ok(message=f"已加入敏感词表", words=eng.sensitive_words())
            return _err(f"未知敏感词操作: {op}")

        if cmd.startswith("workflow:"):
            rest = cmd[len("workflow:"):].strip()
            op, _, payload = rest.partition(" ")
            payload = payload.strip()
            eng = _get_workflow_engine()

            def _build_from_spec(spec: dict):
                """把前端传来的 {name, description, nodes[], context{}} 建成 Workflow。"""
                from core.workflow_engine import WorkflowNode
                wf_name = spec.get("name") or "ui_workflow"
                nodes = spec.get("nodes") or []
                wf = eng.create_workflow(wf_name, spec.get("description", ""))
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
                return wf_name, wf

            if op == "list":
                # 连同完整定义一起返回：此前只回 nodes 的**数量**，前端拿不回
                # 已存工作流的节点与连线，无法"载入后继续编辑"。
                return _ok(workflows=eng.list_workflows(),
                           specs=[w.to_dict() for w in eng.workflows.values()])

            if op in ("get", "load"):
                name = payload
                wf = eng.workflows.get(name)
                if wf is None:
                    return _err(f"未找到工作流 {name}")
                return _ok(workflow=wf.to_dict())

            if op in ("save", "create", "put"):
                # 前端「保存工作流」入口：写入后端引擎并落盘到用户沙箱，
                # 与 LocalStore 的本地副本互为备份（换机器/清缓存后仍可找回）。
                spec = _json.loads(payload) if payload else {}
                if not isinstance(spec, dict) or not spec.get("name"):
                    return _err('save 需要 {"name":..., "nodes":[...]}')
                name, wf = _build_from_spec(spec)
                return _ok(message=f"工作流 {name} 已保存", name=name,
                           workflow=wf.to_dict())

            if op in ("delete", "remove", "del"):
                if not payload:
                    return _err("缺少工作流名")
                if payload not in eng.workflows:
                    return _err(f"未找到工作流 {payload}")
                eng.delete_workflow(payload)
                return _ok(message=f"工作流 {payload} 已删除")

            if op == "run":
                spec = _json.loads(payload) if payload else {}
                wf_name, _wf = _build_from_spec(spec)
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

        if cmd.startswith("memory:"):
            rest = cmd[len("memory:"):].strip()
            op, _, arg = (rest + " ").partition(" ")
            arg = arg.strip()
            engine = _get_engine()
            hub = getattr(engine, "memory_hub", None) if engine is not None else None
            if hub is None:
                return _err("记忆中心未就绪")
            graph = hub.graph
            long = hub.long
            if op == "stats":
                return _ok(memory=long.get_memory_stats(),
                           graph=graph.get_graph_stats())
            if op == "graph":
                return _ok(**graph.get_graph_stats())
            if op == "entity":
                if not arg:
                    return _err("缺少实体名")
                return _ok(entity=graph.get_entity(arg),
                           related=graph.get_related_entities(arg, depth=2))
            if op == "search":
                if not arg:
                    return _err("缺少搜索关键词")
                return _ok(results=graph.search_entities(arg))
            if op == "export":
                fmt = arg if arg in ("json", "graphml") else "json"
                return _ok(format=fmt, data=graph.export_graph(fmt))
            if op == "date":
                spec = _json.loads(arg) if arg else {}
                start = spec.get("start", "")
                end = spec.get("end", "")
                return _ok(items=long.search_by_date(start, end))
            if op == "forget":
                days = 30
                try:
                    days = int(arg) if arg else 30
                except ValueError:
                    days = 30
                removed = long.forget_old(days=days)
                return _ok(removed=removed, days=days)
            return _err(f"未知记忆操作: {op}")

        if cmd.startswith("activity:"):
            rest = cmd[len("activity:"):].strip()
            op, _, arg = (rest + " ").partition(" ")
            arg = arg.strip()
            from core.activity_log import get_activity_log
            log = get_activity_log()
            if op == "recent":
                try:
                    limit = int(arg) if arg else 20
                except ValueError:
                    limit = 20
                return _ok(activities=log.list_recent(limit),
                           stats=log.stats())
            if op == "by_type":
                type_ = (arg or "").strip()
                if type_ not in ("chat", "training", "model", "plugin", "system"):
                    return _err("未知活动类型，可选 chat/training/model/plugin/system")
                return _ok(type=type_, activities=log.list_by_type(type_, 50))
            if op == "stats":
                return _ok(**log.stats())
            if op == "clear":
                n = log.clear()
                return _ok(message=f"已清空 {n} 条活动日志", cleared=n)
            if op == "retention":
                if arg:
                    try:
                        days = log.set_retention_days(int(arg))
                        return _ok(message=f"日志保留天数已设为 {days} 天",
                                   retention_days=days)
                    except ValueError:
                        return _err("保留天数必须是整数")
                return _ok(retention_days=log.get_retention_days())
            return _err(f"未知活动日志操作: {op}")

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

        if cmd.startswith("kb:"):
            rest = cmd[len("kb:"):].strip()
            op, _, arg = (rest + " ").partition(" ")
            arg = arg.strip()
            kb = _get_knowledge_base()
            if op == "search":
                if not arg:
                    return _err("缺少检索关键词")
                top_k = 5
                m = re.match(r"^(.*?)\s+--top\s+(\d+)$", arg)
                if m:
                    arg, top_k = m.group(1).strip(), max(1, min(int(m.group(2)), 20))
                results = kb.hybrid_search(arg, top_k=top_k)
                return _ok(results=results, stats=kb.get_stats(), query=arg)
            if op == "list":
                return _ok(documents=kb.list_documents(), stats=kb.get_stats())
            if op == "add":
                if not arg:
                    return _err("缺少文档路径")
                if not os.path.isfile(arg):
                    return _err(f"文件不存在: {arg}")
                try:
                    with open(arg, "r", errors="ignore") as f:
                        content = f.read()
                except Exception as e:  # noqa: BLE001
                    return _err(f"读取失败: {e}")
                if not content.strip():
                    return _err("文档内容为空")
                name = os.path.basename(arg)
                n = kb.add_document(name, content, path=arg)
                return _ok(message=f"已索引 {name}（{n} 块）",
                           documents=kb.list_documents(), stats=kb.get_stats())
            if op == "delete":
                if not arg:
                    return _err("缺少文档名")
                ok = kb.delete_document(arg)
                return (_ok(message=f"已删除 {arg}") if ok
                        else _err(f"未找到文档 {arg}"))
            if op == "reindex":
                info = kb.reindex()
                return _ok(message="索引已重建", **info)
            if op == "source":
                if not arg:
                    return _err("缺少 chunk_id")
                src = kb.get_source(arg)
                return (_ok(source=src) if src else _err(f"未找到块 {arg}"))
            return _err(f"未知知识库操作: {op}")

        if cmd.startswith("code:"):
            rest = cmd[len("code:"):].strip()
            op, _, arg = (rest + " ").partition(" ")
            arg = arg.strip()
            try:
                idx = _get_code_indexer()
            except Exception as e:  # noqa: BLE001
                return _err(f"代码索引不可用: {e}")

            if op == "callers":
                if not arg:
                    return _err("缺少符号名")
                return _ok(**idx.find_callers(arg))
            if op == "callees":
                if not arg:
                    return _err("缺少符号名")
                return _ok(**idx.find_callees(arg))
            if op == "chain":
                m = re.match(r"^(.*?)\s+--depth\s+(\d+)$", arg)
                depth = 3
                if m:
                    arg, depth = m.group(1).strip(), int(m.group(2))
                if not arg:
                    return _err("缺少符号名")
                return _ok(**idx.get_call_chain(arg, max_depth=depth))
            if op == "graph":
                as_dot = "--dot" in arg
                clean = re.sub(r"--dot", " ", arg)
                dm = re.search(r"--depth\s+(\d+)", clean)
                depth = int(dm.group(1)) if dm else 2
                clean = re.sub(r"--depth\s+\d+", " ", clean).strip()
                if clean:
                    g = idx.get_subgraph(clean, depth=depth)
                else:
                    g = idx.build_call_graph()
                if as_dot:
                    return _ok(dot=idx.export_dot(g), center=clean or None,
                               node_count=g.get("node_count", len(g.get("nodes", []))),
                               edge_count=g.get("edge_count", len(g.get("edges", []))))
                return _ok(**g)
            if op == "goto":
                if not arg:
                    return _err("缺少位置 FILE:LINE:COL")
                parts = arg.rsplit(":", 2)
                if len(parts) != 3:
                    return _err("格式应为 FILE:LINE:COL")
                fpath, lns, cns = parts[0].strip(), parts[1].strip(), parts[2].strip()
                try:
                    lni, cni = int(lns), int(cns)
                except ValueError:
                    return _err("行/列必须为数字")
                return _ok(**idx.goto_definition(fpath, lni, cni))
            if op == "impl":
                if not arg:
                    return _err("缺少接口/抽象类名")
                return _ok(**idx.find_implementation(arg))
            if op == "inherits":
                if not arg:
                    return _err("缺少类名")
                return _ok(**idx.get_inheritance_chain(arg))
            return _err(f"未知代码索引操作: {op}")

        if cmd.startswith("dsh:"):
            # DSH 插件兼容层。core/dsh_compat.py 早已完整实现，但全仓零调用方
            # —— 所谓「兼容 DSH 生态」此前只是文件里的一段代码。这里真正接线。
            rest = cmd[len("dsh:"):].strip()
            op, _, arg = (rest + " ").partition(" ")
            arg = arg.strip()
            dsh = _get_dsh_compat()
            if op in ("list", "", "status"):
                return _ok(plugins=dsh.list_dsh_plugins(),
                           dir=dsh.plugins_dir)
            if op in ("available", "market"):
                return _ok(plugins=dsh.get_available_plugins())
            if op == "parse":
                if not arg:
                    return _err("缺少插件路径")
                return _json.dumps(dsh.parse_dsh_plugin(arg),
                                   ensure_ascii=False)
            if op in ("install", "add"):
                if not arg:
                    return _err("缺少插件来源（npm 包名 / 本地路径 / git URL）")
                return _json.dumps(dsh.install_dsh_plugin(arg),
                                   ensure_ascii=False)
            if op in ("uninstall", "remove"):
                if not arg:
                    return _err("缺少插件名")
                return _ok(message=f"已卸载 DSH 插件 {arg}",
                           removed=dsh.uninstall_dsh_plugin(arg))
            return _err(f"未知 DSH 操作: {op}")

        if cmd.startswith("git:"):
            # Git 工具（core/git_tool.py）。所有 git 命令都过 exec_gate 统一
            # 权限闸门（黑名单 / 联网判定 / 审批 / 审计），参数逐个 shlex.quote。
            # 前端可在**命令最前面**带可选令牌：
            #   --repo=<base64(绝对路径)>  对用户当前仓库操作
            #   --perm=<readonly|full>     配合 repo 显式升权（用户主动选择）
            # 用 base64 是为了路径里的空格/中文/引号绝不与提交信息串味。
            # 不传这些令牌时 = workspace + default，行为与旧版一致。
            rest = cmd[len("git:"):].strip()
            repo_override = ""
            perm_override = "default"
            import base64 as _b64
            while True:
                if rest.startswith('--repo='):
                    token, _, rest = rest.partition(' ')
                    try:
                        repo_override = _b64.b64decode(
                            token[len('--repo='):]).decode('utf-8',
                                                           'replace').strip()
                    except Exception:                                # noqa: BLE001
                        return _err("repo 路径解码失败（应为 --repo=<base64>）")
                    rest = rest.strip()
                elif rest.startswith('--perm='):
                    token, _, rest = rest.partition(' ')
                    perm_override = token[len('--perm='):].strip().lower()
                    rest = rest.strip()
                else:
                    break
            op, _, arg = (rest + " ").partition(" ")
            arg = arg.strip()
            gt = _get_git_tool(repo_override, perm_override)
            if op == "status":
                return _json.dumps(gt.status(), ensure_ascii=False)
            if op == "diff":
                return _json.dumps(gt.diff(arg or None), ensure_ascii=False)
            if op == "commit":
                if not arg:
                    return _err("缺少提交信息")
                return _json.dumps(gt.commit(arg), ensure_ascii=False)
            if op == "branches":
                return _json.dumps(gt.branches(), ensure_ascii=False)
            if op == "checkout":
                if not arg:
                    return _err("缺少分支名")
                return _json.dumps(gt.checkout(arg), ensure_ascii=False)
            if op == "log":
                try:
                    n = int(arg) if arg else 20
                except ValueError:
                    n = 20
                return _json.dumps(gt.log(n), ensure_ascii=False)
            return _err(f"未知 Git 操作: {op}")
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


def _config_module():
    """拿到 core.config 模块，打包态/开发态都能解析。

    开发态``backend/`` 在 sys.path 上，真实包名是 ``core``；打包态产物里
    只有 ``backend/core``，顶层 ``core`` 不存在于磁盘。直接写
    ``from core.config import ...`` 在打包态会 ModuleNotFoundError，
    而调用方普遍有 try/except 兜底 → 功能静默失效。这里两条路都试。

    失败时抛 ImportError，由调用方决定如何降级（不返回 None，避免
    调用方拿到 None 后 AttributeError）。
    """
    import importlib
    last = None
    for name in ('core.config', 'backend.core.config'):
        try:
            return importlib.import_module(name)
        except Exception as e:                              # noqa: BLE001
            last = e
    raise ImportError(f'无法导入配置模块（core.config / backend.core.config）：{last}')


def _get_renderer(log=print):
    """获取 3D 渲染层。

    分工：**画面**由 Flutter 端 model_viewer_plus 渲染；后端这一层负责
    **资源解析与状态维护**（VRM 元信息、动作库、当前模型/动作）。
    原先这里直接 return None，导致 PlayAction 恒报"渲染器不可用"——
    现在改为返回真实的资源舞台，动作播放与模型切换因此恢复可用。
    """
    global _renderer
    with _renderer_lock:
        if _renderer is None:
            try:
                from backend.renderer import get_renderer as _gr
                _renderer = _gr()
                if log:
                    log('[renderer] 3D 资源层已就绪（画面由 Flutter 渲染）')
            except Exception as e:                          # noqa: BLE001
                logger.warning('渲染层不可用：%s', e)
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
    "real": False,       # 是否为真实权重训练（trainer 不产出假曲线，False 即未训练）
    "kind": "",          # 最近一次事件类型：init/info/progress/eval/done/error
    "eval_loss": None,   # 最近一次验证集 loss（无验证集时为 None）
    "adapter_dir": "",   # 训练产出目录（done 事件带上）
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
            from core.config import APP_DIR
            cfg = _cfg.load()
            st = _get_growth_engine().status()
            # 运行时统计：运行时长、总请求数、平均响应时间，写入 message 字段
            uptime = int(time.time() - _server_started_at)
            total_req = sum(s["count"] for s in _request_stats.values())
            info = (f"uptime={uptime}s requests={total_req} "
                    f"avg_ms={_avg_request_ms():.1f}")
            # model 字段必须是「实时」的当前推理模型。
            #
            # 这里的做法经历过两次修坑，最终收敛到 core.model.active_model()：
            #   1. 最早取 cfg['model']['base_model'] —— 那是配置里的**静态默认值**，
            #      换成本地 GGUF / 接口模型后它永远不变，于是模型商店明明已经切到
            #      大模型，状态里还写着 Qwen2.5-0.5B，看起来就像"没加载成功"。
            #   2. 后来改成手工读 _local / get_model() / find_installed 三处兜底 ——
            #      逻辑散在 RPC 层，与 engine 的解析口径并不一致，两边仍可能打架。
            # 现在统一调用唯一真源：磁盘事实为准（已加载 > 选中 > 已安装 > 无），
            # 与「你是谁」的聊天回答、与聊天页头部显示的口径完全一致。
            live_model, loaded, no_model = '', False, False
            try:
                from core.model import active_model
                _eng = _get_engine()
                _mr = getattr(_eng, 'model_replace', None) if _eng else None
                _info = active_model(_mr)
                loaded = bool(_info.get('loaded'))
                no_model = not _info.get('available')
                live_model = str(_info.get('name') or '')
            except Exception:
                live_model, loaded, no_model = '', False, False
            if no_model:
                # 没装模型就**明说**没模型，而不是拿配置默认值假装有
                model_text = '未安装模型（请到模型商店下载）'
            elif live_model:
                model_text = live_model + ('（已加载）' if loaded else '（未加载）')
            else:
                model_text = str((cfg.get('model') or {}).get('base_model')
                                 or '默认')
            _ok = True
            return pb.StatusReply(
                ok=True,
                stage=str(st.get('stage', '初始化')),
                model=model_text,
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
        """列出 3D 角色模型（VRM/FBX/GLB/GLTF）。

        两个必须修好的点：

        1. **不能用 `from core.config import ...`**。打包态（PyInstaller）
           产物里只有 ``backend.core``，顶层 ``core`` 包并不存在于磁盘，
           静态导入直接 ModuleNotFoundError → 整个方法抛异常 → 前端
           ``bootstrap`` 把异常吞成空ModelList → dashboard 拿到
           ``models.first == null`` → 3D 区显示「未加载模型」。
           这正是"模型文件明明齐全却说不加载"的根因。
           现在统一走 ``_config_module()``（core / backend.core 双路兜底）。
        2. **必须递归 + 纳入 ``model_extra_dirs``**。原来只 ``iterdir()``
           一层，且只认 ``resources/models``；用户在自定义目录或子目录
           放的VRM 完全列不出来。

        另外把配置里指定的默认形象（``avatar.model``，默认「小凌.vrm」）
        排到列表首位 —— 前端 dashboard 取的是 ``models.first``，
        原来按文件名排序会选中 ``Imeris.vrm``，而不是配置指定的那一个。
        """
        try:
            from pathlib import Path
            _cfg = _config_module()
            roots = _cfg.model_roots()
            exts = ('.vrm', '.fbx', '.glb', '.gltf')

            files: list = []
            seen: set = set()
            for root in roots:
                try:
                    root = Path(root)
                    if not root.is_dir():
                        continue
                    for p in sorted(root.rglob('*')):
                        try:
                            if not p.is_file() or p.suffix.lower() not in exts:
                                continue
                            key = str(p.resolve()).lower()
                            if key in seen:
                                continue
                            seen.add(key)
                            files.append(p)
                        except Exception:
                            continue
                except Exception:
                    continue

            # 配置指定的默认形象优先，其余保持扫描顺序（稳定排序）
            default_name = ''
            try:
                default_name = str((_cfg.load().get('avatar') or {})
                                   .get('model') or '').strip()
            except Exception:
                default_name = ''
            if default_name:
                def _is_default(p):
                    return p.name == default_name or p.stem == default_name
                files.sort(key=lambda p: 0 if _is_default(p) else 1)

            out = []
            for p in files:
                try:
                    size_mb = p.stat().st_size / (1024.0 * 1024.0)
                except OSError:
                    size_mb = 0.0
                out.append(pb.ModelInfo(name=p.stem, path=str(p),
                                        size_mb=size_mb))
            return pb.ModelList(models=out)
        except Exception as e:
            logger.exception('ListModels failed')
            try:
                context.set_details(f'列出模型失败：{e}')
                context.set_code(grpc.StatusCode.INTERNAL)
            except Exception:
                pass
            return pb.ModelList()

    # ---------------- SwitchModel ----------------
    def SwitchModel(self, request, context):
        try:
            path = request.path
            from core import config as _cfg
            # 关键修复：切换形象必须写「真正被读取的那份配置」。
            # ListModels 排默认形象时读的是 avatar.model（按文件名匹配），
            # 而这里以前只写 model.path —— 没有任何地方按 model.path 选 3D
            # 形象，于是「切换成功」只是假象：重启后又回到默认形象。
            # 现在两者都写：model.path 兼容渲染器，avatar.model 让下次
            # bootstrap 的 models.first 就是用户刚选的那个。
            base = os.path.basename(path or '')
            _cfg.patch({'model': {'path': path},
                        'avatar': {'model': base}})
            r = _get_renderer()
            if r is not None:
                try: r.switch_model(path)
                except Exception as e:
                    logger.exception('Renderer switch_model failed')
                    return pb.StatusReply(ok=False, message=f'配置已写但切换失败：{e}')
            try:
                from core.activity_log import record as _log_act
                _log_act("model", f"已切换模型：{os.path.basename(path)}", path)
            except Exception:
                pass
            return pb.StatusReply(ok=True, message=f'已切换到 {os.path.basename(path)}')
        except Exception as e:                                              # noqa: BLE001
            logger.exception('SwitchModel failed')
            return pb.StatusReply(ok=False, message=str(e))

    # ---------------- ExecuteCommand ----------------
    def ExecuteCommand(self, request, context):
        cmd = (request.command or '').strip()
        try:
            if cmd.startswith('browser:'):
                return pb.CommandReply(output=_handle_browser(cmd[len('browser:'):]))
            if cmd.startswith(('plugin:', 'workflow:', 'security:', 'mcp:', 'memory:',
                               'activity:', 'kb:', 'code:', 'dsh:', 'git:', 'sensitive:')):
                # 注意 'code:' 必须在这个元组里：_handle_ext_command 有 code: 分支
                # （callers/callees/chain/context…），但此前路由元组漏了它，
                # 于是 `code:callers foo` 一路掉到 fusion.try_command，返回
                # 「未知指令」—— 代码索引模块在仓库里，只是永远接不到。
                # 'dsh:' / 'git:' 同理：dsh_compat.py / git_tool.py 早已写好，
                # 只是从没接进路由，所以整段代码是"死的"。
                return pb.CommandReply(output=_handle_ext_command(cmd))
            if cmd.startswith('channels:'):
                # 多通道开关/启停。核心模块 core/channels.py 早已写好，
                # 但 ChannelManager 从未被实例化、start_all() 零调用方 ——
                # 这一族指令把它真正接起来。
                return pb.CommandReply(output=_handle_channels_cmd(cmd.split(':', 1)[1]))
            if cmd.startswith('agent:'):
                return pb.CommandReply(output=_handle_agent(cmd))
            if cmd.startswith('settings:'):
                # 设置页的可选项 / 写入，统一走这里（返回 JSON 字符串）。
                # 这样不必为了加性别、可用性等字段去改 proto 并重新生成
                # Dart/ Python 桩代码。
                from core import options as _options
                return pb.CommandReply(output=_options.handle(cmd.split(':', 1)[1]))
            if cmd.startswith('sandbox:'):
                # 桌面端沙箱：模型商店下载、受限执行、路径/用量查询。
                # 与 settings: 同样返回 JSON，理由一致 —— 不必为此改 proto。
                return pb.CommandReply(output=_handle_sandbox(cmd.split(':', 1)[1]))
            if cmd.startswith('system:'):
                # 实时资源遥测 + 后端体检。走 ExecuteCommand+JSON，理由同上；
                # 也让工作台的 CPU/内存/磁盘不再依赖前端的 wmic/df 外部命令。
                return pb.CommandReply(output=_handle_system_cmd(cmd.split(':', 1)[1]))
            if cmd.startswith('model:'):
                # 模型实时状态：当前用的是哪个模型、有没有模型、怎么用/切模型。
                # 同样返回 JSON —— 加字段不必重新生成 Dart / Python 桩代码。
                return pb.CommandReply(output=_handle_model_cmd(cmd.split(':', 1)[1]))
            if cmd.startswith('update:'):
                # 更新检查统一入口（core/updater.py 的 UpdateChecker），
                # 取代前端 updater.dart 里并行的一整套 http+缓存+解析实现。
                return pb.CommandReply(output=_handle_update_cmd(cmd[len('update:'):]))
            if cmd.startswith('deps:'):
                return pb.CommandReply(output=_handle_deps_cmd(cmd.split(':', 1)[1]))
            if cmd.startswith('api:'):
                # 统一「外部 API 配置」：设置页 API 配置选项卡、蒸馏老师端、
                # Agent 用 API 操作应用，都走这一套（core.api_config）。
                return pb.CommandReply(output=_handle_api_cmd(cmd.split(':', 1)[1]))
            if cmd.startswith('training:'):
                # 训练元数据（trainer 真实产出）：设备 / target_modules /
                # prompt mask 口径 / 适配器体积 / 检查点 / 续训状态。
                # 同样走 ExecuteCommand+JSON，加字段不必重新生成桩代码。
                return pb.CommandReply(output=_handle_training_cmd(cmd.split(':', 1)[1]))
            if cmd.startswith('growth:'):
                # 成长页真值：关系档位定义、亲密度分数、情绪来源、按天活动量。
                # 前端 Dart 里原本写死这些（等级卡片 + 时间线日期），现在改读这里。
                return pb.CommandReply(output=_handle_growth_cmd(cmd.split(':', 1)[1]))
            engine = _get_engine()
            if engine is None:
                return pb.CommandReply(output='引擎未就绪，无法执行指令。')
            try:
                from core import fusion as _fusion
            except Exception as e:                                            # noqa: BLE001
                # 原先这里固定回一句「指令解析模块已下线，暂不支持」——
                # fusion.py 明明在仓库里，真实故障（语法错误、循环导入、
                # 依赖缺失）会被这句话完全掩盖，排查时只会以为是功能取消了。
                logger.exception('fusion import failed')
                return pb.CommandReply(
                    output=f'指令解析模块加载失败：{type(e).__name__}: {e}')
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
            eng = _get_growth_engine()
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
                eng = _get_growth_engine()
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
            pm = _get_plugin_manager()
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
        """委托给进程级单例（引擎内那份优先），与 plugin: 指令族同源。"""
        return _get_plugin_manager()

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
            # 此处原有一行死 import（core.engine.XiaoLing 未使用），已清理；
            # 引擎实例由下方 _get_engine() 统一获取。
            steps = max(1, request.steps or 100)
            lr = float(request.learning_rate or 2e-4)
            bs = max(1, request.batch_size or 4)
            rank = max(1, request.lora_rank or 8)
            ds_name = (request.dataset_name or "").strip()

            _train_state_update(active=True, step=0, total_steps=steps,
                                loss=0.0, final_loss=0.0, real=False,
                                status='准备训练...', started_at=time.time())
            eng = _get_engine()
            if eng is None:
                # 引擎不可用：绝不伪造 loss 曲线，直接返回错误事件并结束流
                err_msg = '成长引擎未加载，请先在模型商店下载并加载模型后再训练'
                _train_state_update(active=False, step=0, total_steps=steps,
                                    loss=0.0, final_loss=0.0, real=False,
                                    status=f'error: {err_msg}')
                yield pb.TrainingProgress(step=0, total_steps=0, loss=0.0,
                    status=f'error: {err_msg}')
                return

            for info in eng.train_stream(steps=steps, learning_rate=lr,
                                         batch_size=bs, lora_rank=rank,
                                         dataset_name=ds_name):
                # 引擎层 error 事件（缺基座 / 缺 torch / 空适配器）：如实终止
                if info.get("type") == "error" or info.get("kind") == "error":
                    err_msg = str(info.get("message") or info.get("status")
                                  or "训练失败")
                    _train_state_update(active=False, step=0, total_steps=steps,
                                        loss=0.0, final_loss=0.0, real=False,
                                        status=f'error: {err_msg}')
                    yield pb.TrainingProgress(step=0, total_steps=0, loss=0.0,
                        status=f'error: {err_msg}')
                    return

                s_ = int(info.get("step", 0))
                t_ = int(info.get("total_steps", steps))
                l_ = float(info.get("loss", 0.0))
                raw_status = str(info.get("status", ""))
                kind = str(info.get("kind", "progress"))
                # 不再有任何 [演练]/simulated 分支：trainer 要么真训练并报真实
                # loss，要么直接 error。事件类型如实前缀，前端按 kind 展示。
                prefix = {'init': '[准备] ', 'info': '[环境] ',
                          'eval': '[验证] ', 'done': '[完成] ',
                          # 训练前蒸馏/样本阶段（engine._growth_distill_and_rows）
                          'distill': '[蒸馏] ', 'sample': '[样本] ',
                          # 检查点/优化器落盘失败不是「训练失败」，训练还在跑，
                          # 但续训这件事已经不可靠了 —— 必须显式露出来。
                          'warning': '[告警] '}.get(kind, '')
                if prefix:
                    raw_status = prefix + raw_status
                _train_state_update(active=(s_ < t_ and kind != 'done'),
                                    step=s_, total_steps=t_, loss=l_,
                                    real=bool(info.get('real', True)),
                                    kind=kind, status=raw_status,
                                    eval_loss=info.get('eval_loss'),
                                    adapter_dir=info.get('adapter_dir'))
                yield pb.TrainingProgress(
                    step=s_, total_steps=t_, loss=l_,
                    status=raw_status)
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
            from core.model import detect_hardware, fit_models_for_hardware
            # 走 fit_models_for_hardware —— 它才是真正按「参数量 + 显存/内存
            # 需求 + 当前可用内存」算 can_run 的那一份逻辑。
            #
            # 旧实现在这里另写了一套 `size_mb/1024*1.5 <= ram` 的判断，
            # 既不看有没有 GPU、也不看显存，等于把 core.model 里已经写好的
            # 适配计算整个架空了；而且 params 字段是拿 size_mb 反推的
            # （0.5B 模型显示成 "469MB"）、context 一律硬编码 "32K"
            # （Llama 实际 128K、Gemma 实际 8K），quant 干脆不填。
            # 用户看到的「推荐」于是跟本机硬件没有真实关系。
            try:
                hw = detect_hardware()
            except Exception:                                   # noqa: BLE001
                logger.exception('ListRecommendedModels: detect_hardware failed')
                context.set_details('硬件检测失败，无法给出真实推荐')
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                return pb.RecommendedModelList()

            out = []
            for item in fit_models_for_hardware(hw):
                out.append(pb.RecommendedModel(
                    name=item["name"],
                    params=str(item.get("params") or ""),
                    quant=str(item.get("quant") or ""),
                    vram_gb=round(float(item.get("vram_need_gb") or 0.0), 1),
                    ram_gb=round(float(item.get("ram_need_gb") or 0.0), 1),
                    quality=int(item.get("score") or 0),
                    context=str(item.get("context") or ""),
                    size_mb=float(item.get("size_mb") or 0.0),
                    can_run=bool(item.get("can_run")),
                    recommended=bool(item.get("recommended")),
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
            elif r.get("cancelled"):
                # 用户取消 ≠ 失败：前端据此把任务移出下载队列且不弹错误
                try:
                    from core import model as _cm
                    _pct = float((_cm.TASKS.get(model_name) or {})
                                 .get('percent', 0.0))
                except Exception:
                    _pct = 0.0
                yield pb.DownloadProgress(
                    percent=round(_pct, 1), downloaded_mb=0.0,
                    total_mb=total_mb,
                    status='cancelled: 用户取消（进度保留，可继续下载）')
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
            try:
                _local_names = {e.get("name", "")
                                for e in store.list_all().get("local", [])}
            except Exception:
                _local_names = set()
            out = []
            for m in store.list_installed():
                # 单文件权重（如 xxx.gguf）的真实路径与 store_dir/name 不同，
                # 必须用扫描得到的 path，否则前端拿到的路径不存在。
                b = float(m.get("bytes", 0) or 0)
                out.append(pb.ModelInfo(
                    name=m.get("name", ""),
                    path=str(m.get("path") or store.store_dir / m.get("name", "")),
                    size_mb=round(b / (1024.0 * 1024.0), 1),
                    # 商城条目也会与本地登记重名：本地登记优先标记为 local
                    source='local' if m.get("name") in _local_names else 'store',
                ))
            return pb.ModelList(models=out)
        except Exception as e:
            logger.exception('ListInstalledModels failed')
            context.set_details(f'列出已安装模型失败：{e}')
            context.set_code(grpc.StatusCode.INTERNAL)
            return pb.ModelList()

    # ---------------- DeleteModel ----------------
    def DeleteModel(self, request, context):
        """下线模型。

        **红线**：绝不删除文件。这里调用 ModelStore.delete()，把权重移入
        D:\\待处理 隔离区并写入桌面清单，等待人工复核。
        """
        try:
            from core.model import ModelStore
            store = ModelStore()
            if store.delete(request.name):
                return pb.StatusReply(
                    ok=True,
                    message=f'已移入待处理区（未删除）：{request.name}')
            # 也可能是本地登记项 / API 端点
            r = store.unregister(request.name)
            if r.get("ok"):
                return pb.StatusReply(
                    ok=True, message=f'已取消登记（磁盘文件未动）：{request.name}')
            return pb.StatusReply(ok=False, message='未找到该模型')
        except Exception as e:
            logger.exception('DeleteModel failed: %s', request.name)
            return pb.StatusReply(ok=False, message=str(e))

    # ---------------- CancelDownload ----------------
    def CancelDownload(self, request, context):
        """取消正在下载的模型。

        取消 ≠ 删除：.part 临时文件保留，下次点下载自动 Range 续传。
        request.purge=True 时再把 .part 移入待处理隔离区（绝不直接删除，
        与全项目"绝不删除文件"红线一致），由人工复核后处理。
        """
        try:
            from core import model as _m
            ok = _m.request_cancel_download(request.name)
            if not ok:
                return pb.StatusReply(
                    ok=False, message=f'当前没有正在进行的下载：{request.name}')
            msg = f'已请求取消：{request.name}（进度保留，可继续下载）'
            if request.purge:
                # 等下载线程退出（最多 8 秒），再把 .part 移入待处理区
                import time as _time
                from core.model import ModelStore
                store = ModelStore()
                for _ in range(16):
                    st = (_m.TASKS.get(request.name) or {}).get('status', '')
                    if st in ('cancelled', 'error', 'done'):
                        break
                    _time.sleep(0.5)
                dest = store.store_dir / request.name
                moved, failed = 0, 0
                if dest.is_dir():
                    from core.quarantine import move_to_pending
                    for part in dest.glob('*.part'):
                        r = move_to_pending(part, reason='取消下载并清理',
                                            category='model')
                        if r.get('ok'):
                            moved += 1
                        else:
                            failed += 1
                msg += f'；已清理 {moved} 个分片临时文件'
                if failed:
                    msg += f'（{failed} 个被占用，稍后可重试）'
            return pb.StatusReply(ok=True, message=msg)
        except Exception as e:
            logger.exception('CancelDownload failed: %s', request.name)
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
            rate = (request.rate or '').strip() or '+0%'
            # 音量（BUG-C 修复）：edge-tts 的 Communicate 本身支持 volume，
            # 但此前这里只传了 rate，导致程序内音量滑块永远无效（只能靠系统音量）。
            # 优先用前端 ReadRequest 传来的 volume；缺失时回落到配置 tts.volume。
            volume = (getattr(request, 'volume', '') or '').strip() or ''
            try:
                from core import config as _cfg
                _c = _cfg.load()
                voice = str((_c.get('voice') or {}).get('id') or voice)
                if not volume:
                    # 配置里的 volume 是 0..1 的浮点（前端滑块语义），
                    # 映射到 edge-tts 的 "-100%..+100%" 百分比字符串。
                    _raw = (  _c.get('tts') or {}).get('volume')
                    if isinstance(_raw, (int, float)):
                        pct = int(round((float(_raw) * 2.0 - 1.0) * 100.0))
                        pct = max(-100, min(100, pct))
                        volume = '%+d%%' % pct
            except Exception:
                pass
            if not volume:
                volume = '+0%'
            result = TTS().synth(text, voice=voice, rate=rate, volume=volume)
            data = bytes(getattr(result, 'data', b'') or b'')
            if not data:
                # 把真实原因写进日志：edge-tts 与服务端之间的失败（如 403
                # 令牌被拒）原来只报「no audio」，排障全靠猜；现在 error 明文落盘。
                logger.warning('ReadAloud: TTS produced no audio (voice=%s): %s',
                               voice, getattr(result, 'error', '') or 'unknown')
            else:
                chunk_size = 4096
                for i in range(0, len(data), chunk_size):
                    yield pb.AudioChunk(data=data[i:i + chunk_size])
        except Exception as e:
            logger.exception('ReadAloud failed')
        finally:
            yield pb.AudioChunk(done=True)

    # ---------------- Transcribe（音频转文字） ----------------
    def Transcribe(self, request, context):
        t0 = time.time()
        try:
            from core.multimodal import ASR
            asr = ASR(language=(request.lang or 'zh').strip() or 'zh')
            if not asr.available():
                return pb.TranscribeReply(
                    ok=False, error=asr.last_error or '语音识别未配置（whisper 未安装）',
                    duration_ms=int((time.time() - t0) * 1000))
            if request.audio:
                text = asr.transcribe_bytes(bytes(request.audio))
                recorded = False
            else:
                seconds = float(request.seconds or 5)
                text = asr.listen(seconds=max(1.0, min(30.0, seconds)))
                recorded = True
            err = '' if text else (asr.last_error or '未识别到语音内容')
            return pb.TranscribeReply(
                ok=bool(text), text=text, error=err, recorded=recorded,
                duration_ms=int((time.time() - t0) * 1000))
        except Exception as e:
            logger.exception('Transcribe failed')
            return pb.TranscribeReply(
                ok=False, error=f'语音识别失败：{type(e).__name__}: {e}',
                duration_ms=int((time.time() - t0) * 1000))

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
            # 以前 engine 为 None（启动时人格引擎构造失败）也会返回
            # ok=True「人格画像已重置」——什么都没做却报成功。
            if engine is None:
                return pb.StatusReply(ok=False, message='引擎未就绪，无法重置人格')
            if getattr(engine, 'persona', None) is None:
                return pb.StatusReply(ok=False, message='人格引擎不可用，未做任何改动')
            engine.reset_persona()
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
            # 落盘由 mark_done 内部的 _notify 触发；以前这里直接改 r['done']
            # 再调 flush()，但 flush 只在 _dirty 时写盘，于是「完成」只活在内存里。
            hit = pro.mark_done(float(request.due_at))
            if not hit:
                return pb.StatusReply(ok=False, message='未找到该提醒')
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
def serve(port: int = 50051, ready_event=None):
    """启动 gRPC 后端并阻塞到退出。

    ``ready_event``：绑定**成功**后置位（失败时置位并写 ``_RUNNING_PORTS
    ['error']``）。调用方（main.py）据此决定打印「已启动」还是「启动失败」，
    不再出现「线程刚 spawn 就宣布已启动」这种把愿望当事实的日志。

    实测：端口被占时 ``add_insecure_port`` 直接抛 RuntimeError（不是返回 0），
    所以这里必须自己 catch，否则异常只会消失在后台线程里。
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb_grpc.add_XiaoLingServicer_to_server(XiaoLingServicer(), server)
    try:
        bound = server.add_insecure_port(f'[::]:{port}')
    except Exception as e:                                      # noqa: BLE001
        msg = f'{type(e).__name__}: {e}'
        _RUNNING_PORTS['error'] = msg
        _RUNNING_PORTS['grpc'] = 0
        logger.error('gRPC 端口 %s 绑定失败：%s', port, msg)
        print(f'  [gRPC] 启动失败：端口 {port} 无法绑定 —— {msg}')
        print('  [gRPC] 多半是上一次的 backend 没退干净还占着端口；'
              '关掉旧进程再启动，或换一个 --port。')
        if ready_event is not None:
            try:
                ready_event.set()
            except Exception:
                pass
        raise
    if bound == 0:
        # 某些版本/平台下不抛异常而是回 0，表示一个端口都没绑上。
        _RUNNING_PORTS['error'] = f'端口 {port} 绑定返回 0'
        _RUNNING_PORTS['grpc'] = 0
        if ready_event is not None:
            try:
                ready_event.set()
            except Exception:
                pass
        raise RuntimeError(f'gRPC 无法绑定端口 {port}')
    if bound != port:
        logger.warning('gRPC bound to unexpected port: %s (requested %s)',
                       bound, port)
    server.start()
    # 到这里才是真的 listen 上了。记录**实际**端口（bound），不是请求值。
    _RUNNING_PORTS['grpc'] = int(bound)
    _RUNNING_PORTS.pop('error', None)
    if ready_event is not None:
        try:
            ready_event.set()
        except Exception:                                       # noqa: BLE001
            pass
    logger.info('XiaoLing gRPC backend started on localhost:%s', bound)
    print(f'  [gRPC] 小凌后端已启动：localhost:{bound}')
    print(f'  [gRPC] 等待 Flutter 前端连接…')
    try:
        from core.activity_log import record as _log_act
        _log_act("system", "后端服务已启动", f"gRPC 监听 localhost:{bound}")
    except Exception:
        pass
    # 已启用通道自启：此前 start_enabled() 只有 channels:set/start 两个
    # 调用点，前端从不发、后端启动时也不调 —— 重启后所有通道静默停摆，
    # 用户看到的就是「多平台连接没反应」。服务就绪后自动拉一次。
    try:
        _get_channel_manager().start_enabled()
    except Exception as _e:                                          # noqa: BLE001
        logger.warning('通道自启失败（不影响主服务）：%s', _e)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info('gRPC server interrupted, shutting down gracefully')
    finally:
        try:
            from core.activity_log import record as _log_act
            _log_act("system", "后端服务已关闭", "gRPC server stopped")
        except Exception:
            pass
        _RUNNING_PORTS['grpc'] = 0
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
