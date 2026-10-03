#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.vrma —— VRMA 动作文件（VRM Animation）解析与重定向播放

VRMA 是"带人形骨骼映射的 glTF 动画"：任何 VRM 都能播放任何 VRMA。
本模块纯 Python 实现（等价于 @pixiv/three-vrm-animation 的核心逻辑）：

  1. 读 VRMA 的 `extensions.VRMC_vrm_animation.humanoid.humanBones` → 骨名到节点映射
  2. 把每条动画通道按骨名重定向到目标 VRM 的骨骼节点
  3. 旋转直接作为局部旋转写入（与官方实现一致）；
     髋部位移按"目标髋高 / 源髋高"缩放并补偿静止偏移
  4. 表情通道 → BlendShape 权重
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from renderer.gltf import GLTF, normalize_quat, trs_matrix


def qmul(a, b):
    """四元数乘法 a*b（与 three.js 的 multiply 同序）。"""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz], np.float32)


def qinv(q):
    q = np.asarray(q, np.float32)
    n = float(np.dot(q, q))
    if n < 1e-12:
        return np.array([0, 0, 0, 1], np.float32)
    return np.array([-q[0], -q[1], -q[2], q[3]], np.float32) / n


def _slerp(q0, q1, t):
    q0 = normalize_quat(q0)
    q1 = normalize_quat(q1)
    d = float(np.dot(q0, q1))
    if d < 0:
        q1, d = -q1, -d
    if d > 0.9995:
        return normalize_quat(q0 + (q1 - q0) * t)
    th0 = math.acos(max(-1.0, min(1.0, d)))
    th = th0 * t
    s0 = math.sin(th0 - th) / math.sin(th0)
    s1 = math.sin(th) / math.sin(th0)
    return normalize_quat(q0 * s0 + q1 * s1)


def _sample(times, values, t, is_quat=False, interpolation='LINEAR'):
    n = len(times)
    if n == 0:
        return None
    if t <= times[0]:
        return values[0].copy()
    if t >= times[-1]:
        return values[-1].copy()
    i = int(np.searchsorted(times, t, side='right') - 1)
    i = max(0, min(i, n - 2))
    if interpolation == 'STEP':
        return values[i].copy()
    span = float(times[i + 1] - times[i])
    a = 0.0 if span <= 1e-9 else (t - times[i]) / span
    if is_quat:
        return _slerp(values[i], values[i + 1], a)
    return values[i] * (1.0 - a) + values[i + 1] * a


class AnimationClip:
    """已重定向到目标模型的动画片段。"""

    def __init__(self, name, tracks, duration, expression_tracks=None, source=None):
        self.name = name
        self.tracks = tracks
        self.duration = max(duration, 1e-3)
        self.expression_tracks = expression_tracks or {}
        self.source = source

    def apply(self, pose, time: float, loop=True):
        t = time % self.duration if loop else min(time, self.duration)
        for node, tr in self.tracks.items():
            if 'rotation' in tr:
                q = _sample(tr['rotation'][0], tr['rotation'][1], t, is_quat=True,
                            interpolation=tr.get('interp_rot', 'LINEAR'))
                if q is not None:
                    pose.rotation[node] = normalize_quat(q)
            if 'translation' in tr:
                v = _sample(tr['translation'][0], tr['translation'][1], t,
                            interpolation=tr.get('interp_trans', 'LINEAR'))
                if v is not None:
                    pose.translation[node] = np.asarray(v, np.float32)
        pose._dirty = True
        return t

    def expression_weights(self, time: float, loop=True) -> dict:
        t = time % self.duration if loop else min(time, self.duration)
        out = {}
        for name, (times, vals) in self.expression_tracks.items():
            w = _sample(times, vals, t)
            if w is not None:
                out[name] = float(w)
        return out


