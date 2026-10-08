# -*- coding: utf-8 -*-
"""极简 VRM/glTF 软件渲染器（离线校验形象用，无 GPU 依赖）。

用法:
    python3 vrmrender.py model.vrm out.png [--yaw 0] [--pitch 0] [--w 640] [--h 960]
"""
import struct, json, io, math, sys
import numpy as np
from PIL import Image


def read_vrm(path):
    d = open(path, 'rb').read()
    off = 12
    js = None
    bin_ = b''
    while off < len(d):
        clen, ctype = struct.unpack('<II', d[off:off+8]); off += 8
        chunk = d[off:off+clen]; off += clen
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode('utf-8'))
        elif ctype == 0x004E4942:
            bin_ = chunk
    return js, bin_


COMP = {5120: ('i1', 1), 5121: ('u1', 1), 5122: ('i2', 2), 5123: ('u2', 2), 5125: ('u4', 4), 5126: ('f4', 4)}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}


def accessor(js, bin_, idx):
    a = js['accessors'][idx]
    bv = js['bufferViews'][a['bufferView']]
    dt, csz = COMP[a['componentType']]
    nc = NCOMP[a['type']]
    item = csz * nc
    stride = bv.get('byteStride') or item
    base = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    n = a['count']
    if stride == item:
        arr = np.frombuffer(bin_, dtype=dt, count=n * nc, offset=base)
        return arr.reshape(n, nc) if nc > 1 else arr
    out = np.empty((n, nc), dtype=dt)
    for i in range(n):
        out[i] = np.frombuffer(bin_, dtype=dt, count=nc, offset=base + i * stride)
    return out


def texture_image(js, bin_, tex_index, cache=None):
    if cache is not None and tex_index in cache:
        return cache[tex_index]
    src = js['textures'][tex_index].get('source')
    if src is None:
        return None
    im = js['images'][src]
    bv = js['bufferViews'][im['bufferView']]
    off = bv.get('byteOffset', 0); ln = bv['byteLength']
    pil = Image.open(io.BytesIO(bin_[off:off+ln])).convert('RGBA')
    arr = np.asarray(pil).astype(np.float32) / 255.0
    srgb = arr[..., :3]
    lin = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4).astype(np.float32)
    res = (lin, arr[..., 3].astype(np.float32))
    if cache is not None:
        cache[tex_index] = res
    return res


def mat_rot(yaw, pitch):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], np.float32)
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], np.float32)
    return Rx @ Ry


