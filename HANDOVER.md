# 小凌 XIAOLING v0.0.1 交接文档

## 架构
Flutter (UI) + Python (AI后端) + gRPC (localhost:50051)

双击exe/AppImage/dmg启动，Flutter自动拉起Python后端，用户视角只有一个程序。

## 目录结构
```
backend/core/    后端核心
  config.py      路径+配置+插件+更新检查
  engine.py      主引擎+意图路由+事件总线
  growth.py      LoRA训练+数据仓库+生命周期
  memory.py      记忆+人格+情绪+关系+RAG+知识图谱
  model.py       硬件探测+模型商店+本地推理
  multimodal.py  TTS语音+ASR+截屏+摄像头+VLM
  tools.py       工具+定时任务+守卫+多Agent
  channels.py    Webhook/Telegram/Discord/飞书/邮件通道
  search.py      DuckDuckGo联网搜索
backend/rpc/     gRPC服务端+pb生成文件
frontend/lib/    Flutter UI
  main.dart     入口+主框架
  pages/        8个页面(聊天/仪表盘/成长/模型商店/插件/设置/启动屏/训练)
  theme/        粉金新拟态主题
  rpc/          gRPC客户端
  widgets/      3D模型展示+更新弹窗
website/         官网源码(Cloudflare Pages)
packaging/       CI打包配置
scripts/         VRM转FBX工具
resources/       模型+音频+材质
```

## 关键信息
- gitee: https://gitee.com/COSMOnb666/XLmodel
- github: https://github.com/3477856804/XLmodel-release
- 官网: https://xiaoling-4o6.pages.dev/
- CI: tag flutter-v0.0.1 触发三平台打包
- 下载: Windows .exe / Linux .AppImage / macOS .dmg
- 版本: v0.0.1
