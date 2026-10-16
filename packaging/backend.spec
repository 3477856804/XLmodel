# -*- mode: python ; coding: utf-8 -*-
"""小凌 · Python 后端打包配置（PyInstaller，onedir 目录模式）

产出：backend.exe —— 与 Flutter 前端 frontend.exe 放在**同一个目录**。
前端 main.dart 的 _startBackend() 会在 exe 同目录找 backend.exe，找到就以
    backend.exe --port 50051 --no-web --web-port <空闲端口>
拉起。所以打包产物的目录结构必须与前端 Release 目录合并，不能分开放。

关键取舍：排除 torch / transformers
    本机 venv(xiaoling312) 是 --system-site-packages，torch 2.11.0+cu128
    实际躺在系统 Python312 里，体积 4.2G。打进包里产物会有数 GB，完全不可接受。
    而全项目**没有任何顶层 `import torch`**，全部是函数内延迟导入：
        · GGUF 推理   → backend/core/model.py  `from llama_cpp import Llama`  （不依赖 torch，保留）
        · HF safetensors 推理 → model.py:2071  `from transformers import ...` （依赖 torch，打包后不可用）
        · LoRA 训练   → growth.py:1233/1818    `from transformers import ...`（依赖 torch，打包后不可用）
    排除后程序照常启动，UI / 3D / 设置 / 模型扫描全部正常，GGUF 模型可正常聊天；
    仅 safetensors 格式模型与训练功能需要完整版（改用未裁剪的 spec 打）。
"""
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

# 与 packaging/build.py 的环境变量开关保持一致：
#   XIAOLING_ONEFILE=1  → 单文件（本地 Linux/macOS 复现脚本与 CI 用，便于塞进 bundle）
#   默认               → onedir（build.py 正式产物，冷启动快、资源平铺）
ONEFILE = os.environ.get('XIAOLING_ONEFILE') == '1'

# ---------------------------------------------------------------- 路径
# spec 位于 packaging/，项目根在其上一层
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
sys.path.insert(0, PROJECT_ROOT)

block_cipher = None

# ------------------------------------------------- llama_cpp（GGUF 推理运行时）
# 它自带 lib/*.dll（ggml 后端），必须整包收，否则 GGUF 模型加载即崩。
llama_datas, llama_binaries, llama_hidden = collect_all('llama_cpp')

# ---------------------------------------------------------------- 源码模块
# backend.core.* 用 `from core.xxx` 短名导入，静态分析扫不全，这里显式列全。
CORE_MODULES = [
    'agent', 'browser_tool', 'channels', 'config', 'context', 'dsh_compat',
    'engine', 'fileops', 'fusion', 'git_tool', 'growth', 'knowledge_base',
    'mcp_client', 'memory', 'model', 'multimodal', 'options',
    'persona_presets', 'plugin_sdk', 'plugin_system', 'quarantine', 'sandbox',
    'search', 'security_center', 'sub_agent', 'system', 'terminal', 'tools',
    'updater', 'webpanel', 'workflow_engine',
]
RPC_MODULES = ['server', 'xiaoling_pb2', 'xiaoling_pb2_grpc']
RENDERER_MODULES = ['stage', 'vrm_gltf']

hiddenimports = (
    ['backend', 'backend.core', 'backend.rpc', 'backend.renderer']
    + ['backend.core.' + m for m in CORE_MODULES]
    + ['backend.rpc.' + m for m in RPC_MODULES]
    + ['backend.renderer.' + m for m in RENDERER_MODULES]
    + llama_hidden
    + collect_submodules('grpc')
    # 这两个是「函数内惰性导入」的 TTS 运行时，静态分析扫不到，必须显式登记，
    # 否则打包后 import edge_tts / import pyttsx3 直接 ModuleNotFoundError，
    # 音色功能（在线 edge-tts + 离线 pyttsx3 兜底）在包内完全失效。
    + ['edge_tts', 'edge_tts.exceptions', 'pyttsx3']
)
# 插件是 importlib.util 动态加载的，静态分析看不到，逐个显式登记
hiddenimports += ['plugins.builtin.hello_world.main']

