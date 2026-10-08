# 晓灵 XiaoLing 架构说明

本文描述 v0.0.1 的实际代码结构与数据流。所有路径与模块名均与仓库一致。

---

## 一、总体架构

晓灵是三语言分离的本地应用：

```
┌──────────────────────────┐   gRPC (localhost:50051)   ┌──────────────────────────┐
│  Flutter 前端 (Dart)      │  ◀──────────────────────▶  │  Python 后端 (main.py)    │
│  UI / 3D 容器 / 本地服务   │                             │  gRPC 服务 + 业务核心      │
└────────────┬─────────────┘                             └──────────┬───────────────┘
             │  InAppWebView 加载 http://127.0.0.1:8765/viewer.html │
             └──────────────────────────────────────────────────────┘
                              后端 webpanel.py 吐静态资源 + /api/vrm/list
```

- UI 与 AI 能力完全解耦：前端只认 gRPC 契约，后端可独立用 `--selftest` / `--status` 验证。
- 3D 不跑在 Flutter 引擎里，而是由后端起一个只绑 `127.0.0.1` 的静态 HTTP 服务，把离线 three.js 页面和 VRM 文件喂给 WebView。

入口 `main.py`：解析 `--port/--web-port/--no-web/--no-grpc/--host/--timeout` 等参数，在后台线程启动 gRPC 服务，主线程保持存活等待关闭信号。

---

## 二、后端架构（Python）

### 2.1 分层

```
backend/
├── rpc/            # 传输层：gRPC 服务 + proto 生成桩
│   ├── server.py       # XiaoLingServicer，46 个 RPC 方法
│   ├── xiaoling.proto  # 通信契约（源）
│   ├── xiaoling_pb2.py / xiaoling_pb2_grpc.py   # 生成代码
│   └── __init__.py
├── core/           # 业务层：可被 RPC 调用的能力模块
└── renderer/       # 渲染辅助：stage.py（舞台编排）、vrm_gltf.py（VRM/GLTF 处理）
```

### 2.2 rpc 传输层

`backend/rpc/server.py` 实现 `XiaoLingServicer`，方法按职责分组：

- 会话与状态：`Chat`（流式对话）、`GetStatus`、`Shutdown`、`ExecuteCommand`
- 模型：`ListModels` / `SwitchModel` / `DetectHardware` / `ListRecommendedModels` / `DownloadModel` / `ListInstalledModels` / `DeleteModel`
- 成长与训练：`GetGrowthStatus` / `StartTraining` / `GetTrainingStatus` / `GetTrainingHistory`
- 插件与动作：`ListPlugins` / `EnablePlugin` / `DisablePlugin`、`ListActions` / `PlayAction`
- 人格与语音：`GetPersona` / `ListPersonas` / `SetPersona` / `AddPersona` / `DeletePersona` / `ResetPersona`、`ListVoices` / `SetVoice` / `ReadAloud` / `Transcribe`（ASR）
- 设置：`GetSettings` / `UpdateSettings`，以及 `settings:options` / `settings:set` 指令族（避免为加字段改 proto）
- 终端与 Agent：`TerminalCreate/Write/Read/Close`、`AgentStart`
- 文件与代码：`FileList` / `FileRead` / `FileWrite`、`CodeSearch`（符号索引检索）、`ProjectContext`
- 提醒与数据：`ListReminders` / `CompleteReminder` / `ExportData` / `ImportData`

每个请求经 `_log_request` 记录方法名、耗时与成败，`GetStatus` 返回 `uptime / requests / avg_ms`。

### 2.3 core 业务模块（按职责分组）

- 引擎与会话：`engine.py`（意图路由：确定性动作直答，闲聊才交给模型）、`context.py`、`options.py`（按平台生成可选项）、`config.py`（配置读写，`version` 字段在此为 `0.0.1`）。
- 模型与推理：`model.py`（transformers 与 GGUF/llama.cpp 双后端自动分派、下载通道回退、切换落盘）、`fusion.py`（OpenAI 兼容接口融合层）。
- 记忆与知识：`memory.py`（短期对话 + 长期记忆 + `KnowledgeGraph` 实体关系图谱，导出 JSON/GraphML）、`knowledge_base.py`（jieba 分词 + TF-IDF，可选 sentence-transformers 语义向量混合检索，未装则降级纯 TF-IDF）。
- 成长与训练：`growth.py`（数据仓库 → 蒸馏节流 → LoRA 训练 → 晋升 → 回滚，记录 embedding 用于去重）。
- 工具与执行：`tools.py`（含代码符号索引，缓存 `.symbol_index.json`）、`terminal.py`、`fileops.py`、`git_tool.py`、`browser_tool.py`（可选 Playwright 真实浏览器自动化：渲染/截图/点击/输入，未装则降级 requests+正则抓取）、`search.py`、`agent.py`（Agent 主循环）。
- 安全与隔离：`sandbox.py`（数据沙箱 + Linux Landlock OS 级路径强制，探测不支持则如实降级）、`quarantine.py`（隔离区，永不删文件）、`security_center.py`。
- 集成与扩展：`mcp_client.py`（MCP 客户端）、`dsh_compat.py`（DSH 插件兼容）、`plugin_system.py` + `plugin_sdk.py`（插件生命周期）、`channels.py`（11 个多通道消息）、`sub_agent.py` + `workflow_engine.py`（子 Agent / 工作流）。
- 形象与多模态：`persona_presets.py`、`multimodal.py`（语音 TTS：pyttsx3/edge-tts 双后端；ASR：`Transcribe` 转写）、`updater.py`、`system.py`、`webpanel.py`（3D 静态 HTTP 服务）、`fusion.py`。

