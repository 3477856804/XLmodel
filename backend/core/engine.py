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
from .channels import ChannelHub
from .search import SearchAgent

VERSION = "0.0.1"
NAME = "小凌"

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


class RequestQueue:
    def __init__(self, max_size: int = 32, workers: int = 1):
        self._q: queue.Queue = queue.Queue(maxsize=max_size)
        self._results: dict[str, ChatResult] = {}
        self._lock = threading.RLock()
        self._stop = False
        self._engine = None
        self._workers: list = []
        for _ in range(max(1, workers)):
            t = threading.Thread(target=self._loop, daemon=True)
            t.start()
            self._workers.append(t)

    def attach(self, engine):
        self._engine = engine

    def submit(self, req_id: str, text: str) -> bool:
        try:
            self._q.put_nowait((req_id, text))
            return True
        except queue.Full:
            return False

    def wait(self, req_id: str, timeout: float = 60.0) -> ChatResult | None:
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self._lock:
                if req_id in self._results:
                    return self._results.pop(req_id)
            time.sleep(0.05)
        return None

    def _loop(self):
        while not self._stop:
            try:
                req_id, text = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if self._engine is None:
                continue
            try:
                result = self._engine._do_chat(text)
            except Exception as e:
                result = ChatResult(ok=False, error=f"{type(e).__name__}: {e}")
            with self._lock:
                self._results[req_id] = result

    def stop(self):
        self._stop = True

    def stats(self) -> dict:
        return {"queue_size": self._q.qsize(), "pending": len(self._results),
                "workers": len(self._workers)}


