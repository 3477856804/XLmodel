#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xiaoling_avatar —— 把任意 VRM 角色改造成"小凌"形象的流水线

用法：
    python3 tools/xiaoling_avatar.py build \
        --base 角色模型/Rabbit_Peridot.vrm \
        --face 素材/xiaoling.png \
        --out 角色模型/小凌.vrm --preview preview/

改造内容：
    1. 服装纯白化（白裙）：保留褶皱明暗，去掉原配色
    2. 白丝：按模型空间坐标在腿部 UV 区域程序化绘制白色过膝袜
    3. 发色重染：抽样立绘发色 → 浅亚麻金
    4. 瞳色重绘：抽样立绘瞳色 → 湛蓝眼 + 高光
    5. 五官迁移：立绘的眼睛/眉毛/嘴唇/腮红 → VRM 面部贴图
    6. 白裙：程序化生成连衣裙网格（自动蒙皮 hips/spine/chest/upperLeg）
    7. 配饰清理：隐藏兔耳/眼镜等不属于小凌的部件
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vrm_lib import VRM  # noqa: E402

# ----------------------------------------------------------------------------
# 小凌的配色（也可由 --face 立绘自动采样覆盖）
# ----------------------------------------------------------------------------
PALETTE = {
    'hair':      (222, 210, 186),   # 浅亚麻金
    'hair_shadow': (188, 168, 138),
    'skin':      (247, 233, 228),   # 冷白皮
    'blush':     (243, 183, 178),
    'iris':      (86, 158, 214),    # 湛蓝
    'iris_deep': (38, 92, 160),
    'brow':      (176, 158, 132),
    'lash':      (58, 52, 58),
    'cloth':     (252, 252, 254),   # 纯白布料
    'trim':      (222, 232, 245),   # 淡蓝装饰线
    'stocking':  (250, 250, 252),
}


def _srgb_lum(rgb):
    return (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])


