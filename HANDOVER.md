# 小凌 XLmodel v0.0.1 完整交接文档

## 一、项目是什么

小凌是一个住在你电脑里的 3D AI 女孩。三语言混合架构：

```
┌─────────────────┐   gRPC/localhost:50051   ┌──────────────────┐
│  Flutter UI      │  ←──────────────────→   │  Python 后端      │
│  (桌面端窗口)     │   二进制协议             │  (PyInstaller)    │
│  Dart 语言       │                          │  Python 语言      │
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

---

## 二、我们实现了什么（全部真实，非假数据）

| 功能 | 原来状态 | 现在状态 | 实测结果 |
|------|---------|---------|---------|
| AI对话 | 写死回复 | Qwen2.5-0.5B-Instruct 真实推理 | 首次加载75秒，后续0.4-2秒/条 |
| 语音合成 | 空壳 | edge-tts 真实MP3流式返回 | 5个中文音色可选 |
| 模型下载 | 假进度条 | HuggingFace snapshot_download | 真实下载988MB |
| LoRA训练 | sleep空壳 | peft r=4 CPU真实梯度下降 | 5步loss 6.29→5.13，适配器已保存 |
| 3D模型展示 | 无 | model_viewer_plus 渲染VRM | 桌面端WebView拖拽旋转 |
| 联网搜索 | 假数据 | DuckDuckGo API | 真实返回搜索结果 |
| 知识图谱 | 假数据 | 三元组抽取+JSON持久化 | 真实存储读取 |
| 定时任务 | 假数据 | 后台线程+调度 | 真实触发提醒 |
| 自动更新 | 假数据 | 检查GitHub release版本 | 真实比较版本号 |
| 目标管理 | 假数据 | JSON文件持久化 | 增删改查真实生效 |
| 聊天自动播报 | 无 | Flutter audioplayers播放MP3 | 回复完自动朗读 |
| 侧边栏导航 | 底部导航 | 左侧200px边栏5页面切换 | Material图标 |
| 三平台打包 | 无 | GitHub Actions CI | Win/Mac/Linux全部成功 |

---

## 三、每个文件是干嘛的

### 根目录

| 文件 | 作用 |
|------|------|
| `main.py` | 后端启动入口。解析命令行参数，启动gRPC服务在localhost:50051。支持 --status 打印状态、--selftest 自检 |

### backend/core/ — AI核心模块

| 文件 | 行数 | 作用 |
|------|------|------|
| `engine.py` | 123 | **主引擎 XiaoLing 类**。初始化所有子模块（记忆/成长/模型/人格/工具/插件），chat()方法优先调真实模型，失败时兜底回复"你说的是：xxx" |
| `model.py` | 151 | **LLM模型系统**。LocalModel类用transformers加载Qwen2.5，generate()做推理。ModelStore管理模型下载。ModelReplacement检查本地是否有模型可用。预设Qwen/Qwen2.5-0.5B-Instruct |
| `voice.py` | 80 | **语音系统**。TTS类用edge-tts合成MP3（asyncio流式读取audio chunk）。5个音色：小凌/晓涵/晓艺/云希/云扬。ASR类是占位（未实现whisper） |
| `training.py` | 136 | **LoRA训练**。PEFTTrainer类：peft LoraConfig r=4 alpha=8，target_modules=["q_proj","v_proj"]，AdamW优化器，CPU可跑。保存适配器到adapters/。RankScheduler动态升rank |
| `growth.py` | 958 | **成长引擎**。五维能力（感知/理解/决策/进化/守护），等级计算，经验值累积 |
| `growth_store.py` | 734 | **成长数据持久化**。JSON文件存储成长进度 |
| `memory.py` | 79 | **长期记忆**。对话历史存data/memory.json |
| `knowledge.py` | 103 | **知识图谱**。三元组(主-谓-宾)抽取+存储 |
| `scheduler.py` | 131 | **定时任务**。后台线程，到时间触发提醒 |
| `goal_manager.py` | 98 | **目标管理**。用户目标增删改查，JSON持久化 |
| `search.py` | 118 | **联网搜索**。DuckDuckGo API真实搜索 |
| `updater.py` | 111 | **自动更新检查**。请求GitHub release API比较版本号 |
| `config.py` | 288 | **配置管理**。读写settings.json |
| `persona.py` | 131 | **人格引擎**。EmotionEngine情绪状态，RelationshipEngine亲密度 |
| `session.py` | 77 | **会话持久化**。对话历史保存/加载 |
| `plugin_manager.py` | 235 | **插件系统**。before_chat/after_chat钩子 |
| `multi_agent.py` | 86 | **多Agent**。子Agent调度 |
| `guards.py` | 80 | **安全守卫**。OfflineGuard检测网络状态 |
| `tools.py` | 87 | **工具管理**。ToolManager+SkillManager |
| `system.py` | 216 | **系统自检**。selftest()跑一遍所有模块 |
| `paths.py` | 124 | **路径管理**。APP_DIR等目录常量 |
| `channels.py` | 314 | **消息通道**。多渠道消息处理 |
| `lifecycle.py` | 471 | **生命周期**。启动/关闭流程 |
| `throttle.py` | 262 | **限流**。防止请求过快 |
| `vision.py` | 65 | **视觉**。截图识别（占位） |
| `filebox.py` | 155 | **文件管理** |
| `avatar.py` | 94 | **头像** |

### backend/rpc/ — gRPC通信层

| 文件 | 作用 |
|------|------|
| `xiaoling.proto` | **接口定义**。定义12个RPC：Chat/GetStatus/GetSettings/UpdateSettings/GetGrowthStatus/GetTrainingStatus/StartTraining/ListPlugins/ListModels/ListVoices/ReadAloud/DownloadModel |
| `server.py` | **gRPC服务实现**。563行。_get_engine()懒加载引擎。每个RPC方法对应一个业务逻辑方法。StartTraining是流式返回每步loss。ReadAloud流式返回MP3字节 |
| `xiaoling_pb2.py` | protobuf自动生成（不要手改） |
| `xiaoling_pb2_grpc.py` | gRPC自动生成，类名XiaoLingStub |

### backend/renderer/ — 渲染层（旧PySide6遗留，Flutter端不再使用）

| 文件 | 作用 |
|------|------|
| `renderer.py` | OpenGL渲染器 |
| `model.py` | VRM模型加载 |
| `camera.py` | 相机控制 |
| `fbx_loader.py` | FBX加载 |
| `gltf.py` | glTF加载 |
| `pose.py` | 姿态 |
| `lipsync.py` | 口型同步 |
| `vrma.py` | VRMA动画 |
| `soft.py` | 软渲染 |
| `gl.py` | OpenGL封装 |
| `i18n.py` | 国际化 |

### frontend/lib/ — Flutter UI层

| 文件 | 行数 | 作用 |
|------|------|------|
| `main.dart` | 151 | **应用入口**。MaterialApp + HomeShell左侧边栏布局。5个导航项：聊天/工作台/训练/成长/设置。200px宽边栏，选中项粉金渐变高亮 |
| `theme/theme.dart` | 247 | **主题系统**。AppTheme类。粉#E85A8A+金#D4AF37+黑#1A1015+白底。glassCard()方法用BackdropFilter做液态玻璃毛玻璃效果。auroraBackground()多层彩色光斑 |
| `pages/splash_page.dart` | 125 | **启动页**。粉色渐变背景，加载完跳HomeShell |
| `pages/chat_page.dart` | 296 | **聊天页**。gRPC流式调Chat，回复完自动调ReadAloud播放MP3（audioplayers）。右上角喇叭开关 |
| `pages/dashboard_page.dart` | 177 | **工作台**。实时调GetGrowthStatus显示成长进度，ModelShowcase展示3D VRM模型，4个快捷按钮接页面跳转 |
| `pages/training_page.dart` | 303 | **训练页**。五维雷达图（感知/理解/决策/进化/守护），开始训练按钮调StartTraining流式显示loss |
| `pages/growth_page.dart` | 249 | **成长页**。成长曲线图表 |
| `pages/settings_page.dart` | 89 | **设置页**。模型选择/音色选择/开关 |
| `pages/model_store_page.dart` | 194 | **模型商店**。下载LLM模型 |
| `widgets/model_showcase.dart` | 138 | **3D模型展示组件**。model_viewer_plus WebView渲染VRM文件，拖拽旋转 |
| `rpc/xiaoling.pbgrpc.dart` | — | Dart gRPC客户端自动生成，类名XiaoLingStub |

### CI/CD

| 文件 | 作用 |
|------|------|
| `.github/workflows/flutter-release.yml` | **三平台打包**。手动触发。Windows: zip, macOS: DMG, Linux: tar.gz。PyInstaller打包后端+Flutter build前端，合并到同一个release tag flutter-v0.0.2 |
| `.github/workflows/build.yml` | 旧构建（已废弃） |
| `.github/workflows/release.yml` | 旧发布（已废弃） |

### 其他

| 文件 | 作用 |
|------|------|
| `packaging/build.py` | 打包脚本 |
| `packaging/runtime_hook.py` | PyInstaller运行时钩子 |
| `plugins/builtin/hello_world/main.py` | 示例插件 |
| `scripts/vrm_to_fbx.py` | VRM转FBX工具 |
| `resources/models/` | VRM模型文件（Imeris.vrm, Vivi.vrm等） |

---

## 四、gRPC 接口详解

| RPC | 请求→返回 | 方向 | 实现位置 |
|-----|-----------|------|---------|
| Chat | ChatRequest→stream ChatChunk | 流式 | engine.chat() 调 model_replace.chat() |
| GetStatus | StatusRequest→StatusReply | 一元 | 版本0.0.1/模型状态/后端类型 |
| GetSettings | Empty→SettingsReply | 一元 | config读取 |
| UpdateSettings | Settings→StatusReply | 一元 | config写入 |
| GetGrowthStatus | Empty→GrowthStatus | 一元 | growth.status() |
| GetTrainingStatus | Empty→TrainingStatus | 一元 | 五维能力维度 |
| StartTraining | TrainingRequest→stream TrainingProgress | 流式 | peft LoRA每步yield loss |
| ListPlugins | Empty→PluginList | 一元 | plugin_manager.list_plugins() |
| ListModels | ListRequest→ModelList | 一元 | 扫描resources/models/*.vrm |
| ListVoices | Empty→VoiceList | 一元 | voice.VOICES列表 |
| ReadAloud | ReadRequest→stream AudioChunk | 流式 | edge-tts合成MP3分块返回 |
| DownloadModel | DownloadRequest→stream Progress | 流式 | huggingface_hub下载 |

---

## 五、配色规范

```
主色粉:  #E85A8A  (primaryPink)
浅粉:    #FF9FBE  (lightPink)
金色:    #D4AF37  (gold)
深色:    #1A1015  (ink，文字)
背景:    #FFF5F8  (bgBase)
卡片:    白色55%透明 + BackdropFilter模糊
```

---

## 六、开发流程

```bash
# 1. 改代码
cd XLmodel-src

# 2. 提交（统一信息）
git add -A
git commit -m "已修复已知问题"

# 3. 推送到两个远程
git push origin main              # Gitee
git push github-release main      # GitHub

# 4. 触发CI打包
curl -X POST -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/3477856804/XLmodel-release/actions/workflows/flutter-release.yml/dispatches" \
  -d '{"ref":"main"}'

# 5. 等约15分钟，Release自动更新三平台包
```

---

## 七、本地开发运行

```bash
# 后端
cd backend
pip install grpcio grpcio-tools transformers torch edge-tts peft numpy<2
python3 -m rpc.server --port 50051

# 前端（新终端）
cd frontend
flutter pub get
flutter run -d linux
```

---

## 八、已知限制

1. ASR语音识别未实现（需whisper，当前是占位）
2. 首次加载模型需75秒（CPU 2核）
3. 模型需用户首次使用时通过模型商店下载（约1GB）
4. 3D VRM在无头环境无法截图验证效果
5. renderer/目录是旧PySide6遗留，Flutter端不再使用，但保留以备参考
