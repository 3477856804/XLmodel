#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 电脑状态感知
=====================

迁移自小玥的「识别当前活动窗口，根据你在干什么来调侃」。
* Windows: ctypes GetForegroundWindow + GetWindowText
* Linux:   xdotool / wmctrl / xprop（X11）；Wayland 尽量降级
* macOS:   osascript（System Events）

`classify(title)` 把窗口标题归到「写代码 / 看视频 / 摸鱼 / 办公 / 游戏 / 听歌 …」，
供主动搭话使用。
"""
from __future__ import annotations

import platform
import re
import shutil
import subprocess

RULES = [
    ('写代码', r'(vscode|visual studio|pycharm|idea|sublime|neovim|vim|emacs|terminal|powershell|cmd|'
               r'iterm|warp|zed|android studio|xcode|jupyter|colab|github|cursor|termux)'),
    ('看视频', r'(youtube|bilibili|哔哩哔哩|netflix|爱奇艺|腾讯视频|优酷|potplayer|vlc|mpv|抖音)'),
    ('听歌', r'(spotify|网易云|qq音乐|music|foobar|酷狗)'),
    ('社交聊天', r'(wechat|微信|qq|telegram|discord|slack|飞书|lark|钉钉|whatsapp)'),
    ('游戏', r'(steam|epic|原神|genshin|minecraft|league|英雄联盟|lol|csgo|dota)'),
    ('办公文档', r'(word|excel|powerpoint|wps|notion|obsidian|onedrive|pdf|xmind|typora)'),
    ('浏览器摸鱼', r'(chrome|edge|firefox|safari|brave|opera|浏览器)'),
    ('学习', r'(anki|kindle|mooc|coursera|zhihu|知乎|wikipedia|词典)'),
]


def active_window_title():
    sysname = platform.system()
    try:
        if sysname == 'Windows':
            import ctypes
            u32 = ctypes.windll.user32
            hwnd = u32.GetForegroundWindow()
            n = u32.GetWindowTextLengthW(hwnd) + 1
            buf = ctypes.create_unicode_buffer(n)
            u32.GetWindowTextW(hwnd, buf, n)
            return buf.value or ''
        if sysname == 'Darwin':
            script = ('tell application "System Events" to get name of first application process '
                      'whose frontmost is true')
            return subprocess.run(['osascript', '-e', script], capture_output=True, text=True,
                                  timeout=5).stdout.strip()
        if shutil.which('xdotool'):
            return subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'],
                                  capture_output=True, text=True, timeout=5).stdout.strip()
        if shutil.which('xprop'):
            out = subprocess.run(['xprop', '-root', '_NET_ACTIVE_WINDOW'],
                                 capture_output=True, text=True, timeout=5).stdout
            wid = out.strip().split()[-1]
            if wid and wid != '0x0':
                out2 = subprocess.run(['xprop', '-id', wid, 'WM_NAME'],
                                      capture_output=True, text=True, timeout=5).stdout
                return re.sub(r'^.*=\s*"?(.*?)"?$', r'\1', out2.strip())
        if shutil.which('wmctrl'):
            out = subprocess.run(['wmctrl', '-lp'], capture_output=True, text=True, timeout=5).stdout
            lines = [l for l in out.splitlines() if l.strip()]
            if lines:
                return lines[-1]
    except Exception:                                                 # noqa: BLE001
        return ''
    return ''


def classify(title: str) -> str:
    t = (title or '').lower()
    for label, pat in RULES:
        if re.search(pat, t):
            return label
    return '随便逛逛' if t else '未知'


def snapshot() -> dict:
    title = active_window_title()
    return {'title': title, 'activity': classify(title), 'platform': platform.system()}


def describe() -> str:
    s = snapshot()
    if not s['title']:
        return '（读不到活动窗口：可能是 Wayland / 无桌面环境）'
    return f"你正在：{s['activity']}（窗口标题：{s['title'][:80]}）"


if __name__ == '__main__':
    print(describe())