def srgb_from_lin(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def sample(tex, uv):
    rgb, a = tex
    H, W = a.shape
    u = uv[:, 0] % 1.0
    v = uv[:, 1] % 1.0
    x = np.clip((u * W).astype(np.int32), 0, W - 1)
    y = np.clip(((1.0 - v) * H).astype(np.int32), 0, H - 1)
    return rgb[y, x], a[y, x]


def render(js, bin_, W=520, H=800, yaw=0.0, pitch=0.02, margin=0.06,
           background=(0.94, 0.94, 0.96), focus='full', hide=(), only=None):
    prims = []
    for mi, me in enumerate(js.get('meshes', [])):
        if me.get('name') in hide:
            continue
        for pi, p in enumerate(me['primitives']):
            at = p['attributes']
            mat = js['materials'][p['material']] if p.get('material') is not None else {}
            if only is not None and mat.get('name') not in only:
                continue
            pos = accessor(js, bin_, at['POSITION']).astype(np.float32)
            nrm = accessor(js, bin_, at['NORMAL']).astype(np.float32) if 'NORMAL' in at else np.zeros_like(pos)
            uv = accessor(js, bin_, at['TEXCOORD_0']).astype(np.float32) if 'TEXCOORD_0' in at else np.zeros((len(pos), 2), np.float32)
            idx = accessor(js, bin_, p['indices']).astype(np.int32) if 'indices' in p else np.arange(len(pos), dtype=np.int32)
            prims.append(dict(pos=pos, nrm=nrm, uv=uv, idx=idx.reshape(-1, 3), mat=mat, name=mat.get('name')))
    if not prims:
        raise SystemExit('no primitives')
    allpos = np.concatenate([p['pos'] for p in prims])
    ymax = allpos[:, 1].max()
    ymin = allpos[:, 1].min()
    if focus == 'head':
        ymin = ymax - 0.42
    cx = float((allpos[:, 0].min() + allpos[:, 0].max()) / 2)
    cy = (ymin + ymax) / 2
    height = max(ymax - ymin, 1e-3)
    fov = math.radians(16)
    dist = (height * (1 + margin * 2)) / (2 * math.tan(fov / 2))
    R = mat_rot(math.radians(yaw), pitch)
    view_center = np.array([cx if focus != 'full' else 0.0, cy, 0], np.float32)
    f = 1.0 / math.tan(fov / 2)
    aspect = W / H
    zbuf = np.full((H, W), 1e9, np.float32)
    color = np.zeros((H, W, 3), np.float32)
    alpha_buf = np.zeros((H, W), np.float32)
    bg = np.array(background, np.float32)

    def project(P):
        q = (P - view_center) @ R.T
        q = q + np.array([0, 0, dist], np.float32)
        z = q[:, 2]
        ok = z > 1e-4
        z = np.where(ok, z, 1e-4)
        xn = (q[:, 0] * f / (z * aspect))
        yn = (q[:, 1] * f / z)
        sx = (xn * 0.5 + 0.5) * W
        sy = (0.5 - yn * 0.5) * H
        return np.stack([sx, sy, z], 1), ok

    tex_cache = {}

    def tri_raster(vs, shade_fn, alpha_mode, cutoff, double_sided, depth_write):
        x0, y0 = vs[0, 0], vs[0, 1]
        x1, y1 = vs[1, 0], vs[1, 1]
        x2, y2 = vs[2, 0], vs[2, 1]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-9:
            return
        minx = max(int(np.floor(min(x0, x1, x2))), 0)
        maxx = min(int(np.ceil(max(x0, x1, x2))), W - 1)
        miny = max(int(np.floor(min(y0, y1, y2))), 0)
        maxy = min(int(np.ceil(max(y0, y1, y2))), H - 1)
        if minx > maxx or miny > maxy:
            return
        xs = np.arange(minx, maxx + 1) + 0.5
        ys = np.arange(miny, maxy + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        w0 = ((x1 - x0) * (gy - y0) - (gx - x0) * (y1 - y0)) / area
        w1 = ((gx - x0) * (y2 - y0) - (x2 - x0) * (gy - y0)) / area
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            return
        z = w0 * vs[0, 2] + w1 * vs[1, 2] + w2 * vs[2, 2]
        sub_z = zbuf[miny:maxy + 1, minx:maxx + 1]
        bias = 0.0 if depth_write else 2e-3
        vis = inside & ((z - bias < sub_z) if True else np.ones_like(inside, bool))
        if not vis.any():
            return
        ww = np.stack([w0, w1, w2], -1)[vis]
        rgb, al = shade_fn(ww)
        rr = color[miny:maxy + 1, minx:maxx + 1]
        ra = alpha_buf[miny:maxy + 1, minx:maxx + 1]
        if alpha_mode == 'MASK':
            keep = al >= cutoff
            if not keep.any():
                return
        else:
            keep = np.ones(len(ww), bool)
        ii = np.where(vis)
        if alpha_mode == 'BLEND':
            a = np.clip(al, 0, 1)[:, None]
            tgt = rr[ii]
            rr[ii] = tgt * (1 - a) + rgb * a
            ra[ii] = np.clip(ra[ii] * (1 - al) + al, 0, 1)
        else:
            rr[ii] = rgb
            ra[ii] = 1.0
        if depth_write:
            if alpha_mode == 'MASK':
                sel = (ii[0][keep], ii[1][keep])
                sub_z[sel] = z[sel]
            else:
                sub_z[ii] = z[ii]

    L1 = np.array([0.35, 0.45, 0.82], np.float32); L1 /= np.linalg.norm(L1)
    L2 = np.array([-0.6, 0.15, 0.6], np.float32); L2 /= np.linalg.norm(L2)

    opaque_tris = []   # (depth, vs3, uvs, n3, alpha_mode, cutoff, double_sided, tex, bcf, unlit)
    blend_tris = []
    for pi in range(len(prims)):
        P = prims[pi]
        mat = P['mat']
        alpha_mode = mat.get('alphaMode', 'OPAQUE')
        double_sided = mat.get('doubleSided', False)
        cutoff = mat.get('alphaCutoff', 0.5)
        unlit = 'KHR_materials_unlit' in (mat.get('extensions') or {})
        pbr = mat.get('pbrMetallicRoughness', {})
        bcf = np.array(pbr.get('baseColorFactor', [1, 1, 1, 1]), np.float32)
        tex = texture_image(js, bin_, pbr['baseColorTexture']['index'], tex_cache) if 'baseColorTexture' in pbr else None
        nrm_R = P['nrm'] @ R.T
        vs, ok = project(P['pos'])
        for t in P['idx']:
            if not (ok[t[0]] and ok[t[1]] and ok[t[2]]):
                continue
            vs3 = vs[t]
            uvs = P['uv'][t]
            n3 = nrm_R[t]
            tn = n3.mean(0)
            if not double_sided and tn[2] < 0:
                continue
            depth = float(vs3[:, 2].mean())
            item = (depth, vs3, uvs, n3, alpha_mode, cutoff, double_sided, tex, bcf, unlit)
            if alpha_mode == 'BLEND':
                blend_tris.append(item)
            else:
                opaque_tris.append(item)

    def draw(item):
        depth, vs3, uvs, n3, alpha_mode, cutoff, double_sided, tex, bcf, unlit = item

        def shade(ww, tex=tex, bcf=bcf, unlit=unlit, uvs=uvs, n3=n3):
            uv = ww @ uvs
            if tex is not None:
                rgb, al = sample(tex, uv)
            else:
                rgb = np.ones((len(uv), 3), np.float32); al = np.ones(len(uv), np.float32)
            al = al * bcf[3]
            rgb = rgb * bcf[:3]
            if not unlit:
                nn = ww @ n3
                nn = nn / (np.linalg.norm(nn, axis=1, keepdims=True) + 1e-6)
                sh = 0.45 + 0.55 * (np.clip(nn @ L1, 0, 1) + 0.30 * np.clip(nn @ L2, 0, 1))
                rgb = rgb * np.clip(sh, 0, 1.6)[:, None]
            return rgb, al

        tri_raster(vs3, shade, alpha_mode, cutoff, double_sided, alpha_mode != 'BLEND')

    for it in opaque_tris:
        draw(it)
    blend_tris.sort(key=lambda x: -x[0])          # 远 → 近（画家算法）
    for it in blend_tris:
        draw(it)

    out = srgb_from_lin(color)
    a = alpha_buf[..., None]
    out = out * a + bg[None, None, :] * (1 - a)
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def render_file(path, out, **kw):
    js, bin_ = read_vrm(path)
    img = render(js, bin_, **kw)
    img.save(out)
    return img


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('model'); ap.add_argument('out')
    ap.add_argument('--yaw', type=float, default=0.0)
    ap.add_argument('--pitch', type=float, default=0.02)
    ap.add_argument('--w', type=int, default=520)
    ap.add_argument('--h', type=int, default=800)
    ap.add_argument('--focus', default='full')
    a = ap.parse_args()
    render_file(a.model, a.out, W=a.w, H=a.h, yaw=a.yaw, pitch=a.pitch, focus=a.focus)
    print('saved', a.out)
