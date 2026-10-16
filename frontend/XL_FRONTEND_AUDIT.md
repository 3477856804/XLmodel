# 晓灵（XiaoLing）Flutter 前端功能完整性审计报告

- 审计对象：`frontend/lib/`（业务代码，已排除 `*.pb*.dart` proto 生成文件）
- 审计方式：**只读静态走查**，未修改任何代码
- 业务代码规模：**31,848 行**（非 proto）；共 44 个 Dart 文件
- 判定标准：功能是否真正调用后端 RPC / 本地持久化 / 真实进程，而非空壳或前端伪造

---

## 一、总体结论（TL;DR）

| 维度 | 结论 |
|---|---|
| 工程骨架 | **扎实**。gRPC 客户端带重试/熔断/健康探测/自动重连/端点回退，错误处理统一 |
| 设计系统 | **完整且高质量**。新拟态（Neumorphism）+ 粉金/黑白深浅双主题，全局生效 |
| 核心主链路 | **真实可用**：聊天流式对话、训练流式、模型下载流式、文件读写、远程终端、本地 git、通知/Reminder、人格 Persona |
| 主要短板 | **"数据看板类"功能大量使用前端伪造数据**：仪表盘 CPU/内存环、成长页时间轴/周对比/情绪曲线、活动流、性格特质、安全中心、社区插件安装、子 Agent 编排、MCP 列表、工作流执行 |
| 空壳/TODO | 几乎没有（全仓 0 个真实 TODO 注释、0 个字面 `onPressed:null`）。问题不在"没按钮"，而在"按钮有反应但反应是假的" |

一句话：**这是一个 UI 完成度极高、动效极其密集的客户端骨架；主业务闭环（聊/练/装模型/文件/终端/git）接了真后端，但"展示型"和"编排型"模块多为演示数据驱动。**

---

## 二、全局统计

| 指标 | 数值 |
|---|---|
| 顶层页面（pages/ + main） | **14** |
| 组件（widgets/） | **16** |
| 自定义 Widget 类总数（含私有辅助类） | **77**（67 Stateful + 10 Stateless） |
| 有状态 Widget 比例 | **≈ 87%**（67/77） |
| `AnimationController` 实例化数量 | **61** |
| 真实 TODO/FIXME 注释 | **0**（唯一命中 `agent_panel.dart:28` 是任务模板字符串"搜索项目中的 TODO"，非注释） |
| 字面空回调 `onPressed:null`/`onTap:null` | **0** |

> 说明：有状态占比与动画控制器数量偏高，反映该项目以"动效密集型大屏/卡片"为主，而非简洁表单型应用。

---

## 三、基础设施审计

### 1. `rpc/client.dart`（XlClient）— 真实、健壮
- 单例 gRPC 通道；自动重连、指数退避重试（`RetryPolicy`）、调用指标计数。
- 健康探测轮询 + `onStatusChange` 驱动全局在线/离线态。
- 端点回退列表、`fastCall` 安全包装。
- **隐患**：`_PendingCall.cancel()` 仅置标志位，**未真正取消底层 gRPC 流**（见聊天页"中断"问题）。

### 2. `theme/theme.dart`（1431 行）— 完整设计系统
- `XlPalette`：深色 `#17131D` 底 + 粉 `#FF6FA5` + 金 `#E8C46A`；浅色主题齐备。✅ 粉金黑白、深浅双主题。
- 新拟态：`neu*/sunken*/raised*` 双阴影（明暗双向偏移）装饰器全套。✅
- 响应式断点：mobile <600 / tablet / desktop。✅
- **隐患**：`XlPalette.copyWith` 直接 `return this`（~998 行）、`lerp` 非真实插值（~1003 行）。因主题为整体切换、未做局部补间，暂不暴露，但属于埋雷。

### 3. `services/sandbox.dart` — 真实原生桥接
- Android `MethodChannel(xiaoling/sandbox)`：start/stop/status/downloadModel。✅ 移动端沙箱真实存在。

### 4. `updater.dart` — 真实
- GitHub Releases 检查、镜像回退、版本比较、changelog 解析、本地缓存。✅

