#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.gltf —— 纯 Python 的 glTF 2.0 / VRM 二进制解析层

不依赖 node/three.js：直接读 .glb/.vrm 的 JSON+BIN 块，按需求取出
accessor（顶点/法线/UV/骨骼权重/索引/动画采样）、bufferView、图像、节点与材质。

* 支持带 byteStride 的交错缓冲
* 支持稀疏 accessor（VRM 导出常见）
* 图像用 Pillow 解码为 numpy（供软件/GPU 两条渲染路径共用）
"""
from __future__ import annotations

import io
import json
import os
import struct
from pathlib import Path

import numpy as np
from PIL import Image

# 贴图上限：手机端（内存紧张、画面又小）可把它调小，例如 XIAOLING_TEXTURE_MAX=384
TEXTURE_MAX = int(os.environ.get('XIAOLING_TEXTURE_MAX', '0') or 0)

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942

COMPONENT_DTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16,
                   5125: np.uint32, 5126: np.float32}
TYPE_COMPONENTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4,
                   'MAT2': 4, 'MAT3': 9, 'MAT4': 16}


class GLTF:
    """一个 glTF/VRM 文件。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        if len(raw) < 12 or struct.unpack('<I', raw[:4])[0] != GLB_MAGIC:
            raise ValueError(f'不是 GLB/VRM 文件：{path}')
        _magic, _ver, _length = struct.unpack('<III', raw[:12])
        off, self.json, self.bin = 12, None, b''
        while off < len(raw):
            clen, ctype = struct.unpack('<II', raw[off:off + 8])
            off += 8
            chunk = raw[off:off + clen]
            off += clen
            if ctype == CHUNK_JSON:
                self.json = json.loads(chunk.decode('utf-8'))
            elif ctype == CHUNK_BIN:
                self.bin = chunk
        if self.json is None:
            raise ValueError('缺少 JSON 块')
        self._img_cache: dict[int, np.ndarray] = {}

    # ------------------------------------------------------------------ 基础
    @property
    def nodes(self):
        return self.json.get('nodes', [])

    @property
    def meshes(self):
        return self.json.get('meshes', [])

    @property
    def materials(self):
        return self.json.get('materials', [])

    @property
    def skins(self):
        return self.json.get('skins', [])

    @property
    def animations(self):
        return self.json.get('animations', [])

    def vrm_ext(self) -> dict:
        return (self.json.get('extensions') or {}).get('VRM', {}) or {}

    def node_parents(self):
        parents = [-1] * len(self.nodes)
        for i, n in enumerate(self.nodes):
            for c in n.get('children', []):
                parents[c] = i
        return parents

    # --------------------------------------------------------------- accessor
    def accessor(self, index: int) -> np.ndarray:
        a = self.json['accessors'][index]
        n = a['count']
        ncomp = TYPE_COMPONENTS[a['type']]
        dt = COMPONENT_DTYPE[a['componentType']]
        if 'bufferView' in a:
            bv = self.json['bufferViews'][a['bufferView']]
            item = np.dtype(dt).itemsize * ncomp
            stride = bv.get('byteStride') or item
            base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
            if stride == item:
                arr = np.frombuffer(self.bin, dtype=dt, count=n * ncomp, offset=base)
                out = arr.reshape(n, ncomp).astype(np.float32 if dt is np.float32 else dt)
            else:
                out = np.stack([np.frombuffer(self.bin, dtype=dt, count=ncomp,
                                              offset=base + i * stride) for i in range(n)])
        else:
            out = np.zeros((n, ncomp), dtype=dt)
        if 'sparse' in a:                       # 稀疏覆盖（VRM 导出常见）
            sp = a['sparse']
            cnt = sp['count']
            ibv = self.json['bufferViews'][sp['indices']['bufferView']]
            idt = COMPONENT_DTYPE[sp['indices']['componentType']]
            ioff = ibv.get('byteOffset', 0) + sp['indices'].get('byteOffset', 0)
            idx = np.frombuffer(self.bin, dtype=idt, count=cnt, offset=ioff).astype(np.int64)
            vbv = self.json['bufferViews'][sp['values']['bufferView']]
            voff = vbv.get('byteOffset', 0) + sp['values'].get('byteOffset', 0)
            vals = np.frombuffer(self.bin, dtype=dt, count=cnt * ncomp, offset=voff).reshape(cnt, ncomp)
            out = np.array(out)
            out[idx] = vals
        return out if ncomp > 1 else out.reshape(-1)

    # ------------------------------------------------------------------ 图像
    def image(self, image_index: int) -> np.ndarray:
        """返回 RGBA uint8 (H, W, 4)。"""
        if image_index in self._img_cache:
            return self._img_cache[image_index]
        im = self.json['images'][image_index]
        if 'bufferView' in im:
            bv = self.json['bufferViews'][im['bufferView']]
            s = bv.get('byteOffset', 0)
            data = self.bin[s:s + bv['byteLength']]
        else:
            data = Path(str(im.get('uri', ''))).read_bytes()
        img = Image.open(io.BytesIO(data)).convert('RGBA')
        if TEXTURE_MAX and max(img.size) > TEXTURE_MAX:      # 手机端降采样，省内存
            r = TEXTURE_MAX / max(img.size)
            img = img.resize((max(int(img.width * r), 4), max(int(img.height * r), 4)),
                             Image.BILINEAR)
        arr = np.asarray(img)
        self._img_cache[image_index] = arr
        return arr

    def texture_image(self, texture_index: int) -> np.ndarray | None:
        src = self.json['textures'][texture_index].get('source')
        return None if src is None else self.image(src)

    # ------------------------------------------------------------------ 材质
    def material_texture(self, material: dict, slot: str) -> np.ndarray | None:
        pbr = material.get('pbrMetallicRoughness', {})
        tex = pbr.get(slot) or (material.get(slot) if slot != 'baseColorTexture' else None)
        if not tex:
            return None
        return self.texture_image(tex['index'])

    def material_color(self, material: dict) -> np.ndarray:
        pbr = material.get('pbrMetallicRoughness', {})
        return np.array(pbr.get('baseColorFactor', [1, 1, 1, 1]), dtype=np.float32)

    def material_shade(self, material: dict) -> np.ndarray:
        """MToon 阴影色（VRM 0.x materialProperties），没有就取基色 0.86 倍。"""
        name = material.get('name', '')
        for mp in self.vrm_ext().get('materialProperties', []):
            if mp.get('name') == name:
                sc = mp.get('shadeColorFactor')
                if sc:
                    return np.array(sc, dtype=np.float32)
        return self.material_color(material)[:3] * 0.86


