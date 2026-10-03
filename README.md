# 小凌 XIAOLING · v0.0.1

> **会成长的 3D AI 桌宠 —— Flutter + Python + gRPC 三语言架构**

---

## v0.0.1 更新了什么

### 架构升级
- **三语言分离**：Flutter (Dart) 写 UI + Python 写 AI 后端 + gRPC 写通信
- **目录精简**：根目录从 20+ 文件夹 → 8 个，干净工整
- **删除 PySide6**：全部 UI 用 Flutter 重写

### 新功能
- **智能模型商店**：自动检测硬件 → 推荐能跑的最强模型 → 一键下载
- **持久记忆**：短期对话记忆 + 长期向量记忆
- **拟人化人格**：情绪状态机（7种情绪）+ 关系亲密度（5个等级）
- **插件系统**：万物皆插件，右下角+号开关
- **通信通道**：Webhook + Telegram 接入
- **自动更新**：三平台增量更新

---

## 项目结构

```
XLmodel/
├── frontend/          # Flutter UI (Dart)
│   └── lib/
│       ├── theme/       # 粉色少女风主题
│       ├── pages/       # 5个页面
│       └── rpc/         # gRPC 客户端
│
├── backend/            # Python AI 后端
│   ├── core/            # 35个 AI 模块
│   ├── renderer/        # 3D 渲染引擎
│   └── rpc/             # gRPC 服务
│
├── shared/proto/        # gRPC 通信契约
├── resources/          # 模型/动作/材质/音效
├── packaging/          # 三平台打包配置
├── scripts/            # 工具脚本
├── tests/              # 测试
└── docs/               # 文档
```

---

## 快速开始

### 环境要求
- Python 3.10+
- Flutter 3.16+
- 支持 OpenGL 的显卡（或软件渲染）

### 安装
```bash
git clone https://gitee.com/COSMOnb666/XLmodel.git
cd XLmodel
pip install -r requirements.txt
```

### 启动
```bash
# 启动 Python 后端
python -m backend.rpc.server

# 启动 Flutter 前端
cd frontend
flutter run
```

---

## 核心特性

### 会成长的大脑
基底模型 + LoRA 适配器 → 蒸馏训练 → 适配器长大后自动合并晋升 → 完全脱离原基底 → 循环成长

### 3D 数字人
- 8 个角色模型（VRM/FBX）
- 46 个动作（待机/舞蹈/手势/情绪）
- 透明置顶窗，可拖拽
- 弹簧骨（头发/裙摆会晃）
- 口型同步

### 语音系统
- 每个角色专属音色
- 文本→语音合成
- 语音识别输入
- 阅读模式自动朗读

### 智能模型商店
- 自动检测硬件（GPU/内存/磁盘）
- 推荐能跑的最强模型
- 国内镜像加速下载（ModelScope）
- 断点续传

---

## 三平台支持

| 平台 | 格式 | 状态 |
|---|---|---|
| Windows | .exe (NSIS) | 配置完成 |
| macOS | .dmg | 配置完成 |
| Linux | .AppImage | 配置完成 |

---

## 技术栈

- **UI**: Flutter 3 (Dart) + Material 3 + Riverpod
- **后端**: Python 3.10+ + gRPC + PyTorch + transformers
- **渲染**: Python 纯软件光栅 + OpenGL
- **通信**: gRPC (localhost)
- **打包**: PyInstaller + NSIS + create-dmg + linuxdeploy

---

## 开发计划

详见 [docs/小凌v0.0.1开发计划.md](docs/小凌v0.0.1开发计划.md)

---

## License

私有项目，保留所有权利。
