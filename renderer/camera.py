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
    """围绕角色头部/全身的固定机位（桌宠视角）。

    朝向约定：VRM 资产实测正面朝 +Z（与文件内眼骨位置一致），因此默认机位放在
    +Z 侧（front_yaw=180），保证打开就是正脸；相机 yaw 为绝对角度，可绕正脸旋转。
    取景按"头骨高度 + 包围盒"自适应：半身照居中于脸部、留足边距，全身照自动收紧。
    """

    def __init__(self, model_height=1.5, focus='bust', fov_deg=20.0,
                 front_yaw=180.0, bbox_min_y=0.0, head_y=None,
                 center_x=0.0, center_z=0.0):
        self.model_height = model_height
        self.focus = focus
        self.fov = math.radians(fov_deg)
        self.front_yaw = float(front_yaw)
        self.yaw = self.front_yaw
        self.pitch = 2.0
        self.zoom = 1.0
        self.bbox_min_y = float(bbox_min_y)
        # 头骨世界高度：没有 humanoid 数据时退回旧的经验值
        self.head_y = float(head_y) if head_y else model_height - 0.26
        self.center_x = float(center_x)
        self.center_z = float(center_z)
        self._target = np.array([self.center_x, model_height * 0.78, self.center_z], np.float32)
        self._dist = 2.2
        self.update()

    def set_focus(self, focus: str):
        self.focus = 'full' if focus == 'full' else 'bust'
        self.update()

    def update(self):
        h = self.model_height
        if self.focus == 'full':
            center_y = (self.bbox_min_y + h) / 2
            span = (h - self.bbox_min_y) * 1.12
        else:
            # 半身：以脸部为中心（眼/脸在头顶与下巴之间），跨度盖住头+一点肩膀
            top = max(h, self.head_y + 0.05)
            center_y = self.head_y + (top - self.head_y) * 0.55
            span = min(1.0, max(0.55, (top - self.head_y) * 2.4))
        self._target = np.array([self.center_x, center_y, self.center_z], np.float32)
        self._dist = (span / max(self.zoom, 0.05)) / (2 * math.tan(self.fov / 2)) * 1.28

    @property
    def target(self):
        return self._target

    def _dir(self):
        # yaw 为绝对角度；front_yaw 对准模型正面（VRM 资产正面朝 +Z → 机位在 +Z 侧）
        yr, pr = math.radians(self.yaw), math.radians(self.pitch)
        return np.array([-math.sin(yr) * math.cos(pr), math.sin(pr),
                         -math.cos(yr) * math.cos(pr)], np.float32)

    def view_proj(self, aspect: float) -> np.ndarray:
        eye = self._target + self._dir() * self._dist
        proj = perspective(self.fov, aspect, 0.05, 50.0)
        return proj @ look_at(eye, self._target)

    def eye(self):
        return self._target + self._dir() * self._dist
