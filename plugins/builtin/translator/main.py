# -*- coding: utf-8 -*-
"""translator 插件

文本翻译（优先中英互译，亦可任意语言对）。
真实调用免费的 MyMemory 翻译 API（https://api.mymemory.translated.net），
不硬编码任何翻译结果；网络失败 / API 报错时返回明确错误。

工具：
  - translate(text, source_lang="auto", target_lang="en")

语言代码使用 ISO 639-1，例如 zh-CN / en。source_lang 传 "auto" 时由调用方
根据 target_lang 推断（MyMemory 不支持真正的自动检测，这里做中英互译的便利推断）。
"""
from __future__ import annotations

import json
from urllib import parse, request

try:
    from core.plugin_system import PluginBase
except ImportError:
    from backend.core.plugin_system import PluginBase


_API = "https://api.mymemory.translated.net/get"
_TIMEOUT = 10  # 秒，外部 API 超时硬约束


def _norm_lang(lang: str) -> str:
    """把常见写法规整为 MyMemory 接受的 langpair 代码。"""
    l = (lang or "").strip().lower()
    # 中文统一为 zh-CN
    if l in ("zh", "cn", "chinese", "中文", "zh-cn"):
        return "zh-CN"
    if l in ("en", "english", "英语"):
        return "en"
    if len(l) >= 2:
        return l[:2]
    return l


class TranslatorPlugin(PluginBase):
    name = "translator"
    version = "0.0.1"
    description = "文本翻译：真实调用免费翻译 API，支持中英互译及任意语言对"
    author = "xiaoling"
    category = "tool"
    permissions = ["network"]

    def init(self):
        self._tools = [
            {
                "name": "translate",
                "description": "把 text 从 source_lang 翻译到 target_lang（ISO 639-1，如 zh-CN/en）",
                "args_schema": {
                    "text": "string",
                    "source_lang": "string?",
                    "target_lang": "string?",
                },
                "handler": self.translate,
            },
        ]

    def setup(self):
        self.init()

    def register_tools(self):
        if not hasattr(self, "_tools"):
            self.init()
        return self._tools

    def translate(self, text: str = "",
                  source_lang: str = "auto", target_lang: str = "en") -> dict:
        try:
            if not text or not str(text).strip():
                return {"ok": False, "error": "缺少参数 text"}
            text = str(text)

            src = _norm_lang(source_lang) if source_lang and source_lang != "auto" else ""
            tgt = _norm_lang(target_lang) if target_lang else "en"
            if not src:
                # MyMemory 不支持自动检测：根据内容是否含 CJK 字符做便利推断
                has_cjk = any("一" <= ch <= "鿿" for ch in text)
                src = "zh-CN" if has_cjk else "en"

            langpair = "{}|{}".format(src, tgt)
            qs = parse.urlencode({"q": text, "langpair": langpair})
            url = "{}?{}".format(_API, qs)

            req = request.Request(url, headers={"User-Agent": "xiaoling-translator/1.0"})
            try:
                with request.urlopen(req, timeout=_TIMEOUT) as resp:
                    raw = resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                return {"ok": False,
                        "error": "翻译 API 请求失败（网络/超时）: {}: {}".format(
                            type(e).__name__, e)}

            try:
                data = json.loads(raw)
            except Exception as e:
                return {"ok": False,
                        "error": "翻译 API 返回无法解析: {}".format(e)}

            rdata = data.get("responseData") or {}
            translated = (rdata.get("translatedText") or "").strip()
            status = data.get("responseStatus", 0)

            # MyMemory 错误时 translatedText 常是错误信息串
            if isinstance(status, int) and status >= 400:
                return {"ok": False,
                        "error": "翻译 API 返回错误 status={}: {}".format(
                            status, translated or data.get("responseDetails", ""))}
            if not translated:
                return {"ok": False,
                        "error": "翻译 API 未返回译文（可能超出免费配额或语言不支持）"}

            return {
                "ok": True,
                "source_lang": src,
                "target_lang": tgt,
                "input": text,
                "translated": translated,
                "service": "MyMemory",
            }
        except Exception as e:
            return {"ok": False,
                    "error": "translate 失败: {}: {}".format(type(e).__name__, e)}
