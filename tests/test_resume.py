#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""断点续训（checkpoint / resume）的行为测试。

这一块此前只有文档上「可续训」三个字，实测全对不上：

  1. resume 只读 trainer_state.json 的 global_step 并按那个数字起算步数。
     检查点被删掉时它照跑：探针实测 steps_this_run=2 / total_steps=5 /
     收尾「训练完成 2 步」，那 2 步其实训在一个从零开始的新 LoRA 上，
     前 3 步只是数字被拼了出来 —— 谎报训练量。
  2. 优化器状态从来没落过盘。AdamW 两个动量项每次续训都从零 warm，
     这叫重新热启动，不叫续训。
  3. _save_checkpoint 会把全局 trainer_state.json 的 loss_curve 写成 []，
     并把 adapter_dir 改写成 checkpoints/stepN —— 曲线接不回去，落点显示
     成一个检查点目录（推理端固定读 ADAPTER_DIR）。
  4. training:adapter 的 resumable = bool(global_step)：state 记了步数就报
     「可续训」，而检查点早没了；checkpoints 还按字符串排序（step10 排在
     step2 前）。
  5. 最要命的一条：save_steps / resume 根本没人传。proto 的 TrainingRequest
     只有 5 个字段且不能改，engine.train_stream 与 growth.LoRATrainer.train
     接了参数却从不传值 —— 这套续训代码在生产路径上永远走不到。

现在：续训由 config.growth.checkpoint_interval / checkpoint_resume 驱动
（training:checkpoint 读写、trainer 在每次训练开始时读），缺权重时如实拒绝
（resume_denied），优化器状态随检查点一起落盘并可装回。

真权重相关的用例需要本地 HF 基座（默认 /tmp/models/tiny-gpt2），缺依赖时
如实 skip —— 不用假产物凑断言。
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "backend", ROOT / "backend" / "rpc"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

tg = importlib.import_module("test_growth")
T = importlib.import_module("core.trainer")

TINY = Path(os.environ.get("XIAOLING_TEST_BASE", "/tmp/models/tiny-gpt2"))


def _ml_available() -> bool:
    try:
        import peft          # noqa: F401
        import torch         # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


needs_base = pytest.mark.skipif(
    not (TINY.is_dir() and (TINY / "config.json").is_file()) or not _ml_available(),
    reason=f"缺少可训练基座 {TINY} 或 torch/peft/transformers 未安装")


@pytest.fixture()
def home(tmp_path, monkeypatch):
    gr = tg._make_home(tmp_path)
    monkeypatch.setenv("XIAOLING_PENDING_DIR", str(tmp_path / "pending"))
    # 默认关掉配置驱动的续训：需要它的用例自己显式打开。
    # 否则「上一个用例把 interval 写成 2」会让别的用例莫名其妙开始落盘/续训。
    _set_growth_cfg(checkpoint_interval=0, checkpoint_resume="off")
    return gr


@pytest.fixture()
def server_mod(home, monkeypatch):
    """只替换 _get_engine：训练指令本体、配置读写都走真实代码。"""
    import server as srv
    monkeypatch.setattr(srv, "_get_engine",
                        lambda: SimpleNamespace(growth=home.GrowthEngine(),
                                                model_replace=None))
    return srv


def _set_growth_cfg(**kw):
    from core import config as C
    cfg = C.load(use_cache=False)
    cfg.setdefault("growth", {}).update(kw)
    C.save(cfg)


def _samples(n: int = 6) -> list:
    return [T.TrainSample(prompt="你好",
                          completion=f"我是小凌，第 {i} 条回复呀")
            for i in range(n)]


def _run(gr, *, steps=3, save_steps=None, resume=None, samples=None, **kw):
    """跑一次真训练。save_steps/resume 传 None = 不传，走配置。"""
    tr = T.LoRATrainerCore(base_dir=str(TINY))
    args: dict = {"steps": steps, "batch_size": 1, "grad_accum": 1,
                  "lora_rank": 4, "max_length": 32, "dataset_tag": "probe"}
    if save_steps is not None:
        args["save_steps"] = save_steps
    if resume is not None:
        args["resume"] = resume
    args.update(kw)
    events = list(tr.run(samples if samples is not None else _samples(), **args))
    return tr, events


