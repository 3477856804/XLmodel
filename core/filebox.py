#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 文件工具箱（迁移自小玥的 scripts/*.js）
=================================================

小玥用 Node 脚本实现的三件套，这里用 Python 统一重写：

  * `organize(dir)`       按类型/日期整理文件夹
  * `compress_images(dir)`PNG → JPG 压缩（可选保底质量）
  * `compress_video(path)`视频压缩（ffmpeg 可用时）
  * `dedupe(dir)`        按内容哈希去重
  * `scan(dir)`          先扫描出报告（只读，安全），再决定是否执行
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path

IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.heic'}
VIDEO_EXT = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv', '.wmv', '.m4v'}
DOC_EXT = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md', '.csv'}
ARCHIVE_EXT = {'.zip', '.rar', '.7z', '.tar', '.gz', '.xz'}
CODE_EXT = {'.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.go', '.rs', '.rb', '.php', '.cs', '.kt', '.swift'}


def human(n):
    for u, d in (('GB', 1024 ** 3), ('MB', 1024 ** 2), ('KB', 1024)):
        if n >= d:
            return f'{n / d:.1f} {u}'
    return f'{int(n)} B'


def category(p: Path) -> str:
    e = p.suffix.lower()
    if e in IMAGE_EXT:
        return '图片'
    if e in VIDEO_EXT:
        return '视频'
    if e in DOC_EXT:
        return '文档'
    if e in ARCHIVE_EXT:
        return '压缩包'
    if e in CODE_EXT:
        return '代码'
    if e in ('.mp3', '.wav', '.flac', '.m4a', '.ogg'):
        return '音频'
    return '其他'


def scan(dir_path) -> dict:
    d = Path(dir_path)
    if not d.exists():
        return {'error': f'目录不存在：{d}'}
    files = [p for p in d.rglob('*') if p.is_file()]
    by_cat = defaultdict(lambda: {'count': 0, 'bytes': 0})
    for p in files:
        c = category(p)
        by_cat[c]['count'] += 1
        by_cat[c]['bytes'] += p.stat().st_size
    dup = defaultdict(list)
    for p in files:
        if p.stat().st_size > 1024:
            dup[hashlib.sha1(p.read_bytes()).hexdigest()].append(str(p))
    dups = {k: v for k, v in dup.items() if len(v) > 1}
    return {'dir': str(d), 'files': len(files),
            'bytes': sum(p.stat().st_size for p in files),
            'bytes_human': human(sum(p.stat().st_size for p in files)),
            'by_category': {k: {'count': v['count'], 'size': human(v['bytes'])} for k, v in by_cat.items()},
            'duplicates': dups, 'duplicate_groups': len(dups)}


def organize(dir_path, dry_run=True) -> dict:
    d = Path(dir_path)
    moved = []
    for p in list(d.rglob('*')):
        if not p.is_file() or p.parent != d:
            continue
        cat = category(p)
        dst = d / cat
        if not dry_run:
            dst.mkdir(exist_ok=True)
            target = dst / p.name
            if target.exists():
                target = dst / f'{p.stem}_{int(time.time())}{p.suffix}'
            shutil.move(str(p), str(target))
        moved.append({'file': p.name, 'to': cat, 'size': human(p.stat().st_size)})
    return {'dir': str(d), 'dry_run': dry_run, 'moved': moved, 'count': len(moved)}


def compress_images(dir_path, quality=82, max_side=2560, dry_run=True) -> dict:
    from PIL import Image
    d = Path(dir_path)
    out = []
    for p in list(d.rglob('*.png')):
        try:
            before = p.stat().st_size
            im = Image.open(p).convert('RGB')
            if max(im.size) > max_side:
                r = max_side / max(im.size)
                im = im.resize((int(im.size[0] * r), int(im.size[1] * r)), Image.LANCZOS)
            dst = p.with_suffix('.jpg')
            if not dry_run:
                im.save(dst, 'JPEG', quality=quality, optimize=True)
                p.unlink()
            after = dst.stat().st_size if dst.exists() else 0
            out.append({'file': p.name, 'before': human(before), 'after': human(after),
                        'saved': f'{(1 - after / max(before, 1)) * 100:.0f}%'})
        except Exception as e:                                        # noqa: BLE001
            out.append({'file': p.name, 'error': str(e)})
    return {'dir': str(d), 'dry_run': dry_run, 'items': out, 'count': len(out)}


def compress_video(path, crf=26, dry_run=True) -> dict:
    p = Path(path)
    if not shutil.which('ffmpeg'):
        return {'error': '未安装 ffmpeg，无法压缩视频'}
    dst = p.with_name(f'{p.stem}_compressed.mp4')
    if dry_run:
        return {'file': str(p), 'dry_run': True, 'target': str(dst), 'size': human(p.stat().st_size)}
    cmd = ['ffmpeg', '-y', '-i', str(p), '-vcodec', 'libx264', '-crf', str(crf),
           '-preset', 'medium', '-acodec', 'aac', '-b:a', '128k', str(dst)]
    subprocess.run(cmd, check=True, timeout=3600, capture_output=True)
    return {'file': str(p), 'target': str(dst), 'size': human(dst.stat().st_size)}


def dedupe(dir_path, dry_run=True) -> dict:
    d = Path(dir_path)
    seen, removed = {}, []
    for p in sorted(d.rglob('*')):
        if not p.is_file():
            continue
        try:
            h = hashlib.sha1(p.read_bytes()).hexdigest()
        except OSError:
            continue
        if h in seen:
            if not dry_run:
                p.unlink()
            removed.append({'removed': str(p), 'keep': seen[h]})
        else:
            seen[h] = str(p)
    return {'dir': str(d), 'dry_run': dry_run, 'removed': removed, 'count': len(removed)}


if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    target = sys.argv[2] if len(sys.argv) > 2 else '.'
    fn = {'scan': scan, 'organize': organize, 'compress': compress_images, 'dedupe': dedupe}.get(cmd, scan)
    print(json.dumps(fn(target), ensure_ascii=False, indent=1)[:2000])
