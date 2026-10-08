# -*- coding: utf-8 -*-
"""calendar_helper 插件

日历助手，全部基于 Python 标准库 datetime 真实计算（不联网、不硬编码）。

工具：
  - today()                         返回今天的日期 / 星期 / 当年第几天
  - weekday(date="YYYY-MM-DD")      返回某日期是星期几
  - countdown(target_date)          距目标日期还有多少天（负数表示已过去）
  - diff_dates(date1, date2)        两个日期相差多少天（绝对值）

日期统一用 YYYY-MM-DD 解析；格式错误时返回明确错误。
"""
from __future__ import annotations

from datetime import date, datetime

try:
    from core.plugin_system import PluginBase
except ImportError:
    from backend.core.plugin_system import PluginBase


_WEEKDAY_ZH = ["星期一", "星期二", "星期三", "星期四",
               "星期五", "星期六", "星期日"]


def _parse_date(s: str) -> date:
    """解析 YYYY-MM-DD；失败抛 ValueError。"""
    s = (s or "").strip()
    return datetime.strptime(s, "%Y-%m-%d").date()


class CalendarHelperPlugin(PluginBase):
    name = "calendar_helper"
    version = "0.0.1"
    description = "日历助手：今天/星期/倒计时/日期差，基于 Python datetime 真实计算"
    author = "xiaoling"
    category = "productivity"
    permissions = []

    def init(self):
        self._tools = [
            {
                "name": "today",
                "description": "返回今天的日期、星期、当年第几天",
                "args_schema": {},
                "handler": self.today,
            },
            {
                "name": "weekday",
                "description": "返回 date(YYYY-MM-DD) 是星期几",
                "args_schema": {"date": "string"},
                "handler": self.weekday,
            },
            {
                "name": "countdown",
                "description": "返回今天距 target_date(YYYY-MM-DD) 还有多少天",
                "args_schema": {"target_date": "string"},
                "handler": self.countdown,
            },
            {
                "name": "diff_dates",
                "description": "返回 date1 与 date2(YYYY-MM-DD) 相差多少天（绝对值）",
                "args_schema": {"date1": "string", "date2": "string"},
                "handler": self.diff_dates,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    def today(self) -> dict:
        try:
            t = date.today()
            return {
                "ok": True,
                "date": t.strftime("%Y-%m-%d"),
                "weekday": _WEEKDAY_ZH[t.weekday()],
                "weekday_index": t.weekday(),  # 周一=0
                "day_of_year": t.timetuple().tm_yday,
            }
        except Exception as e:
            return {"ok": False,
                    "error": "today 失败: {}: {}".format(type(e).__name__, e)}

    def weekday(self, date: str = "") -> dict:
        try:
            try:
                d = _parse_date(date)
            except Exception:
                return {"ok": False,
                        "error": "日期格式应为 YYYY-MM-DD，收到: {!r}".format(date)}
            return {
                "ok": True,
                "date": d.strftime("%Y-%m-%d"),
                "weekday": _WEEKDAY_ZH[d.weekday()],
                "weekday_index": d.weekday(),
                "is_weekend": d.weekday() >= 5,
            }
        except Exception as e:
            return {"ok": False,
                    "error": "weekday 失败: {}: {}".format(type(e).__name__, e)}

    def countdown(self, target_date: str = "") -> dict:
        try:
            try:
                target = _parse_date(target_date)
            except Exception:
                return {"ok": False,
                        "error": "target_date 格式应为 YYYY-MM-DD，收到: {!r}".format(target_date)}
            today = date.today()
            delta = (target - today).days
            if delta > 0:
                msg = "距离 {} 还有 {} 天".format(target.strftime("%Y-%m-%d"), delta)
            elif delta == 0:
                msg = "今天就是 {}！".format(target.strftime("%Y-%m-%d"))
            else:
                msg = "{} 已过去 {} 天".format(target.strftime("%Y-%m-%d"), -delta)
            return {
                "ok": True,
                "target_date": target.strftime("%Y-%m-%d"),
                "today": today.strftime("%Y-%m-%d"),
                "days_left": delta,
                "message": msg,
            }
        except Exception as e:
            return {"ok": False,
                    "error": "countdown 失败: {}: {}".format(type(e).__name__, e)}

    def diff_dates(self, date1: str = "", date2: str = "") -> dict:
        try:
            try:
                d1 = _parse_date(date1)
                d2 = _parse_date(date2)
            except Exception:
                return {"ok": False,
                        "error": "两个日期都应为 YYYY-MM-DD，收到: {!r} / {!r}".format(
                            date1, date2)}
            delta = (d2 - d1).days
            return {
                "ok": True,
                "date1": d1.strftime("%Y-%m-%d"),
                "date2": d2.strftime("%Y-%m-%d"),
                "days": abs(delta),
                "signed_days": delta,  # d2 比 d1 晚为正
            }
        except Exception as e:
            return {"ok": False,
                    "error": "diff_dates 失败: {}: {}".format(type(e).__name__, e)}
