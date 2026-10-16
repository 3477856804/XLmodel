# -*- coding: utf-8 -*-
"""依赖自愈：检测缺失可选依赖并按需 pip 安装。白名单包名、train 档要 force、
失败（离线/无 pip/打包态）如实报错。纯标准库，无第三方依赖。"""
import importlib.util
import os
import subprocess
import sys
import threading

_LIGHT = "light"
_SPEECH = "speech"
_VISION = "vision"
_HUB = "hub"
_TRAIN = "train"

# (pip 包名, import 名, 档位, 用途, 体积提示)
CATALOG = (
    ("psutil", "psutil", _LIGHT, "CPU/内存/电量遥测", "小"),
    ("jieba", "jieba", _LIGHT, "中文分词（检索召回）", "小"),
    ("requests", "requests", _LIGHT, "HTTP 抓取 / 通道", "小"),
    ("aiohttp", "aiohttp", _LIGHT, "异步 HTTP（浏览器/通道）", "小"),
    ("edge-tts", "edge_tts", _SPEECH, "联网情感语音（云端 TTS）", "小"),
    ("openai-whisper", "whisper", _SPEECH, "本地语音识别（需 torch）", "中"),
    ("pyaudio", "pyaudio", _SPEECH, "麦克风录音（Linux 需 portaudio）", "小(可能需系统库)"),
    ("sounddevice", "sounddevice", _SPEECH, "音频输入输出备选", "小"),
    ("opencv-python", "cv2", _VISION, "无 WebView 时的 2D 视频兜底", "大"),
    ("huggingface-hub", "huggingface_hub", _HUB, "HuggingFace 模型下载", "中"),
    ("modelscope", "modelscope", _HUB, "魔搭国内镜像下载通道", "中"),
    ("llama-cpp-python", "llama_cpp", _HUB, "GGUF 本地推理运行时", "大(编译)"),
    ("torch", "torch", _TRAIN, "训练/合并内核", "极多GB"),
    ("transformers", "transformers", _TRAIN, "HF 模型加载", "多(依赖torch)"),
    ("peft", "peft", _TRAIN, "LoRA 适配器", "小(依赖torch)"),
    ("accelerate", "accelerate", _TRAIN, "训练调度", "小(依赖torch)"),
)

_BY_IMPORT = {m: (pkg, tier, use, size) for pkg, m, tier, use, size in CATALOG}
_PACKAGES = {pkg for pkg, _, _, _, _ in CATALOG}
_AUTO_TIERS = (_LIGHT,)


def is_installed(import_name: str) -> bool:
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ValueError):
        return False


def _tier_pkg_names(tier: str) -> list:
    return [pkg for pkg, m, t, u, s in CATALOG if t == tier]


def _import_name(pkg: str) -> str:
    return next(m for p, m, t, u, s in CATALOG if p == pkg)


def _tier_of(pkg: str) -> str:
    return next(t for p, m, t, u, s in CATALOG if p == pkg)


def status() -> dict:
    installed, missing = [], []
    for pkg, imp, tier, use, size in CATALOG:
        row = {"package": pkg, "tier": tier, "purpose": use, "size": size}
        (installed if is_installed(imp) else missing).append(row)
    return {
        "ok": True,
        "python": sys.executable,
        "frozen": bool(getattr(sys, "frozen", False)),
        "pip_available": _pip_available(),
        "network": _has_network(),
        "installed": installed,
        "missing": missing,
        "auto_install_enabled": _auto_enabled(),
        "train_guard": "torch 栈（数 GB）必须显式 force，首启绝不自动下载",
    }


def _pip_cmd(packages: list, *, user: bool) -> list:
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
           "--no-input"]
    if user:
        cmd.append("--user")
    return cmd + packages


def precheck_install() -> dict:
    """安装前的同步预检（frozen / pip / 网络），任一项不满足即返回可执行错误。

    此前的失败路径：同步返回 ok:true + task_id，后台线程在 _run_install
    里秒失败，结果只落进 BackgroundTaskManager 的 task 表无人读取 ——
    前端表现为「点击安装没反应」。把检查前移到这里，让失败原因同步可见。
    """
    if getattr(sys, "frozen", False):
        return {"ok": False,
                "error": "打包模式（frozen）无法在线安装依赖：产物内没有 pip。"
                         "请使用源码模式运行 python main.py --install-deps <包名>，"
                         "或在打包时内置该依赖。"}
    if not _pip_available():
        return {"ok": False,
                "error": "当前解释器没有 pip（%s），无法自动安装。"
                         "请先安装 pip，或用源码模式运行 "
                         "python main.py --install-deps <包名>。" % sys.executable}
    if not _has_network():
        return {"ok": False, "error": "本机没有可用网络，无法下载依赖。"}
    return {"ok": True}


