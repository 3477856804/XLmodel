#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyInstaller 运行时钩子：让打包后的程序"开箱即用"。

* 统一 UTF-8（Windows 控制台中文不乱码）
* 无 GPU / 驱动异常时的软件 OpenGL 兜底（Mesa/Gallium 环境变量）
* 关闭无关噪音（Qt 高分屏、HuggingFace 遥测）
* 标记 XIAOLING_FROZEN 供 core.paths 使用
"""
import os
import sys

os.environ.setdefault('XIAOLING_FROZEN', '1')
if os.environ.get('XIAOLING_LITE') == '1':        # 精简版没有 PyOpenGL → 直接用软件光栅
    os.environ.setdefault('XIAOLING_RENDER_BACKEND', 'soft')
# 软件渲染（无 GPU）时自动缩小画布与面数，保证还有可用帧率；用户可自行覆盖
os.environ.setdefault('XIAOLING_WINDOW_SIZE', os.environ.get('XIAOLING_WINDOW_SIZE', '420x680'))
os.environ.setdefault('XIAOLING_SOFT_MAX_TRIS', os.environ.get('XIAOLING_SOFT_MAX_TRIS', '12000'))
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# 无独显 / 驱动异常时，Mesa 软件光栅还能跑：
#   · llvmpipe 的 LLVM JIT 在部分虚拟化 CPU 上会触发非法指令 → 关掉 JIT 优化
#   · 需要真 llvmpipe 提速时可设 XIAOLING_GALLIUM_DRIVER=llvmpipe
if not os.environ.get('XIAOLING_GALLIUM_DRIVER'):
    os.environ.setdefault('GALLIVM_PERF', 'nopt')

# 不联网也要能用：禁止 transformers/onnx 的在线探测
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')

# Qt：透明窗 + 高 DPI 行为（Windows 上避免缩放糊成一团）
os.environ.setdefault('QT_LOGGING_RULES', '*.debug=false')
os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')

if sys.platform.startswith('win'):
    try:                                    # 高 DPI 感知（PySide6 未加载前设置）
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
