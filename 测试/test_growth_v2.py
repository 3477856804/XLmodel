#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成长管线 v2 回归测试（无需 torch：走 dry-run / 纯 numpy 路径验证流程正确性）

覆盖：数据仓库 / 蒸馏节流 / 三条件评估 / 生命周期 / 动态升 rank / 触发策略 / 用户控制
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.eval import Evaluator, ensure_benchmark_set                      # noqa: E402
from core.growth import GrowthEngine                                       # noqa: E402
from core.growth_store import GrowthStore, cosine, embed                    # noqa: E402
from core.lifecycle import ModelLifecycle, human                           # noqa: E402
from core.rank import grow_lora_rank, read_rank, status as rank_status, write_safetensors  # noqa: E402
from core.throttle import DistillThrottle, cache_key                        # noqa: E402


def _fake_model(root: Path, base_mb=4, adapter_kb=64, valid_adapter=True):
    star = root / '.star_core'
    base, adp = star / 'XLmodel', star / 'adapter'
    base.mkdir(parents=True, exist_ok=True)
    adp.mkdir(parents=True, exist_ok=True)
    (base / 'config.json').write_text(json.dumps({'model_type': 'mini'}), encoding='utf-8')
    (base / 'model.safetensors').write_bytes(b'\0' * (base_mb * 1024 * 1024))
    if valid_adapter:
        import numpy as np
        rng = np.random.default_rng(7)
        write_safetensors(adp / 'adapter_model.safetensors',
                          {'base_model.model.layers.0.self_attn.q_proj.lora_A.weight':
                               rng.normal(size=(8, 64)).astype('float32'),
                           'base_model.model.layers.0.self_attn.q_proj.lora_B.weight':
                               rng.normal(size=(64, 8)).astype('float32')})
    else:
        (adp / 'adapter_model.safetensors').write_bytes(b'\0' * (adapter_kb * 1024))
    (adp / 'adapter_config.json').write_text(
        json.dumps({'r': 8, 'lora_alpha': 16, 'target_modules': ['q_proj']}), encoding='utf-8')
    (root / '数据').mkdir(exist_ok=True)
    return base, adp


# ------------------------------------------------------------------ 数据仓库
def test_store_basics():
    with tempfile.TemporaryDirectory() as td:
        st = GrowthStore(td)
        a = st.add('你好呀小凌', base_output='你好！', teacher_output='你好，很高兴见到你',
                   feedback='like', tags=['称呼'])
        assert a['quality_score'] > 0.5, a
        assert not a['dup'], a
        # 完全相同的问题 → 判重
        b = st.add('你好呀小凌！', base_output='你好啊')
        assert b['dup'] is True, b
        # 质量分：点踩显著低于点赞
        c = st.add('给我讲讲你会什么', base_output='我会聊天', feedback='dislike')
        assert c['quality_score'] < a['quality_score'], (c, a)
        # 反馈更新 + 纠正
        r = st.set_feedback(a['id'], 'correct', '你好，我是小凌')
        assert r['ok'] and r['quality_score'] >= a['quality_score'] * 0.9
        s = st.stats()
        assert s['total'] == 3 and s['duplicates'] == 1, s
        # 去重：非 dry_run 会把重复项标记 dup_of
        rep = st.dedupe()
        assert rep['scanned'] == 3 and rep['marked_dup'] >= 0
        # 训练取样 + 防遗忘混入（补足样本量，使混入比例有意义）
        (Path(td) / '数据' / 'corpus.txt').write_text('\n'.join(f'底座句{i}' for i in range(50)),
                                                      encoding='utf-8')
        for i in range(8):
            st.add(f'第 {i} 个问题是什么', base_output=f'第 {i} 个回答', feedback='like')
        pack = st.sample_for_training(limit=50, base_mix_ratio=0.15)
        assert len(pack['samples']) >= 8 and pack['base_mix'] >= 1, pack
        assert 0 < pack['ratio'] <= 0.2, pack
        # 导出 / 导入 / 清空
        n_total = st.stats()['total']
        out = Path(td) / '数据' / 'export.jsonl'
        e = st.export_jsonl(out)
        assert e['records'] == n_total and out.exists(), e
        st2 = GrowthStore(td, db_path=Path(td) / '.star_core' / 'growth' / 'r2.db')
        imp = st2.import_jsonl(out)
        assert imp['ok'] and imp['imported'] == n_total, imp
        assert st.purge('trained')['ok']
        assert st.purge('all')['remaining'] == 0
        st.close()
        st2.close()
        print('[OK] 数据仓库：记录/判重/质量分/反馈/取样防遗忘/导出导入/清空：通过')