def _state(gr) -> dict:
    p = Path(gr.ADAPTER_DIR) / "trainer_state.json"
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_state(gr, **kw):
    ad = Path(gr.ADAPTER_DIR)
    ad.mkdir(parents=True, exist_ok=True)
    data = {"global_step": 0, "loss_curve": [], "adapter_dir": str(ad)}
    data.update(kw)
    (ad / "trainer_state.json").write_text(json.dumps(data, ensure_ascii=False),
                                           encoding="utf-8")
    return data


def _fake_ckpt(gr, step: int, *, weights=True, optimizer=False,
               state: dict | None = None) -> Path:
    """造一个检查点目录，只放测试关心的那几样东西（不碰真权重）。"""
    d = Path(gr.ADAPTER_DIR) / "checkpoints" / f"step{step}"
    d.mkdir(parents=True, exist_ok=True)
    if weights:
        (d / "adapter_config.json").write_text(json.dumps({"r": 4}),
                                               encoding="utf-8")
    if optimizer:
        (d / "optimizer.pt").write_bytes(b"stub")
    if state is not None:
        (d / "trainer_state.json").write_text(json.dumps(state), encoding="utf-8")
    return d


def _core(gr) -> T.LoRATrainerCore:
    """只测纯函数时用：不加载模型，只要一个绑定好 adapter_dir 的实例。"""
    tr = T.LoRATrainerCore.__new__(T.LoRATrainerCore)
    tr.adapter_dir = Path(gr.ADAPTER_DIR)
    return tr


# --------------------------------------------------------------------------- #
#  1. 续训此前在生产路径上根本走不到：配置必须能驱动它
# --------------------------------------------------------------------------- #

def test_config_defaults_keep_behaviour_unchanged(home):
    """默认 interval=0 / mode=off ⇒ 不落检查点、不续训，meta 里也不留痕迹。"""
    cfg = T.checkpoint_cfg()
    assert cfg["interval"] == 0 and cfg["mode"] == "off", cfg
    # 保留个数必须有默认值：optimizer.pt 比权重还大，无上限会把磁盘吃空
    assert cfg["keep"] == T.DEFAULT_CHECKPOINT_KEEP, cfg
    meta: dict = {}
    assert T._resolve_checkpoint_args(0, False, meta) == (0, False)
    assert meta == {}, meta


def test_config_drives_checkpoint_args(home):
    _set_growth_cfg(checkpoint_interval=7, checkpoint_resume="auto")
    assert T.checkpoint_cfg()["interval"] == 7
    meta: dict = {}
    assert T._resolve_checkpoint_args(0, False, meta) == (7, True)
    assert meta["checkpoint_source"] == "config", meta
    # 模式 off 时只落盘不续训 —— 不自作主张替用户续
    _set_growth_cfg(checkpoint_interval=9, checkpoint_resume="off")
    meta2: dict = {}
    assert T._resolve_checkpoint_args(0, False, meta2) == (9, False), meta2


def test_explicit_args_beat_config(home):
    """调用方显式传参时配置完全不介入（CLI/测试的行为不能被配置改掉）。"""
    _set_growth_cfg(checkpoint_interval=50, checkpoint_resume="auto")
    meta: dict = {}
    assert T._resolve_checkpoint_args(3, False, meta) == (3, False)
    assert T._resolve_checkpoint_args(0, True, meta) == (0, True)
    assert "checkpoint_source" not in meta, meta


def test_mode_without_interval_is_declared_not_guessed(home):
    """开着 auto 但间隔为 0 = 没有落盘依托。不猜一个间隔，如实写明。"""
    _set_growth_cfg(checkpoint_interval=0, checkpoint_resume="always")
    meta: dict = {}
    assert T._resolve_checkpoint_args(0, False, meta) == (0, False)
    assert "checkpoint_interval=0" in meta.get("resume_note", ""), meta


