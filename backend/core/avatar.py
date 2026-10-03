#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.avatar —— 3D 数字人宿主（兼容入口）

v1.0 融合版把渲染层从 JS/WebView 全部换成了 **纯 Python**（见 `renderer/` 包）。
本模块保留旧名字与旧 API，内部转发到 `renderer.app.PythonAvatar`：

    from core.avatar import AvatarHost      # 老代码不用改
    host = AvatarHost(engine=app, log=print)
    host.say('你好呀'); host.dance(); host.next_model()

架构（全部在同一个 Python 进程内，零 IPC、零 web 资源）：

    xl.py 引擎 ──方法调用──▶ renderer.app.PythonAvatar
                                   │
                                   ├─ renderer.renderer.AvatarRenderer（模型/姿势/动作/表情/口型）
                                   ├─ renderer.gl.GLRenderer（GPU：GLSL + 骨矩阵，无 GPU 时 OSMesa/llvmpipe）
                                   ├─ renderer.soft.SoftRenderer（连 GL 都没有时的 numpy 光栅兜底）
                                   └─ renderer.window.PetWindow（Qt 透明置顶窗 + 气泡/菜单/输入）
"""
from __future__ import annotations

import json

from renderer.app import PythonAvatar as _PythonAvatar


class AvatarHost(_PythonAvatar):
    """旧名兼容：小凌 3D 数字人宿主。"""

    def __init__(self, engine=None, model=None, scale=1.0, focus='bust', log=print,
                 on_quit=None, width=420, height=680, backend='auto', **kw):
        super().__init__(engine=engine, model=model, width=width, height=height,
                         scale=scale, focus=focus, backend=backend, log=log,
                         on_quit=on_quit, **kw)


def run_headless_probe(port=None):
    """自检用：不依赖 Qt/显示器，直接验证渲染层与形象资源。"""
    try:
        host = AvatarHost(log=lambda *a: None)
        probe = host.headless_probe()
        probe['qt'] = _qt_available()
        probe['ok'] = bool(probe.get('frame_ok')) and probe.get('actions', 0) > 0
        return probe
    except Exception as e:                                                # noqa: BLE001
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def _qt_available():
    for mod in ('PySide6', 'PyQt5'):
        try:
            __import__(mod)
            return mod
        except Exception:                                                 # noqa: BLE001
            continue
    return None


if __name__ == '__main__':
    print(json.dumps(run_headless_probe(), ensure_ascii=False, indent=1))