### 2.4 渲染与 3D

- `backend/renderer/stage.py`：舞台编排；`renderer/vrm_gltf.py`：VRM/GLTF 模型处理。
- `backend/core/webpanel.py`：只绑 `127.0.0.1` 的静态服务，白名单目录 + 防目录穿越，路由 `/viewer.html`、`/vendor/*`、`/models/*`、`/api/vrm/list`；端口被占自动顺延最多 20 个。
- 前端资源离线内置在 `resources/web/`（three.js r160、three-vrm 1.x、GLTFLoader）。

---

## 三、前端架构（Flutter / Dart）

```
frontend/lib/
├── main.dart          # 入口：选端口、拉起后端、错误隔离、进主界面
├── updater.dart       # 自动更新
├── pages/             # 页面（14 个）
│   ├── chat_page.dart / dashboard_page.dart / growth_page.dart
│   ├── model_store_page.dart / training_page.dart / terminal_page.dart
│   ├── git_page.dart / agent_page.dart / workflow_page.dart / browser_page.dart
│   ├── plugins_page.dart / plugin_community.dart / settings_page.dart
│   └── splash_page.dart
├── widgets/          # 业务组件（18 个，面板/卡片/弹窗等），含 browser_panel.dart（浏览器导航）、knowledge_graph_panel.dart（知识图谱可视化）
├── services/          # 本地服务
│   ├── local_store.dart    # 本地持久化
│   ├── sandbox.dart        # 沙箱路径管理
│   └── viewer_port.dart    # 3D 查看器端口动态发现
├── theme/             # theme.dart（设计系统）+ theme_controller.dart（主题持久化）
└── rpc/               # gRPC Dart 客户端（xiaoling.pb*.dart 为生成代码 + client 封装）
```

- 启动时 `main.dart` 先由 `viewer_port.dart` 的 `pick()` 挑空闲端口，再经 `--web-port` 传给后端。
- gRPC 客户端带重试 / 熔断 / 健康探测 / 自动重连 / 端点回退。
- 单个 widget 构建失败时由 `_SoftErrorBox` 局部占位，不整屏崩溃。

---

## 四、数据流

### 4.1 一次聊天请求
1. Flutter `chat_page` 通过 gRPC 调 `Chat`，请求进入 `rpc/server.py`。
2. server 取引擎 `_get_engine()`，`engine.py` 判断意图：确定性动作（跳转、清空记忆、提醒、训练、帮助等）由路由直接答；闲聊类有模型则交给 `model.py`，无模型走兜底。
3. 回复流式返回，前端渲染；涉及的对话写入 `memory.py`，长期沉淀进 `growth.py` 数据仓库。

### 4.2 3D 形象渲染
1. Flutter 用 `InAppWebView` 打开后端 webpanel 吐出的 `http://127.0.0.1:<port>/viewer.html`。
2. 页面加载离线 three.js / three-vrm，调 `/api/vrm/list` 拿模型列表，加载 `.vrm`。
3. 页面通过 `addJavaScriptHandler('xlViewer')` 上报 ready/error，暴露 `window.__xl` 供 Flutter 调度视角。

### 4.3 成长训练闭环
1. 对话数据进 `growth.py` 数据仓库。
2. 达到节流阈值后触发 LoRA 训练（`StartTraining` RPC），进度经 `GetTrainingStatus` 流式回推前端。
3. 适配器成熟后合并晋升，可回滚；结果写回 `config.model.active`。

### 4.4 安全边界
- 模型下载与工具执行落在 `sandbox.py` 指定的数据目录。
- 任何"删除"经 `quarantine.py` 移入隔离区并登记清单，不直接删磁盘文件。

---

## 五、配置与数据

- 配置：`backend/core/config.py`，根 `version = "0.0.1"`；运行时数据落在 `data/`（已 gitignore）。
- 前端版本：`frontend/pubspec.yaml` 的 `version: 0.0.1+1`。
- 运行时生成物（`.symbol_index.json`、`logs/`、`tmp/`、`workspace/`、`.star_core/`）均不入库。
