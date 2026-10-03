# -*- mode: python ; coding: utf-8 -*-
"""小凌 XIAOLING · 统一 PyInstaller 打包配置（全平台）

用法（一般不用直接调它，用 打包/build.py）：
    pyinstaller 打包/xiaoling.spec --noconfirm --distpath dist --workpath build/pyi

环境变量开关：
    XIAOLING_ONEFILE=1     打成单文件（适合 --lite；含 VRM/大依赖时不推荐）
    XIAOLING_LITE=1        精简版：不带 torch/PySide6/全量资源（软件渲染 + 联网/平台功能）
    XIAOLING_ICON=path     自定义图标（.ico/.icns/.png）
"""
import os
import sys
from pathlib import Path

PROJECT = Path(SPECPATH).parent                      # 项目根（打包/ 的上一级）
ONEFILE = os.environ.get('XIAOLING_ONEFILE') == '1'
LITE = os.environ.get('XIAOLING_LITE') == '1'
ICON = os.environ.get('XIAOLING_ICON', '')

# ---------------------------------------------------------------- 打包资源
datas = [(str(PROJECT / d), d) for d in
         ('core', 'renderer', 'assets', 'sounds', '技能', '数据', '脚本',
          '工具', 'docs', '打包') if (PROJECT / d).exists()]
model_dir = PROJECT / '角色模型'
action_dir = PROJECT / '动作资产'
if LITE:                                             # 精简版只带小凌本体 + 少量动作
    keep_models = ['小凌.vrm']
    keep_actions = ['待机站立.vrma', '待机，原地晃动.vrma', '打招呼.vrma', '比耶.vrma',
                    'dance_舞蹈5.vrma', 'dance_舞蹈12.vrma']
else:
    keep_models = [p.name for p in sorted(model_dir.glob('*.vrm'))]
    keep_actions = [p.name for p in sorted(action_dir.glob('*.vrma'))]

# 把筛选后的模型/动作加入打包资源（只读资源，跟随程序）
for _n in keep_models:
    if (model_dir / _n).exists():
        datas.append((str(model_dir / _n), '角色模型'))
for _n in keep_actions:
    if (action_dir / _n).exists():
        datas.append((str(action_dir / _n), '动作资产'))

# ---------------------------------------------------------------- 隐藏导入
hidden = [
    'core.config', 'core.paths', 'core.growth', 'core.peft_train', 'core.avatar',
    'core.fusion', 'core.rag', 'core.search', 'core.vision', 'core.tts', 'core.asr',
    'core.perception', 'core.proactive', 'core.reminder', 'core.imagen', 'core.filebox',
    'core.selftest',
    # 成长/评估链路上的模块：多由 core.growth 在函数体内延迟 import，
    # 显式列出以免打包版在跑成长流程时才报 ModuleNotFoundError。
    'core.device', 'core.eval', 'core.growth_store', 'core.lifecycle',
    'core.rank', 'core.throttle', 'core.voices', 'core.launcher_ui',
    'renderer.app', 'renderer.renderer', 'renderer.gl', 'renderer.soft', 'renderer.model',
    'renderer.pose', 'renderer.gltf', 'renderer.vrma', 'renderer.camera', 'renderer.window',
    'renderer.settings', 'renderer.lipsync',
    # 延迟导入的 UI 模块：它们只在函数体内 / __main__ 分支里 import，
    # 静态分析通常能找到，但这类"运行时才用"的模块必须显式列出，
    # 否则打包版可能直到打开向导 / 对话窗口 / 工作台时才报 ModuleNotFoundError。
    'renderer.wizard', 'renderer.chat_ui', 'renderer.startup_ui',
    'renderer.i18n', 'renderer.dashboard',
    # v0.0.3 新增：粉色少女风主题 + FBX 模型桥接
    'renderer.theme', 'renderer.fbx_loader',
]
if not LITE:
    hidden += ['OpenGL', 'OpenGL.GL', 'OpenGL.osmesa', 'OpenGL.raw.osmesa.mesa',
               'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'PySide6.QtOpenGLWidgets']
excludes = ['matplotlib', 'tkinter.test', 'test', 'unittest.test', 'PySide6.QtWebEngineCore',
            'PySide6.Qt3DCore', 'PySide6.QtQuick', 'PySide6.QtDesigner', 'PySide6.QtMultimedia',
            'tkinter', 'IPython', 'jupyter', 'notebook', 'tensorboard', 'onnxruntime',
            'PyQt5', 'PyQt6']
if LITE:
    excludes += ['torch', 'transformers', 'peft', 'accelerate', 'PySide6', 'PyOpenGL',
                 'numpy.f2py', 'cv2', 'sounddevice', 'pyttsx3']

block_cipher = None
a = Analysis([str(PROJECT / 'xl.py')],
             pathex=[str(PROJECT)],
             binaries=[],
             datas=datas,
             hiddenimports=hidden,
             hookspath=[],
             runtime_hooks=[str(PROJECT / '打包' / 'runtime_hook.py')],
             excludes=excludes,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe_kwargs = dict(name='xiaoling', debug=False, bootloader_ignore_signals=False, strip=False,
                  upx=False, console=True, disable_windowed_traceback=False)
if ICON and Path(ICON).exists():
    exe_kwargs['icon'] = ICON

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], runtime_tmpdir=None, **exe_kwargs)
    COLLECT = None
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_kwargs)
    # contents_directory='.' → 依赖与资源平铺在程序目录（PyInstaller 6 默认放进 _internal/，
    # 会让 xl.py 的 BASE_DIR=可执行文件目录 找不到 技能/数据/角色模型）
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='xiaoling',
                   contents_directory='.')

# macOS：打包成 .app
if sys.platform == 'darwin' and not ONEFILE:
    app = BUNDLE(coll, name='小凌.app', icon=exe_kwargs.get('icon'),
                 bundle_identifier='app.xiaoling.desktop',
                 info_plist={'CFBundleDisplayName': '小凌 XIAOLING',
                             'CFBundleShortVersionString': '0.0.2',
                             'NSHighResolutionCapable': True,
                             'LSBackgroundOnly': False,
                             'NSMicrophoneUsageDescription': '语音输入需要麦克风',
                             'NSScreenCaptureUsageDescription': '视觉感知（看屏幕）需要屏幕录制权限'})
