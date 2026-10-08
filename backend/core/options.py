"""小凌 · 设置页「可选项」统一出口（跨平台）。

## 为什么要有这个模块

设置页原先有若干**写死**的常量列表。写死的坏处很实在：

=================  ==========================================================
写死的东西          问题
=================  ==========================================================
推理后端            复用了**渲染后端**的列表（软件光栅/OpenGL/Vulkan/Metal）。
                   推理跟光栅化是两件事；而且它和「渲染模式」共用同一个
                   state 变量，改一个另一个跟着动。
推理线程数          固定 2/4/6/8。桌面机给少了浪费，手机上给多了会过热降频。
界面语言            列了繁體中文/English/日本語，但实际只有简体中文被翻译过。
音色表              后端写死 30 个 edge-tts 音色，不管本机装没装 edge-tts；
                   而且性别字段没有随协议传给前端，前端只能靠"名字里有没有
                   xiao/yun"去猜 —— 于是 Aria、ナナミ、曉佳 全被显示成「中性」。
主题模式            选项写死，而且选中后只 setState，既不落盘也不真正换主题。
=================  ==========================================================

## 平台无关原则（重要）

本项目要上架官方网站，支持 **Windows / Linux / macOS / Android(Termux)** 四个
下载目标，所以这里**绝对不能按某一台开发机的现状去"砍掉"别平台的选项**：

- 不能因为本机是 Windows 就把 Metal 从列表里删掉 —— macOS 用户必须能看到它。
- 也不能因为本机有 28 线程就一律给到 28 档 —— 手机上会直接过热降频。

正确做法是**按平台生成**：先识别当前平台，再给出该平台真正可用的项，
并对装了依赖才可用的项（CUDA / MPS / llama.cpp / edge-tts）做真实探测，
不可用的标 `available=false` 由前端置灰并说明原因。

对应项目规范：`docs/codingGuidelines.md` §平台兼容 ——
「业务代码不能硬编码 Windows/Linux/macOS；用 platform 检测平台」。

## 命令

- ``settings:options``              返回全部可选项（JSON）
- ``settings:set <点分路径> <值>``  写入配置，例如 ``settings:set ui.theme dark``
"""
from __future__ import annotations

import json
import os
import sys
import time

from core import config as _cfg

# --------------------------------------------------------------------------
# 平台识别
# --------------------------------------------------------------------------
_WIN = "windows"
_MAC = "macos"
_LIN = "linux"
_AND = "android"

_PLATFORM_LABEL = {
    _WIN: "Windows",
    _MAC: "macOS",
    _LIN: "Linux",
    _AND: "Android",
}


def host_platform() -> str:
    """识别当前运行平台。

    Android 要**先判**：Termux / Chaquopy 里 `sys.platform` 同样是 `linux`，
    如果先走 system() 分支会把手机误判成桌面 Linux，进而给出 28 线程、
    Direct3D 这类完全不适用的选项。
    """
    try:
        if hasattr(sys, "getandroidapilevel"):
            return _AND
    except Exception:
        pass
    if os.environ.get("TERMUX_VERSION") or os.path.exists("/data/data/com.termux"):
        return _AND
    # Chaquopy 会往 environ 里注入 Python 的家目录
    if (os.environ.get("PYTHONHOME") or "").find("com.chaquo") >= 0:
        return _AND
    try:
        import platform as _plat
        s = (_plat.system() or "").strip().lower()
    except Exception:
        s = ""
    if not s:
        s = (sys.platform or "").lower()
    if s == "windows" or s.startswith("win"):
        return _WIN
    if s == "darwin" or s == "mac":
        return _MAC
    if s.startswith("linux"):
        return _LIN
    return s or "unknown"


def platform_label() -> str:
    return _PLATFORM_LABEL.get(host_platform(), host_platform())


def is_mobile_platform() -> bool:
    return host_platform() == _AND


# --------------------------------------------------------------------------
# 主题模式：Flutter ThemeMode 真实支持的三个值，全平台一致
# --------------------------------------------------------------------------
def _themes() -> list[dict]:
    return [
        {"value": "system", "label": "跟随系统",
         "desc": f"跟随{platform_label()}的浅色 / 深色设置"},
        {"value": "dark", "label": "始终深色", "desc": "深色为默认，夜间更护眼"},
        {"value": "light", "label": "始终浅色", "desc": "浅色更高对比、更明亮"},
    ]


