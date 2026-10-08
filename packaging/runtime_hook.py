#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyInstaller 运行时钩子：让打包后的程序"开箱即用"。

* 统一 UTF-8（Windows 控制台中文不乱码）
* 无 GPU / 驱动异常时的软件 OpenGL 兜底（Mesa/Gallium 环境变量）
* 关闭无关噪音（HuggingFace 遥测）
* 标记 XIAOLING_FROZEN 供 core.paths 使用
"""
import os
import sys

os.environ.setdefault('XIAOLING_FROZEN', '1')

# ---- 把可写数据隔离到 runtime/ 子目录（仅打包态生效）----
#
# 冲突背景：backend/core/config.py 里
#     app_dir()      = sys.executable 所在目录（未设 XIAOLING_HOME 时）
#     DATA_DIR       = app_dir() / "data"
#     STAR_DIR       = app_dir() / ".star_core"
# 而 Flutter Windows 的 Release 产物里**也有一个 data/ 目录**
# （放着 app.so、icudtl.dat、flutter_assets）。打包时两个产物要合并到同一目录，
# 于是后端的聊天记录/记忆就会直接写进 Flutter 的资源目录里 —— 两者混在一起，
# 既脏，又让"清理数据"这类操作随时可能误伤前端资源，导致应用打不开。
#
# 解法：打包态下把 XIAOLING_HOME 指到 exe 同级的 runtime/，
# 于是 data/ 与 .star_core/ 全部落进 runtime/，与 Flutter 的 data/ 彻底分开。
# 顺带把打包进去的插件从只读资源区搬到这个可写目录，插件开箱即用。
if getattr(sys, 'frozen', False) and not os.environ.get('XIAOLING_HOME'):
    try:
        import shutil
        _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        _home = os.path.join(_exe_dir, 'runtime')
        os.makedirs(_home, exist_ok=True)
        os.environ['XIAOLING_HOME'] = _home
        _mei = getattr(sys, '_MEIPASS', '') or ''
        _src = os.path.join(_mei, '.star_core', 'plugins')
        _dst = os.path.join(_home, '.star_core', 'plugins')
        if _src and os.path.isdir(_src) and not os.path.isdir(_dst):
            os.makedirs(os.path.dirname(_dst), exist_ok=True)
            shutil.copytree(_src, _dst)
    except Exception:
        pass        # 兜底：隔离失败也无非是退回旧行为，不能挡住启动
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

if sys.platform.startswith('win'):
    try:                                    # 高 DPI 感知
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