def test_embed_similarity():
    v1, v2, v3 = embed('今天天气怎么样'), embed('今天天气怎么样？'), embed('请帮我写一段代码')
    assert cosine(v1, v2) > 0.8, cosine(v1, v2)
    assert cosine(v1, v3) < 0.5, cosine(v1, v3)
    print('[OK] 本地哈希向量：相似问题高相似度、不同问题低相似度：通过')


# -------------------------------------------------------------------- 节流
def test_throttle():
    with tempfile.TemporaryDirectory() as td:
        t = DistillThrottle(td, daily_limit=2)
        assert t.check('问题A')['ok'] is True
        t.record('问题A', '老师答案A', tokens_in=100, tokens_out=200)
        # 命中缓存：不消耗配额
        hit = t.check('问题A')
        assert hit['reason'] == 'cache' and hit['cached'] == '老师答案A', hit
        t.record('问题B', '老师答案B', tokens_in=100, tokens_out=100)
        assert t.used_today() == 2 and t.remaining() == 0, (t.used_today(), t.remaining())
        blocked = t.check('问题C')
        assert blocked['ok'] is False and blocked['reason'] == 'quota', blocked
        # 成本估算（示例单价 1/2 元每百万 token）
        cost = t.cost('total')
        assert abs(cost['cost_yuan'] - (200 / 1e6 * 1 + 300 / 1e6 * 2)) < 1e-6, cost
        # 开关
        t.set_enabled(False)
        assert t.check('问题D')['reason'] == 'disabled'
        t.set_enabled(True)
        t.set_daily_limit(5)                      # 放宽配额后再验证缓存已清空
        assert t.clear_cache()['ok'] and t.check('问题A')['reason'] == 'live'
        assert cache_key('a b') == cache_key('a  b')      # 空白归一化
        print('[OK] 蒸馏节流：缓存/限流/开关/成本估算：通过')


# ------------------------------------------------------------------ 三条件
def test_eval_conditions():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base, adp = _fake_model(root, base_mb=1)
        info = ensure_benchmark_set(root)
        assert set(info['counts']) == {'commonsense', 'general', 'safety'}
        assert info['counts']['commonsense'] == 20 and info['counts']['safety'] == 10
        eng = GrowthEngine(root, log=lambda *a: None, dry_run=True)
        ev = Evaluator(root, eng.base_model_dir, eng.adapter_dir, engine=eng, dry_run=True)
        a = ev.condition_a()
        assert a['ok'] is False and a['percent'] < 100, a
        (adp / 'adapter_model.safetensors').write_bytes(b'\0' * (2 * 1024 * 1024))
        assert ev.condition_a()['ok'] is True
        b = ev.condition_b()
        c = ev.condition_c()
        assert b['simulated'] and c['simulated'], (b, c)
        assert c['pass_rate'] >= c['threshold'], c
        res = ev.evaluate_all()
        assert res['pass'] is True and res['simulated'] is True, res
        assert '晋升' in res['summary']
        # 真实模式（无 torch）→ 不当作通过，且明确标注未评估
        ev2 = Evaluator(root, eng.base_model_dir, eng.adapter_dir, engine=eng, dry_run=False)
        c2 = ev2.condition_c()
        assert c2['ok'] is False and c2['mode'] == 'requires_torch', c2
        assert 'torch' in c2['detail']
        print('[OK] 晋升三条件：内置测试集/体积判定/演练模式/缺依赖诚实降级：通过')