@needs_base
def test_config_opened_resume_actually_resumes(home):
    """整条链路的真实验证：两次训练都不传参，第二次真的接着上次的步数跑。"""
    _set_growth_cfg(checkpoint_interval=2, checkpoint_resume="auto")
    tr1, _ = _run(home, steps=3)          # 不传 save_steps/resume
    assert tr1.result.ok, tr1.result.reason
    assert tr1.result.metadata.get("checkpoint_source") == "config"
    assert tr1.result.steps == 3, tr1.result.steps
    ck = Path(home.ADAPTER_DIR) / "checkpoints" / "step2"
    assert (ck / "adapter_config.json").is_file() and (ck / "optimizer.pt").is_file()

    tr2, ev2 = _run(home, steps=2)
    m = tr2.result.metadata
    assert m.get("resumed_from") == str(ck), m
    assert m.get("optimizer_restored") is True, m
    assert tr2.result.steps == 2, tr2.result.steps
    assert tr2.total_steps == 4, tr2.total_steps      # 2 旧 + 2 新
    assert _state(home)["global_step"] == 4, _state(home)
    done = [e for e in ev2 if e.kind == "done"][0]
    assert "训练完成 2 步" in done.status, done.status
    # 进度事件按「本次 2 步」报，但总进度是 4 步 —— 两者都要对
    prog = [e for e in ev2 if e.kind not in ("init", "info", "warning", "done")]
    assert prog, [e.status for e in ev2]
    assert prog[-1].step == 4 and prog[-1].total_steps == 4, prog[-1]
    assert "训练中 2/2" in prog[-1].status, prog[-1].status


# --------------------------------------------------------------------------- #
#  2. 没有可用权重时不许谎报训练量
# --------------------------------------------------------------------------- #

@needs_base
def test_resume_denied_when_promised_checkpoint_is_gone(home):
    """落过检查点（state 有 latest_checkpoint）又删掉 → 拒绝本次训练。"""
    tr1, _ = _run(home, steps=3, save_steps=2)
    assert tr1.result.ok, tr1.result.reason
    assert _state(home).get("latest_checkpoint"), _state(home)
    shutil.rmtree(Path(home.ADAPTER_DIR) / "checkpoints")

    tr2, ev2 = _run(home, steps=2, save_steps=0, resume=True)
    assert tr2.result.ok is False, tr2.result
    assert tr2.result.metadata.get("resume_denied"), tr2.result.metadata
    assert ev2[-1].kind == "error", ev2[-1]
    # 「训练完成 N 步」这句谎话不能再出现
    assert not any("完成" in e.status for e in ev2), [e.status for e in ev2]
    assert tr2.total_steps == 0, tr2.total_steps
    assert tr2.global_step == 0, tr2.global_step


@needs_base
def test_unpromised_state_restarts_from_zero_with_warning(home):
    """state 有步数但从没落过检查点（旧版训练）：退回第 0 步并明说，不静默。"""
    _write_state(home, global_step=300, loss_curve=[1.0] * 300)
    tr, ev = _run(home, steps=2, save_steps=0, resume=True)
    assert tr.result.ok, tr.result.reason
    m = tr.result.metadata
    assert m.get("resume_denied") is None, m
    assert "从第 0 步重新开始" in m.get("resume_reset", ""), m
    assert any(e.kind == "warning" and "第 0 步" in e.status for e in ev), \
        [e.status for e in ev]
    assert tr.total_steps == 2, tr.total_steps        # 不是 302
    assert tr.result.steps == 2, tr.result.steps
    # 旧的 300 个点不再被拼进曲线冒充本次训练
    assert len(tr.result.loss_curve) == 2, tr.result.loss_curve
    assert not _state(home).get("latest_checkpoint"), _state(home)


def test_promised_checkpoint_distinguishes_lost_from_never_saved(home):
    tr = _core(home)
    assert tr._promised_checkpoint({}) == ""
    assert tr._promised_checkpoint({"global_step": 300}) == ""
    got = tr._promised_checkpoint({"latest_checkpoint": "/x/step10"})
    assert "step10" in got and "读不到" in got, got


