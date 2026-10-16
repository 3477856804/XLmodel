#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调色板对比度体检（Apple HIG《Color》+ WCAG 2.1）。

为什么要有这个脚本：上一版配色只做了 light/dark 两档，而且浅色模式的
强调色是「深色一点点的品牌色」，从来没验过对比度 —— 实测 light 模式下
gold/green/orange/cyan 在卡片上只有 2.8~3.4:1，正文文字（text3/text4）
最低 2.8:1，全都不达标。配色这种东西肉眼看不出 4.5 和 3.0 的差别，
只能算。

用法：
    python3 tools/contrast_audit.py                 # 全量报告
    python3 tools/contrast_audit.py --strict        # 有不达标项就退出码 1

它直接解析 frontend/lib/theme/theme.dart 里的 XlPalette 常量块，
所以改了颜色重新跑一遍即可，不需要跑 Flutter。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

THEME = Path(__file__).resolve().parent.parent / "frontend" / "lib" / "theme" / "theme.dart"

# role -> (最低对比度, 说明)。前景色按 WCAG/Apple 的 4.5:1 正文标准，
# 装饰/大字号用 3:1；hover/ripple 这类半透明的不算文字，跳过。
FG_RULES = {
    "text1": (7.0, "主文字 AAA"),
    "text2": (7.0, "次级文字 AAA"),
    "text3": (4.5, "三级文字 AA"),
    "text4": (4.5, "四级文字 AA"),
    "decor": (4.5, "图标/说明文字 AA"),
    "pink": (4.5, "强调色当文字用 AA"),
    "gold": (4.5, "强调色当文字用 AA"),
    "violet": (4.5, "强调色当文字用 AA"),
    "green": (4.5, "状态：成功 AA"),
    "red": (4.5, "状态：危险 AA"),
    "blue": (4.5, "状态：信息 AA"),
    "orange": (4.5, "状态：警告 AA"),
    "cyan": (4.5, "状态：辅助 AA"),
}

# 按钮墨色相对各档品牌底色的最低对比度（这些底上一定放文字/图标）。
INK_BG = {
    "btnInk": ["gradBrand", "btnFace", "gradBrandH", "gradBrandV", "btnFaceV"],
}


def parse_hex(literal: str) -> tuple[int, int, int, int]:
    """(A, R, G, B) —— 注意顺序：取 RGB 要用 [1:4]。"""
    h = literal[-8:]
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))


def channel_lin(c8: int) -> float:
    c = c8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rel_lum(rgb: tuple[int, int, int]) -> float:
    r, g, b = (channel_lin(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = rel_lum(a), rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def blend(bg: tuple[int, int, int], lit: str) -> tuple[int, int, int]:
    a, r, g, b = parse_hex(lit)
    al = a / 255.0
    return (round(r * al + bg[0] * (1 - al)),
            round(g * al + bg[1] * (1 - al)),
            round(b * al + bg[2] * (1 - al)))


def load_palettes() -> dict[str, dict]:
    src = THEME.read_text(encoding="utf-8")
    out: dict[str, dict] = {}
    for name in ("dark", "darkHc", "light", "lightHc"):
        m = re.search(r"static const %s = XlPalette\((.*?)\n  \);" % name, src, re.S)
        if not m:
            raise SystemExit("找不到 XlPalette.%s，theme.dart 结构变了" % name)
        body = m.group(1)
        colors: dict[str, str] = {}
        for mm in re.finditer(r"^\s{4}(\w+): Color\((0x[0-9A-Fa-f]{8})\),$", body, re.M):
            colors[mm.group(1)] = mm.group(2)
        grads: dict[str, list[str]] = {}
        for mm in re.finditer(r"^\s{4}(\w+): LinearGradient\((.*?)\n\s{4}\),$", body, re.S | re.M):
            grads[mm.group(1)] = re.findall(r"0x[0-9A-Fa-f]{8}", mm.group(2))
        hc = re.search(r"^\s{4}hc: (true|false),$", body, re.M)
        dark = re.search(r"^\s{4}isDark: (true|false),$", body, re.M)
        out[name] = {
            "colors": colors,
            "grads": grads,
            "hc": hc.group(1) == "true",
            "dark": dark.group(1) == "true",
        }
    return out


def audit(pal: dict, name: str) -> list[str]:
    problems: list[str] = []
    c = pal["colors"]
    surfaces = {k: parse_hex(c[k])[1:4] for k in ("bg", "surface", "surfaceHi", "surfaceLo", "screen") if k in c}
    for role, (need, why) in FG_RULES.items():
        if role not in c:
            continue
        rgb = parse_hex(c[role])[1:4]
        # 只报最差的那个面，卡片可能落在任一档上
        worst_bg, worst = "", 99.0
        for sname, srgb in surfaces.items():
            r = contrast(rgb, srgb)
            if r < worst:
                worst, worst_bg = r, sname
        if worst < need:
            problems.append(
                "%-9s %-7s %s  vs %-10s %4.2f < %.1f (%s)"
                % (name, role, c[role][2:], worst_bg, worst, need, why)
            )
    # 半透明前景色（pinkSoft 之类）合成后再看一次，避免「看着有色其实糊成一片」
    for role in ("pinkSoft", "goldSoft", "divider"):
        if role not in c:
            continue
        fg = blend(surfaces["surface"], c[role])
        r = contrast(fg, surfaces["surface"])
        if r < 1.02:
            problems.append("%-9s %-7s %s 合成后与 surface 几乎无差别 (%.3f)" % (name, role, c[role][2:], r))
    for ink, bgs in INK_BG.items():
        if ink not in c:
            continue
        rgb = parse_hex(c[ink])[1:4]
        for gname in bgs:
            stops = [s for s in pal["grads"].get(gname, []) if s[-2:] != "00"]
            if not stops:
                continue
            worst, worst_stop = 99.0, ""
            for s in stops:
                r = contrast(rgb, parse_hex(s)[1:4])
                if r < worst:
                    worst, worst_stop = r, s
            if worst < 4.5:
                problems.append(
                    "%-9s %-7s %s 在 %s(%s) 上只有 %4.2f（按钮文字需 4.5）"
                    % (name, ink, c[ink][2:], gname, worst_stop[2:], worst)
                )
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="有未达标项则退出码 1")
    args = ap.parse_args()
    pals = load_palettes()
    all_problems: list[str] = []
    for name in ("dark", "darkHc", "light", "lightHc"):
        probs = audit(pals[name], name)
        all_problems += probs
        tag = "hc=%s isDark=%s" % (pals[name]["hc"], pals[name]["dark"])
        print("%-8s %-22s %s" % (name, tag, "OK" if not probs else "%d 项待修" % len(probs)))
        for p in probs:
            print("   " + p)
    if all_problems:
        print("\n合计 %d 项未达标" % len(all_problems))
        return 1 if args.strict else 0
    print("\n全部达标：四个变体的前景/背景对比度都满足 HIG + WCAG AA（正文 4.5:1，主标题 7:1）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
