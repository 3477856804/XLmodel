# 晓灵 Android 沙箱环境架构说明

版本：0.0.1
最后更新：2026-10-07

## 1. 目标

在 Android 手机端本地运行 Python 后端，使 Flutter App 无需桌面主机即可：
- 启动本地 gRPC 服务（localhost:50051）
- 管理模型下载到 App 私有目录
- 提供设置 / 记忆 / 插件框架等轻量功能
- 聊天在本地未加载大模型时走模拟/远程 API 降级

## 2. 总体架构

```
Flutter UI (Dart)
   │  MethodChannel("xiaoling/sandbox")
   ▼
MainActivity.kt  ──invoke──►  SandboxService.kt (ForegroundService)
                                   │  Python.start(AndroidPlatform)
                                   ▼
                          Chaquopy (libpython3.8.so)
                                   │
                                   ▼
                          sandbox_entry.py  ──►  backend/config.py
                                   │            backend/model_manager.py
                                   └── gRPC server (grpcio 1.59.3, 127.0.0.1:50051)
                                          ▲
                                   Flutter XlClient 直连 localhost:50051
```

## 3. 关键组件

### 3.1 Android 工程配置
- `frontend/android/settings.gradle`：pluginManagement.repositories 增加 `https://chaquo.com/maven`；plugins 声明 `com.chaquo.python:15.0.1 apply false`。
- `frontend/android/app/build.gradle`：
  - 顶部 `buildscript` 显式声明 AGP 8.1.0 与 `com.chaquo.python:gradle:15.0.1`（Chaquopy 的 checkAgpVersion / findPlugin 需要在 buildscript classpath 上自举）。
  - `defaultConfig.ndk.abiFilters = arm64-v8a, armeabi-v7a, x86_64`。
  - `defaultConfig.python.version = "3.8"`（Chaquopy 对 3.8 的 wheel 支持最完整；3.11 在本机构建环境会 encodings 初始化失败）。
  - `pip { install "grpcio"; install "protobuf" }`。
  - `sourceSets.main.python.srcDirs = ["src/main/python"]`。
- `AndroidManifest.xml`：增加 INTERNET / FOREGROUND_SERVICE / FOREGROUND_SERVICE_DATA_SYNC / POST_NOTIFICATIONS / WAKE_LOCK；声明 `.SandboxService`（foregroundServiceType=dataSync）。

### 3.2 Python 沙箱（frontend/android/app/src/main/python/）
- `sandbox_entry.py`：入口。`setup(home)` 注入 App 私有目录；`start(port)` 启动 gRPC；所有重型依赖 try-except 降级。
- `backend/config.py`：精简配置中心，路径基于 XIAOLING_HOME。
- `backend/model_manager.py`：模型下载管理（urllib 流式下载、进度表、镜像回退）。
- `xiaoling_pb2.py` / `xiaoling_pb2_grpc.py`：从 proto 生成（未修改，仅复制打包）。

### 3.3 Android 服务
- `SandboxService.kt`：前台服务。onCreate 内 `Python.start(AndroidPlatform)`，调用 `sandbox_entry.setup(filesDir)` 与 `start(50051)`。companion 暴露 `statusJson() / modelSnapshotJson() / downloadModel()`。
- `MainActivity.kt`：MethodChannel("xiaoling/sandbox")，方法 `startSandbox / stopSandbox / getSandboxStatus / downloadModel`，全部在单线程后台执行。

### 3.4 Flutter 集成
- `lib/services/sandbox.dart`：`SandboxService` 单例，仅 `Platform.isAndroid` 生效。
- `lib/main.dart`：Android 启动时自动 `SandboxService.start()`。
- `lib/pages/model_store_page.dart`：Android 上 `_startDownload` 走 `SandboxService.downloadModel` + 轮询进度。

## 4. 构建验证

- 命令：`cd frontend && export JAVA_HOME=/home/user/jdk-17.0.12+7 && /home/user/flutter/bin/flutter build apk --debug`
- 结果：成功，产物 `frontend/build/app/outputs/flutter-apk/app-debug.apk`（约 100MB，含 3 ABI + Python 3.8 运行时）。
- pip 解析：grpcio 1.59.3、protobuf 5.29.6 均为 Chaquopy 预编译 wheel，三个 ABI 全部安装成功。
- Python 语法：`python3 -m py_compile` 全部通过。

## 5. 降级策略

- grpcio / protobuf 缺失：gRPC servicer 注册失败，`grpc_available=false`，沙箱仍提供模型下载与状态查询。
- 本地未加载大模型：Chat 返回模拟回复，提示配置远程 API。
- 网络失败：模型下载自动切换 HuggingFace 镜像。

## 6. 已知限制

- 手机端不运行完整 ML 推理；大模型需走远程 API。
- 编译期警告：audioplayers 要求 compileSdk 35（当前 34，非阻塞）；.pyc 字节码编译因宿主 Python 3.12 不兼容而跳过（不影响运行）。
