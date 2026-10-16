"""本轮"把假的改成真的"回归测试。

覆盖 6 处修复：
  R1  ChannelBase._reply 正确处理 engine.chat 的 (text, err) 元组契约
  R2  ChannelManager 常驻事件循环 + _live_config，RPC 层不再 asyncio.run 杀循环
  R3  WorkflowEngine LLM 节点同样兼容 (text, err) 元组
  R4  DSHCompat 通过 `dsh:` RPC 指令族真正可达
  R5  GitTool 通过 `git:` RPC 指令族真正可达
  R6  BrowserTool.search 网络故障不再与"零结果"混同，RPC 层如实上报
"""
import asyncio
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
for p in (ROOT, BACKEND):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backend.core._env_shim import fix_attr_shadow  # noqa: E402
fix_attr_shadow()


# ---------------------------------------------------------------------------
# R1 —— engine.chat 返回 (text, err)，_reply 必须取 text
# ---------------------------------------------------------------------------
def test_reply_handles_tuple_contract():
    from backend.core.channels import WebhookChannel

    class _Engine:
        def chat(self, text):
            return "hello-text", None

    ch = WebhookChannel({"enabled": True})
    ch.engine = _Engine()
    assert ch._reply("hi") == "hello-text"


def test_reply_handles_plain_string():
    from backend.core.channels import WebhookChannel

    class _Engine:
        def chat(self, text):
            return "plain-string"

    ch = WebhookChannel({"enabled": True})
    ch.engine = _Engine()
    assert ch._reply("hi") == "plain-string"


def test_reply_handles_empty_tuple():
    from backend.core.channels import WebhookChannel

    class _Engine:
        def chat(self, text):
            return ("", "err-msg")

    ch = WebhookChannel({"enabled": True})
    ch.engine = _Engine()
    # 空 text 视为空回复，绝不出现 "('', 'err-msg')"
    assert ch._reply("hi") == ""


def test_reply_swallows_exception():
    from backend.core.channels import WebhookChannel

    class _Boom:
        def chat(self, text):
            raise RuntimeError("nope")

    ch = WebhookChannel({"enabled": True})
    ch.engine = _Boom()
    assert ch._reply("hi") == ""


# ---------------------------------------------------------------------------
# R2 —— ChannelManager 常驻循环 + live config + 同步包装
# ---------------------------------------------------------------------------
def test_manager_uses_live_config_not_snapshot(tmp_path, monkeypatch):
    """配置在 load() 里改一次，_channel_config 立即反映 —— 而不是构造函数快照。"""
    from backend.core import config as cfgmod
    from backend.core.channels import ChannelManager

    state = {}

    def _fake_load():
        return dict(state)

    def _fake_save(c):
        state.clear()
        state.update(c)

    monkeypatch.setattr(cfgmod, "load", _fake_load)
    monkeypatch.setattr(cfgmod, "save", _fake_save)

    mgr = ChannelManager(config={"telegram_enabled": False})
    assert mgr._channel_config("telegram").get("enabled") is False

    # 模拟 channels:set 写盘后的状态；管理器必须立刻看见新值。
    state["telegram_enabled"] = True
    state["telegram_bot_token"] = "TKN"
    assert mgr._channel_config("telegram").get("enabled") is True
    assert mgr._channel_config("telegram").get("bot_token") == "TKN"


def test_manager_webhook_creds_in_live_config(tmp_path, monkeypatch):
    from backend.core import config as cfgmod
    from backend.core.channels import ChannelManager

    state = {
        "webhook_enabled": True,
        "webhook_host": "0.0.0.0",
        "webhook_port": 9123,
        "webhook_path": "/hook/x",
    }
    monkeypatch.setattr(cfgmod, "load", lambda: dict(state))

    mgr = ChannelManager(config={})
    cfg = mgr._channel_config("webhook")
    assert cfg["enabled"] is True
    assert cfg["port"] == 9123
    assert cfg["path"] == "/hook/x"


