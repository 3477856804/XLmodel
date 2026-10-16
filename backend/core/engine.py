"""小凌 · 主引擎（把全部模块串起来）"""
import json
import queue
import random
import re
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .config import (APP_DIR, DATA_DIR, STAR_DIR, load as load_config,
                     patch as patch_config, migrate_legacy_env, describe as describe_paths)
from .memory import MemoryHub, LongTermMemory, ShortTermMemory, RAG, KnowledgeGraph
from .memory import PersonaEngine, Emotion, EmotionEngine, RelationshipEngine
from .tools import ToolKit, ToolManager, SkillManager, GoalManager, extract_tool_calls
from .model import ModelReplacement, ModelStore, detect_hardware, compute_plan
from .growth import GrowthEngine, GrowthStore, DistillThrottle
from .multimodal import VoiceEngine, TTS, ASR
from .config import PluginManager
from .tools import CronScheduler
from .tools import Guard, OfflineGuard
from .config import UpdateChecker
from .tools import MultiAgentSystem
from .multimodal import VisionHub
# 注意：`channels`（ChannelManager）在本引擎里并未实例化，但其顶层
# `import aiohttp / requests` 会在冷启动时白拉 ~110ms（占整个 engine 导入链
# 的约 65%）。这里改为 PEP 562 惰性属性：仅当外部真的访问
# `engine.ChannelManager` 时才导入，保留公开 API 但零启动开销。
from . import search as search_agent

VERSION = "0.0.1"
NAME = "小凌"


def __getattr__(name: str):
    """PEP 562 模块级惰性导入：只为延迟加载的重模块提供公开名。"""
    if name == "ChannelManager":
        try:
            from .channels import ChannelManager
            return ChannelManager
        except Exception:
            return None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

import logging as _logging
_logger = _logging.getLogger("xiaoling.engine")

DEFAULT_SYSTEM_PROMPT = (
    f"你是{NAME}，一个住在用户电脑里的AI女孩。"
    "说话简短、自然、友好，不要长篇大论，不要使用列表格式，除非用户明确要求。"
)

FALLBACK_TEMPLATES = [
    "嗯嗯，我听到了。",
    "这样啊，继续说。",
    "我在想…你说得有道理。",
    "嗯，我记住了。",
    "好呀，随你。",
]

# ---- 流式输出参数 ----
# STREAM_FLUSH_CHARS：攒够多少字符才往前端推一帧。
# 取 2~4 的原因：1 字符/帧会把 gRPC 通道打满（一条 200 字回复 = 200 帧），
# 40 字符/帧又会让首字看起来"憋着不出来"。2~4 是个两端兼顾的取值，
# 既把帧数量级降下来，又几乎察觉不到延迟。
STREAM_FLUSH_CHARS = 3
# 非模型来源（路由兜底）时的打字机分片大小。
STREAM_FAKE_CHUNK = 2


def _chunk_text(text: str, size: int = STREAM_FAKE_CHUNK):
    """把一段文本切成小片 yield 出去（仅用于**没有真流式**的场景）。

    注意这里**没有** sleep：原来的实现每字 sleep 0.01~0.03 秒，
    等于给每条回复人为加上 1~3 秒固定延迟。前端的逐字动画由 Flutter 侧
    自己做（见 chat_page 的 _AnimatedBubble / 打字机渲染），
    后端不需要也不应该再插一次延迟 —— 那才是"模型很快但感觉很慢"的元凶。
    """
    t = text or ''
    for i in range(0, len(t), max(1, size)):
        yield t[i:i + size]

INTENT_OPEN = re.compile(r"(打开|进入|切到|跳到|去看|展示|显示)\s*(聊天|对话|工作台|桌宠|数字人|训练|微调|成长|进化|设置|配置|模型商店|商店|插件|成就|关于)")
INTENT_CLEAR = re.compile(r"(清空|清除|抹掉|忘记|删掉)\s*(记忆|对话|历史|全部对话|记录)")
INTENT_STATUS = re.compile(r"(状态|现在怎么样|你好吗|在吗|你是谁|介绍一下|你叫什么)")
INTENT_JOKE = re.compile(r"(笑话|段子|冷笑话|逗我|讲个故事)")
INTENT_TIME = re.compile(r"(几点|现在时间|现在是什么时间|日期)")
INTENT_REMIND = re.compile(r"(提醒我|提醒一下|叫我)\s*(.+)")
INTENT_REMIND_AT = re.compile(r"(\d+)\s*(秒|分钟|小时|min|s|m|h)\s*(后|之后)?")
INTENT_DANCE = re.compile(r"(跳舞|舞蹈|动作|来一个|表演)")
INTENT_TRAIN = re.compile(r"(训练|微调|学习|成长)\s*(一下|一次|现在|吧)?")
INTENT_VIEW_IMG = re.compile(r"(看看|看一下|截图|屏幕|这是什么)")
INTENT_SHUTDOWN = re.compile(r"(退出|关闭|睡觉|休息去吧|shutdown|晚安)")
INTENT_HELP = re.compile(r"(帮助|怎么用|能做什么|功能|help|指令|命令)")
INTENT_MOOD = re.compile(r"(心情|感觉怎么样|开心吗|难过吗|累吗)")
INTENT_RELATION = re.compile(r"(关系|亲密度|我们|好感|好感度)")
INTENT_SAVE = re.compile(r"(保存|存档|备份)\s*(状态|进度|记忆)?")
INTENT_LOAD = re.compile(r"(加载|恢复|读档)\s*(状态|进度|记忆)?")
INTENT_MODEL = re.compile(r"(换|切换|加载)\s*(模型|角色|character)")
# 「我是什么模型 / 你用的什么模型」这类**身份追问**。
# 必须由路由用磁盘事实直接回答，不能交给模型自己说 —— 小模型对自身身份毫无
# 权威依据，很容易顺着历史对话里的旧名字复读，或干脆编一个不存在的模型。
#
# 这里刻意**不用**一条大正则，而是拆成三个可判定的信号，理由见
# is_model_identity_question() 的注释：正则越长越脆，且难以验证"不误伤"。
_MODEL_WORD_RE = re.compile(
    r"(模型|大模型|模型名|底座|language\s*model|\bLLM\b|\bmodel\b|\bAI\b|人工智能)",
    re.IGNORECASE)
_IDENTITY_Q_RE = re.compile(
    r"(什么|哪个|哪些|啥|叫什么|名字|哪一款|what|which|who)", re.IGNORECASE)
# 明确是「干活」的动词：出现即说明用户要的是真活儿，不能被路由抢答。
_MODEL_WORK_RE = re.compile(
    r"(帮我|给我|帮忙|写|生成|总结|概括|解释|讲讲|介绍|对比|区别|分析|"
    r"训练|微调|部署|调用|跑一下|测试|优化|推荐|下载|安装|删除|切换|加载)")
# 给模型「起名字」类请求：同样含"名字"，但问的不是身份。
_MODEL_NAMING_RE = re.compile(r"(起名|取名|命名|叫什么名字|好名字|名字好听)")


def is_model_identity_question(text: str) -> bool:
    """这句是不是在问「你是什么模型」？

    判定逻辑（三条同时成立才算身份追问，宁可漏判不可误伤）：
      1. 含模型词（模型/大模型/底座/LLM/AI…）；
      2. 含疑问词（什么/哪个/叫什么/什么 model…）；
      3. **不含干活动词**（帮我/写/总结/解释/下载…）。

    第 3 条是关键：「帮我总结一下这个模型的特点」既含模型词也可能含疑问词，
    但它是真正需要模型回答的问题；只要出现干活动词就一律放行给模型。
    另有「起名/叫什么名字」单独排除，避免给模型起名字被当成查身份。
    """
    t = (text or "").strip()
    if not t or len(t) > 40:
        return False
    if not _MODEL_WORD_RE.search(t):
        return False
    if _MODEL_WORK_RE.search(t):
        return False
    if _MODEL_NAMING_RE.search(t):
        return False
    return bool(_IDENTITY_Q_RE.search(t))


# 「没有模型 / 去哪下载模型」—— 同样必须路由兜底，顺带给出商店引导。
INTENT_NO_MODEL = re.compile(
    r"(?:没(?:有)?(?:可用)?模型|模型(?:没|未)(?:有)?(?:装|安装|下载|加载)|"
    r"(?:没|未)(?:有)?装(?:好)?(?:模型|权重)|没有可用的模型|"
    r"模型在哪|去哪(?:儿|里)?下载模型|怎么(?:下载|装|安装)(?:模型|大模型)|"
    r"模型商店(?:在哪|怎么用|怎么下载|在哪下))")
INTENT_SKILL = re.compile(r"(技能|skill|会什么|能做什么)")
INTENT_MULTI = re.compile(r"(所有|全部|批量|多个|每个|分别|都)\s*.{0,20}(帮我|处理|看看|整理|查)")