def _run_install(packages: list, timeout: float = 900.0) -> dict:
    pre = precheck_install()
    if not pre.get("ok"):
        return pre
    last = None
    for user in (False, True):
        try:
            cp = subprocess.run(_pip_cmd(packages, user=user),
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "安装超时（>%ss），已终止。" % int(timeout)}
        except Exception as e:                                    # noqa: BLE001
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
        last = cp
        if cp.returncode == 0:
            return {"ok": True, "user_mode": user, "tail": (cp.stdout or "")[-1200:]}
        err = (cp.stderr or cp.stdout or "").lower()
        if "externally-managed" in err or "permission" in err or "--user" in err:
            continue
        break
    tail = ((last.stderr or "") + (last.stdout or ""))[-1200:] if last else ""
    return {"ok": False, "error": "pip 安装失败（退出码 %s）" %
            (last.returncode if last else "?"), "tail": tail}


def validate(names, *, force_train: bool = False) -> dict:
    """同步校验，不执行安装：白名单 / train 档 / 空列表 / 已就绪清单。"""
    if isinstance(names, str):
        names = [n for n in names.replace(",", " ").split() if n]
    req = [n.strip() for n in names if n and n.strip()]
    unknown = [n for n in req if n not in _PACKAGES]
    if unknown:
        return {"ok": False,
                "error": "不在白名单，拒绝安装：%s" % ", ".join(unknown)}
    if not req:
        return {"ok": False, "error": "没有要安装的包"}
    tiers = {_tier_of(n) for n in req}
    if _TRAIN in tiers and not force_train:
        return {"ok": False,
                "error": "train 档（torch 栈，数 GB）不自动下载。确需请带 force 显式确认。"}
    todo = [n for n in req if not is_installed(_import_name(n))]
    skipped = [n for n in req if n not in todo]
    return {"ok": True, "todo": todo, "skipped": skipped}


def install(names, *, force_train: bool = False, output=None) -> dict:
    v = validate(names, force_train=force_train)
    if not v["ok"]:
        return {"ok": False, "error": v["error"]}
    skipped = v["skipped"]
    todo = v["todo"]
    if not todo:
        return {"ok": True, "installed": [], "skipped": skipped,
                "note": "所请求的依赖均已就绪，无需下载"}
    _emit(output, "开始安装：%s" % ", ".join(todo))
    r = _run_install(todo)
    if r.get("ok"):
        verified = [n for n in todo if is_installed(_import_name(n))]
        failed = [n for n in todo if n not in verified]
        _emit(output, "完成：成功 %s，失败 %s" % (verified or "无", failed or "无"))
        return {"ok": not failed, "installed": verified, "failed": failed,
                "skipped": skipped, "user_mode": r.get("user_mode", False)}
    _emit(output, "失败：%s" % r.get("error"))
    return {"ok": False, "error": r.get("error"), "tail": r.get("tail", ""),
            "skipped": skipped}


def ensure(import_name: str) -> dict:
    entry = _BY_IMPORT.get(import_name)
    if not entry:
        return {"ok": False, "error": "未知依赖：%s" % import_name}
    pkg, tier, use, size = entry
    if is_installed(import_name):
        return {"ok": True, "already": True, "package": pkg}
    if tier == _TRAIN:
        return {"ok": False, "package": pkg,
                "error": "%s 属于 train 档（数 GB），需显式确认后再装" % pkg}
    return dict(install([pkg]), package=pkg)


def autofetch_light() -> dict:
    if not _auto_enabled():
        return {"ok": True, "skipped": "config.deps.auto_install=off"}
    if not _pip_available() or getattr(sys, "frozen", False) or not _has_network():
        return {"ok": False, "note": "首启自动获取跳过（无 pip / 打包态 / 无网络）"}
    todo = [pkg for tier in _AUTO_TIERS for pkg in _tier_pkg_names(tier)
            if not is_installed(_import_name(pkg))]
    if not todo:
        return {"ok": True, "installed": [], "note": "轻量依赖已全部就绪"}
    return install(todo)


def handle(sub: str) -> str:
    import json
    sub = (sub or "").strip()
    op, _, arg = (sub + " ").partition(" ")
    op, arg = op.lower(), arg.strip()
    if op in ("", "status", "list"):
        return json.dumps(status(), ensure_ascii=False)
    if op == "install":
        tokens = arg.split()
        force = 'force' in tokens
        names = [t for t in tokens if t != 'force']
        return json.dumps(install(names, force_train=force), ensure_ascii=False)
    return json.dumps({"ok": False,
                       "error": "未知子命令：%s（可用：status / install <包...> [force]）" % op},
                      ensure_ascii=False)


_emitted_lock = threading.Lock()


def _emit(output, text):
    if not callable(output):
        return
    try:
        with _emitted_lock:
            output(str(text))
    except Exception:                                             # noqa: BLE001
        pass


def _auto_enabled() -> bool:
    try:
        try:
            from . import config as _cfg
        except Exception:                                         # noqa: BLE001
            from core import config as _cfg                       # type: ignore
        d = _cfg.load() or {}
        return bool((d.get("deps") or {}).get("auto_install", True))
    except Exception:                                             # noqa: BLE001
        return True


def _pip_available() -> bool:
    return importlib.util.find_spec("pip") is not None


def _has_network() -> bool:
    import socket
    host = os.environ.get("XIAOLING_NET_PROBE", "pypi.org")
    try:
        with socket.create_connection((host, 443), timeout=3.0):
            return True
    except Exception:                                             # noqa: BLE001
        return False
