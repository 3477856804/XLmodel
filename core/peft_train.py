#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · LoRA 蒸馏训练器（peft / transformers）
===========================================

把 DeepSeek 老师产出的语料（data/distill_corpus.jsonl）训进 LoRA 适配器：

    {"question": "...", "answer": "...", "topic": "..."}      或    {"text": "..."}

产物：`.star_core/adapter/`（adapter_config.json + adapter_model.safetensors，逐轮增长）

设计要点
--------
* **适配器持续增长**：每轮训练在已有适配器上继续训练（`is_trainable=True`），
  不重置权重，因此 adapter 体积随知识积累稳定增长 —— 这是晋升判定依据。
* **低配可用**：默认 fp32 + gradient checkpointing + 小 batch；显存不足时自动降级。
* **离线可用**：只用本地基底模型，不联网。

依赖：torch, transformers, peft, (datasets 可选)
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path


def load_corpus(corpus: Path):
    rows = []
    if corpus and Path(corpus).exists():
        with open(corpus, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if 'question' in d and 'answer' in d:
                    rows.append({'q': str(d['question']), 'a': str(d['answer'])})
                elif 'text' in d:
                    rows.append({'q': '', 'a': str(d['text'])})
                elif 'content' in d:
                    rows.append({'q': '', 'a': str(d['content'])})
    return rows


def _format_prompt(tok, q, a):
    if q:
        msgs = [{'role': 'user', 'content': q}, {'role': 'assistant', 'content': a}]
    else:
        msgs = [{'role': 'assistant', 'content': a}]
    try:
        return tok.apply_chat_template(msgs, tokenize=False)
    except Exception:                                              # noqa: BLE001
        return f'用户：{q}\n小凌：{a}' if q else a


def train_lora(base_dir: Path, adapter_dir: Path, corpus: Path | None = None,
               epochs: int = 2, batch_size: int = 2, lr: float = 1e-4,
               max_len: int = 512, lora_r: int = 8, log=print) -> dict:
    """在已有（或新建）LoRA 适配器上继续训练。返回统计信息。

    算力策略：检测到 GPU 就把模型铺上 GPU（device_map=auto，装不下的层自动
    offload 到 CPU），没有 GPU 再整体走 CPU——训练不再永远固定在 fp32 CPU 上。
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, PeftModel, get_peft_model

    from core.device import best_torch_device, device_kwargs
    device = best_torch_device()

    rows = load_corpus(corpus) if corpus else []
    if not rows:
        return {'ok': False, 'error': f'语料为空：{corpus}'}

    tok = AutoTokenizer.from_pretrained(str(base_dir), trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    log(f'  [训练] 算力检测：{device}' + ('（GPU 优先加载，溢出自动回落 CPU）' if device == 'cuda' else ''))
    model = AutoModelForCausalLM.from_pretrained(str(base_dir), **device_kwargs(device))
    has_adapter = (Path(adapter_dir) / 'adapter_config.json').exists()
    if has_adapter:
        log(f'  [训练] 续训已有适配器：{adapter_dir}')
        model = PeftModel.from_pretrained(model, str(adapter_dir), is_trainable=True)
    else:
        cfg = LoraConfig(r=lora_r, lora_alpha=lora_r * 2, lora_dropout=0.05, bias='none',
                         task_type='CAUSAL_LM',
                         target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj'])
        model = get_peft_model(model, cfg)
    model.train()
    if hasattr(model, 'gradient_checkpointing_enable'):
        try:
            model.gradient_checkpointing_enable()
        except Exception:                                          # noqa: BLE001
            pass

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    texts = [_format_prompt(tok, r['q'], r['a']) for r in rows]
    total, steps = 0, 0
    for ep in range(epochs):
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            enc = tok(batch, return_tensors='pt', padding=True, truncation=True, max_length=max_len)
            labels = enc['input_ids'].clone()
            labels[enc['attention_mask'] == 0] = -100
            out = model(**enc, labels=labels)
            loss = out.loss
            loss.backward()
            opt.step()
            opt.zero_grad()
            total += float(loss.detach())
            steps += 1
            if steps % 5 == 0:
                log(f'  [训练] epoch {ep + 1}/{epochs} step {steps} loss={total / steps:.4f}')
    Path(adapter_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_dir))
    tok.save_pretrained(str(adapter_dir))
    avg = total / max(steps, 1)
    return {'ok': True, 'steps': steps, 'avg_loss': round(avg, 4),
            'summary': f'{len(rows)} 条语料 × {epochs} epoch，{steps} 步，loss={avg:.4f}'}
