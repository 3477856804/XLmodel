# 小凌 XLmodel · 项目分析报告

> ⚠️ **这份文件是 v1.1 时期的历史快照，其中多处不是事实**。2026-10-12 复核时
> 逐条查过代码，原第 3、4 节列的模块有一多半在仓库里根本不存在
> （`pet.py`、`core/growth_store.py`、`core/eval.py`、`core/rank.py`、
> `core/lifecycle.py`、`core/device.py`、`core/peft_train.py`、`core/rag.py`、
> `core/selftest.py`、`core/throttle.py`、`renderer/dashboard.py`），
> 目录名 `工具/`、`测试/`、`打包/` 也早已改成 `scripts/`、`tests/`、`packaging/`。
> 顶部那句「扫描仓库真实文件得出，未做任何估算」同样不成立。
> **当前事实请看 [`features.json`](features.json)（含每项状态）与
> [`featureMapping.md`](featureMapping.md)（含核对方式）**，本节只保留原文
> 供对照，并按代码重写了 §3、§4、§6 里最容易被当成承诺的几段。

## 1. 项目定位

`小凌` = **3D 数字人桌宠** + **个人专属模型成长管线**。
用户通过日常对话积累语料，经质量筛选与（可选的）老师端文本蒸馏后训练 LoRA；
适配器长大后合并进基底，成为完全属于用户自己的模型，原基底退役，循环成长。

## 2. 规模快照

（v1.1 时的数字，保留原样仅供历史对照；实时数字见 `docs/stats.json`）

| 指标 | 数值 |
|---|---|
| 文件总数 | 144 |
| 仓库体积 | 196.3 MB |
| Python 文件 | 52 个 / 21198 行 |
| Markdown 文档 | 6 个 / 1179 行 |
| VRM 角色模型 | 7 个 |
| VRMA 动作资产 | 46 个 |

## 3. 技术栈与分层（按当前仓库校正）

```
main.py              进程入口（gRPC 服务 + --selftest 体检）
├── backend/core/     业务层：成长闭环 / 数据仓库 / 蒸馏 / 训练 / 导出 / 记忆 / 通道
│                     （43 个模块；growth.py 同时容纳 GrowthStore +
│                      DistillThrottle + TeacherClient + RankManager +
│                      ModelLifecycle + LoRATrainer + GrowthEngine）
├── backend/renderer/ 资源与状态层：VRM/glTF 解析、动作库、当前模型状态
│                     （画面在 Flutter 端，不在这里）
├── backend/rpc/      gRPC 服务（.proto 已冻结，扩展走 ExecuteCommand + JSON）
├── frontend/         Flutter 桌面 / 移动前端
├── scripts/          形象流水线（VRM 库 / 离线软件光栅预览 / 换装）
├── tests/            回归测试（成长 / 续训 / 蒸馏 / 晋升门槛 / 契约 / 沙箱 …）
└── packaging/        Windows(ISS/NSIS) / Linux(AppImage) / macOS(dmg) / Termux
```

**语言选型**：后端统一 Python（`peft.merge_and_unload()` 这类成长闭环能力只有
Python 生态具备），前端为 Flutter。原报告说的「3D 渲染层整体重写为 Python、
GPU 侧保留 GLSL 着色器」不成立：Python 侧只做资源解析与状态，画面由
`flutter_inappwebview`（WebView2 / WKWebView）与 `resources/web/` 里的
three.js + three-vrm 承担。原因见 [`languageSelection.md`](languageSelection.md)。

## 4. 已实现能力

以 [`features.json`](features.json) 为准（每项都标了真实模块与 `state`，
包括 `partial` / `missing`）。原文里下列说法**不成立**，已删除：

- ~~三条件评估（A 体积 + B 验证集 loss + C 通用基准 常识 20/通用 20/安全 10）~~
  → 真实门槛是**体积 + 磁盘上限**，加可选的 `core/eval_probe.py` 生成式验收
  （4 条探针真跑推理）；验证 loss 只上报不判定，那 50 道题从未存在。
- ~~动态升 rank（旧权重复制保留、新增补零、safetensors 纯 numpy 读写）~~
  → `RankManager` 只把 `adapter_config.json` 的 r 翻倍写回，不动张量，
  且 `grow_rank()` 零调用方。
- ~~显存分级 <4GB 纯 CPU / 4~8GB 4bit 部分层 / >8GB 全 GPU~~
  → 实现是 `HardwareInfo.tier()` 五档 + `train_plan(device)` 的 batch/accum/quant；
  量化仅在显式配 int4/int8 且装了 bitsandbytes 时生效。
- ~~工作台有蒸馏按钮~~ → Flutter 端零命中，蒸馏只在后端 `growth:distill`。
- ~~多平台接入含 QQ~~ → `core/channels.py` 实现的是 telegram / discord / feishu /
  wecom / dingtalk / wechat_oa / whatsapp / slack / signal / email / webhook。
- ~~2D Tkinter 桌宠兜底~~ → 全仓无 tkinter，`pet.py` 从未存在（状态已标 `missing`）。

## 5. 本次补全（v1.0 → v1.1，历史记录）

