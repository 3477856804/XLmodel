# 语言选型：为什么全项目统一 Python

## 结论

业务逻辑与 3D 渲染层**全部 Python**，项目内不存在 JavaScript / HTML / CSS 业务代码。
GPU 侧仅有 GLSL 着色器（显卡指令集，等价于字节码，内联在 `renderer/gl.py`）。

## 三个决定性理由

### 1. 成长闭环只能 Python
用户的最终诉求是「模型自己长大并脱离原基底」，这要求：
`transformers` 加载基底 → `peft` 注入 LoRA → `merge_and_unload()` 合并 → `save_pretrained()` 落盘。
这条链路在 Python 之外没有等价实现（Node 生态无可用 LoRA 训练框架）。

### 2. 渲染层用 Python 是可行的
原本用 Electron/JS 的 3D 层，已用 Python 重写：glTF/VRM 解析、人形骨骼、蒙皮、
表情形变、弹簧骨、VRMA 动作重定向、MToon 风格卡通着色、透明置顶窗。
代价是放弃 Three.js 的成熟度，收益是**单语言、单进程、可离线、可直接读模型权重**。

### 3. 三级降级保证永不黑屏
```
OpenGL（真机 GPU / Mesa 软件 GL） → numpy 纯软件光栅 → 2D 桌宠（Tkinter）→ 命令行
```
任何一环不可用都不会导致启动失败。本次补全的 `pet.py` 让 2D 兜底不再依赖
视频素材（改为程序化绘制），进一步降低环境要求。

## 取舍记录

| 维度 | 选择 | 代价 |
|---|---|---|
| 训练框架 | PyTorch + peft | 依赖体积大（requirements 单列） |
| 渲染 | 自研 GLSL + numpy 光栅 | 帧率低于 Three.js，但可控且可降级 |
| 桌面壳 | PySide6（Qt） | 无 Qt 时退化为 Tkinter / 命令行 |
| 存储 | SQLite + 文件系统 | 无服务端，天然隐私友好 |
