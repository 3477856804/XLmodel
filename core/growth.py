#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 成长闭环引擎 v2（融合版 + 设计文档全量落地）
=====================================================

小凌的核心机制：**基底模型 + LoRA 适配器 → 蒸馏训练（DeepSeek 老师）→ 适配器持续增长
→ 每轮训练后自动检查 → 三条件达标 → 合并 → 成为自研模型 → 原基底退役
→ 适配器晋升为新基底 → 完全脱离原基底 → 循环成长**

v2 相对 v1 的补全（对应《小凌个人模型成长管线设计文档》）：

    触发策略（2.3）     样本 ≥ 阈值 + 距上次 ≥ 24h + 设备空闲 + 电量温度允许 + 用户未暂停
    数据来源（2.2）     接入 core.growth_store：真实对话 / 点赞点踩 / 纠正 / 蒸馏 / 导入
    防遗忘（2.4）       每轮混入 10%~20% 通用语料（`growth.base_mix_ratio`）
    晋升三条件（2.5）   A 体积 + B 用户专属验证集 loss + C 通用基准通过率（core.eval）
    升 rank（7.1）      不达标时自动升 rank（8→16→…→上限，旧权重复制，core.rank）
    退役与生命周期（4） trash/ 退役 + 24h/100 轮稳定期 + 保留代数 GC + 回滚 + 导出（core.lifecycle）
    增长上限（7.6）     最多 N 代 / 总体积上限，可手动解除
    算力策略（6）       读 core.device 显存档位，决定是否训练、batch/accum/量化
    蒸馏节流（3.4）     core.throttle：缓存 / 日限流 / 开关 / 成本估算
    用户控制（7.7）     暂停 / 恢复 / 手动触发 / 回滚 / 导出 / 查看与删除样本

用法：
    python3 -m core.growth status                 # 成长状态（含触发条件、生命周期、算力）
    python3 -m core.growth report                 # 人类可读成长报告
    python3 -m core.growth trigger                # 只看"现在能不能训练，为什么"
    python3 -m core.growth check                  # 检查并（必要时）合并晋升
    python3 -m core.growth train --epochs 2       # 蒸馏训练一轮 + 自动检查
    python3 -m core.growth train --manual         # 手动触发（放宽样本数要求）
    python3 -m core.growth simulate               # 干跑一次完整晋升流程（不动真模型）
    python3 -m core.growth pause | resume         # 暂停 / 恢复成长
    python3 -m core.growth rank                   # 查看/升 LoRA rank
    python3 -m core.growth eval                   # 跑晋升三条件评估
    python3 -m core.growth rollback [--gen N]     # 回滚到旧代
    python3 -m core.growth gc [--keep N]          # 清理旧代（含稳定期校验）
    python3 -m core.growth export --path x.zip    # 导出自己的模型
    python3 -m core.growth samples                # 查看训练样本与蒸馏节流状态
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from core.paths import APP_DIR, STAR_DIR

BASE_DIR = APP_DIR
STAR = STAR_DIR
BASE_DIR_MODEL = STAR / 'XLmodel'
ADAPTER_DIR = STAR / 'adapter'
GROWTH_DIR = STAR / 'growth'
JOURNAL = GROWTH_DIR / 'journal.jsonl'
STATE = GROWTH_DIR / 'replacement_state.json'
CORPUS_DIR = BASE_DIR / '数据'

MODEL_WEIGHT_EXT = ('.safetensors', '.bin', '.gguf', '.pt', '.pth')
ADAPTER_WEIGHT_EXT = ('.safetensors', '.bin', '.pt', '.pth')

# 成长配置默认值（可被 .star_core/xiaoling_config.json 的 growth 段覆盖）
GROWTH_DEFAULTS = {
    'auto_train': True,               # 满足触发条件就自动训练
    'auto_check_after_train': True,   # 每轮训练后自动检查体积
    'retire_mode': 'trash',           # trash（默认，稳定期后清理）/ delete / archive
    'keep_backup': False,
    'simulate_without_torch': False,
    'train_epochs': 2,
    'train_batch': 2,
    'train_lr': 0.0001,
    # —— 触发策略（文档 2.3）——
    'min_samples': 500,
    'manual_min_samples': 20,         # 用户手动说「蒸馏」时的放宽阈值
    'min_interval_hours': 24,
    'require_device_idle': True,
    'require_power_ok': True,
    'allow_train_on_cpu': False,
    # —— 训练与防遗忘 ——
    'base_mix_ratio': 0.15,           # 混入 10%~20% 通用语料
    'init_rank': 8,
    'max_rank': 256,
    'min_quality': 0.5,
    # —— 晋升评估（文档 2.5 / 7.3）——
    'require_eval': True,
    'pass_threshold': 0.90,
    # —— 生命周期（文档 4 / 7.6）——
    'keep_generations': 2,
    'max_generations': 5,
    'max_total_bytes': 10 * 1024 ** 3,
    'stability_hours': 24,
    'stability_rounds': 100,
    # —— 蒸馏节流（文档 3.4）——
    'distill_enabled': True,
    'distill_daily_limit': 200,
    'teacher_price_in': 1.0,
    'teacher_price_out': 2.0,
    # —— 用户控制（文档 7.7）——
    'paused': False,
}


def human(n: float) -> str:
    for unit, div in (('GB', 1024 ** 3), ('MB', 1024 ** 2), ('KB', 1024)):
        if n >= div:
            return f'{n / div:.2f} {unit}'
    return f'{int(n)} B'


def detect_adapter_dir(star: Path) -> Path:
    """兼容两种历史布局：
       · 新版：.star_core/adapter/
       · 旧版：.star_core/  （adapter_config.json / adapter_model.safetensors 直接躺在里面）
    """
    marks = ('adapter_config.json', 'adapter_model.safetensors', 'adapter.bin', 'adapter.pt')
    new = star / 'adapter'
    if any((new / m).exists() for m in marks):
        return new
    if any((star / m).exists() for m in marks):
        return star
    return new