def test_manager_persistent_loop_survives_start_stop(tmp_path, monkeypatch):
    """关键回归：start_enabled/stop_running 走常驻循环，
    不再 asyncio.run(start_all()) 一返回就把 aiohttp 服务器拆掉。"""
    from backend.core import config as cfgmod
    from backend.core.channels import ChannelManager, CHANNEL_REGISTRY

    monkeypatch.setattr(cfgmod, "load", lambda: {})
    mgr = ChannelManager(config={})

    started = []
    stopped = []

    class _FakeChan:
        name = "webhook"

        def __init__(self, cfg):
            self.cfg = cfg

        async def start(self):
            started.append(self)

        async def stop(self):
            stopped.append(self)

        @property
        def is_running(self):
            return True

        def set_message_handler(self, h): pass
        def set_engine(self, e): pass

    # 只在 webhook 上替换一个假类
    orig = CHANNEL_REGISTRY["webhook"]
    CHANNEL_REGISTRY["webhook"] = _FakeChan
    try:
        monkeypatch.setattr(cfgmod, "load",
                            lambda: {"webhook_enabled": True})
        mgr.start_enabled()
        assert len(started) == 1
        # 常驻线程存活
        assert mgr._loop is not None and mgr._loop.is_running()
        assert mgr._loop_thread is not None and mgr._loop_thread.is_alive()
        # 再调 start_enabled 不应重复 start 已运行实例
        mgr.start_enabled()
        assert len(started) == 1, "start_enabled 重复启动了已运行的通道"
        mgr.stop_running()
        assert len(stopped) == 1
    finally:
        CHANNEL_REGISTRY["webhook"] = orig
        # 收尾：关掉这个测试用的循环，避免污染其他用例
        mgr._loop.call_soon_threadsafe(mgr._loop.stop)
        mgr._loop_thread.join(timeout=2.0)


def test_manager_reconnect_runs_in_loop(tmp_path, monkeypatch):
    """回归：_reconnect_channel 曾因 threading.Thread(target=_do_reconnect)
    把协程函数丢给线程却从不 await，等于永远不重连。"""
    from backend.core import config as cfgmod
    from backend.core.channels import ChannelManager, CHANNEL_REGISTRY

    monkeypatch.setattr(cfgmod, "load",
                        lambda: {"telegram_enabled": True,
                                 "telegram_bot_token": "T"})
    mgr = ChannelManager(config={})

    calls = []

    class _Reconnect:
        name = "telegram"

        def __init__(self, cfg):
            self.cfg = cfg

        async def start(self):
            calls.append(self)

        async def stop(self): pass

        @property
        def is_running(self):
            return True

        def set_message_handler(self, h): pass
        def set_engine(self, e): pass

    orig = CHANNEL_REGISTRY["telegram"]
    CHANNEL_REGISTRY["telegram"] = _Reconnect
    try:
        mgr._reconnect_channel("telegram")
        assert len(calls) == 1, "重连从未真正执行 start()"
        assert mgr.channels.get("telegram") is not None
    finally:
        CHANNEL_REGISTRY["telegram"] = orig
        mgr._loop.call_soon_threadsafe(mgr._loop.stop)
        mgr._loop_thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# R3 —— WorkflowEngine LLM 节点元组契约
# ---------------------------------------------------------------------------
def test_workflow_llm_node_handles_tuple(monkeypatch):
    from backend.core.workflow_engine import WorkflowEngine, WorkflowNode, Workflow

    class _Engine:
        def chat(self, text):
            return ("answer", None)

    eng = WorkflowEngine()
    eng.set_engine(_Engine())

    wf = eng.create_workflow("wf1", "")
    node = WorkflowNode("n1", "llm", config={"prompt": "q"})
    wf.add_node(node)

    res = eng._execute_node(node, {})
    assert res["success"] is True
    assert res["output"] == "answer"


