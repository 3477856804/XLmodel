# -*- coding: utf-8 -*-
"""统一 API 接入配置（OpenAI 兼容端点）
====================================

背景（为什么要单独建这个模块）：
仓库里原本有**两套**互不相通的 API 配置：

  1. ``config.training.api_*``  —— 训练页的「API 接入设置」写这里；
  2. ``config.deepseek_api_key`` / ``deepseek_base_url`` / ``teacher_model``
     —— 蒸馏（growth）老师端读这里，键名还写死成 deepseek。

用户在设置里配了端点，蒸馏那边却读另一套键，于是「配了等于没配」。
本模块把「外部大模型 API」收敛成**一份**配置（``config.api.*``），
供三处共同消费：

  * 蒸馏老师端（growth）；
  * 训练页的 API 模式（trainer）；
  * Agent「用 API 操作应用」—— 通过 :func:`chat` 真实调用外部模型。

红线：
  * 只用标准库（urllib），不引入 requests / openai 等第三方依赖；
  * key 永远打码回显，绝不把明文写进任何返回体或日志；
  * 没配 / 连不上时如实报错，绝不伪造 ok=True。

配置结构（config.api）::

    {
      "enabled": bool,        # 总开关：关掉后所有走外部 API 的路径自动降级
      "base":    str,         # 端点，如 https://api.deepseek.com/v1
      "key":     str,         # 密钥（明文只存本地配置，回显一律打码）
      "model":   str,         # 默认模型名
      "provider": str,        # 仅用于展示/占位提示，不影响调用协议
    }
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

# 允许用户覆盖的默认端点（本地 LM Studio / Ollama-openai 常见端口）。
_DEFAULT_BASE = "http://127.0.0.1:1234/v1"

# provider 只是给前端下拉用的展示项，调用协议统一是 OpenAI 兼容的
# /chat/completions，所以这里不写死任何厂商专属逻辑。
PROVIDERS = (
    "openai",        # 任意 OpenAI 兼容端点（含本地 LM Studio / Ollama / vLLM）
    "deepseek",
    "dashscope",     # 阿里通义（OpenAI 兼容模式）
    "moonshot",
    "zhipu",
    "custom",
)


def _mask_key(key: str) -> str:
    """API key 打码：保留前 4 后 4，中间 ****。空值返回空串。"""
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def _load_api() -> dict:
    try:
        try:
            from .config import load as _load
        except Exception:                                        # noqa: BLE001
            from config import load as _load                     # type: ignore
        cfg = _load() or {}
        a = cfg.get("api")
        return a if isinstance(a, dict) else {}
    except Exception:                                            # noqa: BLE001
        return {}


def cfg() -> dict:
    """读取统一 API 配置（key 打码）。永远返回一个结构完整的 dict。"""
    a = _load_api()
    key = str(a.get("key", "") or "").strip()
    base = str(a.get("base", "") or "").strip()
    return {
        "ok": True,
        "enabled": bool(a.get("enabled", False)),
        "base": base or _DEFAULT_BASE,
        "has_base": bool(base),
        "key_masked": _mask_key(key),
        "has_key": bool(key),
        "model": str(a.get("model", "") or "").strip(),
        "provider": str(a.get("provider", "") or "").strip() or "openai",
        "providers": list(PROVIDERS),
        "configured": bool(base and key),
        "source": "config" if a else "default",
    }


def set_field(field: str, value: str) -> dict:
    """写单个字段。field ∈ enabled|base|key|model|provider。

    写 base 校验 http/https；写 key 允许空串=清除；provider 限定在白名单内。
    返回写入后的打码快照。
    """
    field = (field or "").strip().lower()
    if field not in ("enabled", "base", "key", "model", "provider"):
        return {"ok": False,
                "error": f"未知设置项：{field}"
                         "（可用：enabled/base/key/model/provider）"}
    try:
        try:
            from .config import set_value as _set
        except Exception:                                        # noqa: BLE001
            from config import set_value as _set                 # type: ignore
        if field == "enabled":
            v = str(value or "").strip().lower()
            if v not in ("on", "off", "true", "false", "1", "0", "开", "关"):
                return {"ok": False,
                        "error": "enabled 只接受 on/off（或 true/false/1/0/开/关）"}
            _set("api.enabled", v in ("on", "true", "1", "开"))
        elif field == "base":
            base = (value or "").strip().rstrip("/")
            if base and not base.startswith(("http://", "https://")):
                return {"ok": False, "error": "base 必须以 http:// 或 https:// 开头"}
            _set("api.base", base)
        elif field == "key":
            _set("api.key", (value or "").strip())
        elif field == "provider":
            p = (value or "").strip().lower()
            if p and p not in PROVIDERS:
                return {"ok": False,
                        "error": f"未知 provider：{p}（可用：{', '.join(PROVIDERS)}）"}
            _set("api.provider", p)
        else:  # model
            _set("api.model", (value or "").strip())
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "error": f"配置写入失败：{type(e).__name__}: {e}"}
    snap = cfg()
    snap["written"] = field
    return snap


def _resolve_key_model() -> tuple[str | None, str | None]:
    a = _load_api()
    key = str(a.get("key", "") or "").strip() or None
    model = str(a.get("model", "") or "").strip() or None
    return key, model


def chat(messages, *, model: str | None = None, temperature: float = 0.7,
         max_tokens: int = 1024, timeout: float = 60.0) -> dict:
    """真实调用外部 OpenAI 兼容 /chat/completions。

    这是「用 API 操作应用」的底座：Agent 在没有本地模型、或用户显式选择
    「走外部 API」时，用这里把对话/工具决策交给外部模型。

    返回 ``{ok, text, model, elapsed_ms, error?}``。任何一环失败都如实带
    error，绝不伪造成功。未启用（api.enabled=false）时直接回 ok=False，
    让调用方降级到本地引擎 —— 这是「降级要明说」的落点。
    """
    c = cfg()
    if not c["enabled"]:
        return {"ok": False, "error": "外部 API 未启用（设置 → API 配置 打开开关）",
                "disabled": True}
    base = str(c.get("base") or "")
    if not base:
        return {"ok": False, "error": "未配置 api_base"}
    key, cfg_model = _resolve_key_model()
    url = f"{base.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": model or cfg_model or "default",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    t0 = time.time()
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:500]
        except Exception:                                        # noqa: BLE001
            pass
        return {"ok": False, "url": url,
                "error": f"HTTP {e.code}：{body or e.reason}"}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "url": url,
                "error": f"请求失败：{type(e).__name__}: {e}"}
    elapsed = int((time.time() - t0) * 1000)
    if status >= 400:
        return {"ok": False, "url": url, "error": f"HTTP {status}：{raw[:500]}"}
    try:
        data = json.loads(raw)
        text = data["choices"][0]["message"]["content"]
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "url": url, "elapsed_ms": elapsed,
                "error": f"响应不是预期 JSON：{type(e).__name__}: {e}",
                "raw": raw[:500]}
    return {"ok": True, "text": (text or "").strip(),
            "model": data.get("model") or payload["model"],
            "elapsed_ms": elapsed}


def test(timeout: float = 12.0) -> dict:
    """对配置的端点发一次真实最小请求验证连通性。结果如实返回。"""
    c = cfg()
    base = str(c.get("base") or "")
    if not base:
        return {"ok": False, "error": "未配置 api_base"}
    key, model = _resolve_key_model()
    url = f"{base.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {"model": model or "default",
               "messages": [{"role": "user", "content": "ping"}],
               "max_tokens": 1, "temperature": 0}
    t0 = time.time()
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            text = resp.read().decode("utf-8", "replace")[:300]
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:                                        # noqa: BLE001
            pass
        return {"ok": False, "url": url, "http_status": e.code,
                "error": f"HTTP {e.code}：{body or e.reason}"}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "url": url,
                "error": f"请求失败：{type(e).__name__}: {e}"}
    return {"ok": True, "url": url, "http_status": status,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "note": "端点可达且鉴权通过（返回体已截断）",
            "preview": text}


def transcribe(audio_bytes: bytes, *, filename: str = "audio.wav",
               model: str | None = None, language: str | None = None,
               timeout: float = 60.0) -> dict:
    """走外部 OpenAI 兼容 /audio/transcriptions 做语音识别（stdlib multipart）。

    存在的意义：用户机器上没装 whisper 时，只要配了外部 API，语音输入照样能用
    —— 把「语音识别未配置」从死路变成「去 API 配置填个 key」。
    未启用外部 API 时如实回 ok=False，由调用方降级到本地 whisper，绝不伪造。
    """
    c = cfg()
    if not c["enabled"]:
        return {"ok": False, "error": "外部 API 未启用", "disabled": True}
    base = str(c.get("base") or "")
    if not base:
        return {"ok": False, "error": "未配置 api_base"}
    if not audio_bytes:
        return {"ok": False, "error": "音频数据为空"}
    key, cfg_model = _resolve_key_model()
    url = f"{base.rstrip('/')}/audio/transcriptions"
    boundary = "----xlaudio%s" % int(time.time() * 1000)
    parts: list[bytes] = []

    def _field(name: str, value: str):
        parts.append(("--%s\r\n" % boundary).encode())
        parts.append(('Content-Disposition: form-data; name="%s"\r\n\r\n'
                      % name).encode())
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    if model or cfg_model:
        _field("model", model or cfg_model or "whisper-1")
    if language:
        _field("language", language)
    parts.append(("--%s\r\n" % boundary).encode())
    parts.append(('Content-Disposition: form-data; name="file"; filename="%s"\r\n'
                  % filename).encode())
    parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
    parts.append(audio_bytes)
    parts.append(b"\r\n")
    parts.append(("--%s--\r\n" % boundary).encode())
    body = b"".join(parts)

    headers = {"Content-Type": "multipart/form-data; boundary=%s" % boundary}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    t0 = time.time()
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        err = ""
        try:
            err = e.read().decode("utf-8", "replace")[:300]
        except Exception:                                        # noqa: BLE001
            pass
        return {"ok": False, "url": url, "http_status": e.code,
                "error": f"HTTP {e.code}：{err or e.reason}"}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "url": url,
                "error": f"请求失败：{type(e).__name__}: {e}"}
    elapsed = int((time.time() - t0) * 1000)
    if status >= 400:
        return {"ok": False, "url": url, "error": f"HTTP {status}：{raw[:300]}"}
    try:
        data = json.loads(raw)
        text = str(data.get("text") or "").strip()
    except Exception:                                            # noqa: BLE001
        text = raw.strip()
    if not text:
        return {"ok": False, "url": url, "elapsed_ms": elapsed,
                "error": "端点返回空识别结果"}
    return {"ok": True, "text": text, "elapsed_ms": elapsed}
