#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成长权重导出 + 生成式验收 的真实链路测试。

覆盖「训练产物能不能真的被用起来」这一整环：
    真训一轮 LoRA → 合并回基座 → 独立重新加载 → 跑探针验收。
全部用 tiny-gpt2（约 5MB，CPU 秒级）跑真实权重，不 mock 模型；
环境里没有 torch/transformers 或本地没有该基座时整组跳过，
而不是伪造一个「通过」。
"""
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

TINY = Path(os.environ.get("XIAOLING_TEST_BASE", "/tmp/models/tiny-gpt2"))


def _ml_available() -> bool:
    try:
        import torch       # noqa: F401
        import peft        # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


needs_base = pytest.mark.skipif(
    not (TINY.is_dir() and (TINY / "config.json").is_file()) or not _ml_available(),
    reason=f"缺少可训练基座 {TINY} 或 torch/peft/transformers 未安装")

needs_gguf = pytest.mark.skipif(
    not (Path(os.path.expanduser("~/llama.cpp")).is_dir()
         or os.environ.get("XIAOLING_LLAMA_CPP")),
    reason="本机没有 llama.cpp，GGUF 转换用例跳过")


@pytest.fixture()
def star_home(tmp_path):
    """复用 test_growth 里已验证的 HOME 隔离（它会重映射全部 Path 常量）。

    不自己写一份：仓库里同一份源码存在两套模块对象（core.x 与 backend.core.x），
    只刷一套会让隔离**静默失效**并把产物写进真实工作区 —— test_growth 的
    _make_home 专门处理过这个坑，并自带「隔离失效就红着失败」的断言。
    """
    tg = importlib.import_module("test_growth")
    tg._make_home(tmp_path)
    return tmp_path


# --------------------------------------------------------------------------- #
#  导出（LoRA 合并）
# --------------------------------------------------------------------------- #

@needs_base
def test_merge_requires_an_adapter(star_home):
    """没训练过时必须如实拒绝，而不是产出一个等于基座的假「成长模型」。"""
    from core import export as E
    r = E.merge_adapter()
    assert r["ok"] is False
    assert r["stage"] == "adapter"
    assert "先训练" in r["reason"] or "没有权重" in r["reason"], r["reason"]
    assert not list((star_home / ".star_core" / "models").glob("*grown*"))


@needs_base
def test_merge_refuses_base_mismatch(star_home):
    """适配器记录的基座不存在时，绝不能退而求其次去合并别的模型。"""
    from core import export as E
    ad = E._adapter_dir()
    ad.mkdir(parents=True, exist_ok=True)
    (ad / "adapter_model.safetensors").write_bytes(b"x" * 2048)
    (ad / "adapter_config.json").write_text(
        json.dumps({"base_model_name_or_path": "/nonexistent/whatever-9B"}),
        encoding="utf-8")
    r = E.merge_adapter()
    assert r["ok"] is False and r["stage"] == "base", r
    assert "不存在" in r["reason"], r["reason"]


@needs_base
def test_real_train_then_merge_then_probe(star_home):
    """真链路：训练 → 合并 → 独立加载 → 生成式验收，全用真实权重。"""
    from core import trainer as T
    from core import export as E

    samples = [T.TrainSample(prompt=f"问{i}", completion=f"答{i}") for i in range(6)]
    tr = T.LoRATrainerCore(base_dir=str(TINY))
    list(tr.run(samples, steps=4, batch_size=2, lora_rank=4, max_length=48))
    assert tr.result.ok, tr.result.reason

    r = E.merge_adapter()
    assert r["ok"] is True, r
    out = Path(r["path"])
    assert out.name.endswith("+grown"), out.name
    assert (out / "config.json").is_file()
    assert (out / "model.safetensors").is_file() or list(out.glob("model*.safetensors"))
    assert (out / "tokenizer_config.json").is_file(), "缺 tokenizer 的模型没法直接用"
    assert r["bytes"] > 100 * 1024, f"合并产物体积异常：{r['bytes']}"

    prov = json.loads((out / "xiaoling_merge.json").read_text(encoding="utf-8"))
    assert prov["source_base"] == str(TINY), prov
    assert prov["tool"] == "peft.merge_and_unload", prov

    # 二次导出必须拒绝覆盖，不能悄悄把上一份冲掉
    r2 = E.merge_adapter()
    assert r2["ok"] is False and r2["stage"] == "out", r2

    from core import eval_probe as P
    rep = P.run_probes(out, teacher_dir=str(TINY))
    assert rep["ok"] is True, rep
    assert rep["ran"] > 0, rep
    assert rep["verdict"] in ("pass", "fail"), rep["verdict"]
    ran_rows = [row for row in rep["probes"] if row.get("ran")]
    assert ran_rows and all("output" in row for row in ran_rows), rep["probes"]
    assert all("ref_output" in row for row in ran_rows), \
        "给了对照模型就必须回填对照输出"
    assert "通过" in P.summarize(rep), P.summarize(rep)


@needs_base
def test_merge_status_is_read_only_and_honest(star_home):
    from core import export as E
    before = sorted(str(p) for p in (star_home / ".star_core").rglob("*"))
    s = E.merge_status()
    assert s["ok"] is True
    assert s["has_adapter"] is False
    assert "没有已训练的适配器" in s["base_error"], s
    assert s["merged_models"] == []
    after = sorted(str(p) for p in (star_home / ".star_core").rglob("*"))
    assert before == after, "merge_status 不该写任何东西"


def test_gguf_probe_reports_missing_tool_honestly(tmp_path, monkeypatch):
    """没有 llama.cpp 时必须说清缺什么、怎么补，而不是 ok=True。"""
    from core import export as E
    monkeypatch.delenv("XIAOLING_LLAMA_CPP", raising=False)
    monkeypatch.setattr(E, "find_llama_cpp", lambda: {
        "found": False, "reason": "没找到 llama.cpp 的 convert_hf_to_gguf.py"})
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    r = E.convert_to_gguf(tmp_path)
    assert r["ok"] is False and "llama.cpp" in r["reason"], r


def test_gguf_reason_names_the_env_var(monkeypatch, tmp_path):
    """真实探测路径（不 monkeypatch find）：缺工具时的提示必须可执行。"""
    from core import export as E
    monkeypatch.delenv("XIAOLING_LLAMA_CPP", raising=False)
    info = E.find_llama_cpp()
    assert info["found"] is False
    assert "XIAOLING_LLAMA_CPP" in info["reason"], info["reason"]


# --------------------------------------------------------------------------- #
#  GGUF 分线的「找到工具」分支：用桩工具验证**我们的接线**
#
#  桩不是 llama.cpp，因此这些用例证明的是：export.py 确实按约定顺序找到工具、
#  把正确的参数传给 convert_hf_to_gguf.py、正确解析退出码与 stderr、量化缺工具
#  时如实标注而不是谎报 quant。真实转换产物的正确性由下面的 needs_gguf 用例负责。
# --------------------------------------------------------------------------- #

_STUB_CONVERT = """\
import sys, pathlib
args = sys.argv[1:]
assert "--outfile" in args, args
out = pathlib.Path(args[args.index("--outfile") + 1])
if "FAIL" in out.name:
    sys.stderr.write("boom: unsupported arch\\n")
    sys.exit(1)