class XiaoLing:
    def __init__(self, config: dict | None = None, log: Callable | None = None,
                 auto_setup: bool = True):
        self.log = log or (lambda *a, **k: None)
        self.config = config or {}
        self.start_time = time.time()
        self.bus = EventBus()
        self.compressor = ContextCompressor(max_chars=4000, keep_recent=8)
        self.rq = RequestQueue()
        self.rq.attach(self)
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
        self.model_replace = self._safe_make("模型管理", lambda: ModelReplacement(
            selected_name=(cfg.get("model") or {}).get("base_model", ""),
            context_limit=int(cfg.get("max_context_turns", 200)) * 20,
            system_prompt=DEFAULT_SYSTEM_PROMPT))
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

    def chat_async(self, text: str, callback: Callable | None = None):
        req_id = f"req_{int(time.time() * 1000)}_{random.randint(0, 999)}"
        ok = self.rq.submit(req_id, text)
        if not ok:
            result = ChatResult(ok=False, error="请求队列已满")
            if callback:
                callback(result)
            return result
        if callback:
            def _waiter():
                r = self.rq.wait(req_id, timeout=120)
                callback(r or ChatResult(ok=False, error="超时"))
            threading.Thread(target=_waiter, daemon=True).start()
            return None
        return self.rq.wait(req_id, timeout=120)

    def chat_stream(self, text: str, on_chunk: Callable | None = None,
                    on_done: Callable | None = None):
        result = self._do_chat(text)
        if on_chunk:
            for ch in self._chunks(result.text):
                on_chunk(ch)
        if on_done:
            on_done(result)
        return result

    def _chunks(self, text: str, size: int = 3) -> Iterable[str]:
        for i in range(0, len(text), size):
            yield text[i:i + size]

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
            self._post_chat(text, reply, tool_calls)
            result = ChatResult(
                ok=True, text=reply, source=source,
                emotion=self._emotion_label(),
                relationship=self._relationship_label(),
                tokens=len(reply), tool_calls=tool_calls,
                elapsed_ms=round((time.time() - t0) * 1000, 1),
                intent=intent)
            self.bus.emit("chat:after", text, result)
            return result

    def _route(self, text: str) -> tuple:
        t = text.strip()
        lowered = t.lower()
        if lowered in CMD_MAP:
            t = CMD_MAP[lowered]
        m = INTENT_OPEN.search(t)
        if m:
            return self._route_open(m.group(2)), "open"
        if INTENT_CLEAR.search(t):
            return self._route_clear(), "clear"
        if INTENT_HELP.search(t):
            return self._route_help(), "help"
        if INTENT_STATUS.search(t):
            return self._route_status(), "status"
        if INTENT_MOOD.search(t):
            return self._route_mood(), "mood"
        if INTENT_RELATION.search(t):
            return self._route_relation(), "relation"
        if INTENT_JOKE.search(t):
            return self._route_joke(), "joke"
        if INTENT_TIME.search(t):
            return time.strftime("现在是 %Y-%m-%d %H:%M:%S。"), "time"
        if INTENT_DANCE.search(t):
            return self._route_dance(), "dance"
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

    def _route_dance(self) -> str:
        try:
            if self.voice is not None:
                pass
            return "好呀，给你跳一个。"
        except Exception:
            return "现在跳不了呢，稍后再试试。"

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

    def _reply_via_model(self, text: str) -> tuple:
        tool_calls: list = []
        reply = None
        source = "model"
        if self.model_replace is not None:
            try:
                history = self.conversation[-20:]
                reply = self.model_replace.chat(text, history)
            except Exception as e:
                self.log(f"  [模型] 推理失败：{e}")
                reply = None
        if not reply:
            reply = self._fallback_reply(text)
            source = "fallback"
        clean, calls = extract_tool_calls(reply)
        if calls:
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
        if self.toolkit is not None:
            try:
                matched = self.toolkit.match_skills(text)
                if matched:
                    reply = f"{reply}\n（相关技能：{matched[0]['name']}）"
            except Exception:
                pass
        return reply, tool_calls, source

    def _fallback_reply(self, text: str) -> str:
        if self.toolkit is not None:
            try:
                result = self.toolkit.execute("calculator", {"expr": text})
                if result and "工具出错" not in result and "表达式" not in result:
                    return f"算出来是 {result}。"
            except Exception:
                pass
        return random.choice(FALLBACK_TEMPLATES)

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
                self.growth.store.add(text, reply, source="chat")
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

    def context_for_prompt(self) -> str:
        return self.compressor.compress(self.conversation)

    def system_prompt(self) -> str:
        parts = [DEFAULT_SYSTEM_PROMPT]
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
        return (f"{NAME} v{VERSION} | 情绪：{self._emotion_label()} | "
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
            "model_status": (self.model_replace.status_text()
                             if self.model_replace else "未加载"),
            "tools": (len(self.toolkit.tools.tools) if self.toolkit else 0),
            "skills": (len(self.toolkit.skills.skills) if self.toolkit else 0),
            "goals": (self.toolkit.goals.stats() if self.toolkit else {}),
            "plugins": (len(self.plugins.list_plugins()) if self.plugins else 0),
            "memory": (self.memory_hub.stats() if self.memory_hub else {}),
            "persona": (self.persona.snapshot() if self.persona else {}),
            "growth": (self.growth.status() if self.growth else {}),
            "network": (self.offline.status_text() if self.offline else "未知"),
            "queue": self.rq.stats(),
            "bus_events": self.bus.events(),
            "paths": describe_paths(),
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
            "offline": (self.offline.is_online() if self.offline else False),
            "updater": self.updater is not None,
        }
        ok = sum(1 for v in checks.values() if v)
        return {"ok": ok, "total": len(checks), "checks": checks,
                "health": round(ok / len(checks), 2)}

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
                return self.persona.proactive.talk(self.persona.emotion.get_emotion())
        except Exception:
            pass
        return ""

    def tick(self):
        if self.plugins is not None:
            try:
                self.plugins.tick()
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

    def close(self):
        if self._closed:
            return
        self._closed = True
        for comp in (self.growth, self.memory_hub, self.plugins,
                     self.scheduler, self.voice, self.vision):
            if comp is not None and hasattr(comp, "close"):
                try:
                    comp.close()
                except Exception:
                    pass
        try:
            self.rq.stop()
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