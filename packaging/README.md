# 打包说明（四平台）

> 本文件描述当前架构：Flutter 桌面前端 + Python gRPC 后端，入口在根目录 `main.py`，
> 后端代码在 `backend/`。版本固定为 0.0.1（tag `v0.0.1`）。
>
> - 统一后端打包配置是 **`packaging/backend.spec`**（onedir，`contents_directory='.'`，
>   显式收集 VRM/动作/resources/web/插件/proto 与 llama_cpp 运行时）。
> - **`packaging/xiaoling.spec`** 是兼容入口，直接转交 `backend.spec`（不再指向旧的
>   xl.py / core / 中文目录）。
> - **`packaging/build.py`** 是一键打包器（自动按平台产出 zip/tar.gz/deb/AppImage/dmg）。
> - Windows 目录合并：`python packaging/assemble_windows.py --zip`；
>   单文件 exe：`python packaging/build_single_exe.py`。

---

> 小凌的 Python 后端用 PyInstaller 打包，UI 由 Flutter 提供，**不需要 Node/Electron**。

## 一、先看环境体检
```bash
python3 packaging/build.py --check          # 标准版依赖检查
python3 packaging/build.py --check --lite  # 精简版依赖检查
```

## 二、一条命令出包（在对应平台上执行）

| 平台 | 命令 | 产物 |
|---|---|---|
| **Windows** | `python packaging/build.py --zip`，再 `python packaging/assemble_windows.py --zip` | `dist/小凌-Windows-x64/` + `.zip` |
| **Linux** | `python3 packaging/build.py --zip --deb --appimage` | `dist/` 下 onedir + `.tar.gz` + `.deb` + `.AppImage` |
| **macOS** | `python3 packaging/build.py --dmg`（或 `bash packaging/macos/build_dmg.sh`） | `dist/xiaoling-0.0.1.dmg` |
| **Android/Termux** | `bash packaging/termux/install.sh` | 命令行 + 平台机器人（无 3D 窗口，自动降级轻量模式） |

> **PyInstaller 不能交叉编译**：Windows 包必须在 Windows 上打，macOS 包必须在 macOS 上打。
> 想一次出四平台 → 用 GitHub Actions `.github/workflows/build-all.yml`。

## 三、四平台矩阵构建（CI）
`.github/workflows/build-all.yml` 在 push 到 main 或手动触发后，于
ubuntu / windows / macos 矩阵上分别构建，并把产物挂到 GitHub Release `v0.0.1`：
```
xiaoling-linux-0.0.1.tar.gz / xiaoling-windows-0.0.1.zip /
xiaoling-macos-0.0.1.dmg / xiaoling-android-0.0.1.apk
```


## 四、两种构建模式

| 模式 | 命令 | 体积 | 说明 |
|---|---|---|---|
| **标准版** | `--` | 大（含 torch/PySide6/全量 VRM） | 完整功能：3D 桌宠 + 本地模型 + 成长闭环 |
| **精简版** | `--lite` | 小（约 30–60 MB） | 软件渲染 + 联网/平台/形象改造可用；不含 torch，无本地大模型与训练 |
| **单文件** | `--lite --onefile` | 单个可执行文件 | 便携分发；注意 onefile 会解包到临时目录，数据仍写在可执行文件同级 `.star_core/` |

打包配置在 **`packaging/xiaoling.spec`**（由 `packaging/build.py` 调用）：资源清单、隐藏导入、精简版裁剪、
macOS `.app` 元信息都在这里。改资源范围请改 spec，不要改命令。

## 五、打包后的目录结构与数据

```
dist/xiaoling/                # 目录版（推荐）
├── xiaoling(.exe)            # 主程序
├── _internal/                # Python 运行时与依赖（PyInstaller）
├── renderer/ core/ 工具/      # 只读资源（渲染层 / 融合层 / 形象流水线）
├── models/ animations/        # VRM 与小凌的 46 个动作
├── assets/ sounds/ skills/ data/ scripts/ docs/
└── .star_core/               # ← 首次运行自动创建：可写数据
    ├── XLmodel/              #   基底模型权重（缺省自动下载）
    ├── adapter/              #   LoRA 适配器（成长闭环）
    ├── growth/journal.jsonl  #   成长日志
    ├── rag/ xiaoling_config.json  # 记忆与配置
    └── tts/ recordings/ images/
```

**路径规则**（`core/paths.py`）：只读资源跟随程序；可写数据固定在**可执行文件目录**，
可用环境变量 `XIAOLING_HOME` 改到别处（多用户/只读安装目录场景）：
```bash
XIAOLING_HOME=~/.local/share/xiaoling ./xiaoling
```

## 六、无 GPU 也能跑
- Windows/macOS：有显卡就走真实 OpenGL；驱动异常时自动退到 numpy 光栅。
- Linux：建议 `sudo apt install libosmesa6 libgl1-mesa-dri`（脚本 `packaging/linux/install_deps.sh` 会自动装）。
- 程序内置兜底：`GALLIVM_PERF=nopt`（绕开部分虚拟化 CPU 上 llvmpipe 的非法指令）。

## 七、常见问题

| 现象 | 原因 / 解决 |
|---|---|
| 双击没窗口、只有控制台 | 没装 PySide6 → `pip install PySide6`；或本机无桌面环境（linux-headless/WSL 无 X） |
| 提示 `could not load libGL` | 装 Mesa：`apt install libgl1 libglx-mesa0`；或用 `XIAOLING_GALLIUM_DRIVER=softpipe` |
| 首次启动慢 | 正在自动安装 torch 或下载基底模型（4.8GB），进度在控制台与桌宠气泡 |
| 想把小凌整个搬走 | 直接搬 `dist/xiaoling/` 整个文件夹（`.star_core` 跟着走） |
| 杀毒误报 | UPX 已关闭、PyInstaller 产物常见误报，加白名单或自行源码运行 |