def sample_palette_from_face(path, debug_dir=None):
    """从 2D 立绘里采样小凌的发色 / 瞳色 / 肤色 / 唇色。"""
    import numpy as _np
    im = Image.open(path).convert('RGB')
    W, H = im.size
    a = _np.asarray(im).astype(_np.float32) / 255.0

    def patch(cx, cy, r):
        x0, x1 = max(int(cx - r), 0), min(int(cx + r), W)
        y0, y1 = max(int(cy - r), 0), min(int(cy + r), H)
        return a[y0:y1, x0:x1].reshape(-1, 3)

    out = dict(PALETTE)
    # 发色：取头顶区域中较亮的 60%
    hair_zone = a[int(H * 0.06):int(H * 0.22), int(W * 0.30):int(W * 0.70)].reshape(-1, 3)
    if len(hair_zone):
        l = _srgb_lum(hair_zone)
        sel = hair_zone[l >= _np.percentile(l, 40)]
        out['hair'] = tuple((sel.mean(0) * 255).astype(int).tolist())
        out['hair_shadow'] = tuple((sel.mean(0) * 0.80 * 255).astype(int).tolist())
    # 瞳色：全图最蓝的像素簇（剔除高光/眼白）
    blue = a[..., 2] - 0.5 * (a[..., 0] + a[..., 1])
    val = a.max(-1)
    mask = (blue > max(0.10, float(_np.percentile(blue, 99.0)))) & (val < 0.92)
    if mask.sum() < 15:
        mask = blue > float(_np.percentile(blue, 99.5))
    if mask.sum() > 10:
        sel = a[mask]
        l = _srgb_lum(sel)
        core = sel[l <= _np.percentile(l, 55)]
        out['iris'] = tuple((core.mean(0) * 255).astype(int).tolist())
        out['iris_deep'] = tuple((core.mean(0) * 0.55 * 255).astype(int).tolist())
    # 肤色：脸颊偏亮区域
    fy0, fy1 = int(H * 0.30), int(H * 0.52)
    fx0, fx1 = int(W * 0.34), int(W * 0.66)
    skin_zone = a[fy0:fy1, fx0:fx1].reshape(-1, 3)
    if len(skin_zone):
        l = _srgb_lum(skin_zone)
        sel = skin_zone[l >= _np.percentile(l, 65)]
        out['skin'] = tuple((sel.mean(0) * 255).astype(int).tolist())
    # 唇色：嘴部区域最红的部分
    mouth_zone = a[int(H * 0.50):int(H * 0.58), int(W * 0.44):int(W * 0.58)].reshape(-1, 3)
    if len(mouth_zone):
        red = mouth_zone[:, 0] - 0.5 * (mouth_zone[:, 1] + mouth_zone[:, 2])
        sel = mouth_zone[red >= _np.percentile(red, 95)]
        out['blush'] = tuple((sel.mean(0) * 255).astype(int).tolist())
    if debug_dir:
        Path(debug_dir).mkdir(parents=True, exist_ok=True)
        Path(debug_dir, 'palette.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return out


# ----------------------------------------------------------------------------
# 纹理处理原语
# ----------------------------------------------------------------------------
def luminance_normalized(arr_rgb, pct=97.0):
    l = _srgb_lum(arr_rgb)
    l = np.asarray(l, np.float32)
    ref = max(float(np.percentile(l, pct)), 1e-3)
    return np.clip(l / ref, 0, 1.4)


def retint(img, target_rgb, strength=1.0, keep_alpha=True, dark_floor=0.22,
           contrast=(0.42, 1.05)):
    """按亮度结构把任意颜色纹理重染成目标色。

    采用"相对亮度"归一化 + 对比拉伸：即使是纯黑底（原发色/服装色很暗）也能染成
    目标色，同时保留原始明暗褶皱（这是换发色/换配色的关键）。
    """
    a = np.asarray(img.convert('RGBA')).astype(np.float32) / 255.0
    rgb = a[..., :3]
    al = a[..., 3]
    l = np.asarray(_srgb_lum(rgb), np.float32)
    vis = al > 0.04
    ref = float(np.percentile(l[vis], 72)) if vis.any() else 1.0
    ref = max(ref, 1e-3)
    ln = np.clip(l / ref, 0, 2.0)
    lo, hi = contrast
    ln = np.clip((ln - lo) / max(hi - lo, 1e-3), 0, 1.25)
    ln = dark_floor + (1.0 - dark_floor) * ln
    tgt = np.array(target_rgb, np.float32) / 255.0
    new_rgb = np.clip(ln, 0, 1.35)[..., None] * tgt[None, None, :]
    hi_mask = np.clip((ln - 1.02) / 0.25, 0, 1)[..., None]
    new_rgb = new_rgb * (1 - hi_mask) + hi_mask
    out = a.copy()
    out[..., :3] = np.clip(rgb * (1 - strength) + new_rgb * strength, 0, 1)
    if keep_alpha:
        out[..., 3] = al
    return Image.fromarray((out * 255).astype(np.uint8))


def whiten(img, target_rgb=(252, 252, 254), strength=0.96, shadow=0.52):
    """布料纯白化：用相对亮度归一化，黑布料也能变成保留褶皱的白裙。"""
    a = np.asarray(img.convert('RGBA')).astype(np.float32) / 255.0
    rgb = a[..., :3]
    al = a[..., 3]
    l = np.asarray(_srgb_lum(rgb), np.float32)
    vis = al > 0.04
    ref = float(np.percentile(l[vis], 80)) if vis.any() else 1.0
    ln = np.clip(l / max(ref, 1e-3), 0, 2.0)
    ln = np.clip((ln - 0.35) / 0.75, 0, 1.25)
    shade = shadow + (1.0 - shadow) * ln
    tgt = np.array(target_rgb, np.float32) / 255.0
    new = np.clip(shade, 0, 1.15)[..., None] * tgt[None, None, :]
    out = a.copy()
    out[..., :3] = np.clip(rgb * (1 - strength) + new * strength, 0, 1)
    if 'strength' and False:
        pass
    # 透明区域保持透明
    out[..., 3] = al
    return Image.fromarray((out * 255).astype(np.uint8))


def hue_shift_to(img, target_hue, target_sat=None, keep_value=True):
    """把纹理整体色相挪到目标色相（用于瞳色：绿眼→蓝眼）。"""
    hsv = np.asarray(img.convert('RGBA').convert('HSV')) .astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    h = np.full_like(h, target_hue / 360.0 * 255.0)
    if target_sat is not None:
        s = np.clip(s * 0.25 + target_sat / 100.0 * 255.0, 0, 255)
    hsv[..., 0], hsv[..., 1] = h, s
    hsv = hsv.astype(np.uint8)
    rgb = Image.fromarray(hsv, 'HSV').convert('RGBA')
    a = np.asarray(img.convert('RGBA'))[..., 3]
    arr = np.asarray(rgb).copy()
    arr[..., 3] = a
    return Image.fromarray(arr)


def tint_square(img, target_rgb, strength=0.35):
    """整体轻微色调迁移（肤色统一）。"""
    a = np.asarray(img.convert('RGBA')).astype(np.float32) / 255.0
    rgb = a[..., :3]
    m = rgb.reshape(-1, 3).mean(0)
    tgt = np.array(target_rgb, np.float32) / 255.0
    ratio = tgt / np.maximum(m, 1e-3)
    new = np.clip(rgb * ratio[None, None, :], 0, 1)
    out = a.copy()
    out[..., :3] = np.clip(rgb * (1 - strength) + new * strength, 0, 1)
    return Image.fromarray((out * 255).astype(np.uint8))


# ----------------------------------------------------------------------------
# 立绘特征提取（眼睛 / 眉毛 / 嘴唇）
# ----------------------------------------------------------------------------
class FaceSource:
    """从 2D 立绘中提取五官素材。"""

    def __init__(self, path):
        self.im = Image.open(path).convert('RGB')
        self.a = np.asarray(self.im).astype(np.float32) / 255.0
        self.W, self.H = self.im.size
        self.eyes = self._find_eyes()
        self.mouth = self._find_mouth()

    def _find_eyes(self):
        a = self.a
        blue = a[..., 2] - 0.5 * (a[..., 0] + a[..., 1])
        mask = blue > max(0.06, float(np.percentile(blue, 99.0)) * 0.55)
        ys, xs = np.where(mask)
        if len(xs) < 50:
            return []
        # 上半脸、左右各聚一类
        upper = ys < self.H * 0.55
        ys, xs = ys[upper], xs[upper]
        mid = np.median(xs)
        out = []
        for sel in (xs < mid, xs >= mid):
            if sel.sum() < 30:
                continue
            ex, ey = xs[sel], ys[sel]
            x0, x1 = ex.min(), ex.max()
            y0, y1 = ey.min(), ey.max()
            w, h = x1 - x0, y1 - y0
            pad = 0.55
            box = (max(int(x0 - w * pad), 0), max(int(y0 - h * pad * 2.2), 0),
                   min(int(x1 + w * pad), self.W), min(int(y1 + h * pad * 0.8), self.H))
            out.append({'iris_box': (x0, y0, x1, y1), 'box': box,
                        'center': ((x0 + x1) / 2, (y0 + y1) / 2), 'w': w, 'h': h})
        out.sort(key=lambda e: e['center'][0])
        return out

    def _find_mouth(self):
        a = self.a
        y0, y1 = int(self.H * 0.46), int(self.H * 0.60)
        x0, x1 = int(self.W * 0.38), int(self.W * 0.62)
        sub = a[y0:y1, x0:x1]
        red = sub[..., 0] - 0.5 * (sub[..., 1] + sub[..., 2])
        thr = max(0.04, float(np.percentile(red, 99.0)) * 0.5)
        m = red > thr
        ys, xs = np.where(m)
        if len(xs) < 5:
            return None
        bx0, bx1 = xs.min() + x0, xs.max() + x0
        by0, by1 = ys.min() + y0, ys.max() + y0
        w, h = bx1 - bx0, by1 - by0
        pad = 1.4
        box = (max(int(bx0 - w * pad), 0), max(int(by0 - h * pad), 0),
               min(int(bx1 + w * pad), self.W), min(int(by1 + h * pad), self.H))
        return {'box': box, 'center': ((bx0 + bx1) / 2, (by0 + by1) / 2), 'w': w, 'h': h}

    def eye_crop(self, idx, alpha_trim=True):
        e = self.eyes[idx]
        crop = self.im.crop(e['box']).convert('RGBA')
        return crop, e

    def mouth_crop(self):
        m = self.mouth
        return self.im.crop(m['box']).convert('RGBA'), m


def _soft_ellipse_mask(size, feather=0.12):
    W, H = size
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    pad = max(int(min(W, H) * feather), 1)
    d.ellipse((pad, pad, W - 1 - pad, H - 1 - pad), fill=255)
    return m.filter(ImageFilter.GaussianBlur(pad * 0.9))


# ----------------------------------------------------------------------------
# 身体尺寸测量 & 程序化白裙
# ----------------------------------------------------------------------------
def torso_profile(vrm, skin_material):
    """测量躯干半径剖面：返回 f(y) -> (r, cx, cz)。"""
    P, UV, N, IDX = vrm.geometry(skin_material)
    ys = P[:, 1]
    y0, y1 = float(ys.min()), float(ys.max())
    samples = []
    for y in np.arange(0.30, min(y1, 1.30), 0.01):
        sel = np.abs(ys - y) < 0.012
        if sel.sum() < 6:
            continue
        p = P[sel]
        # 只保留躯干附近的点（排除手臂：|x| 过大且 z 很小）
        core = np.abs(p[:, 0]) < 0.30
        if core.sum() < 5:
            continue
        p = p[core]
        cx, cz = float(np.median(p[:, 0])), float(np.median(p[:, 2]))
        r = float(np.percentile(np.sqrt((p[:, 0] - cx) ** 2 + (p[:, 2] - cz) ** 2), 92))
        samples.append((float(y), r, cx, cz))
    samples.sort()
    arr = np.array(samples) if samples else np.array([[0.8, 0.12, 0.0, 0.0]], np.float32)

    def f(y):
        ys_ = arr[:, 0]
        if y <= ys_[0]:
            row = arr[0]
        elif y >= ys_[-1]:
            row = arr[-1]
        else:
            i = int(np.searchsorted(ys_, y) - 1)
            t = (y - ys_[i]) / max(ys_[i + 1] - ys_[i], 1e-6)
            row = arr[i] * (1 - t) + arr[i + 1] * t
        return float(row[1]), float(row[2]), float(row[3])

    return f, (y0, y1)


def _cloth_texture(size=(256, 512), base=(252, 252, 254), trim=(214, 228, 246)):
    W, H = size
    u = (np.arange(W)[None, :] / W) * math.pi * 2 * 9      # 9 条褶皱
    v = np.arange(H)[:, None] / H
    fold = 0.055 * np.sin(u) + 0.022 * np.sin(u * 2.3 + 1.1)
    noise = (np.random.RandomState(7).rand(H, W).astype(np.float32) - 0.5) * 0.02
    shade = 1.0 + fold + noise
    rgb = np.stack([shade * c for c in base], -1)
    img = np.clip(rgb, 0, 255)
    pil = Image.fromarray(img.astype(np.uint8)).convert('RGBA')
    d = ImageDraw.Draw(pil)
    # 腰部缎带（v ≈ 0.30）与裙摆蕾丝（v ≈ 0.94）
    for vv, hh, col in ((0.31, 0.020, trim), (0.335, 0.008, (255, 255, 255)),
                        (0.945, 0.018, trim), (0.965, 0.010, (255, 255, 255))):
        y0 = int((vv - hh) * H); y1 = int((vv + hh) * H)
        d.rectangle((0, y0, W, y1), fill=col + (255,))
    return pil


def build_dress(vrm, prof, y0, y1, seg=64, bodice_rings=12, skirt_rings=22, hem_drop=0.40):
    """生成白色连衣裙网格（含泡泡短袖），返回 skinned mesh 数据。"""
    hips = vrm.node_position(vrm.humanoid_node('hips'))
    chest = vrm.node_position(vrm.humanoid_node('chest'))
    upper = vrm.node_position(vrm.humanoid_node('upperChest'))
    neck = vrm.node_position(vrm.humanoid_node('neck'))
    y_waist = float(hips[1] + 0.06)
    y_top = float(min(neck[1] - 0.05, upper[1] + 0.055))
    y_hem = y_waist - hem_drop

    j_hips = vrm.joint_index(vrm.humanoid_node('hips'))
    j_spine = vrm.joint_index(vrm.humanoid_node('spine'))
    j_chest = vrm.joint_index(vrm.humanoid_node('chest'))
    j_upper = vrm.joint_index(vrm.humanoid_node('upperChest'))
    j_lleg = vrm.joint_index(vrm.humanoid_node('leftUpperLeg'))
    j_rleg = vrm.joint_index(vrm.humanoid_node('rightUpperLeg'))

    def ring_pts(y, r_scale, z_scale, pleat=0.0, waves=8, y_wave=0.0, front_dip=0.0):
        th = np.arange(seg, dtype=np.float32) / seg * math.pi * 2
        r, cx, cz = prof(y)
        rr = (r * r_scale + 0.006) * (1.0 + pleat * np.sin(waves * th))
        x = cx + rr * np.cos(th)
        z = cz + rr * z_scale * np.sin(th)
        yy = np.full(seg, y, np.float32)
        if y_wave:
            yy = yy + y_wave * np.sin(waves * th)
        if front_dip:
            yy = yy - front_dip * np.clip(np.cos(th), 0, 1) ** 2
        return np.stack([x, yy, z], -1)

    rings = []
    # 裙摆 → 腰（从下往上）
    for i in range(skirt_rings + 1):
        t = 1.0 - i / skirt_rings                    # t: 0=腰 1=摆
        y = y_waist - hem_drop * t
        r_scale = 1.06 + 1.05 * (t ** 1.35)          # 喇叭裙
        z_scale = 0.74 + 0.20 * t
        pts = ring_pts(y, r_scale, z_scale, pleat=0.014 + 0.012 * t, waves=9,
                       y_wave=0.006 * t)
        rings.append(pts)
    # 上身（腰 → 胸顶）
    for i in range(1, bodice_rings + 1):
        t = i / bodice_rings
        y = y_waist + (y_top - y_waist) * t
        r_scale = 1.045 - 0.02 * t
        pts = ring_pts(y, r_scale, 0.80, pleat=0.006, waves=9,
                       front_dip=0.045 * max(0.0, (t - 0.68) / 0.32))
        rings.append(pts)

    pos = np.concatenate(rings, 0)
    R = len(rings)
    # UV：u 围绕，v 沿高度
    us = np.tile(np.arange(seg)[None, :] / seg, (R, 1)).reshape(-1)
    vs = np.repeat((np.arange(R)[:, None] / (R - 1)), seg, 1).reshape(-1)
    uv = np.stack([us, 1.0 - vs], -1).astype(np.float32)

    idx = []
    for r_ in range(R - 1):
        for c in range(seg):
            c2 = (c + 1) % seg
            a = r_ * seg + c
            b = r_ * seg + c2
            cc = (r_ + 1) * seg + c
            dd = (r_ + 1) * seg + c2
            idx += [[a, cc, b], [b, cc, dd]]
    idx = np.array(idx, np.uint32)

    # 顶点法线（用网格切向的叉积）
    grid = pos.reshape(R, seg, 3)
    du = np.roll(grid, -1, 1) - np.roll(grid, 1, 1)
    dv = np.concatenate([grid[1:2] - grid[0:1], (grid[2:] - grid[:-2]) * 0.5, grid[-1:] - grid[-2:-1]], 0)
    nrm = np.cross(du, dv)
    ln = np.linalg.norm(nrm, axis=-1, keepdims=True)
    nrm = nrm / np.maximum(ln, 1e-6)
    nrm = nrm.reshape(-1, 3).astype(np.float32)

    # 蒙皮权重：上身 → hips/spine/chest/upperChest；裙摆 → hips + 大腿（少量）
    joints = np.zeros((len(pos), 4), np.uint8)
    weights = np.zeros((len(pos), 4), np.float32)
    for vi, p in enumerate(pos):
        yy, xx = float(p[1]), float(p[0])
        if yy <= y_waist:                                    # 裙子
            t = np.clip((y_waist - yy) / max(hem_drop, 1e-3), 0, 1)
            w_leg = 0.42 * (t ** 2)
            j_leg = j_lleg if xx >= 0 else j_rleg
            joints[vi] = [j_hips, j_leg, 0, 0]
            weights[vi] = [1 - w_leg, w_leg, 0, 0]
        else:                                                # 上身
            t = (yy - y_waist) / max(y_top - y_waist, 1e-3)
            if t < 0.34:
                w = t / 0.34
                joints[vi] = [j_hips, j_spine, 0, 0]
                weights[vi] = [1 - w, w, 0, 0]
            elif t < 0.72:
                w = (t - 0.34) / 0.38
                joints[vi] = [j_spine, j_chest, 0, 0]
                weights[vi] = [1 - w, w, 0, 0]
            else:
                w = (t - 0.72) / 0.28
                joints[vi] = [j_chest, j_upper, 0, 0]
                weights[vi] = [1 - w, w, 0, 0]
        weights[vi] /= weights[vi].sum()

    # ---- 泡泡短袖 ----
    sleeves = []
    v_off = len(pos)
    for side in ('left', 'right'):
        j_up = vrm.joint_index(vrm.humanoid_node(f'{side}UpperArm'))
        p_up = vrm.node_position(vrm.humanoid_node(f'{side}UpperArm'))
        p_lo = vrm.node_position(vrm.humanoid_node(f'{side}LowerArm'))
        axis = p_lo - p_up
        axis = axis / max(float(np.linalg.norm(axis)), 1e-6)
        ref = np.array([0, 1, 0], np.float32) if abs(axis[1]) < 0.9 else np.array([0, 0, 1], np.float32)
        e1 = np.cross(axis, ref); e1 /= max(float(np.linalg.norm(e1)), 1e-6)
        e2 = np.cross(axis, e1)
        L = 0.085
        rings_s = []
        for i in range(7):
            t = i / 6
            r = 0.030 + 0.036 * math.sin(math.pi * min(t * 1.25, 1.0)) ** 0.7
            th = np.arange(20, dtype=np.float32) / 20 * math.pi * 2
            pts = (p_up[None, :] + axis[None, :] * (L * t)
                   + (np.cos(th)[:, None] * e1[None, :] + np.sin(th)[:, None] * e2[None, :]) * r)
            rings_s.append(pts)
        sp = np.concatenate(rings_s, 0).astype(np.float32)
        R2, S2 = 7, 20
        s_us = np.tile(np.arange(S2)[None, :] / S2, (R2, 1)).reshape(-1)
        s_vs = np.repeat(np.arange(R2)[:, None] / (R2 - 1), S2, 1).reshape(-1)
        s_uv = np.stack([s_us, 1 - s_vs], -1).astype(np.float32)
        s_idx = []
        for r_ in range(R2 - 1):
            for c in range(S2):
                c2 = (c + 1) % S2
                a = v_off + r_ * S2 + c
                b = v_off + r_ * S2 + c2
                cc = v_off + (r_ + 1) * S2 + c
                dd = v_off + (r_ + 1) * S2 + c2
                s_idx += [[a, cc, b], [b, cc, dd]]
        s_idx = np.array(s_idx, np.uint32)
        s_j = np.zeros((len(sp), 4), np.uint8); s_j[:, 0] = j_up
        s_w = np.zeros((len(sp), 4), np.float32); s_w[:, 0] = 1.0
        sleeves.append((sp, s_uv, s_idx, s_j, s_w))
        v_off += len(sp)

    pos_cat = np.concatenate([pos] + [s[0] for s in sleeves], 0).astype(np.float32)
    uv_cat = np.concatenate([uv] + [s[1] for s in sleeves], 0).astype(np.float32)
    j_cat = np.concatenate([joints] + [s[3] for s in sleeves], 0)
    w_cat = np.concatenate([weights] + [s[4] for s in sleeves], 0)
    idx_cat = np.concatenate([idx] + [s[2] for s in sleeves], 0).astype(np.uint32)

    # 法线：裙子部分已算，袖子用径向近似
    nrm_cat = np.zeros_like(pos_cat)
    nrm_cat[:len(pos)] = nrm
    off = len(pos)
    for (sp, s_uv, s_idx, s_j, s_w) in sleeves:
        c = sp.reshape(7, 20, 3).mean((0, 1))
        v = sp - c[None, :]
        v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-6)
        nrm_cat[off:off + len(sp)] = v
        off += len(sp)
    return dict(pos=pos_cat, uv=uv_cat, nrm=nrm_cat, idx=idx_cat, joints=j_cat, weights=w_cat,
                y_waist=y_waist, y_hem=y_hem, y_top=y_top)


