#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比「原始项目压缩包」与「当前已提交到 Gitee 的工作区」。

背景：老板手上有项目最初的存档 `XLmodel-main.zip`，需要知道这几轮改动到底动了
哪些文件、每一处改了什么。直接肉眼比对几百个文件不现实，所以写这个脚本产出
结构化的差异清单。

用法：
    python tools/diff_vs_original.py --zip <原始.zip> [--out <报告.md>]

判定口径：
    新增       — 只在当前工作区有（git 已跟踪）
    删除       — 只在原始包里有，当前工作区没有
    修改       — 两边都有且内容不同
    一致       — 两边都有且内容完全相同
"""
import argparse
import hashlib
import io
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 比对时忽略的目录/文件（构建产物、缓存、本机数据，本来就不该入库）
IGNORE_PARTS = {
    '.git', '__pycache__', '.pytest_cache', 'node_modules',
    '.dart_tool', '.idea', 'build', 'dist', 'ephemeral',
    '.flutter-plugins-dependencies',
}
IGNORE_SUFFIX = {'.pyc', '.log', '.zip', '.exe', '.dll', '.so'}


def _norm(p: str) -> str:
    """统一路径分隔符，去掉开头的 XLmodel-main/ 前缀。"""
    p = p.replace('\\', '/')
    for pre in ('XLmodel-main/', './'):
        if p.startswith(pre):
            p = p[len(pre):]
    return p


def _ignored(p: str) -> bool:
    parts = p.split('/')
    if any(x in IGNORE_PARTS for x in parts[:-1]):
        return True
    if Path(p).suffix.lower() in IGNORE_SUFFIX:
        return True
    return False


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_zip(zpath: Path) -> dict:
    """读原始压缩包，返回 {相对路径: sha256}。"""
    out = {}
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            rel = _norm(info.filename)
            if not rel or _ignored(rel):
                continue
            try:
                out[rel] = _sha(z.read(info))
            except Exception as e:
                print(f'  [读取失败] {rel}: {e}', file=sys.stderr)
    return out


def git_tracked(git_root: Path) -> list:
    """列出 git 已跟踪的文件（这正是"提交到 Gitee 的内容"）。"""
    r = subprocess.run(['git', 'ls-files'], cwd=git_root,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    if r.returncode != 0:
        print('git ls-files 失败：', r.stderr, file=sys.stderr)
        sys.exit(1)
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def load_current(git_root: Path) -> dict:
    """读当前工作区中 git 已跟踪的文件，返回 {相对路径: sha256}。"""
    out = {}
    for rel in git_tracked(git_root):
        rel = _norm(rel)
        if _ignored(rel):
            continue
        f = git_root / rel
        if not f.is_file():
            continue
        out[rel] = _sha(f.read_bytes())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description='对比原始压缩包与当前工作区')
    ap.add_argument('--zip', default=r'C:\Users\MVP\Desktop\XLmodel-main.zip',
                    help='原始项目压缩包路径')
    ap.add_argument('--git-root', default=str(ROOT), help='当前 git 仓库根')
    ap.add_argument('--list-only', action='store_true', help='只打印统计，不逐条列文件')
    args = ap.parse_args()

    zpath = Path(args.zip)
    groot = Path(args.git_root)

    print(f'原始包：{zpath}')
    print(f'当前库：{groot}')

    old = load_zip(zpath)
    new = load_current(groot)
    print(f'原始包文件数：{len(old)}')
    print(f'当前已跟踪：{len(new)}')

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    common = sorted(set(old) & set(new))
    modified = sorted(p for p in common if old[p] != new[p])
    same = [p for p in common if old[p] == new[p]]

    print()
    print(f'新增 {len(added)} / 删除 {len(removed)} / 修改 {len(modified)} / 一致 {len(same)}')

    # 按顶层目录归类，便于人读
    def group(paths):
        g = defaultdict(list)
        for p in paths:
            top = p.split('/')[0] if '/' in p else '(根目录)'
            g[top].append(p)
        return g

    if not args.list_only:
        for title, paths in (('新增', added), ('删除', removed), ('修改', modified)):
            if not paths:
                continue
            print(f'\n===== {title} ({len(paths)}) =====')
            for top, items in sorted(group(paths).items()):
                print(f'  [{top}] {len(items)} 个')
                for p in items:
                    print(f'    {p}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