class GrowthEngine:
    """小凌的成长闭环：数据 → 触发 → 训练 → 三条件 → 合并晋升 → 退役 → 循环。"""

    def __init__(self, base_dir: Path | str = BASE_DIR, base_model_dir: Path | None = None,
                 adapter_dir: Path | None = None, log=print, dry_run: bool = False):
        self.base_dir = Path(base_dir)
        self.star = self.base_dir / '.star_core'
        self.base_model_dir = Path(base_model_dir) if base_model_dir else self.star / 'XLmodel'
        self.adapter_dir = Path(adapter_dir) if adapter_dir else detect_adapter_dir(self.star)
        self.growth_dir = self.star / 'growth'
        self.journal_path = self.growth_dir / 'journal.jsonl'
        self.state_path = self.growth_dir / 'replacement_state.json'
        self.corpus_dir = self.base_dir / '数据'
        self.log = log or (lambda *a, **k: None)
        self.dry_run = dry_run
        self.growth_dir.mkdir(parents=True, exist_ok=True)
        self.adapter_dir.mkdir(parents=True, exist_ok=True)
        self._store = None
        self._lifecycle = None
        self._throttle = None

    # ------------------------------------------------------------------ 配置
    def config(self) -> dict:
        cfg = dict(GROWTH_DEFAULTS)
        p = self.star / 'xiaoling_config.json'
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                g = data.get('growth') or {}
                for k, v in g.items():
                    if v is not None:
                        cfg[k] = v
                cfg['paused'] = bool(g.get('paused', data.get('paused', cfg['paused'])))
            except Exception:                                        # noqa: BLE001
                pass
        return cfg

    def cfg(self, key, default=None):
        return self.config().get(key, GROWTH_DEFAULTS.get(key, default))

    # ------------------------------------------------------- 子模块（延迟建）
    @property
    def store(self):
        if self._store is None:
            from core.growth_store import GrowthStore
            self._store = GrowthStore(self.base_dir)
        return self._store

    @property
    def lifecycle(self):
        if self._lifecycle is None:
            from core.lifecycle import ModelLifecycle
            self._lifecycle = ModelLifecycle(
                self.base_dir, log=self.log,
                keep_generations=int(self.cfg('keep_generations')),
                max_generations=int(self.cfg('max_generations')),
                max_total_bytes=int(self.cfg('max_total_bytes')),
                stability_hours=float(self.cfg('stability_hours')),
                stability_rounds=int(self.cfg('stability_rounds')))
        return self._lifecycle

    @property
    def throttle(self):
        if self._throttle is None:
            from core.throttle import DistillThrottle
            self._throttle = DistillThrottle(
                self.base_dir, enabled=bool(self.cfg('distill_enabled')),
                daily_limit=int(self.cfg('distill_daily_limit')),
                price_in=float(self.cfg('teacher_price_in')),
                price_out=float(self.cfg('teacher_price_out')))
        return self._throttle

    # ------------------------------------------------------------------ 量测
    @staticmethod
    def _dir_weight_bytes(d: Path, exts=MODEL_WEIGHT_EXT) -> int:
        if not d or not d.exists():
            return 0
        total = 0
        for p in d.rglob('*'):
            try:
                if p.is_file() and (not exts or p.suffix.lower() in exts):
                    total += p.stat().st_size
            except OSError:
                pass
        return total

    @property
    def base_bytes(self) -> int:
        return self._dir_weight_bytes(self.base_model_dir)

    @property
    def adapter_bytes(self) -> int:
        return self._dir_weight_bytes(self.adapter_dir, ADAPTER_WEIGHT_EXT)

    def progress_percent(self) -> float:
        """适配器体积 / 基底体积 × 100。无基底时无法度量进度，返回 0。"""
        b = self.base_bytes
        if b <= 0:
            return 0.0
        return min(100.0, self.adapter_bytes / b * 100.0)

    def corpus_items(self) -> int:
        n = 0
        for p in self.corpus_dir.glob('*.jsonl'):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    n += sum(1 for line in f if line.strip())
            except OSError:
                continue
        return n

    def state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding='utf-8'))
            except Exception:
                return {}
        return {}

    def is_self_research(self) -> bool:
        return bool(self.state().get('self_research')) or self.base_bytes == 0

    def is_paused(self) -> bool:
        return bool(self.state().get('paused', self.cfg('paused')))

    def status(self) -> dict:
        st = self.state()
        trainable = self.should_train(manual=True)
        return {
            'base_bytes': self.base_bytes,
            'base_human': human(self.base_bytes),
            'adapter_bytes': self.adapter_bytes,
            'adapter_human': human(self.adapter_bytes),
            'progress_percent': round(self.progress_percent(), 2),
            'rounds': int(st.get('rounds', 0)),
            'self_research': bool(st.get('self_research', False)),
            'promotions': int(st.get('promotions', 0)),
            'corpus_items': self.corpus_items(),
            'base_model_dir': str(self.base_model_dir),
            'adapter_dir': str(self.adapter_dir),
            'stage': self.stage_text(),
            'paused': self.is_paused(),
            'rank': self.rank_status().get('rank', 0),
            'auto_train': bool(self.cfg('auto_train')),
            'can_train_now': bool(trainable.get('ok')),
            'train_blockers': trainable.get('reasons', []),
            'config': {k: self.cfg(k) for k in ('min_samples', 'min_interval_hours', 'base_mix_ratio',
                                                'require_eval', 'pass_threshold', 'keep_generations',
                                                'max_generations', 'retire_mode')},
        }

    def stage_text(self) -> str:
        p = self.progress_percent()
        if self.is_paused():
            return '成长已暂停（用户手动暂停，可随时恢复）'
        if self.state().get('self_research'):
            return (f"纯自研模型（第 {self.state().get('promotions', 1)} 代·已脱离原基底）"
                    f"，当前适配器为自研基底的 {p:.1f}%")
        if self.base_bytes == 0 and self.adapter_bytes == 0:
            return '尚未安装基底模型'
        if self.base_bytes == 0:
            return f'无基底权重，适配器 {human(self.adapter_bytes)} 独自积累中'
        if p >= 100:
            return '适配器体积已达基底（进入三条件评估）'
        return f'成长中：适配器为基底的 {p:.1f}%'

    def report(self) -> str:
        s = self.status()
        bar_len = 28
        filled = int(bar_len * s['progress_percent'] / 100)
        bar = '█' * filled + '░' * (bar_len - filled)
        st = self.state()
        lines = [
            '小凌成长报告',
            f"  阶段：{s['stage']}",
            f"  基底：{s['base_human']}   适配器：{s['adapter_human']}   LoRA rank：r={s['rank']}",
            f"  进度：[{bar}] {s['progress_percent']:.1f}%",
            f"  训练轮次：{s['rounds']}   晋升次数：{s['promotions']}   语料：{s['corpus_items']} 条",
            f"  触发策略：样本 ≥ {s['config']['min_samples']}｜间隔 ≥ {s['config']['min_interval_hours']}h"
            f"｜{'需' if self.cfg('require_device_idle') else '不校验'}设备空闲"
            f"｜防遗忘混入 {float(s['config']['base_mix_ratio']) * 100:.0f}%",
            f"  晋升评估：{'开启' if s['config']['require_eval'] else '关闭'}"
            f"（通用基准阈值 {float(s['config']['pass_threshold']) * 100:.0f}%）",
            f"  当前可否训练：{'可以' if s['can_train_now'] else '暂不可 —— ' + '；'.join(s['train_blockers'])}",
        ]
        if st.get('last_train_at'):
            lines.append(f"  上次训练：{st['last_train_at']}")
        try:
            ds = self.store.stats()
            lines.append(f"  数据仓库：{ds['total']} 条记录（去重后 {ds['unique']}）"
                         f"｜待训练 {ds['pending']}｜已训练 {ds['used_in_training']}"
                         f"｜DPO 偏好对 {ds['dpo_pairs']}｜平均质量分 {ds['avg_quality']}")
        except Exception as e:                                       # noqa: BLE001
            lines.append(f"  数据仓库：读取失败（{type(e).__name__}）")
        return '\n'.join(lines)

    # ------------------------------------------------------------------ 日志
    def _journal(self, event: str, **data):
        rec = {'time': datetime.now().isoformat(timespec='seconds'), 'event': event, **data}
        try:
            self.growth_dir.mkdir(parents=True, exist_ok=True)
            with open(self.journal_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        except OSError:
            pass
        return rec

    def _save_state(self, **patch):
        st = self.state()
        st.update(patch)
        st['updated_at'] = datetime.now().isoformat(timespec='seconds')
        self.state_path.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
        return st

    # -------------------------------------------------------------- 用户控制
    def pause(self, reason: str = '用户手动暂停') -> dict:
        self._save_state(paused=True, pause_reason=reason,
                         paused_at=datetime.now().isoformat(timespec='seconds'))
        self._journal('pause', reason=reason)
        self.log('  [成长] 已暂停（桌宠照常聊天，训练调度器不再触发）')
        return {'ok': True, 'paused': True, 'reason': reason}

    def resume(self) -> dict:
        self._save_state(paused=False, resumed_at=datetime.now().isoformat(timespec='seconds'))
        self._journal('resume')
        self.log('  [成长] 已恢复')
        return {'ok': True, 'paused': False}

    def bump_dialogue(self, n: int = 1) -> int:
        """对话轮次计数（稳定期观察 100 轮用；由桌宠每次对话调用）。"""
        return self.lifecycle.bump_dialogue(n)

    # ------------------------------------------------------- 触发条件（文档 2.3）
    def _device_idle(self) -> tuple:
        """设备是否空闲：负载 + 全屏应用/游戏进程（有 psutil 更准，没有则看负载）。"""
        note = ''
        try:
            load = os.getloadavg()[0]
            ncpu = os.cpu_count() or 1
            if load > ncpu * 0.7:
                return False, f'系统负载偏高（{load:.2f} / {ncpu} 核）'
        except (OSError, AttributeError):
            note = '（本平台不支持负载查询，按空闲处理）'
        try:
            import psutil                                          # type: ignore
        except Exception:                                            # noqa: BLE001
            return True, '未安装 psutil，跳过进程级检测' + note
        heavy = ('steam', 'league of legends', 'genshin', 'valorant', 'zoom', 'teams',
                 'obs', 'blender', 'premiere', 'davinci', 'unity', 'unreal', 'blender')
        try:
            for p in psutil.process_iter(['name']):
                name = (p.info.get('name') or '').lower()
                if any(h in name for h in heavy):
                    return False, f'检测到占用设备的重负载程序：{p.info.get("name")}'
            with psutil.virtual_memory() as vm:                       # noqa: F841
                pass
        except Exception:                                            # noqa: BLE001
            pass
        return True, '设备空闲' + note

    def _power_ok(self) -> tuple:
        """电量/温度是否允许（文档 2.3）。查不到就按允许处理并说明。"""
        try:
            import psutil                                          # type: ignore
        except Exception:                                            # noqa: BLE001
            return True, '未安装 psutil，跳过电量/温度检测'
        try:
            bat = psutil.sensors_battery()
            if bat is not None and not bat.power_plugged and bat.percent is not None and bat.percent < 20:
                return False, f'电量偏低（{bat.percent:.0f}%）且未接电源'
        except Exception:                                            # noqa: BLE001
            pass
        try:
            temps = psutil.sensors_temperatures() or {}
            for name, entries in temps.items():
                for e in entries:
                    if e.current and e.current >= 85:
                        return False, f'温度偏高：{name} {e.current:.0f}°C'
        except Exception:                                            # noqa: BLE001
            pass
        return True, '电量/温度正常'

    def should_train(self, manual: bool = False, force: bool = False) -> dict:
        """五条同时满足才触发（文档 2.3）。返回可解释的判定结果。"""
        cfg_need = int(self.cfg('manual_min_samples') if manual else self.cfg('min_samples'))
        details, reasons = {}, []
        if force:
            return {'ok': True, 'forced': True, 'reasons': [], 'need_samples': cfg_need,
                    'details': {'note': '强制模式：跳过触发条件校验'}}
        if self.is_paused():
            reasons.append('成长已暂停')
        # 样本量：优先看数据仓库待训练样本，其次看语料文件
        pending = 0
        try:
            pending = len(self.store.pending(min_quality=float(self.cfg('min_quality'))))
        except Exception:                                            # noqa: BLE001
            pending = 0
        corpus = self.corpus_items()
        samples = pending if pending else corpus
        details['pending_samples'] = pending
        details['corpus_items'] = corpus
        details['mode'] = '数据仓库' if pending else '语料文件'
        if samples < cfg_need:
            reasons.append(f'样本不足（{samples}/{cfg_need}）')
        # 间隔
        last = self.state().get('last_train_at', '')
        hours = None
        if last:
            try:
                hours = (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 3600.0
            except Exception:                                        # noqa: BLE001
                hours = None
        need_h = float(self.cfg('min_interval_hours'))
        details['hours_since_last'] = round(hours, 2) if hours is not None else None
        if hours is not None and hours < need_h:
            reasons.append(f'距上次训练仅 {hours:.1f}h（需 ≥ {need_h:.0f}h）')
        # 设备空闲
        if self.cfg('require_device_idle'):
            idle, note = self._device_idle()
            details['device_idle'] = idle
            details['device_note'] = note
            if not idle:
                reasons.append(note)
        # 电量 / 温度
        if self.cfg('require_power_ok'):
            ok, note = self._power_ok()
            details['power_ok'] = ok
            details['power_note'] = note
            if not ok:
                reasons.append(note)
        # 算力档位（文档 6.6：训练调度器读取显存探测结果）
        try:
            from core.device import plan as dev_plan, train_plan
            p = dev_plan()
            details['compute'] = {'tier': p['tier'], 'note': p['note']}
            can = p['can_train'] or bool(self.cfg('allow_train_on_cpu'))
            if not can:
                reasons.append(f"算力档位 {p['tier']} 不支持训练（{p['note']}）")
            else:
                details['train_plan'] = train_plan(p['tier'])[0]
        except Exception as e:                                       # noqa: BLE001
            details['compute'] = {'error': f'{type(e).__name__}: {e}'}
        ok = not reasons
        return {'ok': ok, 'reasons': reasons, 'need_samples': cfg_need, 'samples': samples,
                'manual': manual, 'details': details,
                'message': '可以训练' if ok else '；'.join(reasons)}

    # ------------------------------------------------------- 训练（蒸馏）入口
    def _round_corpus_from_store(self, min_quality: float) -> dict | None:
        """从数据仓库取本轮语料（含防遗忘混入），返回 write_corpus 的结果。"""
        try:
            if not self.store.stats()['pending']:
                return None
            out = self.growth_dir / 'round_corpus.jsonl'
            pack = self.store.write_corpus(out, limit=int(self.cfg('min_samples')),
                                          min_quality=min_quality,
                                          base_mix_ratio=float(self.cfg('base_mix_ratio')))
            return pack if pack.get('written') else None
        except Exception as e:                                       # noqa: BLE001
            self.log(f'  [训练] 数据仓库取样失败，改用语料文件：{type(e).__name__}: {e}')
            return None

    def train_round(self, epochs: int = 2, batch_size: int = 2, lr: float = 1e-4,
                    corpus: Path | None = None, trainer=None, min_quality: float | None = None) -> dict:
        """一轮 LoRA 蒸馏训练。

        trainer: 可注入的训练函数 `trainer(epochs, batch_size, lr, corpus) -> dict`，
                 默认使用 `self._peft_train`（依赖 torch/transformers/peft）。
        """
        # 暂停必须真正拦住训练：此前只有 should_train() 检查 paused，
        # 而工作台「开始蒸馏训练」直接调本方法，可以绕过暂停照常训练。
        if self.is_paused():
            msg = '成长已暂停（用户手动暂停，恢复后再训练）'
            self.log(f'  [训练] {msg}')
            return {'ok': False, 'skipped': True, 'paused': True,
                    'message': msg, 'reason': msg,
                    'progress_percent': self.progress_percent()}
        t0 = time.time()
        min_quality = float(self.cfg('min_quality') if min_quality is None else min_quality)
        pack = None if self.dry_run else self._round_corpus_from_store(min_quality)
        if corpus is not None:
            corpus_path = Path(corpus)
        elif pack:
            corpus_path = Path(pack['path'])
        else:
            corpus_path = self.corpus_dir / 'distill_corpus.jsonl'
        items = 0
        if corpus_path.exists():
            with open(corpus_path, 'r', encoding='utf-8') as f:
                items = sum(1 for line in f if line.strip())
        round_no = int(self.state().get('rounds', 0)) + 1
        self.log(f'  [训练] 开始第 {round_no} 轮蒸馏训练：{items} 条语料 / {epochs} epoch'
                 + (f"（其中通用防遗忘样本 {pack['base_mix']} 条，占 {pack['ratio'] * 100:.0f}%）"
                    if pack else ''))
        before = self.adapter_bytes
        if pack:
            try:
                self.store.begin_round(round_no, len(pack['records']), pack['base_mix'], before)
            except Exception:                                        # noqa: BLE001
                pass
        fn = trainer or (self._sim_train if self.dry_run else self._peft_train)
        try:
            result = fn(epochs=epochs, batch_size=batch_size, lr=lr, corpus=corpus_path) or {}
        except Exception as e:                                    # noqa: BLE001
            result = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
        if result.get('ok') is False and not self.dry_run:
            self.log(f'  [训练] 失败：{result.get("error")}')
        after = self.adapter_bytes
        st = self.state()
        self._save_state(rounds=round_no,
                         last_train_at=datetime.now().isoformat(timespec='seconds'))
        if pack:
            try:
                self.store.mark_trained(pack['records'], round_no)
                dpo = self.store.dpo_pairs(untrained_only=True)
                if dpo:
                    self.store.mark_dpo_trained([d['id'] for d in dpo], round_no)
                self.store.finish_round(round_no, result.get('avg_loss'), after,
                                        note=result.get('summary', ''))
            except Exception as e:                                   # noqa: BLE001
                self.log(f'  [训练] 轮次记账失败：{type(e).__name__}')
        self._journal('train', epochs=epochs, batch_size=batch_size, lr=lr, corpus_items=items,
                      corpus_source=str(corpus_path), store_records=len(pack['records']) if pack else 0,
                      base_mix=pack['base_mix'] if pack else 0,
                      adapter_before=before, adapter_after=after,
                      seconds=round(time.time() - t0, 1), result=result.get('summary', ''))
        self.log(f'  [训练] 本轮完成，适配器 {human(before)} → {human(after)}'
                 f'（{self.progress_percent():.1f}% / 基底）')
        return {'ok': True, 'round': round_no, 'adapter_before': before, 'adapter_after': after,
                'progress_percent': self.progress_percent(), 'epochs': epochs,
                'store_records': len(pack['records']) if pack else 0,
                'base_mix': pack['base_mix'] if pack else 0, **result}

    def _sim_train(self, epochs=2, batch_size=2, lr=1e-4, corpus=None, growth=0.12):
        """dry-run 训练：只模拟"适配器继续长大"，用于演练流程 / 无 torch 环境 / 自检。"""
        adp_w = self.adapter_dir / 'adapter_model.safetensors'
        cur = adp_w.stat().st_size if adp_w.exists() else 0
        add = max(int(self.base_bytes * growth * max(epochs, 1) / 2), 4096)
        with open(adp_w, 'ab') as f:
            f.write(b'\0' * add)
        if not (self.adapter_dir / 'adapter_config.json').exists():
            (self.adapter_dir / 'adapter_config.json').write_text(
                json.dumps({'r': int(self.cfg('init_rank')), 'lora_alpha': int(self.cfg('init_rank')) * 2,
                            'target_modules': ['q_proj', 'k_proj', 'v_proj', 'o_proj']},
                           ensure_ascii=False), encoding='utf-8')
        self.log(f'  [训练·演练] 适配器模拟增长 +{human(add)}')
        return {'ok': True, 'simulated': True, 'avg_loss': 1.18,
                'summary': f'演练：+{human(add)}'}

    def _peft_train(self, epochs=2, batch_size=2, lr=1e-4, corpus=None):
        """真正的 LoRA 训练（依赖 torch / transformers / peft）。按算力档位给参数。"""
        from core.peft_train import train_lora        # 延迟导入，未装依赖时不影响主流程
        plan_cfg = {}
        try:
            from core.device import plan as dev_plan, train_plan
            p = dev_plan()
            plan_cfg = train_plan(p['tier'])[0]
            batch_size = plan_cfg.get('batch_size', batch_size)
            self.log(f"  [训练] 算力档位 {p['tier']}：batch={batch_size} "
                     f"accum={plan_cfg.get('grad_accum')} quant={plan_cfg.get('quant')}")
        except Exception:                                            # noqa: BLE001
            pass
        return train_lora(base_dir=self.base_model_dir, adapter_dir=self.adapter_dir,
                          corpus=Path(corpus) if corpus else None,
                          epochs=epochs, batch_size=batch_size, lr=lr,
                          grad_accum=int(plan_cfg.get('grad_accum', 1) or 1),
                          quant=plan_cfg.get('quant', 'none'),
                          lora_r=int(self.rank_status().get('rank') or self.cfg('init_rank')))

    # -------------------------------------------------------- 每轮训练后检查
    def after_training_round(self, **train_kwargs) -> dict:
        """按触发策略判断 → 训练一轮 → 自动检查；达标则立刻合并晋升。"""
        manual = bool(train_kwargs.pop('manual', False))
        force = train_kwargs.pop('force', None)
        force = self.dry_run if force is None else force
        gate = self.should_train(manual=manual, force=force)
        self._journal('trigger', ok=gate['ok'], reasons=gate.get('reasons'), manual=manual,
                      details=gate.get('details'))
        if not gate['ok']:
            self.log(f"  [成长] 本轮不触发训练：{gate['message']}")
            return {'train': {'ok': False, 'skipped': True, 'reason': gate['message']},
                    'gate': gate, 'check': {'action': 'skip', 'message': gate['message']}}
        train_kwargs.setdefault('epochs', int(self.cfg('train_epochs')))
        train_kwargs.setdefault('batch_size', int(self.cfg('train_batch')))
        train_kwargs.setdefault('lr', float(self.cfg('train_lr')))
        train = self.train_round(**train_kwargs)
        check = self.check_and_promote() if self.cfg('auto_check_after_train') \
            else {'action': 'skip', 'message': '自动检查已关闭'}
        return {'train': train, 'gate': gate, 'check': check}

    def check_and_promote(self, force: bool = False) -> dict:
        """三条件评估：全过 → 晋升；仅 A 过而 B/C 未过 → 升 rank 继续成长。"""
        # 暂停同样要拦住晋升检查，否则暂停期间仍可能把适配器合并晋升。
        if self.is_paused():
            msg = '成长已暂停，跳过本轮晋升检查'
            self._journal('check', action='skip', paused=True, note=msg)
            return {'action': 'skip', 'message': msg,
                    'progress_percent': self.progress_percent()}
        from core.eval import Evaluator
        base, adp = self.base_bytes, self.adapter_bytes
        pct = self.progress_percent()
        if base == 0:
            msg = '未安装基底权重，适配器继续积累（安装基底后即可进入合并晋升）'
            self._journal('check', action='skip', progress_percent=pct, note=msg)
            return {'action': 'skip', 'message': msg, 'progress_percent': pct}

        cond_a_ok = adp >= base or force
        if not cond_a_ok:
            self._journal('check', action='grow', progress_percent=pct,
                          base_bytes=base, adapter_bytes=adp)
            return {'action': 'grow', 'progress_percent': pct,
                    'message': f'继续成长（适配器 {human(adp)} / 基底 {human(base)}，{pct:.1f}%）'}

        cap = self.lifecycle.cap_check(override=self.dry_run)
        if cap['blocked']:
            self._journal('check', action='blocked', reasons=cap['reasons'])
            return {'action': 'blocked', 'message': cap['message'], 'cap': cap}

        if self.cfg('require_eval'):
            ev = Evaluator(self.base_dir, self.base_model_dir, self.adapter_dir,
                           engine=self, log=self.log, dry_run=self.dry_run)
            result = ev.evaluate_all(threshold=float(self.cfg('pass_threshold')))
            self._journal('eval', **{k: {kk: vv for kk, vv in v.items() if kk != 'by_item'}
                                     for k, v in (('A', result['A']), ('B', result['B']), ('C', result['C']))},
                          **{'pass': result['pass'], 'simulated': result['simulated']})
            if not result['pass']:
                self.log(f"  [成长] 条件 A 达标但评估未通过：{result['summary']}")
                up = self.grow_rank()
                return {'action': 'rank_up', 'eval': result, 'rank': up,
                        'message': f"三条件未全过（{result['summary']}）→ 已尝试升 rank 继续成长"}
        else:
            result = None

        self.log(f'  [成长] 适配器 {human(adp)} ≥ 基底 {human(base)} → 触发合并晋升')
        res = self.merge_and_promote()
        out = {'action': res.get('ok') and 'promoted' or 'promote_failed', **res}
        if result is not None:
            out['eval'] = result
        return out

    # ------------------------------------------------------------ 升 rank
    def rank_status(self) -> dict:
        try:
            from core.rank import status as rank_status
            return rank_status(self.adapter_dir, int(self.cfg('max_rank')))
        except Exception as e:                                       # noqa: BLE001
            return {'rank': 0, 'error': f'{type(e).__name__}: {e}'}

    def grow_rank(self, new_rank: int | None = None) -> dict:
        """晋升条件不达标时升 rank（文档 7.1 / 7.5，上限默认 256）。"""
        try:
            from core.rank import grow_lora_rank
        except Exception as e:                                       # noqa: BLE001
            return {'ok': False, 'error': f'{type(e).__name__}: {e}'}
        res = grow_lora_rank(self.adapter_dir, new_rank, max_rank=int(self.cfg('max_rank')),
                             dry_run=self.dry_run, log=self.log)
        self._journal('rank_up', **{k: v for k, v in res.items() if k != 'message'})
        if res.get('ok'):
            self.log(f"  [成长] LoRA rank 提升到 {res.get('rank_to')}"
                     f"（{res.get('message', '')}）")
        elif res.get('reason') == 'at_max_rank':
            self.log(f"  [成长] {res.get('message')}")
        return res

    # ------------------------------------------------------------ 合并 & 晋升
    def merge_and_promote(self, retire_mode: str | None = None, keep_backup: bool = False) -> dict:
        """① merge_and_unload 合并 LoRA → ② 成为自研模型 → ③ 原基底退役(trash) → ④ 适配器晋升。"""
        cfg = self.config()
        retire_mode = retire_mode or cfg.get('retire_mode', 'trash')
        keep_backup = keep_backup or bool(cfg.get('keep_backup'))
        if keep_backup and retire_mode == 'trash':
            retire_mode = 'archive'
        gen = int(self.state().get('promotions', 0)) + 1
        old_gen = gen - 1
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        merged_dir = self.star / f'_merge_tmp_{stamp}'
        self.log('  [晋升] ① 合并 LoRA 进基底（peft merge_and_unload）…')
        merge_ok, merge_msg = self._merge_adapter_into(merged_dir)
        if not merge_ok:
            shutil.rmtree(merged_dir, ignore_errors=True)
            self._journal('promote_failed', reason=merge_msg, progress_percent=self.progress_percent())
            return {'ok': False, 'message': f'合并失败：{merge_msg}'}
        self.log('  [晋升] ② 校验合并模型 …')
        if not self._validate_model_dir(merged_dir):
            shutil.rmtree(merged_dir, ignore_errors=True)
            self._journal('promote_failed', reason='校验未通过（config/权重缺失或体积异常）')
            return {'ok': False, 'message': '合并后模型校验未通过，已回滚（原基底完好）'}

        # ③ 原基底退役：移入 trash/（文档原则 2：删除改为退役，稳定期后才真删）
        old_base = self.base_model_dir
        old_bytes = self._dir_weight_bytes(old_base)
        self.log(f'  [晋升] ③ 原基底退役（{retire_mode}）…')
        if gen == 1 and not self.lifecycle.generation(0):
            self.lifecycle.register(0, '原始基底', old_base, status='active',
                                    note='首次晋升前的原始基底（尚未退役时登记）')
        ret = self.lifecycle.retire(old_base, old_gen, mode=retire_mode, stamp=stamp)
        if not ret.get('ok'):
            # 退役失败 → 合并结果连同临时目录一起清理，原基底保留
            shutil.rmtree(merged_dir, ignore_errors=True)
            return {'ok': False, 'message': f"基底退役失败：{ret.get('message')}"}
        try:
            shutil.move(str(merged_dir), str(old_base))
        except OSError as e:
            # 尽力恢复：把刚退役的旧基底拉回来
            try:
                if not old_base.exists():
                    shutil.move(str(Path(ret['dir'])), str(old_base))
            except OSError:
                pass
            return {'ok': False, 'message': f'替换基底失败（原基底已恢复）：{e}'}
        new_bytes = self._dir_weight_bytes(old_base)
        self.lifecycle.register(gen, f'第 {gen} 代自研模型', old_base, status='active', stamp=stamp,
                                note=f'由第 {old_gen} 代合并 LoRA 而来（+{human(max(new_bytes - old_bytes, 0))}）')

        # ④ 适配器晋升为新基底：归档旧适配器 + 在新基底上重建空适配器
        seed = self.star / 'adapter_seeds'
        seed.mkdir(parents=True, exist_ok=True)
        dst = seed / f'adapter_seed_gen{gen}_{stamp}'
        has_adapter = self.adapter_dir.exists() and any(self.adapter_dir.iterdir())
        if has_adapter:
            dst.mkdir(parents=True, exist_ok=True)
            if self.adapter_dir.resolve() == self.star.resolve():          # 旧版布局：只搬适配器文件
                for p in list(self.adapter_dir.iterdir()):
                    if p.is_file() and (p.suffix.lower() in ADAPTER_WEIGHT_EXT
                                        or p.name.startswith('adapter')
                                        or p.name in ('chat_template.jinja',)):
                        shutil.move(str(p), str(dst / p.name))
                self.adapter_dir = self.star / 'adapter'      # 迁移到新版布局
            else:
                shutil.move(str(self.adapter_dir), str(dst))
            self.adapter_dir.mkdir(parents=True, exist_ok=True)
            self.log(f'  [晋升] ④ 适配器晋升：旧适配器归档为种子 {dst.name}，已在新基底上重建'
                     f'（下一轮从 rank {self.cfg("init_rank")} 重新成长）')
        self._save_state(self_research=True, promotions=gen, rounds=0,
                         promoted_at=datetime.now().isoformat(timespec='seconds'),
                         base_bytes_at_promote=new_bytes, retire_mode=retire_mode,
                         last_promote_adapter_bytes=self.adapter_bytes)
        self._journal('promote', generation=gen, merged_from=merge_msg,
                      new_base_bytes=new_bytes, retire_mode=retire_mode,
                      retired_dir=ret.get('dir'), retired_bytes=ret.get('bytes'))
        self.log(f'  [晋升] [OK] 小凌完成第 {gen} 次自我进化：现在她跑在完全属于'
                 f'自己的模型上（{human(new_bytes)}）')
        # 晋升后按磁盘策略做一次保守清理（稳定期未到则只报告、不删）
        try:
            gc_res = self.lifecycle.gc()
            self._journal('gc', **{k: v for k, v in gc_res.items() if k not in ('stability',)})
        except Exception:                                            # noqa: BLE001
            pass
        return {'ok': True, 'generation': gen, 'new_base_bytes': new_bytes,
                'retired': {'dir': ret.get('dir'), 'bytes': ret.get('bytes'), 'mode': retire_mode},
                'message': f'第 {gen} 代自研模型就绪'}

    # -------------------------------------------------------------- 合并实现
    def _merge_adapter_into(self, out_dir: Path):
        if self.dry_run:
            return True, self._simulate_merge(out_dir)
        try:
            import torch                                            # noqa: F401
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel
        except Exception as e:                                      # noqa: BLE001
            return False, (f'缺少依赖 {type(e).__name__}: {e}（pip install torch transformers peft）；'
                           f'可用 dry_run 演练流程')
        try:
            self.log('        加载基底 …')
            from core.device import best_torch_device, device_kwargs
            device = best_torch_device()
            if device == 'cuda':
                self.log('        算力检测：GPU 可用 → 合并也走 GPU（溢出自动回落 CPU）')
            model = AutoModelForCausalLM.from_pretrained(str(self.base_model_dir),
                                                         **device_kwargs(device))
            tok = AutoTokenizer.from_pretrained(str(self.base_model_dir), trust_remote_code=True)
            self.log('        挂载 LoRA 适配器 …')
            peft_model = PeftModel.from_pretrained(model, str(self.adapter_dir))
            self.log('        merge_and_unload …')
            merged = peft_model.merge_and_unload()
            out_dir.mkdir(parents=True, exist_ok=True)
            merged.save_pretrained(str(out_dir), safe_serialization=True)
            tok.save_pretrained(str(out_dir))
            # 复制非权重文件（config/chat template 等）
            for p in self.base_model_dir.iterdir():
                if p.is_file() and p.suffix.lower() not in MODEL_WEIGHT_EXT:
                    shutil.copy2(p, out_dir / p.name)
            size = self._dir_weight_bytes(out_dir)
            return True, f'{human(size)} 已合并（LoRA → 基底）'
        except Exception as e:                                      # noqa: BLE001
            return False, f'合并异常 {type(e).__name__}: {e}'

    def _simulate_merge(self, out_dir: Path) -> str:
        """dry-run：按真实流程走一遍文件操作，用于演练/自检/无 torch 环境。"""
        out_dir.mkdir(parents=True, exist_ok=True)
        if self.base_model_dir.exists():
            for p in self.base_model_dir.iterdir():
                if p.is_file():
                    shutil.copy2(p, out_dir / p.name)
        cfg = out_dir / 'config.json'
        if not cfg.exists():
            cfg.write_text(json.dumps({'model_type': 'xiaoling-simulated', 'hidden_size': 2048},
                                      ensure_ascii=False), encoding='utf-8')
        # 模拟"适配器知识已并入基底"：新基底 = 旧基底 + 适配器体积
        extra = out_dir / 'model.safetensors'
        want = self.base_bytes + self.adapter_bytes
        if not extra.exists() or extra.stat().st_size < want:
            with open(extra, 'wb') as f:
                f.write(b'\0' * want)
        return f'模拟合并完成（{human(want)}）'

    def _validate_model_dir(self, d: Path) -> bool:
        if not d.exists():
            return False
        has_cfg = (d / 'config.json').exists()
        weights = self._dir_weight_bytes(d)
        if not has_cfg or weights <= 0:
            return False
        if not self.dry_run and self.base_bytes > 0:
            # 合并后体积不应明显小于原基底（说明权重没写全）
            if weights < self.base_bytes * 0.5:
                self.log(f'        体积异常：{human(weights)} < 基底 50%')
                return False
        return True

    # -------------------------------------------------------------- 便捷接口
    def rollback(self, gen: int | None = None, dry_run: bool = False) -> dict:
        res = self.lifecycle.rollback(gen, dry_run or self.dry_run)
        if res.get('ok') and not res.get('dry_run'):
            st = self.state()
            self._save_state(promotions=int(res.get('target_gen') or 0),
                             self_research=int(res.get('target_gen') or 0) > 0)
            self._journal('rollback', **{k: v for k, v in res.items() if k != 'message'})
        return res

    def export(self, dest: Path | str) -> dict:
        return self.lifecycle.export(dest)

    def gc(self, keep: int | None = None, dry_run: bool = False, force: bool = False) -> dict:
        res = self.lifecycle.gc(keep, dry_run or self.dry_run, force)
        self._journal('gc', **{k: v for k, v in res.items() if k != 'stability'})
        return res

    def evaluate(self, threshold: float | None = None) -> dict:
        from core.eval import Evaluator
        ev = Evaluator(self.base_dir, self.base_model_dir, self.adapter_dir,
                       engine=self, log=self.log, dry_run=self.dry_run)
        return ev.evaluate_all(threshold if threshold is not None
                               else float(self.cfg('pass_threshold')))

    def samples_report(self) -> str:
        """样本 + 蒸馏节流 + 损失曲线 的一页式摘要（仪表盘也用这个口径）。"""
        try:
            s = self.store.stats()
        except Exception as e:                                       # noqa: BLE001
            return f'数据仓库不可用：{type(e).__name__}: {e}'
        t = self.throttle.usage_report()
        curve = self.store.loss_curve(10)
        lines = [
            '小凌 · 样本与蒸馏状态',
            f"  记录 {s['total']} 条（唯一 {s['unique']}，重复 {s['duplicates']}）"
            f"｜待训练 {s['pending']}｜已训练 {s['used_in_training']}",
            f"  反馈：赞 {s['feedback']['like']}｜踩 {s['feedback']['dislike']}"
            f"｜纠正 {s['feedback']['correct']}｜未评 {s['feedback']['none']}",
            f"  蒸馏样本 {s['with_teacher']} 条｜DPO 偏好对 {s['dpo_pairs']}（已用 {s['dpo_used']}）",
            f"  平均质量分 {s['avg_quality']}｜训练轮次 {s['train_rounds']}",
            f"  蒸馏 API：{'开' if t['enabled'] else '关'}｜今日 {t['used_today']}/{t['daily_limit']}"
            f"（缓存命中 {t['today']['cache_hits']}）｜本月预估 {t['month']['cost_yuan']:.4f} 元",
            f"  损失曲线（最近 {len(curve)} 轮）：" + ('、'.join(f"r{c['round']}={c['avg_loss']}"
                                                           for c in curve) if curve else '尚无记录'),
        ]
        return '\n'.join(lines)


# ---------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description='小凌成长闭环引擎 v2')
    ap.add_argument('cmd', choices=['status', 'report', 'check', 'train', 'simulate', 'reset',
                                    'trigger', 'pause', 'resume', 'rank', 'eval', 'rollback',
                                    'gc', 'export', 'samples', 'lifecycle'])
    ap.add_argument('--epochs', type=int, default=None)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--manual', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--gen', type=int, default=None)
    ap.add_argument('--keep', type=int, default=None)
    ap.add_argument('--rank', type=int, default=None)
    ap.add_argument('--path', default='')
    ap.add_argument('--root', default=str(BASE_DIR))
    a = ap.parse_args(argv)
    eng = GrowthEngine(a.root, dry_run=a.dry_run)
    if a.cmd in ('status', 'report'):
        print(eng.report())
        print(json.dumps(eng.status(), ensure_ascii=False, indent=1))
    elif a.cmd == 'trigger':
        print(json.dumps(eng.should_train(manual=a.manual, force=a.force), ensure_ascii=False, indent=1))
    elif a.cmd == 'check':
        print(json.dumps(eng.check_and_promote(force=a.force), ensure_ascii=False, indent=1))
    elif a.cmd == 'train':
        kw = {'manual': a.manual, 'force': a.force or None}
        if a.epochs:
            kw['epochs'] = a.epochs
        print(json.dumps(eng.after_training_round(**kw), ensure_ascii=False, indent=1))
    elif a.cmd == 'simulate':
        eng.dry_run = True
        print(json.dumps(eng.after_training_round(epochs=1, force=True), ensure_ascii=False, indent=1))
    elif a.cmd == 'reset':
        eng._save_state(self_research=False, promotions=0)
        print('状态已重置')
    elif a.cmd == 'pause':
        print(json.dumps(eng.pause(), ensure_ascii=False, indent=1))
    elif a.cmd == 'resume':
        print(json.dumps(eng.resume(), ensure_ascii=False, indent=1))
    elif a.cmd == 'rank':
        if a.rank:
            print(json.dumps(eng.grow_rank(a.rank), ensure_ascii=False, indent=1))
        else:
            print(json.dumps(eng.rank_status(), ensure_ascii=False, indent=1))
    elif a.cmd == 'eval':
        print(json.dumps(eng.evaluate(), ensure_ascii=False, indent=1))
    elif a.cmd == 'rollback':
        print(json.dumps(eng.rollback(a.gen), ensure_ascii=False, indent=1))
    elif a.cmd == 'gc':
        print(json.dumps(eng.gc(a.keep, force=a.force), ensure_ascii=False, indent=1))
    elif a.cmd == 'export':
        if not a.path:
            print(json.dumps({'ok': False, 'error': '请用 --path 指定导出文件'}))
        else:
            print(json.dumps(eng.export(a.path), ensure_ascii=False, indent=1))
    elif a.cmd == 'samples':
        print(eng.samples_report())
    elif a.cmd == 'lifecycle':
        print(eng.lifecycle.report())


if __name__ == '__main__':
    main()
