#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer —— 小凌 3D 数字人渲染层（100% Python）

    gltf.py       glTF/VRM 二进制解析
    model.py      VRM 语义层（人形骨骼 / 表情 / 弹簧骨 / 材质）
    pose.py       姿势 / 蒙皮 / 表情形变 / 弹簧骨
    vrma.py       VRMA 动作解析与重定向
    camera.py     相机与投影
    gl.py         OpenGL(GPU) 后端（GLSL + 骨矩阵 uniform）
    soft.py       numpy 软件光栅化后端（无 GPU 兜底）
    lipsync.py    文本 → 口型
    renderer.py   统一门面 AvatarRenderer（模型/动作/表情/口型/每帧出图）
    window.py     Qt 透明置顶窗 + 气泡/菜单/输入框（桌面宠物外壳）
    settings.py   设置对话框（取代旧版渲染层的 HTML 设置页）
    app.py        与 xl.py 引擎对接的宿主（API 与原 Electron 版对齐）
"""
__all__ = ['gltf', 'model', 'pose', 'vrma', 'camera', 'gl', 'soft', 'lipsync',
           'renderer', 'window', 'settings', 'app']
