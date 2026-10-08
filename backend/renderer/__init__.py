# -*- coding: utf-8 -*-
"""小凌 · 3D 渲染层（资源与状态）

分工：
    画面渲染  → Flutter 端（model_viewer_plus，基于 WebView2）
    资源/状态 → 本模块（VRM 解析、动作库、当前模型与动作状态）

对外暴露 `Renderer`，其接口与 `server._get_renderer()` 的调用契约一致：
    switch_model(path) / play_action(path) / list_models() / list_actions()
"""
from __future__ import annotations

from .stage import Stage, MODEL_EXTS, ACTION_EXTS  # noqa: F401

__all__ = ["Stage", "Renderer", "MODEL_EXTS", "ACTION_EXTS"]

_singleton: "Renderer | None" = None


class Renderer:
    """渲染器门面：把 Stage 包装成 server 期望的接口。"""

    def __init__(self):
        self.stage = Stage()

    # ---- server.py 调用契约 ----
    def switch_model(self, path: str) -> dict:
        return self.stage.switch_model(path)

    def play_action(self, path: str) -> dict:
        return self.stage.play_action(path)

    def list_models(self) -> list:
        return self.stage.list_models()

    def list_actions(self) -> list:
        return self.stage.list_actions()

    # ---- 附加能力 ----
    def describe_model(self, path: str) -> dict:
        return self.stage.describe_model(path)

    def state(self) -> dict:
        return self.stage.state()

    @property
    def model_path(self) -> str:
        return self.stage.model_path

    @property
    def action_path(self) -> str:
        return self.stage.action_path


def get_renderer() -> Renderer:
    """获取全局渲染器实例（惰性创建，复用同一份状态）。"""
    global _singleton
    if _singleton is None:
        _singleton = Renderer()
    return _singleton
