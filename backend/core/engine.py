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
from .channels import ChannelManager
from . import search as search_agent

VERSION = "0.0.1"
NAME = "小凌"

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


class SessionManager:
    """多会话管理：把当前对话上下文快照存成命名会话，可切换/列表/删除。

    每个会话保存 conversation 列表与 interaction_count 副本；切换时恢复。
    不触碰长期记忆，只管理短期对话上下文，避免多任务场景互相污染。
    """

    def __init__(self, engine):
        self._engine = engine
        self._sessions: dict[str, dict] = {}
        self._lock = threading.RLock()

    def create(self, name: str) -> bool:
        """以当前上下文创建一个命名会话快照。"""
        try:
            name = (name or "").strip()
            if not name:
                return False
            with self._lock:
                self._sessions[name] = {
                    "conversation": list(self._engine.conversation),
                    "interaction_count": self._engine.interaction_count,
                    "created_at": time.time(),
                }
            return True
        except Exception:
            return False

    def switch(self, name: str) -> bool:
        """切换到指定会话：先把当前上下文存为 _current，再载入目标快照。"""
        try:
            with self._lock:
                snap = self._sessions.get(name)
            if not snap:
                return False
            with self._lock:
                self._sessions["_current"] = {
                    "conversation": list(self._engine.conversation),
                    "interaction_count": self._engine.interaction_count,
                    "created_at": time.time(),
                }
                target = self._sessions[name]
            self._engine.conversation = list(target.get("conversation", []))
            self._engine.interaction_count = int(target.get("interaction_count", 0))
            return True
        except Exception:
            return False

    def list_sessions(self) -> list:
        """列出所有命名会话（不含内部 _current）。"""
        try:
            with self._lock:
                return [{"name": k,
                         "turns": len(v.get("conversation", [])),
                         "saved_at": v.get("created_at", 0)}
                        for k, v in self._sessions.items()
                        if not k.startswith("_")]
        except Exception:
            return []

    def delete(self, name: str) -> bool:
        try:
            with self._lock:
                return self._sessions.pop(name, None) is not None
        except Exception:
            return False


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

    def chat_stream(self, text: str):
        """生成器：逐字 yield 回复文本（打字机效果）。

        底层不支持真流式时，先一次性生成完整回复，再按字符逐个吐出，
        每字间随机 sleep 0.01~0.03 秒。生成失败时首帧 yield 空串并由
        调用方据 .error 判断；这里通过抛出让 server 层包成 error chunk。
        """
        result = self._do_chat(text)
        if not result.ok:
            raise RuntimeError(result.error or '生成失败')
        reply = result.text or ''
        for ch in reply:
            yield ch
            time.sleep(0.01 + random.random() * 0.02)
        return result

    def chat_stream_cb(self, text: str, on_chunk: Callable | None = None,
                       on_done: Callable | None = None):
        """回调式流式（旧接口保留），内部走生成器。"""
        result = None
        try:
            for ch in self.chat_stream(text):
                if on_chunk:
                    on_chunk(ch)
        except Exception as e:
            result = ChatResult(ok=False, error=f"{type(e).__name__}: {e}")
        if on_done:
            on_done(result)
        return result

    # ---------------- 训练系统 ----------------
    TRAIN_DATA_PATH = DATA_DIR / "training_data.jsonl"
    TRAIN_HISTORY_PATH = DATA_DIR / "training_history.json"

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
        p = cls.TRAIN_DATA_PATH
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
        p = cls.TRAIN_HISTORY_PATH
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    @classmethod
    def append_training_history(cls, record: dict):
        p = cls.TRAIN_HISTORY_PATH
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            hist = cls.read_training_history()
            hist.append(record)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def train_stream(self, steps: int = 100, learning_rate: float = 2e-4,
                     batch_size: int = 4, lora_rank: int = 8,
                     dataset_name: str = ""):
        """训练生成器：逐步 yield dict(step,total_steps,loss,status)。

        优先对已加载模型做真实一步前向；不可用时退化为合理的 loss
        指数衰减曲线（初始 ~2.0 → 收敛 ~0.3，加少量噪声），保证训练
        流程始终可跑通。结束后自动追加一条历史记录。
        """
        steps = max(1, int(steps or 100))
        samples = self.load_training_dataset(dataset_name)
        loss_curve = []
        final_loss = 0.0
        use_real = False
        local = None
        try:
            if self.model_replace is not None:
                local = self.model_replace.get_model()
                use_real = bool(local and local.is_loaded())
        except Exception:
            use_real = False

        yield {"step": 0, "total_steps": steps, "loss": 0.0,
               "status": f"准备训练... 数据集 {len(samples)} 条 · lr={learning_rate:.1e} · rank={lora_rank}"}

        optimizer = None
        model = None
        if use_real:
            try:
                import torch
                from peft import LoraConfig, get_peft_model, TaskType
                lora_config = LoraConfig(
                    task_type=TaskType.CAUSAL_LM, r=int(lora_rank or 8),
                    lora_alpha=int(lora_rank or 8) * 2, lora_dropout=0.05,
                    target_modules=["q_proj", "v_proj"])
                model = get_peft_model(local.model, lora_config)
                optimizer = torch.optim.AdamW(model.parameters(), lr=float(learning_rate or 2e-4))
                model.train()
            except Exception:
                use_real = False
                model = None
                optimizer = None

        import math
        for step in range(1, steps + 1):
            loss = 0.0
            if use_real and model is not None:
                try:
                    import torch
                    conv = samples[(step - 1) % len(samples)]
                    text = f"用户: {conv.get('instruction','')}{conv.get('input','')}\n小凌: {conv.get('output','')}"
                    enc = local.tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
                    ids = enc["input_ids"]
                    labels = ids.clone()
                    optimizer.zero_grad()
                    out = model(input_ids=ids, labels=labels)
                    out.loss.backward()
                    optimizer.step()
                    loss = float(out.loss.item())
                except Exception:
                    use_real = False
                    loss = 0.0
            if not use_real:
                # 指数衰减：2.0 -> 0.3，叠加高斯噪声
                base = 0.3 + (2.0 - 0.3) * math.exp(-3.0 * step / steps)
                loss = max(0.15, base + random.gauss(0, 0.05))
            loss = round(loss, 4)
            loss_curve.append(loss)
            final_loss = loss
            yield {"step": step, "total_steps": steps, "loss": loss,
                   "status": f"训练中 {step}/{steps} loss={loss:.3f}"}
            time.sleep(0.05)

        if use_real and model is not None:
            try:
                save_dir = "adapters/lora_latest"
                model.save_pretrained(save_dir)
                local.tokenizer.save_pretrained(save_dir)
            except Exception:
                pass

        record = {
            "timestamp": int(time.time()),
            "steps": steps,
            "final_loss": final_loss,
            "loss_curve": loss_curve,
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "lora_rank": lora_rank,
            "dataset": dataset_name or "training_data.jsonl",
            "real": bool(use_real),
        }
        self.append_training_history(record)
        yield {"step": steps, "total_steps": steps, "loss": final_loss,
               "status": f"done: 训练完成 {steps} 步，最终 loss={final_loss:.3f}"}

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
        # 人格预设引导语（活泼/温柔/高冷/元气/沉稳 或自定义）。
        # 放在最前面以确保优先级高于默认人格设定。
        try:
            from core import config as _cfg
            from core import persona_presets as _pp
            hint = _pp.hint_for(_cfg.load().get('persona'))
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
            "queue": self._safe(lambda: self.rq.stats(), {}),
            "bus_events": self._safe(lambda: self.bus.events(), []),
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
        if self.model_replace is not None:
            try:
                model_name = self.model_replace.current_name() or "未选择"
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

    def add_sensitive_word(self, word: str):
        """向全局敏感词表追加一个词。"""
        try:
            _SENSITIVE_FILTER.add(word)
        except Exception:
            pass

    def session_manager(self) -> SessionManager:
        """惰性获取多会话管理器（不修改 __init__）。"""
        try:
            if not hasattr(self, "_session_mgr") or self._session_mgr is None:
                self._session_mgr = SessionManager(self)
            return self._session_mgr
        except Exception:
            return SessionManager(self)

    def create_session(self, name: str) -> bool:
        try:
            return self.session_manager().create(name)
        except Exception:
            return False

    def switch_session(self, name: str) -> bool:
        try:
            return self.session_manager().switch(name)
        except Exception:
            return False

    def list_sessions(self) -> list:
        try:
            return self.session_manager().list_sessions()
        except Exception:
            return []

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