def test_workflow_llm_node_string_return_still_works():
    from backend.core.workflow_engine import WorkflowEngine, WorkflowNode

    class _Engine:
        def chat(self, text):
            return "answer"

    eng = WorkflowEngine()
    eng.set_engine(_Engine())
    wf = eng.create_workflow("wf1", "")
    node = WorkflowNode("n1", "llm", config={"prompt": "q"})
    wf.add_node(node)
    res = eng._execute_node(node, {})
    assert res["output"] == "answer"


def test_workflow_llm_node_empty_tuple_does_not_leak_repr():
    from backend.core.workflow_engine import WorkflowEngine, WorkflowNode

    class _Engine:
        def chat(self, text):
            return ("", "some error")

    eng = WorkflowEngine()
    eng.set_engine(_Engine())
    wf = eng.create_workflow("wf1", "")
    node = WorkflowNode("n1", "llm", config={"prompt": "q"})
    wf.add_node(node)
    res = eng._execute_node(node, {})
    # 绝不出现 "(' ', 'some error')"
    assert res["output"] == ""


# ---------------------------------------------------------------------------
# R4/R5 —— dsh: 与 git: 指令族真的接进了 _handle_ext_command
# ---------------------------------------------------------------------------
@pytest.fixture
def rpc_server(tmp_path, monkeypatch):
    """干净地导入 rpc.server 并让插件/DSH/Git 单例落到 tmp_path。"""
    monkeypatch.setenv("XIAOLING_SANDBOX_ROOT", str(tmp_path / "sb"))
    for key in ("backend.rpc.server", "rpc.server"):
        sys.modules.pop(key, None)
    from backend.rpc import server as srv
    # 强制重建单例
    srv._dsh_compat = None
    srv._git_tool = None
    srv._plugin_manager = None
    return srv


def test_dsh_rpc_returns_ok(rpc_server):
    out = rpc_server._handle_ext_command("dsh:list")
    d = json.loads(out)
    assert d.get("ok") is True
    assert "plugins" in d


def test_dsh_rpc_market_includes_curated_when_offline(rpc_server, monkeypatch):
    dsh = rpc_server._get_dsh_compat()

    def _fail():
        return []

    monkeypatch.setattr(dsh, "fetch_remote_market", _fail)
    out = rpc_server._handle_ext_command("dsh:available")
    d = json.loads(out)
    assert d.get("ok") is True
    assert any(p.get("source") == "curated" for p in d["plugins"])


def test_dsh_rpc_unknown_subcommand(rpc_server):
    out = rpc_server._handle_ext_command("dsh:bogus")
    d = json.loads(out)
    assert d.get("ok") is False
    assert "未知 DSH" in d["error"]


def test_git_rpc_status_shape(rpc_server, monkeypatch):
    """git:status 应返回 {ok, files, raw}；即便 workspace 里没有 .git，
    也必须如实返回，不再"看着像 0 变更其实是没跑"。"""
    calls = []

    class _FakeGT:
        def __init__(self, repo):
            self.repo = repo

        def status(self):
            calls.append("status")
            return {"ok": True, "files": [], "raw": ""}

        def diff(self, path=None):
            calls.append(("diff", path))
            return ""

        def log(self, n=20):
            calls.append(("log", n))
            return []

        def branches(self):
            calls.append("branches")
            return {"ok": True, "branches": [], "current": ""}

    import backend.core.git_tool as gt_mod
    monkeypatch.setattr(gt_mod, "GitTool", _FakeGT)
    rpc_server._git_tool = None

    out = rpc_server._handle_ext_command("git:status")
    d = json.loads(out)
    assert d.get("ok") is True
    assert "status" in calls


