#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.pose —— 姿势 / 蒙皮 / 表情形变 / 弹簧骨（纯 Python + numpy）

这是"变形管线"：把骨骼姿势变成顶点位置，两条渲染后端（GPU / 软件）共用同一份结果。
"""
from __future__ import annotations

import numpy as np

from renderer.gltf import normalize_quat, quat_to_mat3, trs_matrix


class Pose:
    """一颗骨架的姿势（局部 TRS 覆盖 + 世界矩阵）。"""

    def __init__(self, model):
        self.model = model
        self.n = len(model.nodes)
        self.translation = [np.array(model.nodes[i].get('translation', [0, 0, 0]), np.float32)
                            for i in range(self.n)]
        self.rotation = [normalize_quat(model.nodes[i].get('rotation', [0, 0, 0, 1]))
                         for i in range(self.n)]
        self.scale = [np.array(model.nodes[i].get('scale', [1, 1, 1]), np.float32)
                      for i in range(self.n)]
        self.world = [m.copy() for m in model.rest_world]
        self.order = model._topo_order()
        self._dirty = True

    # -------------------------------------------------------------- 姿势修改
    def reset(self):
        m = self.model
        for i in range(self.n):
            self.translation[i] = np.array(m.nodes[i].get('translation', [0, 0, 0]), np.float32)
            self.rotation[i] = normalize_quat(m.nodes[i].get('rotation', [0, 0, 0, 1]))
            self.scale[i] = np.array(m.nodes[i].get('scale', [1, 1, 1]), np.float32)
        self._dirty = True

    def set_bone_rotation(self, bone: str, quat):
        node = self.model.humanoid.get(bone)
        if node is not None:
            self.rotation[node] = normalize_quat(quat)
            self._dirty = True

    def set_bone_translation(self, bone: str, vec):
        node = self.model.humanoid.get(bone)
        if node is not None:
            self.translation[node] = np.asarray(vec, np.float32)
            self._dirty = True

    def add_bone_rotation(self, bone: str, quat):
        node = self.model.humanoid.get(bone)
        if node is None:
            return
        q1 = self.rotation[node]
        q2 = normalize_quat(quat)
        # 四元数乘法 q1*q2
        x1, y1, z1, w1 = q1
        x2, y2, z2, w2 = q2
        self.rotation[node] = normalize_quat(np.array([
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2], np.float32))
        self._dirty = True

    # -------------------------------------------------------------- 世界矩阵
    def update_world(self, force=False):
        if not self._dirty and not force:
            return self.world
        for i in self.order:
            local = trs_matrix(self.translation[i], self.rotation[i], self.scale[i])
            p = self.model.parents[i]
            self.world[i] = local if p < 0 else self.world[p] @ local
        self._dirty = False
        return self.world

    def update_subtree(self, node: int):
        """只重算某节点及其子树的世界矩阵（弹簧骨逐骨更新时用，避免全树重算）。"""
        stack = [node]
        while stack:
            i = stack.pop()
            local = trs_matrix(self.translation[i], self.rotation[i], self.scale[i])
            p = self.model.parents[i]
            self.world[i] = local if p < 0 else self.world[p] @ local
            stack.extend(self.model.nodes[i].get('children', []))

    def bone_world(self, bone: str) -> np.ndarray | None:
        node = self.model.humanoid.get(bone)
        if node is None:
            return None
        self.update_world()
        return self.world[node]

    def bone_head(self, bone: str) -> np.ndarray | None:
        w = self.bone_world(bone)
        return None if w is None else w[:3, 3].copy()

    # -------------------------------------------------------------- 蒙皮矩阵
    def skin_matrices(self, skin_index: int, prim) -> np.ndarray | None:
        """返回 (N,4,4)：每个顶点直接用"加权后的蒙皮矩阵"，便于一次性变换。"""
        if prim.joints is None or prim.weights is None:
            return None
        self.update_world()
        skin = self.model.skins[skin_index] if skin_index < len(self.model.skins) else None
        if skin is None:
            return None
        joints = np.asarray(skin['joints'], np.int32)
        ibm = skin['ibm']
        mats = np.empty((len(joints), 4, 4), np.float32)
        for k, node in enumerate(joints):
            m = self.world[node] if node < len(self.world) else self.model.rest_world[node]
            mats[k] = m @ (ibm[k] if ibm is not None else np.eye(4, dtype=np.float32))
        j = prim.joints
        w = prim.weights
        valid = np.ones(len(j), bool)
        if len(joints):
            valid = (j < len(joints)).all(axis=1)
        picked = np.zeros((len(j), 4, 4, 4), np.float32)
        jj = np.clip(j, 0, max(len(joints) - 1, 0))
        for k in range(4):
            picked[:, k] = mats[jj[:, k]]
        weighted = (picked * w[:, :, None, None]).sum(axis=1)
        weighted[~valid] = np.eye(4, dtype=np.float32)
        return weighted


def apply_morphs(prim, weights: dict[int, float]):
    """按表情权重叠加形变目标：返回 (positions, normals)。"""
    pos = prim.positions
    nrm = prim.normals
    if not weights or not prim.morphs:
        return pos, nrm
    pos = pos.copy()
    nrm = nrm.copy()
    for tgt_i, w in weights.items():
        if w == 0 or tgt_i >= len(prim.morphs):
            continue
        dp, dn = prim.morphs[tgt_i]
        if dp is not None:
            pos += dp * w
        if dn is not None:
            nrm += dn * w
    return pos, nrm


def deform_primitive(prim, pose: Pose, skin_index: int = 0, morph_weights=None):
    """完整变形：形变目标 → 蒙皮 → 返回世界空间的 (positions, normals)。"""
    pos, nrm = apply_morphs(prim, morph_weights or {})
    actual_skin = getattr(prim, 'skin_index', skin_index)
    mats = pose.skin_matrices(actual_skin, prim)
    if mats is None:
        return pos, nrm
    n = len(pos)
    homo = np.concatenate([pos, np.ones((n, 1), np.float32)], axis=1)          # (N,4)
    out = np.einsum('nij,nj->ni', mats, homo)[:, :3]
    n3 = mats[:, :3, :3]
    normals = np.einsum('nij,nj->ni', n3, nrm)
    ln = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.maximum(ln, 1e-8)
    return out.astype(np.float32), normals.astype(np.float32)


class SpringBones:
    """VRM 0.x secondaryAnimation 的简化 Verlet 实现（头发 / 裙子摆动）。

    对每个骨链：用"目标方向（父骨旋转后的静止方向）+ 重力 + 阻尼 + 惯性"驱动摆动，
    再把结果写回姿势的四元数。数值稳定性优先（高阻尼 + 速度上限）。
    """

    def __init__(self, model):
        self.model = model
        self.chains = []
        for grp in model.spring_groups:
            bones = [b for b in grp['bones'] if b < len(model.nodes)]
            if not bones:
                continue
            rest_heads = [model.rest_world[b][:3, 3].copy() for b in bones]
            lengths = []
            for i, b in enumerate(bones):
                if i + 1 < len(bones):
                    lengths.append(float(np.linalg.norm(rest_heads[i + 1] - rest_heads[i])))
                else:
                    children = [c for c in model.nodes[b].get('children', [])]
                    if children:
                        lengths.append(float(np.linalg.norm(
                            np.array(model.nodes[children[0]].get('translation', [0, 0, 0])))))
                    else:
                        lengths.append(grp['hit_radius'] * 2 or 0.04)
            self.chains.append({'bones': bones, 'lengths': np.array(lengths, np.float32),
                                'tails': [h + np.array([0, -l, 0]) for h, l in zip(rest_heads, lengths)],
                                'prev': [h + np.array([0, -l, 0]) for h, l in zip(rest_heads, lengths)],
                                'group': grp, 'init': False})

    def reset(self):
        for ch in self.chains:
            ch['init'] = False

    def update(self, pose: Pose, dt: float = 1 / 30, wind=None):
        """推进一帧。wind: 世界空间外力（如风扇/风感），可省略。"""
        wind = np.zeros(3, np.float32) if wind is None else np.asarray(wind, np.float32)
        pose.update_world()
        for ch in self.chains:
            grp = ch['group']
            bones, lens = ch['bones'], ch['lengths']
            stiff = float(np.clip(grp['stiffness'] * 0.30, 0.02, 0.9))
            drag = float(np.clip(1.0 - grp['drag'] * 0.35, 0.40, 0.98))
            grav = grp['gravity_dir'] * grp['gravity'] * 0.20 + wind
            for i, node in enumerate(bones):
                if node >= len(pose.world):
                    continue
                head = pose.world[node][:3, 3].copy()
                rest_head = self.model.rest_world[node][:3, 3]
                parent = self.model.parents[node]
                rot_parent = (pose.world[parent][:3, :3] if parent >= 0
                              else np.eye(3, dtype=np.float32))
                # 静止状态下该骨"往下"的方向（指向子骨；末骨用长度兜底）
                if i + 1 < len(bones):
                    rest_off = self.model.rest_world[bones[i + 1]][:3, 3] - rest_head
                else:
                    rest_off = np.array([0.0, -float(lens[i]), 0.0], np.float32)
                target_tail = head + rot_parent @ rest_off
                if not ch['init']:
                    ch['tails'][i] = target_tail.copy()
                    ch['prev'][i] = target_tail.copy()
                vel = (ch['tails'][i] - ch['prev'][i]) * drag + grav * dt
                ch['prev'][i] = ch['tails'][i].copy()
                tail = ch['tails'][i] + vel + (target_tail - ch['tails'][i]) * stiff
                delta = tail - head
                ln = float(np.linalg.norm(delta))
                max_len = max(float(lens[i]) * 2.6, 0.02)
                if not np.isfinite(ln) or ln < 1e-6:
                    ch['tails'][i] = target_tail.copy()
                    continue
                delta = delta / ln * min(ln, max_len)
                ch['tails'][i] = head + delta
                # 让骨骼的局部 -Y 轴指向尾端：世界旋转对齐
                cur_world_rot = rot_parent @ quat_to_mat3(pose.rotation[node])
                cur_dir = cur_world_rot @ np.array([0, -1.0, 0], np.float32)
                align = _quat_between(cur_dir, delta)
                new_world_rot = quat_to_mat3(align) @ cur_world_rot
                pose.rotation[node] = _mat3_to_quat(
                    np.linalg.inv(rot_parent).astype(np.float32) @ new_world_rot)
                pose.update_subtree(node)
            ch['init'] = True

def _quat_between(a, b):
    a = a / max(float(np.linalg.norm(a)), 1e-8)
    b = b / max(float(np.linalg.norm(b)), 1e-8)
    d = float(np.clip(np.dot(a, b), -1, 1))
    if d > 0.99999:
        return np.array([0, 0, 0, 1], np.float32)
    if d < -0.99999:
        axis = np.cross(a, np.array([1, 0, 0], np.float32))
        if float(np.linalg.norm(axis)) < 1e-4:
            axis = np.cross(a, np.array([0, 1, 0], np.float32))
        axis /= max(float(np.linalg.norm(axis)), 1e-8)
        return np.array([axis[0], axis[1], axis[2], 0], np.float32)
    axis = np.cross(a, b)
    q = np.array([axis[0], axis[1], axis[2], 1 + d], np.float32)
    return normalize_quat(q)


def _mat3_to_quat(m):
    m = np.asarray(m, np.float32)
    t = float(np.trace(m))
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    return normalize_quat(np.array([x, y, z, w], np.float32))