### 5. RPC 表面（pages 层直连 stub）
后端实际暴露能力（页面直接调用 stub 验证）：`chat` 流式、`status/bootstrap`、`growth`、`training`/`startTraining` 流式/`getTrainingHistory`、`models`/`recommended`/`installedModels`/`download` 流式/`switchModel`、`plugins`/`enablePlugin`/`disablePlugin`、`voices`/`readAloudBytes`、`settings`/`updateSettings`、`actions`/`command`、`persona` CRUD、`reminders`/`fetchReminders`/`finishReminder`、`fileList`/`fileRead`/`fileWrite`、`terminalCreate`/`terminalRead`流/`terminalWrite`/`terminalClose`、`agentStart` 流式、`projectContext`/`codeSearch`。
> ⚠️ 无后端的能力：git（前端 `Process.run` 本地执行）、MCP、安全审计、工作流执行、社区插件安装、子 Agent 编排。

---

## 四、页面逐个审计（14）

图例：✅ 真实接后端/持久化 ｜ 🟡 半真（UI 真、数据或落库假） ｜ 🔴 演示/伪造

### 1. `main.dart`（HomeShell 入口壳）
- 核心 Widget：`HomeShell`（Stateful，`TickerProviderStateMixin`）。
- 关键功能：开机拉起 `backend.exe` → 探测 gRPC → 起 Android 沙箱；7 页导航；深浅主题切换；通知/人格侧滑覆盖层；全局搜索浮层。
- 状态：`setState` + 2 个 AnimationController（辉光/侧栏）。
- 响应式：✅ <600 用底部导航，否则侧边栏。
- **要点**：仅挂载 **7 个**主页面（聊天/工作台/训练/成长/设置/模型商店/插件）；其余 5 页走二级跳转（见下）。主题切换**仅内存态**，未持久化。

### 2. `splash_page.dart` — 🟡
- 核心 Widget：`SplashPage`（Stateful，**8 个 AnimationController**：脉冲/进度/淡入/旋转/光环/浮动/文字/微光）。
- 加载阶段文字轮播为装饰；**跳转靠固定 2.6s 定时器，不等真实后端就绪**（虽在探测，但不阻塞于探测结果）。

### 3. `dashboard_page.dart`（工作台）— 🟡（外壳真、数据半假）
- 核心 Widget：`DashboardPage`（Stateful，7 AnimationController）。
- 真实：`bootstrap()` 拉 status/growth/training/hardware；**离线横幅 + 重试**✅；**9 个快捷操作全部可跳转**✅（聊天/语音/模型商店/插件/终端/git/工作流/训练/成长）；硬件加速标签。
- 🔴 **资源环形图数据伪造**：`_tickResource()` 每 1.6s 对 CPU/MEM/DEM 做随机游走，并非真实硬件遥测。
- 🔴 **"自动刷新"是假的**：30s 倒计时归零只 `_refreshTick++` 并改时间戳，**不重新 `_bootstrap()`**（手动按钮才真刷新）。
- 🔴 活动时间线、性格特质（温柔/活泼…）、"本周 +8%" 等为本地编造文案。

### 4. `chat_page.dart`（聊天）— ✅（主链路真实，1 处缺陷）
- 核心 Widget：`ChatPage`（Stateful，4 AnimationController + 消息气泡私有控制器）。
- 逐项：
  - 流式对话 ✅（`chatSession(...).onDelta`）
  - 搜索高亮 ✅（`_searchCtrl` 过滤 + `RichText` 高亮 + 命中计数）
  - 消息导出 ✅（写 `.txt` + `.json` 到应用目录）
  - 引用回复 🟡（引用横幅真实，发送时仅把引用文本拼进消息前缀，非结构化引用/回链）
  - 输入历史 ✅（Alt+↑/↓，**内存态不持久**）
  - AI 中断 🔴（见问题清单：仅置 UI 状态，未取消 gRPC 流，deltas 仍追加）
  - 时间戳 ✅（`_showTimestamp` 开关 + 气泡下时钟）
  - 附加：TTS（`readAloudBytes`→mp3 播放）✅；跳 Agent 页 ✅。
- **聊天记录不跨会话持久化**（纯内存 `_msgs`）。

### 5. `training_page.dart`（训练）— ✅（主链路真实）
- 核心 Widget：`TrainingPage`（Stateful，3 AnimationController + 日志/雷达/损失图私有控制器）。
- 真实：`training()` 状态；`startTraining(TrainingRequest)` **流式**返回 step/loss/totalSteps；`getTrainingHistory` 历史记录。
- 逐项：参数配置(lr/bs/rank/steps)✅；实时 Loss 曲线 ✅（`_LiveLossChart` 累积最多 60 个流式 loss 点）；进度✅；历史记录✅；ETA✅（按实测步速 `_recalc` 真算）；参数预设 🟡（3 个静态预设 + 自存预设**仅内存**）。
- 停止为客户端"停止监听"（`_stopRequested` break 循环），未发后端停止指令。