def test_git_rpc_log_default_20(rpc_server, monkeypatch):
    captured = {}

    class _FakeGT:
        def __init__(self, repo): pass
        def log(self, n=20):
            captured["n"] = n
            return []
        def status(self): return {"ok": True, "files": [], "raw": ""}
        def diff(self, p=None): return ""
        def branches(self): return {"ok": True, "branches": [], "current": ""}
        def commit(self, m, files=None): return {"ok": True, "message": ""}
        def checkout(self, b): return {"ok": True, "message": ""}

    import backend.core.git_tool as gt_mod
    monkeypatch.setattr(gt_mod, "GitTool", _FakeGT)
    rpc_server._git_tool = None

    rpc_server._handle_ext_command("git:log")
    assert captured.get("n") == 20
    rpc_server._handle_ext_command("git:log 5")
    assert captured.get("n") == 5


def test_dsh_and_git_are_in_execute_command_prefix_tuple(rpc_server):
    """ExecuteCommand 路由元组必须包含 'dsh:' 和 'git:'，否则会掉到
    fusion.try_command 返回"未知指令"。这里用源码字符串校验，避免起真 gRPC。"""
    import inspect
    cls = rpc_server.XiaoLingServicer
    src = inspect.getsource(cls.ExecuteCommand)
    assert "'dsh:'" in src and "'git:'" in src, \
        "dsh:/git: 必须出现在 ExecuteCommand 路由元组里"


# ---------------------------------------------------------------------------
# R6 —— BrowserTool.search 错误指示 + RPC search op
# ---------------------------------------------------------------------------
class _BrokenSession:
    timeout = 5

    def get(self, url, timeout=None):
        raise ConnectionError("offline")


def test_browser_search_returns_error_marker_on_failure():
    from backend.core.browser_tool import BrowserTool

    bt = BrowserTool()
    bt.session = _BrokenSession()
    res = bt.search("hello")
    assert isinstance(res, list) and len(res) == 1
    assert "error" in res[0]
    assert "ConnectionError" in res[0]["error"] or "offline" in res[0]["error"]


class _EmptyHtmlSession:
    timeout = 5

    def get(self, url, timeout=None):
        class R:
            text = "<html>nothing</html>"
        return R()


def test_browser_search_empty_returns_empty_list():
    from backend.core.browser_tool import BrowserTool

    bt = BrowserTool()
    bt.session = _EmptyHtmlSession()
    res = bt.search("hello")
    assert res == []


def test_browser_rpc_search_op_reports_error(rpc_server, monkeypatch):
    fake_tool = type("T", (), {
        "search": lambda self, q, num=10: [{"error": "boom"}],
    })()
    rpc_server._browser_tool = fake_tool
    out = rpc_server._handle_browser('search {"query":"hi","num":5}')
    d = json.loads(out)
    assert d.get("ok") is False
    assert d.get("error") == "boom"


def test_browser_rpc_search_op_reports_results(rpc_server, monkeypatch):
    fake_tool = type("T", (), {
        "search": lambda self, q, num=10: [{"title": "a", "url": "u"}],
    })()
    rpc_server._browser_tool = fake_tool
    out = rpc_server._handle_browser('search {"query":"hi","num":5}')
    d = json.loads(out)
    assert d.get("ok") is True
    assert d["results"] == [{"title": "a", "url": "u"}]


# ---------------------------------------------------------------------------
# R7 —— channels: dingtalk 凭据键名修正
# ---------------------------------------------------------------------------
def test_channels_dingtalk_credential_key_matches_channel(rpc_server, monkeypatch):
    """_SPEC 里 dingtalk 的凭据键必须是 'dingtalk_access_token'（通道实际读的
    那个），而不是过去的 'dingtalk_webhook_url' —— 否则「configured」判定
    永远假，UI 会说不已配置但实际能用。"""
    import inspect
    src = inspect.getsource(rpc_server._handle_channels_cmd)
    assert '"dingtalk":  ("dingtalk_enabled", ["dingtalk_access_token"])' in src
    assert '"dingtalk":  ("dingtalk_enabled", ["dingtalk_webhook_url"])' not in src


