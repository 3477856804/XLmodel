#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 桌宠独立入口（3D / 2D / 命令行 三级降级）

    python pet.py                 # auto：能开 3D 就 3D，否则 2D，最后命令行
    python pet.py --mode 3d       # 只开 3D 数字人（透明置顶窗）
    python pet.py --mode 2d       # 2D 桌宠（Tkinter 程序化绘制，不依赖任何视频素材）
    python pet.py --mode console  # 纯命令行

设计说明：为了让桌宠在"没有任何视频素材、没有 GPU、没有 Qt"的机器上也能跑起来，
2D 模式**不读取 assets/animations 下的 WEBM**，而是用 Tkinter 画布程序化绘制小凌
（呼吸浮动 + 眨眼 + 心情色），因此不存在"素材缺失就黑屏"的问题。
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

GREETING = '你好呀，我是小凌～双击我可以说说话'
PALETTE = {'skin': '#f6e3d8', 'hair': '#d9c48d', 'dress': '#f2f4f8', 'eye': '#4a7fb5'}


def mode_3d() -> bool:
    """启动 3D 数字人窗口；成功返回 True。"""
    try:
        from core.avatar import AvatarHost
    except Exception as e:                                            # noqa: BLE001
        print(f'  [2D/3D] 3D 宿主不可用：{type(e).__name__}: {e}')
        return False
    try:
        host = AvatarHost()
        if host is None:
            return False
        host.start()
        return True
    except Exception as e:                                            # noqa: BLE001
        print(f'  [2D/3D] 3D 启动失败，准备降级：{type(e).__name__}: {e}')
        return False


def mode_2d() -> bool:
    """2D 桌宠：Tkinter 程序化绘制（无素材依赖）。"""
    try:
        import tkinter as tk
    except Exception as e:                                            # noqa: BLE001
        print(f'  [2D] 缺少 tkinter（{type(e).__name__}），降级到命令行；'
              f'Debian/Ubuntu 可 sudo apt install python3-tk')
        return False
    try:
        root = tk.Tk()
    except Exception as e:                                            # noqa: BLE001
        print(f'  [2D] 无图形环境（{type(e).__name__}），降级到命令行')
        return False
    root.title('小凌')
    root.overrideredirect(True)
    try:
        root.attributes('-topmost', True)
        root.attributes('-alpha', 0.94)
    except Exception:                                                 # noqa: BLE001
        pass
    W, H = 220, 260
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f'{W}x{H}+{sw - W - 40}+{sh - H - 80}')
    canvas = tk.Canvas(root, width=W, height=H, highlightthickness=0, bg='#20242c')
    canvas.pack()

    state = {'t': 0, 'x': W // 2, 'happy': False}

    def draw_face(cx, cy, r):
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=PALETTE['skin'], outline='')
        canvas.create_arc(cx - r - 6, cy - r - 10, cx + r + 6, cy + r - 20,
                          start=0, extent=180, fill=PALETTE['hair'], outline='')
        blink = state['t'] % 180 < 6
        for dx in (-r * 0.38, r * 0.38):
            if blink:
                canvas.create_line(cx + dx - 6, cy - 2, cx + dx + 6, cy - 2,
                                   fill=PALETTE['eye'], width=2)
            else:
                canvas.create_oval(cx + dx - 5, cy - 7, cx + dx + 5, cy + 3,
                                   fill=PALETTE['eye'], outline='')
        if state['happy']:
            canvas.create_arc(cx - 12, cy + 12, cx + 12, cy + 30, start=200, extent=140,
                              style='arc', width=2, outline='#c96a6a')
        else:
            canvas.create_arc(cx - 8, cy + 16, cx + 8, cy + 26, start=200, extent=140,
                              style='arc', width=2, outline='#c96a6a')

    def render():
        canvas.delete('all')
        bob = math.sin(state['t'] / 22.0) * 4
        cy = 118 + bob
        # 身体
        canvas.create_polygon(state['x'] - 52, cy + 190, state['x'] + 52, cy + 190,
                              state['x'] + 26, cy + 52, state['x'] - 26, cy + 52,
                              fill=PALETTE['dress'], outline='')
        # 头发 / 脸
        canvas.create_oval(state['x'] - 62, cy + 6, state['x'] + 62, cy + 96,
                           fill=PALETTE['hair'], outline='')
        draw_face(state['x'], cy + 46, 42)
        canvas.create_text(state['x'], 20, text=GREETING[:14], fill='#cfd6e4',
                           font=('sans', 9))
        state['t'] += 1
        root.after(50, render)

    def on_drag(e):
        root.geometry(f'+{e.x_root - W // 2}+{e.y_root - H // 2}')

    def on_talk(_e=None):
        state['happy'] = not state['happy']
        print('  [2D] 双击：' + ('开心表情' if state['happy'] else '恢复平静'))
        try:
            from core.growth import GrowthEngine
            print(GrowthEngine(log=lambda *a: None).report())
        except Exception:                                             # noqa: BLE001
            pass

    canvas.bind('<B1-Motion>', on_drag)
    canvas.bind('<Double-Button-1>', on_talk)
    canvas.bind('<Button-3>', lambda e: root.destroy())
    render()
    print('  [2D] 桌宠已启动：拖动=移动，双击=开心/成长报告，右键=关闭')
    root.mainloop()
    return True


def mode_console() -> None:
    from core.growth import GrowthEngine
    eng = GrowthEngine(log=lambda *a: None)
    print('小凌 · 命令行模式（输入 quit 退出）')
    print(eng.report())
    while True:
        try:
            text = input('你：').strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text in ('quit', 'exit', '退出'):
            break
        if not text:
            continue
        if any(k in text for k in ('成长', '进度')):
            print(eng.report())
        elif '样本' in text:
            print(eng.samples_report())
        else:
            print('小凌：我在呢～（命令行模式下请用 python xl.py 获得完整对话能力）')


def main(argv=None):
    ap = argparse.ArgumentParser(description='小凌桌宠')
    ap.add_argument('--mode', default='auto', choices=['auto', '3d', '2d', 'webm', 'console'])
    a = ap.parse_args(argv)
    mode = a.mode
    if mode == 'webm':
        mode = '2d'          # 保留旧参数名：2D 兜底已改为程序化绘制，不再依赖 WEBM
    if mode in ('auto', '3d'):
        if os.environ.get('XIAOLING_NO_AVATAR'):
            print('  [桌宠] 环境变量要求跳过 3D')
        elif mode_3d():
            return 0
        elif mode == '3d':
            print('  [桌宠] 3D 不可用')
            return 1
    if mode in ('auto', '2d'):
        if mode_2d():
            return 0
    mode_console()
    return 0


if __name__ == '__main__':
    sys.exit(main())