# ----------------------------------------------------------------------------
# 图像连通域 / 遮罩工具
# ----------------------------------------------------------------------------
def components(mask, min_px=40):
    """极简四连通标签（返回 [(bbox, pixel_count, centroid, (ys,xs))]）。"""
    H, W = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    ys_all, xs_all = np.where(mask)
    coords = set(zip(ys_all.tolist(), xs_all.tolist()))
    for y0, x0 in zip(ys_all.tolist(), xs_all.tolist()):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pix = []
        while stack:
            y, x = stack.pop()
            pix.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(pix) >= min_px:
            arr = np.array(pix)
            out.append({'bbox': (int(arr[:, 0].min()), int(arr[:, 1].min()),
                                int(arr[:, 0].max()), int(arr[:, 1].max())),
                        'n': len(pix), 'centroid': (float(arr[:, 0].mean()), float(arr[:, 1].mean())),
                        'pix': arr})
    out.sort(key=lambda c: -c['n'])
    return out


def feature_mask(crop_rgb, skin_ref=None, thr=0.16, blur=2.0):
    """从立绘裁片里抠出"五官"（与肤色差异大的像素）作为 alpha 遮罩。"""
    a = np.asarray(crop_rgb.convert('RGB')).astype(np.float32) / 255.0
    ref = a.reshape(-1, 3).mean(0) if skin_ref is None else np.asarray(skin_ref, np.float32) / 255.0
    diff = np.abs(a - ref[None, None, :]).max(-1)
    m = np.clip((diff - thr * 0.5) / max(thr, 1e-6), 0, 1)
    pil = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))
    return pil


