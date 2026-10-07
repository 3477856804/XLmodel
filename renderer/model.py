#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.model —— VRM 语义层（人形骨骼 / 表情 / 弹簧骨 / 材质 / 可渲染图元）

把 glTF 的"通用数据"提升为"角色数据"，供 pose.py（变形）与两条渲染后端共用。
纯 Python（numpy + Pillow）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from renderer.gltf import GLTF, node_local_matrix

def vec3(v, default=(0.0, 0.0, 0.0)) -> np.ndarray:
    """VRM 0.x 里向量既可能是 [x,y,z]，也可能是 {"x":..,"y":..,"z":..}。"""
    if isinstance(v, dict):
        return np.array([float(v.get('x', 0)), float(v.get('y', 0)), float(v.get('z', 0))],
                        dtype=np.float32)
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        return np.array(v[:3], dtype=np.float32)
    return np.array(default, dtype=np.float32)


BONE_ALIASES = {
    'hips': 'hips', 'spine': 'spine', 'chest': 'chest', 'upperChest': 'upper_chest',
    'neck': 'neck', 'head': 'head', 'leftShoulder': 'left_shoulder',
    'rightShoulder': 'right_shoulder', 'leftUpperArm': 'left_upper_arm',
    'rightUpperArm': 'right_upper_arm', 'leftLowerArm': 'left_lower_arm',
    'rightLowerArm': 'right_lower_arm', 'leftHand': 'left_hand', 'rightHand': 'right_hand',
    'leftUpperLeg': 'left_upper_leg', 'rightUpperLeg': 'right_upper_leg',
    'leftLowerLeg': 'left_lower_leg', 'rightLowerLeg': 'right_lower_leg',
    'leftFoot': 'left_foot', 'rightFoot': 'right_foot', 'leftToes': 'left_toes',
    'rightToes': 'right_toes', 'leftEye': 'left_eye', 'rightEye': 'right_eye',
    'jaw': 'jaw',
}


@dataclass
class Material:
    index: int
    name: str
    color: np.ndarray                      # (4,) 线性基色
    shade: np.ndarray                      # (3,) 阴影色
    texture: np.ndarray | None             # (H,W,4) uint8
    alpha_mode: str = 'OPAQUE'
    cutoff: float = 0.5
    double_sided: bool = False
    unlit: bool = True
    emissive: np.ndarray = field(default_factory=lambda: np.zeros(3, np.float32))


@dataclass
class Primitive:
    index: int
    mesh_index: int
    material: int
    positions: np.ndarray                  # (N,3)
    normals: np.ndarray                    # (N,3)
    uvs: np.ndarray                        # (N,2)
    indices: np.ndarray                    # (M,3) int32
    joints: np.ndarray | None              # (N,4) int32（skin.joints 下标）
    weights: np.ndarray | None             # (N,4) float32
    morphs: list = field(default_factory=list)   # [(dpos (N,3), dnrm (N,3) 或 None)]
    skin_index: int = 0                   # 关联的 skin（从 node.skin 读取）


