# 小凌 XLmodel v0.0.1 交接文档

## 项目概述

小凌是住在用户电脑里的 3D AI 女孩。

```
┌─────────────────┐   gRPC/localhost:50051   ┌──────────────────┐
│  Flutter UI      │  ←──────────────────→   │  Python 后端      │
│  (桌面端窗口)     │   二进制协议             │  (PyInstaller)    │
└─────────────────┘                          └────────┬─────────┘
                                                      │
                                          ┌───────────┼───────────┐
                                          ↓           ↓           ↓
                                    Qwen2.5-0.5B  edge-tts   VRM模型
                                    (本地LLM)     (语音合成)  (resources/)
```

- Gitee: https://gitee.com/COSMOnb666/XLmodel
- GitHub: https://github.com/3477856804/XLmodel-release
- 官网: https://xiaoling-4o6.pages.dev
- 版本: 0.0.1

## 已实现功能

- AI对话：Qwen2.5-0.5B-Instruct 本地推理
- 语音合成：edge-tts 五个中文音色
- 模型下载：HuggingFace 断点续传
- LoRA微调：peft r=4，CPU可跑，适配器保存
- 3D模型展示：model_viewer_plus 渲染VRM
- 联网搜索：DuckDuckGo
- 知识图谱：三元组抽取+JSON持久化
- 定时任务：后台线程调度
- 自动更新：GitHub release版本检查
- 目标管理：JSON持久化增删改查
- 聊天自动播报：audioplayers播放MP3
- 左侧边栏导航：聊天/工作台/训练/成长/设置
- 三平台打包：Windows/macOS/Linux

## 文件说明

### 根目录

| 文件 | 作用 |
|------|------|
| `main.py` | 后端启动入口，启动gRPC服务在localhost:50051 |

### backend/core/ — AI核心

| 文件 | 作用 |
|------|------|
| `engine.py` | 主引擎 XiaoLing 类，整合所有模块，chat()优先调真实模型 |
| `model.py` | LLM加载与推理（transformers + Qwen2.5），模型下载与管理 |
| `voice.py` | edge-tts语音合成，5个音色 |
| `training.py` | LoRA r=4 CPU微调，适配器保存 |
| `growth.py` | 成长引擎，五维能力等级 |
| `growth_store.py` | 成长数据JSON持久化 |
| `memory.py` | 长期记忆，对话历史 |
| `knowledge.py` | 知识图谱三元组 |
| `scheduler.py` | 定时任务调度 |
| `goal_manager.py` | 目标管理 |
| `search.py` | DuckDuckGo搜索 |
| `updater.py` | GitHub release更新检查 |
| `config.py` | 配置读写 |
| `persona.py` | 情绪与亲密度 |
| `session.py` | 会话持久化 |
| `plugin_manager.py` | 插件钩子 |
| `multi_agent.py` | 多Agent调度 |
| `guards.py` | 网络状态守卫 |
| `tools.py` | 工具与技能管理 |
| `system.py` | 系统自检 |
| `paths.py` | 路径常量 |
| `channels.py` | 消息通道 |
| `lifecycle.py` | 生命周期管理 |
| `throttle.py` | 限流 |
| `vision.py` | 视觉（占位） |
| `filebox.py` | 文件管理 |
| `avatar.py` | 头像 |

### backend/rpc/ — gRPC通信

| 文件 | 作用 |
|------|------|
| `xiaoling.proto` | 12个RPC接口定义 |
| `server.py` | gRPC服务实现，引擎懒加载，流式Chat/Training/TTS |
| `xiaoling_pb2.py` | protobuf自动生成 |
| `xiaoling_pb2_grpc.py` | gRPC自动生成，类名XiaoLingStub |

### frontend/lib/ — Flutter UI

| 文件 | 作用 |
|------|------|
| `main.dart` | 应用入口，左侧边栏5页面布局 |
| `theme/theme.dart` | 粉+金+黑+白主题，液态玻璃卡片 |
| `pages/splash_page.dart` | 启动页 |
| `pages/chat_page.dart` | 聊天页，流式回复+自动TTS播报 |
| `pages/dashboard_page.dart` | 工作台，3D模型展示+快捷按钮 |
| `pages/training_page.dart` | 训练页，五维雷达图+loss流式 |
| `pages/growth_page.dart` | 成长曲线 |
| `pages/settings_page.dart` | 设置 |
| `pages/model_store_page.dart` | 模型商店下载LLM |
| `widgets/model_showcase.dart` | 3D VRM展示组件 |
| `rpc/xiaoling.pbgrpc.dart` | Dart gRPC自动生成 |

### CI

| 文件 | 作用 |
|------|------|
| `.github/workflows/flutter-release.yml` | 三平台打包，手动触发 |

## gRPC接口

| RPC | 方向 | 说明 |
|-----|------|------|
| Chat | 流式 | 对话 |
| GetStatus | 一元 | 程序状态 |
| GetSettings/UpdateSettings | 一元 | 配置读写 |
| GetGrowthStatus | 一元 | 成长进度 |
| GetTrainingStatus | 一元 | 五维能力 |
| StartTraining | 流式 | LoRA训练进度 |
| ListPlugins | 一元 | 插件列表 |
| ListModels | 一元 | VRM模型列表 |
| ListVoices | 一元 | TTS音色 |
| ReadAloud | 流式 | 文字→MP3 |
| DownloadModel | 流式 | LLM模型下载 |

## 配色

```
粉: #E85A8A  金: #D4AF37  黑: #1A1015  白: #FFF5F8
```

## 开发

```bash
# 后端
cd backend && pip install grpcio grpcio-tools transformers torch edge-tts peft numpy<2
python3 -m rpc.server --port 50051

# 前端
cd frontend && flutter pub get && flutter run -d linux
```

## 发布

```bash
git add -A && git commit -m "已修复已知问题"
git push origin main && git push github-release main
# 手动触发 GitHub Actions，等15分钟
```

## 已知限制

- ASR语音识别未实现
- 首次加载模型需约75秒（CPU）
- 模型需首次使用时下载（约1GB）