# 界面语言：supported=False 的一律标注下来，前端会提示"尚未完成翻译"，
# 免得选了之后界面纹丝不动、以为是自己点错了。
_LANGUAGES = [
    {"value": "zh-CN", "label": "简体中文", "supported": True},
    {"value": "zh-TW", "label": "繁體中文", "supported": False},
    {"value": "en-US", "label": "English", "supported": False},
    {"value": "ja-JP", "label": "日本語", "supported": False},
]

# --------------------------------------------------------------------------
# 渲染模式：先给全平台通用的三档，再按平台追加该平台特有的图形 API
# --------------------------------------------------------------------------
_COMMON_RENDER = [
    {"value": "auto", "label": "自动", "desc": "按设备能力自动选择"},
    {"value": "software", "label": "软件光栅", "desc": "兼容性最好，最省电"},
    {"value": "gpu", "label": "GPU 加速", "desc": "更流畅，占用显存"},
]

# 每个平台真正存在的原生图形 API。**不要跨平台串味**：Metal 只在 Apple 平台，
# Direct3D 只在 Windows，OpenGL ES 只在移动 / 嵌入式。
_NATIVE_RENDER = {
    _WIN: [{"value": "d3d11", "label": "Direct3D 11", "desc": "Windows 原生图形接口"},
           {"value": "opengl", "label": "OpenGL", "desc": "跨平台遗留接口"},
           {"value": "vulkan", "label": "Vulkan", "desc": "低开销，需硬件支持"}],
    _MAC: [{"value": "metal", "label": "Metal", "desc": "Apple 平台原生图形接口"},
           {"value": "opengl", "label": "OpenGL", "desc": "macOS 已弃用，仅作兼容"}],
    _LIN: [{"value": "opengl", "label": "OpenGL", "desc": "桌面 Linux 主流接口"},
           {"value": "vulkan", "label": "Vulkan", "desc": "低开销，需硬件支持"}],
    _AND: [{"value": "gles", "label": "OpenGL ES", "desc": "Android 标准图形接口"},
           {"value": "vulkan", "label": "Vulkan", "desc": "需设备支持 Vulkan 1.1+"}],
}


def _render_modes() -> list[dict]:
    return _COMMON_RENDER + _NATIVE_RENDER.get(host_platform(), [])


# --------------------------------------------------------------------------
# 推理后端：跟"渲染"是两码事，且各平台加速方案完全不同
# --------------------------------------------------------------------------
def _torch():
    try:
        import torch  # noqa: PLC0415
        return torch
    except Exception:
        return None


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _cuda_state(torch_mod):
    """(可用?, 设备名)。硬件存在但 torch 是 CPU 版 → 可用=False 并如实说明。"""
    if torch_mod is None or not getattr(torch_mod, "cuda", None):
        return False, ""
    try:
        if torch_mod.cuda.is_available():
            try:
                return True, torch_mod.cuda.get_device_name(0)
            except Exception:
                return True, "CUDA GPU"
    except Exception:
        pass
    return False, ""


