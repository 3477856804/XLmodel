# 更新日志

本文件记录小凌 XIAOLING 的版本变更。格式遵循「分类 + 条目」，版本号语义与
`backend/core/config.py`（CURRENT_VERSION）、`frontend/pubspec.yaml`（version）保持一致。

## [0.0.1] - 2026-10-08

首个正式发布版本。完成从「单文件巨石 xl.py（7199 行）」到「Flutter 前端 +
Python gRPC 后端」新架构的重构，打通 Windows / Linux / macOS / Android 四端打包与
GitHub Release 发布链路。

关键里程碑：

- 去伪存真 9 轮：清理旧架构残留，删除 core/ renderer/ 等 15 个旧目录与 xl.py 等旧文件
- 16 个内置插件（日历、代码工具、Git、笔记、PDF、RSS、系统监控、待办、翻译、天气、网页摘要等）
- 11 个消息通道（Telegram / Discord / 飞书 / 企业微信 / 微信公众号 / 钉钉 / Slack / Signal / WhatsApp / Email / Webhook）
- 46 个 gRPC 接口（Flutter 前端与 Python 后端契约）
- 143 个自动化测试全部通过

### 新功能

- 新架构落地：Flutter 桌面前端 + Python gRPC 后端，前端按 exe 同目录自动拉起后端，监听 localhost:50051
- 真 3D 形象：桌面端走内置 WebView + three.js / three-vrm 离线渲染 VRM 模型，含动作库（.vrma）
- 本地模型推理：GGUF 经 llama.cpp 运行时加载聊天；safetensors 格式与 LoRA 训练由完整版提供
- 成长闭环：蒸馏 / 合并 / 晋升管线，LoRA 适配器与成长日志落在用户数据沙箱
- 插件系统：右下角入口图形化，万物皆插件，内置 16 个插件并支持用户插件动态加载
- 多通道接入：11 个消息平台通道，Bot API / Webhook 无需额外依赖即可启用
- 工作台 UI：对话栏、角色选择、模型选择、蒸馏按钮、设置面板全部图形化，后台预加载引擎避免卡顿
- 自检与状态：`python main.py --selftest` 与 `--status` 一键体检
- 单文件 exe：启动器自解压到 %LOCALAPPDATA%，首次释放后毫秒级冷启动，覆盖升级自动重新释放

### 修复

- 修复 PyInstaller 打包后 3D 查看器黑屏：contents_directory 平铺资源，使 sys._MEIPASS 与资源真实位置一致
- 修复后端在 Windows 打包后找不到 VRM / 插件 / proto：backend.spec 显式收集资源与 hiddenimports
- 修复插件在打包后全部静默失效：随包拷贝 plugin.json，缺失时不再跳过加载
- 修复插件启用状态误带开发机快照：打包时排除 state.json，运行时按需重建
- 修复数据目录与 Flutter 自带 data/ 撞名：打包态把可写数据隔离到用户沙箱 runtime/
- 修复后端残留进程占用 50051：前端退出后由启动器统一回收后端进程
- 修复单文件启动器尾部资源解析顺序：与写入端严格对齐，避免误判无内置资源
- 修复 Python 3.11 下 f-string 含反斜杠的语法错误
- 修复 3D 模型渲染破碎：禁用 cluster_decimate 过度简化，正确关联 mesh 的 skin_index
- 修复 GitHub Release 上传权限与资产文件匹配问题

### 优化

- 去伪存真 9 轮：删除旧架构 15 个目录与 xl.py 巨石，合并功能相近模块（knowledge / system / guards / scheduler 等）
- 体积控制：打包排除 torch / transformers（合计约 4.2GB），GGUF 路径不依赖 torch 即可聊天
- 构建与 CI：GitHub Actions 四端矩阵构建并自动上传 Release 资产
- 启动体验：无 GPU 时自动 Mesa 软件光栅并关闭 llvmpipe JIT 优化，避免虚拟化 CPU 非法指令
- 版本管理：版本号统一收敛到后端单一来源，打包脚本不再散落硬编码
- 依赖清单：补齐 llama-cpp-python / protobuf / requests / aiohttp，明确标注可选依赖
- 仓库卫生：移除大文件资产、完善 .gitignore、取消跟踪 .dart_tool

### 文档

- 新增本 CHANGELOG
- 完善打包说明：四端脚本与 CI 矩阵、产物命名规范、数据目录与沙箱说明
- README 对齐新架构入口与版本信息

### 产物命名规范

GitHub Release `v0.0.1` 挂载以下资产：

- xiaoling-windows-0.0.1.zip
- xiaoling-linux-0.0.1.tar.gz
- xiaoling-macos-0.0.1.dmg
- xiaoling-android-0.0.1.apk