def paste_soft(base, patch, box, mask=None, opacity=1.0, flip=False):
    """把 patch 以柔和遮罩贴到 base 的 box 位置。"""
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    w, h = max(x1 - x0, 1), max(y1 - y0, 1)
    p = patch.resize((w, h), Image.LANCZOS)
    if flip:
        p = p.transpose(Image.FLIP_LEFT_RIGHT)
    if mask is not None:
        p.putalpha(mask.resize((w, h), Image.LANCZOS))
        if flip:
            p.putalpha(p.getchannel('A').transpose(Image.FLIP_LEFT_RIGHT))
    if opacity < 1.0:
        al = p.getchannel('A').point(lambda v: int(v * opacity))
        p.putalpha(al)
    base.alpha_composite(p, (max(x0, 0), max(y0, 0)))
    return base


def erase_region(img, mask, radius=9, passes=3):
    """用周围像素模糊填充指定区域（去字/去原五官）。"""
    arr = np.asarray(img.convert('RGBA')).astype(np.float32)
    m = np.asarray(mask.convert('L')).astype(np.float32) / 255.0
    filled = arr.copy()
    for _ in range(passes):
        blur = Image.fromarray(filled[..., :3].astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius))
        barr = np.asarray(blur).astype(np.float32)
        w = m[..., None]
        filled[..., :3] = filled[..., :3] * (1 - w) + barr * w
        filled[..., 3] = np.maximum(filled[..., 3], w[..., 0] * arr[..., 3])
    return Image.fromarray(np.clip(filled, 0, 255).astype(np.uint8))


