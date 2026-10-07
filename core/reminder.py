#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 定时提醒 / 专注计时
=============================

迁移自小玥的「30分钟后提醒我喝水」「专注模式结束提醒」。
自然语言识别 + 后台线程调度 + 到点回调（气泡 / 语音 / 系统通知）。
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from core.paths import STAR_DIR

BASE_DIR = STAR_DIR.parent
STORE = STAR_DIR / 'reminders.json'

_CN_NUM = {'一': 1, '两': 2, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8,
           '九': 9, '十': 10, '半': 0.5, '半小时': 0.5, '一小时': 1, '一刻': 0.25}


def parse_when(text: str):
    """从自然语言里解析延迟秒数与被提醒事项。"""
    t = (text or '').strip()
    m = re.search(r'(\d+(?:\.\d+)?)\s*(秒|分钟|分|小时|时|天)', t)
    seconds = None
    if m:
        v = float(m.group(1))
        unit = m.group(2)
        seconds = v * {'秒': 1, '分钟': 60, '分': 60, '小时': 3600, '时': 3600, '天': 86400}[unit]
    else:
        for k, v in _CN_NUM.items():
            if k in t and ('分' in t or '小时' in t or '时' in t):
                seconds = v * (3600 if ('小时' in t or '时' in t) else 60)
                break
    what = re.sub(r'(提醒我|提醒|叫我|一会|待会|\d+(?:\.\d+)?\s*(秒|分钟|分|小时|时|天)(后|以后)?)', '', t).strip(' ，,。.!！')
    return seconds, (what or '该休息一下啦')


def add(text: str, seconds: float = None, notify=None, save=True):
    if seconds is None:
        seconds, _ = parse_when(text)
    if not seconds:
        return None
    when = time.time() + float(seconds)
    item = {'id': f'rm{int(when * 1000)}', 'text': text, 'seconds': float(seconds),
            'fire_at': when, 'at': datetime.fromtimestamp(when).strftime('%m-%d %H:%M:%S'),
            'done': False}
    data = _load()
    data.append(item)
    if save:
        _save(data)
    threading.Thread(target=_wait_fire, args=(item, notify), daemon=True).start()
    return item


def _wait_fire(item, notify):
    delta = max(item['fire_at'] - time.time(), 0)
    time.sleep(delta)
    msg = item['text']
    try:
        if notify:
            notify(msg)
        else:
            _default_notify(msg)
    finally:
        data = _load()
        for d in data:
            if d['id'] == item['id']:
                d['done'] = True
        _save(data)


def _default_notify(msg):
    print(f'\n[提醒] 小凌提醒你：{msg}\n')
    try:
        import platform
        if platform.system() == 'Windows':
            from win10toast import ToastNotifier
            ToastNotifier().show_toast('小凌提醒', msg, duration=8)
        elif platform.system() == 'Darwin':
            import subprocess
            subprocess.run(['osascript', '-e', f'display notification "{msg}" with title "小凌提醒"'])
        elif shutil_which('notify-send'):
            import subprocess
            subprocess.run(['notify-send', '小凌提醒', msg])
    except Exception:                                                 # noqa: BLE001
        pass


def shutil_which(x):
    import shutil
    return shutil.which(x)


def _load():
    if STORE.exists():
        try:
            return json.loads(STORE.read_text(encoding='utf-8'))
        except Exception:                                             # noqa: BLE001
            return []
    return []


def _save(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def pending():
    return [d for d in _load() if not d.get('done')]


def focus_timer(minutes: float, notify=None):
    """专注计时：到点提醒休息。"""
    return add(f'{minutes} 分钟专注结束，休息一下', minutes * 60, notify=notify)


if __name__ == '__main__':
    import sys
    txt = ' '.join(sys.argv[1:]) or '10秒后提醒我喝水'
    item = add(txt, notify=lambda m: print('[提醒]', m))
    print('已设置：', item)
    time.sleep((item or {}).get('seconds', 0) + 1)