def _inference_backends() -> list[dict]:
    """按平台列出推理加速方案。

    每一项都标了 availability，理由也写清楚 —— 不能让老板看着一堆选项
    却不知道为什么点不了。
    """
    plat = host_platform()
    out: list[dict] = [
        {"value": "auto", "label": "自动（推荐）", "desc": "按本机能力自动挑选最快的一种"},
        {"value": "cpu", "label": "CPU", "desc": "全平台可用，兼容性最好，速度较慢"},
    ]
    torch_mod = _torch()
    cuda_ok, cuda_name = _cuda_state(torch_mod)

    # ---- NVIDIA CUDA：Windows / Linux（桌面及部分工作站）----
    if plat in (_WIN, _LIN):
        if cuda_ok:
            out.append({"value": "cuda", "label": f"CUDA / NVIDIA GPU（{cuda_name}）",
                        "desc": "当前 torch 已支持 CUDA"})
        else:
            out.append({"value": "cuda", "label": "CUDA / NVIDIA GPU", "available": False,
                        "desc": "未检测到可用的 CUDA 版 torch"})

    # ---- Apple Metal 加速：仅 macOS ----
    if plat == _MAC:
        mps_ok = False
        if torch_mod is not None and hasattr(getattr(torch_mod, "backends", None), "mps"):
            try:
                mps_ok = bool(torch_mod.backends.mps.is_available())
            except Exception:
                mps_ok = False
        out.append({
            "value": "mps",
            "label": "Metal 加速（MPS / CoreML）",
            "available": mps_ok,
            "desc": ("统一内存架构，Apple Silicon 上最快"
                     if mps_ok else "需要 macOS 12.3+ 且 ARM 架构（Apple Silicon）"),
        })

    # ---- AMD ROCm（Linux）/ DirectML（Windows）：只在确实装了对应后端时才列出 ----
    #     torch 的 ROCm 构建会把 torch.version.hip 暴露出来，这是最稳的判据。
    if plat == _LIN:
        rocm_ok = False
        if torch_mod is not None:
            try:
                hip = getattr(getattr(torch_mod, "version", None), "hip", "") or ""
                rocm_ok = bool(str(hip).strip())
            except Exception:
                rocm_ok = False
        if rocm_ok:
            out.append({"value": "rocm", "label": "AMD ROCm", "desc": "AMD 显卡加速"})
    elif plat == _WIN:
        # DirectML 走的是独立的 torch-directml 包
        if _has_module("torch_directml"):
            out.append({"value": "directml", "label": "DirectML（AMD / Intel GPU）",
                        "desc": "Windows 上非 NVIDIA 显卡的通用加速"})

    # ---- GGUF / llama.cpp：全平台（含 Termux，arm64 有官方构建）----
    if _has_module("llama_cpp"):
        out.append({"value": "gguf", "label": "GGUF / llama.cpp",
                    "desc": "用于 .gguf 自包含模型，CPU 推理"})
    else:
        out.append({"value": "gguf", "label": "GGUF / llama.cpp", "available": False,
                    "desc": "需要 llama-cpp-python"})

    # ---- Android 额外说明：手机只能走轻量路径 ----
    if plat == _AND:
        out.append({"value": "nnapi", "label": "NNAPI（神经网络 API）",
                    "available": False,
                    "desc": "尚未接入，建议先用 GGUF 小模型 + CPU"})
    return out


# --------------------------------------------------------------------------
# 推理线程数：桌面按真实核心数，移动端必须克制
# --------------------------------------------------------------------------
# 手机上一味堆线程只会触发温控降频，反而更慢更烫；这里给硬上限。
_MOBILE_THREAD_CAP = 4


def _cpu_cores() -> int:
    try:
        return max(1, os.cpu_count() or 1)
    except Exception:
        return 1


