#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.throttle —— DeepSeek 蒸馏节流（缓存 / 限流 / 开关 / 成本）
=================================================================

对应设计文档 3.4 节「DeepSeek 蒸馏节流」，四件事：

    缓存    hash(prompt) → teacher_response，相同问题不重复请求
    限流    每天最多 N 次 API 调用（用户可配）
    开关    用户可关闭 API 蒸馏，纯本地成长
    成本    仪表盘展示本月 API 调用次数与预估费用

另外实现文档 3.5 节隐私边界：默认只做本地缓存与统计，不外发任何数据。

说明（重要）：token 单价默认为**示例值**，仅用于本地费用估算，不代表任何官方报价；
请按你自己的实际资费在配置 `growth.teacher_price_in` / `teacher_price_out`
（单位：元/百万 token）中修改，估算结果不构成账单依据。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, date
from pathlib import Path

from core.paths import APP_DIR

DEFAULT_DAILY_LIMIT = 200
# 示例单价（元 / 百万 token）——非官方报价，仅本地估算用，用户可改
DEFAULT_PRICE_IN = 1.0
DEFAULT_PRICE_OUT = 2.0


def _today() -> str:
    return date.today().isoformat()


def _month() -> str:
    return datetime.now().strftime('%Y-%m')


def cache_key(prompt: str, model: str = '') -> str:
    norm = ' '.join((prompt or '').strip().split())
    return hashlib.sha256(f'{model}\x00{norm}'.encode('utf-8')).hexdigest()[:40]


class DistillThrottle:
    """蒸馏 API 的节流与成本控制器（纯本地，无网络依赖）。"""

    def __init__(self, root: Path | str | None = None, enabled: bool | None = None,
                 daily_limit: int | None = None, price_in: float | None = None,
                 price_out: float | None = None):
        self.app_dir = Path(root) if root else APP_DIR
        self.dir = self.app_dir / '.star_core' / 'growth'
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.dir / 'distill_cache.json'
        self.usage_path = self.dir / 'api_usage.json'
        cfg = self._load_cfg()
        self.enabled = bool(cfg.get('distill_enabled', True)) if enabled is None else bool(enabled)
        self.daily_limit = int(cfg.get('daily_limit', DEFAULT_DAILY_LIMIT)) \
            if daily_limit is None else int(daily_limit)
        self.price_in = float(cfg.get('price_in', DEFAULT_PRICE_IN)) if price_in is None else float(price_in)
        self.price_out = float(cfg.get('price_out', DEFAULT_PRICE_OUT)) if price_out is None else float(price_out)

    # ------------------------------------------------------------- 配置/读写
    def _load_cfg(self) -> dict:
        p = self.app_dir / '.star_core' / 'xiaoling_config.json'
        if not p.exists():
            return {}
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
            g = data.get('growth', {}) or {}
            return {'distill_enabled': g.get('distill_enabled', True),
                    'daily_limit': g.get('distill_daily_limit', DEFAULT_DAILY_LIMIT),
                    'price_in': g.get('teacher_price_in', DEFAULT_PRICE_IN),
                    'price_out': g.get('teacher_price_out', DEFAULT_PRICE_OUT)}
        except Exception:                                            # noqa: BLE001
            return {}

    def _read_json(self, p: Path, default):
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:                                            # noqa: BLE001
            return default

    def _write_json(self, p: Path, data):
        try:
            p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        except OSError:
            pass

    def _cache(self) -> dict:
        return self._read_json(self.cache_path, {})

    def _usage(self) -> dict:
        u = self._read_json(self.usage_path, {})
        u.setdefault('days', {})
        u.setdefault('months', {})
        u.setdefault('total', {'calls': 0, 'cache_hits': 0, 'tokens_in': 0, 'tokens_out': 0,
                               'blocked': 0})
        return u

    # ------------------------------------------------------------- 查询/判定
    def cached(self, prompt: str, model: str = '') -> str | None:
        return self._cache().get(cache_key(prompt, model))

    def used_today(self) -> int:
        return int(self._usage()['days'].get(_today(), {}).get('calls', 0))

    def remaining(self) -> int:
        if self.daily_limit <= 0:
            return 10 ** 9
        return max(self.daily_limit - self.used_today(), 0)

    def check(self, prompt: str, model: str = '') -> dict:
        """调用前判定：能否请求？命中缓存则不消耗配额。"""
        if not self.enabled:
            return {'ok': False, 'reason': 'disabled', 'message': '用户已关闭 API 蒸馏（纯本地成长）',
                    'cached': None}
        hit = self.cached(prompt, model)
        if hit is not None:
            self._bump('cache_hits')
            return {'ok': True, 'reason': 'cache', 'cached': hit, 'message': '命中缓存，未消耗配额'}
        if self.remaining() <= 0:
            self._bump('blocked')
            return {'ok': False, 'reason': 'quota', 'cached': None,
                    'message': f'今日配额已用完（{self.used_today()}/{self.daily_limit}）'}
        return {'ok': True, 'reason': 'live', 'cached': None,
                'message': f'可调用（今日 {self.used_today()}/{self.daily_limit}）'}

    # ------------------------------------------------------------- 记账
    def _bump(self, field: str, n: int = 1):
        u = self._usage()
        u['total'][field] = int(u['total'].get(field, 0)) + n
        self._write_json(self.usage_path, u)

    def record(self, prompt: str, response: str = '', model: str = '',
               tokens_in: int = 0, tokens_out: int = 0, from_cache: bool = False) -> dict:
        """调用结束后记账（真实调用与缓存命中分别统计）。"""
        u = self._usage()
        day = _today()
        mon = _month()
        d = u['days'].setdefault(day, {'calls': 0, 'cache_hits': 0, 'tokens_in': 0, 'tokens_out': 0})
        m = u['months'].setdefault(mon, {'calls': 0, 'cache_hits': 0, 'tokens_in': 0, 'tokens_out': 0})
        key = 'cache_hits' if from_cache else 'calls'
        for bucket in (d, m, u['total']):
            bucket[key] = int(bucket.get(key, 0)) + 1
            if not from_cache:
                bucket['tokens_in'] = int(bucket.get('tokens_in', 0)) + int(tokens_in)
                bucket['tokens_out'] = int(bucket.get('tokens_out', 0)) + int(tokens_out)
        if response and not from_cache:
            cache = self._cache()
            cache[cache_key(prompt, model)] = response
            # 缓存上限保护：只保留最近 5000 条
            if len(cache) > 5000:
                for k in list(cache.keys())[:len(cache) - 5000]:
                    cache.pop(k, None)
            self._write_json(self.cache_path, cache)
        self._write_json(self.usage_path, u)
        return self.cost()

    def set_enabled(self, on: bool) -> dict:
        self.enabled = bool(on)
        self._write_json(self.cache_path, self._cache())          # 保证目录存在
        return {'ok': True, 'enabled': self.enabled}

    def set_daily_limit(self, n: int) -> dict:
        self.daily_limit = int(n)
        return {'ok': True, 'daily_limit': self.daily_limit}

    # ------------------------------------------------------------- 成本
    def cost_of(self, tokens_in: int, tokens_out: int) -> float:
        return round(tokens_in / 1e6 * self.price_in + tokens_out / 1e6 * self.price_out, 6)

    def cost(self, scope: str = 'month') -> dict:
        """费用估算（元）。scope: today | month | total"""
        u = self._usage()
        if scope == 'today':
            b = u['days'].get(_today(), {})
        elif scope == 'total':
            b = u['total']
        else:
            b = u['months'].get(_month(), {})
        ti, to = int(b.get('tokens_in', 0)), int(b.get('tokens_out', 0))
        return {'scope': scope, 'calls': int(b.get('calls', 0)), 'cache_hits': int(b.get('cache_hits', 0)),
                'tokens_in': ti, 'tokens_out': to, 'cost_yuan': self.cost_of(ti, to),
                'price_in': self.price_in, 'price_out': self.price_out,
                'price_note': '示例单价，非官方报价；请在配置 growth.teacher_price_in/out 中改为你的实际资费'}

    def usage_report(self) -> dict:
        u = self._usage()
        m = u['months'].get(_month(), {})
        return {
            'enabled': self.enabled,
            'daily_limit': self.daily_limit,
            'used_today': self.used_today(),
            'remaining_today': self.remaining(),
            'cache_entries': len(self._cache()),
            'total': dict(u['total']),
            'today': self.cost('today'),
            'month': self.cost('month'),
            'all_time': self.cost('total'),
            'month_calls': int(m.get('calls', 0)),
            'month_cache_hits': int(m.get('cache_hits', 0)),
            'days_recorded': len(u['days']),
        }

    def reset_today(self) -> dict:
        u = self._usage()
        u['days'].pop(_today(), None)
        self._write_json(self.usage_path, u)
        return {'ok': True, 'message': '今日计数已清零'}

    def clear_cache(self) -> dict:
        n = len(self._cache())
        self._write_json(self.cache_path, {})
        return {'ok': True, 'cleared': n}


