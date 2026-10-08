# 打包说明（当前架构）

> 本文描述**当前架构**的打包方式。
> `packaging/README.md`、`packaging/build.py`、`packaging/xiaoling.spec` 是旧架构
> （Python 单语言 + PySide6，入口 `xl.py`）的遗留物，已失效，仅作历史留档。

## 一、架构决定了打包方式

```
小凌.exe（Flutter 桌面前端）
 │
 │ 启动时按"自己所在目录"找 backend.exe，找到就拉起：
 │ backend.exe --port 50051 --no-web --web-port <空闲端口>
 ▼
backend.exe（Python gRPC 后端 + 3D 查看器 HTTP 服务）
 ├── gRPC localhost:50051 ← 前端所有功能（聊天/设置/模型管理）走这里
 └── HTTP 127.0.0.1:<动态> ← 真 3D：把 viewer.html / three.js / .vrm 吐给前端 WebView
```

**两个 exe 必须在同一个目录。** 前端 `main.dart` 的 `_startBackend()`
是按 `File(Platform.resolvedExecutable).parent` 找 `backend.exe` 的，找不到就**静默跳过**
—— 表现是界面能开但一切功能无响应，且日志里什么都不报。这是分开放最常见的坑。

## 二、三步骤

### 1. 构建 Flutter 前端

```bash
cd frontend
flutter build windows --release
# 产物：frontend/build/windows/x64/runner/Release/
```

Windows 首次构建有两个已知坑，均已修好，勿回退：
- **NUGET-NOTFOUND（MSB3073，退出码 9009）**：`flutter_inappwebview_windows` 需要 nuget 拉
 WebView2 / CppWinRT / WIL / nlohmann.json。本机 VS Build Tools 未带 → 已把官方 `nuget.exe`
 放到 `C:\Users\MVP\.workbuddy\binaries\tools\` 并加进用户 PATH。
- **MSVC 14.51 报 `error C2338: STL1011`**：插件用了废弃的 `<experimental/coroutine>`。
 已在 `frontend/windows/CMakeLists.txt` 的 `add_subdirectory(flutter)` **之前**加
 `add_definitions(-D_SILENCE_EXPERIMENTAL_COROUTINE_DEPRECATION_WARNINGS)`。
 顺序不能反，反了就不生效。

### 2. 打包 Python 后端

```bash
# 必须用"不共享系统站点包"的干净 venv，见下方"为什么"
C:/Users/MVP/.workbuddy/binaries/python/envs/xiaoling_pkg/Scripts/python.exe \
 -m PyInstaller packaging/backend.spec \
 --distpath packaging/dist --workpath packaging/build_tmp --noconfirm
# 产物：packaging/dist/backend/backend.exe
```

#### 为什么必须用干净 venv

项目原本的 `xiaoling312` venv 是 `--system-site-packages`，会把系统 Python312 里
**所有**包（torch 4.2G、modelscope…）暴露给 PyInstaller。后果：
- PyInstaller 构建期的 `import_library()` 子进程会真的去 `import modelscope`，
 而它 `__init__` 时要 JIT 编译 CUDA 扩展 → 直接崩
 （`RuntimeError: Ninja is required to load C++ extensions`）。
- 即便绕过去，产物也会奔着数 GB 去。

`xiaoling_pkg` 是为此新建的独立 venv（Python 3.12，无 `--system-site-packages`），
只装后端实际需要的包：llama-cpp-python、grpcio(+tools)、protobuf、numpy、Pillow、
diskcache、psutil、requests、aiohttp、edge_tts、pyttsx3、jieba、PyInstaller。

#### 为什么排除 torch / transformers

体积。torch 2.11.0+cu128 本体 4.2G，打进包里产物不可分发。
全项目**没有任何顶层 `import torch`**，全部是函数内延迟导入，因此排除后程序照常启动：

| 功能 | 依赖 | 本包是否可用 |
|---|---|---|
| GGUF 模型推理 | `llama_cpp`（已打包） | 正常聊天 |
| HF safetensors 目录格式模型 | `transformers` → torch | 需完整版 |
| LoRA 训练 / 成长闭环 | `transformers` + `peft` | 需完整版 |
| 显存/显卡信息 | `torch.cuda` | 降级为 OS 侧探测（仍显示显卡，只是不显示 torch 可用） |
| UI / 真 3D / 设置 / 模型扫描登记 | 无 | 全部正常 |

需要完整版时：在一个装了 torch 的**干净** venv 里，把 `backend.spec` 的 `excludes`
里 `torch`/`transformers`/`peft` 三行去掉再打即可（其余排除项要留着）。

#### 两个容易踩空的配置

- **`contents_directory='.'`（必须）**：PyInstaller 6.x 默认把依赖塞进 `_internal/`，
 但 `config.py` 的 `resource_dir()` 取的是 `sys._MEIPASS`（= exe 所在目录）→ 会指空，
 3D 直接黑屏。平铺才能让两者一致。
- **onedir 而非 onefile**：onefile 每次启动要把 173MB 的 VRM 解压到临时目录，
 冷启动慢到不能忍；且 `_MEIPASS`（临时目录）与 `app_dir()`（exe 目录）分离，
 会造成"资源在 A、数据在 B"的错位。

### 3. 合并成一个可运行目录

```bash
python packaging/assemble_windows.py --zip
# 产物：dist/小凌-Windows-x64/ 与 dist/小凌-Windows-x64.zip
```

脚本会：拷贝 Flutter Release → 拷贝后端产物（同名文件保留前端版本）→
`frontend.exe` 重命名为 `小凌.exe` → 写 `启动说明.txt` → 做完整性体检并打印体积。
体检缺项会以退出码 2 结束。

## 三、产物目录

```
小凌-Windows-x64/
├── 小凌.exe Flutter 界面（真 3D 经内置 WebView 渲染 VRM）
├── backend.exe Python 后端
├── flutter_windows.dll / data/ / *.dll Flutter 运行时与插件
├── resources/web/ 3D 查看器 + three.js / three-vrm / GLTFLoader（全离线）
├── resources/models/*.vrm 角色模型
├── resources/animations/ 动作库 .vrma
├── plugins/ skills/ 插件与技能
├── 启动说明.txt
└── data/ .star_core/ ← 首次运行后自动生成（聊天记录、配置、模型）
```

`ty.fbx`（22MB）被刻意排除：渲染器只认 VRM，这个文件既加载不了又白占体积。

## 四、排障

| 现象 | 原因 / 处理 |
|---|---|
| 界面能开但聊天没反应 | 前端没找到 `backend.exe` → 确认两个 exe 同目录 |
| 3D 区域全黑 | `resources/web/vendor/*.js` 缺失，或 `contents_directory` 不是 `'.'` |
| 后端控制台报端口占用 | 结束占用 50051 的旧进程（后端会派生父子两个 PID，要一起杀） |
| 双击后弹黑窗口 | 正常 —— 那是 backend.exe 的控制台，故意保留以便你看报错 |
| 想搬走整个小凌 | 直接搬整个文件夹，`data/` 与 `.star_core/` 跟着走 |

## 五、另见

- 真 3D 实现与排障：见 `docs/PUBLISHING.md`
- 四平台发布与官网下载：`docs/PUBLISHING.md`
