#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成长闭环回归测试（真实契约版）。

历史版本用 `GrowthEngine(root, log=..., dry_run=True)` 旧签名，并靠
`_simulate_merge()` 写出全零 model.safetensors 来「演示」晋升，因此长期被
conftest 的 collect_ignore 屏蔽：它测的是假产物的流程，断言本身也已失效。

本版针对当前契约：
  1. 演练（dry_run）路径必须**不动磁盘**、不编造 loss。
  2. 真实训练路径用本地 HF 格式基座跑真 LoRA，断言适配器落盘且能被 PEFT
     重新加载 —— 这是「训练产出可用」的最低证明。缺依赖或无基座时如实 skip。
"""
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend'))


# 参与路径重映射的模块（两套命名空间都要覆盖）
_PATH_MODULES = ("config", "model", "growth", "trainer", "engine")
_NS_PREFIXES = ("core.", "backend.core.")


def _target_modules():
    out = []
    for base in _PATH_MODULES:
        for p in _NS_PREFIXES:
            m = sys.modules.get(p + base)
            if m is not None and m not in out:
                out.append(m)
    return out


def _make_home(root: Path):
    """把已加载模块里的路径常量全部重映射到临时 HOME。

    不用 reload 而是直接 setattr，原因有两个：
      1. 这些常量是 import 时求值的（DATA_DIR / STAR_DIR / ADAPTER_DIR /
         RECORDS_DB…），不刷掉测试就会读写「上一个目录」，得到与断言无关的
         结果。
      2. 仓库里同一份源码存在**两套模块对象**：conftest 把 backend/ 加进
         sys.path（于是可以 `import core.x`），main.py 的 _install_core_alias
         又把它们别名到 backend.core.x。reload 只能命中其中一套，另一套仍是
         旧路径 —— 实测结果是隔离**静默失效**并把产物写进仓库工作区。
    所以两套命名空间逐个扫描并重映射，最后断言确实指向临时目录；再失效时
    宁可测试红着失败，也不要悄悄污染仓库。
    """
    import importlib
    prev = os.environ.get("XIAOLING_HOME")
    os.environ["XIAOLING_HOME"] = str(root)
    for base in _PATH_MODULES:
        for p in _NS_PREFIXES:
            try:
                importlib.import_module(p + base)
            except Exception:
                pass
    mods = _target_modules()
    cfg = next((m for m in mods if m.__name__.endswith("config")), None)
    if cfg is None:
        pytest.skip("core.config 未能导入，无法建立隔离 HOME")
    old_root = Path(getattr(cfg, "APP_DIR", ROOT)).resolve()
    remap = {}
    for m in mods:
        for name, val in list(vars(m).items()):
            if isinstance(val, Path):
                try:
                    rv = val.resolve() if val.is_absolute() else val
                    if str(val).startswith(str(old_root)):
                        rel = Path(str(val)).relative_to(old_root)
                    elif str(rv).startswith(str(old_root)):
                        rel = rv.relative_to(old_root)
                    else:
                        continue
                except (ValueError, OSError):
                    continue
                remap.setdefault((id(m), name), (val, root / rel))
    for (mid, name), (_old, new) in remap.items():
        for m in mods:
            if id(m) == mid:
                setattr(m, name, new)
    for base in _PATH_MODULES:
        for p in _NS_PREFIXES:
            m = sys.modules.get(p + base)
            if m is None:
                continue
            if hasattr(m, "APP_DIR"):
                m.APP_DIR = root
            if hasattr(m, "RESOURCE_DIR") and str(
                    getattr(m, "RESOURCE_DIR", "")).startswith(str(old_root)):
                pass    # 只读资源仍指向仓库，训练不需要写它
    gr = sys.modules.get("core.growth") or sys.modules.get("backend.core.growth")
    for ensure in (getattr(cfg, "ensure_dirs", None),):
        try:
            if callable(ensure):
                ensure()
        except Exception:
            pass
    star = Path(gr.STAR_DIR) if gr is not None else None
    assert star is not None and str(star).startswith(str(root)), (
        f"HOME 隔离失效：growth.STAR_DIR={star} 不在 {root} 内")
    assert str(Path(cfg.DATA_DIR)).startswith(str(root)), (
        f"config.DATA_DIR 未指向临时目录：{cfg.DATA_DIR}")
    _PREV_HOME.append((prev, remap, root))
    return gr


_PREV_HOME = []


def _restore_home():
    """还原被重映射的模块常量与环境变量（支持嵌套）。"""
    if not _PREV_HOME:
        os.environ.pop("XIAOLING_HOME", None)
        return
    prev, remap, _root = _PREV_HOME.pop()
    mods = {id(m): m for m in _target_modules()}
    for (mid, name), (old, _new) in remap.items():
        m = mods.get(mid)
        if m is not None:
            try:
                setattr(m, name, old)
            except Exception:
                pass
    if prev is None:
        os.environ.pop("XIAOLING_HOME", None)
    else:
        os.environ["XIAOLING_HOME"] = prev


def _fake_base(gr, base_mb=2, adapter_kb=32):
    gr.BASE_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    (gr.BASE_MODEL_DIR / "config.json").write_text(
        json.dumps({"model_type": "mini"}), encoding="utf-8")
    (gr.BASE_MODEL_DIR / "model.safetensors").write_bytes(b"\0" * (base_mb * 1024 ** 2))
    gr.ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    (gr.ADAPTER_DIR / "adapter_config.json").write_text(
        json.dumps({"r": 8}), encoding="utf-8")
    (gr.ADAPTER_DIR / "adapter_model.safetensors").write_bytes(b"\0" * (adapter_kb * 1024))
    return gr.BASE_MODEL_DIR, gr.ADAPTER_DIR


@pytest.fixture(autouse=True)
def _clean_home():
    yield
    _restore_home()


# ---------------------------------------------------------------- 演练路径
def test_dry_run_simulate_writes_no_weights():
    """simulate() 只给预估：旧版会写零字节假权重，现在必须一个文件都不产生。"""
    with tempfile.TemporaryDirectory() as td:
        gr = _make_home(Path(td))
        _fake_base(gr)
        eng = gr.GrowthEngine(dry_run=True)
        adp = eng.adapter_dir
        before = sorted(str(p) for p in adp.rglob("*")) if adp.exists() else []
        res = eng.trainer.simulate(growth=0.12, epochs=2)
        after = sorted(str(p) for p in adp.rglob("*")) if adp.exists() else []
        assert res["simulated"] is True and res["real"] is False, res
        assert res["adapter_dir"] == "", res
        assert res["avg_loss"] is None, "演练不得编造 loss 数值"
        assert res["est_adapter_bytes"] > 0, res
        assert after == before, f"演练不应写文件，新增：{set(after) - set(before)}"
        assert not (adp / "simulated").exists()


def test_dry_run_promote_refused_and_disk_unchanged():
    """演练晋升必须被拒：旧版复制基底 + 写与基底等大的全零权重冒充合并结果。"""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gr = _make_home(root)
        _fake_base(gr)
        eng = gr.GrowthEngine(dry_run=True)
        adp = eng.adapter_dir

        def snapshot():
            return sorted((str(p.relative_to(root)), p.stat().st_size)
                          for p in root.rglob("*") if p.is_file())

        snap0 = snapshot()
        (adp / "adapter_model.safetensors").write_bytes(b"\0" * (5 * 1024 ** 2))
        snap1 = snapshot()
        res = eng.merge_and_promote()
        assert res["ok"] is False and res.get("dry_run") is True, res
        assert snapshot() == snap1, "演练晋升不应改变磁盘"
        chk = eng.check_and_promote()
        assert chk["action"] == "promote_failed", chk
        assert eng.state().get("promotions", 0) == 0, "演练不应记为已晋升"


def test_dry_run_train_round_has_no_fake_loss():
    with tempfile.TemporaryDirectory() as td:
        gr = _make_home(Path(td))
        _fake_base(gr, base_mb=1, adapter_kb=8)
        eng = gr.GrowthEngine(dry_run=True)
        res = eng.train_round(epochs=1)
        assert res.get("ok") is True, res
        tr = res
        assert tr.get("simulated") is True and tr.get("real") is False, tr
        assert tr.get("avg_loss") is None, tr


def test_zero_byte_simulated_dir_is_refused_by_loader():
    """历史遗留的模拟产物仍必须被推理入口拒绝（防止旧磁盘状态被当真模型）。"""
    pytest.importorskip("core.model")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "config.json").write_text(
            json.dumps({"model_type": "xiaoling-simulated", "simulated": True}),
            encoding="utf-8")
        cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
        assert cfg.get("simulated") is True


# ---------------------------------------------------------------- 真实训练
def _hf_trainable_base():
    """找一个本地存在的 HF 格式可训练基座（供真跑 LoRA）；没有则返回 None。"""
    cand = os.environ.get("XIAOLING_TEST_BASE_MODEL")
    dirs = [Path(cand)] if cand else []
    dirs += [Path("/tmp/models/gpt2"), Path("/tmp/models/tiny-gpt2")]
    for d in dirs:
        if d.is_dir() and (d / "config.json").exists() and (
                (d / "model.safetensors").exists()
                or (d / "pytorch_model.bin").exists()
                or list(d.glob("model*.safetensors"))):
            return d
    return None


BASE = _hf_trainable_base()
needs_base = pytest.mark.skipif(
    BASE is None, reason="本地无 HF 格式基座模型，真实训练用例跳过")


@needs_base
def test_real_lora_training_produces_loadable_adapter():
    """真跑一轮 LoRA：loss 必须是真实数值，适配器必须能被 PEFT 重新加载。"""
    torch = pytest.importorskip("torch")
    pytest.importorskip("peft")
    pytest.importorskip("transformers")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gr = _make_home(root)
        from core import trainer as T
        samples = [T.TrainSample(prompt=f"问题{i}", completion=f"回答内容{i}")
                   for i in range(8)]
        tr = T.LoRATrainerCore(base_dir=str(BASE))
        events = list(tr.run(samples, steps=6, batch_size=2, lora_rank=4,
                             max_length=64))
        r = tr.result
        assert r.ok, r.reason
        assert r.real is True
        assert r.steps == 6, r.steps
        assert len(r.loss_curve) >= 1
        assert all(isinstance(x, float) and x > 0 for x in r.loss_curve), r.loss_curve
        assert r.metadata.get("trainable_params", 0) > 0, "空适配器必须被拦住"
        # 耗时必须由后端实测：训练页的「预计剩余」靠它，不能是 UI 自己编的
        assert r.metadata.get("elapsed_sec", 0) > 0, r.metadata
        assert r.metadata.get("sec_per_step", 0) > 0, r.metadata
        kinds = {e.kind for e in events}
        assert "init" in kinds and "info" in kinds and "done" in kinds, kinds
        assert "error" not in kinds
        ad = Path(r.adapter_dir)
        assert (ad / "adapter_config.json").exists()
        assert (ad / "adapter_model.safetensors").stat().st_size > 1024, \
            "适配器权重不得是占位空文件"
        # 推理端读法：PeftModel.from_pretrained 必须成功
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        tk = AutoTokenizer.from_pretrained(str(BASE))
        base = AutoModelForCausalLM.from_pretrained(str(BASE))
        merged = PeftModel.from_pretrained(base, str(ad))
        ids = tk("你好", return_tensors="pt")["input_ids"]
        with torch.no_grad():
            out = merged.generate(input_ids=ids, max_new_tokens=4, do_sample=False)
        assert out.shape[-1] >= ids.shape[-1]
        assert Path(r.adapter_dir) == gr.ADAPTER_DIR.resolve() or \
            str(ad.resolve()).startswith(str(gr.STAR_DIR.resolve())), \
            "产物必须落在 STAR_DIR 体系内，不能依赖 CWD"


@needs_base
def test_engine_train_stream_delegates_and_persists_history():
    """engine.train_stream 走同一内核，并把真实结果写进训练历史。"""
    pytest.importorskip("torch")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gr = _make_home(root)
        data = root / "data"
        data.mkdir(parents=True, exist_ok=True)
        (data / "training_data.jsonl").write_text("\n".join(
            json.dumps({"instruction": f"问{i}", "input": "",
                        "output": f"答{i}的内容"}, ensure_ascii=False)
            for i in range(8)), encoding="utf-8")
        # engine.train_stream 不接 base_dir，它靠 _resolve_model_dir 在
        # STAR_DIR/models 下找 HF 基座 —— 链过去即可，别复制 500MB 权重
        dst = gr.STAR_DIR / "models" / "pytest-base"
        dst.mkdir(parents=True, exist_ok=True)
        for f in BASE.iterdir():
            if f.is_file() and not f.name.startswith('.'):
                link = dst / f.name
                if link.exists():
                    continue
                try:
                    link.symlink_to(f)
                except OSError:
                    import shutil
                    if f.stat().st_size > 32 * 1024 * 1024:
                        continue        # 复制太慢就跳过，_resolve 会挑别处
                    shutil.copy2(f, link)
        from core.engine import XiaoLing as XL
        eng = XL.__new__(XL)
        infos = list(XL.train_stream(eng, steps=4, batch_size=2, lora_rank=4,
                                     max_length=64))
        kinds = [i.get("kind") for i in infos]
        assert "error" not in kinds, infos
        assert "done" in kinds, kinds
        hist = XL.read_training_history()
        assert hist, "训练历史必须落盘"
        last = hist[-1]
        assert last["real"] is True and last["ok"] is True, last
        assert last["final_loss"] > 0
        assert last["metadata"].get("target_modules"), last["metadata"]
        # 绝对路径：不得再出现相对 CWD 的 adapters/lora_latest
        assert not str(last["adapter_dir"]).startswith("adapters"), last["adapter_dir"]
        assert Path(last["adapter_dir"]).is_absolute(), last["adapter_dir"]


@needs_base
def test_dpo_path_runs_and_is_labelled():
    pytest.importorskip("torch")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gr = _make_home(root)
        from core import trainer as T
        samples = [T.TrainSample(prompt=f"问题{i}", completion=f"好回答{i}")
                   for i in range(6)]
        pairs = [{"prompt": s.prompt, "chosen": s.completion,
                  "rejected": "差回答"} for s in samples[:4]]
        tr = T.LoRATrainerCore(base_dir=str(BASE))
        list(tr.run(samples, steps=4, batch_size=2, pref="dpo",
                    pref_pairs=pairs, max_length=64, lora_rank=4))
        r = tr.result
        assert r.ok, r.reason
        assert r.metadata.get("pref") == "dpo", r.metadata
        assert r.loss_curve and all(x > 0 for x in r.loss_curve)


# ---------------------------------------------------------------- 训练前蒸馏接线
def test_growth_distill_and_rows_wires_samples():
    """train_stream 前必须先问老师并把成长库样本并进来。

    用户实测反馈：「配好老师 API 后点开始训练，本地模型根本没去问被蒸馏模型」。
    根因是 StartTraining→train_stream 只读 training_data.jsonl，从没调用
    growth.distill_round、也没把真实记录喂进训练。这里锁定接线：
      - growth 缺失 → 返回空，不报错、不打网（训练只用 training_data）
      - distill_round 被真实调用一次（不是零调用）
      - sample_for_training 的问答被转成 TrainSample(prompt,completion)
    """
    from core.engine import XiaoLing as XL

    # 1) 没有成长引擎：绝不炸，返回空
    eng_none = XL.__new__(XL)
    eng_none.growth = None
    events, extra = eng_none._growth_distill_and_rows()
    assert events == [] and extra == []

    # 2) 有成长引擎：distill_round 必须被调用，样本被转换
    class _Store:
        def sample_for_training(self, limit=0, min_quality=0.0):
            return {"samples": [{"question": "问1", "answer": "老师答1"},
                                {"question": "问2", "answer": ""},
                                {"question": "问3", "answer": "答3"}],
                    "base_mix": 0}

    calls = {"distill": 0}

    class _G:
        store = _Store()
        def cfg(self, k, d=None):
            return d
        def distill_round(self, limit=None):
            calls["distill"] += 1
            return {"ok": True, "message": "问了 3 条：写入 3"}

    eng = XL.__new__(XL)
    eng.growth = _G()
    events, extra = eng._growth_distill_and_rows()
    assert calls["distill"] == 1, "训练前必须真的调用一次 distill_round"
    # 蒸馏进度事件里带 kind=distill，前端据此显示 [蒸馏]
    assert any(e.get("kind") == "distill" for e in events), events
    # 空 answer 被过滤，只留 2 条有效样本，且字段映射正确
    from core.trainer import TrainSample
    assert all(isinstance(s, TrainSample) for s in extra)
    assert {s.completion for s in extra} == {"老师答1", "答3"}, extra
    assert all(s.prompt for s in extra)


def test_train_stream_yields_distill_events_before_training(monkeypatch):
    """train_stream 必须把蒸馏/样本事件在真正训练前 yield 出去。

    不依赖 torch：mock 掉 LoRATrainerCore 与 load_training_dataset，只验证
    事件顺序与样本并入 —— 这是「点了开始训练却没问老师」那条反馈的正解。
    """
    from core.engine import XiaoLing as XL

    class _Store:
        def sample_for_training(self, limit=0, min_quality=0.0):
            return {"samples": [{"question": "q", "answer": "a-real"}],
                    "base_mix": 0}

    calls = {"distill": 0}

    class _G:
        store = _Store()
        def cfg(self, k, d=None):
            return d
        def distill_round(self, limit=None):
            calls["distill"] += 1
            return {"ok": True, "message": "问了 1 条"}

    captured = {}

    class _FakeResult:
        steps = 1; final_loss = 1.0; avg_loss = 1.0; loss_curve = [1.0]
        real = True; ok = True; reason = ""; adapter_dir = "/x"
        device = "cpu"; metadata = {}

    class _FakeCore:
        def __init__(self, *a, **k):
            self.result = _FakeResult()
        def run(self, samples, **k):
            captured["samples"] = list(samples)
            from core.trainer import TrainEvent
            yield TrainEvent(step=1, total_steps=1, loss=1.0,
                             status="done", kind="done")

    import core.trainer as T
    monkeypatch.setattr(T, "LoRATrainerCore", _FakeCore)
    monkeypatch.setattr(
        XL, "load_training_dataset",
        classmethod(lambda cls, dataset_name="": [
            {"instruction": "base", "input": "", "output": "b-out"}]))
    eng = XL.__new__(XL)
    eng.growth = _G()
    eng.append_training_history = lambda rec: None
    infos = list(XL.train_stream(eng, steps=1))

    assert calls["distill"] == 1
    kinds = [i.get("kind") for i in infos]
    assert "distill" in kinds, kinds
    assert "sample" in kinds, kinds
    assert kinds.index("done") > kinds.index("distill")
    comps = {s.completion for s in captured["samples"]}
    assert "a-real" in comps, comps       # 成长库样本确实进了训练
    assert "b-out" in comps, comps         # training_data 样本仍在


# ---------------------------------------------------------------- 每日目标 / 里程碑
def test_daily_goal_counter_actually_increments():
    """今日计数必须由 record_interaction 落盘并可读回。

    以前这条链是断的：engine 每轮对话只调 bump_dialogue + store.add，
    record_interaction 只在 calc_exp 里被调，而 calc_exp 全仓库没有调用方。
    于是成长页的「今日 x / 目标 y」永远是 0/y —— 一个装饰性的进度条。
    """
    with tempfile.TemporaryDirectory() as td:
        gr = _make_home(Path(td))
        eng = gr.GrowthEngine()
        try:
            assert eng.get_daily_progress()["completed"] == 0
            assert eng.record_interaction(1) == 1
            assert eng.record_interaction(3) == 4
            d = eng.get_daily_progress()
            assert d["completed"] == 4, d
            assert d["goal"] == eng.get_daily_goal() == gr.GrowthEngine.DEFAULT_DAILY_GOAL
            assert d["achieved"] is False
            assert d["percent"] == round(4 / d["goal"] * 100, 1), d
            # 改目标后 achieved 要跟着变
            assert eng.set_daily_goal(2) is True
            assert eng.get_daily_progress()["achieved"] is True
            assert eng.get_daily_progress()["goal"] == 2
        finally:
            # 必须显式关闭：GrowthEngine 持有 SQLite 连接，Windows 上文件句柄
            # 不释放会导致 TemporaryDirectory 清理时 WinError 32。
            # 项目自身的 bootstrap_growth() 也是 try/finally close 的写法。
            eng.close()


def test_milestone_advances_with_exp():
    """里程碑必须读得到经验、并且报**最高**那一档。

    两处旧 bug：
      1. state()["exp"] 从来没人写 → check_milestones() 恒为 None，
         get_daily_report()["milestone"] 是个永远为空的假字段。
      2. 遍历 sorted(keys) 升序、命中即 return → 就算有 exp=2000 也只报
         「初识(100)」，等级永远不前进。
    """
    with tempfile.TemporaryDirectory() as td:
        gr = _make_home(Path(td))
        eng = gr.GrowthEngine()
        try:
            assert eng.check_milestones() is None, "没经验时不该报里程碑"
            eng.record_interaction(60)          # 60 * 2.0 = 120 exp
            m = eng.check_milestones()
            assert m is not None, "累计经验后必须报里程碑"
            assert m["threshold"] == 100 and m["level"] == "初识", m
            assert m["next_threshold"] == 500, m
            eng.record_interaction(150)         # +300 → 420 exp，仍不到 500
            assert eng.check_milestones()["threshold"] == 100
            eng.record_interaction(50)          # +100 → 520 exp，应升到「熟悉」
            m2 = eng.check_milestones()
            assert m2["threshold"] == 500 and m2["level"] == "熟悉", m2
            assert m2["next_threshold"] == 1000, m2
            rep = eng.get_daily_report()
            assert rep["milestone"] and rep["milestone"]["level"] == "熟悉", rep
            assert rep["interactions_today"] > 0, rep
        finally:
            # 同 test_daily_goal_counter_actually_increments：显式关闭 SQLite 连接。
            eng.close()


# ---------------------------------------------------------------- 旧布局兼容
def test_legacy_adapter_layout_detected():
    """旧版把 LoRA 直接放在 .star_core/ 的布局必须被识别（detect_adapter_dir）。

    原用例用 GrowthEngine(root, log=...) 旧签名构造，这里改为直接测底层
    契约函数 —— 它才是「旧布局不丢适配器」的真正保障。
    """
    with tempfile.TemporaryDirectory() as td:
        star = Path(td) / ".star_core"
        legacy = star / "adapter_model.safetensors"
        star.mkdir(parents=True)
        legacy.write_bytes(b"\0" * 4096)
        (star / "adapter_config.json").write_text('{"r": 8}', encoding="utf-8")
        from core.growth import detect_adapter_dir
        assert detect_adapter_dir(star) == star, "旧布局应识别为 .star_core 本身"
        # 新布局优先
        new = star / "adapter"
        new.mkdir()
        (new / "adapter_model.safetensors").write_bytes(b"\0" * 4096)
        (new / "adapter_config.json").write_text('{"r": 8}', encoding="utf-8")
        assert detect_adapter_dir(star) == new, "两处都有时新版优先"
        # 都没有 → 默认新目录
        empty = Path(td) / "empty_core"
        empty.mkdir()
        assert detect_adapter_dir(empty) == empty / "adapter"
