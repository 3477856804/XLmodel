"""小凌 · 成长权重导出（LoRA 合并 → 独立 HF 模型 → GGUF 通道）

为什么需要这个模块
------------------
训练侧只能吃 HF 格式（safetensors/bin），推理侧的主力却是 GGUF
（llama.cpp，四端都靠它跑本地模型）。这两边以前是断的：
`trainer.py` 明确拒绝 GGUF 训练，而训练产出的 adapter 只有走
transformers + peft 的慢路径才用得上，集显机器基本不会去走。
结果就是「本地成长」长出来的东西没法被日常使用的那个模型加载。

这一环补上：训练完成后把 adapter **合并**回基座，产出一个不依赖
peft 的独立 HF 模型目录，落在模型商店会扫到的位置；GGUF 转换
本身需要 llama.cpp 的 convert 脚本（体积与构建依赖都不适合随包分发），
所以这里只做**如实的能力探测 + 可执行的下一步**，绝不在缺工具时
假装导出成功。

诚实约定（项目惯例）
--------------------
- 任何一步失败都返回 ok=False + 真实原因，不返回半成品路径。
- `gguf` 字段描述的是「本机现在能不能转 GGUF」，取不到工具就
  reason 里写清楚缺什么、怎么给（环境变量 XIAOLING_LLAMA_CPP）。
- 合并是真实计算：加载基座 + 加载 adapter + merge_and_unload +
  save_pretrained，产物必须能被 AutoModelForCausalLM 独立重新加载
  才算成功（在 _verify 里真的重加载并生成一次）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# 合并后模型的命名后缀：模型商店里一眼能看出这是「长大的」而不是原基座
MERGED_SUFFIX = "+grown"


def _star_models_dir() -> Path:
    try:
        from .config import STAR_DIR
        return STAR_DIR / "models"
    except Exception:
        env = os.environ.get("XIAOLING_HOME")
        base = Path(env).resolve() if env else Path.cwd().resolve()
        return base / ".star_core" / "models"


def _adapter_dir() -> Path:
    from .trainer import _resolve_adapter_dir
    return _resolve_adapter_dir()


def _base_dir(adapter_dir: Path) -> tuple[Path | None, str]:
    """基座目录：优先 adapter_config.json 里记的那一个。

    不能靠 _resolve_model_dir 的「扫 models/ 找第一个能加载的」兜底：
    用户装了多个 safetensors 模型时，那会把 A 模型的 adapter 合到
    B 模型上，产出一个两边都不是的权重。合并必须用训练时那份基座。
    """
    cfg = adapter_dir / "adapter_config.json"
    if cfg.is_file():
        try:
            rec = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception as e:
            return None, f"adapter_config.json 解析失败：{type(e).__name__}: {e}"
        src = str(rec.get("base_model_name_or_path") or "").strip()
        if src:
            p = Path(src).expanduser()
            if p.is_dir() and (p / "config.json").is_file():
                return p, ""
            return None, (f"适配器记录的基座不存在或已改名：{src}。"
                          "请先把它放回原位，或重新训练一次。")
        return None, "adapter_config.json 里没有 base_model_name_or_path，无法确定基座"
    return None, "适配器目录里没有 adapter_config.json，不像是一个训练产物"


def find_llama_cpp() -> dict:
    """探测本机 llama.cpp 的 HF→GGUF 转换能力（只读，不安装）。

    查找顺序：XIAOLING_LLAMA_CPP 指向的目录 → PATH 上的
    convert_hf_to_gguf.py / llama-quantize → 常见的仓库检出位置。
    """
    def _probe(root: str) -> dict | None:
        d = Path(root).expanduser()
        if not d.is_dir():
            return None
        conv = None
        for cand in (d / "convert_hf_to_gguf.py",
                     d / "examples" / "convert_hf_to_gguf.py",
                     d / "gguf-py" / "examples" / "convert_hf_to_gguf.py"):
            if cand.is_file():
                conv = cand
                break
        if conv is None:
            return None
        quant = shutil.which("llama-quantize", path=str(d / "build" / "bin")) or \
            shutil.which("llama-quantize")
        return {"dir": str(d), "convert": str(conv), "quantize": quant}

    env = (os.environ.get("XIAOLING_LLAMA_CPP") or "").strip()
    tried: list[str] = []
    if env:
        tried.append(env)
        hit = _probe(env)
        if hit:
            return {"found": True, "source": "env", **hit}
    which = shutil.which("convert_hf_to_gguf.py")
    if which:
        hit = _probe(str(Path(which).parent))
        if hit:
            return {"found": True, "source": "PATH", **hit}
    for guess in ("~/llama.cpp", "/opt/llama.cpp", "/usr/local/llama.cpp",
                  "~/src/llama.cpp"):
        tried.append(guess)
        hit = _probe(guess)
        if hit:
            return {"found": True, "source": "probe", **hit}
    return {"found": False,
            "reason": ("没找到 llama.cpp 的 convert_hf_to_gguf.py。"
                       "合并出的 HF 模型已经能直接用 transformers 跑；"
                       "要转 GGUF 请 clone https://github.com/ggml-org/llama.cpp "
                       "并把路径写进环境变量 XIAOLING_LLAMA_CPP。"
                       f"（已尝试：{', '.join(tried) or '无'}）")}


def _free_bytes(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return shutil.disk_usage(str(probe)).free
    except Exception:
        return 0


def _weight_bytes(d: Path) -> int:
    total = 0
    for p in d.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".safetensors", ".bin"):
            total += p.stat().st_size
    return total


def merge_status() -> dict:
    """导出条件的只读快照（给设置页/成长页如实展示，不做任何写入）。"""
    ad = _adapter_dir()
    has_adapter = (ad / "adapter_model.safetensors").is_file()
    base, err = _base_dir(ad) if has_adapter else (None, "没有已训练的适配器")
    llama = find_llama_cpp()
    out_root = _star_models_dir()
    return {
        "ok": True,
        "adapter_dir": str(ad),
        "has_adapter": has_adapter,
        "base_dir": str(base) if base else "",
        "base_error": err,
        "merged_models": sorted(
            p.name for p in out_root.iterdir()
            if p.is_dir() and p.name.endswith(MERGED_SUFFIX))
        if out_root.is_dir() else [],
        "gguf": llama,
        "free_bytes": _free_bytes(out_root),
    }


def merge_adapter(*, out_name: str | None = None,
                  keep_tokenizer: bool = True) -> dict:
    """把当前 LoRA adapter 合并进基座，产出独立 HF 模型目录。

    返回 {ok, path, name, ...}；失败时 ok=False 且 reason 是真话。
    同步执行（CPU 上 1B 级模型约十几秒），调用方负责放到工作线程里。
    """
    t0 = time.time()
    ad = _adapter_dir()
    if not (ad / "adapter_model.safetensors").is_file():
        return {"ok": False, "stage": "adapter",
                "reason": f"适配器目录里没有权重文件：{ad}。先训练一轮再导出。"}
    base, err = _base_dir(ad)
    if base is None:
        return {"ok": False, "stage": "base", "reason": err}

    name = out_name or f"{base.name}{MERGED_SUFFIX}"
    out_root = _star_models_dir()
    out_dir = out_root / name
    if out_dir.exists():
        return {"ok": False, "stage": "out",
                "reason": f"目标已存在：{out_dir}。换名字或删除后重试。"}
    need = _weight_bytes(base)
    free = _free_bytes(out_root)
    if need and free and free < need * 1.2:
        return {"ok": False, "stage": "disk",
                "reason": (f"磁盘空间不足：合并约需 {need / 1e9:.2f}GB，"
                           f"{out_root} 只剩 {free / 1e9:.2f}GB")}

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        return {"ok": False, "stage": "deps",
                "reason": f"导出依赖未安装（{e}）。需要 torch / transformers / peft。"}

    try:
        tokenizer = AutoTokenizer.from_pretrained(str(base), trust_remote_code=True)
    except Exception as e:
        return {"ok": False, "stage": "tokenizer",
                "reason": f"tokenizer 加载失败：{type(e).__name__}: {e}"}
    try:
        loaded = AutoModelForCausalLM.from_pretrained(
            str(base), trust_remote_code=True, low_cpu_mem_usage=True)
    except Exception as e:
        return {"ok": False, "stage": "base",
                "reason": f"基座加载失败：{type(e).__name__}: {e}"}
    try:
        model = PeftModel.from_pretrained(loaded, str(ad))
        merged = model.merge_and_unload()
    except Exception as e:
        return {"ok": False, "stage": "merge",
                "reason": (f"LoRA 合并失败：{type(e).__name__}: {e}。"
                           "常见原因是适配器与基座不匹配（基座被换过）。")}
    try:
        merged.config.use_cache = True   # 训练期被关掉，导出给推理用必须打开
    except Exception:
        pass

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_dir.with_name(out_dir.name + ".writing")
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        tmp.mkdir(parents=True)
        merged.save_pretrained(str(tmp), safe_serialization=True)
        if keep_tokenizer:
            tokenizer.save_pretrained(str(tmp))
        prov = {
            "source_base": str(base),
            "source_adapter": str(ad),
            "merged_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "elapsed_sec": round(time.time() - t0, 2),
            "tool": "peft.merge_and_unload",
        }
        (tmp / "xiaoling_merge.json").write_text(
            json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(out_dir)
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return {"ok": False, "stage": "save",
                "reason": f"写出失败：{type(e).__name__}: {e}"}

    verify = _verify_merged(out_dir)
    if not verify["ok"]:
        shutil.rmtree(out_dir, ignore_errors=True)
        return {"ok": False, "stage": "verify",
                "reason": verify["reason"], "cleaned": str(out_dir)}

    return {"ok": True, "path": str(out_dir), "name": name,
            "base": str(base), "adapter": str(ad),
            "bytes": _weight_bytes(out_dir),
            "elapsed_sec": round(time.time() - t0, 2),
            "gguf": find_llama_cpp()}


def _verify_merged(out_dir: Path) -> dict:
    """独立重新加载 + 真生成一次：只有这一步过了才敢说导出成功。"""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(str(out_dir))
        m = AutoModelForCausalLM.from_pretrained(str(out_dir))
        ids = tok("你好", return_tensors="pt")["input_ids"]
        with torch.no_grad():
            g = m.generate(input_ids=ids, max_new_tokens=4, do_sample=False)
        if g.shape[-1] <= ids.shape[-1]:
            return {"ok": False, "reason": "重新加载后没有产出新 token"}
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "reason": f"产物自检失败：{type(e).__name__}: {e}"}


def convert_to_gguf(model_dir: str | Path, *, quant: str = "q4_k_m") -> dict:
    """用本机 llama.cpp 把一个 HF 目录转成 GGUF，并可选量化。

    没有 llama.cpp 时如实返回不可用（不下载、不 pip install）。
    quant="f16"/"none" 表示只要全精度 GGUF，不调 llama-quantize。
    转换是子进程长任务，调用方负责放后台线程并轮询进度。
    """
    d = Path(model_dir).expanduser()
    if not (d / "config.json").is_file():
        return {"ok": False, "reason": f"{d} 不是一个 HF 模型目录"}
    llama = find_llama_cpp()
    if not llama.get("found"):
        return {"ok": False, "reason": llama["reason"]}
    f16 = d / f"{d.name}-f16.gguf"
    cmd = [sys.executable or "python3", llama["convert"], str(d),
           "--outfile", str(f16)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "转换超时（>1 小时），已中止"}
    except Exception as e:
        return {"ok": False, "reason": f"启动转换失败：{type(e).__name__}: {e}"}
    if r.returncode != 0 or not f16.is_file():
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-5:]
        return {"ok": False, "reason": "convert_hf_to_gguf.py 退出码 "
                f"{r.returncode}：{' / '.join(tail) or '无输出'}"}
    out = {"ok": True, "gguf": str(f16), "bytes": f16.stat().st_size,
           "quant": "f16"}
    if quant and quant.lower() not in ("f16", "none"):
        qtool = llama.get("quantize")
        qpath = d / f"{d.name}-{quant}.gguf"
        if not qtool:
            out["quant_note"] = ("已产出 f16 GGUF；本机没有 llama-quantize，"
                                 f"未做 {quant} 量化。")
            return out
        try:
            rq = subprocess.run([qtool, str(f16), str(qpath), quant],
                                capture_output=True, text=True, timeout=3600)
        except Exception as e:
            out["quant_note"] = f"量化进程异常：{type(e).__name__}: {e}（保留 f16）"
            return out
        if rq.returncode == 0 and qpath.is_file():
            out.update(gguf=str(qpath), bytes=qpath.stat().st_size, quant=quant)
        else:
            tail = (rq.stderr or rq.stdout or "").strip().splitlines()[-3:]
            out["quant_note"] = (f"llama-quantize 退出码 {rq.returncode}："
                                 f"{' / '.join(tail) or '无输出'}（保留 f16）")
    return out