def test_promised_checkpoint_survives_garbage(home):
    tr = _core(home)
    assert tr._promised_checkpoint({"latest_checkpoint": 12345}) != ""
    assert tr._promised_checkpoint({"latest_checkpoint": "   "}) == ""


# --------------------------------------------------------------------------- #
#  3. 步数跟着权重的真实进度走
# --------------------------------------------------------------------------- #

def test_latest_checkpoint_is_numeric_and_requires_weights(home):
    tr = _core(home)
    _fake_ckpt(home, 2)
    _fake_ckpt(home, 10)
    _fake_ckpt(home, 6, weights=False)    # 半截目录：只有 optimizer.pt
    assert tr._latest_checkpoint(100).name == "step10"
    assert tr._latest_checkpoint(9).name == "step2"
    assert tr._latest_checkpoint(1) is None
    (Path(home.ADAPTER_DIR) / "checkpoints" / "backup").mkdir(exist_ok=True)
    assert tr._latest_checkpoint(100).name == "step10"
    assert tr._latest_checkpoint(0) is None
    shutil.rmtree(Path(home.ADAPTER_DIR) / "checkpoints")
    assert tr._latest_checkpoint(100) is None


@needs_base
def test_resume_uses_real_checkpoint_step_when_state_is_ahead(home):
    """state 说 5 步、可用的只有 step2 → 从 2 续，并如实说明差了多少。"""
    tr1, _ = _run(home, steps=5, save_steps=2)
    assert tr1.result.ok, tr1.result.reason
    st = _state(home)
    assert st["global_step"] == 5, st
    shutil.rmtree(Path(home.ADAPTER_DIR) / "checkpoints" / "step4")

    tr2, _ev = _run(home, steps=1, save_steps=0, resume=True)
    m = tr2.result.metadata
    assert m.get("resumed_from", "").endswith("step2"), m
    assert "只有 2 步" in str(m.get("resume_behind_state", "")), m
    assert tr2.total_steps == 3, tr2.total_steps
    assert tr2.result.steps == 1, tr2.result.steps
    # 曲线取 step2 自己那份快照（2 个点），不是 state 里对不上的 5 个
    assert len(tr2.result.loss_curve) == 3, tr2.result.loss_curve


def test_curve_prefers_matching_checkpoint_snapshot(home):
    tr = _core(home)
    ck = _fake_ckpt(home, 4, state={"global_step": 4,
                                    "loss_curve": [1.0, 2.0, 3.0, 4.0]})
    state = {"global_step": 4, "loss_curve": [9.0, 9.0]}
    assert tr._curve_for_checkpoint(ck, state, 4) == [1.0, 2.0, 3.0, 4.0]
    # 快照步数与要续的步数不一致 ⇒ 不可信，退回全局 state
    stale = _fake_ckpt(home, 8, state={"global_step": 8, "loss_curve": [5.0]})
    assert tr._curve_for_checkpoint(stale, state, 4) == [9.0, 9.0]
    broken = _fake_ckpt(home, 5)
    (broken / "trainer_state.json").write_text("{坏掉的 json", encoding="utf-8")
    assert tr._curve_for_checkpoint(broken, state, 5) == [9.0, 9.0]


# --------------------------------------------------------------------------- #
#  4. 优化器状态：真落盘、真装回、装不上就明说
# --------------------------------------------------------------------------- #

@needs_base
def test_checkpoint_saves_optimizer_and_snapshot(home):
    tr, _ = _run(home, steps=4, save_steps=2)
    assert tr.result.ok, tr.result.reason
    for step in (2, 4):
        ck = Path(home.ADAPTER_DIR) / "checkpoints" / f"step{step}"
        assert (ck / "adapter_config.json").is_file(), step
        assert (ck / "optimizer.pt").is_file(), (
            "AdamW 动量没落盘 = 续训只会从头热启动")
        snap = json.loads((ck / "trainer_state.json").read_text(encoding="utf-8"))
        assert snap["global_step"] == step, snap
        assert snap.get("checkpoint") is True, snap
        assert len(snap["loss_curve"]) == step, snap
        assert snap["adapter_dir"] == str(ck), snap
    st = _state(home)
    # 全局 state 的落点必须是推理端读的 adapter_dir，不是某个检查点
    assert st["adapter_dir"] == str(Path(home.ADAPTER_DIR)), st
    assert len(st["loss_curve"]) >= 4, st
    assert st["latest_checkpoint"].endswith("step4"), st
    assert st["checkpoint_optimizer"] is True, st