# ---------------------------------------------------------------- 数据文件
# 格式：(源路径, 产物内相对路径)
#
# 注意 resources/models 下有个 ty.fbx（22MB，FBX 格式）—— 渲染器只认 VRM，
# 这个文件既加载不了又白占体积，打包时用 TOC 过滤掉（源码里的文件不动）。
def _vrm_only():
    """只收 resources/models 下的 .vrm，剔除 fbx 等非 VRM 资源。"""
    out = []
    d = os.path.join(PROJECT_ROOT, 'resources', 'models')
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        if name.lower().endswith('.vrm'):
            out.append((os.path.join(d, name), os.path.join('resources', 'models')))
    return out


def _star_core_plugins():
    """.star_core/plugins 下的插件（整目录拷贝）。

    每个插件是「一个目录 + main.py + plugin.json」两件套 —— **只拷 .py 是不够的**：
    plugin.json 缺失时 plugin_system 会逐条报「插件缺少 plugin.json/manifest.json」
    并跳过加载，表面上程序正常，实际 11 个插件全废，且只在打包后才暴露。

    刻意排除顶层 state.json：那是插件启用状态的开发机快照，带到别的机器没有意义，
    运行时会按需重新生成。

    另外注意：.star_core/models（老板本机 6.2G 的 GGUF 模型库）与
    xiaoling_config.json（写死了开发机绝对路径）都不在收集范围内。
    """
    out = []
    d = os.path.join(PROJECT_ROOT, '.star_core', 'plugins')
    if not os.path.isdir(d):
        return out
    for root, _dirs, files in os.walk(d):
        for f in sorted(files):
            if f.lower() == 'state.json':
                continue
            src = os.path.join(root, f)
            rel_dir = os.path.relpath(root, d)
            dest = os.path.join('.star_core', 'plugins') \
                if rel_dir == '.' else os.path.join('.star_core', 'plugins', rel_dir)
            out.append((src, dest))
    return out


def _data_dir(rel: str, dest: str | None = None):
    """把一个仓库内目录加进 datas；**目录不存在时跳过而不是让构建失败**。

    为什么需要：`resources/animations`（*.vrma）、`resources/models`（*.vrm）
    与 `skills/` 都被 .gitignore 排除，全新 clone 里根本不存在。
    PyInstaller 对 datas 里不存在的源路径是**硬报错**：
        ERROR: Unable to find '...\\resources\\animations' when adding binary
               and data files.
    结果就是「从仓库拉下来照文档打不出包」，与"源码自主、本地可完全自建"的
    定位直接冲突。这里改为按存在性收集，缺失只警告（运行时 config.ensure_dirs()
    会在用户沙箱里补建这些目录）。
    """
    p = os.path.join(PROJECT_ROOT, rel)
    if not os.path.isdir(p):
        print(f'[backend.spec] 跳过不存在的资源目录：{rel}（被 .gitignore 排除）')
        return []
    return [(p, dest or rel)]


datas = []
# 3D 查看器：viewer.html + vendor(three.js / three-vrm / GLTFLoader / BufferGeometryUtils)
# 桌面端真 3D 全靠它，少了任何一个 .js，WebView 里就是一片黑。
datas += _data_dir('resources/web', 'resources/web')
# 动作库（.vrma）—— 仓库不含 *.vrma，缺失时由发行包/用户素材补入
datas += _data_dir('resources/animations', 'resources/animations')
# 贴图 / 音效
datas += _data_dir('resources/materials', 'resources/materials')
datas += _data_dir('resources/sounds', 'resources/sounds')
# 角色模型（.vrm）—— 主体收集见 _vrm_only()，这里只保证目录被带上
datas += _data_dir('resources/models', 'resources/models')
# 内置插件 + 技能（能收集就收集，缺失不阻断构建）
datas += _data_dir('plugins', 'plugins')
datas += _data_dir('skills', 'skills')
# proto 契约定义（保留原始 .proto，便于排查与后续重新生成）
datas += _data_dir('shared/proto', 'shared/proto')
# 源码兜底：把 backend/ 原样拷进产物。
# main.py 会把 sys.path 指向该目录，源码里大量 `from core.xxx import ...`
# 靠它解析；即使 meta path 别名兜底失灵，核心功能也不会静默失效。
datas += _data_dir('backend', 'backend')
datas += _vrm_only()
datas += _star_core_plugins()
datas += llama_datas