# ----------------------------------------------------------------------------
# 各改造步骤
# ----------------------------------------------------------------------------
CLOTH_HINTS = ('cloth', 'clothes', 'onepiece', 'tops', 'costume', 'dress', 'skirt', 'jacket',
               'costumes', 'cuff', 'sleeve', 'shoes', 'boots', 'socks', 'tie', 'ribbon')
HAIR_HINTS = ('hair',)
EYE_HINTS = ('eye', 'iris')
FACE_HINTS = ('face', 'brow', 'mouth', 'eyeline', 'lash', 'cheek', 'sunburn')


def classify_material(name):
    n = name.lower()
    if any(h in n for h in ('brow', 'eyeline', 'lash', 'mouth', 'cheek', 'sunburn')):
        return 'face'
    if any(h in n for h in EYE_HINTS):
        return 'eye'
    if any(h in n for h in HAIR_HINTS):
        return 'hair'
    if any(h in n for h in FACE_HINTS):
        return 'face'
    if any(h in n for h in CLOTH_HINTS):
        return 'cloth'
    if 'skin' in n or 'body' in n or 'skin_' in n:
        return 'skin'
    return 'other'


def step_whiten_clothes(vrm, pal, log=print):
    done = set()
    for i, m in enumerate(vrm.json.get('materials', [])):
        name = m.get('name', '')
        if classify_material(name) != 'cloth':
            continue
        tex = vrm.tex_source_of_material(name)
        if tex is None:
            continue
        img_i = vrm.image_index_of_texture(tex)
        if img_i is None or img_i in done:
            continue
        img = vrm.image(img_i)
        vrm.set_image(img_i, whiten(img, pal['cloth'], strength=0.94, shadow=0.42))
        done.add(img_i)
        log(f'  [白裙] 服装贴图纯白化: {name}')
    return len(done)


def step_tint_skin(vrm, pal, log=print):
    done = set()
    for i, m in enumerate(vrm.json.get('materials', [])):
        name = m.get('name', '')
        if classify_material(name) not in ('skin', 'face'):
            continue
        tex = vrm.tex_source_of_material(name)
        if tex is None:
            continue
        img_i = vrm.image_index_of_texture(tex)
        if img_i is None or img_i in done:
            continue
        img = vrm.image(img_i)
        img = tint_square(img, pal['skin'], strength=0.22)
        vrm.set_image(img_i, img)
        done.add(img_i)
        log(f'  [肤色] 统一为小凌冷白皮: {name}')
    return len(done)


def step_recolor_hair(vrm, pal, log=print):
    done = set()
    for m in vrm.json.get('materials', []):
        name = m.get('name', '')
        if classify_material(name) != 'hair':
            continue
        pbr = m.get('pbrMetallicRoughness', {})
        # 发色靠纹理
        tex = vrm.tex_source_of_material(name)
        if tex is not None:
            img_i = vrm.image_index_of_texture(tex)
            if img_i is not None and img_i not in done:
                img = vrm.image(img_i)
                vrm.set_image(img_i, retint(img, pal['hair'], strength=0.95, dark_floor=0.52,
                                            contrast=(0.62, 1.12)))
                done.add(img_i)
                log(f'  [发色] 重染为浅亚麻金: {name}')
        # 部分模型用 baseColorFactor 控制发色（如 VRM 1.0）
        if 'baseColorFactor' in pbr:
            pbr['baseColorFactor'] = [pal['hair'][0] / 255, pal['hair'][1] / 255, pal['hair'][2] / 255, pbr['baseColorFactor'][3]]
    return len(done)


