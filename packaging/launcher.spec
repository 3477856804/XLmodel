# -*- mode: python ; coding: utf-8 -*-
"""小凌 · 单文件启动器的 PyInstaller 配置。

与 backend.spec 的关键差异：
    * onefile —— 整个启动器就是一个 exe，方便把资源追加到它尾部
    * windowed（console=False）—— 用户双击后不应该再冒出一个黑窗口
    * 依赖极简 —— 只用标准库，所以产物很小（约 10 MB）

真正的运行资源（Flutter 界面 + Python 后端）**不在这里面**，它们由
packaging/build_single_exe.py 打成 zip 后追加到本 exe 的尾部，
首次运行时由 launcher.py 释放到 %LOCALAPPDATA%\\Xiaoling\\app。
"""
import os

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

block_cipher = None

a = Analysis(
    [os.path.join(SPECPATH, 'launcher.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 启动器不需要任何第三方库，全部排掉以压体积
        'torch', 'transformers', 'numpy', 'PIL', 'llama_cpp', 'grpc',
        'pandas', 'scipy', 'matplotlib', 'tkinter', 'pytest', 'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # 关键：不留控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
