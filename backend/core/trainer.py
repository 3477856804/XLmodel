"""小凌 · 统一 LoRA 微调内核（PyTorch + PEFT）

本模块是训练链路的**唯一实现**。此前 backend/core/engine.py::train_stream 与
backend/core/growth.py::LoRATrainer.train 各写了一套，重复实现导致同一个缺陷
被复制两份（labels=input_ids 不做 prompt mask、batch_size 参数声明了却逐条
循环）。两套现均改为本模块的薄封装。

与旧实现的关键差异（都是修正，不是加料）：

1. **loss 只算在 assistant 回复上**。旧实现 labels=input_ids，等于连用户的
   提问也在拟合，模型会学成「复述问题」。这里用 tokenizer 把 prompt 段
   （system + user）全部置为 IGNORE_INDEX(-100)。模板不支持
   chat_template 时退化为「只拟合「小凌:」之后」，并在 metadata 里如实记录
   prompt_mask="degraded"。

2. **batch 是真的**。旧实现接了 batch_size 参数却从不攒 batch；这里按
   batch_size 打包，配合 grad_accum 做梯度累积。

3. **产物路径是绝对路径**。旧实现 save_pretrained("adapters/lora_latest")
   依赖进程 CWD，打包版从任意目录启动就会把权重写到别处，推理端
   （model.py 固定读 STAR_DIR/"adapter"）永远读不到。现在默认落在
   ADAPTER_DIR（.star_core/adapter），并额外产出规范名 lora_latest
   （ADAPTER_DIR/"lora_latest"）。

4. **不伪造任何数值**。没有可用基底模型 / 缺 torch 时直接 ok=False + 原因，
   不吐假 loss 曲线、不写零字节假权重。

5. **可续训**。每 save_steps 步往 ADAPTER_DIR/"checkpoints"/stepN 落一份
   完整状态：LoRA 权重 + optimizer.pt（AdamW 动量）+ 该步的 loss 曲线快照，
   并把进度写进 ADAPTER_DIR/"trainer_state.json"。resume=True 时按检查点的
   **真实**步数接着跑，并把优化器状态装回去。
   三条如实约定（都是修出来的，不是加料）：
     - 检查点被删/读不出来时**拒绝本次训练**（resume_denied），绝不拿一个
       全新的随机 LoRA 按旧步数编号继续 —— 那等于谎报训练量；
     - optimizer.pt 缺失（旧版落的盘）或装不回去时，明说「本次只续权重、
       动量从头积累」，不假装是完整续训；
     - 调用方没显式传 save_steps/resume 时，读 config.growth 的
       checkpoint_interval / checkpoint_resume（见 checkpoint_cfg）。默认
       interval=0 表示不落检查点、不续训，训练行为与引入本功能前完全一致 ——
       proto 的 TrainingRequest 只有 5 个字段、改不了，续训开关只能在后端配置。
     - 一份检查点里的 optimizer.pt 比 LoRA 权重本身还大，一路落盘会把磁盘吃空，
       所以只保留最近 checkpoint_keep（默认 3）个 stepN 快照；非 stepN 的目录
       是用户自己放的，不碰（见 _rotate_checkpoints）。

关于「更好的训练方法」：本模块额外支持两种同样基于 PEFT 的真实微调，它们
比全权重微调省显存、比纯 SFT 更贴「伴侣人格」这个目标：
  - quant="int4"/"int8"：QLoRA（bitsandbytes 在 CUDA 上可用时自动生效，
    否则如实回退并在 metadata 记录 fallback）。
  - pref="dpo"：用数据仓库里的 (prompt, chosen, rejected) 偏好对做 DPO，
    比把纠错后的答案当 SFT 语料更有效——用户点「不喜欢」的回复会被真正
    当成负样本。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

IGNORE_INDEX = -100

# 磁盘上保留最近几个续训检查点。optimizer.pt 是 AdamW 的两份动量（fp32，
# 比 LoRA 权重本身还大），一路落下去能把用户磁盘吃空，所以必须有上限。
DEFAULT_CHECKPOINT_KEEP = 3

# 不同模型家族的 LoRA 注入点。猜错模块名 PEFT 会静默地包不到任何层，
# 训练照跑、loss 照降，但适配器是空的——最难查的一类假实现，所以显式列表。
TARGET_MODULE_CANDIDATES = [
    ["q_proj", "k_proj", "v_proj", "o_proj"],      # Llama / Qwen2 / Mistral 系
    ["c_attn", "c_proj", "c_fc"],                   # GPT-2 / GPT-J（全部 Conv1D）
    ["q_proj", "v_proj"],                           # 保守：仅 attention 投影
    ["Wqkv", "out_proj"],                           # Falcon / MPT 系
    ["query_key_value"],                            # ChatGLM 系
    ["fc1", "fc2", "out_proj"],                     # T5 / M2M100
    ["wqe", "wkq", "wv", "wo"],                     # 部分国产小模型
]

DEFAULT_SYSTEM_PROMPT = "你是小凌，住在用户电脑里的 AI 女孩。"


def _resolve_adapter_dir() -> Path:
    """适配器落盘目录：**调用时**解析，绝不冻结在 import 时刻。

    模块级常量在 import 时就把 STAR_DIR 求成固定绝对路径。打包版的
    runtime_hook 是在运行期才注入 XIAOLING_HOME 的，测试也靠临时 HOME 做隔离；
    冻结常量会让训练把适配器写到上一个（或默认的）目录，表现为
    「训练成功但推理端读不到」。取不到 config 时退回绝对路径兜底。
    """
    try:
        from .config import STAR_DIR as _SD
        return _SD / "adapter"
    except Exception:
        env = os.environ.get("XIAOLING_HOME")
        base = Path(env).resolve() if env else Path.cwd().resolve()
        return base / ".star_core" / "adapter"


# 仅作向后兼容展示用；任何路径决策都不要引用它，改用 _resolve_adapter_dir()
ADAPTER_DIR = _resolve_adapter_dir()


@dataclass
class TrainSample:
    """一条训练样本：prompt（不参与 loss）+ completion（参与 loss）。"""
    prompt: str
    completion: str
    system: str = DEFAULT_SYSTEM_PROMPT

    @classmethod
    def from_row(cls, row: dict) -> "TrainSample":
        """兼容 data/training_data.jsonl 的两种字段写法。"""
        if "prompt" in row and "response" in row:
            return cls(prompt=str(row.get("prompt", "")),
                       completion=str(row.get("response", "")))
        inst = str(row.get("instruction", "") or "")
        extra = str(row.get("input", "") or "").strip()
        prompt = f"{inst}\n{extra}" if (inst and extra) else (inst or extra)
        return cls(prompt=prompt, completion=str(row.get("output", "") or ""))


@dataclass
class TrainEvent:
    step: int = 0
    total_steps: int = 0
    loss: float = 0.0
    status: str = ""
    kind: str = "progress"          # progress | init | info | eval | done | error
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"step": self.step, "total_steps": self.total_steps,
                "loss": self.loss, "status": self.status, "kind": self.kind,
                **self.extra}


@dataclass
class TrainResult:
    ok: bool
    reason: str = ""
    steps: int = 0
    final_loss: float | None = None
    avg_loss: float | None = None
    loss_curve: list = field(default_factory=list)
    adapter_dir: str = ""
    device: str = ""
    real: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "reason": self.reason, "steps": self.steps,
                "final_loss": self.final_loss, "avg_loss": self.avg_loss,
                "loss_curve": self.loss_curve, "adapter_dir": self.adapter_dir,
                "device": self.device, "real": self.real,
                "metadata": self.metadata}


def detect_target_modules(model, preferred: list | None = None) -> list:
    """在真实模型里探测可注入 LoRA 的线性层名。

    PEFT 对不存在的 target_modules 只是警告，不报错——必须自己校验，
    否则会得到一个「训练成功但没有任何参数可训」的空适配器。
    """
    names = {n.split(".")[-1] for n, _ in model.named_modules()}
    cands = [preferred] + TARGET_MODULE_CANDIDATES if preferred else TARGET_MODULE_CANDIDATES
    for cand in cands:
        hit = [m for m in cand if m in names]
        if hit:
            return hit
    # 兜底：扫真正的 Linear / Conv1D 子模块，取出现最多的末段名
    try:
        import torch.nn as nn
        from collections import Counter
        from transformers.pytorch_utils import Conv1D as _HFConv1D
        cnt = Counter(n.split(".")[-1] for n, m in model.named_modules()
                      if isinstance(m, (nn.Linear, _HFConv1D)))
        if cnt:
            return [cnt.most_common(1)[0][0]]
    except Exception:
        pass
    return []


def has_conv1d_target(model, targets: list) -> bool:
    """命中的目标层里是否含 HF Conv1D（GPT-2 / GPT-J 系）。

    Conv1D 的权重形状是 (in, out)，与 nn.Linear 的 (out, in) 相反。PEFT
    不加 fan_in_fan_out 就会把 A/B 接反：训练照样跑、loss 照样降，但适配器
    是坏的——正是最难查的那种「看起来成功了」。

    detect_target_modules 是按「末段名」匹配的，所以这里同样按末段名判定，
    而不是要求完整路径命中。
    """
    try:
        from transformers.pytorch_utils import Conv1D as _HFConv1D
        tl = {t.split(".")[-1] for t in targets}
        for n, m in model.named_modules():
            if isinstance(m, _HFConv1D) and n.split(".")[-1] in tl:
                return True
    except Exception:
        pass
    return False


def build_example(tokenizer, s: TrainSample, max_length: int) -> dict | None:
    """构造 input_ids + labels，把 prompt 段的 label 全部置为 IGNORE_INDEX。

    返回 None 表示这条样本没有可学习的 completion token（比如 output 为空），
    调用方应跳过而不是塞个全 -100 的样本进去——那种样本会让 loss 变成 NaN。
    """
    messages = [
        {"role": "system", "content": s.system},
        {"role": "user", "content": s.prompt},
    ]
    ids_prompt = None
    masked_by = "chat_template"
    try:
        # 只有 tokenizer 真的带 chat_template 才走这条路（gpt2 这类老模型没有，
        # apply_chat_template 会直接抛 ValueError）
        if not getattr(tokenizer, "chat_template", None):
            raise ValueError("no chat_template")
        text_full = tokenizer.apply_chat_template(
            messages + [{"role": "assistant", "content": s.completion}],
            tokenize=False, add_generation_prompt=False)
        text_prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
        if isinstance(text_full, list):      # 少数模板直接返回 ids
            ids_prompt = tokenizer(text_prompt, add_special_tokens=False)["input_ids"]
            enc = {"input_ids": text_full[0]}
        else:
            enc = tokenizer(text_full, add_special_tokens=False, truncation=True,
                            max_length=max_length)
            ids_prompt = tokenizer(text_prompt, add_special_tokens=False)["input_ids"]
    except Exception:
        # 模板缺失/损坏：退化为「小凌:」文本分界。这是近似值——分词边界可能
        # 把「小凌:」的第一个 token 和上文粘在一起，所以标注 degraded。
        masked_by = "degraded"
        text_full = f"{s.prompt}\n小凌: {s.completion}"
        enc = tokenizer(text_full, add_special_tokens=False, truncation=True,
                        max_length=max_length)
        ids_prompt = tokenizer(f"{s.prompt}\n小凌: ",
                               add_special_tokens=False)["input_ids"]

    ids = list(enc["input_ids"])
    if not ids:
        return None
    n_prompt = min(len(ids_prompt or []), len(ids) - 1)
    labels = [IGNORE_INDEX] * n_prompt + ids[n_prompt:]
    # completion 被 max_length 截没了：这条样本没有监督信号，丢弃
    if all(l == IGNORE_INDEX for l in labels):
        return None
    return {"input_ids": ids, "labels": labels,
            "attention_mask": [1] * len(ids),
            "masked_by": masked_by,
            "trainable_tokens": sum(1 for l in labels if l != IGNORE_INDEX)}


def collate(features: list, pad_token_id: int) -> dict:
    """右侧 padding；labels 用 IGNORE_INDEX 填，padding 位置不参与 loss。"""
    import torch
    width = max(len(f["input_ids"]) for f in features)
    batch = {"input_ids": [], "labels": [], "attention_mask": []}
    for f in features:
        pad = width - len(f["input_ids"])
        batch["input_ids"].append(f["input_ids"] + [pad_token_id] * pad)
        batch["labels"].append(f["labels"] + [IGNORE_INDEX] * pad)
        batch["attention_mask"].append([1] * len(f["input_ids"]) + [0] * pad)
    t = {k: torch.tensor(v, dtype=torch.long) for k, v in batch.items()}
    t["_trainable_tokens"] = sum(
        sum(1 for l in f["labels"] if l != IGNORE_INDEX) for f in features)
    t["_masked_by"] = (features[0].get("masked_by") or "unknown") if features else "unknown"
    return t


def _pad_id(tokenizer) -> int:
    """取一个安全的 padding id：pad_token → eos_token → 0。"""
    try:
        if getattr(tokenizer, "pad_token_id", None) is not None:
            return int(tokenizer.pad_token_id)
    except Exception:
        pass
    try:
        if getattr(tokenizer, "eos_token_id", None) is not None:
            return int(tokenizer.eos_token_id)
    except Exception:
        pass
    return 0


def checkpoint_cfg() -> dict:
    """续训配置（growth.checkpoint_interval / checkpoint_resume / checkpoint_keep）。

    TrainingRequest（proto）里没有 save_steps/resume 字段，前端也改不了 ——
    续训只能由后端配置驱动。刻意用「和 growth.CONFIG_KEYS 不重合」的名字，
    免得多出的键混进成长页配置表却走不到 growth 的写入校验。

    checkpoint_interval：< 1 = 不落检查点（训练行为与引入续训前完全一致）；
    checkpoint_resume：auto / always / off（默认 off，与 interval=0 一起
    表示「这件事没开」）。
      auto    —— 有可用检查点才续；检查点被删/读不出来时 trainer 如实拒绝
                 本次训练（resume_denied），拒绝本身会原样显示给用户。
      always  —— 与 auto 相同，只是表明用户明确要求续训。
      off     —— 从不续训，从 step0 开新适配器。
    checkpoint_keep：磁盘上保留最近几个检查点。optimizer.pt 比权重还大，
      不设上限的话长训练会把磁盘吃空，所以这必须有默认值（3）而不是「无限」。
    读不到配置时按「关闭」处理并记录 error —— 不猜一个「开启」。
    """
    out = {"interval": 0, "mode": "off", "keep": DEFAULT_CHECKPOINT_KEEP,
           "source": "default"}
    try:
        from .config import load as _load
        g = ((_load() or {}).get("growth") or {})
        try:
            out["interval"] = max(0, int(g.get("checkpoint_interval", 0) or 0))
        except (TypeError, ValueError):
            out["interval"] = 0
        mode = str(g.get("checkpoint_resume", "off") or "off").strip().lower()
        out["mode"] = mode if mode in ("auto", "always", "off") else "off"
        try:
            keep = int(g.get("checkpoint_keep", DEFAULT_CHECKPOINT_KEEP))
        except (TypeError, ValueError):
            keep = DEFAULT_CHECKPOINT_KEEP
        out["keep"] = min(24, max(1, keep))
        out["source"] = "config"
    except Exception as e:                                       # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _resolve_checkpoint_args(save_steps: int, resume: bool,
                             meta: dict) -> tuple[int, bool]:
    """调用方显式传参优先；未传时用配置值。

    这样 CLI/测试里 save_steps=2, resume=True 的行为不变，而所有生产调用
    （StartTraining、成长轮）都自动吃到用户开的续训配置。
    """
    if (save_steps and int(save_steps) > 0) or resume:
        return int(save_steps or 0), bool(resume)
    cfg = checkpoint_cfg()
    if cfg.get("source") != "config":
        if cfg.get("error"):
            meta["checkpoint_config_error"] = cfg["error"]
        return int(save_steps or 0), bool(resume)
    interval, mode = int(cfg["interval"]), cfg["mode"]
    # 配置完全关着（默认值）时不留任何痕迹：训练行为与引入续训前一致。
    if interval < 1 and mode == "off":
        return 0, False
    meta["checkpoint_source"] = "config"
    if interval < 1:
        # 落了个 auto/off 的说明。不是异常分支伪造的：用户可能真的只改了模式。
        meta["resume_note"] = (
            f"续训模式={mode}，但 growth.checkpoint_interval={interval}"
            "（<1 不落检查点），本次不续训。想续训先设间隔："
            "training:checkpoint 50 auto")
        return 0, False
    return interval, mode in ("auto", "always")


def _resolve_model_dir(base_dir: Path | str | None) -> tuple[Path | None, str]:
    """找到可训练的**HF 格式**基底目录；GGUF 不能用于 PEFT 训练，如实拒绝。"""
    from .config import STAR_DIR, load as load_config
    candidates: list[Path] = []
    if base_dir:
        candidates.append(Path(base_dir))
    try:
        from .growth import BASE_MODEL_DIR
        candidates.append(Path(BASE_MODEL_DIR))
    except Exception:
        pass
    try:
        name = str(((load_config() or {}).get("model") or {})
                   .get("base_model") or "").strip()
        if name:
            candidates.append(STAR_DIR / "models" / name)
    except Exception:
        pass
    models_root = STAR_DIR / "models"
    if models_root.is_dir():
        candidates.extend(sorted(models_root.iterdir()))

    seen = set()
    for d in candidates:
        if d is None or not d.is_dir():
            continue
        key = str(d.resolve())
        if key in seen:
            continue
        seen.add(key)
        if (d / "config.json").exists() and (
                (d / "model.safetensors").exists()
                or (d / "pytorch_model.bin").exists()
                or list(d.glob("model*.safetensors"))
                or list(d.glob("pytorch_model-*.bin"))):
            return d, ""
        if list(d.glob("*.gguf")):
            continue    # GGUF 只用于 llama.cpp 推理，不参与训练
    return None, ("没找到可训练的 HF 格式（safetensors/bin）基底模型。"
                  "GGUF 量化文件只能推理、不能做 LoRA 微调，"
                  "请在模型商店下载 safetensors 版本的基底模型。")


# --------------------------------------------------------------------------- #
#  当前在跑的训练 —— gRPC 侧 training:cancel 需要拿到正在跑的那个 core 实例
#  才能真的停下来。以前 trainer 有 cancel() 却没有任何调用方，等于没有取消。
#
#  用「最近若干个 core」的短列表而不是全局单例：run() 是生成器，由 gRPC 线程
#  持有；客户端断开时生成器可能不会被立刻关闭，注册表里会留下已经跑完的实例。
#  request_cancel() 只挑「还没被取消过」的实例下手，并限定在最近 8 个以内，
#  所以残留条目要么无影响、要么只导致「这次没停住」，绝不会虚报成功，
#  也不会无界增长。
# --------------------------------------------------------------------------- #
_LIVE_LOCK = threading.Lock()
_LIVE: "list[LoRATrainerCore]" = []


def _live_register(tr) -> None:
    with _LIVE_LOCK:
        _LIVE.append(tr)
        # 只保留最近的，避免长进程里无界增长
        del _LIVE[:-8]


def live_trainers() -> list:
    with _LIVE_LOCK:
        return list(_LIVE)


def request_cancel(reason: str = "user") -> dict:
    """请求停止正在运行的训练。返回真实结果，不虚报「已停止」。

    只挑 running=True 的实例：跑完/失败的实例仍在注册表里，若不看 running
    就会给一个已经结束的训练打上 cancel 标记并回 ok=True —— 那正是本仓库
    一路在清除的「假成功」。
    """
    reason = (reason or "user").strip()[:60] or "user"
    with _LIVE_LOCK:
        tgts = [tr for tr in _LIVE if tr.running and not tr.cancelled]
        for tr in tgts:
            tr.request_stop(reason)
    if not tgts:
        return {"ok": False, "cancelled": 0,
                "reason": "当前没有正在运行的训练任务（可能已结束或已被取消）"}
    return {"ok": True, "cancelled": len(tgts),
            "steps": [tr.global_step for tr in tgts],
            "total_steps": [tr.total_steps for tr in tgts],
            "reason": f"已请求停止 {len(tgts)} 个训练任务（当前 step 结束后退出）"}


class LoRATrainerCore:
    """真实 LoRA/QLoRA/DPO 微调内核。

    用法：
        tr = LoRATrainerCore()
        for ev in tr.run(samples, steps=100):     # 流式，供 gRPC 转发
            ...
        tr.result                                  # 汇总，落训练历史
    """

    def __init__(self, adapter_dir: Path | str | None = None,
                 base_dir: Path | str | None = None):
        # 构造时解析，而不是用模块级常量：见 _resolve_adapter_dir 的说明
        self.adapter_dir = (Path(adapter_dir) if adapter_dir
                            else _resolve_adapter_dir())
        self.base_dir_hint = base_dir
        self.result = TrainResult(ok=False)
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self.stop_reason = ""
        self.global_step = 0
        self.total_steps = 0
        # 是否真的在跑：run() 是生成器，进入函数体即开始，最后一个事件 yield
        # 出去（done/error）或被异常打断即结束。取消必须只作用于在跑的实例。
        self.running = False

    # ---------------- 控制 ----------------
    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def request_stop(self, reason: str = "user") -> None:
        """外部（gRPC training:cancel）请求停止，并记下是谁要的。"""
        with self._lock:
            self.stop_reason = reason or "user"
        self._cancel.set()

    # ---------------- 状态持久化 ----------------
    def _state_path(self) -> Path:
        return self.adapter_dir / "trainer_state.json"

    def read_state(self) -> dict:
        try:
            p = self._state_path()
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def write_state(self, state: dict) -> bool:
        """落 trainer_state.json，返回是否真的落上。

        写不上不抛异常（状态文件坏掉不该让一次真训练失败），但调用方必须能
        知道「没落上」—— 否则下次续训读不到进度，用户却以为进度保住了。
        """
        try:
            self.adapter_dir.mkdir(parents=True, exist_ok=True)
            p = self._state_path()
            tmp = p.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            os.replace(tmp, p)
            return True
        except OSError:
            return False

    # ---------------- 加载 ----------------
    def _prepare(self, quant: str):
        """加载 tokenizer / 基座 / LoRA，返回 (torch, model, tokenizer, meta, err)。"""
        meta: dict = {}
        try:
            import torch
            from peft import LoraConfig, TaskType, get_peft_model
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:
            # 按运行形态给可执行建议：源码态才说 pip install；打包态产物内
            # 没有 pip，那句提示对用户是死指令，只会让人觉得「训练坏了」。
            if getattr(sys, "frozen", False):
                hint = ("当前为打包版，未内置 PyTorch 训练栈，且产物内没有 pip "
                        "无法在线补装。请改用源码模式运行 python main.py，"
                        "或使用内置训练栈的完整版后端。")
            else:
                hint = "请 pip install torch transformers peft accelerate"
            return None, None, None, meta, f"训练依赖未安装（{e}）。{hint}"
        mdir, err = _resolve_model_dir(self.base_dir_hint)
        if mdir is None:
            return None, None, None, meta, err
        device = "cpu"
        try:
            from .model import best_device
            device = best_device()
        except Exception:
            pass
        quant_applied = "none"
        load_kwargs: dict = {"trust_remote_code": True}
        if device != "cpu":
            load_kwargs.update({"device_map": "auto", "torch_dtype": "auto"})
        else:
            load_kwargs["low_cpu_mem_usage"] = True
        if quant in ("int4", "int8"):
            try:
                import bitsandbytes  # noqa: F401
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = (
                    BitsAndBytesConfig(load_inference_4bit=True)
                    if quant == "int4" else BitsAndBytesConfig(load_inference_8bit=True))
                load_kwargs.pop("torch_dtype", None)
                quant_applied = quant
            except Exception as e:
                meta["quant_fallback"] = f"{quant}→none（{type(e).__name__}: {e}）"
        try:
            tokenizer = AutoTokenizer.from_pretrained(str(mdir), trust_remote_code=True)
        except Exception as e:
            return None, None, None, meta, f"tokenizer 加载失败：{type(e).__name__}: {e}"
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        try:
            base = AutoModelForCausalLM.from_pretrained(str(mdir), **load_kwargs)
        except Exception as e:
            return None, None, None, meta, f"基座模型加载失败：{type(e).__name__}: {e}"
        try:
            base.config.use_cache = False
        except Exception:
            pass
        targets = detect_target_modules(base)
        if not targets:
            return None, None, tokenizer, meta, "基座里没找到可注入 LoRA 的线性层"
        meta.update({"target_modules": targets, "quant": quant_applied,
                     "device": device, "base_dir": str(mdir)})
        conv1d = has_conv1d_target(base, targets)
        meta["fan_in_fan_out"] = bool(conv1d)
        try:
            lora = LoraConfig(task_type=TaskType.CAUSAL_LM, r=self._r,
                              lora_alpha=self._r * 2, lora_dropout=0.05,
                              target_modules=targets, fan_in_fan_out=conv1d)
            model = get_peft_model(base, lora)
        except Exception as e:
            return None, None, tokenizer, meta, f"LoRA 包装失败：{type(e).__name__}: {e}"
        trainable = 0
        try:
            trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        except Exception:
            pass
        if trainable <= 0:      # 空适配器：PEFT 包了个寂寞，必须中止而不是假报成功
            return None, None, tokenizer, meta, ("LoRA 未命中任何层（可训参数 0），"
                                                 f"target_modules={targets} 与模型不匹配")
        meta["trainable_params"] = trainable
        if quant_applied != "none":
            try:
                from peft import prepare_model_for_kbit_training
                model = prepare_model_for_kbit_training(model)
            except Exception:
                pass
        try:
            model.train()
        except Exception:
            pass
        try:
            if device == "cpu":
                model = model.to("cpu")
        except Exception:
            pass
        return torch, model, tokenizer, meta, ""

    # ---------------- 主循环 ----------------
    def run(self, samples: list[TrainSample], **kw) -> Iterable[TrainEvent]:
        """带生命周期登记的 run()。

        running 标记必须包住整个生成器：run() 的实现是惰性求值的，注册表里
        的实例可能在「被创建」和「真正开始跑」之间被 training:cancel 看到，
        也可能在跑完后仍留在注册表里。所以：进入时置 True，无论正常结束、
        出错、还是调用方提前 close()（客户端断开）都在 finally 里置回 False，
        让 request_cancel() 只会打中真正在跑的那个。
        """
        self._cancel.clear()
        self.stop_reason = ""
        self.global_step = 0
        # 先置 running 再登记：反过来会留出一个「已登记但还没 running」的窗口，
        # 此时 training:cancel 打不中，只能回「没有正在运行的训练」。
        self.running = True
        _live_register(self)
        try:
            for ev in self._run(samples, **kw):
                yield ev
        finally:
            self.running = False

    def _run(self, samples: list[TrainSample], *, steps: int = 100,
            learning_rate: float = 2e-4, batch_size: int = 4,
            grad_accum: int = 1, lora_rank: int = 8, max_length: int = 256,
            quant: str = "none", eval_ratio: float = 0.1,
            save_steps: int = 0, resume: bool = False,
            pref: str = "sft", pref_pairs: list | None = None,
            dataset_tag: str = "") -> Iterable[TrainEvent]:
        """执行真实训练，逐步 yield TrainEvent。

        pref="dpo" 且给了 pref_pairs 时改用 DPOTrainer（accelerate 缺失时
        如实回退 SFT，并在 metadata 标注 fallback 原因）。
        """
        self._r = max(1, int(lora_rank or 8))
        # 登记与 running 标记在 run() 包装里做（_run 只被它调用），
        # 这里不要再登记一次，否则同一个实例在注册表里出现两遍，
        # request_cancel() 会报「停了 2 个」。
        t0 = time.time()
        samples = [s for s in (samples or []) if s and s.completion.strip()]
        yield TrainEvent(kind="init", status=f"准备训练：数据集 {len(samples)} 条 "
                         f"· lr={learning_rate:.1e} · rank={self._r}")

        if not samples:
            self.result = TrainResult(ok=False, reason="训练集为空")
            yield TrainEvent(kind="error", status="训练集为空，无法训练")
            return
        steps = max(1, int(steps or 100))

        torch, model, tokenizer, meta, err = self._prepare(quant)
        if model is None or tokenizer is None:
            self.result = TrainResult(ok=False, reason=err, metadata=meta)
            yield TrainEvent(kind="error", status=err)
            return

        # 调用方没显式开检查点/续训时，用配置值兜上：proto 里的
        # TrainingRequest 只有 steps/lr/batch/rank/dataset 五个字段，改不了，
        # 续训这件事只能由后端配置驱动（见 checkpoint_cfg）。
        save_steps, resume = _resolve_checkpoint_args(save_steps, resume, meta)

        # 划分训练/验证集（可复现：按顺序切，不打乱后再切）
        n_eval = max(0, int(len(samples) * eval_ratio)) if len(samples) > 4 else 0
        eval_samples = samples[-n_eval:] if n_eval else []
        train_pool = samples[:len(samples) - n_eval] or samples

        feats = [f for f in (build_example(tokenizer, s, max_length)
                             for s in train_pool) if f]
        if not feats:
            self.result = TrainResult(ok=False,
                                      reason="样本过短或模板异常，没有可学习的回复 token",
                                      metadata=meta)
            yield TrainEvent(kind="error", status="没有可学习的回复 token")
            return
        eval_feats = []
        if eval_samples:
            eval_feats = [f for f in (build_example(tokenizer, s, max_length)
                                      for s in eval_samples) if f]

        pad = _pad_id(tokenizer)
        use_dpo = pref == "dpo" and bool(pref_pairs)
        dpo_impl = None
        if use_dpo:
            try:
                from trl import DPOTrainer as _D, DPOConfig as _DC   # noqa: F401
                dpo_impl = "trl"
            except Exception:
                try:
                    from .dpo import manual_dpo_loss                  # noqa: F401
                    dpo_impl = "manual"
                except Exception:
                    dpo_impl = None
            if dpo_impl is None:
                meta["dpo_fallback"] = "sft（未装 trl 且内置 DPO 不可用）"
                use_dpo = False

        resume_step = 0
        prior_curve: list = []
        optimizer_state = None      # 只有 resume 成功才会带上；未续训时保持 None
        if resume:
            st = self.read_state()
            try:
                claimed = int(st.get("global_step", 0) or 0)
            except (TypeError, ValueError):
                claimed = 0
            # 只认「磁盘上真的存在」的检查点：state 说跑到 3 步、save_steps=2
            # 时只有 step2 落盘，这是正常情况。取不超过 claimed 的最大那个，
            # 并把 resume_step 校准成它 —— 步数必须跟着权重的真实进度算。
            ck = self._latest_checkpoint(claimed) if claimed else None
            if claimed and ck is None:
                # 关键：state 说「已经跑到 N 步」而一个可用权重都没有时，绝不能
                # 从全新的随机 LoRA 接着往下跑。旧实现正是如此 —— 它照样把
                # global_step 从 N 起算、把 N 之前那段 loss 曲线拼回来，界面显示
                # 「训练完成 N+M 步」，用户以为续上了，实际上这 M 步是在一个从零
                # 开始的新适配器上训的，前 N 步白算。
                #
                # 分两种情况如实处理，都不再谎报步数：
                #   a) 从来没落过检查点（旧版训练、或检查点间隔一直关着）——
                #      没有「丢失」可言，退回第 0 步重开，并告警说明；
                #   b) 落过检查点但现在读不到（被删 / 半截目录）—— 训练成果
                #      真的没了，这不是能靠「重开」糊过去的，直接拒绝本次训练。
                promised = self._promised_checkpoint(st)
                if not promised:
                    meta["resume_reset"] = (
                        f"trainer_state.json 记录 global_step={claimed}，但检查点"
                        "功能当时是关闭的，没有任何可续的权重。本次从第 0 步重新"
                        "开始（不再沿用旧步数）。")
                    yield TrainEvent(kind="warning", step=0, total_steps=steps,
                                     status=meta["resume_reset"])
                    claimed = 0
                    st = {}
                else:
                    meta["resume_denied"] = (
                        f"trainer_state.json 记录 global_step={claimed}，"
                        f"{promised}，无法续训。")
                    self.result = TrainResult(
                        ok=False,
                        reason=meta["resume_denied"] + " 想从头再训请把续训关掉"
                                                       "（training:checkpoint 0 off）。",
                        metadata=meta)
                    yield TrainEvent(kind="error", status=meta["resume_denied"],
                                     step=0, total_steps=steps)
                    return
            if ck is not None:
                resume_step = int(ck.name.replace("step", "") or 0)
                if resume_step < claimed:
                    meta["resume_behind_state"] = (
                        f"state 记录 {claimed} 步，可用的最新检查点只有 "
                        f"{resume_step} 步，本次从 {resume_step} 步续。")
                # 曲线也从检查点自带的快照取，而不是无条件相信 state：
                # state 与权重可能对不上（例如中途手工删过 checkpoints）。
                prior_curve = self._curve_for_checkpoint(ck, st, resume_step)
                try:
                    from peft import PeftModel
                    model = PeftModel.from_pretrained(model.base_model.model,
                                                      str(ck), is_trainable=True)
                    meta["resumed_from"] = str(ck)
                except Exception as e:
                    meta["resume_failed"] = f"{type(e).__name__}: {e}"
                    self.result = TrainResult(
                        ok=False,
                        reason=f"检查点存在但读不出来：{meta['resume_failed']}。"
                               "想从头再训请把「续训」关掉（resume=False）。",
                        metadata=meta)
                    yield TrainEvent(kind="error",
                                     status=f"续训失败：{meta['resume_failed']}",
                                     step=0, total_steps=steps)
                    return
                # 优化器状态一起续：AdamW 的两个动量项没了，等于学习率与
                # 梯度方向从头 warm，续训的头几步会把之前学到的方向冲掉 ——
                # 这不是「小差异」，是「续训」这件事名不副实。读不出来时如实
                # 标注，不假装续上了。
                opt_ckpt = ck / "optimizer.pt"
                # 这里只表示「读出了一个 state dict」；真正是否续上，
                # 要等优化器构造完 load_state_dict 之后才决定。
                meta["optimizer_restored"] = False
                if opt_ckpt.is_file():
                    try:
                        import torch as _t
                        # 注意：state dict 只放局部变量，绝不塞进 meta ——
                        # meta 会随 TrainResult 写进训练历史 JSON，torch 张量
                        # 序列化不了，塞进去等于埋一个「历史写不进去」的雷。
                        optimizer_state = _t.load(opt_ckpt, map_location="cpu",
                                                  weights_only=False)
                    except Exception as e:
                        meta["optimizer_restored"] = False
                        meta["optimizer_restore_failed"] = (
                            f"读不出来 {type(e).__name__}: {e}"
                            "（本次仅续权重，动量从头积累）")
                else:
                    meta["optimizer_restored_note"] = (
                        "该检查点没有 optimizer.pt（旧版训练落的盘），"
                        "本次只能续权重，优化器动量从头开始。")

        lr = float(learning_rate or 2e-4)
        bs = max(1, int(batch_size or 1))
        ga = max(1, int(grad_accum or 1))
        self.total_steps = steps + resume_step
        try:
            params = [p for p in model.parameters() if p.requires_grad]
            optimizer = torch.optim.AdamW(params, lr=lr)
        except Exception as e:
            self.result = TrainResult(ok=False, reason=f"优化器初始化失败：{e}",
                                      metadata=meta)
            yield TrainEvent(kind="error", status=f"优化器初始化失败：{e}")
            return
        if optimizer_state is not None:
            # 参数组对不上（换了 rank / target_modules / 基座）时 load 会抛，
            # 这时必须明说「优化器没续上」，而不是继续喊「续训成功」。
            try:
                optimizer.load_state_dict(optimizer_state)
                meta["optimizer_restored"] = True
            except Exception as e:
                meta["optimizer_restored"] = False
                meta["optimizer_restore_failed"] = (
                    f"{type(e).__name__}: {e}（本次仅续权重，动量从头积累）")

        curve: list = list(prior_curve)
        losses_win: list = []
        global_step = resume_step
        total = steps + resume_step
        save_every = int(save_steps or 0)
        masked_by = "chat_template" if all(
            f.get("masked_by") == "chat_template" for f in feats) else "degraded"
        meta.update({"batch_size": bs, "grad_accum": ga,
                     "prompt_mask": masked_by,
                     "n_train": len(feats), "n_eval": len(eval_feats),
                     "pref": "dpo" if use_dpo else "sft",
                     "dpo_impl": dpo_impl})
        # pinned 必须先初始化：GPU/MPS 机器上 if 分支不执行，finally 里
        # 引用未定义变量会抛 UnboundLocalError 并覆盖真实训练结果（修复）。
        pinned = None
        try:
            from .model import best_device
            if best_device() == "cpu" and hasattr(torch, "set_num_threads"):
                pinned = torch.get_num_threads()
                torch.set_num_threads(max(1, (os.cpu_count() or 2)))
                meta["threads"] = torch.get_num_threads()
        except Exception:
            pinned = None

        yield TrainEvent(kind="info", step=global_step, total_steps=total,
                         status=f"环境就绪：device={meta.get('device')} · "
                                f"targets={meta.get('target_modules')} · "
                                f"可训参数={meta.get('trainable_params')} · "
                                f"quant={meta.get('quant')} · "
                                f"prompt_mask={masked_by} · "
                                f"方式={'DPO' if use_dpo else 'SFT'}")

        model_dev = next(model.parameters()).device
        idx = 0
        optim_steps = 0
        eval_every = max(1, int(steps / 4 or 1))
        dpo_pairs = [p for p in (pref_pairs or [])
                     if p.get("prompt") and p.get("chosen") and p.get("rejected")]
        try:
            while global_step < total and not self.cancelled:
                # ---- 一个 step：SFT 或 DPO ----
                try:
                    if use_dpo and dpo_pairs:
                        chunk = [dpo_pairs[(global_step + k) % len(dpo_pairs)]
                                 for k in range(min(bs, len(dpo_pairs)))]
                        from .dpo import dpo_batch_loss
                        loss = dpo_batch_loss(model, tokenizer, chunk,
                                              max_length=max_length)
                        if loss is None:
                            use_dpo = False
                            meta["dpo_fallback"] = "sft（偏好对构不出有效 token）"
                            continue
                    else:
                        batch = []
                        for _ in range(bs):
                            batch.append(feats[idx % len(feats)])
                            idx += 1
                        data = collate(batch, pad)
                        data.pop("_trainable_tokens", None)
                        mb = data.pop("_masked_by", "unknown")
                        if mb != "chat_template":
                            meta["prompt_mask"] = "degraded"
                        data = {k: v.to(model_dev) for k, v in data.items()}
                        out = model(**data)
                        loss = out.loss
                except Exception as e:
                    meta["error"] = f"前向失败：{type(e).__name__}: {e}"
                    break
                if loss is None or not torch.isfinite(loss):
                    meta["nonfinite_loss"] = meta.get("nonfinite_loss", 0) + 1
                    global_step += 1
                    continue
                try:
                    (loss / ga).backward()
                except Exception as e:
                    meta["error"] = f"反向失败：{type(e).__name__}: {e}"
                    break
                val = float(loss.detach().item())
                losses_win.append(val)
                global_step += 1
                # 暴露进度给 training:cancel / training:status（它们在另一个
                # RPC 线程读，不能等 yield 之后才更新）
                self.global_step = global_step
                self.total_steps = total
                if global_step % ga == 0:
                    try:
                        torch.nn.utils.clip_grad_norm_(params, 1.0)
                    except Exception:
                        pass
                    optimizer.step()
                    optimizer.zero_grad()
                    optim_steps += 1
                curve.append(round(val, 4))
                yield TrainEvent(step=global_step, total_steps=total,
                                 loss=round(val, 4),
                                 status=f"训练中 {global_step - resume_step}/"
                                        f"{steps} loss={val:.4f}")
                if eval_feats and global_step % eval_every == 0:
                    ev = self._evaluate(torch, model, eval_feats, pad)
                    if ev is not None:
                        yield TrainEvent(step=global_step, total_steps=total,
                                         loss=round(val, 4), kind="eval",
                                         status=f"验证 loss={ev:.4f}",
                                         extra={"eval_loss": round(ev, 4)})
                if save_every and global_step % save_every == 0:
                    try:
                        ck_info = self._save_checkpoint(
                            model, tokenizer, global_step, curve=curve,
                            optimizer=optimizer, dataset_tag=dataset_tag)
                    except Exception as e:
                        # 落检查点的簿记不能把一次真训练带崩：出了异常就如实
                        # 当成「这个检查点没有」，续训依托没了，必须说出来。
                        ck_info = {"ok": False, "dir": "", "optimizer_ok": False,
                                   "error": f"{type(e).__name__}: {e}"}
                    if not ck_info["ok"]:
                        # 检查点落不下去，续训就没有依托 —— 必须当场告诉用户，
                        # 而不是等下次点「续训」才发现权重早丢了。
                        meta["checkpoint_error"] = ck_info["error"]
                        yield TrainEvent(
                            step=global_step, total_steps=total,
                            loss=round(val, 4), kind="warning",
                            status=f"检查点落盘失败（step {global_step}）："
                                   f"{ck_info['error']}，此后中断将无法续训")
                    elif not ck_info.get("state_ok", True):
                        # 权重在、进度不在：trainer 续训时读的是
                        # trainer_state.json，读不到就跟没有检查点一样。
                        meta["checkpoint_error"] = ck_info["error"]
                        yield TrainEvent(
                            step=global_step, total_steps=total,
                            loss=round(val, 4), kind="warning",
                            status=f"检查点权重已落盘，但进度写不进去"
                                   f"（step {global_step}）：{ck_info['error']}，"
                                   f"中断后无法续训")
                    elif not ck_info["optimizer_ok"]:
                        meta["checkpoint_optimizer_error"] = ck_info["error"]
                        yield TrainEvent(
                            step=global_step, total_steps=total,
                            loss=round(val, 4), kind="warning",
                            status=f"检查点已落盘，但优化器状态没落上："
                                   f"{ck_info['error']}（续训只能续权重）")
        finally:
            if pinned is not None:
                try:
                    torch.set_num_threads(pinned)
                except Exception:
                    pass

        if self.cancelled:
            meta["cancelled_at"] = global_step
            meta["cancel_reason"] = self.stop_reason or "user"
        # t0 在 _run 开头取；这里落总耗时，前端「每次训练耗时」才有真值，
        # 而不是靠 UI 自己的计时器猜（页面一关就没了）。
        meta["elapsed_sec"] = round(time.time() - t0, 2)
        meta["sec_per_step"] = (round(meta["elapsed_sec"] / max(1, global_step - resume_step), 3)
                                if curve else None)
        if not curve:
            reason = meta.get("error") or "训练未产生任何有效 step"
            self.result = TrainResult(ok=False, reason=reason, metadata=meta,
                                      device=str(meta.get("device", "")))
            yield TrainEvent(kind="error", status=reason, step=global_step,
                             total_steps=total)
            return

        saved_to = self._finalize(model, tokenizer, global_step)
        avg = round(sum(curve[-len(losses_win) or 1:]) / max(1, len(losses_win)), 4) \
            if losses_win else None
        self.result = TrainResult(
            ok=bool(saved_to), reason="" if saved_to else "适配器写入失败",
            steps=global_step - resume_step, final_loss=curve[-1], avg_loss=avg,
            loss_curve=curve, adapter_dir=str(saved_to or ""),
            device=str(meta.get("device", "")), real=True, metadata=meta)
        # 收尾写全局 state。这里必须把检查点相关的字段带上：write_state 是
        # 整体覆盖，漏掉 latest_checkpoint 会让下次续训读成「从来没落过检查点」，
        # 于是明明还在的 stepN 被当成旧状态、从第 0 步重开 —— 静默丢掉进度。
        prev = self.read_state()
        carry = {k: prev[k] for k in ("latest_checkpoint", "checkpoint_optimizer")
                 if prev.get(k)}
        self.write_state({"global_step": global_step, "loss_curve": curve[-512:],
                          "adapter_dir": str(saved_to or ""),
                          "updated_at": int(time.time()),
                          "dataset": dataset_tag, "steps_since_resume": optim_steps,
                          **carry})
        yield TrainEvent(step=total, total_steps=total, loss=curve[-1],
                         kind="done",
                         status=(f"训练已取消（{self.stop_reason or 'user'}）："
                                 f"跑到 {global_step - resume_step}/{steps} 步 · "
                                 f"最后 loss={curve[-1]:.4f} · "
                                 f"适配器→{saved_to or '未写入'}"
                                 if self.cancelled else
                                 f"训练完成 {global_step - resume_step} 步 · "
                                 f"最终 loss={curve[-1]:.4f} · "
                                 f"适配器→{saved_to or '未写入'}"),
                         extra={"adapter_dir": str(saved_to or ""),
                                "device": str(meta.get("device", "")),
                                "cancelled": bool(self.cancelled),
                                "real": True})

    # ---------------- 内部 ----------------
    def _evaluate(self, torch, model, eval_feats: list, pad: int) -> float | None:
        try:
            import random as _r
            batch = [_r.choice(eval_feats)]
            data = collate(batch, pad)
            # 键名必须与 collate 的产出一致（下划线前缀），否则弹不掉
            # 非张量键，model(**data) 必抛 → 验证 loss 永远是死代码（修复）。
            data.pop("_trainable_tokens", None)
            data.pop("_masked_by", None)
            was = model.training
            model.eval()
            with torch.no_grad():
                out = model(**{k: v.to(next(model.parameters()).device)
                               for k, v in data.items()})
            if was:
                model.train()
            v = float(out.loss.item())
            return v if v == v else None
        except Exception:
            return None

    def _rotate_checkpoints(self) -> list:
        """只保留最近 checkpoint_keep 个检查点，返回被删掉的那些名字。

        删的是「更旧的」快照，最新那个（续训真正会用）永远留着。判据与
        _latest_checkpoint 一致：只认 stepN 目录。非 stepN 的目录（用户自己
        放的备份）不动 —— 那是用户的文件，不是本模块的产物。
        """
        keep = max(1, int(checkpoint_cfg().get("keep") or DEFAULT_CHECKPOINT_KEEP))
        ck_root = self.adapter_dir / "checkpoints"
        if not ck_root.is_dir():
            return []
        steps: list[tuple[int, Path]] = []
        try:
            cands = list(ck_root.iterdir())
        except OSError:
            return []
        for p in cands:
            if not p.is_dir() or not p.name.startswith("step"):
                continue
            try:
                steps.append((int(p.name[4:]), p))
            except ValueError:
                continue
        steps.sort(key=lambda t: t[0])
        pruned: list[str] = []
        for _n, p in steps[:-keep] if keep < len(steps) else []:
            try:
                shutil.rmtree(p)
                pruned.append(p.name)
            except OSError:
                # 删不掉（占用/权限）不影响续训本身，但磁盘占用没降下来 ——
                # 由 training:adapter 的 checkpoints 列表如实呈现，不假装删了。
                pass
        return pruned

    def _promised_checkpoint(self, state: dict) -> str:
        """state 是否曾经承诺过「有检查点可续」。返回承诺内容，没承诺返回 ''。

        判据用 latest_checkpoint —— 只有 _save_checkpoint 会写它，即真的落过
        一次盘。旧版训练（没有这个字段）说「跑到 300 步」却一个检查点都没有，
        那是从来没有过，不是丢了：这时退回第 0 步重开是如实的，而把真的丢了的
        检查点也当成「从来没有」则是替用户掩盖数据丢失。
        """
        latest = str(state.get("latest_checkpoint") or "").strip()
        if not latest:
            return ""
        return (f"曾经落过检查点 {latest}，但它现在读不到了"
                f"（{self.adapter_dir / 'checkpoints'} 下没有可用权重）")

    def _latest_checkpoint(self, not_above: int) -> Path | None:
        """不超过 not_above 步、且**真的能当检查点用**的最新目录。

        判据用 adapter_config.json（PEFT 落盘的标志），不看 trainer_state.json
        —— 后者是全局状态文件的副本语义，会随每次落盘漂移。
        """
        ck_root = self.adapter_dir / "checkpoints"
        if not ck_root.is_dir():
            return None
        best: Path | None = None
        best_step = -1
        try:
            cands = list(ck_root.iterdir())
        except OSError:
            return None
        for p in cands:
            if not p.is_dir() or not p.name.startswith("step"):
                continue
            try:
                n = int(p.name[4:])
            except ValueError:
                continue
            if n > not_above or n <= best_step:
                continue
            if (p / "adapter_config.json").is_file():
                best, best_step = p, n
        return best

    def _curve_for_checkpoint(self, ck: Path, state: dict, step: int) -> list:
        """续训时的 loss 曲线起点：优先用检查点自带的那段，其次才退回全局 state。

        旧实现无条件相信 trainer_state.json 的 loss_curve。但
        _save_checkpoint 曾经把它清成空列表、而 _finalize 又只在结束时写全 ——
        于是「state 说 4 步、曲线只剩 2 个点」这种对不上的情况会一路带到前端。
        """
        p = ck / "trainer_state.json"
        if p.is_file():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if int(d.get("global_step", -1) or -1) == int(step):
                    return [float(x) for x in (d.get("loss_curve") or [])]
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        return [float(x) for x in (state.get("loss_curve") or [])]

    def _save_checkpoint(self, model, tokenizer, step: int,
                         curve: list | None = None,
                         optimizer=None, dataset_tag: str = "") -> dict:
        """落一个可续训的检查点：权重 + 优化器状态 + 那段曲线，各自成一份。

        返回 {ok, dir, optimizer_ok, error} —— 调用方要能把「优化器没落上」
        这件事如实告诉用户，而不是静默少一个文件。

        两个曾经的坑：
          1. 以前会把全局 trainer_state.json 的 loss_curve 清成 []，中断后
             曲线就没了，续训也接不回原来的点；
          2. 以前把全局 state 的 adapter_dir 改写成检查点目录，于是
             「training:adapter」读到的落点变成 checkpoints/stepN，推理端
             固定读 ADAPTER_DIR，界面却显示成检查点在的地方。
        现在全局 state 保持「推理落点 = adapter_dir」的原样，只更新进度，
        曲线快照写进检查点自己的 trainer_state.json。
        """
        info = {"ok": False, "dir": "", "optimizer_ok": False,
                "state_ok": False, "error": ""}
        try:
            ck = self.adapter_dir / "checkpoints" / f"step{step}"
            ck.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(str(ck))
            info["dir"] = str(ck)
            info["ok"] = True
        except Exception as e:
            info["error"] = f"{type(e).__name__}: {e}"
            return info
        if optimizer is not None:
            try:
                import torch as _t
                _t.save(optimizer.state_dict(), str(ck / "optimizer.pt"))
                info["optimizer_ok"] = True
            except Exception as e:
                info["error"] = f"优化器状态落盘失败：{type(e).__name__}: {e}"
        snap = {"global_step": step, "loss_curve": list(curve or [])[-512:],
                "adapter_dir": str(ck), "updated_at": int(time.time()),
                "dataset": dataset_tag, "checkpoint": True}
        try:
            (ck / "trainer_state.json").write_text(
                json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            info["error"] = (info["error"] + f" / 曲线快照写入失败：{e}").strip(" /")
        # 全局 state：只报进度与曲线，落点仍指向推理读的 adapter_dir
        written = self.write_state({"global_step": step,
                                    "loss_curve": list(curve or [])[-512:],
                                    "adapter_dir": str(self.adapter_dir),
                                    "updated_at": int(time.time()),
                                    "dataset": dataset_tag,
                                    "latest_checkpoint": str(ck),
                                    "checkpoint_optimizer": bool(info["optimizer_ok"])})
        info["state_ok"] = bool(written)
        if not written:
            # 权重落上了但进度没落上：续训读的是 trainer_state.json 里的
            # global_step / latest_checkpoint，读不到就等于这检查点白落
            # —— 必须照样报出来。
            info["error"] = (info["error"] + " / 状态更新失败：写不进去").strip(" /")
        # 检查点轮换：续训只需要最近那几个，而 optimizer.pt 比权重还大，
        # 长训练一路落下去能把磁盘吃空（此前生产环境从不落检查点，所以这个
        # 问题不存在；开了续训就必须同时把它管住）。
        info["pruned"] = self._rotate_checkpoints()
        return info

    def _finalize(self, model, tokenizer, step: int):
        """写 ADAPTER_DIR（推理端读取处）+ 规范名 lora_latest。"""
        wrote = None
        for target in (self.adapter_dir, self.adapter_dir / "lora_latest"):
            try:
                target.mkdir(parents=True, exist_ok=True)
                model.save_pretrained(str(target))
                try:
                    tokenizer.save_pretrained(str(target))
                except Exception:
                    pass
                if wrote is None:
                    wrote = target
            except Exception:
                continue
        return wrote


def train_lora(samples: list[TrainSample], *, on_event: Callable[[TrainEvent], None]
               | None = None, **kw) -> TrainResult:
    """一次性调用（非流式）。on_event 可拿进度。"""
    tr = LoRATrainerCore(**{k: kw.pop(k) for k in ("adapter_dir", "base_dir")
                            if k in kw})
    res: TrainResult | None = None
    for ev in tr.run(samples, **kw):
        if on_event:
            on_event(ev)
    return tr.result


def summarize_curve(curve: list, points: int = 60) -> list:
    """把长 loss 曲线降采样到 points 个点，供前端画图与持久化历史。"""
    if not curve or len(curve) <= points:
        return [float(x) for x in (curve or [])]
    out = []
    per = len(curve) / points
    for i in range(points):
        seg = curve[int(i * per):max(int((i + 1) * per), int(i * per) + 1)]
        out.append(round(sum(seg) / len(seg), 4))
    return out


# --------------------------------------------------------------------------- #
#  API 接入设置（OpenAI 兼容接口）
#
#  训练模块除本地 GPU 微调外，还应能接入外部 OpenAI 兼容 API（如 LM Studio /
#  vLLM / 各云端推理服务）做数据蒸馏、验收探测或远程推理。这里只负责
#  「接入设置的读写与连通性测试」，不假装替用户训练：
#    - 配置落在 config.training.api_*（api_enabled / api_base / api_key /
#      api_model），与 growth.checkpoint_* 一样走后端配置驱动；
#    - 读回时 api_key 一律打码（只留前 4 后 4），明文永不回流到前端；
#    - 测试连接用真实 HTTP 请求，结果如实返回，不做任何模拟成功。
# --------------------------------------------------------------------------- #

API_CFG_KEYS = {
    "enabled": "training.api_enabled",
    "base": "training.api_base",
    "key": "training.api_key",
    "model": "training.api_model",
}

_DEFAULT_API_BASE = "http://127.0.0.1:1234/v1"


def _mask_key(key: str) -> str:
    """API key 打码：保留前 4 后 4，中间用 ****。空值返回空串。"""
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def api_cfg() -> dict:
    """读取 API 接入设置。api_key 只回打码值，绝不回明文。

    向后兼容 + 收敛：优先读训练专属的 ``training.api_*``；如果那套没配，
    再回落到统一的 ``api.*``（core.api_config）。这样用户在设置页「API 配置」
    里配好端点后，训练页不用重复配一遍就能用 —— 修掉原来「配了等于没配」。
    """
    out = {"ok": True, "enabled": False, "base": _DEFAULT_API_BASE,
           "key_masked": "", "model": "", "has_key": False, "source": "default"}
    try:
        from .config import load as _load
        cfg = _load() or {}
        t = (cfg.get("training") or {})
        base = str(t.get("api_base", "") or "").strip()
        key = str(t.get("api_key", "") or "").strip()
        model = str(t.get("api_model", "") or "").strip()
        if base or key or model:
            out["enabled"] = bool(t.get("api_enabled", False))
            out["base"] = base or _DEFAULT_API_BASE
            out["key_masked"] = _mask_key(key)
            out["has_key"] = bool(key)
            out["model"] = model
            out["source"] = "training"
            return out
        # 训练专属没配 → 回落到统一 API 配置
        try:
            try:
                from . import api_config as _api
            except Exception:                                    # noqa: BLE001
                from api_config import _api                      # type: ignore
            u = _api.cfg()
            out["enabled"] = bool(u.get("enabled"))
            out["base"] = str(u.get("base") or _DEFAULT_API_BASE)
            out["key_masked"] = str(u.get("key_masked") or "")
            out["has_key"] = bool(u.get("has_key"))
            out["model"] = str(u.get("model") or "")
            out["source"] = "unified" if u.get("source") == "config" else "default"
        except Exception as e:                                   # noqa: BLE001
            out["ok"] = False
            out["error"] = f"{type(e).__name__}: {e}"
    except Exception as e:                                       # noqa: BLE001
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def api_set(field: str, value: str) -> dict:
    """写单个 API 接入设置项。返回写入后的打码快照。

    field ∈ enabled | base | key | model。写 base 时做 URL 基本校验
    （必须 http/https 开头），写 key 时允许空串=清除。
    """
    field = (field or "").strip().lower()
    if field not in API_CFG_KEYS:
        return {"ok": False,
                "error": f"未知设置项：{field}（可用：enabled/base/key/model）"}
    try:
        from .config import set_value as _set
        if field == "enabled":
            v = str(value or "").strip().lower()
            if v not in ("on", "off", "true", "false", "1", "0", "开", "关"):
                return {"ok": False,
                        "error": "enabled 只接受 on/off（或 true/false/1/0/开/关）"}
            _set(API_CFG_KEYS["enabled"], v in ("on", "true", "1", "开"))
        elif field == "base":
            base = (value or "").strip().rstrip("/")
            if base and not base.startswith(("http://", "https://")):
                return {"ok": False, "error": "base 必须以 http:// 或 https:// 开头"}
            _set(API_CFG_KEYS["base"], base)
        elif field == "key":
            _set(API_CFG_KEYS["key"], (value or "").strip())
        else:
            _set(API_CFG_KEYS["model"], (value or "").strip())
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "error": f"配置写入失败：{type(e).__name__}: {e}"}
    snap = api_cfg()
    snap["written"] = field
    return snap


def _resolve_api_plain() -> dict:
    """按 training.api_* → api.* 回落链读取**明文** API 配置（仅内部消费）。

    api_cfg() 按同一优先级解析但只回打码 key；测试连接需要真 key，
    故单开此函数。明文绝不外流：只在本进程内用于构造 HTTP 请求头，
    不进任何返回前端的快照。
    """
    out = {"base": "", "key": "", "model": ""}
    try:
        from .config import load as _load
        cfg = _load() or {}
        t = cfg.get("training") or {}
        a = cfg.get("api") or {}
        out["base"] = str(t.get("api_base") or a.get("base") or "").strip()
        out["key"] = str(t.get("api_key") or a.get("key") or "").strip()
        out["model"] = str(t.get("api_model") or a.get("model") or "").strip()
    except Exception:                                            # noqa: BLE001
        pass
    return out


def api_test(timeout: float = 10.0) -> dict:
    """对配置的 OpenAI 兼容端点发一次真实 /chat/completions 请求。

    结果如实返回：网络/鉴权/模型名任何一环失败都给真实原因，
    绝不返回伪造的 ok=True。
    """
    cfg = api_cfg()
    base = str(cfg.get("base") or "")
    # key/model 必须走与 api_cfg() 相同的回落链（training.api_* → api.*），
    # 且要明文：api_cfg() 只回打码值。此前 key/model 只从 training.api_*
    # 直读，用户在设置页配的统一 API（需鉴权端点）测试时必 401，而本地
    # 免鉴权端点却能过 —— 表现为「测试成功但训练/蒸馏时没用」。
    plain = _resolve_api_plain()
    key = plain.get("key") or None
    model = plain.get("model") or None
    if not base:
        return {"ok": False, "error": "未配置 api_base"}
    url = f"{base.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {"model": model or "default",
               "messages": [{"role": "user", "content": "ping"}],
               "max_tokens": 1, "temperature": 0}
    t0 = time.time()
    try:
        import requests
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        status, text = r.status_code, r.text
    except ImportError:
        # requests 缺席时用标准库兜底，测试能力不因依赖缺失而失效
        import urllib.request
        import urllib.error
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status, text = resp.status, resp.read().decode("utf-8", "replace")
        except Exception as e:                                   # noqa: BLE001
            return {"ok": False, "url": url,
                    "error": f"请求失败：{type(e).__name__}: {e}"}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "url": url,
                "error": f"请求失败：{type(e).__name__}: {e}"}
    latency = round((time.time() - t0) * 1000)
    if status != 200:
        return {"ok": False, "url": url, "status": status,
                "latency_ms": latency,
                "error": f"HTTP {status}：{text[:200]}"}
    try:
        body = json.loads(text)
        reply = (((body.get("choices") or [{}])[0].get("message") or {})
                 .get("content"))
        used_model = body.get("model") or model or ""
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "url": url, "latency_ms": latency,
                "error": f"响应不是合法 JSON：{type(e).__name__}: {e}"}
    return {"ok": True, "url": url, "status": 200, "latency_ms": latency,
            "model": used_model, "sample_reply": str(reply or "")[:80]}