def _radial_iris(img, pal, log=print, highlights=True):
    """把虹膜贴图的每个眼瞳圆盘重绘成小凌的湛蓝眼（径向渐变 + 缩瞳环 + 高光）。"""
    a = np.asarray(img.convert('RGBA')).astype(np.float32) / 255.0
    alpha = a[..., 3] > 0.10
    comps = [c for c in components(alpha, min_px=300)]
    comps = sorted(comps, key=lambda c: -c['n'])[:4]
    if not comps:
        return img, 0
    out = a.copy()
    deep = np.array(pal['iris_deep'], np.float32) / 255.0
    mid = np.array(pal['iris'], np.float32) / 255.0
    for c in comps:
        y0, x0, y1, x1 = c['bbox']
        cy, cx = c['centroid']
        r = max((x1 - x0), (y1 - y0)) / 2.0
        if r < 6:
            continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / max(r, 1e-3)
        inner = np.clip(d, 0, 1.2)
        # 外圈深 → 中圈亮蓝 → 瞳孔深
        t = np.clip((inner - 0.55) / 0.45, 0, 1)[..., None]
        col = mid[None, None, :] * (1 - t) + deep[None, None, :] * t
        ring = np.clip((inner - 0.90) / 0.12, 0, 1)[..., None]
        col = col * (1 - 0.45 * ring)
        pupil = np.clip((0.26 - inner) / 0.10, 0, 1)[..., None]
        col = col * (1 - pupil) + np.array([0.06, 0.10, 0.18], np.float32)[None, None, :] * pupil
        if highlights:
            hx, hy = cx - r * 0.34, cy - r * 0.40
            hd = np.sqrt((xx - hx) ** 2 + (yy - hy) ** 2) / max(r * 0.30, 1e-3)
            hl = np.clip(1.0 - hd, 0, 1) ** 1.6
            col = col * (1 - hl[..., None] * 0.85) + 0.98 * hl[..., None] * 0.85
            hx2, hy2 = cx + r * 0.36, cy + r * 0.42
            hd2 = np.sqrt((xx - hx2) ** 2 + (yy - hy2) ** 2) / max(r * 0.18, 1e-3)
            hl2 = np.clip(1.0 - hd2, 0, 1) ** 1.8
            col = col * (1 - hl2[..., None] * 0.5) + 0.92 * hl2[..., None] * 0.5
        sub = out[y0:y1 + 1, x0:x1 + 1]
        keep = alpha[y0:y1 + 1, x0:x1 + 1]
        sub[..., :3] = np.where(keep[..., None], col, sub[..., :3])
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)), len(comps)


def step_recolor_eyes(vrm, pal, face, log=print, debug_dir=None):
    """瞳色 → 小凌的湛蓝眼（程序化径向重绘，保留原眼型/蒙版）。"""
    n = 0
    for m in vrm.json.get('materials', []):
        name = m.get('name', '')
        low = name.lower()
        tex = vrm.tex_source_of_material(name)
        if tex is None:
            continue
        img_i = vrm.image_index_of_texture(tex)
        if img_i is None:
            continue
        if ('iris' in low) or ('eye' in low and not any(k in low for k in ('white', 'highlight', 'eyeline', 'eyelash', 'lash', 'brow', 'line'))):
            img = vrm.image(img_i)
            img2, k = _radial_iris(img, pal)
            if k:
                vrm.set_image(img_i, img2)
                n += k
                log(f'  [瞳色] 湛蓝眼重绘（{k} 个眼瞳）: {name}')
            else:
                vrm.set_image(img_i, retint(img, pal['iris'], strength=0.85, dark_floor=0.18))
                log(f'  [瞳色] 蓝色重染: {name}')
        elif 'highlight' in low:
            img = vrm.image(img_i)
            vrm.set_image(img_i, tint_square(img, (255, 254, 250), strength=0.35))
            log(f'  [高光] 眼球高光微调: {name}')
    return n


def _mouth_uv_box(vrm, face_mat, size, log=print):
    """用几何信息定位嘴部在面部贴图中的矩形区域（VRoid 面部贴图 = 正面投影）。"""
    W, H = size
    pm, hit, _ = vrm.uv_posmap(face_mat, (W, H))
    try:
        eye_y = float(np.mean([vrm.node_position(vrm.humanoid_node('leftEye'))[1],
                               vrm.node_position(vrm.humanoid_node('rightEye'))[1]]))
    except Exception:
        eye_y = None
    P, UV, N, IDX = vrm.geometry(face_mat)
    front = P[P[:, 2] > np.percentile(P[:, 2], 75)]
    chin_y = float(front[:, 1].min())
    if eye_y is None:
        eye_y = float(front[:, 1].max() - 0.06)
    y_mouth = chin_y + 0.36 * (eye_y - chin_y)
    band = hit & (np.abs(pm[..., 0]) < 0.028) & (np.abs(pm[..., 1] - y_mouth) < 0.014) & (pm[..., 2] > 0.015)
    if band.sum() < 8:
        return None, y_mouth
    ys, xs = np.where(band)
    box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    log(f'  [五官] 嘴部定位: y={y_mouth:.3f} → 贴图区域 {box}')
    return box, y_mouth


def _mouth_alpha(crop):
    a = np.asarray(crop.convert('RGB')).astype(np.float32) / 255.0
    red = a[..., 0] - 0.5 * (a[..., 1] + a[..., 2])
    m = np.clip((red - 0.015) * 9.0, 0, 1)
    # 暗线（唇线）
    dark = np.clip((0.55 - a.mean(-1)) * 4.0, 0, 1)
    m = np.maximum(m, dark)
    return Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6))


