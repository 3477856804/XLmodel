# -*- coding: utf-8 -*-
"""人格预设管理。

设计要点
--------
- **5 个内置预设**：活泼 / 温柔 / 高冷 / 元气 / 沉稳，覆盖不同语气类型。
- **可扩展自定义**：用户新增的人格存到 ``.star_core/persona_custom.json``，
  内置预设**不可删除**（只能切换），自定义可删。
- **切换即生效**：写入 ``config.persona``，``XiaoLing._build_prompt`` 下轮
  对话就会把对应 ``prompt_hint`` 注入 system prompt。

权威配置仍在 :mod:`core.config` 的 ``persona`` 字段，本模块只负责
"有哪些预设 / 自定义增删" 这层元数据。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.config import STAR_DIR

# --------------------------------------------------------------------------- #
#  5 个内置人格预设
# --------------------------------------------------------------------------- #
BUILTIN_PERSONAS: list[dict[str, Any]] = [
    {
        "id": "lively",
        "name": "活泼",
        "description": "元气满满，爱蹦爱跳，永远有说不完的话",
        "prompt_hint": "你性格活泼外向，语气轻快上扬，常用语气词，喜欢主动延伸话题。",
    },
    {
        "id": "gentle",
        "name": "温柔",
        "description": "轻声细语，耐心倾听，善于安抚情绪",
        "prompt_hint": "你性格温柔耐心，语气柔和共情，先共情再回应，少打断。",
    },
    {
        "id": "aloof",
        "name": "高冷",
        "description": "话不多但句句精准，偶尔毒舌",
        "prompt_hint": "你性格高冷克制，回复简短精炼，不说废话，偶尔带一点毒舌。",
    },
    {
        "id": "genki",
        "name": "元气",
        "description": "超级话痨，热情高涨，像永远不充电的电池",
        "prompt_hint": "你元气爆棚，热情高涨，回复充满能量，爱用感叹号和夸张表达。",
    },
    {
        "id": "steady",
        "name": "沉稳",
        "description": "冷静可靠，条理清晰，偏理性分析",
        "prompt_hint": "你性格沉稳理性，条理清晰，优先给结论和依据，不情绪化。",
    },
]

DEFAULT_PERSONA = "活泼"

_CUSTOM_PATH: Path = STAR_DIR / "persona_custom.json"
_MAX_CUSTOM = 20          # 自定义人格上限，防止文件无限膨胀
_MAX_NAME_LEN = 12


# --------------------------------------------------------------------------- #
#  自定义人格读写
# --------------------------------------------------------------------------- #
def _load_custom() -> list[dict[str, Any]]:
    if not _CUSTOM_PATH.exists():
        return []
    try:
        data = json.loads(_CUSTOM_PATH.read_text(encoding="utf-8"))
        items = data.get("personas") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        return [x for x in items if isinstance(x, dict) and x.get("name")]
    except (OSError, ValueError):
        return []


def _save_custom(items: list[dict[str, Any]]) -> bool:
    try:
        _CUSTOM_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CUSTOM_PATH.write_text(
            json.dumps({"personas": items}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------- #
#  对外 API
# --------------------------------------------------------------------------- #
def list_personas(active: str | None = None) -> list[dict[str, Any]]:
    """返回全部预设（内置在前，自定义在后），每项含 ``builtin`` / ``active``。

    ``active`` 参数既可传名字（``活泼``）也可传 id（``lively``）。
    """
    act = (active or DEFAULT_PERSONA).strip()
    out: list[dict[str, Any]] = [
        {**p, "builtin": True, "active": p["name"] == act or p["id"] == act}
        for p in BUILTIN_PERSONAS
    ]
    for p in _load_custom():
        out.append({
            "id": str(p.get("id") or f"custom_{int(p.get('created_at', 0))}"),
            "name": str(p.get("name") or "自定义"),
            "description": str(p.get("description") or ""),
            "prompt_hint": str(p.get("prompt_hint") or ""),
            "builtin": False,
            "active": str(p.get("name")) == act,
        })
    return out


def resolve(name: str | None) -> dict[str, Any] | None:
    """按名字或 id 找到预设；找不到返回 None。

    注意两个参数都要认：内置用短 id（``aloof``）方便前端调用，
    自定义只有中文名没有稳定 id，所以匹配时**两者都试**。
    """
    target = (name or "").strip()
    if not target:
        return None
    all_presets = list_personas(target)
    # 先按名字精确匹配（自定义人格只有名字）
    for p in all_presets:
        if p["name"] == target:
            return p
    # 再按 id 匹配（内置预设的短 id）
    for p in all_presets:
        if p["id"] == target:
            return p
    return None


def hint_for(name: str | None) -> str:
    """取人格对应的 prompt 引导语；未知人格返回空串（不阻断对话）。"""
    p = resolve(name)
    return str(p["prompt_hint"]) if p else ""


def add_custom(name: str, description: str = "", prompt_hint: str = "") -> tuple[bool, str]:
    """新增自定义人格。返回 (是否成功, 提示信息)。"""
    nm = (name or "").strip()[:_MAX_NAME_LEN]
    if not nm:
        return False, "人格名不能为空"
    items = _load_custom()
    if any(x.get("name") == nm for x in items):
        return False, f"已存在同名人格「{nm}」"
    if len(items) >= _MAX_CUSTOM:
        return False, f"自定义人格已达上限（{_MAX_CUSTOM} 个）"
    items.append({
        "id": f"custom_{int(time.time())}",
        "name": nm,
        "description": (description or "").strip()[:80],
        "prompt_hint": (prompt_hint or "").strip()[:300],
        "created_at": int(time.time()),
    })
    if not _save_custom(items):
        return False, "保存失败：无法写入人格文件"
    return True, f"已添加人格「{nm}」"


def delete_custom(name: str) -> tuple[bool, str]:
    """删除自定义人格。内置预设拒绝删除。"""
    nm = (name or "").strip()
    if any(p["name"] == nm for p in BUILTIN_PERSONAS):
        return False, "内置人格不可删除，可以直接切换"
    items = _load_custom()
    nxt = [x for x in items if x.get("name") != nm]
    if len(nxt) == len(items):
        return False, f"未找到自定义人格「{nm}」"
    if not _save_custom(nxt):
        return False, "保存失败：无法写入人格文件"
    return True, f"已删除人格「{nm}」"


# --------------------------------------------------------------------------- #
#  预设编辑 / 导入导出 / 使用统计
# --------------------------------------------------------------------------- #
_usage_count: dict[str, int] = {}      # preset_id 或 name -> 使用次数


def update_preset(preset_id: str, **kwargs) -> tuple[bool, str]:
    """更新自定义人格预设字段（name/description/prompt_hint），内置预设不可修改。"""
    pid = (preset_id or "").strip()
    if not pid:
        return False, "预设 id 不能为空"
    if any(p["id"] == pid for p in BUILTIN_PERSONAS):
        return False, "内置人格不可修改"
    items = _load_custom()
    for x in items:
        if x.get("id") == pid or x.get("name") == pid:
            for field in ("name", "description", "prompt_hint"):
                if field in kwargs and kwargs[field] is not None:
                    x[field] = str(kwargs[field])[:300 if field == "prompt_hint" else 80]
            if not _save_custom(items):
                return False, "保存失败"
            return True, "预设已更新"
    return False, f"未找到预设「{pid}」"


def export_presets(filepath: str) -> str:
    """导出所有预设（内置+自定义）为 JSON 文件，返回写入路径。"""
    data = {"builtin": BUILTIN_PERSONAS, "custom": _load_custom(),
            "usage": dict(_usage_count)}
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(p)


def import_presets(filepath: str) -> tuple[int, int]:
    """从 JSON 导入自定义预设，跳过重复 id。返回 (新增数, 跳过数)。"""
    try:
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0, 0
    incoming = data.get("custom") if isinstance(data, dict) else None
    if not isinstance(incoming, list):
        return 0, 0
    items = _load_custom()
    existing_ids = {x.get("id") for x in items}
    added = skipped = 0
    for x in incoming:
        if not isinstance(x, dict) or not x.get("name"):
            continue
        if x.get("id") in existing_ids:
            skipped += 1
            continue
        items.append({
            "id": x.get("id") or f"custom_{int(time.time())}_{added}",
            "name": str(x["name"])[:_MAX_NAME_LEN],
            "description": str(x.get("description", ""))[:80],
            "prompt_hint": str(x.get("prompt_hint", ""))[:300],
            "created_at": int(time.time()),
        })
        existing_ids.add(items[-1]["id"])
        added += 1
    if added and not _save_custom(items):
        return 0, skipped
    return added, skipped


def record_usage(preset_id: str) -> None:
    """记录某人格被使用一次。"""
    pid = (preset_id or "").strip()
    if pid:
        _usage_count[pid] = _usage_count.get(pid, 0) + 1


def get_usage_stats() -> dict:
    """返回每个人格的使用次数统计。"""
    return dict(sorted(_usage_count.items(), key=lambda kv: kv[1], reverse=True))