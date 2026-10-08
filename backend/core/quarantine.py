# -*- coding: utf-8 -*-
"""安全移除工具 —— 项目级红线实现。

核心约束（老板明确要求，不可违背）：
    任何情况下不得以任何方式删除磁盘上的文件。

所有"需要删除"的文件一律：
    1) 移动到隔离区目录（Windows: D:\待处理；其它平台: ~/待处理；
       可用环境变量 XIAOLING_PENDING_DIR 覆盖），带时间戳与「待删除」后缀，
       绝不覆盖同名文件
    2) 记入清单 <隔离区>/_待删除清单.json
    3) 清单副本同步到桌面（或主目录），供人工复核

只有人工（老板）复核后自行决定是否真正清除，本模块永不执行 delete/unlink/rmtree。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path


def _default_pending_root() -> Path:
    """隔离区默认目录（跨平台）。

    Windows 沿用老板约定的 ``D:\\待处理``；Linux/macOS/Android 没有 D: 盘，
    若照搬 ``D:\\待处理`` 会被当成 cwd 下一个带反斜杠的怪目录名。
    非 Windows 一律落在用户主目录下的 ``待处理``，语义一致且可见。
    """
    env = os.environ.get("XIAOLING_PENDING_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform.startswith("win"):
        return Path(r"D:\待处理")
    try:
        return Path.home() / "待处理"
    except Exception:
        return Path("待处理")


# 隔离区根目录（可用 XIAOLING_PENDING_DIR 覆盖）
PENDING_ROOT = _default_pending_root()
MANIFEST_NAME = "_待删除清单.json"

_lock = threading.RLock()


def _desktop_dir() -> Path | None:
    """定位当前用户桌面目录（兼容 Windows 与类 Unix）。"""
    try:
        home = Path.home()
    except Exception:
        return None
    for cand in (home / "Desktop", home / "桌面", home):
        if cand.is_dir():
            return cand
    return None


def ensure_pending_dir() -> Path:
    PENDING_ROOT.mkdir(parents=True, exist_ok=True)
    return PENDING_ROOT


def _unique(dst: Path) -> Path:
    """绝不覆盖：若目标已存在，追加序号。"""
    if not dst.exists():
        return dst
    parent = dst.parent
    stem = dst.name
    for i in range(1, 10000):
        alt = parent / f"{stem}.{i}"
        if not alt.exists():
            return alt
    return parent / f"{stem}.{int(time.time())}"


def move_to_pending(path: str | Path, reason: str = "", category: str = "") -> dict:
    """把"需要删除"的文件/目录移入隔离区。返回结构化结果。

    返回:
        {"ok": bool, "src": str, "dst": str, "reason": str, "error": str}
    """
    src = Path(path)
    result = {"ok": False, "src": str(src), "dst": "", "reason": reason,
              "category": category, "error": ""}
    if not src.exists():
        result["error"] = "源路径不存在（无需处理）"
        return result

    try:
        ensure_pending_dir()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = src.name
        # 目录与文件统一加中文后缀，便于人工识别
        target_name = f"{base}__{stamp}__待删除"
        dst = _unique(PENDING_ROOT / target_name)

        # 同盘：move 是"重命名"语义，不产生删除动作 —— 安全。
        # 跨盘：shutil.move 内部会 copy + 删除源，会触发真正的删除动作。
        #       红线要求"绝不删除"，因此跨盘一律改为"复制过去 + 保留源"。
        src_drive = os.path.splitdrive(str(src))[0].upper()
        dst_drive = os.path.splitdrive(str(dst))[0].upper()
        if src_drive and dst_drive and src_drive != dst_drive:
            if src.is_dir():
                shutil.copytree(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))
            result["mode"] = "copied"
            result["kept_source"] = True
        else:
            shutil.move(str(src), str(dst))
            result["mode"] = "moved"
            result["kept_source"] = False

        result["dst"] = str(dst)
        result["ok"] = True
        _append_manifest(result)
        return result
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
        return result


def _manifest_path() -> Path:
    return ensure_pending_dir() / MANIFEST_NAME


def _append_manifest(entry: dict) -> None:
    """把本次移出记录追加进清单（只写，绝不删）。"""
    with _lock:
        data = {"updated": datetime.now().isoformat(timespec="seconds"),
                "items": []}
        mp = _manifest_path()
        if mp.is_file():
            try:
                data = json.loads(mp.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "items" not in data:
                    data = {"updated": "", "items": []}
            except Exception:
                pass
        data["updated"] = datetime.now().isoformat(timespec="seconds")
        data.setdefault("items", []).append({
            "time": entry.get("time") or datetime.now().isoformat(timespec="seconds"),
            "原名": os.path.basename(entry.get("src", "")),
            "原位置": entry.get("src", ""),
            "隔离后位置": entry.get("dst", ""),
            "类别": entry.get("category", ""),
            "原因": entry.get("reason", ""),
            "方式": "已复制到隔离区（原位置保留，未删除）"
                    if entry.get("kept_source") else "已移入隔离区（未删除）",
        })
        try:
            mp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        except Exception:
            pass
        _export_to_desktop(data)


def _export_to_desktop(data: dict) -> None:
    """把清单副本同步到桌面，便于老板复核。只写，不删。"""
    d = _desktop_dir()
    if not d:
        return
    try:
        items = data.get("items", [])
        lines = [
            "# 待删除文件清单（已隔离到 {root}）".format(root=str(PENDING_ROOT)),
            "",
            "说明：以下文件/目录**均未被删除**，已移入隔离区等待人工复核。",
            "复核后如需彻底清除，请自行处理；程序不会自动删除任何东西。",
            "",
            "生成时间：{t}".format(t=data.get("updated", "")),
            "共 {n} 项".format(n=len(items)),
            "",
            "| # | 原文件名 | 原位置 | 隔离后位置 | 类别 | 原因 | 处理方式 |",
            "|---|---|---|---|---|---|---|",
        ]
        for i, it in enumerate(items, 1):
            lines.append(
                "| {i} | {name} | {src} | {dst} | {cat} | {why} | {mode} |".format(
                    i=i,
                    name=it.get("原名", ""),
                    src=it.get("原位置", ""),
                    dst=it.get("隔离后位置", ""),
                    cat=it.get("类别", ""),
                    why=it.get("原因", ""),
                    mode=it.get("方式", ""),
                ))
        (d / "待删除文件清单.md").write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass


def pending_items() -> list:
    """读取当前隔离清单（只读）。"""
    mp = _manifest_path()
    if not mp.is_file():
        return []
    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
        return list(data.get("items", []))
    except Exception:
        return []


def safe_replace_dir(target: Path, source: Path) -> dict:
    """用 source 替换 target，且**不删除**原 target：先隔离，再复制。

    用于插件/模型"重装"场景——老版本进隔离区，而不是被 rmtree 抹掉。
    """
    target = Path(target)
    source = Path(source)
    out = {"ok": False, "quarantined": "", "error": ""}
    if target.exists():
        r = move_to_pending(target, reason="被新版本替换", category="replace")
        if not r.get("ok"):
            out["error"] = r.get("error", "隔离失败")
            return out
        out["quarantined"] = r.get("dst", "")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(source), str(target))
        out["ok"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out
