# 打包说明（三平台）

> 小凌的唯一语言是 Python，所以打包只需要 PyInstaller，**不需要 Node/Electron**。

## 一、先看环境体检
```bash
python packaging/build.py --check          # 标准版依赖检查
python packaging/build.py --check --lite    # 精简版依赖检查
```

## 二、一条命令出包（在对应平台上执行）

| 平台 | 命令 | 产物 |
|---|---|---|
| **Windows** | `python packaging\build.py --zip` | `dist\xiaoling\xiaoling.exe` + `dist\xiaoling-windows-x64.zip` |
| **Linux** | `python3 packaging/build.py --zip --deb --appimage` | `dist/xiaoling/xiaoling` + `.tar.gz` + `.deb` + `.AppImage` |
| **macOS** | `python3 packaging/build.py --zip`（或 `packaging/macos/make_dmg.sh`） | `dist/小凌.app` + `.dmg` |
| **Android/Termux** | `bash packaging/termux/install.sh` | 命令行 + 平台机器人 + 离线出图（无 3D 窗口） |

> **PyInstaller 不能交叉编译**：Windows 包必须在 Windows 上打，macOS 包必须在 macOS 上打。
> 想一次出三平台 → 用下面的 GitHub Actions。

## 三、三平台矩阵构建（推荐）
推一个 tag 即可：
```bash
git tag v1.0.0 && git push origin v1.0.0
```
`.github/workflows/release.yml` 会在 windows-latest / macos-latest / ubuntu-latest 上分别打包，
跑完 4 套回归测试，并把产物挂到 GitHub Release（含 sha256）。

## 四、两种构建模式

| 模式 | 命令 | 体积 | 说明 |
|---|---|---|---|
| **标准版** | `--` | 大（含 torch/PySide6/全量 VRM） | 完整功能：3D 桌宠 + 本地模型 + 成长闭环 |
| **精简版** | `--lite` | 小（约 30–60 MB） | 软件渲染 + 联网/平台/形象改造可用；不含 torch，无本地大模型与训练 |
| **单文件** | `--lite --onefile` | 单个可执行文件 | 便携分发；注意 onefile 会解包到临时目录，数据仍写在可执行文件同级 `.star_core/` |

## 五、打包后的目录结构与数据

```
dist/xiaoling/                # 目录版（推荐）
├── xiaoling(.exe)            # 主程序
├── _internal/                # Python 运行时与依赖（PyInstaller）
├── renderer/ core/ tools/    # 只读资源（渲染层 / 融合层 / 形象流水线）
├── 角色模型/ 动作资产/        # VRM 与小凌的 46 个动作
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