# ---------------------------------------------------------------- 生命周期
def test_lifecycle():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base, adp = _fake_model(root, base_mb=2)
        lc = ModelLifecycle(root, log=lambda *a: None, stability_hours=0.0, keep_generations=1)
        lc.register(0, '原始基底', base, status='active')
        # 退役 → 回收区
        r = lc.retire(base, 0, mode='trash')
        assert r['ok'] and Path(r['dir']).exists(), r
        assert not base.exists()
        # 旧代已过稳定期（stability_hours=0）→ 可清理
        gc1 = lc.gc(keep=0)
        assert gc1['allowed'] and 0 in gc1['deleted'], gc1
        # 回滚：造两代，回滚到上一代
        base.mkdir(parents=True, exist_ok=True)
        (base / 'config.json').write_text('{}', encoding='utf-8')
        (base / 'model.safetensors').write_bytes(b'1' * 1024)
        gen1 = root / '.star_core' / 'g1'
        gen1.mkdir(parents=True, exist_ok=True)
        (gen1 / 'config.json').write_text('{}', encoding='utf-8')
        (gen1 / 'model.safetensors').write_bytes(b'2' * 2048)
        lc.register(1, '第 1 代', gen1, status='trash')
        reg = lc.registry()
        for g in reg['generations']:
            if g['gen'] == 1:
                g['status'] = 'trash'
                g['retired_at'] = g.get('retired_at') or ''
        lc._save_registry(reg)
        lc.register(2, '第 2 代', base, status='active')
        rb = lc.rollback(1)
        assert rb['ok'] and rb['target_gen'] == 1, rb
        assert (base / 'model.safetensors').read_bytes() == b'2' * 2048
        # 增长上限
        cap = lc.cap_check()
        assert 'generations' in cap and cap['max_generations'] == 5
        assert 'override' in lc.cap_check(override=True)
        # 导出
        z = lc.export(root / 'out' / 'model.zip')
        assert z['ok'] and Path(z['path']).stat().st_size > 0, z
        import zipfile
        with zipfile.ZipFile(z['path']) as f:
            names = f.namelist()
        assert any(n.startswith('XLmodel/') for n in names), names
        assert any(n.startswith('meta/') for n in names), names
        # 稳定期
        st = lc.stability()
        assert 'dialogue_turns' in st and st['need_turns'] == 100
        assert lc.bump_dialogue(3) >= 3
        assert human(2048) == '2.00 KB'
        print('[OK] 生命周期：退役进回收区/GC/回滚/增长上限/导出/稳定期：通过')


# --------------------------------------------------------------- 动态升 rank
def test_rank_growth():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base, adp = _fake_model(root, base_mb=1)
        st = rank_status(adp)
        assert st['rank'] == 8 and st['next_rank'] == 16, st
        from core.rank import read_safetensors
        _h, before = read_safetensors(adp / 'adapter_model.safetensors')
        key_a = 'base_model.model.layers.0.self_attn.q_proj.lora_A.weight'
        key_b = 'base_model.model.layers.0.self_attn.q_proj.lora_B.weight'
        res = grow_lora_rank(adp, dry_run=True)
        assert res['ok'] and res['rank_to'] == 16 and read_rank(adp) == 8, res
        res = grow_lora_rank(adp, log=lambda *a: None)
        assert res['ok'] and res['rank_to'] == 16, res
        assert read_rank(adp) == 16
        _h, after = read_safetensors(adp / 'adapter_model.safetensors')
        assert after[key_a].shape == (16, 64) and after[key_b].shape == (64, 16)
        # 旧权重复制保留
        import numpy as np
        assert np.allclose(after[key_a][:8], before[key_a], atol=1e-6)
        assert np.allclose(after[key_b][:, :8], before[key_b], atol=1e-6)
        # 新增 B 列补零 → 升 rank 后初始输出与升之前一致
        assert np.allclose(after[key_b][:, 8:], 0.0, atol=1e-6)
        assert res['size_after'] > res['size_before'], res
        cfg = json.loads((adp / 'adapter_config.json').read_text(encoding='utf-8'))
        assert cfg['r'] == 16 and cfg['lora_alpha'] == 32, cfg
        # 上限保护
        up = grow_lora_rank(adp, new_rank=999, max_rank=8, log=lambda *a: None)
        assert up['ok'] is False and up['reason'] == 'at_max_rank', up
        print('[OK] 动态升 rank：旧权重复制/新增补零/体积增长/上限保护：通过')