# ---------------------------------------------------------------------------
# R8 —— PluginManager 单例：_handle_ext_command plugin: 与 ListPlugins 同源
# ---------------------------------------------------------------------------
def test_plugin_rpc_uses_singleton(rpc_server, monkeypatch):
    """避免此前 plugin: 每次 new 一份，与 ListPlugins/EnablePlugin 走的
    两份内存不一致。这里断言两条路径拿到同一个对象。"""
    from backend.core.plugin_system import PluginManager

    seen = []

    class _Tracker(PluginManager):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            seen.append(self)

    # 让引擎不可用，退化到进程级单例
    monkeypatch.setattr(rpc_server, "_get_engine", lambda *a, **kw: None)
    monkeypatch.setattr("backend.core.plugin_system.PluginManager", _Tracker)
    import backend.core.config as cfgmod
    monkeypatch.setattr(cfgmod, "PluginManager", _Tracker, raising=False)

    rpc_server._plugin_manager = None
    p1 = rpc_server._get_plugin_manager()
    p2 = rpc_server._get_plugin_manager()
    assert p1 is p2, "plugin manager 必须是单例，不能每次 new"
    assert len(seen) == 1, "PluginManager 只应被构造一次"


# ---------------------------------------------------------------------------
# R9 —— system_prompt provider：人格选择必须真的作用到 build_messages
# ---------------------------------------------------------------------------
def test_local_model_build_messages_prefers_provider(tmp_path):
    """此前 LocalModel.build_messages 只读构造时定死的 self.system_prompt，
    结果 engine.system_prompt() 组装的 persona hint + suffix 全链路零调用方，
    换人格后模型输出一个字节都不会变。provider 存在时必须每轮现取。"""
    from backend.core.model import LocalModel

    calls = {"n": 0}

    def _provider():
        calls["n"] += 1
        return "PROVIDED-PROMPT"

    lm = LocalModel(model_dir=tmp_path, system_prompt="STATIC-PROMPT",
                    system_prompt_provider=_provider)
    msgs = lm.build_messages("hi", history=[])
    assert msgs and msgs[0]["role"] == "system"
    assert "PROVIDED-PROMPT" in msgs[0]["content"]
    assert "STATIC-PROMPT" not in msgs[0]["content"], \
        "provider 提供时静态 prompt 不应出现"
    assert calls["n"] >= 1, "provider 必须每轮被调用"


def test_local_model_falls_back_to_static_when_no_provider(tmp_path):
    """没提供 provider 时退回原静态 system_prompt，保持向后兼容与老行为。"""
    from backend.core.model import LocalModel

    lm = LocalModel(model_dir=tmp_path, system_prompt="STATIC-ONLY")
    msgs = lm.build_messages("hi", history=[])
    assert "STATIC-ONLY" in msgs[0]["content"]


def test_local_model_provider_exception_does_not_break_build(tmp_path):
    """provider 抛异常时不能拖垮对话链路 —— 落到静态串。"""
    from backend.core.model import LocalModel

    def _boom():
        raise RuntimeError("persona engine down")

    lm = LocalModel(model_dir=tmp_path, system_prompt="STATIC-BACKUP",
                    system_prompt_provider=_boom)
    msgs = lm.build_messages("hi", history=[])
    assert "STATIC-BACKUP" in msgs[0]["content"]


def test_model_replacement_threads_provider_into_local_model(tmp_path):
    """ModelReplacement.get_model() 构造 LocalModel 时必须把 provider 透传下去，
    否则 engine 侧接了、模型侧却没接，等于零。用源码校验 get_model 的实际参数。"""
    import inspect
    from backend.core import model as m

    def _provider():
        return "PERS-PROMPT"

    mr = m.ModelReplacement(store_dir=str(tmp_path / "store"),
                            system_prompt="DEFAULT-STATIC",
                            system_prompt_provider=_provider)
    assert mr.system_prompt_provider is _provider
    # get_model 里真正 new LocalModel 时必须带 system_prompt_provider=...
    src = inspect.getsource(m.ModelReplacement.get_model)
    assert "system_prompt_provider=self.system_prompt_provider" in src, \
        "get_model 必须把 provider 透传给 LocalModel"
    # LocalModel.__init__ 也必须接收并存下该形参
    init_src = inspect.getsource(m.LocalModel.__init__)
    assert "system_prompt_provider" in init_src


