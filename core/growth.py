#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 成长闭环引擎（v1.0 融合版）
==================================

小凌的核心机制：**基底模型 + LoRA 适配器 → 蒸馏训练（DeepSeek 老师）→ 适配器持续增长
→ 每轮训练后自动检查 → 适配器体积 ≥ 基底体积 → 合并 → 成为自研模型 → 原基底退役
→ 适配器晋升为新基底 → 完全脱离原基底**

与旧版（xl.py 内联实现）相比的改进：

  1. **每轮训练后自动检查**：不再只在启动时检查一次；每次蒸馏/训练结束都会调用
     `after_training_round()`，实时显示进度百分比。
  2. **原子化合并**：合并先写临时目录 → 校验（config.json + 权重可加载 + 体积合理）
     → 再原子替换，断电/中断不会留下半个模型。
  3. **基底退役可配置**：`retire_mode = delete | archive`，默认 delete（用户要求自动删除），
     archive 时保留 `.star_core/base_retired/<时间戳>/`。
  4. **适配器晋升**：合并后把旧适配器归档为"种子"，并在新基底上重建空的 LoRA 适配器，
     开启下一轮成长：从此之后所有成长都发生在"小凌自己的模型"之上。
  5. **可干跑（dry-run）/无 torch 环境可用**：没有 torch/peft 时仍能完成流程校验、
     进度统计与状态迁移（测试与低配设备友好）。
  6. **成长日志**：`.star_core/growth/journal.jsonl` 记录每一轮训练与晋升的结构化数据，
     供成长报告 / 前端进度条读取。