@needs_base
def test_optimizer_round_trip_restores_moments(home):
    import torch
    tr1, _ = _run(home, steps=2, save_steps=2)
    assert tr1.result.ok, tr1.result.reason
    ck = Path(home.ADAPTER_DIR) / "checkpoints" / "step2"
    raw = torch.load(ck / "optimizer.pt", map_location="cpu", weights_only=False)
    assert raw.get("state"), "optimizer.pt 里没有动量状态"
    tr2, _ = _run(home, steps=1, save_steps=0, resume=True)
    m = tr2.result.metadata
    assert m.get("optimizer_restored") is True, m
    assert m.get("optimizer_restore_failed") is None, m


@needs_base
def test_corrupt_optimizer_is_declared_not_hidden(home):
    tr1, _ = _run(home, steps=2, save_steps=2)
    assert tr1.result.ok, tr1.result.reason
    (Path(home.ADAPTER_DIR) / "checkpoints" / "step2" / "optimizer.pt"
     ).write_bytes(b"\x00\x01 not a tensor at all")
    tr2, _ = _run(home, steps=1, save_steps=0, resume=True)
    assert tr2.result.ok, tr2.result.reason        # 权重照样能续
    m = tr2.result.metadata
    assert m.get("optimizer_restored") is False, m
    assert "本次仅续权重" in str(m.get("optimizer_restore_failed", "")), m


@needs_base
def test_old_checkpoint_without_optimizer_is_declared(home):
    tr1, _ = _run(home, steps=2, save_steps=2)
    assert tr1.result.ok, tr1.result.reason
    (Path(home.ADAPTER_DIR) / "checkpoints" / "step2" / "optimizer.pt").unlink()
    tr2, _ = _run(home, steps=1, save_steps=0, resume=True)
    assert tr2.result.ok, tr2.result.reason
    m = tr2.result.metadata
    assert m.get("resumed_from", "").endswith("step2"), m
    assert m.get("optimizer_restored") is False, m
    assert "没有 optimizer.pt" in str(m.get("optimizer_restored_note", "")), m


@needs_base
def test_unreadable_checkpoint_is_refused(home):
    """检查点目录在、权重读不出来：明说「读不出来」并拒绝，不静默开新的。"""
    tr1, _ = _run(home, steps=2, save_steps=2)
    assert tr1.result.ok, tr1.result.reason
    ck = Path(home.ADAPTER_DIR) / "checkpoints" / "step2"
    (ck / "adapter_config.json").write_text("{}", encoding="utf-8")
    (ck / "adapter_model.safetensors").write_bytes(b"garbage")
    tr2, ev = _run(home, steps=1, save_steps=0, resume=True)
    assert tr2.result.ok is False, tr2.result
    assert tr2.result.metadata.get("resume_failed"), tr2.result.metadata
    assert ev[-1].kind == "error", ev[-1]
    assert not any("完成" in e.status for e in ev), [e.status for e in ev]


# --------------------------------------------------------------------------- #
#  5. 落盘失败必须当场说出来
# --------------------------------------------------------------------------- #

@needs_base
def test_checkpoint_write_failure_warns(home, monkeypatch):
    tr_saved = T.LoRATrainerCore._save_checkpoint
    monkeypatch.setattr(T.LoRATrainerCore, "_save_checkpoint",
                        lambda self, *a, **k: {"ok": False, "dir": "",
                                               "optimizer_ok": False,
                                               "error": "磁盘只读"})
    tr, ev = _run(home, steps=2, save_steps=1)
    assert any(e.kind == "warning" and "无法续训" in e.status for e in ev), \
        [e.status for e in ev]
    assert tr.result.metadata.get("checkpoint_error") == "磁盘只读", \
        tr.result.metadata
    monkeypatch.setattr(T.LoRATrainerCore, "_save_checkpoint", tr_saved)


