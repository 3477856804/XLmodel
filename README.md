# 晓灵 XiaoLing · v0.0.1

会成长的 AI 伴侣 + Agent 平台 —— Flutter + Python + gRPC 三语言架构，本地优先，桌面常驻。

---

## 项目简介

晓灵不是一个"问一句答一句"的聊天框，而是一个常驻桌面、有持久人格与记忆、能在你本地机器上真正干活的 AI 伴侣兼 Agent 平台。

它把两类能力合在了一起：

- **AI 伴侣属性**：3D 数字人形象、情绪与亲密度、长期记忆、拟人化人格，桌面常驻可交互。
- **Agent 工程能力**：本地工具调用（终端、文件、git、搜索）、MCP 接入、插件体系、子 Agent 编排、代码符号索引与知识库检索，可在沙箱内安全执行。

架构上 UI（Flutter/Dart）与 AI 后端（Python）通过 localhost 上的 gRPC 解耦，前端可替换，后端可独立运行自检。

---

## 核心特性

下列特性均对应仓库中实际存在的后端模块，未做夸大。

### 本地成长与 LoRA 训练
- 基底模型 + LoRA 适配器的成长闭环：对话数据进数据仓库 → 蒸馏节流 → LoRA 训练 → 适配器成熟后合并晋升 → 可脱离原基底继续长大，并支持回滚（`backend/core/growth.py`）。
- 训练与合并基于 PyTorch / transformers / peft，CPU 可跑小模型，有 GPU 自动用 GPU。

### 3D VRM 数字人
- 桌面端通过内置 InAppWebView 加载本地 three.js + three-vrm 页面渲染 VRM，自带轨道相机、三点布光、呼吸/眨眼/注视。
- three.js 与 three-vrm 全部离线内置，不依赖 CDN，断网也能出 3D（`backend/core/webpanel.py`、`resources/web/`）。

### 多通道消息
- 统一外部消息通道抽象，支持 Webhook / Telegram / Discord / 飞书 / 邮件，所有出站调用带 10 秒超时与失败降级，不阻塞主程序（`backend/core/channels.py`）。

### MCP 接入
- 内置 Model Context Protocol 客户端：工具调用结果缓存、网络错误指数退避重试、连接健康检查、服务器配置持久化、统一超时（`backend/core/mcp_client.py`）。

### DSH 插件兼容
- DSH 插件兼容层，可解析、安装、管理 DSH 格式插件（`backend/core/dsh_compat.py`）。

### 沙箱与安全
- 自有数据沙箱：模型下载与工具执行隔离在用户数据目录，避免写入 Program Files、升级覆盖用户数据、以及工具越权读写全盘（`backend/core/sandbox.py`）。
- "永不删除"红线：任何待删文件一律移入隔离区并登记清单，不直接从磁盘删除（`backend/core/quarantine.py`）。

### 代码符号索引与知识库检索
- 代码符号索引：扫描 def / class / function / import 等符号，缓存到 `.symbol_index.json`，支撑代码检索（`backend/core/tools.py`）。
- 知识库检索：jieba 中文分词（不可用时降级为正则分词）+ TF-IDF 加权词法检索（`backend/core/knowledge_base.py`）。说明：这是关键词加权检索，并非向量 embedding 检索。

### 本地模型与模型商店
- 同时支持 transformers 目录模型与 GGUF 单文件权重，推理后端自动分派（`backend/core/model.py`）。
- 模型商店可自动检测硬件、多下载通道（HuggingFace 镜像 / ModelScope）回退、断点续传，并支持添加 OpenAI 兼容接口（如 LM Studio，`backend/core/fusion.py`）。

### 插件系统
- 插件开关状态持久化、从 URL/zip 真实安装、按模板自建插件；同名插件升级时旧版先移入隔离区再写入，不覆盖（`backend/core/plugin_system.py`）。

---

## 快速开始

### 环境要求
- Python 3.10+（实测 3.12）
- Flutter 3.32+（本项目 CI 用 3.47.6，Dart 3.13）
- 本地模型推理需要足够内存；无 GPU 时训练与推理自动退回 CPU

### 安装依赖
```bash
git clone https://gitee.com/COSMOnb666/XLmodel.git
cd XLmodel
pip install -r requirements.txt
```

### 启动后端
```bash
# gRPC 后端 + Web 实测面板（默认端口 50051，面板 8765）
python3 main.py

# 仅 gRPC（Flutter 正式联调时使用）
python3 main.py --port 50051 --no-web

# 打印引擎状态后退出 / 运行自检
python3 main.py --status
python3 main.py --selftest
```