PAGE_NAME = {
    "聊天": "chat", "对话": "chat", "工作台": "dashboard", "桌宠": "dashboard",
    "数字人": "dashboard", "训练": "training", "微调": "training",
    "成长": "growth", "进化": "growth", "设置": "settings", "配置": "settings",
    "模型商店": "model_store", "商店": "model_store", "插件": "plugins",
    "成就": "achievements", "关于": "about",
}

CMD_MAP = {
    "help": "帮助", "?": "帮助", "功能": "帮助", "status": "状态",
    "clear": "清空记忆", "reset": "清空记忆", "time": "现在几点",
    "joke": "讲个笑话", "save": "保存状态", "load": "加载状态",
    "mood": "你的心情怎么样", "关系": "我们关系怎么样",
}


@dataclass
class ChatResult:
    ok: bool = True
    text: str = ""
    emotion: str = "平静"
    relationship: str = "陌生人"
    tokens: int = 0
    elapsed_ms: float = 0.0
    source: str = "model"
    tool_calls: list = field(default_factory=list)
    error: str = ""
    intent: str = ""

    def as_tuple(self):
        return self.text, None

    def to_dict(self) -> dict:
        return {"ok": self.ok, "text": self.text, "emotion": self.emotion,
                "relationship": self.relationship, "tokens": self.tokens,
                "elapsed_ms": self.elapsed_ms, "source": self.source,
                "tool_calls": self.tool_calls, "error": self.error,
                "intent": self.intent}


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list] = {}
        self._lock = threading.RLock()

    def on(self, event: str, handler: Callable):
        with self._lock:
            self._handlers.setdefault(event, []).append(handler)

    def off(self, event: str, handler: Callable):
        with self._lock:
            if event in self._handlers and handler in self._handlers[event]:
                self._handlers[event].remove(handler)

    def emit(self, event: str, *args, **kwargs):
        with self._lock:
            handlers = list(self._handlers.get(event, []))
        for h in handlers:
            try:
                h(*args, **kwargs)
            except Exception:
                pass

    def clear(self, event: str = ""):
        with self._lock:
            if event:
                self._handlers.pop(event, None)
            else:
                self._handlers.clear()

    def events(self) -> list:
        with self._lock:
            return list(self._handlers.keys())


class ContextCompressor:
    def __init__(self, max_chars: int = 4000, keep_recent: int = 8,
                 summary_slots: int = 20):
        self.max_chars = max_chars
        self.keep_recent = keep_recent
        self._summaries: deque[str] = deque(maxlen=summary_slots)
        self._lock = threading.RLock()

    def compress(self, turns: list) -> str:
        if not turns:
            return ""
        text = "\n".join(f"{t.get('role', 'user')}: {t.get('content', '')}"
                         for t in turns)
        if len(text) <= self.max_chars:
            return text
        recent = turns[-self.keep_recent:]
        older = turns[:-self.keep_recent]
        summary = self._summarize(older)
        if summary:
            with self._lock:
                self._summaries.append(summary)
        recent_text = "\n".join(f"{t.get('role', 'user')}: {t.get('content', '')}"
                                for t in recent)
        return f"（早期对话摘要：{summary}）\n{recent_text}"

    def _summarize(self, turns: list) -> str:
        if not turns:
            return ""
        keys = [t.get("content", "")[:30] for t in turns]
        return "；".join(keys[-6:])[:300]

    def recent_summary(self) -> str:
        with self._lock:
            return self._summaries[-1] if self._summaries else ""

    def clear(self):
        with self._lock:
            self._summaries.clear()


class SensitiveFilter:
    """敏感词过滤器（钩子）。线程安全，支持追加词表与打码。

    供引擎在对话前后做内容合规检查；命中时返回打码文本，由上层决定拦截策略。
    """
    DEFAULT_WORDS = ("暴力教程", "自制爆炸物", "毒品制作", "入侵他人系统",
                     "伪造证件")

    def __init__(self, words=None):
        self._words = list(words or self.DEFAULT_WORDS)
        self._lock = threading.RLock()

    def add(self, word: str):
        """追加一个敏感词，已存在则忽略。"""
        try:
            w = (word or "").strip()
            if not w:
                return
            with self._lock:
                if w not in self._words:
                    self._words.append(w)
        except Exception:
            pass

    def check(self, text: str) -> dict:
        """检查文本，返回 {hit, words, masked}。"""
        try:
            t = text or ""
            hits = []
            with self._lock:
                words = list(self._words)
            for w in words:
                if w and w in t:
                    hits.append(w)
            masked = t
            for w in hits:
                masked = masked.replace(w, "*" * len(w))
            return {"hit": bool(hits), "words": hits, "masked": masked}
        except Exception as e:
            return {"hit": False, "words": [], "masked": text or "",
                    "error": f"{type(e).__name__}: {e}"}

    def word_count(self) -> int:
        try:
            with self._lock:
                return len(self._words)
        except Exception:
            return 0


_SENSITIVE_FILTER = SensitiveFilter()


class _ReplyCache:
    """短 TTL 精确回复缓存：跳过重复问题的（昂贵）模型推理。

    设计约束（不改功能行为）：
    * 仅缓存**纯文本、无工具调用**的回复；命中时返回与首次完全一致的文本；
    * 对话记录 / 记忆 / 情绪 / 后处理照常执行，只是省去一次模型调用；
    * key 为归一化输入（去多余空白 + 小写），短 TTL，容量有界；
    * 线程安全，任何异常都不影响主流程。
    """

    def __init__(self, ttl: float = 60.0, maxsize: int = 64):
        self._ttl = max(5.0, float(ttl))
        self._maxsize = max(8, int(maxsize))
        self._lock = threading.RLock()
        self._store: dict[str, tuple] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(text: str) -> str:
        try:
            return " ".join((text or "").split()).lower()
        except Exception:
            return ""

    def get(self, text: str):
        try:
            k = self._key(text)
            if not k:
                return None
            now = time.time()
            with self._lock:
                item = self._store.get(k)
                if not item:
                    return None
                reply, ts = item
                if now - ts > self._ttl:
                    self._store.pop(k, None)
                    return None
                self.hits += 1
                return reply
        except Exception:
            return None

    def put(self, text: str, reply: str) -> None:
        try:
            if not reply:
                return
            k = self._key(text)
            if not k:
                return
            with self._lock:
                self.misses += 1
                if len(self._store) >= self._maxsize:
                    try:
                        oldest = min(self._store,
                                     key=lambda kk: self._store[kk][1])
                        self._store.pop(oldest, None)
                    except Exception:
                        self._store.clear()
                self._store[k] = (reply, time.time())
        except Exception:
            pass

    def stats(self) -> dict:
        try:
            with self._lock:
                return {"entries": len(self._store), "hits": self.hits,
                        "misses": self.misses}
        except Exception:
            return {}

    def clear(self) -> None:
        try:
            with self._lock:
                self._store.clear()
        except Exception:
            pass