def _thread_options() -> tuple[list[dict], int]:
    """按**平台 + 真实核心数**生成线程档位。

    桌面：给到真实核心数；
    移动：上限 _MOBILE_THREAD_CAP，并在标签里说明原因，别让人以为漏档了。
    """
    cores = _cpu_cores()
    mobile = is_mobile_platform()
    cap = _MOBILE_THREAD_CAP if mobile else cores
    out: list[dict] = []
    picks = sorted({max(2, cores // 4), max(4, cores // 2), cap})
    for n in picks:
        if n <= cap:
            out.append({"value": str(n), "label": f"{n} 线程"})
    if not out:
        out.append({"value": str(cap), "label": f"{cap} 线程"})
    label = (f"自动（最多 {min(cores, cap)} 线程"
             + ("，移动端已封顶以避免降频）" if mobile else "）"))
    return ([{"value": "auto", "label": label}] + out, cores)


# --------------------------------------------------------------------------
# 人格预设：从 persona_presets 真实读取
# --------------------------------------------------------------------------
def _personas() -> list[dict]:
    try:
        from core import persona_presets as _pp
        active = str(_cfg.load().get("persona") or _pp.DEFAULT_PERSONA)
        items = _pp.list_personas(active)
        out = []
        for it in items:
            name = str(it.get("name") or it.get("id") or "").strip()
            if not name:
                continue
            out.append({
                "value": name,
                "label": name,
                "desc": str(it.get("description") or ""),
                "active": bool(it.get("active")),
                "builtin": bool(it.get("builtin", True)),
            })
        if out:
            return out
    except Exception:
        pass
    return [{"value": "活泼", "label": "活泼"}]


# --------------------------------------------------------------------------
# 语音合成：按平台探测真实可用的 TTS 引擎
# --------------------------------------------------------------------------
# pyttsx3 在不同平台用完全不同的驱动，可用性必须实测，不能按统一列表返回。
_PYTTSX3_DRIVER = {_WIN: "sapi5", _MAC: "nsss", _LIN: "espeak"}


def _tts_engine_state() -> dict:
    plat = host_platform()
    st = {"edge_tts": _has_module("edge_tts"),
          "pyttsx3": _has_module("pyttsx3"),
          "ffmpeg": False,
          "platform_tts": False,
          "driver": _PYTTSX3_DRIVER.get(plat, ""),
          "note": ""}
    # Android 上语音由**前端（Flutter）**侧的原生 TTS 负责，
    # 后端这一栏仅供参考，不要拿没有 pyttsx3 驱动当成"语音坏了"。
    if plat == _AND:
        st["note"] = "Android 上语音由 APP 原生 TTS 处理（后端仅作记录）"
    elif plat == _MAC:
        st["note"] = "macOS 使用 NSSpeechSynthesizer（nsss）"
    elif plat == _LIN:
        st["note"] = "Linux 需要系统装有 espeak / espeak-ng"
    elif plat == _WIN:
        st["note"] = "Windows 使用 SAPI5 系统语音"
    # pyttsx3 光 import 成功不代表驱动可用（比如 Linux 没装 espeak），
    # 真正 init 一次才算数。
    if st["pyttsx3"]:
        try:
            import pyttsx3  # noqa: PLC0415
            eng = pyttsx3.init()
            eng.stop()
            st["platform_tts"] = True
        except Exception:
            st["platform_tts"] = False
    try:
        from core.multimodal import AudioConverter
        st["ffmpeg"] = bool(AudioConverter.available())
    except Exception:
        pass
    return st


def _voices() -> list[dict]:
    """音色表：带上**真实性别与风格**，前端不必再从名字里猜。"""
    out = []
    try:
        from core.multimodal import VOICES
    except Exception:
        return out
    eng = _tts_engine_state()
    edge_ok = eng["edge_tts"]
    for v in VOICES:
        g = str(v.get("gender", "")).lower()
        if g.startswith("f"):
            glabel = "女声"
        elif g.startswith("m"):
            glabel = "男声"
        else:
            glabel = "中性"
        lang = str(v.get("lang", "zh-CN"))
        # edge-tts 音色只有在 edge_tts 装好后才能真正合成；
        # 手机上就算装了也要联网，且通常不如系统 TTS 稳。
        avail = bool(edge_ok)
        note = ""
        if not avail:
            note = "需要 edge-tts"
        elif is_mobile_platform():
            note = "移动端建议改用系统 TTS"
        out.append({
            "id": str(v.get("id", "")),
            "name": str(v.get("name", "")),
            "lang": lang,
            "gender": g or "neutral",
            "gender_label": glabel,
            "style": str(v.get("style", "")),
            "engine": "edge-tts",
            "available": avail,
            "note": note,
        })
    return out


# --------------------------------------------------------------------------
# 滑块取值范围（原先散落在前端各处）
#
# platforms 用于标注「哪些平台才有意义」—— 比如「窗口透明度」是桌面窗口的概念，
# 手机上没有自由浮动窗口，硬列出一个调不动的滑块只会让人困惑。
# 留空表示全平台通用。
# --------------------------------------------------------------------------
_DESKTOP = [_WIN, _MAC, _LIN]

_SLIDER_SPECS = {
    "speed": {"min": 0.0, "max": 1.0, "default": 0.55, "label": "语速",
              "platforms": []},
    "volume": {"min": 0.0, "max": 1.0, "default": 0.80, "label": "音量",
               "platforms": []},
    "opacity": {"min": 0.3, "max": 1.0, "default": 0.92, "label": "窗口透明度",
                "platforms": _DESKTOP},
    "renderQuality": {"min": 0.1, "max": 1.0, "default": 0.78, "label": "3D 渲染质量",
                      "platforms": []},
}


def _norm_lang(v) -> str:
    s = str(v or "").strip()
    return {
        "": "zh-CN", "zh": "zh-CN", "zh-cn": "zh-CN", "zh-hans": "zh-CN",
        "zh-tw": "zh-TW", "zh-hant": "zh-TW",
        "en": "en-US", "en-us": "en-US",
        "ja": "ja-JP", "ja-jp": "ja-JP",
    }.get(s.lower(), s or "zh-CN")


def all_options() -> dict:
    """汇总所有设置项可选项。"""
    cfg = _cfg.load()
    threads, cores = _thread_options()
    ui_cfg = cfg.get("ui") or {}
    voice_cfg = cfg.get("voice") or {}
    model_cfg = cfg.get("model") or {}
    try:
        from core.multimodal import VOICES
        voice_count = len(VOICES)
    except Exception:
        voice_count = 0
    return {
        "ok": True,
        "ts": time.time(),
        # 前端据此显示"本机 / 当前平台"，也便于排查用户提交的环境信息
        "platform": {
            "os": host_platform(),
            "label": platform_label(),
            "mobile": is_mobile_platform(),
            "cores": cores,
        },
        "ui": {
            "themes": _themes(),
            "languages": _LANGUAGES,
            "theme": str(ui_cfg.get("theme") or "dark"),
            "language": _norm_lang(cfg.get("language")),
        },
        "model": {
            "personas": _personas(),
            "persona": str(cfg.get("persona") or ""),
            "inference_backends": _inference_backends(),
            "inference_backend": str(model_cfg.get("inference_backend") or "auto"),
            "threads": threads,
            "threads_max": cores,
            "threads_current": str(model_cfg.get("threads") or "auto"),
        },
        "render": {
            "modes": _render_modes(),
            "mode": str((cfg.get("render") or {}).get("backend") or "auto"),
        },
        "voice": {
            "engines": _tts_engine_state(),
            "count": voice_count,
            "voices": _voices(),
            "current": str(voice_cfg.get("id") or ""),
        },
        "sliders": _SLIDER_SPECS,
    }


# --------------------------------------------------------------------------
# settings:set —— 把设置真正写进配置（原先多数只 setState，重启就没了）
# --------------------------------------------------------------------------
_ALLOWED_PATHS = {
    "ui.theme": ("ui", "theme"),
    "ui.language": (None, "language"),
    "model.persona": (None, "persona"),
    "model.inference_backend": ("model", "inference_backend"),
    "model.threads": ("model", "threads"),
    "render.backend": ("render", "backend"),
    "voice.id": ("voice", "id"),
    "ui.sliders": ("ui", "sliders"),
}

# 各设置项允许的值，写成 "配置路径 -> 可选值来源"，
# 这样跨平台时不会出现「Windows 上把 render.backend 写成 metal」这种笑话。
_VALUE_RULES = {
    "ui.theme": lambda: [o["value"] for o in _themes()],
    "ui.language": lambda: [o["value"] for o in _LANGUAGES],
    "render.backend": lambda: [o["value"] for o in _render_modes()],
    "model.inference_backend": lambda: [o["value"] for o in _inference_backends()],
}


def set_option(path: str, value):
    """按点分路径写配置。

    只允许白名单路径；取值还要跟当前平台的实际可选项核对，
    避免写了一台机器上根本不存在的后端名。
    """
    path = (path or "").strip()
    if path not in _ALLOWED_PATHS:
        return {"ok": False,
                "error": f"不支持的设置项：{path}；可用：{sorted(_ALLOWED_PATHS)}"}
    value = str(value or "").strip()
    rule = _VALUE_RULES.get(path)
    if rule is not None:
        try:
            allowed = rule()
        except Exception:
            allowed = []
        if allowed and value not in allowed:
            return {"ok": False,
                    "error": f"「{value}」在{platform_label()}上不可用；"
                             f"可用值：{allowed}"}
    parent, key = _ALLOWED_PATHS[path]
    try:
        if parent is None:
            _cfg.patch({key: value})
        else:
            cfg = _cfg.load()
            cur = dict(cfg.get(parent) or {})
            cur[key] = value
            _cfg.patch({parent: cur})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "path": path, "value": value}


def handle(rest: str) -> str:
    """处理 ``settings:`` 命令族，返回 JSON 字符串。"""
    rest = (rest or "").strip()
    op, _, arg = rest.partition(" ")
    op = op.strip().lower()
    if op in ("options", "opts", "列表", ""):
        return json.dumps(all_options(), ensure_ascii=False)
    if op in ("set", "设置"):
        path, _, val = arg.partition(" ")
        if not path.strip():
            return json.dumps({"ok": False, "error": "用法：settings:set ui.theme dark"},
                              ensure_ascii=False)
        return json.dumps(set_option(path.strip(), val), ensure_ascii=False)
    return json.dumps({"ok": False,
                       "error": f"未知设置指令：{op}（可用：options / set）"},
                      ensure_ascii=False)
