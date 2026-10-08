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

# ---- 把可写数据放进「用户目录 / 沙箱」，永久与程序本体分离 ----
#
# 要解决的问题其实有两个，而且都不能忍：
#   1) 撞名：config.py 里 DATA_DIR = app_dir()/"data"，而 Flutter Windows 的
#      Release 产物自带一个 data/（app.so、icudtl.dat、flutter_assets）。
#      两者同名会让聊天记录、记忆直接写进前端资源目录。
#   2) 易失：如果把数据放在 exe 同级，用户把 exe 挪个地方、解压覆盖升级，
#      或者装到 Program Files（不可写），辛苦下载的模型就没了/写不进去。
#
# 解法：打包态下把 XIAOLING_HOME 指到**本机用户数据目录**下的 <沙箱>，
#      · Windows  %LOCALAPPDATA%\Xiaoling\runtime
#      · Linux    $XDG_DATA_HOME 或 ~/.local/share/xiaoling/runtime
#      · macOS    ~/Library/Application Support/Xiaoling/runtime
#   于是 .star_core/（含 models/）与 data/ 全部落在那里：
#      · 程序可以任意移动、覆盖升级，已下载的模型不受影响；
#      · 用户从模型商店下载的 GGUF 就存在这个沙箱里，重启后直接可用；
#      · 不需要管理员权限，Program Files 也能正常用。
#   沙箱根目录见 backend/core/sandbox.py，两者是同一个地方。
if getattr(sys, 'frozen', False) and not os.environ.get('XIAOLING_HOME'):
    try:
        import shutil

        if sys.platform.startswith('win'):
            base = os.environ.get('LOCALAPPDATA') or \
                os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
            root = os.path.join(base, 'Xiaoling')
        elif sys.platform == 'darwin':
            root = os.path.join(os.path.expanduser('~'), 'Library',
                                'Application Support', 'Xiaoling')
        else:
            base = os.environ.get('XDG_DATA_HOME') or \
                os.path.join(os.path.expanduser('~'), '.local', 'share')
            root = os.path.join(base, 'xiaoling')

        _home = os.path.join(root, 'runtime')
        os.makedirs(_home, exist_ok=True)
        os.environ['XIAOLING_HOME'] = _home
        os.environ['XIAOLING_SANDBOX_ROOT'] = root

        # 首次运行：把打包进去的插件从只读资源区搬到这个可写沙箱
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
