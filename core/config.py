#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 统一配置中心
=====================

历史上小凌（Python）与小玥（Electron/JS）各有一套配置；融合后由本模块统一托管：

    .star_core/xiaoling_config.json     ← 唯一真相（single source of truth）

* `DEFAULTS` 汇总了两边全部可配置项（模型 / 人格 / 语音 / 视觉 / 感知 / 平台 / 形象 / 成长）
* `load()` / `save()` / `patch()` 供 xl.py 与 3D 渲染层（renderer/settings.py）共用
* 老配置自动迁移：`.star_core/model_choice.txt`、旧 `xl_config.json` 等会被吸收
"""
from __future__ import annotations

import json
from pathlib import Path

from core.paths import APP_DIR, STAR_DIR

BASE_DIR = APP_DIR
STAR = STAR_DIR
CONFIG_PATH = STAR / 'xiaoling_config.json'

DEFAULTS = {
    'version': '1.0.0-fusion',
    'name': '小凌',
    'user_name': '你',
    'persona': '活泼',                       # 活泼 / 温柔 / 专业
    # ---- 模型与成长 ----
    'model': {
        'base_model': '自研2B模型',
        'hf_id': 'openbmb/MiniCPM5-2B',
        'ms_id': 'OpenBMB/MiniCPM5-2B',
        'quant': 'q4_k_m',
        'auto_download': True,
    },
    'growth': {
        'auto_check_after_train': True,      # 每轮训练后自动检查体积
        'retire_mode': 'delete',             # delete（默认，原基底自动删除）/ archive
        'keep_backup': False,
        'simulate_without_torch': False,
        'train_epochs': 2,
        'train_batch': 2,
        'train_lr': 0.0001,
    },
    # ---- 老师（蒸馏）----
    'deepseek_api_key': '暂未填入',
    'deepseek_base_url': 'https://api.deepseek.com/v1',
    'teacher_model': 'deepseek-chat',
    # ---- 对话 ----
    'temperature': 0.85,
    'max_tokens': 8192,
    'max_context_turns': 200,
    'short_term_turns': 80,
    'summary_every_turns': 30,
    'enable_voice': True,
    'voice_rate': 175,
    'auto_save_memory': True,
    'proactive': True,
    # ---- 形象（数字人）----
    'avatar': {
        'enabled': True,
        'model': '小凌.vrm',
        'scale': 1.0,
        'focus': 'bust',                 # bust（半身桌面宠物）/ full（全身）
        'transparent': True,
        'always_on_top': True,
        'read_aloud': True,              # 阅读模式：桌宠说话自动用当前角色音色朗读
        'idle_action': '待机站立.vrma',
        'dance_on_happy': True,
        'webm_fallback': True,
    },
    # ---- 小玥迁移能力 ----
    'rag': {'enabled': True, 'top_k': 4, 'dim': 512},
    'search': {'enabled': True, 'engine': 'duckduckgo', 'max_results': 5},
    'vision': {
        'enabled': True, 'api_key': '', 'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'model': 'qwen-vl-max', 'max_side': 1280, 'quality': 72,
    },
    'tts': {'engine': 'auto', 'minimax_key': '', 'minimax_voice': 'female-shaonv',
            'edge_voice': 'zh-CN-XiaoxiaoNeural', 'emotion_map': True},
    'asr': {'enabled': False, 'engine': 'baidu', 'baidu_key': '', 'baidu_secret': '',
            'seconds': 5, 'sample_rate': 16000},
    'perception': {'enabled': True, 'interval': 60, 'tell_user': False},
    'imagen': {'enabled': False, 'api_key': '', 'base_url': '', 'model': '', 'pipeline': ''},
    'reminder': {'enabled': True, 'notify_tts': True},
    'weather': {'engine': 'free', 'city': ''},
    'platforms': {
        'wechat': {'enabled': False, 'token': '', 'webhook': ''},
        'feishu': {'enabled': False, 'app_id': '', 'app_secret': '', 'webhook': ''},
        'qq': {'enabled': False, 'onebot_ws': 'ws://127.0.0.1:6700', 'group': ''},
        'wecom': {'enabled': False, 'corp_id': '', 'agent_id': '', 'secret': '', 'webhook': ''},
        'dingtalk': {'enabled': False, 'webhook': '', 'secret': ''},
        'telegram': {'enabled': False, 'bot_token': '', 'allowed_users': ''},
        'discord': {'enabled': False, 'bot_token': '', 'channel_id': ''},
    },
    'offline_mode': 'auto',
}


def _deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path: Path | None = None) -> dict:
    p = Path(path) if path else CONFIG_PATH
    cfg = dict(DEFAULTS)
    if p.exists():
        try:
            cfg = _deep_merge(DEFAULTS, json.loads(p.read_text(encoding='utf-8')))
        except Exception:                                            # noqa: BLE001
            pass
    # 兼容老版小凌的模型档位选择
    legacy = STAR / 'model_choice.txt'
    if legacy.exists():
        try:
            cfg['model']['base_model'] = legacy.read_text(encoding='utf-8').strip() or cfg['model']['base_model']
        except OSError:
            pass
    return cfg


def save(cfg: dict, path: Path | None = None) -> Path:
    p = Path(path) if path else CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding='utf-8')
    return p


def patch(changes: dict, path: Path | None = None) -> dict:
    cfg = _deep_merge(load(path), changes or {})
    save(cfg, path)
    return cfg


def get(dotted: str, default=None):
    """cfg.get('avatar.scale') 形式的取值。"""
    cur = load()
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur if cur is not None else default


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        print(save(load()))
    else:
        print(json.dumps(load(), ensure_ascii=False, indent=1))