# --------------------------------------------------------------- 触发与引擎
def test_engine_trigger_and_control():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base, adp = _fake_model(root, base_mb=1)
        eng = GrowthEngine(root, log=lambda *a: None, dry_run=True)
        g = eng.should_train()
        assert g['ok'] is False and any('样本不足' in r for r in g['reasons']), g
        eng.store.add('你好呀，今天过得怎么样？我想听你讲讲今天发生的有趣事情',
                      base_output='今天很好呀，我一直在等你回来和我说话呢',
                      teacher_output='今天过得很好，很开心你能来问我', feedback='like', tags=['称呼'])
        g2 = eng.should_train()
        assert 'pending_samples' in g2['details'] and g2['details']['pending_samples'] >= 1, g2
        # 暂停 / 恢复
        assert eng.pause()['paused'] is True
        assert eng.should_train(manual=True)['ok'] is False
        assert '暂停' in '；'.join(eng.should_train(manual=True)['reasons'])
        # P0-4 回归：暂停必须同时拦住 train_round 与 check_and_promote。
        # 此前只有 should_train() 检查 paused，工作台「开始蒸馏训练」直接调 train_round，
        # 可以绕过暂停照常训练并把适配器合并晋升。
        tr = eng.train_round(epochs=1)
        assert tr.get('paused') is True and tr.get('skipped') is True, tr
        assert '暂停' in tr.get('message', ''), tr
        cp = eng.check_and_promote()
        assert cp.get('action') == 'skip' and '暂停' in cp.get('message', ''), cp
        assert eng.resume()['paused'] is False
        # 强制 / 演练放行
        assert eng.should_train(force=True)['ok'] is True
        # 训练 → 检查 → 晋升（演练）
        (adp / 'adapter_model.safetensors').write_bytes(b'\0' * (2 * 1024 * 1024))
        out = eng.after_training_round(epochs=1)
        assert out['train']['ok'] and out['check']['action'] == 'promoted', out
        assert eng.state()['promotions'] == 1
        # 晋升后：基底进了回收区，新一代登记在册
        assert eng.lifecycle.generation(0) is not None
        assert (root / '.star_core' / 'trash').exists()
        assert eng.lifecycle.generation(1)['status'] == 'active'
        # 控制指令：回滚 / 导出 / 报告
        # eng 是演练模式（dry_run=True），而 lifecycle.rollback(dry_run=True) 按设计
        # 只出方案、不动文件也不改状态（core/lifecycle.py 的 dry_run 分支直接 return）。
        # 这里需要「基底真的退回上一代」，所以必须用真实模式的引擎执行回滚——
        # 紧接着的 eng2 断言（adapter 3MB ≥ 基底 → rank_up）也依赖基底已还原。
        e_real = GrowthEngine(root, log=lambda *a: None, dry_run=False)
        rb = e_real.rollback(0)
        assert rb['ok'] and not rb.get('dry_run') and rb['target_gen'] == 0, rb
        assert e_real.state()['promotions'] == 0, e_real.state()
        assert eng.state()['promotions'] == 0, '回滚后成长状态应同步归零'
        ex = eng.export(root / 'my.zip')
        assert ex['ok'] and ex['files'] > 0, ex
        assert '成长报告' in eng.report()
        assert '样本与蒸馏状态' in eng.samples_report()
        assert '模型生命周期' in eng.lifecycle.report()
        # 真实模式（无 torch）：条件 B/C 未评估 → 只升 rank，不误判晋升
        eng2 = GrowthEngine(root, log=lambda *a: None, dry_run=False)
        (eng2.adapter_dir / 'adapter_model.safetensors').write_bytes(b'\0' * (3 * 1024 * 1024))
        r2 = eng2.check_and_promote()
        assert r2['action'] == 'rank_up', r2
        assert r2['eval']['pass'] is False
        print('[OK] 触发策略/暂停恢复/训练晋升/回收区登记/回滚/导出/真实模式不误判：通过')


if __name__ == '__main__':
    test_store_basics()
    test_embed_similarity()
    test_throttle()
    test_eval_conditions()
    test_lifecycle()
    test_rank_growth()
    test_engine_trigger_and_control()
    print('全部成长管线 v2 测试通过')