def step_face_transfer(vrm, pal, face, log=print, debug_dir=None):
    """五官迁移：嘴 → 小凌的软粉小口；眉/睫毛 → 小凌的柔和色。"""
    face_mat = None
    for m in vrm.json.get('materials', []):
        nm = (m.get('name') or '').lower()
        if 'face' in nm and 'skin' in nm:
            face_mat = m['name']
    if face_mat is None:
        for m in vrm.json.get('materials', []):
            if classify_material(m.get('name', '')) == 'face':
                face_mat = m['name']
    for m in vrm.json.get('materials', []):
        name = m.get('name', '')
        low = name.lower()
        tex = vrm.tex_source_of_material(name)
        if tex is None:
            continue
        img_i = vrm.image_index_of_texture(tex)
        img = vrm.image(img_i)
        if 'brow' in low:
            vrm.set_image(img_i, retint(img, pal['brow'], strength=0.9, dark_floor=0.30,
                                        contrast=(0.30, 0.95)))
            log('  [五官] 眉毛 → 小凌的浅棕软眉')
            continue
        if 'eyeline' in low or 'lash' in low:
            vrm.set_image(img_i, retint(img, pal['lash'], strength=0.75, dark_floor=0.12,
                                        contrast=(0.20, 0.95)))
            log('  [五官] 睫毛/眼线 → 小凌的柔和深灰')
            continue
        if name == face_mat or ('face' in low and 'mouth' not in low):
            W, H = img.size
            box, y_mouth = _mouth_uv_box(vrm, face_mat, (W, H), log=log)
            if box is None or not face.mouth:
                continue
            mx0, my0, mx1, my1 = box
            cw = max(mx1 - mx0, 6)
            crop, meta = face.mouth_crop()
            target_w = min(cw * 1.75, W * 0.12)
            scale = target_w / max(meta['w'], 1e-3)
            cy = (my0 + my1) / 2.0
            cx = (mx0 + mx1) / 2.0
            pbox = (cx - target_w / 2, cy - meta['h'] * scale * 0.55,
                    cx + target_w / 2, cy + meta['h'] * scale * 0.45)
            grow = Image.new('L', (W, H), 0)
            ImageDraw.Draw(grow).rectangle((mx0 - 4, my0 - 4, mx1 + 4, my1 + 4), fill=255)
            grown = Image.fromarray(np.maximum(np.asarray(grow),
                                              np.asarray(Image.fromarray(
                                                  np.asarray(grow).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)))))
            img = erase_region(img, grown, radius=5, passes=2)
            m_ = _mouth_alpha(crop)
            img = paste_soft(img, crop, pbox, m_, opacity=0.94)
            log(f'  [五官] 嘴唇 → 小凌的软粉小口（{target_w:.0f}px）')
            if debug_dir:
                Path(debug_dir).mkdir(parents=True, exist_ok=True)
                img.copy().save(Path(debug_dir) / 'debug_face_texture.png')
            vrm.set_image(img_i, img)


def step_stockings(vrm, pal, skin_material, log=print, knee=0.58, ankle=0.03):
    """白丝：在腿部 UV 区域绘制白色过膝长袜。"""
    tex = vrm.tex_source_of_material(skin_material)
    img_i = vrm.image_index_of_texture(tex)
    img = vrm.image(img_i)
    W, H = img.size
    pm, hit, nm = vrm.uv_posmap(skin_material, (W, H))
    leg = hit & (pm[..., 1] > ankle) & (pm[..., 1] < knee) & (np.abs(pm[..., 0]) < 0.30)
    # 膝盖以上的大腿只在正面保留（避免误涂到别的岛）
    if leg.sum() < 10:
        log('  [白丝] 未找到腿部 UV 区域，跳过')
        return 0
    a = np.asarray(img.convert('RGBA')).astype(np.float32) / 255.0
    rgb = a[..., :3]
    ln = luminance_normalized(rgb, 96.0)
    stock = np.array(pal['stocking'], np.float32) / 255.0
    shade = np.clip(0.80 + 0.22 * ln, 0, 1.2)[..., None] * stock[None, None, :]
    # 顶部蕾丝边 + 柔和过渡
    y = pm[..., 1]
    edge = np.clip((knee - y) / 0.035, 0, 1)
    lace = (np.abs(y - (knee - 0.018)) < 0.012)
    alpha = leg.astype(np.float32) * np.clip(edge + 0.15, 0, 1)
    alpha = np.where(lace, np.minimum(alpha + 0.55, 1.0), alpha)
    new_rgb = rgb * (1 - alpha[..., None]) + shade * alpha[..., None]
    pair = np.where(lace, np.minimum(1.0, 1.0 - 0.25 * np.abs(np.sin(pm[..., 0] * 240))), 1.0)
    new_rgb = new_rgb * pair[..., None]
    out = a.copy()
    out[..., :3] = np.clip(new_rgb, 0, 1)
    vrm.set_image(img_i, Image.fromarray((out * 255).astype(np.uint8)))
    log(f'  [白丝] 腿部白色长袜绘制完成（覆盖 {leg.sum()} 个纹理像素）')
    return int(leg.sum())


def step_whiten_underwear(vrm, skin_material, pal, log=print):
    """把身体纹理上的深色内衣改成柔和白色（避免白裙下透出黑色）。"""
    tex = vrm.tex_source_of_material(skin_material)
    img_i = vrm.image_index_of_texture(tex)
    img = vrm.image(img_i)
    a = np.asarray(img.convert('RGBA')).astype(np.float32) / 255.0
    rgb = a[..., :3]
    ln = _srgb_lum(rgb)
    dark = (ln < 0.30) & (a[..., 3] > 0.1)
    if dark.sum() == 0:
        return 0
    soft = np.array([0.93, 0.93, 0.95], np.float32)
    out = a.copy()
    out[..., :3] = np.where(dark[..., None], soft[None, None, :], rgb)
    vrm.set_image(img_i, Image.fromarray((out * 255).astype(np.uint8)))
    log(f'  [底衣] 深色内衣 → 柔和白（{int(dark.sum())} 像素）')
    return int(dark.sum())


def step_hide_accessories(vrm, log=print, keywords=('rabbit', 'glasses', 'ear', 'accessory_glasses')):
    n = 0
    for m in list(vrm.json.get('materials', [])):
        name = (m.get('name') or '')
        low = name.lower()
        if any(k in low for k in keywords):
            removed = vrm.remove_primitives_of_material(name)
            if removed:
                n += removed
                log(f'  [配饰] 隐藏: {name}')
    return n


