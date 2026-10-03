#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主动行为 - 定时提醒 + 专注计时 + 主动搭话"""
from __future__ import annotations

import json
import random
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from core.paths import STAR_DIR

# ============================================================
# 定时提醒
# ============================================================
STORE = STAR_DIR / 'reminders.json'

_CN_NUM = {'一': 1, '两': 2, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8,
           '九': 9, '十': 10, '半': 0.5, '半小时': 0.5, '一小时': 1, '一刻': 0.25}


def parse_when(text: str):
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


def add_reminder(text: str, seconds: float = None, notify=None, save=True):
    if seconds is None:
        seconds, _ = parse_when(text)
    if not seconds:
        return None
    when = time.time() + float(seconds)
    item = {'id': f'rm{int(when * 1000)}', 'text': text, 'seconds': float(seconds),
            'fire_at': when, 'at': datetime.fromtimestamp(when).strftime('%m-%d %H:%M:%S'),
            'done': False}
    data = _load_reminders()
    data.append(item)
    if save:
        _save_reminders(data)
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
        data = _load_reminders()
        for d in data:
            if d['id'] == item['id']:
                d['done'] = True
        _save_reminders(data)


def _default_notify(msg):
    print(f'\n[提醒] 小凌提醒你：{msg}\n')


def _load_reminders():
    if STORE.exists():
        try:
            return json.loads(STORE.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []


def _save_reminders(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def pending_reminders():
    return [d for d in _load_reminders() if not d.get('done')]


def focus_timer(minutes: float, notify=None):
    return add_reminder(f'{minutes} 分钟专注结束，休息一下', minutes * 60, notify=notify)


# ============================================================
# 主动搭话
# ============================================================
class ProactiveEngine:
    def __init__(self, host=None, engine=None, rag=None):
        self.host = host
        self.engine = engine or getattr(host, 'engine', None)
        self.rag = rag or _default_rag()

    def _time_slot(self):
        h = datetime.now().hour
        if h < 6: return '深夜'
        if h < 11: return '早上'
        if h < 14: return '中午'
        if h < 18: return '下午'
        if h < 23: return '晚上'
        return '深夜'

    def _activity(self):
        try:
            from core import perception
            s = perception.snapshot()
            return s.get('activity') or ''
        except Exception:
            return ''

    def _memory_hint(self):
        if not self.rag:
            return ''
        try:
            hits = self.rag.search(f'{self._time_slot()} 主人 最近 聊 心情', k=1)
            if hits:
                return hits[0]['text'][:60]
        except Exception:
            pass
        return ''

    def _news_hint(self):
        try:
            from core import search
            rs = search.search_web('今日热点 新闻', n=1)
            if rs:
                return rs[0]['title'][:50]
        except Exception:
            pass
        return ''

    def compose(self) -> str:
        slot = self._time_slot()
        act = self._activity()
        mem = self._memory_hint()
        news = self._news_hint()
        pool = []
        if act == '写代码':
            pool += ['还在敲代码呀？记得起来走走，肩膀会僵的',
                     '这段是不是又调了半天？先喝口水再战']
        elif act == '看视频':
            pool += ['看得入神啦？记得眨眨眼']
        elif act == '游戏':
            pool += ['打得顺手吗？别气到手抖哦']
        if slot == '深夜':
            pool += ['夜深了，早点睡好不好']
        elif slot == '早上':
            pool += ['早上好呀，今天想做点什么']
        elif slot == '中午':
            pool += ['中午啦，别忘了吃饭']
        elif slot == '晚上':
            pool += ['晚上好～今天过得怎么样']
        if mem:
            pool.append(f'上次你提到「{mem}」，后来怎么样啦？')
        pool += ['我在这儿，随时找我']
        line = random.choice(pool)
        return self._polish(line)

    def _polish(self, line: str) -> str:
        eng = self.engine
        if eng is None:
            return line
        for meth in ('quick_reply', 'chat', 'reply'):
            fn = getattr(eng, meth, None)
            if callable(fn):
                try:
                    out = fn(f'（请用一句自然、简短、口语化的话对主人说：{line}）')
                    if isinstance(out, str) and 0 < len(out) <= 80:
                        return out.strip()
                except Exception:
                    return line
        return line


def _default_rag():
    try:
        from core.rag import get_rag
        return get_rag()
    except Exception:
        return None


# 兼容旧导入
def add(text, seconds=None, notify=None, save=True):
    return add_reminder(text, seconds, notify, save)

def pending():
    return pending_reminders()


if __name__ == '__main__':
    print(ProactiveEngine().compose())