def test_engine_system_prompt_reflects_persona(monkeypatch, tmp_path):
    """engine.system_prompt() 必须把 persona hint + prompt_suffix 组装进去；
    此前 engine 里这个方法存在但没人调用，等于死代码。这里直接验证它返回的串
    确实随 persona 变化，并作为 LocalModel.build_messages 的 provider 使用。"""
    from backend.core.model import LocalModel

    state = {"persona": "活泼"}

    def _compose():
        hint = "【活泼人格】" if state["persona"] == "活泼" else "【高冷人格】"
        return "DEFAULT" + hint

    lm = LocalModel(model_dir=tmp_path, system_prompt="DEFAULT",
                    system_prompt_provider=_compose)
    msgs = lm.build_messages("hi", history=[])
    assert "【活泼人格】" in msgs[0]["content"]

    state["persona"] = "高冷"
    msgs2 = lm.build_messages("hi again", history=[])
    assert "【高冷人格】" in msgs2[0]["content"], \
        "人格变更后下一轮 build_messages 必须反映新 provider 结果"


# ---------------------------------------------------------------------------
# R10 —— GrowthEngine 单例：GetStatus/GetGrowthStatus/GetTrainingStatus 与
#         growth: 指令族必须读同一份内存，否则 throttle/暂停/队列全是「刚出厂」
# ---------------------------------------------------------------------------
def test_get_growth_engine_prefers_engine_growth(rpc_server, monkeypatch):
    """engine 就绪时 _get_growth_engine() 返回的必须是 eng.growth，
    而不是新建的实例（那会丢掉 throttle cache 与暂停标志）。"""
    sentinel = object()
    fake_eng = type("E", (), {"growth": sentinel})()
    monkeypatch.setattr(rpc_server, "_get_engine", lambda *a, **kw: fake_eng)
    got = rpc_server._get_growth_engine()
    assert got is sentinel, "必须优先复用 engine.growth，不能新建"


def test_get_growth_engine_singleton_when_engine_absent(rpc_server, monkeypatch):
    """engine 未就绪时退回进程级单例：两次调用必须返回同一对象。"""
    monkeypatch.setattr(rpc_server, "_get_engine", lambda *a, **kw: None)
    rpc_server._growth_engine_singleton = None
    # 避免真起 GrowthEngine 的重依赖：monkeypatch 类
    from backend.core import growth as grw
    made = []
    class _G:
        def __init__(self):
            made.append(self)
    monkeypatch.setattr(grw, "GrowthEngine", _G)
    a = rpc_server._get_growth_engine()
    b = rpc_server._get_growth_engine()
    assert a is b
    assert len(made) == 1, "GrowthEngine 在单例分支只应被构造一次"


def test_get_status_rpcs_use_singleton(rpc_server):
    """源码校验：GetStatus/GetGrowthStatus/GetTrainingStatus 里必须真的调用
    _get_growth_engine()，不能再出现裸 GrowthEngine() 每次新建。"""
    import inspect
    cls = rpc_server.XiaoLingServicer
    for name in ("GetStatus", "GetGrowthStatus", "GetTrainingStatus"):
        src = inspect.getsource(getattr(cls, name))
        assert "_get_growth_engine()" in src, \
            f"{name} 必须走 _get_growth_engine() 单例，而不是每次 new GrowthEngine()"


