# -*- coding: utf-8 -*-
"""vrm_lib —— VRM(glTF) 读写 / 纹理重绘 / 白裙生成 / 换脸 / 白丝 工具箱

纯 Python + numpy + Pillow 实现，不依赖 Blender / Unity / three.js。
用于把小玥的 VRM models改造成"小凌"形象：

    · 服装纯白化（保留褶皱明暗）
    · 腿部程序化绘制白色长袜（白丝）
    · 发色重染（银白发 → 小凌的浅亚麻金）
    · 瞳色重绘（→ 小凌的湛蓝眼）
    · 五官迁移（把 2D 立绘的眼睛/眉毛/嘴/腮红映射到 VRM 面部贴图）
    · 程序化生成白色连衣裙网格（自动蒙皮到 hips/spine/chest 骨骼）
    · 隐藏原配饰（兔耳/眼镜等）

作者：小凌项目组   协议：MIT
"""

import io
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

GLTF_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942

COMP_DTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
TYPE_N = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}


def _pad4(b, fill=b'\x00'):
    r = len(b) % 4
    return b if r == 0 else b + fill * (4 - r)


class VRM:
    """极简 VRM/glTF 编辑器（保留全部原始数据，仅替换需要改动的部分）。"""

    def __init__(self, path):
        self.path = Path(path)
        self.json, self.bin = self._read(self.path)
        self._img_cache = {}
        self._dirty_images = {}

    # ---------- 读写 ----------
    @staticmethod
    def _read(path):
        raw = Path(path).read_bytes()
        magic, ver, length = struct.unpack('<III', raw[:12])
        if magic != GLTF_MAGIC:
            raise ValueError(f'不是 glTF/VRM 文件: {path}')
        off, js, bin_ = 12, None, b''
        while off < len(raw):
            clen, ctype = struct.unpack('<II', raw[off:off + 8])
            off += 8
            chunk = raw[off:off + clen]
            off += clen
            if ctype == CHUNK_JSON:
                js = json.loads(chunk.decode('utf-8'))
            elif ctype == CHUNK_BIN:
                bin_ = chunk
        return js, bin_

    def save(self, path):
        js = self.json
        # 1) 重新拼接 BIN（镜像类 bufferView 用新图替换）
        views = js['bufferViews']
        chunks = []
        offset = 0
        for i, bv in enumerate(views):
            if i in self._dirty_images:
                data = self._dirty_images[i]
            else:
                s = bv.get('byteOffset', 0)
                data = self.bin[s:s + bv['byteLength']]
            chunks.append(data)
            bv['byteOffset'] = offset
            bv['byteLength'] = len(data)
            offset += len(_pad4(data))
        new_bin = b''.join(_pad4(c) for c in chunks)
        js['buffers'][0]['byteLength'] = len(new_bin)

        json_bytes = _pad4(json.dumps(js, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), b' ')
        bin_bytes = _pad4(new_bin)
        total = 12 + 8 + len(json_bytes) + (8 + len(bin_bytes) if bin_bytes else 0)
        out = io.BytesIO()
        out.write(struct.pack('<III', GLTF_MAGIC, 2, total))
        out.write(struct.pack('<II', len(json_bytes), CHUNK_JSON))
        out.write(json_bytes)
        if bin_bytes:
            out.write(struct.pack('<II', len(bin_bytes), CHUNK_BIN))
            out.write(bin_bytes)
        Path(path).write_bytes(out.getvalue())
        self.path = Path(path)
        return Path(path)

    # ---------- accessor / bufferView ----------
    def accessor(self, idx):
        a = self.json['accessors'][idx]
        bv = self.json['bufferViews'][a['bufferView']]
        dt = COMP_DTYPE[a['componentType']]
        n = TYPE_N[a['type']]
        item = np.dtype(dt).itemsize * n
        stride = bv.get('byteStride') or item
        base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        if stride == item:
            arr = np.frombuffer(self.bin, dtype=dt, count=a['count'] * n, offset=base)
            return arr.reshape(a['count'], n) if n > 1 else arr
        rows = [np.frombuffer(self.bin, dtype=dt, count=n, offset=base + i * stride) for i in range(a['count'])]
        return np.stack(rows)

    def add_accessor(self, array, comp_type, type_name, minmax=True, target=None):
        """把 numpy 数组追加进 BIN，返回 accessor 索引。"""
        arr = np.asarray(array)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        raw = _pad4(arr.astype(COMP_DTYPE[comp_type]).tobytes())
        offset = len(self.bin)
        self.bin = self.bin + raw
        bv = {'buffer': 0, 'byteOffset': offset, 'byteLength': len(raw)}
        if target:
            bv['target'] = target
        self.json['bufferViews'].append(bv)
        acc = {'bufferView': len(self.json['bufferViews']) - 1,
               'componentType': comp_type, 'count': int(arr.shape[0]), 'type': type_name}
        if minmax:
            acc['min'] = [float(x) for x in arr.min(0)]
            acc['max'] = [float(x) for x in arr.max(0)]
        self.json['accessors'].append(acc)
        return len(self.json['accessors']) - 1

    # ---------- 材质 / 网格 ----------
    def material(self, name):
        for i, m in enumerate(self.json.get('materials', [])):
            if m.get('name') == name:
                return i, m
        raise KeyError(name)

    def material_names(self):
        return [m.get('name') for m in self.json.get('materials', [])]

    def primitives_of_material(self, mat_name):
        mi = self.material(mat_name)[0]
        out = []
        for m_i, me in enumerate(self.json.get('meshes', [])):
            for p_i, p in enumerate(me['primitives']):
                if p.get('material') == mi:
                    out.append((m_i, p_i, p, me))
        return out

    def geometry(self, mat_name):
        """合并某材质所有图元 → (positions, uvs, normals, indices)"""
        pos, uv, nrm, idx = [], [], [], []
        base = 0
        for _mi, _pi, p, _me in self.primitives_of_material(mat_name):
            at = p['attributes']
            q = self.accessor(at['POSITION']).astype(np.float32)
            t = self.accessor(at['TEXCOORD_0']).astype(np.float32) if 'TEXCOORD_0' in at else np.zeros((len(q), 2), np.float32)
            n = self.accessor(at['NORMAL']).astype(np.float32) if 'NORMAL' in at else np.zeros_like(q)
            i = self.accessor(p['indices']).astype(np.int64) if 'indices' in p else np.arange(len(q))
            pos.append(q); uv.append(t); nrm.append(n); idx.append(i.reshape(-1, 3) + base)
            base += len(q)
        if not pos:
            raise KeyError(mat_name)
        return (np.concatenate(pos), np.concatenate(uv), np.concatenate(nrm),
                np.concatenate(idx) if idx else np.zeros((0, 3), np.int64))

    def all_geometry(self):
        pos, uv, idx, mat_of_tri = [], [], [], []
        base = 0
        for m_i, me in enumerate(self.json.get('meshes', [])):
            for p_i, p in enumerate(me['primitives']):
                at = p['attributes']
                q = self.accessor(at['POSITION']).astype(np.float32)
                t = self.accessor(at['TEXCOORD_0']).astype(np.float32) if 'TEXCOORD_0' in at else np.zeros((len(q), 2), np.float32)
                i = self.accessor(p['indices']).astype(np.int64) if 'indices' in p else np.arange(len(q))
                i = i.reshape(-1, 3)
                pos.append(q); uv.append(t); idx.append(i + base)
                mat_of_tri.append(np.full(len(i), p.get('material', -1)))
                base += len(q)
        return (np.concatenate(pos), np.concatenate(uv), np.concatenate(idx),
                np.concatenate(mat_of_tri))

    # ---------- 图像 ----------
    def image_index_of_texture(self, tex_index):
        return self.json['textures'][tex_index].get('source')

    def image(self, img_index, copy=True):
        """读取图像（优先返回本次会话中被改写过的版本）。"""
        bv_index = self.json['images'][img_index]['bufferView']
        if bv_index in self._dirty_images:
            pil = Image.open(io.BytesIO(self._dirty_images[bv_index])).convert('RGBA')
        else:
            if img_index not in self._img_cache:
                im = self.json['images'][img_index]
                bv = self.json['bufferViews'][im['bufferView']]
                s = bv.get('byteOffset', 0)
                self._img_cache[img_index] = Image.open(
                    io.BytesIO(self.bin[s:s + bv['byteLength']])).convert('RGBA')
            pil = self._img_cache[img_index]
        return pil.copy() if copy else pil

    def set_image(self, img_index, pil, mime='image/png'):
        buf = io.BytesIO()
        pil.convert('RGBA').save(buf, format='PNG', optimize=True)
        bv_index = self.json['images'][img_index]['bufferView']
        self._dirty_images[bv_index] = buf.getvalue()
        self._img_cache.pop(img_index, None)
        im = self.json['images'][img_index]
        im['mimeType'] = 'image/png'
        im.pop('uri', None)

    def material_image(self, mat_name, slot='baseColorTexture'):
        _i, m = self.material(mat_name)
        tex = m.get('pbrMetallicRoughness', {}).get(slot)
        if not tex:
            return None
        return self.image_index_of_texture(tex['index'])

    # ---------- 3D → UV 映射（纹理空间反投影） ----------
    def uv_posmap(self, mat_names, size, flip_v=True):
        """把材质三角面栅格化到纹理空间，返回 (posmap[H,W,3], hit[H,W], nrmmap[H,W,3])。

        posmap[y, x] = 该纹理像素对应的models空间坐标（绑定姿势）。
        """
        W, H = size
        posmap = np.zeros((H, W, 3), np.float32)
        nrmmap = np.zeros((H, W, 3), np.float32)
        hit = np.zeros((H, W), bool)
        for name in ([mat_names] if isinstance(mat_names, str) else mat_names):
            try:
                P, UV, N, IDX = self.geometry(name)
            except KeyError:
                continue
            # 纹理坐标 → 像素
            px = UV[:, 0] * W
            py = (1.0 - UV[:, 1]) * H if flip_v else UV[:, 1] * H
            for tri in IDX:
                x0, y0 = px[tri[0]], py[tri[0]]
                x1, y1 = px[tri[1]], py[tri[1]]
                x2, y2 = px[tri[2]], py[tri[2]]
                area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
                if abs(area) < 1e-9:
                    continue
                xmin = max(int(math.floor(min(x0, x1, x2))), 0)
                xmax = min(int(math.ceil(max(x0, x1, x2))), W - 1)
                ymin = max(int(math.floor(min(y0, y1, y2))), 0)
                ymax = min(int(math.ceil(max(y0, y1, y2))), H - 1)
                if xmin > xmax or ymin > ymax:
                    continue
                gx, gy = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
                w0 = ((x1 - x0) * (gy - y0) - (gx - x0) * (y1 - y0)) / area
                w1 = ((gx - x0) * (y2 - y0) - (x2 - x0) * (gy - y0)) / area
                w2 = 1.0 - w0 - w1
                inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
                if not inside.any():
                    continue
                ww = np.stack([w0, w1, w2], -1)[inside]
                sub = posmap[ymin:ymax + 1, xmin:xmax + 1]
                subn = nrmmap[ymin:ymax + 1, xmin:xmax + 1]
                subh = hit[ymin:ymax + 1, xmin:xmax + 1]
                sub[inside] = ww @ P[tri]
                subn[inside] = ww @ N[tri]
                subh[inside] = True
        return posmap, hit, nrmmap

    # ---------- 隐藏部件 ----------
    def remove_primitives_of_material(self, mat_name):
        """物理删除某材质的所有图元（用于隐藏兔耳/眼镜/原配饰）。"""
        mi, _ = self.material(mat_name)
        n = 0
        for me in self.json.get('meshes', []):
            keep = []
            for p in me['primitives']:
                if p.get('material') == mi:
                    n += 1
                else:
                    keep.append(p)
            me['primitives'] = keep
            if not keep:
                me['primitives'] = []
        return n

    def humanoid_node(self, bone):
        for b in self.json['extensions']['VRM']['humanoid']['humanBones']:
            if b['bone'] == bone:
                return b['node']
        raise KeyError(bone)

    def joint_index(self, node_index):
        """返回 node 在 skin.joints 里的下标（JOINTS_0 使用的编号）。"""
        for s in self.json['skins']:
            if node_index in s['joints']:
                return s['joints'].index(node_index)
        raise KeyError(node_index)

    def node_position(self, node_index):
        """骨骼绑定姿势下的模型空间位置（沿父链累加平移）。"""
        parent = {}
        for i, nd in enumerate(self.json['nodes']):
            for c in nd.get('children', []):
                parent[c] = i
        pos = np.zeros(3, np.float32)
        cur = node_index
        while True:
            nd = self.json['nodes'][cur]
            t = nd.get('translation', [0, 0, 0])
            pos = pos + np.array(t, np.float32)
            if 'matrix' in nd:
                m = np.array(nd['matrix'], np.float32).reshape(4, 4).T
                pos = pos + m[:3, 3]
            if cur not in parent:
                break
            cur = parent[cur]
        return pos

    # ---------- 新增网格（程序化连衣裙） ----------
    def add_skinned_mesh(self, name, positions, uvs, normals, indices, joints, weights,
                         material_index, node_name=None):
        acc_p = self.add_accessor(positions, 5126, 'VEC3')
        acc_u = self.add_accessor(uvs, 5126, 'VEC2')
        acc_n = self.add_accessor(normals, 5126, 'VEC3')
        acc_j = self.add_accessor(joints, 5121, 'VEC4')
        acc_w = self.add_accessor(weights, 5126, 'VEC4')
        acc_i = self.add_accessor(indices.reshape(-1), 5125, 'SCALAR', minmax=False)
        mesh = {'name': name, 'primitives': [{
            'attributes': {'POSITION': acc_p, 'TEXCOORD_0': acc_u, 'NORMAL': acc_n,
                           'JOINTS_0': acc_j, 'WEIGHTS_0': acc_w},
            'indices': acc_i, 'material': material_index, 'mode': 4}]}
        self.json['meshes'].append(mesh)
        mesh_index = len(self.json['meshes']) - 1
        node = {'name': node_name or name, 'mesh': mesh_index, 'skin': 0}
        self.json['nodes'].append(node)
        node_index = len(self.json['nodes']) - 1
        self.json.setdefault('scenes', [{}])
        self.json['scenes'][self.json.get('scene', 0)].setdefault('nodes', []).append(node_index)
        return node_index

    def add_material(self, name, base_color=(1, 1, 1, 1), image=None, double_sided=True,
                     alpha_mode='OPAQUE', unlit=True, metallic=0.0, roughness=0.9):
        mat = {'name': name,
               'doubleSided': double_sided,
               'alphaMode': alpha_mode,
               'pbrMetallicRoughness': {'baseColorFactor': list(base_color),
                                        'metallicFactor': metallic,
                                        'roughnessFactor': roughness}}
        if unlit:
            mat['extensions'] = {'KHR_materials_unlit': {}}
        self.json.setdefault('materials', []).append(mat)
        mi = len(self.json['materials']) - 1
        if image is not None:
            self.add_image_texture(image, mi)
        return mi

    def add_image_texture(self, pil, material_index, slot='baseColorTexture'):
        buf = io.BytesIO()
        pil.convert('RGBA').save(buf, format='PNG', optimize=True)
        raw = _pad4(buf.getvalue())
        offset = len(self.bin)
        self.bin = self.bin + raw
        bv = {'buffer': 0, 'byteOffset': offset, 'byteLength': len(raw)}
        self.json.setdefault('bufferViews', []).append(bv)
        bvi = len(self.json['bufferViews']) - 1
        self.json.setdefault('images', []).append({'name': 'gen_tex', 'mimeType': 'image/png', 'bufferView': bvi})
        img_i = len(self.json['images']) - 1
        self.json.setdefault('textures', []).append({'sampler': 0, 'source': img_i})
        tex_i = len(self.json['textures']) - 1
        self.json['materials'][material_index].setdefault('pbrMetallicRoughness', {})[slot] = {'index': tex_i}
        return tex_i

    def add_texture_from_image(self, pil):
        buf = io.BytesIO()
        pil.convert('RGBA').save(buf, format='PNG', optimize=True)
        raw = _pad4(buf.getvalue())
        offset = len(self.bin)
        self.bin = self.bin + raw
        self.json.setdefault('bufferViews', []).append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(raw)})
        self.json.setdefault('images', []).append({'name': 'gen_tex', 'mimeType': 'image/png',
                                                   'bufferView': len(self.json['bufferViews']) - 1})
        self.json.setdefault('textures', []).append({'sampler': 0, 'source': len(self.json['images']) - 1})
        return len(self.json['textures']) - 1

    def tex_source_of_material(self, mat_name, slot='baseColorTexture'):
        _i, m = self.material(mat_name)
        t = m.get('pbrMetallicRoughness', {}).get(slot)
        return t['index'] if t else None

    def set_material_texture(self, mat_name, tex_index, slot='baseColorTexture'):
        _i, m = self.material(mat_name)
        m.setdefault('pbrMetallicRoughness', {})[slot] = {'index': tex_index}

    def vrm_meta(self):
        return self.json['extensions']['VRM'].get('meta', {})
