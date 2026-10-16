# 语言选型：为什么后端统一 Python（含旧版结论的勘误）

> 这份文档的旧版本写于重构前，里面有四条今天**不成立**的事实，已在正文逐条更正：
> ~~「3D 渲染层全部 Python」~~、~~「GPU 侧仅有 GLSL 着色器，内联在 `renderer/gl.py`」~~
> （`renderer/gl.py` 不存在，全仓 `.glsl` 零命中）、~~「桌面壳 PySide6（Qt）」~~
> （`requirements.txt` 第 6 行已明写「不再包含 PySide6/PyOpenGL，旧架构遗留，
> 后端已无引用」，全仓无 QtWidgets）、~~「`pet.py` 的 Tkinter 2D 兜底」~~
> （`pet.py` 从未进过仓库，全仓 `tkinter` 零命中）。
> 结论本身（后端只用 Python）依然成立，但理由要换成经得起查的那三条。

## 结论

**后端业务逻辑全部 Python**；画面由 Flutter 前端（`flutter_inappwebview` +
离线 three.js / three-vrm，资源在 `resources/web/`）承担。
Python 后端不做实时渲染，只做 VRM/glTF 的**解析与状态管理**
（`backend/renderer/stage.py`、`vrm_gltf.py`）。
仓库里没有 JavaScript 业务代码 —— `resources/web/viewer.html` 是查看器宿主页面，
不是业务层。

## 三个决定性理由（按可核对的事实写）

### 1. 成长闭环只能 Python

用户的最终诉求是「模型自己长大并脱离原基底」，这要求：
`transformers` 加载基底 → `peft` 注入 LoRA → `merge_and_unload()` 合并 →
`save_pretrained()` 落盘，再加优化器状态续训与 GGUF 导出。
这条链路在 Python 之外没有等价实现（Node 生态无可用 LoRA 训练框架）。
对应代码：`core/growth.py`、`core/trainer.py`、`core/export.py`。

### 2. 推理与训练要直接读权重，Python 生态是前提

LoRA 合并、验收探针（`core/eval_probe.py` 真跑一次生成）、GGUF 转换
（`core/export.py` 调本机 llama.cpp，只探测不代装）都要在同一进程里拿到张量。
换任何别的语言，这几步都得跨进程传权重，成长闭环就不成立了。

### 3. 降级链是真的存在的，但方向和旧文档写的不一样

```
有 GPU（best_device→cuda/mps） → 纯 CPU（train_plan：batch 1 / grad_accum 8 / 不量化）
有 llama.cpp（GGUF 推理）        → 没有就只跑 transformers，并如实报不可用
有嵌入模型（sentence-transformers）→ 没有就 hash-ngram 关键词降级，stats() 里标注
有图形环境（Flutter WebView 出画面）→ 没有就命令行对话 + `scripts/vrm_preview.py` 离线出图
```

最后一条是**离线出图**，不是运行时窗口：`scripts/vrm_preview.py` 里那份
numpy 三角光栅只用于校验形象资源，不在交互链路上。
旧文档说的「OpenGL → numpy 光栅 → Tkinter → 命令行」四级运行时降级没有实现，
Tkinter 那一级根本不存在。缺依赖时后端的行为是**如实报错并降级**，
而不是自动换一套渲染栈。

## 取舍记录

| 维度 | 选择 | 代价 |
|---|---|---|
| 训练框架 | PyTorch + peft | 依赖体积大，打包版默认排除 torch 全家（约 4.2GB），装完才出真训练 |
| 画面 | Flutter + 离线 three.js / three-vrm | 后端拿不到渲染结果，只能用 `stage.state()` 同步模型/动作状态；好处是四端同一套 |
| 桌面壳 | Flutter（`window_manager` 提供置顶/透明度） | 多语言栈（Dart + Python），靠 gRPC 契约粘合；`.proto` 已冻结，扩展只能走 ExecuteCommand + JSON |
| 存储 | SQLite + 文件系统 | 无服务端，天然隐私友好；代价是没有并发多客户端 |