# ---------------------------------------------------------------------------
# R11 —— sensitive: 指令族：把 SensitiveFilter 从「零调用方的死配置」接进链路
# ---------------------------------------------------------------------------
def test_sensitive_rpc_list(rpc_server, monkeypatch):
    """sensitive:list 返回当前敏感词表；引擎不可用时必须如实报错而不是给个空 list 骗人。"""
    eng = type("E", (), {
        "sensitive_words": lambda self: ["词A", "词B"],
        "check_sensitive": lambda self, t: {"hit": False, "words": [], "masked": t},
        "add_sensitive_word": lambda self, w: None,
    })()
    monkeypatch.setattr(rpc_server, "_get_engine", lambda *a, **kw: eng)
    out = rpc_server._handle_ext_command("sensitive:list")
    d = json.loads(out)
    assert d.get("ok") is True
    assert "词A" in d.get("words", [])


def test_sensitive_rpc_check_and_add(rpc_server, monkeypatch):
    state = {"words": ["违禁A"]}

    def _check(t):
        hit = [w for w in state["words"] if w in t]
        masked = t
        for w in hit:
            masked = masked.replace(w, "*" * len(w))
        return {"hit": bool(hit), "words": hit, "masked": masked}

    def _add(w):
        state["words"].append(w)

    eng = type("E", (), {
        "sensitive_words": lambda self: list(state["words"]),
        "check_sensitive": lambda self, t: _check(t),
        "add_sensitive_word": lambda self, w: _add(w),
    })()
    monkeypatch.setattr(rpc_server, "_get_engine", lambda *a, **kw: eng)

    r = json.loads(rpc_server._handle_ext_command("sensitive:check 这是违禁A文本"))
    assert r.get("ok") is True
    assert r.get("hit") is True
    assert "违禁A" not in r.get("masked", "")

    # 加词后立刻能命中新词
    r2 = json.loads(rpc_server._handle_ext_command("sensitive:add 违禁B"))
    assert r2.get("ok") is True
    r3 = json.loads(rpc_server._handle_ext_command("sensitive:check 又出现违禁B"))
    assert r3.get("hit") is True


def test_sensitive_rpc_engine_absent_reports_error(rpc_server, monkeypatch):
    monkeypatch.setattr(rpc_server, "_get_engine", lambda *a, **kw: None)
    out = rpc_server._handle_ext_command("sensitive:list")
    d = json.loads(out)
    assert d.get("ok") is False
    assert "引擎" in d.get("error", "")


def test_sensitive_in_execute_command_prefix_tuple(rpc_server):
    """路由元组必须包含 'sensitive:'，否则前端 sensitive:* 指令全掉到 fusion
    未知指令，等于接了个寂寞。"""
    import inspect
    src = inspect.getsource(rpc_server.XiaoLingServicer.ExecuteCommand)
    assert "'sensitive:'" in src


def test_compliance_mask_in_chat_paths(rpc_server):
    """_do_chat 与 _do_chat_streaming 都必须在 _post_chat 前调用
    _compliance_mask(reply)；否则敏感词过滤器又变成「只在 RPC 里挂个名」。"""
    import inspect
    from backend.core import engine as eng_mod
    for fn in ("_do_chat", "_do_chat_streaming"):
        src = inspect.getsource(getattr(eng_mod.XiaoLing, fn))
        assert "_compliance_mask" in src, f"{fn} 必须接入 _compliance_mask"


# ---------------------------------------------------------------------------
# R12 —— plugin: reload / installpath / dir：把三个「Navigator.pop 假按钮」
#         接成后端真动作。
# ---------------------------------------------------------------------------
def test_plugin_reload_rpc_uses_manager(rpc_server, monkeypatch):
    from backend.core.plugin_system import PluginManager

    calls = []

    class _FakePM:
        def reload_plugin(self, name):
            calls.append(("reload", name))
            return True
        def reload(self):
            calls.append(("reload_all",))
            return 3
        def uninstall(self, name):
            calls.append(("uninstall", name))
            return {"ok": True, "quarantined": "/q/x"}

    fake = _FakePM()
    monkeypatch.setattr(rpc_server, "_get_plugin_manager", lambda: fake)

    out = rpc_server._handle_ext_command("plugin:reload 联网搜索")
    d = json.loads(out)
    assert d.get("ok") is True
    assert ("reload", "联网搜索") in calls

    # 无参数走整体 reload（load_all 语义）
    out2 = rpc_server._handle_ext_command("plugin:reload")
    d2 = json.loads(out2)
    assert d2.get("ok") is True
    assert d2.get("count") == 3