@needs_base
def test_optimizer_only_failure_warns(home, monkeypatch):
    monkeypatch.setattr(T.LoRATrainerCore, "_save_checkpoint",
                        lambda self, *a, **k: {"ok": True, "dir": "/x/step1",
                                               "optimizer_ok": False,
                                               "error": "优化器状态落盘失败：OSError"})
    _tr, ev = _run(home, steps=2, save_steps=1)
    assert any("优化器状态没落上" in e.status for e in ev if
               e.kind == "warning"), [e.status for e in ev]


@needs_base
def test_state_write_failure_is_reported(home, monkeypatch):
    """进度写不上 = 这检查点下次读不到，等于白落：必须如实报失败。

    write_state 自己吞掉 OSError（状态文件坏掉不该让一次真训练失败），
    所以这里模拟「返回 False」这个真实出口。
    """
    monkeypatch.setattr(T.LoRATrainerCore, "write_state",
                        lambda self, st: False)
    tr, _ = _run(home, steps=2, save_steps=2)
    assert tr.result.ok, tr.result.reason            # 训练本身是成功的
    assert "状态更新失败" in tr.result.metadata.get("checkpoint_error", ""), \
        tr.result.metadata
    ck = Path(home.ADAPTER_DIR) / "checkpoints" / "step2"
    assert (ck / "optimizer.pt").is_file(), "权重与动量本身是落下去了的"
    # 进度没落上 → training:adapter 不能声称可续训
    assert not (Path(home.ADAPTER_DIR) / "trainer_state.json").is_file()


# --------------------------------------------------------------------------- #
#  6. 体积口径：检查点不是「适配器长大了」
# --------------------------------------------------------------------------- #

def test_adapter_weight_bytes_ignores_snapshots_and_dupes(home):
    gr = home
    ad = Path(gr.ADAPTER_DIR)
    ad.mkdir(parents=True, exist_ok=True)
    (ad / "adapter_model.safetensors").write_bytes(b"a" * 1000)
    latest = ad / "lora_latest"
    latest.mkdir(exist_ok=True)
    # _finalize 会写两个名字，那是同一份权重
    (latest / "adapter_model.safetensors").write_bytes(b"a" * 1000)
    ck = ad / "checkpoints" / "step2"
    ck.mkdir(parents=True, exist_ok=True)
    (ck / "adapter_model.safetensors").write_bytes(b"a" * 1000)
    (ck / "optimizer.pt").write_bytes(b"a" * 4000)          # 比权重还大
    (ck / "trainer_state.json").write_text("{}", encoding="utf-8")
    assert gr.adapter_weight_bytes(ad) == 1000, gr.adapter_weight_bytes(ad)
    # 磁盘占用报表要的是全部，dir_bytes 口径不变
    assert gr.dir_bytes(ad) >= 7000, gr.dir_bytes(ad)


def test_progress_percent_not_inflated_by_checkpoints(home):
    gr = home
    eng = gr.GrowthEngine()
    ad = Path(eng.adapter_dir)
    ad.mkdir(parents=True, exist_ok=True)
    (ad / "adapter_model.safetensors").write_bytes(b"a" * 512)
    ck = ad / "checkpoints" / "step9"
    ck.mkdir(parents=True, exist_ok=True)
    (ck / "adapter_model.safetensors").write_bytes(b"a" * 512)
    (ck / "optimizer.pt").write_bytes(b"a" * 9000)
    assert eng.adapter_bytes == 512, eng.adapter_bytes
    # 真权重更大时才算数
    (ad / "adapter_model.safetensors").write_bytes(b"a" * 700)
    assert eng.adapter_bytes == 700, eng.adapter_bytes