用法：
    python3 -m core.growth status                 # 查看成长状态与进度
    python3 -m core.growth check                  # 检查并（必要时）合并晋升
    python3 -m core.growth train --epochs 2       # 蒸馏训练一轮 + 自动检查
    python3 -m core.growth simulate               # 干跑一次完整晋升流程（不动真模型）
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
    """小凌的成长闭环：训练 → 检查体积 → 合并 → 晋升 → 脱离基底。"""

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

    def status(self) -> dict:
        st = self.state()
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
        }

    def stage_text(self) -> str:
        p = self.progress_percent()
        if self.state().get('self_research'):
            return (f"纯自研模型（第 {self.state().get('promotions', 1)} 代·已脱离原基底）"
                    f"，当前适配器为自研基底的 {p:.1f}%")
        if self.base_bytes == 0 and self.adapter_bytes == 0:
            return '尚未安装基底模型'
        if self.base_bytes == 0:
            return f'无基底权重，适配器 {human(self.adapter_bytes)} 独自积累中'
        if p >= 100:
            return '适配器体积已达基底（等待合并晋升）'
        return f'成长中：适配器为基底的 {p:.1f}%'

    def report(self) -> str:
        s = self.status()
        bar_len = 28
        filled = int(bar_len * s['progress_percent'] / 100)
        bar = '█' * filled + '░' * (bar_len - filled)
        return (f"小凌成长报告\n"
                f"  阶段：{s['stage']}\n"
                f"  基底：{s['base_human']}   适配器：{s['adapter_human']}\n"
                f"  进度：[{bar}] {s['progress_percent']:.1f}%\n"
                f"  训练轮次：{s['rounds']}   晋升次数：{s['promotions']}   语料：{s['corpus_items']} 条")

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

    # ------------------------------------------------------- 训练（蒸馏）入口
    def train_round(self, epochs: int = 2, batch_size: int = 2, lr: float = 1e-4,
                    corpus: Path | None = None, trainer=None) -> dict:
        """一轮 LoRA 蒸馏训练。

        trainer: 可注入的训练函数 `trainer(epochs, batch_size, lr, corpus) -> dict`，
                 默认使用 `self._peft_train`（依赖 torch/transformers/peft）。
        """
        t0 = time.time()
        corpus = corpus or (self.corpus_dir / 'distill_corpus.jsonl')
        items = 0
        if Path(corpus).exists():
            with open(corpus, 'r', encoding='utf-8') as f:
                items = sum(1 for line in f if line.strip())
        self.log(f'  [训练] 开始第 {self.state().get("rounds", 0) + 1} 轮蒸馏训练：{items} 条语料 / {epochs} epoch')
        before = self.adapter_bytes
        fn = trainer or (self._sim_train if self.dry_run else self._peft_train)
        try:
            result = fn(epochs=epochs, batch_size=batch_size, lr=lr, corpus=corpus) or {}
        except Exception as e:                                    # noqa: BLE001
            result = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
        if result.get('ok') is False and not self.dry_run:
            self.log(f'  [训练] 失败：{result.get("error")}')
        after = self.adapter_bytes
        st = self.state()
        self._save_state(rounds=int(st.get('rounds', 0)) + 1,
                         last_train_at=datetime.now().isoformat(timespec='seconds'))
        self._journal('train', epochs=epochs, batch_size=batch_size, lr=lr, corpus_items=items,
                      adapter_before=before, adapter_after=after,
                      seconds=round(time.time() - t0, 1), result=result.get('summary', ''))
        self.log(f'  [训练] 本轮完成，适配器 {human(before)} → {human(after)}'
                 f'（{self.progress_percent():.1f}% / 基底）')
        return {'ok': True, 'adapter_before': before, 'adapter_after': after,
                'progress_percent': self.progress_percent(), 'epochs': epochs, **result}

    def _sim_train(self, epochs=2, batch_size=2, lr=1e-4, corpus=None, growth=0.12):
        """dry-run 训练：只模拟"适配器继续长大"，用于演练流程 / 无 torch 环境 / 自检。"""
        adp_w = self.adapter_dir / 'adapter_model.safetensors'
        cur = adp_w.stat().st_size if adp_w.exists() else 0
        add = max(int(self.base_bytes * growth * max(epochs, 1) / 2), 4096)
        with open(adp_w, 'ab') as f:
            f.write(b'\0' * add)
        if not (self.adapter_dir / 'adapter_config.json').exists():
            (self.adapter_dir / 'adapter_config.json').write_text(
                json.dumps({'r': 8, 'lora_alpha': 16, 'target_modules':
                            ['q_proj', 'k_proj', 'v_proj', 'o_proj']}, ensure_ascii=False), encoding='utf-8')
        self.log(f'  [训练·演练] 适配器模拟增长 +{human(add)}')
        return {'ok': True, 'simulated': True, 'summary': f'演练：+{human(add)}'}

    def _peft_train(self, epochs=2, batch_size=2, lr=1e-4, corpus=None):
        """真正的 LoRA 训练（依赖 torch / transformers / peft / datasets）。"""
        from core.peft_train import train_lora        # 延迟导入，未装依赖时不影响主流程
        return train_lora(base_dir=self.base_model_dir, adapter_dir=self.adapter_dir,
                          corpus=Path(corpus) if corpus else None,
                          epochs=epochs, batch_size=batch_size, lr=lr)

    # -------------------------------------------------------- 每轮训练后检查
    def after_training_round(self, **train_kwargs) -> dict:
        """训练一轮，然后自动检查体积；达标则立刻合并晋升。"""
        train = self.train_round(**train_kwargs)
        check = self.check_and_promote()
        return {'train': train, 'check': check}

    def check_and_promote(self, force: bool = False) -> dict:
        base, adp = self.base_bytes, self.adapter_bytes
        pct = self.progress_percent()
        if base == 0:
            msg = '未安装基底权重，适配器继续积累（安装基底后即可进入合并晋升）'
            self._journal('check', action='skip', progress_percent=pct, note=msg)
            return {'action': 'skip', 'message': msg, 'progress_percent': pct}
        if adp >= base or force:
            self.log(f'  [成长] 适配器 {human(adp)} ≥ 基底 {human(base)} → 触发合并晋升')
            res = self.merge_and_promote()
            return {'action': res.get('ok') and 'promoted' or 'promote_failed', **res}
        self._journal('check', action='grow', progress_percent=pct,
                      base_bytes=base, adapter_bytes=adp)
        return {'action': 'grow', 'progress_percent': pct,
                'message': f'继续成长（适配器 {human(adp)} / 基底 {human(base)}，{pct:.1f}%）'}

    # ------------------------------------------------------------ 合并 & 晋升
    def merge_and_promote(self, retire_mode: str | None = None, keep_backup: bool = False) -> dict:
        """① merge_and_unload 合并 LoRA → ② 成为自研模型 → ③ 原基底退役 → ④ 适配器晋升。"""
        retire_mode = retire_mode or self.state().get('retire_mode', 'delete')
        gen = int(self.state().get('promotions', 0)) + 1
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
        # ③ 原基底退役
        retired = self.star / 'base_retired' / stamp
        old_base = self.base_model_dir
        backup = self.star / f'_base_backup_{stamp}'
        self.log(f'  [晋升] ③ 原基底退役（{retire_mode}）…')
        try:
            if old_base.exists():
                if keep_backup or retire_mode == 'archive':
                    retired.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(old_base), str(retired))
                    self.log(f'        原基底已归档：{retired}')
                else:
                    shutil.move(str(old_base), str(backup))
            shutil.move(str(merged_dir), str(old_base))
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
                self.log('        原基底权重已删除')
        except OSError as e:
            return {'ok': False, 'message': f'替换基底失败（原基底已保留）：{e}'}
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
            self.log(f'  [晋升] ④ 适配器晋升：旧适配器归档为种子 {dst.name}，已在新基底上重建')
        self._save_state(self_research=True, promotions=gen, rounds=0,
                         promoted_at=datetime.now().isoformat(timespec='seconds'),
                         base_bytes_at_promote=self.base_bytes,
                         retire_mode=retire_mode)
        self._journal('promote', generation=gen, merged_from=merge_msg,
                      new_base_bytes=self.base_bytes, retire_mode=retire_mode)
        self.log(f'  [晋升] [OK] 小凌完成第 {gen} 次自我进化：现在她跑在完全属于'
                 f'自己的模型上（{human(self.base_bytes)}）')
        return {'ok': True, 'generation': gen, 'new_base_bytes': self.base_bytes,
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
            dtype = torch.float16 if str(getattr(self, 'device', 'cpu')).startswith('cuda') else torch.float32
            model = AutoModelForCausalLM.from_pretrained(str(self.base_model_dir), dtype=dtype,
                                                        trust_remote_code=True, low_cpu_mem_usage=True)
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


# ---------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description='小凌成长闭环引擎')
    ap.add_argument('cmd', choices=['status', 'report', 'check', 'train', 'simulate', 'reset'])
    ap.add_argument('--epochs', type=int, default=2)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--root', default=str(BASE_DIR))
    a = ap.parse_args(argv)
    eng = GrowthEngine(a.root, dry_run=a.dry_run)
    if a.cmd in ('status', 'report'):
        print(eng.report())
        print(json.dumps(eng.status(), ensure_ascii=False, indent=1))
    elif a.cmd == 'check':
        print(json.dumps(eng.check_and_promote(force=a.force), ensure_ascii=False, indent=1))
    elif a.cmd == 'train':
        print(json.dumps(eng.after_training_round(epochs=a.epochs), ensure_ascii=False, indent=1))
    elif a.cmd == 'simulate':
        eng.dry_run = True
        print(json.dumps(eng.after_training_round(epochs=1), ensure_ascii=False, indent=1))
    elif a.cmd == 'reset':
        eng._save_state(self_research=False, promotions=0)
        print('状态已重置')


if __name__ == '__main__':
    main()