def step_add_dress(vrm, pal, skin_material, log=print):
    prof, (y0, y1) = torso_profile(vrm, skin_material)
    d = build_dress(vrm, prof, y0, y1)
    tex = _cloth_texture(base=tuple(pal['cloth']), trim=tuple(pal['trim']))
    mi = vrm.add_material('XIAOLING_Dress', base_color=(1, 1, 1, 1), double_sided=True)
    ti = vrm.add_texture_from_image(tex)
    vrm.set_material_texture('XIAOLING_Dress', ti)
    vrm.add_skinned_mesh('XIAOLING_Dress', d['pos'], d['uv'], d['nrm'], d['idx'],
                         d['joints'], d['weights'], mi, node_name='XIAOLING_Dress')
    log(f"  [白裙] 程序化连衣裙已生成：{len(d['pos'])} 顶点 / {len(d['idx'])} 三角面"
        f"（腰 {d['y_waist']:.2f}m 摆 {d['y_hem']:.2f}m）")
    return d


def step_hide_garments(vrm, log=print, keep=()):
    """隐藏原模型的衣服（保留鞋、袜子等小件可选）。"""
    n = 0
    for m in list(vrm.json.get('materials', [])):
        name = m.get('name') or ''
        if classify_material(name) != 'cloth':
            continue
        if any(k.lower() in name.lower() for k in keep):
            continue
        if any(k in name.lower() for k in ('shoe', 'boot')):
            continue
        removed = vrm.remove_primitives_of_material(name)
        if removed:
            n += removed
            log(f'  [清理] 隐藏原服装: {name}')
    return n


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def auto_skin_material(vrm):
    """挑选主身体（皮肤）材质。"""
    best, best_n = None, -1
    for m in vrm.json.get('materials', []):
        name = m.get('name', '')
        low = name.lower()
        if any(k in low for k in ('hair', 'eye', 'face', 'cloth', 'clothes', 'onepiece',
                                  'tops', 'costume', 'shoe', 'tie', 'accessory', 'glasses')):
            continue
        if 'skin' in low or 'body' in low:
            try:
                P, UV, N, IDX = vrm.geometry(name)
            except KeyError:
                continue
            if len(P) > best_n:
                best, best_n = name, len(P)
    if best is None:
        raise SystemExit('未能识别身体(皮肤)材质，请用 --skin-material 指定')
    return best


def build(base, face_png, out, preview_dir=None, log=print, palette_out=None):
    pal = sample_palette_from_face(face_png)
    log(f"  [配色] 抽样：发色 {pal['hair']} / 瞳色 {pal['iris']} / 肤色 {pal['skin']}")
    if palette_out:
        Path(palette_out).write_text(json.dumps(pal, ensure_ascii=False, indent=1), encoding='utf-8')
    vrm = VRM(base)
    face = FaceSource(face_png)
    log(f"  [立绘] 识别到 {len(face.eyes)} 只眼睛，嘴部={'识别' if face.mouth else '未识别'}")
    skin_mat = auto_skin_material(vrm)
    log(f'  [识别] 身体材质 = {skin_mat}')

    step_hide_accessories(vrm, log=log)
    step_hide_garments(vrm, log=log)
    step_whiten_clothes(vrm, pal, log=log)
    step_whiten_underwear(vrm, skin_mat, pal, log=log)
    step_tint_skin(vrm, pal, log=log)
    step_recolor_hair(vrm, pal, log=log)
    step_recolor_eyes(vrm, pal, face, log=log, debug_dir=preview_dir)
    step_face_transfer(vrm, pal, face, log=log, debug_dir=preview_dir)
    step_stockings(vrm, pal, skin_mat, log=log)
    step_add_dress(vrm, pal, skin_mat, log=log)

    meta = vrm.json['extensions']['VRM'].setdefault('meta', {})
    meta.update({
        'title': '小凌 XIAOLING',
        'version': str(meta.get('version', '1.0')) + '+xiaoling',
        'author': 'XIAOLING 项目组（基于原模型改造）',
        'otherLicenseUrl': meta.get('otherLicenseUrl', ''),
        'texture': meta.get('texture'),
    })
    vrm.json['extensions']['VRM'].setdefault('meta', {})['allowedUserName'] = meta.get('allowedUserName', 'OnlyAuthor')
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if log is not None:
        log(f'  [调试] 已改写的贴图 bufferView: {sorted(vrm._dirty_images.keys())}')
    vrm.save(out)
    log(f'  [导出] {out}（{out.stat().st_size/1e6:.1f} MB）')

    if preview_dir:
        from vrm_preview import render_file
        pdir = Path(preview_dir)
        pdir.mkdir(parents=True, exist_ok=True)
        for tag, kw in (('front', dict(W=520, H=800, yaw=0)),
                        ('side', dict(W=520, H=800, yaw=90)),
                        ('back', dict(W=520, H=800, yaw=180)),
                        ('head', dict(W=460, H=460, yaw=0, focus='head'))):
            img = render_file(out, str(pdir / f'xiaoling_{tag}.png'), **kw)
            log(f'  [预览] {pdir / f"xiaoling_{tag}.png"}')
        # 全家福
        from PIL import Image
        ims = [Image.open(pdir / f'xiaoling_{t}.png') for t in ('front', 'side', 'back', 'head')]
        W = sum(i.width for i in ims[:3]) + ims[3].width
        H = max(max(i.height for i in ims[:3]), ims[3].height)
        sheet = Image.new('RGB', (W, H), (238, 238, 244))
        x = 0
        for i in ims:
            sheet.paste(i, (x, 0)); x += i.width
        sheet.save(pdir / 'xiaoling_sheet.png')
    return pal


def main():
    ap = argparse.ArgumentParser(description='VRM → 小凌形象改造流水线')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build', help='执行完整改造')
    b.add_argument('--base', required=True)
    b.add_argument('--face', required=True, help='小凌立绘（如 素材/xiaoling.png）')
    b.add_argument('--out', required=True)
    b.add_argument('--preview', default=None)
    b.add_argument('--palette-out', default=None)
    s = sub.add_parser('sample', help='仅采样立绘配色')
    s.add_argument('--face', required=True)
    a = ap.parse_args()
    if a.cmd == 'sample':
        print(json.dumps(sample_palette_from_face(a.face), ensure_ascii=False, indent=1))
        return
    build(a.base, a.face, a.out, a.preview, palette_out=a.palette_out)


if __name__ == '__main__':
    main()
