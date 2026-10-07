#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成长闭环回归测试（无需 torch，走 dry-run 路径验证流程正确性）。"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.growth import GrowthEngine  # noqa: E402


def _make_fake_model(root: Path, base_mb=4, adapter_kb=64):
    star = root / '.star_core'
    base = star / 'XLmodel'
    adp = star / 'adapter'
    base.mkdir(parents=True, exist_ok=True)
    adp.mkdir(parents=True, exist_ok=True)
    (base / 'config.json').write_text(json.dumps({'model_type': 'mini'}), encoding='utf-8')
    (base / 'model.safetensors').write_bytes(b'\0' * (base_mb * 1024 * 1024))
    (adp / 'adapter_config.json').write_text(json.dumps({'r': 8}), encoding='utf-8')
    (adp / 'adapter_model.safetensors').write_bytes(b'\0' * (adapter_kb * 1024))
    (root / '数据').mkdir(exist_ok=True)
    (root / '数据' / 'distill_corpus.jsonl').write_text(
        '\n'.join(json.dumps({'question': f'q{i}', 'answer': f'a{i}'}, ensure_ascii=False) for i in range(12)),
        encoding='utf-8')
    return base, adp


def test_grow_then_promote():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base, adp = _make_fake_model(root)
        logs = []
        eng = GrowthEngine(root, log=logs.append, dry_run=True)
        st = eng.status()
        assert st['progress_percent'] < 100, st
        assert st['base_bytes'] > 0 and st['adapter_bytes'] > 0
        assert '成长中' in st['stage']

        # 适配器长到超过基底 → 检查应触发晋升
        (adp / 'adapter_model.safetensors').write_bytes(b'\0' * (5 * 1024 * 1024))
        assert eng.progress_percent() >= 100
        res = eng.check_and_promote()
        assert res['action'] == 'promoted', res
        assert res['ok'] is True
        assert eng.state()['self_research'] is True
        assert eng.state()['promotions'] == 1
        # 原基底已退役：新基底体积应 ≥ 旧基底 + 适配器
        assert eng.base_bytes >= 4 * 1024 * 1024
        # 适配器已归档为新基底种子，且新适配器目录为空（等待下一轮成长）
        seeds = list((root / '.star_core' / 'adapter_seeds').iterdir())
        assert len(seeds) == 1, seeds
        assert not any(eng.adapter_dir.iterdir())
        # 成长日志已落盘
        journal = [json.loads(l) for l in eng.journal_path.read_text(encoding='utf-8').splitlines() if l.strip()]
        events = [r['event'] for r in journal]
        assert 'promote' in events, events
        # 二次检查：已在新基底上继续成长（不再重复合并同一份适配器）
        again = eng.check_and_promote()
        assert again['action'] == 'grow', again
        print('[OK] 适配器增长 → 合并 → 自研模型 → 基底退役 → 适配器晋升：全部通过')


def test_training_round_and_report():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_fake_model(root, base_mb=2, adapter_kb=16)
        logs = []
        eng = GrowthEngine(root, log=logs.append, dry_run=True)
        res = eng.after_training_round(epochs=1)
        assert res['train']['ok'], res
        assert eng.state()['rounds'] == 1
        assert '成长报告' in eng.report()
        assert res['check']['action'] in ('grow', 'promoted', 'skip')
        print('[OK] 训练轮次 + 进度报告：通过')


def test_second_generation():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base, adp = _make_fake_model(root, base_mb=1, adapter_kb=8)
        eng = GrowthEngine(root, log=lambda *a: None, dry_run=True)
        (adp / 'adapter_model.safetensors').write_bytes(b'\0' * (2 * 1024 * 1024))
        assert eng.check_and_promote()['ok']
        gen1_bytes = eng.base_bytes
        # 第二代：在新基底上继续成长
        (eng.adapter_dir / 'adapter_config.json').write_text(json.dumps({'r': 8}), encoding='utf-8')
        (eng.adapter_dir / 'adapter_model.safetensors').write_bytes(b'\0' * (gen1_bytes + 1024))
        res = eng.check_and_promote()
        assert res['ok'] and res['generation'] == 2, res
        assert eng.state()['promotions'] == 2
        print('[OK] 第 2 代自我进化（在新基底上继续成长并再次晋升）：通过')


def test_legacy_adapter_layout():
    """旧版把 LoRA 直接放在 .star_core/ 的布局必须兼容（并自动迁移到 .star_core/adapter/）。"""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base, _adp = _make_fake_model(root, base_mb=2, adapter_kb=8)
        star = root / '.star_core'
        # 模拟旧布局：把适配器从 .star_core/adapter 移到 .star_core/
        for p in list((star / 'adapter').iterdir()):
            p.rename(star / p.name)
        (star / 'adapter').rmdir()
        eng = GrowthEngine(root, log=lambda *a: None, dry_run=True)
        assert eng.adapter_dir == star, eng.adapter_dir          # 自动识别旧布局
        (star / 'adapter_model.safetensors').write_bytes(b'\0' * (3 * 1024 * 1024))
        res = eng.check_and_promote()
        assert res['ok'], res
        seeds = list((star / 'adapter_seeds').iterdir())
        assert len(seeds) == 1 and (seeds[0] / 'adapter_model.safetensors').exists()
        assert (star / 'XLmodel').exists()                        # .star_core 本身没被搬走
        assert eng.adapter_dir == star / 'adapter'                # 已迁移到新版布局
        print('[OK] 旧版适配器布局兼容 + 自动迁移：通过')


if __name__ == '__main__':
    test_grow_then_promote()
    test_training_round_and_report()
    test_second_generation()
    test_legacy_adapter_layout()
    print('全部成长闭环测试通过')
