#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.camera —— 相机与投影（纯 numpy，供 GL / 软件两条路径共用）"""
from __future__ import annotations

import math

import numpy as np


def perspective(fovy_rad: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / math.tan(fovy_rad / 2)
    m = np.zeros((4, 4), np.float32)
    m[0, 0] = f / max(aspect, 1e-6)
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye, target, up=(0, 1, 0)) -> np.ndarray:
    eye = np.asarray(eye, np.float32)
    target = np.asarray(target, np.float32)
    up = np.asarray(up, np.float32)
    f = target - eye
    f = f / max(float(np.linalg.norm(f)), 1e-8)
    s = np.cross(f, up)
    s = s / max(float(np.linalg.norm(s)), 1e-8)
    u = np.cross(s, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


class OrbitCamera:
    """围绕角色头部/全身的固定机位（桌宠视角）。"""

    def __init__(self, model_height=1.5, focus='bust', fov_deg=20.0):
        self.model_height = model_height
        self.focus = focus
        self.fov = math.radians(fov_deg)
        self.yaw = 0.0
        self.pitch = 2.0
        self.zoom = 1.0
        self._target = np.array([0.0, model_height * 0.78, 0.0], np.float32)
        self._dist = 2.2
        self.update()

    def set_focus(self, focus: str):
        self.focus = 'full' if focus == 'full' else 'bust'
        self.update()

    def update(self):
        h = self.model_height
        if self.focus == 'full':
            center_y, span = h * 0.5, h * 1.06
        else:
            center_y, span = h - 0.26, 0.56
        self._target = np.array([0.0, center_y, 0.0], np.float32)
        self._dist = (span / max(self.zoom, 0.05)) / (2 * math.tan(self.fov / 2)) * 1.12

    @property
    def target(self):
        return self._target

    def _dir(self):
        # yaw=0 → 相机在 -Z 侧：VRM 0.x 模型（UniGLTF 导出）正面朝 -Z，
        # 这样默认机位正对角色（与官方 three-vrm 的 rotateVRM0 结论一致）
        yr, pr = math.radians(self.yaw), math.radians(self.pitch)
        return np.array([-math.sin(yr) * math.cos(pr), math.sin(pr),
                         -math.cos(yr) * math.cos(pr)], np.float32)

    def view_proj(self, aspect: float) -> np.ndarray:
        eye = self._target + self._dir() * self._dist
        proj = perspective(self.fov, aspect, 0.05, 50.0)
        return proj @ look_at(eye, self._target)

    def eye(self):
        return self._target + self._dir() * self._dist