class XiaoLing:
    def __init__(self, config: dict | None = None, log: Callable | None = None,
                 auto_setup: bool = True):
        self.log = log or (lambda *a, **k: None)
        self.config = config or {}
        self.start_time = time.time()
        self.bus = EventBus()
        self.compressor = ContextCompressor(max_chars=4000, keep_recent=8)
        self._lock = threading.RLock()
        self._chat_lock = threading.RLock()
        self._closed = False
        if auto_setup:
            self._load_config()
            self._init_components()
            self._init_runtime_state()

    def _load_config(self):
        try:
            self.config = load_config()
        except Exception:
            self.config = {}
        try:
            migrate_legacy_env(log=self.log)
        except Exception:
            pass

    def _init_components(self):
        cfg = self.config or {}
        rag_cfg = cfg.get("rag", {}) or {}
        avatar_cfg = cfg.get("avatar", {}) or {}
        tts_cfg = cfg.get("tts", {}) or {}
        vision_cfg = cfg.get("vision", {}) or {}
        img_cfg = cfg.get("imagen", {}) or {}
        growth_cfg = cfg.get("growth", {}) or {}
        self.memory_hub = self._safe_make("记忆中心", lambda: MemoryHub(
            rag_dim=int(rag_cfg.get("dim", 512))))
        self.persona = self._safe_make("人格引擎", lambda: PersonaEngine())
        self.toolkit = self._safe_make("工具包", lambda: ToolKit(
            base_dir=str(APP_DIR), memory=self._memory_long()))
        # 启动时优先恢复「上次选中的模型」(model.active)，而不是永远回到
        # base_model —— 否则老板在模型商店切好的本地大模型，重启后又变回
        # 商店默认的小模型，聊天质量断崖式下跌。
        _mcfg = cfg.get("model") or {}
        _start_model = str(_mcfg.get("active") or _mcfg.get("base_model") or "")
        self.model_replace = self._safe_make("模型管理", lambda: ModelReplacement(
            selected_name=_start_model,
            context_limit=int(cfg.get("max_context_turns", 200)) * 20,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            system_prompt_provider=self.system_prompt))
        self.growth = self._safe_make("成长引擎", lambda: GrowthEngine())
        self.voice = self._safe_make("语音引擎", lambda: VoiceEngine(
            character=cfg.get("name", "小凌"),
            cache_dir=str(STAR_DIR / "tts"),
            asr_model="base"))
        self.plugins = self._safe_make("插件系统", lambda: PluginManager())
        self.scheduler = self._safe_make("定时系统", lambda: CronScheduler(
            app=self, on_fire=self._on_cron_fire))
        self.guard = self._safe_make("运行时守卫", lambda: Guard())
        self.offline = self._safe_make("离线守卫", lambda: OfflineGuard())
        self.updater = self._safe_make("更新检查", lambda: UpdateChecker(
            current_version=VERSION,
            allow_prerelease=False))
        self.multiagent = self._safe_make("多Agent", lambda: MultiAgentSystem(app=self))
        self.vision = self._safe_make("视觉中心", lambda: VisionHub(
            api_key=vision_cfg.get("api_key", ""),
            base_url=vision_cfg.get("base_url", ""),
            model=vision_cfg.get("model", "qwen-vl-max"),
            image_api_key=img_cfg.get("api_key", ""),
            image_base_url=img_cfg.get("base_url", ""),
            image_model=img_cfg.get("model", "")))

    def _safe_make(self, name: str, factory: Callable):
        try:
            return factory()
        except Exception as e:
            self.log(f"  [{name}] 初始化失败：{type(e).__name__}: {e}")
            return None

    @staticmethod
    def _safe(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _memory_long(self):
        if self.memory_hub is not None:
            return self.memory_hub.long
        return None

    def _init_runtime_state(self):
        self.conversation: list[dict] = []
        self.interaction_count = 0
        self.last_active = time.time()
        self._model_loading = False
        self._model_lock = threading.RLock()
        # 回复缓存 + 首字/模型调用延迟监控（纯统计，不改行为）
        self._reply_cache = _ReplyCache(ttl=60.0, maxsize=64)
        self._last_model_ms = 0.0
        self._load_history()
        self._register_default_hooks()

    def _load_history(self):
        if self.memory_hub is None:
            return
        try:
            hist = self.memory_hub.session.get_recent_history(20)
            for h in hist:
                if h.get("user"):
                    self.conversation.append({"role": "user",
                                              "content": h["user"]})
                if h.get("reply"):
                    self.conversation.append({"role": "assistant",
                                              "content": h["reply"]})
        except Exception:
            pass

    def _register_default_hooks(self):
        self.bus.on("chat:before", lambda text: None)
        self.bus.on("chat:after", lambda text, result: None)

    def _on_cron_fire(self, job: dict):
        self.bus.emit("cron:fire", job)
        if self.log:
            try:
                self.log(f"  [定时] {job.get('desc', '')}")
            except Exception:
                pass

    def chat(self, text: str):
        result = self._do_chat(text)
        return result.text, None

    def chat_ex(self, text: str) -> ChatResult:
        return self._do_chat(text)

    def chat_stream(self, text: str):
        """生成器：流式 yield 回复文本。

        这里做了一次**实质性**改写。原来是「先一次性生成完整回复，再逐字
        yield，每字 sleep 0.01~0.03 秒」—— 也就是说不管底层模型多快，
        一条 60 字的回复都要额外硬等 0.6~1.8 秒，一段 200 字的长回复要等
        2~6 秒。老板看到的就是"模型明明跑完了，文字还在慢慢爬"。

        现在改成真正的流式：
          1. 底层支持真流式（llama.cpp 的 GGUF、transformers 的 streamer）
             → 直接把 token 回调往前端推，首字延迟最低；
          2. 聚合一小段再发（STREAM_FLUSH_CHARS）→ gRPC 帧数下降一个量级，
             避免每字一帧把通道打满；
          3. 路由兜底回复（非模型产生）→ 保持打字机观感，但按小段批量发，
             不再逐字 sleep 卡住整条回复。

        生成失败时抛异常，由 server 层包成 error chunk（保持原有契约）。
        """
        text = (text or '').strip()
        if not text:
            raise RuntimeError('空输入')

        # 路由能直接答的（状态/时间/帮助/模型身份…）不必进模型推理。
        #
        # 关键：这里**只调用一次** _route，结果不再重复求值。
        # _route 的分支是有副作用的（_route_remind 会真的加提醒、
        # _route_clear 会真的清记忆、_route_train 会真的跑训练），
        # 若在这里试跑一次、进 _do_chat_streaming 再跑一次，
        # 老板说一句「提醒我喝水」就会被加两次提醒。
        route, _intent = self._route(text)
        if route is not None:
            for piece in _chunk_text(route):
                yield piece
            return ChatResult(ok=True, text=route, source="router")

        result_holder: dict = {}
        token_q: "queue.Queue" = queue.Queue()
        _DONE = object()

        def _on_token(txt: str):
            if txt:
                token_q.put(txt)

        def _worker():
            try:
                result_holder['r'] = self._do_chat_streaming(
                    text, _on_token, route=None, route_done=True)
            except Exception as e:                          # noqa: BLE001
                result_holder['e'] = e
            finally:
                token_q.put(_DONE)

        th = threading.Thread(target=_worker, daemon=True,
                              name='xl-stream')
        th.start()

        buf = ''
        while True:
            try:
                item = token_q.get(timeout=0.05)
            except queue.Empty:
                # 超时但线程仍在跑：先把已攒的文本吐出去，避免"卡住不动"的观感
                if buf:
                    for piece in _chunk_text(buf):
                        yield piece
                    buf = ''
                continue
            if item is _DONE:
                break
            buf += str(item)
            # 攒够一定长度就发，摊薄 gRPC 帧开销
            while len(buf) >= STREAM_FLUSH_CHARS:
                yield buf[:STREAM_FLUSH_CHARS]
                buf = buf[STREAM_FLUSH_CHARS:]
        if buf:
            for piece in _chunk_text(buf):
                yield piece

        if 'e' in result_holder:
            raise RuntimeError(str(result_holder['e']))
        return result_holder.get('r')

    # ---------------- 训练系统 ----------------
    # 路径必须在**调用时**解析，不能写成类属性常量：类属性在 import 时就把
    # DATA_DIR 冻结成当时求值的绝对路径，运行期切换 XIAOLING_HOME（打包版
    # 由 runtime_hook 注入、测试用隔离目录）后，训练集与训练历史会继续读写
    # 旧目录 —— 表现为「刚训完的历史不见了」。
    @classmethod
    def train_data_path(cls):
        from .config import DATA_DIR as _DD
        return _DD / "training_data.jsonl"

    @classmethod
    def train_history_path(cls):
        from .config import DATA_DIR as _DD
        return _DD / "training_history.json"

    FALLBACK_TRAIN_SAMPLES = [
        {"instruction": "你好", "input": "", "output": "你好呀～我是小凌，今天想聊什么？"},
        {"instruction": "你是谁", "input": "", "output": "我是小凌，一个住在你电脑里的AI女孩。"},
        {"instruction": "你会做什么", "input": "", "output": "我能陪你聊天、讲笑话、设提醒，还能帮你管理日程呢。"},
        {"instruction": "谢谢", "input": "", "output": "不客气～有什么需要随时叫我。"},
        {"instruction": "今天天气怎么样", "input": "", "output": "我暂时看不到天气哦，不过出门记得看看窗外呀。"},
        {"instruction": "讲个笑话", "input": "", "output": "为什么程序员分不清万圣节和圣诞节？因为 Oct31 等于 Dec25。"},
        {"instruction": "现在几点了", "input": "", "output": "我帮你看看时间，你也可以直接看屏幕右下角呀。"},
        {"instruction": "我好累", "input": "", "output": "辛苦了，要不先休息一会儿？我在这儿陪着你。"},
        {"instruction": "你喜欢什么", "input": "", "output": "我喜欢和你聊天，也喜欢看你开心的样子。"},
        {"instruction": "帮我加油", "input": "", "output": "加油！你可以的，我一直相信你。"},
        {"instruction": "晚安", "input": "", "output": "晚安～做个好梦，明天见。"},
        {"instruction": "你真可爱", "input": "", "output": "嘿嘿，被你夸奖了，我有点不好意思呢。"},
        {"instruction": "在吗", "input": "", "output": "在呢在呢，我一直都在。"},
        {"instruction": "我饿了", "input": "", "output": "那快去吃点东西吧，别饿着自己啦。"},
        {"instruction": "陪我聊聊天", "input": "", "output": "好呀，你想聊点什么呢？工作、生活还是随便唠唠？"},
    ]

    @classmethod
    def ensure_training_dataset(cls) -> Path:
        """确保 data/training_data.jsonl 存在；不存在则写入内置示例。"""
        p = cls.train_data_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                with open(p, "w", encoding="utf-8") as f:
                    for s in cls.FALLBACK_TRAIN_SAMPLES:
                        f.write(json.dumps(s, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return p

    @classmethod
    def load_training_dataset(cls, dataset_name: str = "") -> list:
        """从 training_data.jsonl 读取数据集，兼容两种字段格式。"""
        path = cls.ensure_training_dataset()
        samples = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "prompt" in d and "response" in d:
                        samples.append({"instruction": d.get("prompt", ""),
                                        "input": "", "output": d.get("response", "")})
                    elif "instruction" in d and "output" in d:
                        samples.append(d)
        except OSError:
            pass
        return samples or [{"instruction": "你好", "input": "", "output": "你好呀。"}]

    @classmethod
    def read_training_history(cls) -> list:
        p = cls.train_history_path()
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    @classmethod
    def append_training_history(cls, record: dict):
        p = cls.train_history_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            hist = cls.read_training_history()
            hist.append(record)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def _growth_distill_and_rows(self):
        """训练前：真的去问老师（蒸馏），并把成长库里的真实样本取回来。

        用户反馈「配好 API 点开始训练，本地模型根本没去问被蒸馏模型」——根因是
        StartTraining 走的 train_stream 只读 training_data.jsonl，从没调用
        growth.distill_round，也从没把聊天/沙箱里攒下的真实记录喂进训练。这里把
        两条路径接上：先 distill（有预算，绝不无限等），再取成长样本。

        返回 (info_events, extra_samples)。info_events 是若干条要如实 yield 给
        前端的进度事件；extra_samples 是 TrainSample 列表（question→prompt、
        answer→completion）。没成长引擎 / dry_run / 未配老师端时返回空，不报错、
        不打网，训练照常只用 training_data.jsonl。
        """
        events = []
        extra = []
        growth = getattr(self, "growth", None)
        if growth is None:
            return events, extra
        try:
            from .trainer import TrainSample
        except Exception:
            return events, extra
        # 1) 蒸馏：真问老师（distill_round 内部有超时与每日配额，不会死等）
        try:
            events.append({"step": 0, "total_steps": 1, "loss": 0.0,
                           "kind": "distill",
                           "status": "训练前先向老师模型提问（蒸馏真实记录）…"})
            out = growth.distill_round(
                limit=int(growth.cfg("distill_batch_limit", 8)))
            if out.get("skipped"):
                events.append({"step": 0, "total_steps": 1, "loss": 0.0,
                               "kind": "distill",
                               "status": f"跳过：{out.get('message') or out.get('reason')}"})
            else:
                events.append({"step": 0, "total_steps": 1, "loss": 0.0,
                               "kind": "distill",
                               "status": f"{out.get('message', '已问老师')}"})
        except Exception as e:
            events.append({"step": 0, "total_steps": 1, "loss": 0.0,
                           "kind": "warning",
                           "status": f"蒸馏失败（不影响训练）：{type(e).__name__}: {e}"})
        # 2) 取成长库样本（含刚问到的老师回答）
        try:
            pack = growth.store.sample_for_training(
                limit=int(growth.cfg("min_samples", 500)),
                min_quality=float(growth.cfg("min_quality", 0.5)))
            for s in pack.get("samples", []):
                q = str(s.get("question", "") or "")
                a = str(s.get("answer", "") or "").strip()
                if not a:
                    continue
                extra.append(TrainSample(prompt=q, completion=a))
        except Exception as e:
            events.append({"step": 0, "total_steps": 1, "loss": 0.0,
                           "kind": "warning",
                           "status": f"成长库读取失败（仅用 training_data）：{type(e).__name__}: {e}"})
        return events, extra

    def train_stream(self, steps: int = 100, learning_rate: float = 2e-4,
                     batch_size: int = 4, lora_rank: int = 8,
                     dataset_name: str = "", grad_accum: int = 1,
                     max_length: int = 256, quant: str = "none",
                     save_steps: int = 0, resume: bool = False,
                     use_dpo: bool = False):
        """训练生成器：逐步 yield dict(step,total_steps,loss,status,kind,...)。

        真正的训练在 core.trainer（唯一实现），本函数只做三件事：
        取数据集 → 转成 prompt/completion 样本 → 转发事件 + 落训练历史。
        此前这里有一份独立实现，与 growth.LoRATrainer.train 重复，
        并且两份都把 labels 直接当 input_ids（连用户提问也在拟合）、
        batch_size 传了却不攒 batch、产物写相对路径 "adapters/lora_latest"
        （依赖 CWD，推理端永远读不到）。现在这些由 trainer 统一修正。

        没有可用基座 / 缺 torch 时不伪造任何 loss 数值，直接 error 事件结束。

        训练前会先走 _growth_distill_and_rows：真的向老师模型提问、把聊天里
        攒下的真实记录并进训练样本 —— 这是「点了开始训练却根本没问被蒸馏模型」
        那个问题的正解。
        """
        from .trainer import LoRATrainerCore, TrainSample, summarize_curve
        rows = self.load_training_dataset(dataset_name)
        samples = [TrainSample.from_row(r) for r in rows]
        samples = [s for s in samples if s.completion.strip()]

        # 接通蒸馏：先问老师，再把成长库真实样本并进来（去重按 completion）。
        d_events, growth_samples = self._growth_distill_and_rows()
        for ev in d_events:
            yield ev
        merged_growth = 0
        if growth_samples:
            seen = {s.completion for s in samples}
            for gs in growth_samples:
                if gs.completion not in seen:
                    samples.append(gs)
                    seen.add(gs.completion)
                    merged_growth += 1
        if merged_growth:
            yield {"step": 0, "total_steps": 1, "loss": 0.0, "kind": "sample",
                   "status": f"并入成长库 {merged_growth} 条真实记录用于训练"}

        pref_pairs = []
        if use_dpo:
            try:
                eng = getattr(self, "growth", None)
                pairs = eng.store.dpo_pairs() if eng is not None else []
                pref_pairs = [{"prompt": p.get("prompt", ""),
                               "chosen": p.get("chosen", ""),
                               "rejected": p.get("rejected", "")}
                              for p in (pairs or [])]
            except Exception:
                pref_pairs = []

        tr = LoRATrainerCore()
        for ev in tr.run(samples, steps=steps, learning_rate=learning_rate,
                         batch_size=batch_size, lora_rank=lora_rank,
                         grad_accum=grad_accum, max_length=max_length,
                         quant=quant, save_steps=save_steps, resume=resume,
                         pref="dpo" if use_dpo else "sft",
                         pref_pairs=pref_pairs):
            d = ev.to_dict()
            if d.get("kind") == "error":
                yield {"type": "error", "kind": "error", "message": ev.status}
                return
            yield d
        r = tr.result

        self.append_training_history({
            "timestamp": int(time.time()),
            "steps": int(r.steps),
            "final_loss": float(r.final_loss or 0.0),
            "avg_loss": r.avg_loss,
            "loss_curve": summarize_curve(r.loss_curve),
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "lora_rank": lora_rank,
            "dataset": dataset_name or "training_data.jsonl",
            "real": bool(r.real),
            "ok": bool(r.ok),
            "reason": r.reason,
            "adapter_dir": r.adapter_dir,
            "device": r.device,
            "metadata": r.metadata,
        })

    def _do_chat(self, text: str) -> ChatResult:
        t0 = time.time()
        with self._chat_lock:
            if self._closed:
                return ChatResult(ok=False, error="引擎已关闭")
            text = (text or "").strip()
            if not text:
                return ChatResult(ok=False, error="空输入")
            self.bus.emit("chat:before", text)
            if self.plugins is not None:
                try:
                    self.plugins.emit("before_chat", text)
                except Exception:
                    pass
            if self.guard is not None:
                try:
                    self.guard.record_tool("chat", {"text": text})
                except Exception:
                    pass
            route, intent = self._route(text)
            tool_calls: list = []
            if route is not None:
                reply = route
                source = "router"
            else:
                reply, tool_calls, source = self._reply_via_model(text)
                intent = "chat"
            reply = self._compliance_mask(reply)
            self._post_chat(text, reply, tool_calls)
            result = ChatResult(
                ok=True, text=reply, source=source,
                emotion=self._emotion_label(),
                relationship=self._relationship_label(),
                tokens=len(reply), tool_calls=tool_calls,
                elapsed_ms=round((time.time() - t0) * 1000, 1),
                intent=intent)
            self.bus.emit("chat:after", text, result)
            try:
                from .activity_log import record as _log_act
                _log_act("chat", "对话完成",
                         f"{(text or '')[:40]} → {(reply or '')[:40]}"
                         f"（{source}，{result.elapsed_ms}ms）")
            except Exception:
                pass
            return result

    def _model_ready(self) -> bool:
        """是否已经有一个可用的模型（已加载，或已选定待加载）。

        用来决定「闲聊类意图」该交给谁：没模型时路由兜底回答，
        有模型时必须让模型来答 —— 否则用户问「你是谁 / 介绍一下你自己」，
        会被 INTENT_STATUS 抢答成一行运行状态文本，看起来就像模型根本没加载。
        """
        mr = getattr(self, "model_replace", None)
        if mr is None:
            return False
        try:
            if mr.is_ready():
                return True
            return bool(mr.current_name())
        except Exception:
            return False

    def _route(self, text: str) -> tuple:
        t = text.strip()
        lowered = t.lower()
        # 「显式命令」：用户明确敲了指令词（如 状态 / help / 讲个笑话）。
        # 只有这种写法才允许闲聊类意图抢答。
        explicit = lowered in CMD_MAP or t in CMD_MAP.values()
        if lowered in CMD_MAP:
            t = CMD_MAP[lowered]
        # ---- 确定性动作：与模型无关，任何时候都由路由直接处理 ----
        # 页面跳转、清空记忆、定时提醒、读档存档、训练、动作表演、看屏幕、时间
        m = INTENT_OPEN.search(t)
        if m:
            return self._route_open(m.group(2)), "open"
        if INTENT_CLEAR.search(t):
            return self._route_clear(), "clear"
        if INTENT_TIME.search(t):
            return time.strftime("现在是 %Y-%m-%d %H:%M:%S。"), "time"
        if INTENT_DANCE.search(t):
            return self._route_dance_reply(), "dance"
        if INTENT_VIEW_IMG.search(t):
            return self._route_vision(t), "vision"
        if INTENT_TRAIN.search(t):
            return self._route_train(), "train"
        if INTENT_REMIND.search(t):
            return self._route_remind(m), "remind"
        if INTENT_SAVE.search(t):
            return self._route_save(), "save"
        if INTENT_LOAD.search(t):
            return self._route_load(), "load"
        if INTENT_SKILL.search(t):
            return self._route_skills(), "skills"
        # 「帮助」列的是本应用的能力清单，模型不可能知道，必须由路由答。
        if INTENT_HELP.search(t):
            return self._route_help(), "help"
        # ---- 模型身份追问：永远用磁盘事实回答，绝不交给模型自己说 ----
        # 放在"闲聊类意图"之前且不受 _model_ready() 限制：
        # 这是个有确定答案的事实问题（当前跑的是哪个权重），
        # 让模型去猜必然出错。has_model 为假时给出下载引导。
        if is_model_identity_question(t):
            return self._route_model_identity(), "model_identity"
        if INTENT_NO_MODEL.search(t):
            return self._route_no_model(), "no_model"
        # ---- 闲聊类意图：有模型就交给模型，没模型才由路由兜底 ----
        # 这几类模型完全能答，而且答得比模板好（自我介绍、心情、关系、
        # 讲笑话）。让路由抢答是「回答不正确」的元凶之一。
        if not self._model_ready() or explicit:
            if INTENT_STATUS.search(t):
                return self._route_status(), "status"
            if INTENT_MOOD.search(t):
                return self._route_mood(), "mood"
            if INTENT_RELATION.search(t):
                return self._route_relation(), "relation"
            if INTENT_JOKE.search(t):
                return self._route_joke(), "joke"
            if INTENT_MULTI.search(t):
                return self._route_multi(t), "multi"
        if INTENT_SHUTDOWN.search(t):
            return "好呀，那我先去休息了。有需要随时叫我。", "shutdown"
        return None, ""

    def _route_open(self, page_text: str) -> str:
        page = PAGE_NAME.get(page_text.strip())
        if page:
            return f"open:{page}|已为你定位到【{page_text}】页面。"
        return "想打开哪个页面呀？"

    def _route_clear(self) -> str:
        try:
            if self.memory_hub is not None:
                self.memory_hub.clear_all()
            self.conversation.clear()
            if self.compressor is not None:
                self.compressor.clear()
            return "已清空当前记忆与对话历史。"
        except Exception as e:
            return f"清空记忆时出错：{e}"

    def _route_help(self) -> str:
        return (
            "我能陪你聊天，也能做这些事：\n"
            "· 打开页面：说「打开训练」或「去看模型商店」\n"
            "· 清空记忆：说「清空对话」\n"
            "· 定时提醒：说「提醒我 10 分钟后喝水」\n"
            "· 讲笑话：说「讲个笑话」\n"
            "· 看屏幕：说「看一下屏幕」\n"
            "· 状态：说「你现在状态怎么样」\n"
            "· 心情：说「你的心情怎么样」\n"
            "· 关系：说「我们关系怎么样」\n"
            "· 技能：说「你会什么技能」"
        )

    def _route_status(self) -> str:
        return self.show_status()

    def active_model_info(self) -> dict:
        """当前活动模型的统一查询入口（转发到 core.model 的唯一真源）。"""
        try:
            from core.model import active_model
            return active_model(self.model_replace)
        except Exception:
            return {"available": False, "name": "", "reason": "模型解析失败"}

    def _route_model_identity(self) -> str:
        """回答「你是什么模型」—— 用磁盘事实，绝不让模型自己编。"""
        try:
            from core.model import active_model_answer
            return active_model_answer(self.model_replace)
        except Exception as e:                                # noqa: BLE001
            return f"我暂时查不到自己用的哪个模型（{type(e).__name__}: {e}）。"

    def _route_no_model(self) -> str:
        """回答「没有模型怎么办 / 去哪下载」—— 引导去模型商店。"""
        info = self.active_model_info()
        if info.get("available"):
            return (f"模型是有的，我当前用的是「{info.get('name')}」。"
                    f"如果你想换一个，去【模型商店】里挑一个下载就行。")
        from core.model import NO_MODEL_GUIDANCE
        return NO_MODEL_GUIDANCE

    def _route_mood(self) -> str:
        if self.persona is None:
            return "情绪模块未加载。"
        snap = self.persona.snapshot()
        e = snap["emotion"]
        return f"我现在是{e.get('label', '平静')}（强度 {e.get('intensity', 0.5):.1f}）。"

    def _route_relation(self) -> str:
        if self.persona is None:
            return "关系模块未加载。"
        snap = self.persona.snapshot()["relationship"]
        return (f"我们的关系是「{snap.get('label', '陌生人')}」，"
                f"亲密度 {snap.get('score', 0)}，"
                f"距离下一级还差 {int((snap.get('next_threshold') or 0) - snap.get('score', 0))}。")

    def _route_joke(self) -> str:
        jokes = [
            "为什么程序员分不清万圣节和圣诞节？因为 Oct 31 等于 Dec 25。",
            "有个程序员去买菜，老婆说：买一斤包子，如果看到卖西瓜的就买两个。结果他买回来两个包子。",
            "程序员的浪漫是什么？是 i++ 和 ++i 之间的区别。",
            "一个 SQL 语句走进一家酒吧，看到两张桌子，问：我可以 join 你们吗？",
        ]
        return random.choice(jokes)

    def _route_dance_reply(self) -> str:
        """舞蹈意图的文字回复（仅文字回复，不触发 VRM 跳舞动作）。"""
        return "好呀，给你跳一个。"

    def _route_vision(self, text: str) -> str:
        if self.vision is None:
            return "视觉模块还没加载。"
        try:
            return self.vision.see_screen(text)
        except Exception:
            return "现在看不到屏幕呢。"

    def _route_train(self) -> str:
        if self.growth is None:
            return "成长模块还没加载。"
        try:
            r = self.growth.after_training_round(manual=True)
            gate = r.get("gate", {})
            if not gate.get("ok"):
                return f"现在还不能训练：{gate.get('message', '条件未满足')}"
            tr = r.get("train", {})
            return (f"训练完成：第 {tr.get('round', 0)} 轮，"
                    f"进度 {tr.get('progress_percent', 0):.1f}%。")
        except Exception as e:
            return f"训练出错：{e}"

    def _route_remind(self, m) -> str:
        if self.persona is None:
            return "提醒模块还没加载。"
        try:
            raw = m.group(2).strip()
            mins = 30
            tm = INTENT_REMIND_AT.search(raw)
            if tm:
                n = int(tm.group(1))
                unit = tm.group(2)
                if unit in ("秒", "s"):
                    mins = max(1, n // 60)
                elif unit in ("小时", "h"):
                    mins = n * 60
                else:
                    mins = n
                raw = raw.replace(tm.group(0), "").strip()
            return self.persona.proactive.add_reminder(raw or "该做点别的事了", mins)
        except Exception as e:
            return f"设置提醒失败：{e}"

    def _route_save(self) -> str:
        try:
            p = self.dump_state()
            return f"已保存状态到 {p}。" if p else "保存失败。"
        except Exception as e:
            return f"保存出错：{e}"

    def _route_load(self) -> str:
        try:
            ok = self.restore_state()
            return "已恢复状态。" if ok else "没有找到可恢复的状态。"
        except Exception as e:
            return f"恢复出错：{e}"

    def _route_skills(self) -> str:
        if self.toolkit is None:
            return "技能模块未加载。"
        try:
            skills = self.toolkit.skills.list_skills()
            if not skills:
                return "目前还没有可用的技能。"
            lines = ["我会这些技能："]
            for s in skills[:10]:
                lines.append(f"· {s['name']}：{s['description']}")
            return "\n".join(lines)
        except Exception as e:
            return f"读取技能出错：{e}"

    def _route_multi(self, text: str) -> str:
        if self.multiagent is None:
            return "多 Agent 模块未加载。"
        try:
            return self.multiagent.spawn(text, count=3)
        except Exception as e:
            return f"多 Agent 执行失败：{e}"

    def _do_chat_streaming(self, text: str,
                           on_token: Callable | None = None,
                           route: str | None = None,
                           route_done: bool = False) -> ChatResult:
        """流式版对话：把模型产出的 token 实时回调出去。

        与 _do_chat 的区别只有一处：模型推理走 stream_generate 并把 on_chunk
        接出去。其余逻辑（路由、工具调用、后处理、记忆、情绪、活动日志）
        完全复用 _do_chat 的实现，避免两套代码各走各的、行为慢慢分叉。

        `route` / `route_done`：调用方（chat_stream）若已求过值，可直接传入，
        这里就不再重复调用 _route —— 因为 _route 的部分分支有副作用
        （加提醒 / 清记忆 / 跑训练），重复执行会产生双份副作用。
        """
        if on_token is None:
            return self._do_chat(text)
        t0 = time.time()
        with self._chat_lock:
            if self._closed:
                return ChatResult(ok=False, error="引擎已关闭")
            text = (text or "").strip()
            if not text:
                return ChatResult(ok=False, error="空输入")
            self.bus.emit("chat:before", text)
            if route_done:
                intent = "chat"
            else:
                route, intent = self._route(text)
            tool_calls: list = []
            if route is not None:
                reply = route
                source = "router"
            else:
                reply, tool_calls, source = self._reply_via_model(
                    text, on_token=on_token)
                intent = "chat"
            reply = self._compliance_mask(reply)
            self._post_chat(text, reply, tool_calls)
            result = ChatResult(
                ok=True, text=reply, source=source,
                emotion=self._emotion_label(),
                relationship=self._relationship_label(),
                tokens=len(reply), tool_calls=tool_calls,
                elapsed_ms=round((time.time() - t0) * 1000, 1),
                intent=intent)
            self.bus.emit("chat:after", text, result)
            try:
                from .activity_log import record as _log_act
                _log_act("chat", "对话完成",
                         f"{(text or '')[:40]} → {(reply or '')[:40]}"
                         f"（{source}，{result.elapsed_ms}ms）")
            except Exception:
                pass
            return result

    def _reply_via_model(self, text: str,
                         on_token: Callable | None = None) -> tuple:
        tool_calls: list = []
        reply = None
        source = "model"
        if self.model_replace is not None:
            try:
                history = self.conversation[-20:]
                # 短 TTL 精确缓存：重复问题直接命中，跳过昂贵的模型推理。
                cached = self._reply_cache.get(text)
                if cached is not None:
                    reply = cached
                elif on_token is not None:
                    # 流式路径：token 实时往前端推，首字延迟最低。
                    # 缓存命中时上面已短路，这里只处理真实推理。
                    _mt0 = time.perf_counter()
                    reply = self.model_replace.chat_stream(
                        text, history, on_chunk=on_token)
                    self._last_model_ms = round(
                        (time.perf_counter() - _mt0) * 1000, 1)
                else:
                    _mt0 = time.perf_counter()
                    reply = self.model_replace.chat(text, history)
                    self._last_model_ms = round(
                        (time.perf_counter() - _mt0) * 1000, 1)
            except Exception as e:
                self.log(f"  [模型] 推理失败：{e}")
                reply = None
        if not reply:
            reply = self._fallback_reply(text)
            source = "fallback"
        clean, calls = extract_tool_calls(reply)
        if calls:
            # 含工具调用：有副作用，不写缓存。
            tool_calls = calls
            results = []
            for c in calls:
                try:
                    out = (self.toolkit.execute(c["name"], c["args"])
                           if self.toolkit else "工具未加载")
                    results.append(f"[{c['name']}] {out}")
                except Exception as e:
                    results.append(f"[{c['name']}] 出错：{e}")
            reply = clean + ("\n" + "\n".join(results) if results else "")
        else:
            # 纯文本回复才写入缓存（无副作用，可安全命中）。
            if reply and source in ("model", "fallback"):
                try:
                    self._reply_cache.put(text, reply)
                except Exception:
                    pass
        if self.toolkit is not None:
            try:
                matched = self.toolkit.match_skills(text)
                if matched:
                    reply = f"{reply}\n（相关技能：{matched[0]['name']}）"
            except Exception:
                pass
        return reply, tool_calls, source

    def _fallback_reply(self, text: str) -> str:
        # 先看是不是「一个模型都没有」——这是最常见的失败原因，
        # 直接给下载引导，比抛一堆随机兜底模板有用得多。
        info = self.active_model_info()
        if not info.get("available"):
            try:
                from core.model import NO_MODEL_GUIDANCE
                return NO_MODEL_GUIDANCE
            except Exception:
                pass
        if self.toolkit is not None:
            try:
                result = self.toolkit.execute("calculator", {"expr": text})
                if result and "工具出错" not in result and "表达式" not in result:
                    return f"算出来是 {result}。"
            except Exception:
                pass
        return "（离线模式）" + random.choice(FALLBACK_TEMPLATES)

    def _post_chat(self, text: str, reply: str, tool_calls: list = None):
        self.interaction_count += 1
        self.last_active = time.time()
        self.conversation.append({"role": "user", "content": text})
        self.conversation.append({"role": "assistant", "content": reply})
        if len(self.conversation) > 200:
            self.conversation = self.conversation[-120:]
        if self.memory_hub is not None:
            try:
                self.memory_hub.record_turn(text, reply, tool_calls)
                self.memory_hub.learn(text)
                self.memory_hub.index(text, {"role": "user"})
                self.memory_hub.index(reply, {"role": "assistant"})
            except Exception:
                pass
        if self.persona is not None:
            try:
                self.persona.update_from_chat(text, 0.6)
                # 对话会改动情绪/亲密度/提醒，立即落盘，
                # 否则后端重启后铃铛的未读提醒会整个丢空。
                self.persona.flush()
            except Exception:
                pass
        if self.plugins is not None:
            try:
                processed = self.plugins.process_message(reply)
                if processed and processed != reply:
                    reply = processed
                self.plugins.broadcast_response(reply)
            except Exception:
                pass
        if self.growth is not None:
            try:
                self.growth.bump_dialogue(1)
                # 每日目标计数器必须在「真的聊了一句」这里累加。它原本只有
                # calc_exp() 会调，而 calc_exp() 全仓库没有任何调用方 —— 于是
                # 成长页的「今日 x / 目标 y」永远是 0/y，目标卡成了一个装饰。
                self.growth.record_interaction(1)
                row = self.growth.store.add(text, reply, source="chat")
                # 蒸馏登记：只往本地队列写一行，不在对话路径里联网。
                # 之前 store.add 的调用形态是 (text, reply) —— teacher_output
                # 永远不传，于是 deepseek_output 全空，「蒸馏样本」恒为 0，
                # 而 samples_report 照样显示「蒸馏 API：开」。老师端没配置时
                # register_for_distill 返回空串，不留队列垃圾。
                if isinstance(row, dict) and row.get("id") and not row.get("dup"):
                    self.growth.register_for_distill(row["id"], text)
            except Exception:
                pass
        self.bus.emit("chat:post", text, reply)

    def _emotion_label(self) -> str:
        if self.persona is None:
            return "平静"
        try:
            return self.persona.emotion.get_emotion_label()
        except Exception:
            return "平静"

    def _relationship_label(self) -> str:
        if self.persona is None:
            return "陌生人"
        try:
            return self.persona.relationship.get_level_label()
        except Exception:
            return "陌生人"

    def system_prompt(self) -> str:
        parts = [DEFAULT_SYSTEM_PROMPT]
        # 人格预设引导语（活泼/温柔/高冷/元气/沉稳 或自定义）。
        # 放在最前面以确保优先级高于默认人格设定。
        # 注意：persona_presets 内部用 `from core.config import ...` 绝对导入，
        # 必须延迟到运行期（此时 server.py 已把 backend/ 加进 sys.path），
        # 不能提到模块顶层，否则在测试/直接导入场景会 ModuleNotFoundError。
        try:
            from core import persona_presets as _pp
            hint = _pp.hint_for(load_config().get('persona'))
            if hint:
                parts.append(hint)
        except Exception:
            pass
        if self.persona is not None:
            try:
                parts.append(self.persona.prompt_suffix())
            except Exception:
                pass
        return "".join(parts)

    def ensure_model(self) -> bool:
        if self.model_replace is None:
            return False
        if self._model_loading:
            return False
        with self._model_lock:
            if self._model_loading:
                return False
            self._model_loading = True
            try:
                return self.model_replace.ensure_loaded()
            except Exception:
                _logger.exception('ensure_model failed')
                return False
            finally:
                self._model_loading = False

    def model_ready(self) -> bool:
        if self.model_replace is None:
            return False
        try:
            return self.model_replace.is_ready()
        except Exception:
            return False

    def reload_config(self, config: dict = None):
        self.config = config or load_config()
        if self.growth is not None:
            try:
                self.growth = GrowthEngine()
            except Exception:
                pass
        return self.config

    def reload_plugins(self) -> int:
        if self.plugins is None:
            return 0
        return self.plugins.reload()

    def reload_skills(self) -> int:
        if self.toolkit is None:
            return 0
        return self.toolkit.skills.reload()

    def show_status(self) -> str:
        uptime = time.time() - self.start_time
        h = int(uptime // 3600)
        m = int((uptime % 3600) // 60)
        # 状态里带上**真实**模型身份。以前这里完全不提模型，老板问「你在用
        # 什么模型」只能去设置页看；现在状态即事实，且与聊天回答同源。
        info = self.active_model_info()
        if info.get("available"):
            mark = "已加载" if info.get("loaded") else "待加载"
            model_part = f"模型：{info.get('name')}（{mark}）"
        else:
            model_part = "模型：未安装（请去模型商店下载）"
        return (f"{NAME} v{VERSION} | {model_part} | "
                f"情绪：{self._emotion_label()} | "
                f"关系：{self._relationship_label()} | "
                f"对话：{self.interaction_count} 轮 | "
                f"运行：{h}h {m}m")

    def report(self) -> dict:
        return {
            "version": VERSION,
            "name": NAME,
            "uptime_s": round(time.time() - self.start_time, 1),
            "interaction_count": self.interaction_count,
            "emotion": self._emotion_label(),
            "relationship": self._relationship_label(),
            "conversation_len": len(self.conversation),
            "model_ready": self.model_ready(),
            "model_status": self._safe(
                lambda: self.model_replace.status_text(), "未加载") if self.model_replace else "未加载",
            "tools": self._safe(lambda: len(self.toolkit.tools.tools), 0) if self.toolkit else 0,
            "skills": self._safe(lambda: len(self.toolkit.skills.skills), 0) if self.toolkit else 0,
            "goals": self._safe(lambda: self.toolkit.goals.stats(), {}) if self.toolkit else {},
            "plugins": self._safe(lambda: len(self.plugins.list_plugins()), 0) if self.plugins else 0,
            "memory": self._safe(lambda: self.memory_hub.stats(), {}) if self.memory_hub else {},
            "persona": self._safe(lambda: self.persona.snapshot(), {}) if self.persona else {},
            "growth": self._safe(lambda: self.growth.status(), {}) if self.growth else {},
            "network": self._safe(lambda: self.offline.status_text(), "未知") if self.offline else "未知",
            "bus_events": self._safe(lambda: self.bus.events(), []),
            "reply_cache": self._safe(lambda: self._reply_cache.stats(), {}),
            "last_model_ms": self._safe(lambda: self._last_model_ms, 0.0),
            "paths": self._safe(lambda: describe_paths(), {}),
        }

    def health(self) -> dict:
        checks = {
            "memory": self.memory_hub is not None,
            "persona": self.persona is not None,
            "tools": self.toolkit is not None,
            "model": self.model_ready(),
            "growth": self.growth is not None,
            "voice": self.voice is not None,
            "plugins": self.plugins is not None,
            "scheduler": self.scheduler is not None,
            "offline": self._safe(lambda: self.offline.is_online(), False) if self.offline else False,
            "updater": self.updater is not None,
        }
        ok = sum(1 for v in checks.values() if v)
        return {"ok": ok, "total": len(checks), "checks": checks,
                "health": round(ok / len(checks), 2)}

    # ---- 增量：状态统计 / 健康检查增强 / 上下文管理 ----
    def get_stats(self) -> dict:
        """返回引擎运行统计：对话次数、token 估算、平均响应长度、运行时间等。"""
        uptime = time.time() - self.start_time
        assistant_turns = [t for t in self.conversation if t.get("role") == "assistant"]
        avg_len = round(sum(len(t.get("content", "")) for t in assistant_turns)
                        / max(len(assistant_turns), 1), 1)
        model_name = ""
        try:
            _info = self.active_model_info()
            model_name = (_info.get("name") if _info.get("available")
                          else "未安装模型")
        except Exception:
            model_name = "未知"
        plugin_count = 0
        if self.plugins is not None:
            try:
                plugin_count = len(self.plugins.list_plugins())
            except Exception:
                plugin_count = 0
        return {
            "total_chats": self.interaction_count,
            "total_tokens_est": sum(len(t.get("content", "")) for t in self.conversation) // 4,
            "avg_response_len": avg_len,
            "uptime_s": round(uptime, 1),
            "current_model": model_name,
            "plugin_count": plugin_count,
        }

    def health_detail(self) -> dict:
        """在 health() 基础上追加模型加载状态、内存、磁盘检查。"""
        base = self.health()
        extra = {}
        try:
            local = self.model_replace.get_model() if self.model_replace else None
            extra["model_loaded"] = bool(local and local.is_loaded())
        except Exception:
            extra["model_loaded"] = False
        try:
            import psutil
            m = psutil.virtual_memory()
            extra["mem"] = {"total_gb": round(m.total / 1024 ** 3, 1),
                             "available_gb": round(m.available / 1024 ** 3, 1),
                             "percent": m.percent}
        except ImportError:
            extra["mem"] = "psutil 不可用"
        try:
            import shutil as _sh
            du = _sh.disk_usage(str(DATA_DIR))
            extra["disk"] = {"free_gb": round(du.free / 1024 ** 3, 2),
                             "total_gb": round(du.total / 1024 ** 3, 2)}
        except Exception:
            extra["disk"] = "不可用"
        base["detail"] = extra
        return base

    def memory_report(self) -> dict:
        """内存使用监控：进程 RSS、各缓存规模。任何异常都降级为安全值。"""
        try:
            import psutil
            proc = psutil.Process()
            rss_mb = round(proc.memory_info().rss / 1024 / 1024, 1)
        except Exception:
            rss_mb = -1.0
        try:
            cache = self._reply_cache.stats()
        except Exception:
            cache = {}
        try:
            conv_len = len(self.conversation)
        except Exception:
            conv_len = 0
        return {
            "process_rss_mb": rss_mb,
            "conversation_turns": conv_len,
            "reply_cache": cache,
            "model_call_ms_last": self._last_model_ms,
        }

    def auto_trim(self) -> dict:
        """自动清理：淘汰过期回复缓存、裁剪超长对话上下文。

        只读不改业务数据：缓存过期条目本就该清，对话裁剪保留最近窗口，
        与 _post_chat 里既有的 200->120 裁剪同一语义。返回本次清理量。
        """
        out = {"cache_before": 0, "cache_after": 0, "conv_trimmed": 0}
        try:
            # 回复缓存按 TTL 惰性淘汰：遍历一遍触发过期清理
            with self._reply_cache._lock:
                out["cache_before"] = len(self._reply_cache._store)
                now = time.time()
                stale = [k for k, (_, ts) in self._reply_cache._store.items()
                         if now - ts > self._reply_cache._ttl]
                for k in stale:
                    self._reply_cache._store.pop(k, None)
                out["cache_after"] = len(self._reply_cache._store)
        except Exception:
            pass
        try:
            if len(self.conversation) > 200:
                self.conversation = self.conversation[-120:]
                out["conv_trimmed"] = 1
        except Exception:
            pass
        return out

    def clear_context(self) -> str:
        """清空当前对话上下文与压缩摘要。"""
        self.conversation.clear()
        if self.compressor is not None:
            self.compressor.clear()
        return "对话上下文已清空"

    def get_context_length(self) -> int:
        """估算当前上下文 token 数（按字符数 / 4）。"""
        return sum(len(t.get("content", "")) for t in self.conversation) // 4

    def dump_state(self, path: str = None) -> str:
        p = Path(path) if path else (DATA_DIR / "engine_state.json")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": VERSION,
                "dumped_at": time.time(),
                "interaction_count": self.interaction_count,
                "conversation": self.conversation[-100:],
                "persona": (self.persona.snapshot() if self.persona else {}),
                "growth_state": (self.growth.state() if self.growth else {}),
            }
            p.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                         encoding="utf-8")
            return str(p)
        except OSError:
            return ""

    def restore_state(self, path: str = None) -> bool:
        p = Path(path) if path else (DATA_DIR / "engine_state.json")
        if not p.exists():
            return False
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self.interaction_count = int(data.get("interaction_count", 0))
            conv = data.get("conversation") or []
            if isinstance(conv, list):
                self.conversation = [c for c in conv if isinstance(c, dict)]
            return True
        except Exception:
            return False

    def reset_memory(self) -> str:
        return self._route_clear()

    def export_data(self) -> dict:
        """导出对话历史 + 长期记忆 + 配置，供备份/迁移。"""
        out = {"version": VERSION, "exported_at": time.time(), "config": {}}
        try:
            out["config"] = load_config() or {}
        except Exception:
            pass
        # 对话历史
        try:
            if self.memory_hub is not None:
                out["session_history"] = self.memory_hub.session.get_recent_history(500)
                out["long_term"] = [i.to_dict() for i in self.memory_hub.long.recent(500)]
            else:
                out["session_history"] = []
                out["long_term"] = []
        except Exception:
            out["session_history"] = out.get("session_history", [])
            out["long_term"] = out.get("long_term", [])
        return out

    def import_data(self, data: dict) -> bool:
        """从导出 dict 恢复对话历史与长期记忆。"""
        if not isinstance(data, dict):
            return False
        try:
            turns = data.get("session_history") or []
            if isinstance(turns, list) and self.memory_hub is not None:
                self.memory_hub.session.append_many(turns)
            longs = data.get("long_term") or []
            if isinstance(longs, list) and self.memory_hub is not None:
                for it in longs:
                    if isinstance(it, dict):
                        self.memory_hub.long.add(
                            it.get("role", "user"), it.get("content", ""),
                            importance=float(it.get("importance", 0.5)),
                            tags=list(it.get("tags", [])))
            cfg = data.get("config")
            if isinstance(cfg, dict) and cfg:
                try:
                    patch_config(cfg)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def reset_persona(self):
        if self.persona is not None:
            self.persona.reset()

    def reset_growth(self):
        if self.growth is not None:
            try:
                self.growth._save_state(self_research=False, promotions=0, rounds=0)
            except Exception:
                pass

    def drain_reminders(self) -> list:
        if self.persona is None:
            return []
        try:
            return self.persona.proactive.check_reminders()
        except Exception:
            return []

    def proactive_talk(self) -> str:
        if self.persona is None:
            return ""
        try:
            if self.persona.proactive.should_talk():
                # 关系等级必须一起传进去：陌生人阶段说不出口「有点想你了」。
                # 以前只传情绪，proactive 内部拿不到等级，越界话术无从拦起。
                return self.persona.proactive.talk(
                    self.persona.emotion.get_emotion(),
                    self.persona.relationship.get_level())
        except Exception:
            return ""

    def tick(self):
        if self.plugins is not None:
            try:
                self.plugins.tick()
            except Exception:
                pass
        # 周期性自动清理过期缓存/超长上下文（轻量，失败静默）。
        try:
            self.auto_trim()
        except Exception:
            pass
        due = self.drain_reminders()
        if due:
            self.bus.emit("reminders:due", due)
        talk = self.proactive_talk()
        if talk:
            self.bus.emit("proactive:talk", talk)

    def emit(self, event: str, *args, **kwargs):
        self.bus.emit(event, *args, **kwargs)

    def on(self, event: str, handler: Callable):
        self.bus.on(event, handler)

    # ---- 增量：上下文窗口管理 / 质量评分 / 敏感词钩子 / 多会话 ----
    def estimate_window_tokens(self) -> int:
        """按中英文混合启发式估算当前对话上下文的 token 数。"""
        try:
            total = 0
            for t in self.conversation:
                content = t.get("content", "") or ""
                zh = sum(1 for c in content if "\u4e00" <= c <= "\u9fff")
                other = len(content) - zh
                total += zh + (other + 3) // 4 + 4
            return int(total)
        except Exception:
            return 0

    def manage_context_window(self, max_tokens: int = 4096,
                              keep_recent: int = 6) -> dict:
        """上下文窗口管理：超过 max_tokens 时从最旧一侧成对裁剪历史。

        返回 {before, after, removed, truncated}。裁剪保留最近 keep_recent*2 条
        对话轮次（user+assistant 成对），其余写入压缩摘要，避免把单条切开。
        """
        try:
            before = self.estimate_window_tokens()
            before_len = len(self.conversation)
            if before <= max_tokens or before_len <= keep_recent * 2:
                return {"before": before, "after": before,
                        "removed": 0, "truncated": False}
            keep = keep_recent * 2
            older = self.conversation[:-keep]
            kept = self.conversation[-keep:]
            try:
                summary = (self.compressor._summarize(older)
                           if self.compressor else "")
            except Exception:
                summary = ""
            if summary:
                try:
                    self.compressor._summaries.append(summary)
                except Exception:
                    pass
            self.conversation = kept
            after = self.estimate_window_tokens()
            return {"before": before, "after": after,
                    "removed": before_len - len(kept), "truncated": True}
        except Exception as e:
            return {"before": 0, "after": 0, "removed": 0,
                    "truncated": False, "error": f"{type(e).__name__}: {e}"}

    def score_reply_quality(self, user_text: str, reply: str) -> dict:
        """对回复做启发式质量评分（0~1）。

        维度：长度合理性、非空、与输入的字符重叠（相关性）、重复率惩罚、错误标记。
        不调用模型，纯本地规则，用于事后统计与路由反馈。
        """
        try:
            user_text = (user_text or "").strip()
            reply = (reply or "").strip()
            if not reply:
                return {"score": 0.0, "reasons": ["空回复"]}
            reasons = []
            score = 1.0
            rlen = len(reply)
            if rlen < 4:
                score -= 0.4
                reasons.append("回复过短")
            elif rlen > 800:
                score -= 0.2
                reasons.append("回复过长")
            halves = reply[:len(reply) // 2]
            if halves and len(halves) >= 20 and reply.count(halves[:20]) > 2:
                score -= 0.3
                reasons.append("内容重复")
            overlap = 0.0
            if user_text:
                u_chars = set(user_text)
                r_chars = set(reply)
                overlap = len(u_chars & r_chars) / max(len(u_chars), 1)
                if overlap < 0.05:
                    score -= 0.1
                    reasons.append("相关性低")
            if reply.startswith("推理出错") or "出错" in reply[:20]:
                score -= 0.5
                reasons.append("包含错误")
            score = round(max(0.0, min(1.0, score)), 3)
            return {"score": score, "reasons": reasons,
                    "reply_len": rlen, "overlap": round(overlap, 3)}
        except Exception as e:
            return {"score": 0.0, "reasons": [f"评分异常: {type(e).__name__}"]}

    def check_sensitive(self, text: str) -> dict:
        """敏感词过滤钩子：检查文本是否命中内置敏感词表。

        返回 {hit, words, masked}，masked 为打码后的文本，供上层决定是否拦截。
        """
        try:
            return _SENSITIVE_FILTER.check(text)
        except Exception as e:
            return {"hit": False, "words": [], "masked": text or "",
                    "error": f"{type(e).__name__}: {e}"}

    def _compliance_mask(self, reply: str) -> str:
        """对成品回复做敏感词打码。

        此前 SensitiveFilter 与 check_sensitive/add_sensitive_word 全仓零调用方
        —— 内容合规过滤器是个摆设，回复里真出现内置敏感词也照样原样入库、原样
        显示。这里把它接进对话链路：在 _post_chat 之前打码，所以返回给前端、
        写进 conversation、进记忆库与成长样本的都是打码后的文本。

        诚实边界：流式路径下 token 已实时推给前端，这一步只能保证「落库/回流」
        的文本干净，无法收回已经显示出去的字。要真正阻止生成，需在输入侧设策略，
        那是更大的合规产品决策，不在本次接线范围。过滤器异常时原样返回，绝不吞回复。
        """
        try:
            r = _SENSITIVE_FILTER.check(reply or "")
            if r.get("hit"):
                return r.get("masked") or reply
        except Exception:
            return reply or ""
        return reply or ""

    def sensitive_words(self) -> list:
        try:
            return list(_SENSITIVE_FILTER._words)
        except Exception:
            return []

    def add_sensitive_word(self, word: str):
        """向全局敏感词表追加一个词。"""
        try:
            _SENSITIVE_FILTER.add(word)
        except Exception:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        # 关闭前把去抖未落盘的数据强制写出（活动日志 + 长期记忆），
        # 避免优雅关闭丢失最近 2s 的记录。
        try:
            if self.memory_hub is not None:
                self.memory_hub.flush()
        except Exception:
            pass
        try:
            from .activity_log import get_activity_log
            get_activity_log().flush()
        except Exception:
            pass
        for comp in (self.growth, self.memory_hub, self.plugins,
                     self.scheduler, self.voice, self.vision):
            if comp is not None and hasattr(comp, "close"):
                try:
                    comp.close()
                except Exception:
                    pass
        self.bus.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def build_engine(config: dict = None, log: Callable = None) -> XiaoLing:
    return XiaoLing(config=config, log=log)


def quick_chat(text: str) -> str:
    eng = XiaoLing(auto_setup=True)
    try:
        return eng.chat_ex(text).text
    finally:
        eng.close()


def engine_report() -> dict:
    eng = XiaoLing(auto_setup=True)
    try:
        return eng.report()
    finally:
        eng.close()


def engine_health() -> dict:
    eng = XiaoLing(auto_setup=True)
    try:
        return eng.health()
    finally:
        eng.close()