class VRMAFile:
    """一个 .vrma 文件。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.gltf = GLTF(path)
        ext = ((self.gltf.json.get('extensions') or {}).get('VRMC_vrm_animation', {}) or {})
        hum = ((ext.get('humanoid') or {}).get('humanBones') or {})
        self.bone_to_node = {}
        for bone, info in hum.items():
            if isinstance(info, dict) and 'node' in info:
                self.bone_to_node[bone] = int(info['node'])
        self.node_to_bone = {v: k for k, v in self.bone_to_node.items()}
        self.expression_nodes = {}
        for name, info in ((ext.get('expressions') or {}) or {}).items():
            if isinstance(info, dict) and 'node' in info:
                self.expression_nodes[int(info['node'])] = name
        self.name = self.path.stem
        self._src_hips_height = self._compute_source_hips_height()

    def _compute_source_hips_height(self) -> float:
        parents = self.gltf.node_parents()
        node = self.bone_to_node.get('hips')
        if node is None:
            return 1.0
        chain, cur = [], node
        while cur >= 0:
            chain.append(cur)
            cur = parents[cur]
        m = np.eye(4, dtype=np.float32)
        for cur in reversed(chain):
            n = self.gltf.nodes[cur]
            m = m @ trs_matrix(n.get('translation', (0, 0, 0)),
                               n.get('rotation', (0, 0, 0, 1)),
                               n.get('scale', (1, 1, 1)))
        return float(m[1, 3]) or 1.0

    def clip(self, model, animation_index: int = 0, scale_root: bool = True) -> AnimationClip | None:
        anims = self.gltf.animations
        if not anims or animation_index >= len(anims):
            return None
        anim = anims[animation_index]
        tracks: dict[int, dict] = {}
        duration = 0.0
        ex_tracks: dict[str, tuple] = {}
        hips_scale = 1.0
        if scale_root and self._src_hips_height > 1e-4:
            hips_scale = float(model.hips_height / self._src_hips_height)
        src_node_of = dict(self.bone_to_node)          # 骨名 → VRMA 源节点
        src_hips = self.bone_to_node.get('hips')
        tgt_hips = model.humanoid.get('hips')
        tgt_hips_rest = (np.array(model.nodes[tgt_hips].get('translation', [0, 0, 0]), np.float32)
                         if tgt_hips is not None else None)
        src_hips_rest = (np.array(self.gltf.nodes[src_hips].get('translation', [0, 0, 0]), np.float32)
                         if src_hips is not None else None)

        for ch in anim.get('channels', []):
            tgt = ch.get('target', {})
            node = tgt.get('node')
            path = tgt.get('path')
            if node is None or path not in ('rotation', 'translation', 'scale'):
                continue
            smp = anim['samplers'][ch['sampler']]
            times = self.gltf.accessor(smp['input']).astype(np.float32)
            values = self.gltf.accessor(smp['output']).astype(np.float32)
            interp = smp.get('interpolation', 'LINEAR')
            if len(times):
                duration = max(duration, float(times[-1]))

            expr_name = self.expression_nodes.get(node)
            if expr_name is not None and path == 'translation':
                ex_tracks[expr_name] = (times, values[:, 1] if values.ndim > 1 else values)
                continue

            bone = self.node_to_bone.get(node)
            if bone is None:
                continue
            tgt_node = model.humanoid.get(bone)
            if tgt_node is None:
                continue
            tr = tracks.setdefault(tgt_node, {})
            if path == 'rotation':
                # 重定向公式（父坐标系增量法，48 个动作实测最稳）：
                #   源骨骼静止 rs、目标骨骼静止 rt
                #   增量（表达在父坐标系）= R_source(t) · rs⁻¹
                #   目标局部旋转        = Δ · rt
                # 这样既不吃 VRMA 源骨架的静止朝向差异，也不吃目标模型的静止朝向差异。
                rest_local = normalize_quat(model.nodes[tgt_node].get('rotation', (0, 0, 0, 1)))
                src_node = src_node_of.get(bone)
                src_rest = (normalize_quat(self.gltf.nodes[src_node].get('rotation', (0, 0, 0, 1)))
                            if src_node is not None else np.array([0, 0, 0, 1], np.float32))
                srci = qinv(src_rest)
                conv = (np.stack([qmul(qmul(normalize_quat(v), srci), rest_local)
                                  for v in values])
                        if len(values) else values)
                tr['rotation'] = (times, conv.astype(np.float32))
                tr['interp_rot'] = interp
            elif path == 'translation':
                v = values.reshape(-1, 3).copy()
                if node == src_hips and src_hips_rest is not None and tgt_hips_rest is not None:
                    v = tgt_hips_rest[None, :] + (v - src_hips_rest[None, :]) * hips_scale
                tr['translation'] = (times, v)
                tr['interp_trans'] = interp
            elif path == 'scale' and node == src_hips:
                tr['scale'] = (times, values.reshape(-1, 3).copy())
        return AnimationClip(self.name, tracks, duration, ex_tracks, source=str(self.path))

    def summary(self) -> dict:
        return {'file': self.path.name, 'bones': len(self.bone_to_node),
                'animations': len(self.gltf.animations),
                'channels': sum(len(a.get('channels', [])) for a in self.gltf.animations),
                'source_hips_height': round(self._src_hips_height, 3)}