### 6. `growth_page.dart`（成长）— 🟡
- 核心 Widget：`GrowthPage`（Stateful，`_timelineCtrl` 等）。
- 真实：亲密度 `normalizedProgress`、段位/rank、进化代数、情绪 `displayEmotion/emotionEnergy` 均来自 `growth()`；**数据导出**✅（写 CSV/JSON）；每日目标今日计数来自后端。
- 🔴 **时间轴**：6 个硬编码节点（初识/记忆突破…），日期为 `DateTime.now().subtract` 编造。
- 🔴 **周对比**：`thisWeek/lastWeek` 写死数组。
- 🔴 **情绪趋势 sparkline**：写死 7 个 double。
- 🟡 每日目标 `_dailyGoal` 本地 ±5 调整，不持久。

### 7. `settings_page.dart`（设置）— 🟡
- 核心 Widget：`SettingsPage`（Stateful）。
- 真实：主题切换（注入上层）；MCP 入口→`McpPanel`✅；安全中心→`SecurityPanel`✅；诊断/变更日志区；系统信息。
- 🟡 **多通道开关**：`_channels` 本地态，切换时调用的是**空 `SettingsRequest()`**（未真正下发通道配置）。
- 🟡 **语言切换**：仅切字符串变量，UI 自注"目前仅简体中文为完整支持"——无实际 i18n。

### 8. `model_store_page.dart`（模型商店）— ✅
- 核心 Widget：`ModelStorePage`（Stateful）。
- 真实：模型列表/推荐 `models()`/`recommended()`；已安装 `installedModels()`；**下载进度流式** ✅（percent/速度/已下MB，支持并发 `_downloading` 集合）；分类✅；搜索✅；量化筛选(Q4/Q8)✅；换模型 `switchModel`。
- 🟡 **收藏**：`_favorites` Set 内存态，不持久。
- 🟡 下载队列条展示进行中的并发下载（真实），但无后台排队/失败重试队列管理。

### 9. `plugins_page.dart`（插件）— ✅
- 核心 Widget：`PluginsPage`（Stateful）。
- 三标签 **已安装/商店/社区** ✅；列表来自 `plugins()`；开关 ✅（`enablePlugin/disablePlugin` 真 RPC，带 busy 态与结果回显）；配置入口；社区→`PluginCommunityPage`。

### 10. `plugin_community.dart` — 🔴（展示壳）
- `PluginCommunityPage` 为静态社区内容列表；安装动作落到 `plugin_store._install`（见组件：仅延时 900ms 后标记已装，无后端）。

### 11. `terminal_page.dart`（终端）— ✅
- 薄壳：两 Tab（终端 / 文件浏览器）。
- 终端→`TerminalPanel`（**真实 gRPC 远程终端**）；文件→`FileExplorer`（`fileList`）+ `CodeEditor`（`fileRead/fileWrite`）。

### 12. `agent_page.dart`（Agent）— 🟡/🔴
- 真实部分：`AgentPanel` 接 `agentStart(AgentRequest)` **流式执行**；`CodeSearchPanel` 接 `projectContext/codeSearch`；`AgentCreator` 本地 JSON 持久化 CRUD。
- 🔴 **`SubAgentPanel`（子 Agent 编排）纯前端模拟**：`Timer.periodic(450ms)` 本地把任务 pending→running→completed、进度 +18/tick，结果文案写死"子 Agent 完成任务…"，无任何后端调用。

### 13. `git_page.dart`（Git）— ✅
- 薄壳包裹 `GitPanel`。**真实**：`Process.run('git', …)` 本地执行 status/log/diff/branch/add/commit/checkout。
- ⚠️ 仅桌面可用（依赖本机 git 二进制与工作目录），Android 沙箱内不可用。

### 14. `workflow_page.dart`（工作流）— 🔴
- 薄壳包裹 `WorkflowBuilder`；画布节点/已存工作流均为**本地内存列表，无"运行工作流"后端 RPC**。无代码搭建器可拖拽编辑，但执行未接线。

---

## 五、组件逐个审计（16）