class VRMModel:
    """加载后的 VRM（含人形骨骼映射 / 表情 / 弹簧骨）。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.gltf = GLTF(path)
        g = self.gltf
        self.nodes = g.nodes
        self.parents = g.node_parents()
        self.name = (g.vrm_ext().get('meta', {}) or {}).get('title') or self.path.stem
        self.rest_local = [node_local_matrix(n) for n in self.nodes]
        self.rest_world = self._compute_rest_world()

        # ---- 材质 ----
        self.materials: list[Material] = []
        for i, m in enumerate(g.materials):
            pbr = m.get('pbrMetallicRoughness', {})
            self.materials.append(Material(
                index=i, name=m.get('name', f'mat{i}'),
                color=g.material_color(m), shade=g.material_shade(m),
                texture=g.material_texture(m, 'baseColorTexture'),
                alpha_mode=m.get('alphaMode', 'OPAQUE'), cutoff=float(m.get('alphaCutoff', 0.5)),
                double_sided=bool(m.get('doubleSided', False)),
                unlit='KHR_materials_unlit' in (m.get('extensions') or {}),
                emissive=np.array(m.get('emissiveFactor', [0, 0, 0]), dtype=np.float32)))

        # ---- 图元 ----
        # 先建立 mesh_index -> skin_index 映射（从 node.skin 读取）
        mesh_skin = {}
        for node in g.nodes:
            mi = node.get('mesh')
            if mi is not None and 'skin' in node:
                mesh_skin[mi] = node['skin']

        self.primitives: list[Primitive] = []
        for mi, mesh in enumerate(g.meshes):
            skin_idx = mesh_skin.get(mi, 0)
            for pi, p in enumerate(mesh.get('primitives', [])):
                at = p['attributes']
                pos = g.accessor(at['POSITION']).astype(np.float32)
                nrm = (g.accessor(at['NORMAL']).astype(np.float32)
                       if 'NORMAL' in at else np.zeros_like(pos))
                uvs = (g.accessor(at['TEXCOORD_0']).astype(np.float32)
                       if 'TEXCOORD_0' in at else np.zeros((len(pos), 2), np.float32))
                idx = (g.accessor(p['indices']).astype(np.int32)
                       if 'indices' in p else np.arange(len(pos), dtype=np.int32))
                joints = weights = None
                if 'JOINTS_0' in at:
                    joints = g.accessor(at['JOINTS_0']).astype(np.int32).reshape(-1, 4)
                if 'WEIGHTS_0' in at:
                    weights = g.accessor(at['WEIGHTS_0']).astype(np.float32).reshape(-1, 4)
                morphs = []
                for tgt in p.get('targets', []) or []:
                    dp = (g.accessor(tgt['POSITION']).astype(np.float32)
                          if 'POSITION' in tgt else None)
                    dn = (g.accessor(tgt['NORMAL']).astype(np.float32)
                          if 'NORMAL' in tgt else None)
                    morphs.append((dp, dn))
                self.primitives.append(Primitive(
                    index=len(self.primitives), mesh_index=mi, material=p.get('material', -1),
                    skin_index=skin_idx,
                    positions=pos, normals=nrm, uvs=uvs,
                    indices=idx.reshape(-1, 3).astype(np.int32), joints=joints, weights=weights,
                    morphs=morphs))

        # ---- 人形骨骼 ----
        vrm = g.vrm_ext()
        self.humanoid: dict[str, int] = {}
        for b in (vrm.get('humanoid', {}) or {}).get('humanBones', []):
            self.humanoid[b['bone']] = b['node']
        self.bone_of_node = {v: k for k, v in self.humanoid.items()}
        self.hips_height = float(self.rest_world[self.humanoid['hips']][1, 3]) \
            if 'hips' in self.humanoid else 0.9

        # ---- 表情（BlendShape 组） ----
        self.expressions: dict[str, list[tuple[int, int, float]]] = {}
        for grp in (vrm.get('blendShapeMaster', {}) or {}).get('blendShapeGroups', []):
            name = grp.get('presetName') or grp.get('name')
            binds = []
            for b in grp.get('binds', []) or []:
                mesh_i, tgt_i = int(b.get('mesh', 0)), int(b.get('index', 0))
                w = float(b.get('weight', 100)) / 100.0
                for prim in self.primitives:
                    if prim.mesh_index == mesh_i and tgt_i < len(prim.morphs):
                        binds.append((prim.index, tgt_i, w))
            if binds:
                self.expressions[name] = binds

        # ---- 弹簧骨 ----
        self.spring_groups = []
        for grp in (vrm.get('secondaryAnimation', {}) or {}).get('boneGroups', []):
            bones = [int(b) for b in grp.get('bones', [])]
            if not bones:
                continue
            self.spring_groups.append({
                'name': grp.get('comment', 'ch'), 'bones': bones,
                'stiffness': float(grp.get('stiffiness', 1.0)),
                'drag': float(grp.get('dragForce', 0.4)),
                'gravity': float(grp.get('gravityPower', 0.0)),
                'gravity_dir': vec3(grp.get('gravityDir', [0, -1, 0]), (0, -1, 0)),
                'hit_radius': float(grp.get('hitRadius', 0.0)),
            })

        # ---- 皮肤 ----
        self.skins = []
        for s in self.gltf.skins:
            # glTF 的矩阵是列主序存储 → 读出来要转置才是数学意义上的矩阵
            ibm = (g.accessor(s['inverseBindMatrices']).astype(np.float32)
                   .reshape(-1, 4, 4).transpose(0, 2, 1)
                   if 'inverseBindMatrices' in s else None)
            self.skins.append({'joints': list(s['joints']), 'ibm': ibm})

        # ---- 包围盒 ----
        allpos = np.concatenate([p.positions for p in self.primitives])
        self.bbox_min = allpos.min(0)
        self.bbox_max = allpos.max(0)
        # 朝向：VRM 0.x 面向 +Z（three 惯例为 -Z，Python 渲染器直接用 +Z 正对镜头）
        self.meta = dict(vrm.get('meta', {}) or {})

    # ------------------------------------------------------------------ 工具
    def _compute_rest_world(self):
        n = len(self.nodes)
        world = [None] * n
        order = self._topo_order()
        for i in order:
            local = self.rest_local[i]
            p = self.parents[i]
            world[i] = local if p < 0 else world[p] @ local
        return world

    def _topo_order(self):
        order, seen = [], [False] * len(self.nodes)

        def visit(i):
            if seen[i]:
                return
            seen[i] = True
            p = self.parents[i]
            if p >= 0:
                visit(p)
            order.append(i)
        for i in range(len(self.nodes)):
            visit(i)
        return order

    def node_bone(self, node_index: int) -> str | None:
        return self.bone_of_node.get(node_index)

    def find_material(self, name: str) -> Material | None:
        for m in self.materials:
            if m.name == name:
                return m
        return None

    def triangle_count(self) -> int:
        return int(sum(len(p.indices) for p in self.primitives))

    def vertex_count(self) -> int:
        return int(sum(len(p.positions) for p in self.primitives))

    def summary(self) -> dict:
        return {'name': self.name, 'path': str(self.path),
                'bones': len(self.humanoid), 'expressions': sorted(self.expressions.keys()),
                'spring_groups': len(self.spring_groups), 'materials': len(self.materials),
                'primitives': len(self.primitives), 'triangles': self.triangle_count(),
                'vertices': self.vertex_count(),
                'height': round(float(self.bbox_max[1] - self.bbox_min[1]), 3),
                'license': self.meta.get('licenseName', '')}

    # ------------------------------------------------------- 表情权重（0..1）
    def expression_names(self) -> list[str]:
        return sorted(self.expressions.keys())

    def preset_of(self, key: str) -> str | None:
        low = key.lower().replace('_', '').replace('-', '')
        table = {'blink': 'Blink', 'blink_l': 'Blink_L', 'blink_r': 'Blink_R',
                 'happy': 'Joy', 'joy': 'Joy', 'fun': 'Fun', 'angry': 'Angry',
                 'angry': 'Angry', 'sad': 'Sorrow', 'sorrow': 'Sorrow',
                 'surprised': 'Surprised', 'aa': 'A', 'ih': 'I', 'ou': 'U',
                 'ee': 'E', 'oh': 'O', 'relaxed': 'Neutral'}
        want = table.get(low, key)
        for name in self.expressions:
            if name.lower() == want.lower():
                return name
        return None
