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
    'version': '0.0.2',
    'name': '小凌',
    'user_name': '你',
    'persona': '活泼',                       # 活泼 / 温柔 / 专业
    'language': 'zh',                        # 界面语言：zh / en（实现见 renderer/i18n.py）
    # ---- 模型与成长 ----
    'model': {
        'base_model': '自研2B模型',
        'hf_id': 'openbmb/MiniCPM5-2B',
        'ms_id': 'OpenBMB/MiniCPM5-2B',
        'quant': 'q4_k_m',
        'auto_download': True,
    },
    'growth': {
        'auto_train': True,                  # 满足触发条件就自动训练
        'auto_check_after_train': True,      # 每轮训练后自动检查体积
        'retire_mode': 'trash',              # trash（默认：移入回收区，稳定期后清理）/ delete / archive
        'keep_backup': False,
        'simulate_without_torch': False,
        'train_epochs': 2,
        'train_batch': 2,
        'train_lr': 0.0001,
        # 触发策略（设计文档 2.3）
        'min_samples': 500,                  # 高质量样本数达标
        'manual_min_samples': 20,            # 手动说「蒸馏」时的放宽阈值
        'min_interval_hours': 24,            # 距上次训练间隔
        'require_device_idle': True,         # 设备空闲（不在游戏/会议）
        'require_power_ok': True,            # 电量/温度允许
        'allow_train_on_cpu': False,         # 无 GPU 时是否仍然训练
        # 训练与防遗忘（设计文档 2.4 / 7.1）
        'base_mix_ratio': 0.15,              # 混入 10%~20% 通用语料
        'init_rank': 8,                      # 新一代 LoRA 起始 rank
        'max_rank': 256,                     # rank 上限（超过改用多适配器堆叠）
        'min_quality': 0.5,                  # 训练样本最低质量分
        # 晋升评估（设计文档 2.5 / 7.3）
        'require_eval': True,                # 是否启用三条件评估
        'pass_threshold': 0.9,               # 条件 C 通用基准通过率阈值
        # 生命周期（设计文档 4 / 7.6）
        'keep_generations': 2,               # 保留代数（当前 + 上一代）
        'max_generations': 5,                # 最多晋升代数
        'max_total_bytes': 10737418240,      # 总体积上限（10GB）
        'stability_hours': 24,               # 稳定期：小时
        'stability_rounds': 100,             # 稳定期：对话轮次
        # 蒸馏节流（设计文档 3.4）
        'distill_enabled': True,             # 关闭则纯本地成长
        'distill_daily_limit': 200,          # 每日 API 调用上限
        'teacher_price_in': 1.0,             # 示例单价（元/百万 token，非官方报价）
        'teacher_price_out': 2.0,
        # 用户控制（设计文档 7.7）
        'paused': False,                     # 一键暂停成长
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
    # ---- 环境配置向导（零配置直接启动：renderer/wizard.py）----
    'wizard': {
        'never_show': False,        # 用户勾了「不再提醒」→ 启动时不再自动弹向导
        'skip_until_change': '',    # 跳过时的环境指纹；指纹不变就不再自动弹
        'mirror': 'tuna',           # pip 镜像源：tuna / aliyun / official
    },
    'render': {
        'backend': 'auto',          # auto / gpu / soft / osmesa（对应 XIAOLING_RENDER_BACKEND）
    },
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


# --------------------------------------------------------------------------- #
#  历史 .env 迁移
#
#  旧版 setup_kali.sh 把 Key 写进 <项目根>/.env 的 DEEPSEEK_API_KEY / API_BASE_URL，
#  但程序从来只读 .star_core/xiaoling_config.json 的 deepseek_api_key /
#  deepseek_base_url —— 键名和文件都不是同一个，所以那条配置一直是死的
#  （用户按脚本配完，蒸馏老师仍然离线）。
#
#  现在统一到 config.json（单一真相源），这里负责把老用户的 .env 搬过来，
#  避免他们丢配置。**只读 .env，不删除它**，迁移后提示用户可自行删除。
# --------------------------------------------------------------------------- #
_LEGACY_ENV_MAP = {
    'DEEPSEEK_API_KEY': 'deepseek_api_key',
    'DEEPSEEK_BASE_URL': 'deepseek_base_url',
    'API_BASE_URL': 'deepseek_base_url',          # 旧脚本用的就是这个键名
    'TEACHER_MODEL': 'teacher_model',
}


def _parse_env_file(path: Path) -> dict:
    """极简 .env 解析（不引入 python-dotenv）。支持 export 前缀、引号、# 注释。"""
    out = {}
    try:
        for raw in Path(path).read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.lower().startswith('export '):
                line = line[7:].strip()
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k, v = k.strip(), v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1]
            if k:
                out[k] = v
    except Exception:                                                # noqa: BLE001
        pass
    return out


def migrate_legacy_env(env_path: Path | None = None, log=None) -> dict:
    """把历史 .env 的 DeepSeek 配置迁移进 xiaoling_config.json。

    只迁移「config.json 里还没填」的键，绝不覆盖用户在 UI 里已经设好的值。
    返回 {'found', 'migrated', 'skipped', 'path', 'env_path'}
    """
    say = log or (lambda *a, **k: None)
    env_file = Path(env_path) if env_path else (APP_DIR / '.env')
    res = {'found': False, 'migrated': [], 'skipped': [], 'keys': {},
           'path': str(CONFIG_PATH), 'env_path': str(env_file)}
    if not env_file.exists():
        return res
    parsed = _parse_env_file(env_file)
    picked = {dst: parsed[src] for src, dst in _LEGACY_ENV_MAP.items()
              if parsed.get(src)}
    if not picked:
        return res
    res['found'] = True
    res['keys'] = dict(picked)

    cur = load()
    changes = {}
    for k, v in picked.items():
        now = cur.get(k)
        # 判定"用户是否真的设过"：空 / 占位符 / 仍等于出厂默认值 → 都算没设过。
        # 注意不能只判空：deepseek_base_url 的默认值就是官方 URL，
        # 若只判空，用户在中转站 .env 里配的地址会被永久跳过。
        default = DEFAULTS.get(k)
        unset = (now in (None, '', '暂未填入')) or (default is not None and now == default)
        if unset:
            changes[k] = v
        else:
            res['skipped'].append(k)
    if changes:
        patch(changes)
        res['migrated'] = sorted(changes)
        say(f'  [配置] 已从历史 .env 迁移 {len(changes)} 项到 {CONFIG_PATH.name}：'
            f'{"、".join(sorted(changes))}')
    if res['skipped']:
        say(f'  [配置] 已存在配置、未覆盖：{"、".join(res["skipped"])}')
    if res['migrated'] or res['skipped']:
        say(f'  [配置] 迁移完成，可自行删除旧文件：{env_file}（程序不再读它）')
    return res


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        print(save(load()))
    else:
        print(json.dumps(load(), ensure_ascii=False, indent=1))