| 组件 | 核心类 | 功能 | 真实度 |
|---|---|---|---|
| terminal_panel | `TerminalPanel` | gRPC 远程终端（Create/Read 流/Write/Close，ANSI 剥离） | ✅ 真实 |
| file_explorer | `FileExplorer` | `fileList` 递归目录浏览 | ✅ 真实 |
| code_viewer | `CodeViewer` | 代码查看/高亮展示 | ✅ 展示（读文件内容） |
| code_editor | `CodeEditor` | 编辑并 `fileWrite` 保存 | ✅ 真实 |
| agent_panel | `AgentPanel` | `agentStart` 流式任务执行 | ✅ 真实 |
| code_search_panel | `CodeSearchPanel` | `projectContext` + `codeSearch` | ✅ 真实 |
| agent_creator | `AgentCreator` | 自定义 Agent 增删改默认，写本地 JSON | 🟡 本地持久化，非后端执行 |
| git_panel | `GitPanel` | `Process.run('git')`：变更/历史/分支/diff/提交 | ✅ 真实（仅桌面） |
| mcp_panel | `McpPanel` | MCP 服务器/工具列表 | 🔴 本地列表，无后端连接 |
| security_panel | `SecurityPanel` | 工具权限/操作审计 | 🔴 硬编码 `_tools`/`_audit` 列表 |
| persona_panel | `PersonaPanel` | 人格 CRUD/切换/重置（fetchPersona(s)/switch/create/remove/reset） | ✅ 真实 |
| notif_panel | `NotifPanel` | 训练态 + Reminders 拉取/完成 | ✅ 真实 |
| update_dialog | `showUpdateDialog` | 基于 `Updater` 的版本更新/更新日志/版本对比 | ✅ 真实 |
| model_showcase | `ModelShowcase` | 3D/舞台式模型展示 | 🟡 展示组件 |
| plugin_store | `PluginStore` | 社区插件商店 | 🔴 `_install` 仅 `Future.delayed(900ms)` 标记已装，无后端 |
| workflow_builder | `WorkflowBuilder` | 无代码拖拽画布 | 🔴 本地节点，无运行接线 |

---

## 六、功能验证对照表（按需求逐项）

| 需求功能 | 结论 | 说明 |
|---|---|---|
| **聊天·流式对话** | ✅ | chatSession onDelta 真流式 |
| 聊天·搜索高亮 | ✅ | 过滤+RichText 高亮+计数 |
| 聊天·消息导出 | ✅ | txt+json 落本地 |
| 聊天·引用回复 | 🟡 | 仅文本前缀拼接，非结构化引用 |
| 聊天·输入历史 | ✅ | Alt+↑↓，内存态 |
| 聊天·AI 中断 | 🔴 | 未真正取消底层流 |
| 聊天·时间戳 | ✅ | 开关+气泡下时钟 |
| **仪表盘·资源环形图** | 🔴 | 随机游走伪造，非真实 CPU/MEM |
| 仪表盘·自动刷新 | 🔴 | 倒计时装饰，不真重拉 |
| 仪表盘·快捷操作 | ✅ | 9 个全部可达 |
| 仪表盘·离线状态 | ✅ | 离线横幅+重试 |
| **训练·参数配置** | ✅ | lr/bs/rank/steps |
| 训练·实时 Loss 曲线 | ✅ | 流式累积绘图 |
| 训练·进度 | ✅ | step/total |
| 训练·历史记录 | ✅ | getTrainingHistory |
| 训练·参数预设 | 🟡 | 静态预设+内存自存 |
| 训练·ETA | ✅ | 按步速实算 |
| **成长·亲密度/等级/进化/情绪** | ✅ | 来自 growth() |
| 成长·时间轴 | 🔴 | 6 个硬编码节点 |
| 成长·每日目标 | 🟡 | 今日计数真，目标阈值本地 |
| 成长·周对比 | 🔴 | 写死双周数组 |
| 成长·数据导出 | ✅ | CSV/JSON |
| **设置·多通道配置** | 🟡 | 开关本地，下发空请求 |
| 设置·主题 | ✅ | 深浅切换 |
| 设置·语言 | 🔴 | 仅 UI 占位，无 i18n |
| 设置·MCP 入口 | ✅ | 可打开面板（面板本身假） |
| 设置·安全中心 | 🔴 | 硬编码权限/审计 |
| 设置·变更日志/系统信息 | ✅ | 基于 Updater |
| **模型商店·列表/下载进度/分类/搜索/量化筛选** | ✅ | 全部真实流式 |
| 模型商店·收藏 | 🟡 | 内存态 |
| 模型商店·下载队列 | 🟡 | 并发下载真，无排队管理 |
| **插件·三标签/开关/配置** | ✅ | enable/disable 真 RPC |
| **终端·终端模拟器** | ✅ | gRPC 真远程终端 |
| 终端·文件浏览器/查看器/编辑器 | ✅ | fileList/Read/Write |
| **Agent·任务执行** | ✅ | agentStart 流式 |
| Agent·代码搜索 | ✅ | codeSearch |
| Agent·子 Agent | 🔴 | 前端 450ms tick 模拟 |
| Agent·自定义 Agent 创建 | 🟡 | 本地 JSON 持久化 |
| **Git·变更/历史/分支/diff** | ✅ | 本机 git（仅桌面） |
| **工作流·无代码构建器** | 🟡 | 画布可搭，执行未接线 |
| **主题·新拟态/粉金黑白/深浅双主题** | ✅ | 完整设计系统 |
| **移动端·响应式/底部导航/沙箱** | ✅ | 断点+底栏+Android MethodChannel |