| 类别 | 内容 |
|---|---|
| 补齐缺失 | `docs/` 全套文档、`scripts/make_sounds.py` 程序化音效（原写的「`pet.py` 桌宠入口」没有落进仓库） |
| 成长二期 | 数据仓库、晋升门槛（原称「三条件评估」）、rank 登记、模型生命周期、蒸馏节流、算力分档 |
| 用户控制 | 暂停/恢复、手动触发、点赞点踩纠正、回滚、导出、清理旧代（**接线状态见 §6.10**） |
| 回归测试 | 当时新增成长 v2 用例；现行测试见 `tests/`（含 `test_resume.py`、`test_distill.py`、`test_promotion_gate.py`、`test_sandbox_degraded_guard.py`、`test_model_search.py`、`test_webpanel_static.py`） |

## 6. 已知边界（诚实说明，按代码校正）

0. **形象资源的真实来源（务必别搞错）**：翻遍 Gitee 与 GitHub 两个远端的
   **全部提交历史**，没有任何一个 `.vrm` / `.glb` / `.fbx` 文件曾被提交或删除过 ——
   原因是 `.gitignore` 用 `resources/models/` 排除了整个目录，而被忽略的目录
   Git 不会进入，`!` 例外规则永远不生效。所以「去历史里把之前那几个人物 3D 模型放回来」
   **做不到**，不是没找。现在仓库带的 `resources/models/小凌.vrm` 是用仓库自有管线
   真实生成的（`scripts/xiaoling_avatar.py` + `scripts/vrm_lib.py`，
   基底来自 ModelScope `oleehu/vrm-models`，脸图 `resources/materials/xiaoling.png`），
   来源、授权与再生命令写在 `resources/models/README.md`。
1. **降级沙箱不是安全边界**：本机内核 5.10 → 无 Landlock，因此「降级路径就是默认路径」。
   `lexical_escape_check()` 只镜像 Landlock 的放行面，`cat /etc/passwd` 是刻意放过的；
   返回体标 `guard:'lexical'`，`capability().path_isolation` 仍为 `False`。
   Windows Job Object 只限资源、不做路径隔离。真机需要 OS 级路径强制请上 ≥5.13 内核。
2. **硬件推荐依赖探测成功**：`model:recommend` 拿不到 RAM 时 `available:false`、
   `why` 写明原因，并把所有 `recommended` 强制置 `false`。前端如实显示「硬件未探测到」，
   不编一个推荐出来。Android/Termux 上的 `nvidia-smi`、`shutil.disk_usage` 行为未经真机验证。
3. **远端搜索依赖魔搭 OpenAPI 可用性**：`/openapi/v1/models?search=` 实测可用，
   但 `success=false`、非 200、JSON 解析失败一律 `ok:false + error`，
   并保留「重试」入口 —— 不会把接口故障画成「没有这个模型」。
   非量化仓库（没有 `.gguf`）无法直接下载，会照实说明而不是硬下。
5. **生成式验收默认关**：`growth.require_eval=false` 时晋升只看体积与磁盘上限，
   报告与 `growth:promotecheck` 会明说「未做生成式验收，仅凭 loss 晋升」；
   开启后探针跑不动或没跑全一律拦住，不会「看不见就当过了」。
6. **费用估算单价为示例值**：`growth.teacher_price_in/out` 默认 1/2 元每百万 token，
   非官方报价，仅为本地估算，请自行改为实际资费。
7. **蒸馏需要老师端**：`deepseek_api_key` / `deepseek_base_url` / `teacher_model`
   三者齐备且 key 不是占位符才算已配置；未配置时对话照常入库但不入队，
   一条请求都不发。这里是**文本蒸馏**（把老师答案当 SFT 语料），不是 soft-label KD。
8. **Android APK 需本地构建**：Termux 脚本与 Flutter 工程就位，仓库不附带产物，
   也没有 Chaquopy 配置。
9. **授权限制**：基底 VRM 授权含 `Redistribution_Prohibited` 时，
   改造产物仅供本地自用，请勿再分发。
10. **暂停/回滚/GC/清库已接通到前端**：后端六条子命令 `growth:pause` /
   `growth:resume` / `growth:status` / `growth:rollback` / `growth:gc` /
   `growth:purge`（只读或演练为默认，破坏性动作必须显式 `confirm`），
   实测见 `tests/test_growth_ops.py`；成长页「成长工具」区新增
   「暂停成长 / 恢复成长」按钮与「成长运维」浮层
   （`frontend/lib/pages/growth_page.dart`）。
   **仍未验证的部分要说清**：本机没有 Flutter SDK，Dart 侧只用
   `dart format` 做过解析校验（能解析、未改仓库既有格式），
   没有跑过 `flutter analyze`，也没有真机点过 —— 按钮是否真的可用属待验证。
   蒸馏（`growth:distill`）在 Flutter 端依然**没有任何入口**（`grep 蒸馏|distill` 零命中）。
11. **模型商店的魔搭面板同样未经真机验证**：后端 `model:search` / `files` / `recommend` /
   `downloadremote` 已用真实魔搭接口跑通（`search qwen2.5 gguf` → total 5200、
   `recommend` → tier=entry、`files` → 42 个文件），单元与离线回归见
   `tests/test_model_search.py`。但新增的前端面板
   `frontend/lib/widgets/model_remote_panel.dart` 与页面接线
   （`model_store_page.dart` 的「魔搭社区」一节）只过了 `dart format` 解析校验，
   **没有** Flutter SDK 无法 `flutter analyze`，也没有在手机上点过：
   搜索防抖、分页按钮、展开列文件、下载进度轮询（2 秒一次 `sandbox:status`）、
   取消（`agent:task cancel`）这些交互是否顺手，仍需真机复核。
   内置清单上方那个搜索框现在明确标注为「本地筛选」，远端搜索走新面板。

