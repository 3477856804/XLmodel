# -*- coding: utf-8 -*-
"""渲染舞台（stage）—— 3D 角色与动作的资源管理层。

定位说明（重要）：
    v0.0.1 架构把**画面渲染**移到了 Flutter 端（model_viewer_plus + WebView2），
    后端 `server._get_renderer()` 因此刻意返回 None。
    但这样带来两个后果：
      1) `PlayAction` RPC 恒返回"渲染器不可用"
      2) 模型/动作只有文件名，没有元信息（骨骼数、材质、时长等）

    本模块不重复做光栅化渲染，而是补齐后端**缺失的那一半**：
      - 解析 VRM/glTF，给出模型元信息（骨骼/材质/表情）
      - 管理动作库（resources/animations/*.vrma）
      - 维护"当前模型 / 当前动作"状态，并写入配置供前端读取

    这样后端与 Flutter 各司其职：后端管资源与状态，前端管画面。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from .vrm_gltf import VRM, GLTF_MAGIC  # noqa: F401
except Exception:                          # pragma: no cover - 独立导入场景
    from vrm_gltf import VRM, GLTF_MAGIC   # noqa: F401


# ---------------------------------------------------------------- 资源定位
def _resource(*parts: str) -> Path:
    """定位 resources 目录。优先用 config，失败时回退到项目根。"""
    try:
        from core.config import resource
        return Path(resource(*parts))
    except Exception:
        root = Path(__file__).resolve().parent.parent.parent
        return root.joinpath("resources", *parts)


def _star(*parts: str) -> Path:
    try:
        from core.config import star
        return Path(star(*parts))
    except Exception:
        root = Path(__file__).resolve().parent.parent.parent
        return root.joinpath(".star_core", *parts)


MODEL_EXTS = (".vrm", ".glb", ".fbx")
ACTION_EXTS = (".vrma", ".bvh", ".fbx")


class Stage:
    """3D 舞台：模型 + 动作的资源管理与状态维护。"""

    def __init__(self, models_dir: Path | None = None,
                 actions_dir: Path | None = None):
        self.models_dir = Path(models_dir) if models_dir else _resource("models")
        self.actions_dir = Path(actions_dir) if actions_dir else _resource("animations")
        self._model_path: str = ""
        self._action_path: str = ""
        self._cache: dict = {}
        self._mouth_open: float = 0.0
        self._blink_request_at: float = 0.0
        self._eye_x: float = 0.0
        self._eye_y: float = 0.0
        self._load_state()

    # ---------------- 状态持久化 ----------------
    def _load_state(self) -> None:
        try:
            from core.config import load
            cfg = load() or {}
            av = (cfg.get("avatar") or {})
            self._model_path = av.get("model_path", "") or ""
            self._action_path = av.get("action_path", "") or ""
        except Exception:
            pass

    def _save_state(self) -> None:
        try:
            from core.config import patch
            patch({"avatar": {
                "model_path": self._model_path,
                "action_path": self._action_path,
                "updated_at": time.time(),
            }})
        except Exception:
            pass

    # ---------------- 模型 ----------------
    def list_models(self) -> list:
        """列出可用角色模型（含元信息）。"""
        out = []
        if not self.models_dir.is_dir():
            return out
        for p in sorted(self.models_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in MODEL_EXTS:
                out.append({
                    "name": p.stem,
                    "path": str(p.resolve()),
                    "ext": p.suffix.lower(),
                    "size": p.stat().st_size,
                    "size_text": _human(p.stat().st_size),
                    **self.describe_model(str(p)),
                })
        return out

    def describe_model(self, path: str) -> dict:
        """解析模型元信息。失败时降级为仅文件大小，绝不抛异常。"""
        p = Path(path)
        if not p.is_file():
            return {"ok": False, "error": "文件不存在"}
        if p.suffix.lower() != ".vrm":
            return {"ok": True, "parsed": False,
                    "note": "非 VRM 格式，跳过解析"}
        try:
            v = VRM(p)
            js = v.json
            ext = (js.get("extensions") or {}).get("VRM") or {}
            nodes = js.get("nodes") or []
            # 骨骼：node 带 skin 引用或位于 skins 的 joints 中
            joint_ids = set()
            for s in (js.get("skins") or []):
                joint_ids.update(s.get("joints") or [])
            bones = len(joint_ids) if joint_ids else sum(
                1 for n in nodes if n.get("skin") is not None)
            blend = ((ext.get("blendShapeMaster") or {})
                     .get("blendShapeGroups") or [])
            return {
                "ok": True, "parsed": True,
                "version": ext.get("specVersion") or ext.get("version") or "",
                "title": (ext.get("meta") or {}).get("title") or p.stem,
                "author": (ext.get("meta") or {}).get("author") or "",
                "meshes": len(js.get("meshes") or []),
                "materials": len(js.get("materials") or []),
                "nodes": len(nodes),
                "bones": bones,
                "expressions": len(blend),
            }
        except Exception as e:                              # noqa: BLE001
            return {"ok": True, "parsed": False,
                    "error": f"{type(e).__name__}: {e}"}

    def switch_model(self, path: str) -> dict:
        """切换当前角色（记录状态，供前端读取后加载）。"""
        p = Path(path)
        if not p.is_file():
            return {"ok": False, "error": f"模型文件不存在：{path}"}
        self._model_path = str(p.resolve())
        self._save_state()
        return {"ok": True, "model": self._model_path,
                **self.describe_model(self._model_path)}

    @property
    def model_path(self) -> str:
        return self._model_path

    # ---------------- 动作 ----------------
    def list_actions(self) -> list:
        """列出动作库（resources/animations）。"""
        out = []
        if not self.actions_dir.is_dir():
            return out
        for p in sorted(self.actions_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in ACTION_EXTS:
                name = p.stem
                low = name.lower()
                out.append({
                    "name": name,
                    "path": str(p.resolve()),
                    "size": p.stat().st_size,
                    "size_text": _human(p.stat().st_size),
                    "dance": ("dance" in low) or ("舞" in name),
                    "idle": ("待机" in name) or ("idle" in low) or ("挂机" in name),
                })
        return out

    def play_action(self, path: str) -> dict:
        """播放动作（记录状态，前端据此触发 ModelViewer 播放）。"""
        p = Path(path)
        if not p.is_file():
            return {"ok": False, "error": f"动作文件不存在：{path}"}
        self._action_path = str(p.resolve())
        self._save_state()
        return {"ok": True, "action": self._action_path,
                "name": p.stem, "message": f"正在播放：{p.stem}"}

    @property
    def action_path(self) -> str:
        return self._action_path

    # ---------------- 面部驱动（口型 / 眨眼 / 视线） ----------------
    def set_mouth_open(self, level: float) -> dict:
        """控制 VRM 模型嘴部开合（0.0-1.0）。"""
        try:
            if not self._model_path:
                return {"ok": False, "error": "模型未加载，无法控制嘴部"}
            lv = max(0.0, min(1.0, float(level)))
            self._mouth_open = lv
            return {"ok": True, "mouth_open": lv}
        except Exception as e:
            return {"ok": False, "error": f"set_mouth_open: {type(e).__name__}: {e}"}

    def blink(self) -> dict:
        """触发一次眨眼动画。"""
        try:
            if not self._model_path:
                return {"ok": False, "error": "模型未加载，无法触发眨眼"}
            self._blink_request_at = time.time()
            return {"ok": True, "at": self._blink_request_at}
        except Exception as e:
            return {"ok": False, "error": f"blink: {type(e).__name__}: {e}"}

    def set_eye_target(self, x: float, y: float) -> dict:
        """设置视线目标位置（x, y 归一化到 -1.0~1.0）。"""
        try:
            if not self._model_path:
                return {"ok": False, "error": "模型未加载，无法设置视线目标"}
            self._eye_x = max(-1.0, min(1.0, float(x)))
            self._eye_y = max(-1.0, min(1.0, float(y)))
            return {"ok": True, "x": self._eye_x, "y": self._eye_y}
        except Exception as e:
            return {"ok": False, "error": f"set_eye_target: {type(e).__name__}: {e}"}

    def get_animation_list(self) -> dict:
        """返回可用动画列表。"""
        try:
            if not self._model_path:
                return {"ok": False, "error": "模型未加载", "animations": []}
            actions = self.list_actions()
            builtin = [
                {"name": "idle", "label": "站立待机", "built_in": True},
                {"name": "wave", "label": "挥手", "built_in": True},
                {"name": "nod", "label": "点头", "built_in": True},
            ]
            return {"ok": True, "animations": builtin + [
                {"name": a["name"], "label": a["name"], "built_in": False,
                 "path": a["path"]} for a in actions
            ]}
        except Exception as e:
            return {"ok": False, "error": f"get_animation_list: {type(e).__name__}: {e}",
                    "animations": []}

    # ---------------- 汇总 ----------------
    def state(self) -> dict:
        return {
            "backend": "flutter(model_viewer_plus) + python(resource stage)",
            "note": "画面由 Flutter 渲染；后端只负责资源解析与状态维护",
            "models_dir": str(self.models_dir),
            "actions_dir": str(self.actions_dir),
            "model": self._model_path,
            "action": self._action_path,
            "model_count": len(self.list_models()),
            "action_count": len(self.list_actions()),
            "mouth_open": self._mouth_open,
            "eye_target": [self._eye_x, self._eye_y],
            "blink_request_at": self._blink_request_at,
        }


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"
