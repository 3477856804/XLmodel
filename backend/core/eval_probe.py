"""小凌 · 晋升前的生成式验收（真跑一次推理，而不是只看 loss）

为什么需要这个模块
------------------
成长管线以前判断「这一轮训练有没有变好」只看 loss / 验证 loss。
loss 下降并不等于人格还在：小模型 LoRA 最常见的失败模式是**灾难性
遗忘** —— loss 一路降，同时把名字、记忆、说话风格全忘掉，甚至退化成
复读机。只看曲线的结果是「数字更好了，人没了」，而晋升是按数字做的。

这里补的是另一半：拿一组**固定探针问题**，用同一套解码参数
（greedy、同一 max_new_tokens）对新权重和基座各生成一次，逐条比对，
产出可核对的事实现场：
  - identity    还认得自己叫什么 / 是什么
  - style       该出现的语气词还在不在、有没有退回通用助手腔
  - degenerate  是否退化成复读（同一 n-gram 高频重复）或空输出

诚实约定
--------
- 探针必须**真实生成**才计分。加载失败 / 生成超时 / 环境没 torch 时，
  返回 ok=False + reason，绝不给一个「全 0 分」冒充「测过了」。
- 分数只统计**真的跑过**的探针；跳过的条目单独列 skipped。
- 判定阈值写死在常量里并在报告里回显，前端不要自己另算一套。
- 这个模块不自动否决晋升，只把事实交给调用方（UI 与 growth 的
  晋升门槛都读它），避免「脚本一跑就把用户训练成果删了」。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

# 探针集：expect 是「必须出现」的关键词（任一命中即通过），
# forbid 是「不该出现」的关键词。全部用小模型也吃得下的短问句。
PROBES: list[dict] = [
    {"id": "who_are_you", "kind": "identity",
     "prompt": "你是谁？", "expect": ["小凌", "小灵", "XiaoLing", "AI", "人工智能"]},
    {"id": "what_are_you", "kind": "identity",
     "prompt": "你是什么做的？",
     "expect": ["模型", "语言模型", "AI", "人工智能", "程序", "神经网络"]},
    {"id": "greeting_style", "kind": "style",
     "prompt": "打个招呼",
     "expect": ["你好", "嗨", "哈喽", "Hi", "hello", "Hello"]},
    {"id": "not_generic", "kind": "style",
     "prompt": "你是谁？",
     "expect": [], "forbid": ["作为一个大型语言模型，我无法",
                              "I'm just an AI"]},
]

# 复读判定：同一个 4-gram 在 32 个 token 内出现次数达到这个值即视为退化
REPEAT_NGRAM = 4
REPEAT_MIN_HITS = 3
MAX_NEW_TOKENS = 32
PASS_RATE = 0.75          # 通过率达到这个值才算「人格没被训坏」


def _degenerate(text: str) -> bool:
    """复读/塌缩检测：n-gram 高频重复，或输出短到没有信息。"""
    t = (text or "").strip()
    if not t:
        return True
    chars = [c for c in t if not c.isspace()]
    if len(chars) < 4:
        return False            # 太短不算复读（可能是正常短答）
    n = REPEAT_NGRAM
    seen: dict[str, int] = {}
    for i in range(len(chars) - n + 1):
        g = "".join(chars[i:i + n])
        seen[g] = seen.get(g, 0) + 1
    return any(v >= REPEAT_MIN_HITS for v in seen.values())


def run_probes(model_dir: str | Path, *, teacher_dir: str | Path | None = None,
               max_new_tokens: int = MAX_NEW_TOKENS,
               timeout_sec: int = 600,
               pass_rate: float | None = None) -> dict:
    """对一个模型目录跑全部探针，返回逐条事实 + 汇总。

    teacher_dir 给了就同时跑一遍"对照模型"，用于回答「这轮训练到底
    让哪几条变好/变坏了」——没有对照时只报绝对分数，不编造 delta。

    pass_rate 让调用方（growth 的晋升门槛读 config 里的 pass_threshold）
    覆盖模块默认阈值；不传就用 PASS_RATE。报告里的 threshold 字段回显
    **实际用的那一个**，前端不要自己另算。
    """
    threshold = PASS_RATE if pass_rate is None else float(pass_rate)
    t0 = time.time()
    d = Path(model_dir).expanduser()
    if not (d / "config.json").is_file():
        return {"ok": False, "reason": f"{d} 不是可加载的 HF 模型目录",
                "probes": [], "skipped": len(PROBES)}
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        return {"ok": False, "reason": f"缺少推理依赖（{e}），探针未执行",
                "probes": [], "skipped": len(PROBES)}

    def _generate_all(dirp: Path) -> tuple[dict[str, str], str]:
        try:
            tok = AutoTokenizer.from_pretrained(str(dirp), trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                str(dirp), trust_remote_code=True, low_cpu_mem_usage=True)
            model.eval()
        except Exception as e:
            return {}, f"{type(e).__name__}: {e}"
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        outs: dict[str, str] = {}
        for pr in PROBES:
            if time.time() - t0 > timeout_sec:
                return outs, "超时中止"
            try:
                ids = tok(pr["prompt"], return_tensors="pt")["input_ids"]
                with torch.no_grad():
                    gen = model.generate(input_ids=ids,
                                         max_new_tokens=max_new_tokens,
                                         do_sample=False,
                                         pad_token_id=tok.pad_token_id)
                new = gen[0][ids.shape[-1]:]
                outs[pr["id"]] = tok.decode(new, skip_special_tokens=True).strip()
            except Exception as e:
                outs[pr["id"]] = f"__ERROR__ {type(e).__name__}: {e}"
        return outs, ""

    cand, err = _generate_all(d)
    if err and not cand:
        return {"ok": False, "reason": f"候选模型推理失败：{err}",
                "probes": [], "skipped": len(PROBES)}
    ref: dict[str, str] = {}
    ref_err = ""
    if teacher_dir:
        tp = Path(teacher_dir).expanduser()
        if (tp / "config.json").is_file():
            ref, ref_err = _generate_all(tp)
        else:
            ref_err = f"对照目录不是 HF 模型：{tp}"

    rows: list[dict] = []
    passed = 0
    ran = 0
    for pr in PROBES:
        text = cand.get(pr["id"])
        if text is None:
            rows.append({"id": pr["id"], "kind": pr["kind"], "ran": False,
                         "note": "未生成（超时或提前中止）"})
            continue
        ran += 1
        if text.startswith("__ERROR__"):
            rows.append({"id": pr["id"], "kind": pr["kind"], "ran": True,
                         "ok": False, "output": text, "note": "生成过程报错"})
            continue
        deg = _degenerate(text)
        forbid_hit = next((f for f in pr.get("forbid", []) if f in text), None)
        expect_hit = (True if not pr.get("expect")
                      else any(e in text for e in pr["expect"]))
        ok = expect_hit and forbid_hit is None and not deg
        passed += 1 if ok else 0
        row = {"id": pr["id"], "kind": pr["kind"], "ran": True, "ok": ok,
               "prompt": pr["prompt"], "output": text[:240],
               "expect_hit": expect_hit, "degenerate": deg}
        if forbid_hit:
            row["forbid_hit"] = forbid_hit
        if pr["id"] in ref:
            row["ref_output"] = ref[pr["id"]][:240]
        rows.append(row)

    rate = (passed / ran) if ran else 0.0
    return {
        "ok": ran > 0,
        "model_dir": str(d),
        "ran": ran, "skipped": len(PROBES) - ran,
        "passed": passed, "pass_rate": round(rate, 3),
        "threshold": threshold,
        "verdict": ("pass" if ran and rate >= threshold
                    else "fail" if ran else "unknown"),
        "ref_error": ref_err,
        "probes": rows,
        "elapsed_sec": round(time.time() - t0, 2),
        "decoded_with": {"do_sample": False, "max_new_tokens": max_new_tokens},
    }


def summarize(report: dict) -> str:
    """一行结论，给日志与 UI 直接显示，不重新发明判定。"""
    if not report.get("ok"):
        return f"验收未完成：{report.get('reason', '未知原因')}"
    v = report["verdict"]
    line = (f"{v}：{report['passed']}/{report['ran']} 条探针通过"
            f"（阈值 {report['threshold']}）")
    if report.get("skipped"):
        line += f"，{report['skipped']} 条未跑到"
    bad = [r["id"] for r in report.get("probes", []) if r.get("ran") and not r.get("ok")]
    if bad:
        line += f"；未通过：{', '.join(bad)}"
    return line


def probe_definitions() -> str:
    return json.dumps(PROBES, ensure_ascii=False)