---

## 七、问题清单（按严重度）

### 高（功能名不副实 / 静默错误）
1. **聊天"中断"不真正中断**：`_interruptGeneration` 仅置 `_interruptRequested`/`_busy`，未取消 `chatSession` 底层流；onDelta 回调仍会继续向消息追加 token。根因在 `XlClient` 的 `cancel()` 只置标志、未发 gRPC cancel。
2. **仪表盘资源环数据伪造**：CPU/MEM/DISK 来自 `_tickResource` 随机游走，与硬件无关，易误导用户。
3. **仪表盘"自动刷新"名不副实**：30s 归零只改计数，不触发 `_bootstrap()` 重拉。
4. **子 Agent 编排（agent_page SubAgentPanel）纯演示**：450ms 定时器伪造进度与结果，无后端。
5. **社区插件安装（plugin_store）假安装**：900ms 延时后本地标记已装，无安装 RPC。
6. **安全中心（security_panel）/MCP（mcp_panel）硬编码**：权限清单与审计日志、MCP 服务器列表均为写死数据。

### 中（数据不持久 / 行为与文案不符）
7. **多通道设置下发空请求**：`updateSettings(SettingsRequest())` 未携带 `_channels`，开关重启即丢、后端未生效。
8. **聊天记录/输入历史不持久**：纯内存，杀进程即失。
9. **模型收藏、训练自存预设、每日目标**均为内存态。
10. **语言切换无实际 i18n**：UI 占位。
11. **成长页时间轴/周对比/情绪曲线**为硬编码演示数据。
12. **主题切换不持久化**（main.dart `_mode` 仅内存）。
13. **工作流无运行接线**：可编辑不可执行。

### 低（健壮性 / 跨端）
14. `XlPalette.copyWith` 返回 `this`、`lerp` 非真插值（埋雷）。
15. `git_panel` 依赖本机 git，Android 沙箱不可用；页面未做平台降级提示。
16. splash 跳转靠固定 2.6s，未与后端探测结果强绑定（慢机可能进 HomeShell 时后端未就绪，靠各页自己的错误重试兜底）。
17. 导出文件写入应用目录，无系统分享面板（移动端用户不易拿到文件）。

---

## 八、总结

- **架构成熟度高于典型"演示项目"**：gRPC 层、设计系统、响应式与动效都达到产品级水准，没有空按钮、没有 TODO 债。
- **真实打通的主闭环**：聊天流式、训练流式、模型下载流式、远程终端、文件读写、本地 git、人格/通知/插件开关——这些是"能用"的。
- **主要风险集中在"看起来很炫但数据是假的"的展示与编排模块**：仪表盘资源/自动刷新、成长时间轴/周对比、子 Agent、社区插件安装、安全中心、MCP、工作流执行。对外演示无虞，但若以"已交付功能"对外承诺，这几处需接真后端或降级标注为演示。
- **建议下一步优先级**：
  1. 修复聊天中断的真取消（`XlClient` 透传 gRPC cancel）；
  2. 仪表盘资源环接 `HardwareInfo` 真实遥测、自动刷新真正重拉；
  3. 多通道设置把配置真正塞进 `SettingsRequest`；
  4. 对伪造模块要么接后端，要么在 UI 标注"演示数据"，避免误导。
