# 小凌 XLmodel v0.0.1 交接文档

## 项目概述

小凌是一个住在你电脑里的 3D AI 女孩。Flutter (UI) + Python (AI后端) + gRPC (通信) 三语言混合架构。

- Gitee: https://gitee.com/COSMOnb666/XLmodel
- GitHub: https://github.com/3477856804/XLmodel-release
- 官网: https://xiaoling-4o6.pages.dev
- 版本: 0.0.1

## 架构

```
┌─────────────┐   gRPC    ┌──────────────┐
│  Flutter UI │ ←──────→ │ Python 后端   │
│  (桌面端)    │  :50051  │  (PyInstaller)│
└─────────────┘          └──────┬───────┘
                                │
                    ┌───────────┼───────────┐
                    ↓           ↓           ↓
              Qwen2.5-0.5B  edge-tts   VRM模型文件
              (本地LLM)     (语音合成)   (resources/models/)
```

## 目录结构

```
XLmodel-src/
├── backend/              # Python 后端
│   ├── main.py           # 入口，启动 gRPC serve()
│   ├── core/
│   │   ├── engine.py     # 主引擎，chat() 优先调模型
│   │   ├── model.py      # Qwen2.5 加载 + HuggingFace 下载
│   │   ├── voice.py      # edge-tts 语音合成
│   │   ├── training.py    # LoRA r=4 CPU 微调
│   │   ├── growth.py     # 成长引擎
│   │   ├── memory.py     # 长期记忆
│   │   ├── knowledge.py  # 知识图谱+RAG
│   │   ├── scheduler.py   # 定时任务
│   │   ├── goal_manager.py # 目标管理(JSON持久化)
│   │   ├── search.py     # DuckDuckGo搜索
│   │   ├── updater.py    # 自动更新检查
│   │   └── plugin_manager.py
│   └── rpc/
│       ├── xiaoling.proto    # gRPC 接口定义
│       ├── xiaoling_pb2.py   # 自动生成
│       ├── xiaoling_pb2_grpc.py
│       └── server.py         # gRPC servicer 实现
├── frontend/             # Flutter UI
│   └── lib/
│       ├── main.dart     # HomeShell 左侧边栏布局
│       ├── pages/
│       │   ├── chat_page.dart      # 聊天+自动TTS播报
│       │   ├── dashboard_page.dart # 工作台+3D模型展示
│       │   ├── training_page.dart  # 五维雷达图
│       │   ├── growth_page.dart    # 成长曲线
│       │   └── settings_page.dart  # 设置
│       ├── widgets/
│       │   └── model_showcase.dart # 3D VRM展示(model_viewer_plus)
│       └── rpc/          # Dart gRPC 生成代码
├── resources/
│   └── models/           # VRM 模型文件
├── models/               # 下载的LLM模型(gitignore)
├── adapters/             # LoRA适配器(gitignore)
└── .github/workflows/    # CI 三平台打包
```

## gRPC 接口清单

| 接口 | 方向 | 说明 |
|------|------|------|
| Chat | 流式 | 用户消息→AI回复 |
| GetStatus | 一元 | 程序状态 |
| GetSettings/UpdateSettings | 一元 | 读写配置 |
| GetGrowthStatus | 一元 | 成长进度 |
| GetTrainingStatus | 一元 | 五维能力 |
| StartTraining | 流式 | LoRA训练进度 |
| ListPlugins | 一元 | 插件列表 |
| ListModels | 一元 | VRM模型列表 |
| ListVoices | 一元 | TTS音色 |
| ReadAloud | 流式 | 文字→MP3音频 |
| DownloadModel | 流式 | 下载LLM模型 |
| DetectHardware | 一元 | CPU/内存/GPU |

## 已实现功能

- 真实 LLM 对话: Qwen2.5-0.5B-Instruct (CPU推理)
- 真实 TTS: edge-tts (晓晓/晓涵/晓艺等中文音色)
- 真实 LoRA 微调: peft r=4, CPU可跑
- 真实模型下载: HuggingFace
- 3D模型展示: model_viewer_plus (拖拽旋转)
- 联网搜索: DuckDuckGo
- 知识图谱: 三元组抽取+JSON持久化
- 定时任务: 后台线程+提醒
- 自动更新: 检查 GitHub release
- 左侧边栏导航: 5个页面
- 粉色+金色+黑+白主题
- 聊天后自动语音播报
- 三平台 CI 打包 (Win/Mac/Linux)

## 配色

- 主色粉: #E85A8A
- 辅助金: #D4AF37
- 文字: #1a1a1a
- 背景: #FFF5F8 (浅粉白)

## 开发流程

1. 改代码后 commit，提交信息统一写"已修复已知问题"
2. push 到 gitee main 和 github-release main
3. 手动触发 GitHub Actions (workflow_dispatch) 打包
4. 等待三平台构建完成
5. 从 Release 下载对应平台包测试

## 本地运行

```bash
# 后端
cd backend
pip install -r requirements.txt  # 或手动装: grpcio grpcio-tools transformers torch edge-tts peft
python3 -m rpc.server --port 50051

# 前端
cd frontend
flutter pub get
flutter run -d linux  # 或 chrome
```

## 已知限制

1. 首次加载模型需 ~75秒 (CPU 2核)
2. 首次推理慢，后续 0.4-2秒
3. ASR 语音识别未实现 (需whisper)
4. 模型需用户首次使用时通过"模型商店"下载
5. 3D VRM渲染在无头环境测试受限

## 账号密钥

密钥见原始交接说明文档，不在此文件中存储。