# --------------------------------------------------------------------------- #
#  7. training:adapter / training:checkpoint 的如实汇报
# --------------------------------------------------------------------------- #

def _training(server_mod, sub: str) -> dict:
    return json.loads(server_mod._handle_training_cmd(sub))


def test_adapter_resumable_requires_usable_checkpoint(server_mod, home):
    """resumable 不能再等于「state 记过步数」——那是界面与 trainer 打架的根源。"""
    _write_state(home, global_step=6, latest_checkpoint="/x/step6")
    d = _training(server_mod, "adapter")
    assert d["resumable"] is False, d
    assert "6" in d["resume_blocked_reason"], d
    _fake_ckpt(home, 6, optimizer=True)
    d = _training(server_mod, "adapter")
    assert d["resumable"] is True, d
    assert d["resume_would_use"] == "step6", d
    assert d["optimizer_in_checkpoint"] is True, d
    assert d["checkpoints_usable"] == ["step6"], d
    # 半截目录列出来但标成没有权重，且不算 usable
    _fake_ckpt(home, 4, weights=False)
    d = _training(server_mod, "adapter")
    assert d["checkpoints"] == ["step4", "step6"], d
    assert d["checkpoints_usable"] == ["step6"], d
    assert d["checkpoint_missing_weights"] == ["step4"], d
    assert d["optimizer_in_checkpoint"] is True, d


def test_adapter_uses_the_checkpoint_trainer_would_actually_pick(server_mod, home):
    """检查点比 state 记录的步数更新时不能报「可续训」——trainer 挑不中它。"""
    _write_state(home, global_step=6)
    _fake_ckpt(home, 10, optimizer=True)     # 例如手工拷进来的备份
    d = _training(server_mod, "adapter")
    assert d["resumable"] is False, d
    assert d["resume_would_use"] == "", d
    assert d["optimizer_in_checkpoint"] is False, d
    assert "不会续训" in d["resume_blocked_reason"], d


def test_adapter_reports_setting_when_feature_is_off(server_mod, home):
    """显示「不可续训」时必须同时说清是没检查点还是压根没开这个功能。"""
    d = _training(server_mod, "adapter")
    assert d["resumable"] is False, d
    assert d["checkpoint_setting"]["interval"] == 0, d
    assert "training:checkpoint" in d["resume_hint"], d
    # 开着功能但还没跑过：这时候拦路的是进度，不是开关
    _training(server_mod, "checkpoint 20 auto")
    _write_state(home, global_step=0)
    d = _training(server_mod, "adapter")
    assert "resume_hint" not in d, d
    assert "global_step=0" in d["resume_blocked_reason"], d


def test_adapter_reports_unreadable_state(server_mod, home):
    ad = Path(home.ADAPTER_DIR)
    ad.mkdir(parents=True, exist_ok=True)
    (ad / "trainer_state.json").write_text("{坏", encoding="utf-8")
    d = _training(server_mod, "adapter")
    assert "state_error" in d, d
    assert d["resumable"] is False, d


def test_checkpoint_op_read_and_write(server_mod, home):
    d = _training(server_mod, "checkpoint")
    assert d["ok"] and d["interval"] == 0 and d["mode"] == "off", d
    assert "training:checkpoint" in d["usage"], d

    # 间隔还是 0 时只给模式：不猜一个数字，如实拒绝
    d = _training(server_mod, "checkpoint auto")
    assert d["ok"] is False and "training:checkpoint 30 auto" in d["error"], d

    d = _training(server_mod, "checkpoint 30 auto")
    assert d["written"] is True and d["interval"] == 30 and d["mode"] == "auto", d
    assert "每 30 步" in d["note"], d
    assert T.checkpoint_cfg()["interval"] == 30, T.checkpoint_cfg()

    # 已有间隔时只改模式是合法写法（沿用现有间隔）
    d = _training(server_mod, "checkpoint always")
    assert d["written"] and d["interval"] == 30 and d["mode"] == "always", d

    # 关掉：检查点与续训一起归零
    d = _training(server_mod, "checkpoint off")
    assert d["written"] and d["interval"] == 0 and d["mode"] == "off", d
    assert "已关闭" in d["note"], d
    # 只写 0 等同于关
    _training(server_mod, "checkpoint 30 auto")
    d = _training(server_mod, "checkpoint 0")
    assert d["interval"] == 0 and d["mode"] == "off", d

    # 落检查点但不自动续训：合法配置，但要说清差别
    d = _training(server_mod, "checkpoint 40 off")
    assert d["written"] and d["interval"] == 40 and d["mode"] == "off", d
    assert "不会自动接着上次跑" in d["note"], d

    for bad in ("checkpoint abc", "checkpoint 30 sometimes", "checkpoint -5",
                "checkpoint 99999999", "checkpoint 30 auto 0",
                "checkpoint 30 auto 25"):
        d = _training(server_mod, bad)
        assert d["ok"] is False, (bad, d)
    cfg = T.checkpoint_cfg()
    assert cfg["interval"] == 40 and cfg["mode"] == "off", cfg


