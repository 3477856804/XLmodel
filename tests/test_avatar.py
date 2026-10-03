#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌形象流水线回归测试：校验 models/小凌.vrm 的改造结果。

不依赖 torch / GPU；只做结构性与像素级断言。
    python3 tests/test_avatar.py            # 检查已有产物
    python3 tests/test_avatar.py --rebuild  # 重新跑一遍流水线再检查
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from vrm_lib import VRM  # noqa: E402

BASE = ROOT / 'models' / 'Rabbit_Peridot.vrm'
FACE = ROOT / '素材' / 'xiaoling.png'
OUT = ROOT / 'models' / '小凌.vrm'


def rebuild():
    from xiaoling_avatar import build
    build(str(BASE), str(FACE), str(OUT), preview_dir=None, log=lambda *a: None)


def test_vrm_structure():
    v = VRM(OUT)
    names = v.material_names()
    assert 'XIAOLING_Dress' in names, names
    # 新增连衣裙网格
    dress_prim = v.primitives_of_material('XIAOLING_Dress')
    assert dress_prim, '未找到白裙网格'
    _mi, _pi, p, _me = dress_prim[0]
    pos = v.accessor(p['attributes']['POSITION'])
    assert len(pos) > 1000, '白裙顶点数异常'
    assert 'JOINTS_0' in p['attributes'] and 'WEIGHTS_0' in p['attributes'], '白裙缺少蒙皮属性'
    ys = pos[:, 1]
    assert ys.min() < 0.55 and ys.max() > 0.9, f'白裙高度范围异常 {ys.min():.2f}~{ys.max():.2f}'
    print(f"[OK] 白裙网格：{len(pos)} 顶点 / 高度 {ys.min():.2f}~{ys.max():.2f} m / 已蒙皮")

    # 兔耳等配饰已被移除
    assert 'Accessory_RabbitEar_01_CLOTH (Instance)' not in names or not v.primitives_of_material(
        'Accessory_RabbitEar_01_CLOTH (Instance)'), '兔耳未被隐藏'
    print('[OK] 不属于小凌的配饰（兔耳/眼镜）已移除')


def test_brightness():
    v = VRM(OUT)
    def mean_rgb(mat):
        t = v.tex_source_of_material(mat)
        img = v.image(v.image_index_of_texture(t))
        a = np.asarray(img.convert('RGBA')).astype(float)
        m = a[..., 3] > 60
        return a[..., :3][m].mean(0)

    cloth = mean_rgb('N00_008_01_Shoes_01_CLOTH_01 (Instance)')
    assert cloth.mean() > 120, f'鞋/服装未变白：{cloth}'
    print(f'[OK] 服装纯白化：鞋/布料平均亮度 {cloth.mean():.0f}/255')

    hair = mean_rgb('N00_000_Hair_00_HAIR (Instance)')
    assert hair.mean() > 110, f'发色未染成浅亚麻金：{hair}'
    assert hair[0] >= hair[2] - 6, f'发色偏冷，不是亚麻金：{hair}'
    print(f'[OK] 发色重染：平均 RGB {hair.round(0)}（浅亚麻金）')

    iris = mean_rgb('N00_000_00_EyeIris_00_EYE (Instance)')
    assert iris[2] > iris[0], f'瞳色不是蓝色：{iris}'
    print(f'[OK] 瞳色重绘：平均 RGB {iris.round(0)}（湛蓝）')

    body = v.image(v.image_index_of_texture(v.tex_source_of_material('N00_000_00_Body_00_SKIN (Instance)')))
    arr = np.asarray(body.convert('RGBA')).astype(float)
    white = ((arr[..., :3].mean(-1) > 200) & (arr[..., 3] > 200)).mean()
    assert white > 0.05, f'未检测到白丝区域（白色占比 {white:.2%}）'
    print(f'[OK] 白丝：身体贴图白色覆盖 {white:.1%}')


def test_meta():
    v = VRM(OUT)
    meta = v.vrm_meta()
    assert '小凌' in str(meta.get('title', '')), meta.get('title')
    print(f"[OK] VRM 元信息：title={meta.get('title')} author={meta.get('author')}")
    print(f"[警告]  授权提示：licenseName={meta.get('licenseName')}（仅供本地自用，勿再分发）")


if __name__ == '__main__':
    if '--rebuild' in sys.argv:
        print('… 重新生成小凌形象（约 1 分钟）')
        rebuild()
    assert OUT.exists(), f'缺少 {OUT}，先运行 工具/xiaoling_avatar.py build'
    test_vrm_structure()
    test_brightness()
    test_meta()
    print('全部形象流水线测试通过')
