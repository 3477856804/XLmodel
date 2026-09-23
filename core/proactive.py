#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 主动搭话
=================

迁移并整合小玥的「闲置主动搭话」：结合
    ① 时间（早/午/晚/深夜）  ② 电脑状态（你在写代码/看视频/摸鱼）
    ③ 长期记忆（RAG 检索最近聊过的事）  ④ 心情/情绪  ⑤ 可选热搜
生成一句自然的话；有本地模型或老师模型时用它润色，否则用模板。
"""
from __future__ import annotations

import random
import time
from datetime import datetime


class ProactiveEngine:
    def __init__(self, host=None, engine=None, rag=None):
        self.host = host
        self.engine = engine or getattr(host, 'engine', None)
        self.rag = rag or _default_rag()

    # ------------------------------------------------------------- 素材
    def _time_slot(self):
        h = datetime.now().hour
        if h < 6:
            return '深夜'
        if h < 11:
            return '早上'
        if h < 14:
            return '中午'
        if h < 18:
            return '下午'
        if h < 23:
            return '晚上'
        return '深夜'

    def _activity(self):
        try:
            from core import perception
            s = perception.snapshot()
            return s.get('activity') or ''
        except Exception:                                             # noqa: BLE001
            return ''

    def _memory_hint(self):
        if not self.rag:
            return ''
        try:
            hits = self.rag.search(f'{self._time_slot()} 主人 最近 聊 心情', k=1)
            if hits:
                return hits[0]['text'][:60]
        except Exception:                                             # noqa: BLE001
            pass
        return ''

    def _news_hint(self):
        try:
            from core import search
            rs = search.search_web('今日热点 新闻', n=1)
            if rs:
                return rs[0]['title'][:50]
        except Exception:                                             # noqa: BLE001
            pass
        return ''

    # ------------------------------------------------------------- 生成
    def compose(self) -> str:
        slot = self._time_slot()
        act = self._activity()
        mem = self._memory_hint()
        news = self._news_hint()
        pool = []
        if act == '写代码':
            pool += ['还在敲代码呀？记得起来走走，肩膀会僵的',
                     '这段是不是又调了半天？先喝口水再战',
                     '我看你写了挺久了，要不要我给你念两句鼓励的话']
        elif act == '看视频':
            pool += ['看得入神啦？记得眨眨眼', '这个好不好看呀，回头也讲给我听']
        elif act == '游戏':
            pool += ['打得顺手吗？别气到手抖哦', '赢了记得跟我炫耀一下']
        elif act in ('办公文档', '学习'):
            pool += ['专心做事的你最好看了', '需要我帮你整理一下思路吗']
        if slot == '深夜':
            pool += ['夜深了，早点睡好不好', '这么晚还醒着，我陪你一会儿']
        elif slot == '早上':
            pool += ['早上好呀，今天想做点什么', '新的一天，我们从哪儿开始']
        elif slot == '中午':
            pool += ['中午啦，别忘了吃饭', '要不要我帮你安排下午的节奏']
        elif slot == '晚上':
            pool += ['晚上好～今天过得怎么样', '忙完啦？我给你放首歌放松一下']
        if mem:
            pool.append(f'上次你提到「{mem}」，后来怎么样啦？')
        if news:
            pool.append(f'刚看到「{news}」，要听听吗？')
        pool += ['我在这儿，随时找我', '在忙吗？我悄悄陪着你']
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
                except Exception:                                     # noqa: BLE001
                    return line
        return line


def _default_rag():
    try:
        from core.rag import get_rag
        return get_rag()
    except Exception:                                                 # noqa: BLE001
        return None


if __name__ == '__main__':
    print(ProactiveEngine().compose())
