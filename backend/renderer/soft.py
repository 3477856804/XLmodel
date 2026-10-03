#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.soft —— 纯 Python（numpy）软件光栅化后端（无任何 GL/GPU 依赖）

* 与 GL 后端共用 renderer.pose 的变形结果（形变目标 → 蒙皮），保证观感一致
* 逐三角重心扫描 + z-buffer；不透明先画，半透明按"画家算法"远→近叠加
* 顶点聚簇抽取（可选）用于把 5 万面降到可实时交互的量级

定位：GL 不可用时的兜底（无桌面/无 Mesa/驱动异常），或离线出图。
性能参考：320×480、5 万面 ≈ 0.3~0.9 s/帧（纯 Python）；开启抽取后可到 ~5 fps。
"""
from __future__ import annotations

import math
import time

import numpy as np

from renderer.pose import deform_primitive


def _lin(rgb_u8):
    a = rgb_u8.astype(np.float32) / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4).astype(np.float32)


def _srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def _kind(name: str) -> str:
    n = (name or '').lower()
    if 'hair' in n:
        return 'hair'
    if 'shoe' in n or 'boot' in n:
        return 'shoes'
    if any(k in n for k in ('cloth', 'onepiece', 'tops', 'costume', 'tie', 'dress')):
        return 'cloth'
    return 'skin'


def cluster_decimate(pos, uv, idx, eps):
    """顶点聚簇抽取：吸附到 eps 网格 → 合并重复点 → 去退化三角。"""
    if eps <= 0:
        return pos, uv, idx
    grid = np.floor(pos / eps).astype(np.int64)
    _, inv, counts = np.unique(grid, axis=0, return_inverse=True, return_counts=True)
    n = len(counts)
    new_pos = np.zeros((n, 3), np.float32)
    new_uv = np.zeros((n, 2), np.float32)
    np.add.at(new_pos, inv, pos)
    np.add.at(new_uv, inv, uv)
    new_pos /= counts[:, None]
    new_uv /= counts[:, None]
    tri = inv[idx].astype(np.int32)
    good = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
    tri = tri[good]
    if len(tri):
        _, uniq = np.unique(np.sort(tri, axis=1), axis=0, return_index=True)
        tri = tri[np.sort(uniq)]
    return new_pos, new_uv, tri


class _Prepared:
    __slots__ = ('prim', 'mat', 'tri', 'uv_tri', 'color', 'shade', 'alpha_mode', 'cutoff',
                 'double_sided', 'unlit', 'tex_lin', 'tex_a')

    def __init__(self, prim, mat, tri, uv_tri, tex_lin, tex_a):
        self.prim = prim
        self.mat = mat
        self.tri = tri
        self.uv_tri = uv_tri
        self.color = mat.color
        self.shade = mat.shade
        self.alpha_mode = mat.alpha_mode
        self.cutoff = mat.cutoff
        self.double_sided = mat.double_sided
        self.unlit = mat.unlit
        self.tex_lin = tex_lin
        self.tex_a = tex_a


class SoftRenderer:
    """CPU 光栅渲染器。"""

    def __init__(self, model, width=320, height=480, background=(0.96, 0.96, 0.97),
                 decimate=False, max_triangles=30000):
        self.model = model
        self.w, self.h = width, height
        self.bg = np.array(background, np.float32)
        self.decimate = decimate
        self.prepared: list[_Prepared] = []
        self.frame_ms = 0.0
        self._build(max_triangles)

    def _build(self, max_triangles=100000):
        total = self.model.triangle_count()
        # 面数过多时按倍率加大聚簇网格（eps 要小，避免过度简化破坏模型）
        base_eps = 0.0008
        if total > max_triangles:
            base_eps = 0.0008 * (total / max_triangles) ** 0.4
        for prim in self.model.primitives:
            mat = (self.model.materials[prim.material]
                   if 0 <= prim.material < len(self.model.materials) else None)
            if mat is None:
                continue
            pos, uv, idx = prim.positions, prim.uvs, prim.indices
            if self.decimate:
                factor = {'hair': 1.2, 'cloth': 1.1, 'shoes': 1.0}.get(_kind(mat.name), 1.0)
                pos, uv, idx = cluster_decimate(pos, uv, idx, base_eps * factor)
            uv_tri = uv[idx] if len(idx) else np.zeros((0, 3, 2), np.float32)
            tex_lin = tex_a = None
            if mat.texture is not None:
                tex_lin = _lin(mat.texture[..., :3])
                tex_a = mat.texture[..., 3].astype(np.float32) / 255.0
            self.prepared.append(_Prepared(prim, mat, idx, uv_tri, tex_lin, tex_a))

    def stats(self) -> dict:
        return {'backend': 'soft', 'primitives': len(self.prepared),
                'triangles': int(sum(len(p.tri) for p in self.prepared)),
                'size': [self.w, self.h], 'frame_ms': round(self.frame_ms, 1)}

    # ------------------------------------------------------------------ 渲染
    def render(self, pose, morph_map=None, view_proj=None, camera=None, focus='bust',
               light=(0.35, 0.45, 0.82)):
        t0 = time.perf_counter()
        if view_proj is None:
            from renderer.camera import OrbitCamera
            cam = camera or OrbitCamera(self.model.bbox_max[1], focus=focus)
            view_proj = cam.view_proj(self.w / self.h)
        W, H = self.w, self.h
        zbuf = np.full((H, W), 1e9, np.float32)
        color = np.zeros((H, W, 3), np.float32)
        abuf = np.zeros((H, W), np.float32)
        L = np.array(light, np.float32)
        L = L / (np.linalg.norm(L) + 1e-6)
        items = []
        for p in self.prepared:
            mw = (morph_map or {}).get(p.prim.index)
            pos, nrm = deform_primitive(p.prim, pose, 0, mw)
            v = _project(pos, view_proj, W, H)
            order = np.argsort(-v[p.tri][:, :, 2].mean(1)) if p.alpha_mode == 'BLEND' else None
            tri = p.tri[order] if order is not None else p.tri
            uv_tri = p.uv_tri[order] if order is not None else p.uv_tri
            items.append((0 if p.alpha_mode != 'BLEND' else 1, p, v, nrm, tri, uv_tri))
        for _k, p, v, nrm, tri, uv_tri in sorted(items, key=lambda t: t[0]):
            depth_write = p.alpha_mode != 'BLEND'
            for i in range(len(tri)):
                t = tri[i]
                _raster(self, p, v[t], nrm[t], uv_tri[i], zbuf, color, abuf, L, depth_write)
        out = _srgb(color)
        a = abuf[..., None]
        return np.clip(out * a + self.bg[None, None, :] * (1 - a), 0, 1)


def _project(pos, view_proj, W, H):
    n = len(pos)
    homo = np.concatenate([pos, np.ones((n, 1), np.float32)], 1)
    clip = homo @ view_proj.T
    w = np.where(np.abs(clip[:, 3]) < 1e-6, 1e-6, clip[:, 3])
    ndc = clip[:, :3] / w[:, None]
    return np.stack([(ndc[:, 0] * 0.5 + 0.5) * W, (0.5 - ndc[:, 1] * 0.5) * H, -ndc[:, 2]], 1)


def _raster(r, p, vs, ns, uvs, zbuf, color, abuf, L, depth_write):
    W, H = r.w, r.h
    x0, y0, x1, y1, x2, y2 = vs[0, 0], vs[0, 1], vs[1, 0], vs[1, 1], vs[2, 0], vs[2, 1]
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-9:
        return
    minx = max(int(math.floor(min(x0, x1, x2))), 0)
    maxx = min(int(math.ceil(max(x0, x1, x2))), W - 1)
    miny = max(int(math.floor(min(y0, y1, y2))), 0)
    maxy = min(int(math.ceil(max(y0, y1, y2))), H - 1)
    if minx > maxx or miny > maxy:
        return
    gx, gy = np.meshgrid(np.arange(minx, maxx + 1) + 0.5, np.arange(miny, maxy + 1) + 0.5)
    w2 = ((x1 - x0) * (gy - y0) - (gx - x0) * (y1 - y0)) / area
    w1 = ((gx - x0) * (y2 - y0) - (x2 - x0) * (gy - y0)) / area
    w0 = 1.0 - w1 - w2
    inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    if not inside.any():
        return
    z = w0 * vs[0, 2] + w1 * vs[1, 2] + w2 * vs[2, 2]
    sub_z = zbuf[miny:maxy + 1, minx:maxx + 1]
    vis = inside & ((z - (0.0 if depth_write else 3e-3)) < sub_z)
    if not vis.any():
        return
    ww = np.stack([w0, w1, w2], -1)[vis]
    uv = ww @ uvs
    if p.tex_lin is not None:
        th, tw = p.tex_a.shape
        px = np.clip((np.mod(uv[:, 0], 1.0) * tw).astype(np.int32), 0, tw - 1)
        py = np.clip(((1.0 - np.mod(uv[:, 1], 1.0)) * th).astype(np.int32), 0, th - 1)
        rgb = p.tex_lin[py, px] * p.color[:3]
        al = p.tex_a[py, px] * p.color[3]
    else:
        rgb = np.ones((len(uv), 3), np.float32) * p.color[:3]
        al = np.ones(len(uv), np.float32) * p.color[3]
    if not p.unlit:
        nn = ww @ ns
        nn = nn / (np.linalg.norm(nn, axis=1, keepdims=True) + 1e-6)
        lit = np.clip(nn @ L, 0, 1)
        band = np.where(lit > 0.28, 1.0, np.where(lit > 0.02, 0.72, 0.5))
        rgb = rgb * (p.shade[None, :] * (1 - band[:, None]) + band[:, None])
    ii = np.where(vis)
    rr = color[miny:maxy + 1, minx:maxx + 1]
    ra = abuf[miny:maxy + 1, minx:maxx + 1]
    if p.alpha_mode == 'MASK':
        keep = al >= p.cutoff
        if not keep.any():
            return
        sel = (ii[0][keep], ii[1][keep])
        rr[sel] = rgb[keep]
        ra[sel] = 1.0
        if depth_write:
            sub_z[sel] = z[ii][keep]
    elif p.alpha_mode == 'BLEND':
        a = al[:, None]
        rr[ii] = rr[ii] * (1 - a) + rgb * a
        ra[ii] = np.clip(ra[ii] * (1 - al) + al, 0, 1)
    else:
        rr[ii] = rgb
        ra[ii] = 1.0
        if depth_write:
            sub_z[ii] = z[ii]
