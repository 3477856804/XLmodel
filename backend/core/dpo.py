"""小凌 · 手动 DPO 损失（不依赖 trl / accelerate）

为什么单独写一个：growth.py 的数据仓库已经在收集 (prompt, chosen, rejected)
偏好对（用户点「不喜欢」+ 纠正后的答案就是天然负样本），把 rejected 只当
「不训」而不是负样本，等于浪费了一半信号。但 trl 的 DPOTrainer 强依赖
accelerate 和一份独立的 ref_model，CPU / 移动端跑不动，打包体积也不允许。

这里用 PEFT 的标准做法：
  1. 一次前向同时拿到 policy 的 logits；再用 disable_adapter() 上下文以
     no_grad 拿基座（无 LoRA）的 logprob 当 reference，省掉第二份权重。
  2. 每条序列只累计「非 IGNORE_INDEX 位置」的 logprob，即回复段的序列
     log 概率——prompt 段不参与，与 trainer.build_example 同一口径。
  3. loss = -logsigmoid(beta * ((pi_c - ref_c) - (pi_r - ref_r))).mean()

pi_* 保留 autograd 图（直接从 logits 算，不是先 .item() 再造假 tensor），
否则 loss.backward() 什么都更新不到，训练会「成功但权重没动」。
"""
from __future__ import annotations

IGNORE_INDEX = -100


def sequence_logprobs(logits, labels):
    """逐样本的回复段 log 概率之和，保留梯度。

    logits: (B, T, V) float；labels: (B, T)，IGNORE_INDEX 处不计。
    因果 LM 的错位：位置 i 的输出预测 token i+1，所以 logits 取 [:-1]、
    labels 取 [1:]。返回 (B,) 的 tensor。
    """
    import torch
    shift_logits = logits[:, :-1, :].contiguous()
    shift_labels = labels[:, 1:].contiguous()
    sel = (shift_labels != IGNORE_INDEX).float()
    safe = shift_labels.clamp(min=0).unsqueeze(2)
    logp = torch.log_softmax(shift_logits.float(), dim=-1)
    tok = logp.gather(2, safe).squeeze(2)
    return (tok * sel).sum(dim=1), sel.sum(dim=1)


def _encode_pair(tokenizer, pair: dict, system: str, max_length: int):
    from .trainer import TrainSample, build_example
    prompt = str(pair.get("prompt", "") or "")
    fc = build_example(tokenizer, TrainSample(
        prompt=prompt, completion=str(pair.get("chosen", "") or ""),
        system=system), max_length)
    fr = build_example(tokenizer, TrainSample(
        prompt=prompt, completion=str(pair.get("rejected", "") or ""),
        system=system), max_length)
    if not fc or not fr:
        return None
    if fc["trainable_tokens"] <= 0 or fr["trainable_tokens"] <= 0:
        return None
    return fc, fr


def dpo_batch_loss(model, tokenizer, pairs: list, *, beta: float = 0.1,
                   system: str = "", max_length: int = 256):
    """一批偏好对的 DPO loss；返回标量 tensor（可 backward），无有效对返回 None。

    pairs: [{"prompt": str, "chosen": str, "rejected": str}, ...]
    """
    import torch
    from .trainer import collate, _pad_id
    feats: list = []
    n_chosen = 0
    for p in pairs or []:
        enc = _encode_pair(tokenizer, p, system, max_length)
        if enc is None:
            continue
        fc, fr = enc
        feats.append(fc)
        feats.append(fr)
        n_chosen += 1
    if n_chosen == 0:
        return None
    # 每条各自成 batch 元素：chosen/rejected 交替，索引 2k / 2k+1
    pad = _pad_id(tokenizer)
    rows = []
    for f in feats:
        rows.append({"input_ids": f["input_ids"], "labels": f["labels"],
                     "attention_mask": f["attention_mask"]})
    data = collate(rows, pad)
    data.pop("_trainable_tokens", None)
    data.pop("_masked_by", None)
    dev = next(model.parameters()).device
    data = {k: v.to(dev) for k, v in data.items()}
    labels = data["labels"]

    pi, _n = sequence_logprobs(model(**data).logits, labels)
    with torch.no_grad():
        try:
            with model.disable_adapter():
                ref, _ = sequence_logprobs(model(**data).logits, labels)
        except AttributeError:
            ref, _ = sequence_logprobs(model(**data).logits, labels)
    ref = ref.detach()

    # 偶数下标 = chosen，奇数 = rejected
    pi_c, pi_r = pi[0::2], pi[1::2]
    ref_c, ref_r = ref[0::2], ref[1::2]
    pref = (pi_c - ref_c) - (pi_r - ref_r)
    return -torch.nn.functional.logsigmoid(float(beta) * pref).mean()


def manual_dpo_loss(model, tokenizer, pairs: list, *, beta: float = 0.1,
                    system: str = "", max_length: int = 256):
    """兼容别名。"""
    return dpo_batch_loss(model, tokenizer, pairs, beta=beta, system=system,
                          max_length=max_length)
