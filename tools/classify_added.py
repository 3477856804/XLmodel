#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按文件时间戳区分「新增」文件的真实来源。

背景：老板给的原始存档 XLmodel-main.zip 是**部分导出**（1.4MB，缺 packaging/、
tests/、shared/、plugins/、website/、tools/ 等整目录）。直接拿它跟当前工作区做
diff，会把一批"项目原本就有、只是没被打进 zip 的文件"误算成"本轮新增"。

区分依据：这批文件的磁盘 mtime 集中在某个更早的同一时刻（项目落地时间），
而本轮真正新建的文件 mtime 在当天的开发时段。本脚本据此二分，并打印结果。

用法：
    python tools/classify_added.py [--zip <原始.zip>] [--hour-split N]
"""
import argparse
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import diff_vs_original as dv  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', default=r'C:\Users\MVP\Desktop\XLmodel-main.zip')
    ap.add_argument('--hour-split', type=int, default=9,
                    help='几点之前算"项目自带"（默认 9 点）')
    args = ap.parse_args()

    old = set(dv.load_zip(Path(args.zip)).keys())
    new = dv.load_current(ROOT)
    added = sorted(set(new) - old)

    preexisting, newly = [], []
    for p in added:
        f = ROOT / p
        mt = datetime.datetime.fromtimestamp(f.stat().st_mtime)
        (preexisting if mt.hour < args.hour_split else newly).append(
            (p, mt.strftime('%m-%d %H:%M')))

    total = len(added)
    n_pre = len(preexisting)
    n_new = len(newly)
    print('新增文件 %d 个，其中：' % total)
    print('  A. 项目自带但 zip 未收录：%d 个' % n_pre)
    print('  B. 本轮改动真正新建   ：%d 个' % n_new)
    print()

    print('=== A. 项目自带（zip 打包时遗漏）===')
    for p, t in preexisting:
        print('   %s  %s' % (t, p))
    print()
    print('=== B. 本轮真正新增 ===')
    for p, t in newly:
        print('   %s  %s' % (t, p))
    return 0


if __name__ == '__main__':
    sys.exit(main())
