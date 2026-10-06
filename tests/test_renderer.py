#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染层回归测试：确认 3D 数字人**全部由 Python 渲染**且功能正确。

覆盖：
  1. 项目里不再有任何 JS/HTML 渲染层文件（语言统一性硬约束）
  2. glTF/VRM 解析 + 蒙皮（绑定姿势下蒙皮矩阵应为单位阵）
  3. OpenGL(GPU/llvmpipe) 后端能出图；CPU 光栅后端能出图
  4. 表情形变会改变画面；VRMA 动作会改变骨骼；弹簧骨数值稳定
  5. 口型时间轴 + 动作库可用
"""
import glob
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend'))
# 资源统一在 resources/ 下
MODELS_DIR = ROOT / 'resources' / 'models'
ANIM_DIR = ROOT / 'resources' / 'animations'
os.environ.setdefault('XIAOLING_GALLIUM_DRIVER', os.environ.get('XIAOLING_GALLIUM_DRIVER', 'llvmpipe'))


IGNORE_PARTS = ('/.git/', '/.venv/', '/venv/', '/docs/', '/build/', '/dist/', '/.buildozer/',
                '/.gradle/', '/node_modules/', '/app/build/', '/.pyinstaller/')


def _source_files(pattern):
    out = []
    for p in ROOT.rglob(pattern):
        s = '/' + str(p.relative_to(ROOT)).replace('\\', '/')
        if any(part in s for part in IGNORE_PARTS):
            continue
        out.append(str(p.relative_to(ROOT)))
    return out


def test_no_javascript():
    """语言统一性硬约束：源码里不能有 JS/HTML/CSS（构建产物与上游文档除外）。"""
    js = _source_files('*.js')
    html = _source_files('*.html')
    css = _source_files('*.css')
    assert not js, f'仍有 JS 文件：{js[:5]}'
    assert not html, f'仍有 HTML 文件：{html[:5]}'
    assert not css, f'仍有 CSS 文件：{css[:5]}'
    assert not (ROOT / 'avatar').exists(), '旧的 JS 渲染层目录 avatar/ 仍存在'
    print('[OK] 语言统一：源码内已无任何 JS/HTML/CSS（3D 渲染层也是 Python）')


def test_model_and_skinning():
    from renderer.model import VRMModel
    from renderer.pose import Pose
    m = VRMModel(MODELS_DIR / '小凌.vrm')
    assert len(m.humanoid) > 40, '缺少人形骨骼'
    assert m.expressions, '缺少表情（BlendShape）'
    assert m.triangle_count() > 5000
    pose = Pose(m)
    pose.update_world()
    skin = m.skins[0]
    worst = 0.0
    for k, node in enumerate(skin['joints'][:40]):
        worst = max(worst, float(np.abs(pose.world[node] @ skin['ibm'][k] - np.eye(4)).max()))
    assert worst < 1e-3, f'绑定姿势下蒙皮矩阵不是单位阵（最大偏差 {worst}）'
    print(f'[OK] VRM 解析/蒙皮正确（{m.triangle_count()} 面 · {len(m.humanoid)} 骨 · '
          f'{len(m.expressions)} 表情组 · 绑定姿势偏差 {worst:.1e}）')


_CACHE = {}


def _gl_renderer():
    """同一个进程里只建一个 GL 上下文（OSMesa 多上下文易崩），测试内复用。"""
    if 'gl' not in _CACHE:
        from renderer.renderer import AvatarRenderer
        _CACHE['gl'] = AvatarRenderer(backend='gl', width=200, height=300,
                                      log=lambda *a: None)
    return _CACHE['gl']


GL_UNAVAILABLE_SKIP = 'GL_UNAVAILABLE_SKIP'


def test_gl_render():
    r = _gl_renderer()
    if r.backend_kind != 'gl':
        # 无 OpenGL 上下文（无显示/无 Mesa 驱动的容器与 CI）→ 明确跳过，不当作代码缺陷
        msg = str(r.last_error or '')
        if any(k in msg for k in ('GLContextError', 'OpenGL 上下文', 'Egl', 'EGL', 'libGL')):
            print(f'[SKIP] 环境无可用 OpenGL 上下文（{msg}）→ 跳过 GL 断言；'
                  f'软件光栅后端仍由后续用例覆盖')
            return
    assert r.backend_kind == 'gl', f'GL 后端不可用：{r.last_error}'
    img = r.frame(with_pose=False)
    assert img.shape == (300, 200, 3) and img.std() > 5, 'GL 后端没有画出有效画面'
    print(f"[OK] OpenGL 后端出图正常（{r.context.info()['renderer'][:40]}，像素标准差 {img.std():.1f}）")
    return r


def test_morph_changes_image():
    r = _gl_renderer()
    r.idle()
    a = r.frame(with_pose=False).astype(np.int16)
    r.set_expression('Blink', 1.0)
    for _ in range(6):
        b = r.frame(dt=1 / 30).astype(np.int16)
    diff = float(np.abs(a - b).mean())
    assert diff > 0.15, f'表情没有改变画面（平均差 {diff}）'
    print(f'[OK] 表情形变生效（眨眼前后平均像素差 {diff:.2f}）')


def test_vrma_and_springs():
    from renderer.model import VRMModel
    from renderer.pose import Pose, SpringBones
    from renderer.vrma import VRMAFile
    m = VRMModel(MODELS_DIR / '小凌.vrm')
    files = sorted(glob.glob(str(ANIM_DIR / '*.vrma')))
    assert len(files) >= 10, '动作库缺失'
    ok, empty = 0, []
    for f in files:
        clip = VRMAFile(f).clip(m)
        if clip and clip.tracks:
            ok += 1
        else:
            empty.append(Path(f).name)
    assert ok >= len(files) - 1, f'{len(empty)} 个动作无法重定向：{empty[:3]}'
    pose = Pose(m)
    sb = SpringBones(m)
    clip = VRMAFile(files[0]).clip(m)
    head_before = pose.bone_world('head')[:3, 3].copy()
    for i in range(40):
        clip.apply(pose, i / 30.0)
        sb.update(pose, 1 / 30)
    pose.update_world()
    assert bool(np.isfinite(np.array(pose.world)).all()), '弹簧骨产生非有限数值'
    head_after = pose.bone_world('head')[:3, 3]
    assert float(np.linalg.norm(head_after - head_before)) > 1e-3, '动作没有驱动骨骼'
    print(f'[OK] VRMA 动作 {ok}/{len(files)} 可播放；弹簧骨稳定；骨骼被驱动 '
          f'(头部位移 {float(np.linalg.norm(head_after - head_before)):.3f} m)')


def test_soft_backend():
    """CPU 光栅后端放到子进程里测：避免与 OSMesa 上下文在同一进程互相干扰。"""
    import subprocess
    backend_dir = str(ROOT / 'backend')
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "from renderer.renderer import AvatarRenderer\n"
        "r = AvatarRenderer(backend='soft', width=140, height=200, log=lambda *a: None)\n"
        "img = r.frame(with_pose=False)\n"
        "assert r.backend_kind == 'soft' and img.shape == (200,140,3) and img.std() > 5\n"
        "print(r.soft_renderer.stats()['triangles'])\n" % backend_dir)
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True,
                         timeout=600, cwd=str(ROOT))
    assert out.returncode == 0, f'CPU 光栅后端失败：{out.stderr[-400:]}'
    print(f'[OK] CPU 纯 numpy 光栅后端出图正常（{out.stdout.strip().splitlines()[-1]} 面）')


def test_lipsync():
    from renderer.lipsync import LipSync
    ls = LipSync()
    dur = ls.play('你好呀，我是小凌！Hello there')
    assert dur > 0.5
    seen = set()
    for _ in range(60):
        ls.update(1 / 60)
        seen |= {k for k, v in ls.weights().items() if v > 0.05}
    assert seen, '口型没有产生任何权重'
    print(f'[OK] 口型时间轴正常（{dur:.2f}s，出现口型 {sorted(seen)}）')


if __name__ == '__main__':
    test_no_javascript()
    test_model_and_skinning()
    test_gl_render()
    test_morph_changes_image()
    test_vrma_and_springs()
    test_soft_backend()
    test_lipsync()
    print('全部渲染层测试通过（3D 数字人完全由 Python 渲染）')
