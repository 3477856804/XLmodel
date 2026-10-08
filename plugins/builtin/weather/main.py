# -*- coding: utf-8 -*-
"""weather 插件

天气查询：真实调用 wttr.in 免费天气服务（返回 JSON），
不硬编码任何天气数据；网络失败 / 城市找不到时返回明确错误。

工具：
  - get_weather(city) -> 温度 / 天气描述 / 湿度 / 风速

数据源：https://wttr.in/<city>?format=j1 （当前实况在 current_condition[0]）。
外部请求硬超时 10 秒。
"""
from __future__ import annotations

import json
from urllib import parse, request

try:
    from core.plugin_system import PluginBase
except ImportError:
    from backend.core.plugin_system import PluginBase


_TIMEOUT = 10  # 秒


class WeatherPlugin(PluginBase):
    name = "weather"
    version = "0.0.1"
    description = "天气查询：真实调用免费天气服务，返回温度/天气/湿度/风速"
    author = "xiaoling"
    category = "tool"
    permissions = ["network"]

    def init(self):
        self._tools = [
            {
                "name": "get_weather",
                "description": "查询指定城市的当前天气（温度/天气/湿度/风速）",
                "args_schema": {"city": "string"},
                "handler": self.get_weather,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    def get_weather(self, city: str = "") -> dict:
        try:
            if not city or not str(city).strip():
                return {"ok": False, "error": "缺少参数 city"}
            city = str(city).strip()
            url = "https://wttr.in/{}?format=j1&lang=zh".format(
                parse.quote(city))

            req = request.Request(url, headers={
                "User-Agent": "curl/weather",  # wttr.in 对 curl UA 返回正常
                "Accept": "application/json",
            })
            try:
                with request.urlopen(req, timeout=_TIMEOUT) as resp:
                    raw = resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                return {"ok": False, "city": city,
                        "error": "天气服务请求失败（网络/超时，或城市无法识别）: {}: {}".format(
                            type(e).__name__, e)}

            try:
                data = json.loads(raw)
            except Exception:
                # wttr.in 找不到城市时返回一段 HTML 而非 JSON
                return {"ok": False, "city": city,
                        "error": "天气服务未返回有效数据（城市可能不存在或服务暂不可用）"}

            cur = (data.get("current_condition") or [])
            if not cur:
                return {"ok": False, "city": city,
                        "error": "未获取到该城市的天气实况，请检查城市名"}
            cur = cur[0]

            def _desc():
                descs = cur.get("lang_zh") or cur.get("weatherDesc") or []
                if descs and isinstance(descs, list):
                    return descs[0].get("value", "")
                return ""

            area = (data.get("nearest_area") or [{}])[0]
            area_name = ""
            try:
                area_name = (area.get("areaName") or [{}])[0].get("value", "")
            except Exception:
                area_name = ""

            result = {
                "ok": True,
                "city": area_name or city,
                "temperature_c": cur.get("temp_C"),
                "feels_like_c": cur.get("FeelsLikeC"),
                "weather": _desc(),
                "humidity": cur.get("humidity"),
                "wind_speed_kmh": cur.get("windspeedKmph"),
                "wind_dir": cur.get("winddir16Point"),
                "observation_time": cur.get("localObsDateTime"),
                "service": "wttr.in",
            }
            return result
        except Exception as e:
            return {"ok": False,
                    "error": "get_weather 失败: {}: {}".format(type(e).__name__, e)}