binaries = llama_binaries

# ---------------------------------------------------------------- 裁剪
# torch 系列：4.2G，且全为延迟导入，缺席不影响启动（见文件头说明）
# 其余是打包过程自身与被误收的重型科学计算库
excludes = [
    # ---- 重型推理/训练栈：4.2G，且全为延迟导入，缺席不影响启动 ----
    'torch', 'transformers', 'nvidia', 'triton', 'xformers', 'peft',
    # modelscope 尤其危险：它 __init__ 时会去 JIT 编译 CUDA 扩展，
    # PyInstaller 构建期的 import_library 子进程会因此直接崩掉
    # （RuntimeError: Ninja is required to load C++ extensions）。
    'modelscope',
    # ---- 其他可选重型项：代码里都是 try/except ImportError 兜底 ----
    'cv2', 'whisper', 'pyaudio', 'pytesseract',
    # ---- 科学计算 / 可视化：本项目用不到 ----
    'scipy', 'sklearn', 'pandas', 'matplotlib', 'tensorflow',
    'jupyter', 'notebook', 'IPython', 'pytest', 'setuptools', 'wheel',
    'pip', 'PyInstaller', 'altgraph', 'pefile', 'win32ctypes',
    'tkinter', 'unittest', 'doctest', 'pydoc',
]

# ---------------------------------------------------------------- Analysis
a = Analysis(
    [os.path.join(PROJECT_ROOT, 'main.py')],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(SPECPATH, 'runtime_hook.py')],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---------------------------------------------------------------- onedir 模式
# 为什么不用 onefile：
#   1) onefile 每次启动都要把 173MB 的 VRM 模型解压到临时目录，冷启动慢到不能忍；
#   2) backend/core/config.py 里 resource_dir() 取的是 sys._MEIPASS —— onefile 下
#      它指向临时解压目录，而 app_dir() 指向 exe 所在目录，两者不是同一个地方，
#      会让"资源在 A、数据在 B"这种错位问题变得极难排查。
#   onedir 下两者都是 exe 所在目录，且与 Flutter Release 目录天然同构，可直接合并。
#
# 布局说明（2026-10-16 核实，PyInstaller 6.22.3 实测）：
#   onedir 产物实际是 <run>/backend.exe + <run>/_internal/。
#   contents_directory 只在 EXE() 上生效；放在 COLLECT 上会被静默忽略
#   （PyInstaller/building/api.py 的 COLLECT.__init__ 只从 EXE 实例读取）。
#   本项目所有消费方（config.resource_dir、webpanel、runtime_hook、
#   assemble_windows）都从 sys._MEIPASS 动态推导，两种布局都能正确解析，
#   故保持默认 _internal/ 布局即可。不要为了「平铺」把参数挪到 EXE——
#   那会让 .star_core 数据目录落进包顶层，被 assemble 的跳过规则漏掉，
#   插件种子静默失效。
if ONEFILE:
    # 单文件模式（XIAOLING_ONEFILE=1）：后端打成单个 dist/backend 可执行文件，
    # 便于本地 Linux/macOS 复现脚本与 CI 直接 `cp dist/backend $BUNDLE/backend`。
    # 资源（VRM/动作/插件/proto/llama_cpp 运行时）全部由 datas/binaries 收进 exe。
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        exclude_binaries=False,
        name='backend',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='backend',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,              # 不依赖 UPX：本机未必装，压缩也拖慢冷启动
        runtime_tmpdir=None,
        # 无控制台窗口：由 packaging/launcher.py 以 CREATE_NO_WINDOW 拉起，
        # 用户全程看不到黑窗口。输出会被重定向到 <用户根>/logs/backend.log，
        # 排障时仍然有据可查（见 launcher.py 的 _backend_log）。
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='backend',
    )