# --------------------------------------------------------------------- 矩阵
def trs_matrix(translation=(0, 0, 0), rotation=(0, 0, 0, 1), scale=(1, 1, 1)) -> np.ndarray:
    """T*R*S → 4x4（列主序语意的标准行主序矩阵）。"""
    x, y, z, w = rotation
    n = x * x + y * y + z * z + w * w
    if n < 1e-12:
        x, y, z, w = 0.0, 0.0, 0.0, 1.0
        n = 1.0
    s = 2.0 / n
    xx, yy, zz = x * x * s, y * y * s, z * z * s
    xy, xz, yz = x * y * s, x * z * s, y * z * s
    wx, wy, wz = w * x * s, w * y * s, w * z * s
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = 1 - (yy + zz); m[0, 1] = xy - wz;        m[0, 2] = xz + wy
    m[1, 0] = xy + wz;       m[1, 1] = 1 - (xx + zz);  m[1, 2] = yz - wx
    m[2, 0] = xz - wy;       m[2, 1] = yz + wx;        m[2, 2] = 1 - (xx + yy)
    m[:3, 0] *= scale[0]; m[:3, 1] *= scale[1]; m[:3, 2] *= scale[2]
    m[:3, 3] = translation
    return m


def node_local_matrix(node: dict) -> np.ndarray:
    if 'matrix' in node:
        return np.array(node['matrix'], dtype=np.float32).reshape(4, 4).T
    return trs_matrix(node.get('translation', (0, 0, 0)),
                      node.get('rotation', (0, 0, 0, 1)),
                      node.get('scale', (1, 1, 1)))


def quat_to_mat3(q) -> np.ndarray:
    return trs_matrix(rotation=q)[:3, :3]


def normalize_quat(q) -> np.ndarray:
    q = np.asarray(q, dtype=np.float32)
    n = float(np.linalg.norm(q))
    return q / n if n > 1e-8 else np.array([0, 0, 0, 1], dtype=np.float32)