### 启动前端
```bash
cd frontend
flutter pub get
flutter run
```

前端会自动挑选空闲端口启动后端并通过 gRPC 连接；也可用浏览器打开后端打印的 `http://127.0.0.1:8765/viewer.html` 直接看 3D。

---

## 目录结构

```
xl_project/
├── main.py                 # 后端启动入口（gRPC + 可选 Web 面板 / 3D 查看器）
├── backend/
│   ├── core/               # 业务模块（引擎/模型/记忆/成长/插件/工具/沙箱/通道/MCP 等）
│   ├── renderer/           # VRM/GLTF 渲染辅助
│   └── rpc/                # gRPC 服务 + proto 生成桩代码
├── frontend/               # Flutter (Dart) 桌面/移动 UI
│   └── lib/
│       ├── pages/          # 页面：聊天/工作台/训练/模型商店/终端/git/插件/设置 等
│       ├── widgets/        # 业务组件
│       ├── services/        # 后端端口发现、更新器等本地服务
│       ├── theme/          # 主题与持久化
│       └── rpc/            # gRPC Dart 客户端
├── shared/proto/           # gRPC 通信契约（.proto 源）
├── resources/              # 模型 / 动作 / 材质 / 音效 / 离线 3D 前端资源
├── plugins/                # 内置插件
├── tests/                  # pytest 用例（test_contracts 等）
├── docs/                   # 设计与发布文档
├── packaging/              # 三平台打包配置
└── tools/                  # 比对 / 推送等辅助脚本
```

---

## 与主流编码 Agent 工具的定位对比

Trae、Codex、Qoder、DSH、WorkBuddy、OpenClaw 等都是以"写代码 / 命令行干活"为核心的编码 Agent。晓灵与它们的定位差异如下：

| 维度 | 编码 Agent（Trae/Codex/Qoder/DSH 等） | 晓灵 XiaoLing |
|---|---|---|
| 核心定位 | 代码生成 / 终端命令执行 | 常驻桌面的 AI 伴侣 + Agent 平台 |
| 形象与情感 | 无 | 3D VRM 数字人 + 情绪/亲密度/人格 |
| 模型来源 | 多依赖云端 API | 本地 GGUF / transformers 模型，可断网运行 |
| 自我成长 | 无 | 本地 LoRA 训练 → 合并晋升的成长闭环 |
| 消息触达 | 多在 IDE 内 | 多通道（Webhook/Telegram/Discord/飞书/邮件） |
| 代码理解 | 编辑器内 | 符号索引 + 知识库检索，可被 Agent 调用 |
| 插件生态 | 各自封闭 | MCP 客户端 + DSH 兼容层 + 自建插件 |

说明：晓灵并不试图取代这些编码工具，而是把"会干活的 Agent"和"有形象、能成长、陪在桌面的伴侣"结合在同一个本地进程里。

---

## 差异化优势

- **AI 伴侣属性**：不只是工具，而是有 3D 形象、情绪、亲密度与长期记忆的常驻角色。
- **本地 LoRA 成长训练**：模型随使用在本地长大，蒸馏、合并、晋升、回滚闭环完整，不依赖云端训练服务。
- **VRM 3D 数字人**：离线 three.js + three-vrm 渲染，断网可用，五平台统一。
- **多通道消息**：同一人格通过 Webhook / Telegram / Discord / 飞书 / 邮件对外触达。
- **源码自主、本地可完全自建**：UI 与后端 gRPC 解耦，数据落在本地沙箱，无云端锁定；源码托管于 Gitee 与 GitHub 双仓。

---

## 技术栈

- UI：Flutter 3 (Dart) + Material 3，新拟态设计系统，深浅双主题
- 后端：Python 3.10+，gRPC（localhost:50051）
- 推理与训练：PyTorch + transformers + peft，GGUF 经 llama.cpp 封装
- 3D：three.js r160 + @pixiv/three-vrm 1.x，离线 vendor，经 InAppWebView 嵌入
- 打包：PyInstaller + 各平台安装器

---

## 测试

```bash
python3 -m pytest tests/ -v
```

当前 26 个契约测试全部通过；后端全部核心模块可导入，`main.py` 可正常启动并响应 `GetStatus` RPC。

---

## 版本

- 后端：`0.0.1`（见 `backend/core/config.py`）
- 前端：`0.0.1+1`（见 `frontend/pubspec.yaml`）

## License

当前为源码双仓托管项目，尚未选定开源许可证；具体授权以仓库后续补充的 LICENSE 文件为准。