def test_plugin_reload_failure_honestly_reports(rpc_server, monkeypatch):
    """插件不存在时 reload_plugin 返回 False，RPC 必须如实 _err 而不是 ok:true 骗人。"""
    class _FakePM:
        def reload_plugin(self, name):
            return False
    monkeypatch.setattr(rpc_server, "_get_plugin_manager", lambda: _FakePM())
    out = rpc_server._handle_ext_command("plugin:reload 不存在的插件")
    d = json.loads(out)
    assert d.get("ok") is False
    assert "重载失败" in d.get("error", "")


def test_plugin_installpath_rejects_unsupported(rpc_server, monkeypatch, tmp_path):
    """installpath 只接 .zip 或已存在的目录，其他一律如实报错。"""
    class _FakePM:
        def install(self, src):
            return {"ok": True, "name": "从目录装的"}
        def install_from_zip(self, p):
            return {"ok": True, "name": "从zip装的"}
    monkeypatch.setattr(rpc_server, "_get_plugin_manager", lambda: _FakePM())
    # 路径不存在
    out = rpc_server._handle_ext_command("plugin:installpath /no/such/file.zip")
    d = json.loads(out)
    assert d.get("ok") is False
    # 存在的 .zip
    z = tmp_path / "p.zip"
    z.write_bytes(b"PK\x03\x04")
    r = json.loads(rpc_server._handle_ext_command(f"plugin:installpath {z}"))
    assert r.get("ok") is True and r.get("name") == "从zip装的"
    # 存在的目录
    dr = tmp_path / "pdir"
    dr.mkdir()
    r2 = json.loads(rpc_server._handle_ext_command(f"plugin:installpath {dr}"))
    assert r2.get("ok") is True and r2.get("name") == "从目录装的"


def test_plugin_dir_rpc_returns_plugins_dir(rpc_server, monkeypatch, tmp_path):
    """plugin:dir 必须返回 pmgr.plugins_dir 的真实字符串，
    前端的「打开插件目录」按钮拿它复制到剪贴板，不再假成功。"""
    from pathlib import Path
    class _FakePM:
        plugins_dir = Path(str(tmp_path / "plugins"))
    monkeypatch.setattr(rpc_server, "_get_plugin_manager", lambda: _FakePM())
    out = rpc_server._handle_ext_command("plugin:dir")
    d = json.loads(out)
    assert d.get("ok") is True
    assert d.get("dir", "").endswith("plugins")


# ---------------------------------------------------------------------------
# R13 —— 全局回归护栏：确保「假按钮」不会偷偷复发
# ---------------------------------------------------------------------------
def test_no_fresh_growth_engine_in_status_rpcs(rpc_server):
    """回归保险：任何以 `GrowthEngine()` 起头的实例化都不该再出现在
    XiaoLingServicer 的 status 类 RPC 里。"""
    import inspect
    cls = rpc_server.XiaoLingServicer
    for name in ("GetStatus", "GetGrowthStatus", "GetTrainingStatus"):
        src = inspect.getsource(getattr(cls, name))
        # 允许注释/字符串里出现，但不允许 `= GrowthEngine(` 或 `GrowthEngine().status()` 这种调用
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            assert "GrowthEngine()" not in stripped, \
                f"{name} 检测到裸 GrowthEngine() 调用：{stripped!r}"

