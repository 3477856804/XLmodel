# 变更记录 · 2026-10-14 · Windows 单文件 EXE 打包

> 操作人：MVPth。红线遵守：全程未删除任何文件；中间产物按「改后缀 .back / 移入待删除目录」处理（本次 PyInstaller 使用全新 distpath，未产生待删项）。

## 一、产物（主交付物已另存桌面）

| 产物 | 项目内路径 | 桌面副本 | 体积 |
|---|---|---|---|
| 单文件版（主交付） | `dist/小凌.exe` | `C:\Users\MVP\Desktop\小凌.exe` | 110.4 MB |
| 目录版压缩包 | `dist/小凌-Windows-x64.zip` | `C:\Users\MVP\Desktop\小凌-Windows-x64.zip` | 102.7 MB |
| 目录版（未复制桌面） | `dist/小凌-Windows-x64/` | — | 235.7 MB |

规格：Windows x64、前后端同一 EXE（PyInstaller 启动器 + 尾部 zip payload，magic=XLPAY1）、首次双击自释放到 `%LOCALAPPDATA%\Xiaoling\app`。仅含 Windows 运行件，无 macOS/Linux/Android 残留（已程序化校验）。

## 二、打包前修复（含备份）

| 文件 | 操作 | 备份 |
|---|---|---|
| `frontend/lib/widgets/model_remote_panel.dart:269` | 编译错误修复：`_RemoteDl(..., repo: m.repo)` 传了不存在的命名参数 → 移除（map 本以 repo 为键） | 同目录 `.bak-20261014` |
| 补空目录 `skills / backend/plugins / backend/skills / materials / sounds` | `backend.spec` datas 强依赖，缺失即硬失败（教训 F-02） | — |
| `backend/core/sandbox.py` | 核查：已有 `import resource` 的 ImportError 降级保护（F-16b 已在源码修复），无需改动 | — |

## 三、构建流水（全部实测通过）

1. 后端：`xiaoling_pkg` venv PyInstaller → `packaging/dist_fresh/backend/`（全新 distpath，规避删除确认，教训 F-14/F-08）。
2. 前端：`flutter pub get && flutter build windows --release` → `frontend.exe`（3m40s）。
3. 合并：`assemble_windows.py --zip --backend-dist packaging/dist_fresh/backend`（必带 --zip，教训 F-13）。
4. 单文件：`build_single_exe.py` → `dist/小凌.exe`（版本标记 01728f5952a80b0b，409 条目）。

## 四、验证清单（全过）

1. `backend.exe --status`：11 个插件全部加载。
2. 新代码进包：`_internal/backend/core/trainer.py` 含 `api_cfg`（上一轮 API 接入功能确认在包内）。
3. 尾标 magic `XLPAY1` 校验通过；payload 内含 `小凌.exe / backend.exe / viewer.html / 小凌.vrm`。
4. 冒烟启动：双击 exe → 释放并静默启动，50051（gRPC）+ 8765（3D Web）双监听；日志零 `ModuleNotFoundError`；RPC GetStatus 8.7ms 正常。
5. 退出清理：进程结束、无端口残留。

## 五、遗留说明

- 打包版**有意排除** torch/transformers/peft：不能加载 safetensors、不能本地 LoRA 训练（GGUF 推理正常）。训练模块 API 接入设置等元数据功能正常。
- 桌面另存的 `小凌-Windows-x64.zip` 是目录版的分发备份；日常用 `小凌.exe` 单文件即可。