def test_checkpoint_keep_bounds_disk_growth(server_mod, home, monkeypatch):
    """开续训带来的新问题：optimizer.pt 一路落盘会把磁盘吃空，必须有上限。"""
    d = _training(server_mod, "checkpoint 20 auto 2")
    assert d["written"] and d["keep"] == 2, d
    assert T.checkpoint_cfg()["keep"] == 2, T.checkpoint_cfg()

    gr = home
    ck_root = Path(gr.ADAPTER_DIR) / "checkpoints"
    for step in (2, 4, 6, 8):
        _fake_ckpt(gr, step, optimizer=True)
    assert _ck_steps(ck_root) == [2, 4, 6, 8]
    tr = _core(gr)
    assert tr._rotate_checkpoints() == ["step2", "step4"], tr
    assert _ck_steps(ck_root) == [6, 8]
    # 再落一个新的：只多删一个最旧的，最新的两个留着
    _fake_ckpt(gr, 10, optimizer=True)
    assert tr._rotate_checkpoints() == ["step6"], tr._rotate_checkpoints()
    assert _ck_steps(ck_root) == [8, 10]


def _ck_steps(ck_root: Path) -> list:
    """按步数排序（字符串排序会把 step10 排在 step8 前面）。"""
    return sorted(int(p.name[4:]) for p in ck_root.iterdir()
                  if p.name.startswith("step"))


def test_rotation_never_touches_non_step_dirs_or_the_newest(home):
    _set_growth_cfg(checkpoint_keep=1)
    tr = _core(home)
    ck_root = Path(home.ADAPTER_DIR) / "checkpoints"
    for step in (2, 4, 6):
        _fake_ckpt(home, step, optimizer=True)
    (ck_root / "my_backup").mkdir(exist_ok=True)
    (ck_root / "my_backup" / "keep.txt").write_text("x", encoding="utf-8")
    pruned = tr._rotate_checkpoints()
    assert pruned == ["step2", "step4"], pruned
    assert _ck_steps(ck_root) == [6], "最新那个不能被删"
    assert (ck_root / "my_backup" / "keep.txt").is_file(), "用户自己的目录不该动"


def test_rotation_is_a_no_op_when_nothing_is_over_the_cap(home):
    tr = _core(home)
    assert tr._rotate_checkpoints() == []          # 目录都不存在
    _fake_ckpt(home, 2, optimizer=True)
    assert tr._rotate_checkpoints() == []


def test_checkpoint_off_when_state_write_fails_is_not_silently_ok(server_mod,
                                                                  home,
                                                                  monkeypatch):
    """写不进配置时不能回一句「已关闭」——得说没写成。"""
    from core import config as C
    monkeypatch.setattr(C, "save", lambda *a, **k: (_ for _ in ()).throw(
        OSError("盘满")))
    d = _training(server_mod, "checkpoint 30 auto")
    assert d["ok"] is False and "配置写入失败" in d["error"], d


def test_unknown_training_op_lists_checkpoint(server_mod):
    d = _training(server_mod, "nonsense")
    assert "checkpoint" in d["error"], d