out.write_bytes(b"GGUF" + b"\\0" * 64)
print("wrote", out)
"""

_STUB_QUANTIZE = """\
import sys, pathlib
src, dst, mode = sys.argv[1], sys.argv[2], sys.argv[3]
assert pathlib.Path(src).is_file(), src
pathlib.Path(dst).write_bytes(b"GGUF" + mode.encode()[:8].ljust(8, b"\\0"))
"""


def _stub(body: str) -> str:
    """shebang 必须写绝对解释器：用例里 PATH 被收紧成只含桩目录，
    `#!/usr/bin/env python3` 那种写法会 127，测出来的就是假失败。"""
    return f"#!{sys.executable}\n" + body

@pytest.fixture()
def fake_llama(tmp_path, monkeypatch):
    """造一个假的 llama.cpp 检出目录，并把 PATH 收紧到只含它的 build/bin。"""
    root = tmp_path / "llama.cpp"
    (root / "examples").mkdir(parents=True)
    (root / "examples" / "convert_hf_to_gguf.py").write_text(
        _stub(_STUB_CONVERT), encoding="utf-8")
    conv = root / "convert_hf_to_gguf.py"
    conv.write_text(_stub(_STUB_CONVERT), encoding="utf-8")
    bindir = root / "build" / "bin"
    bindir.mkdir(parents=True)
    q = bindir / "llama-quantize"
    q.write_text(_stub(_STUB_QUANTIZE), encoding="utf-8")
    q.chmod(0o755)
    monkeypatch.setenv("XIAOLING_LLAMA_CPP", str(root))
    monkeypatch.setenv("PATH", str(bindir))
    return root, conv


def test_find_llama_cpp_uses_the_env_var(monkeypatch, tmp_path):
    """环境变量指向的目录优先，且要如实报告来源，供前端显示「工具来自哪」。"""
    from core import export as E
    monkeypatch.delenv("XIAOLING_LLAMA_CPP", raising=False)
    # 先确认 PATH 里干净（避免开发机真装了 llama.cpp 干扰本用例）
    if E.find_llama_cpp()["found"]:
        pytest.skip("本机真的装了 llama.cpp，无法验证「未找到」分支")
    root, conv = tmp_path / "lc", tmp_path / "lc" / "convert_hf_to_gguf.py"
    conv.parent.mkdir()
    conv.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    monkeypatch.setenv("XIAOLING_LLAMA_CPP", str(root))
    info = E.find_llama_cpp()
    assert info["found"] is True and info["source"] == "env", info
    assert Path(info["convert"]) == conv
    assert Path(info["convert"]).is_absolute()


@needs_base
def test_convert_to_gguf_found_branch_end_to_end(fake_llama, star_home):
    """有工具时真的走完 convert → quantize 两步，产物与字段都对得上。"""
    from core import export as E
    d = star_home / "hf_model"
    d.mkdir(parents=True)
    (d / "config.json").write_text("{}", encoding="utf-8")
    r = E.convert_to_gguf(d, quant="q4_k_m")
    assert r["ok"] is True, r
    final = Path(r["gguf"])
    assert final.name == "hf_model-q4_k_m.gguf", r   # 量化产物覆盖默认值
    assert final.read_bytes()[:4] == b"GGUF", r
    assert r["quant"] == "q4_k_m", r
    assert r["bytes"] == final.stat().st_size, r
    assert (d / "hf_model-f16.gguf").is_file(), "f16 中间产物应保留"
    assert "quant_note" not in r, r


@needs_base
def test_convert_to_gguf_without_quantize_reports_partial(fake_llama, star_home):
    """缺 llama-quantize 时：f16 产物算成功，但必须明说没量化，不能谎报 quant。"""
    from core import export as E
    root, _ = fake_llama
    (root / "build" / "bin" / "llama-quantize").unlink()
    d = star_home / "hf_nq"
    d.mkdir(parents=True)
    (d / "config.json").write_text("{}", encoding="utf-8")
    r = E.convert_to_gguf(d, quant="q4_k_m")
    assert r["ok"] is True and r["quant"] == "f16", r
    assert "quant_note" in r and "q4_k_m" in r["quant_note"], r


def test_convert_to_gguf_failure_keeps_exit_code_and_stderr(fake_llama, star_home):
    """转换失败时不能只说「失败」：退出码与 stderr 末行要带给用户。"""
    from core import export as E
    d = star_home / "FAIL_model"
    d.mkdir(parents=True)
    (d / "config.json").write_text("{}", encoding="utf-8")
    r = E.convert_to_gguf(d, quant="f16")
    assert r["ok"] is False, r
    assert "退出码 1" in r["reason"], r["reason"]
    assert "unsupported arch" in r["reason"], r["reason"]


def test_convert_to_gguf_rejects_non_hf_dir(fake_llama, tmp_path):
    from core import export as E
    r = E.convert_to_gguf(tmp_path / "does_not_exist")
    assert r["ok"] is False and "不是" in r["reason"], r


@needs_gguf
def test_convert_to_gguf_produces_a_real_file(star_home):
    """有 llama.cpp 时真的转出一个能打开的 GGUF（magic bytes 校验）。"""
    from core import export as E
    out = star_home / "hf_src"
    out.mkdir(parents=True)
    for f in (TINY / "config.json", TINY / "tokenizer_config.json",
              TINY / "vocab.json", TINY / "merges.txt"):
        if f.is_file():
            (out / f.name).write_bytes(f.read_bytes())
    w = TINY / "pytorch_model.bin"
    if w.is_file():
        (out / "model.safetensors").write_bytes(w.read_bytes())
    r = E.convert_to_gguf(out, quant="f16")
    assert r["ok"] is True, r
    assert Path(r["gguf"]).read_bytes()[:4] == b"GGUF", "产物不是 GGUF"


# --------------------------------------------------------------------------- #
#  生成式验收
# --------------------------------------------------------------------------- #

def test_degenerate_detector_is_real_not_stub():
    from core.eval_probe import _degenerate
    assert _degenerate("") is True
    assert _degenerate("好的") is False
    assert _degenerate("我是小凌我是小凌我是小凌我是小凌") is True
    assert _degenerate("我是小凌，很高兴认识你呀") is False


def test_probes_reject_non_model_dir(tmp_path):
    from core import eval_probe as P
    r = P.run_probes(tmp_path)
    assert r["ok"] is False and "不是可加载" in r["reason"], r


@needs_base
def test_probes_do_not_fabricate_scores(tmp_path):
    """加载不了的目录：ok=False 且 ran==0 —— 不能给 0 分冒充「测过了」。"""
    from core import eval_probe as P
    d = tmp_path / "broken"
    d.mkdir()
    (d / "config.json").write_text('{"architectures":["Nope"]}', encoding="utf-8")
    r = P.run_probes(d)
    assert r["ok"] is False, r
    assert r.get("ran", 0) == 0, r
    assert "未完成" in P.summarize(r), P.summarize(r)