def main(argv=None):
    ap = argparse.ArgumentParser(description='DeepSeek 蒸馏节流器')
    ap.add_argument('cmd', choices=['status', 'check', 'clear-cache', 'reset-today',
                                    'enable', 'disable', 'set-limit'])
    ap.add_argument('--prompt', default='')
    ap.add_argument('--limit', type=int, default=DEFAULT_DAILY_LIMIT)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--root', default=str(APP_DIR))
    a = ap.parse_args(argv)
    t = DistillThrottle(a.root)
    if a.cmd == 'status':
        rep = t.usage_report()
        if a.json:
            print(json.dumps(rep, ensure_ascii=False, indent=1))
        else:
            print('小凌 · 蒸馏节流状态')
            print(f"  开关：{'开' if rep['enabled'] else '关'}   今日 {rep['used_today']}/{rep['daily_limit']}"
                  f"（剩余 {rep['remaining_today']}）")
            print(f"  缓存：{rep['cache_entries']} 条   本月调用 {rep['month_calls']} 次"
                  f"（命中缓存 {rep['month_cache_hits']} 次）")
            print(f"  本月预估费用：{rep['month']['cost_yuan']:.4f} 元"
                  f"（{rep['month']['tokens_in']}+{rep['month']['tokens_out']} tokens）")
            print(f"  注：{rep['month']['price_note']}")
    elif a.cmd == 'check':
        print(json.dumps(t.check(a.prompt), ensure_ascii=False, indent=1))
    elif a.cmd == 'clear-cache':
        print(json.dumps(t.clear_cache(), ensure_ascii=False))
    elif a.cmd == 'reset-today':
        print(json.dumps(t.reset_today(), ensure_ascii=False))
    elif a.cmd == 'enable':
        print(json.dumps(t.set_enabled(True), ensure_ascii=False))
    elif a.cmd == 'disable':
        print(json.dumps(t.set_enabled(False), ensure_ascii=False))
    elif a.cmd == 'set-limit':
        print(json.dumps(t.set_daily_limit(a.limit), ensure_ascii=False))


if __name__ == '__main__':
    main()
