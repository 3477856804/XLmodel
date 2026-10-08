#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐个 diff「原始包」与「当前工作区」，产出可读的变更摘要。

输出分两部分：
  1) 统计表：每个改动文件的 +/- 行数、规模变化
  2) 变更片段：增删的代码行（按文件分组），便于人工写说明

用法：
    python tools/diff_detail.py [--orig <解压后的原始目录>] [--max-lines N]
"""
import argparse
import difflib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ORIG = Path(r'C:\Users\MVP\AppData\Local\Temp\xl_orig\XLmodel-main')

IGNORE_PARTS = {
    '.git', '__pycache__', '.pytest_cache', 'node_modules',
    '.dart_tool', '.idea', 'build', 'dist', 'ephemeral',
}
IGNORE_SUFFIX = {'.pyc', '.log', '.zip', '.exe', '.dll', '.so', '.vrm', '.vrma',
                 '.fbx', '.png', '.ôtdat'}


def _read(p: Path) -> list:
    try:
        return p.read_text(encoding='utf-8', errors='replace').splitlines()
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--orig', default=str(DEFAULT_ORIG))
    ap.add_argument('--files', nargs='*', default=None,
                    help='只看指定文件（相对路径），默认全部改动文件')
    ap.add_argument('--max-lines', type=int, default=40,
                    help='每个文件最多打印多少行变更片段')
    args = ap.parse_args()

    orig_root = Path(args.orig)
    if not orig_root.is_dir():
        print(f'原始目录不存在：{orig_root}', file=sys.stderr)
        return 1

    targets = args.files
    if targets is None:
        # 遍历当前 git 跟踪的文件（复用 diff_vs_original 的忽略规则）
        sys.path.insert(0, str(ROOT / 'tools'))
        import diff_vs_original as dv
        cur = {p: None for p in dv.load_current(ROOT).keys()}
        old_files = set()
        for dp, _dn, fn in os.walk(orig_root):
            if any(x in IGNORE_PARTS for x in Path(dp).parts):
                continue
            for f in fn:
                rel = str(Path(dp).relative_to(orig_root) / f).replace('\\', '/')
                old_files.add(rel)
        targets = sorted(p for p in cur if p in old_files)

    print(f'比对 {len(targets)} 个文件：{orig_root}  ->  {ROOT}\n')

    changed = []
    for rel in targets:
        a = orig_root / rel
        b = ROOT / rel
        if not a.is_file() or not b.is_file():
            continue
        la, lb = _read(a), _read(b)
        if la == lb:
            continue
        added = sum(1 for l in difflib.unified_diff(
            la, lb, n=0, lineterm='') if l.startswith('+') and not l.startswith('+++'))
        removed = sum(1 for l in difflib.unified_diff(
            la, lb, n=0, lineterm='') if l.startswith('-') and not l.startswith('---'))
        changed.append((rel, len(la), len(lb), added, removed))

    changed.sort(key=lambda x: -(x[3] + x[4]))
    print('=== 变更统计（按改动量排序）===')
    print(f'{"文件":<58} {"原行数":>7} {"现行数":>7} {"增":>6} {"删":>6}')
    for rel, la, lb, add, rem in changed:
        print(f'{rel:<58} {la:>7} {lb:>7} {add:>6} {rem:>6}')
    print(f'\n合计 {len(changed)} 个文件有内容差异')

    # 打印变更片段
    print('\n\n=== 变更片段 ===')
    for rel, la, lb, add, rem in changed:
        print(f'\n{"=" * 78}\n### {rel}   原 {la} 行 -> 现 {lb} 行   (+{add} / -{rem})')
        d = list(difflib.unified_diff(
            _read(orig_root / rel), _read(ROOT / rel),
            fromfile='原始', tofile='当前', n=1, lineterm=''))
        shown = 0
        for line in d[2:]:
            if shown >= args.max_lines:
                print(f'  ... （还有 {len(d) - 2 - shown} 行变更未显示）')
                break
            print('  ' + line[:300])
            shown += 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
