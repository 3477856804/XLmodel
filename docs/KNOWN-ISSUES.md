# 待改进清单（KNOWN-ISSUES）

> 来源：2026-10-14 用户实测反馈（QQ 截图整理）。
> 状态标记：⬜ 未开始 / 🔶 进行中 / ✅ 已解决。
> 纪律：任何修复不得删除文件，改动前同目录留 `.bak` 备份，并追加变更记录到 `docs/CHANGES-*.md`。
> 本轮（第二批，2026-10-14）详细过程见 `docs/CHANGES-2026-10-14b-unified-api-and-sandbox-shell.md`。

## 一、语音对话不能用（优先级：高）——🔶 识别已通，录音仍缺依赖

- **现象**：顶部告警「语言识别未配置（whisper 未安装）」，语音对话功能整体不可用。
- **已修（2026-10-14 第二批）**：
  1. 设置页新增「API 配置」选项卡（统一外部 API，见本文件第八节）；
  2. whisper 未装但已配置外部 API 时，`ASR.available()` 返回 True，
     识别改走 OpenAI 兼容 `/audio/transcriptions`（纯标准库 multipart，无新依赖）；
     端点返回空结果时如实报错，不冒充识别成功。
- **剩余（如实说明，非代码问题）**：
  1. **后端麦克风录音需要 `pip install pyaudio`** —— 这是环境缺依赖，本轮没有（也无法）绕过；
  2. 打包产物内置 whisper 运行时与模型，或首启引导一键下载；
  3. 真机验证：配置真实兼容端点后走一次完整「按住说话 → 识别 → 回复」链路。

## 二、表情包不能用（优先级：中）——✅ 已解决（假按钮换成真面板）

- **原委**：表情按钮是**假的**——点击没有任何实现。
- **已修（2026-10-14 第二批）**：零依赖方案，Dart `\u{...}` Unicode 码点内置 4 组面板
  （常用/表情/手势/符号），文本默认符号补 U+FE0F（VS16）强制彩色；
  底部弹层 GridView + tab 分页，点击插入光标处（含 offset 钳制）。
- **剩余**：真机验证渲染效果（沙箱无 Flutter SDK，仅通过 `dart format` 解析校验）；
  若用户想要自定义贴纸表情资源，需另行提供资源目录并接入打包释放清单。

## 三、训练不能用——没有接入训练 API（优先级：高）——🔶 配置链路已通，端到端训练仍欠

- **现象**：能力训练页无法实际训练，未接入训练 API。
- **已完成（两部分，都如实标注来源）**：
  1. 用户自己的提交 5e076ad 已落地 `training:api` 指令族与训练页对话框；
  2. 本轮（第二批）新增**统一「API 配置」选项卡**（`config.api.*`），并让
     `trainer.api_cfg()` 在 `training.api_*` 未配时**回落到统一配置**（`source:"unified"`）——
     修掉原先「训练页配一套、别处配另一套、互不相通」的「配了等于没配」。
- **剩余**：
  1. 端到端验证：配置真实 OpenAI 兼容端点后，跑通一次完整训练任务（含蒸馏问老师）；
  2. 训练页顶部增加「未接入 API」引导提示；
  3. 训练失败时的错误回显与重试。

## 四、3D 角色无法显示和切换（优先级：高，历史遗留）——🔶 切换逻辑已修，渲染待真机验证

- **现象**：3D 角色显示与切换均不可用；长期未解决，用户要求「换个来搞」。
- **切换「不生效」的真根因（本轮找到并修掉）**：
  `SwitchModel` 只写 `model.path`，而全链路没有任何地方按 `model.path` 选形象；
  `ListModels` 排默认形象读的是 `avatar.model` ——「切换成功」只是回包假象，重启必回默认。
  现在两个键都写（`model.path` 兼容渲染器，`avatar.model` 供 bootstrap 排序）。
- **UI 补位**：dashboard 原先**没有任何形象切换入口**，本轮新增多形象芯片切换器
  （乐观更新 + 失败回滚 + toast）。
- **显示问题（4f6a228 已处理资源链路）**：`.gitignore` 整目录排除导致形象从未入库、
  查看器端口盲扫、Range/HEAD 缺失等已修；详见该轮 CHANGES。
- **剩余**：沙箱无 Flutter SDK / 无 WebGL，最终画面与切换持久化必须真机回归
  （切形象 → 重启 → 是否还是切后的那个）。

## 五、音色没落实（优先级：中）——⬜ 待排查；用户前提需纠正

- **用户怀疑**：音色模型没有拉取下来，上一版本正常。
- **事实纠正（降级要明说，绝不顺着猜）**：当前 TTS 走 **edge-tts，是云端服务**，
  本地根本不存在「音色模型」这个实体——「模型没拉下来」这个修复方向不成立。
- **真正的排查方向**：
  1. edge-tts 在线可达性（网络/代理变动是最常见的「上一版好这一版坏」原因）；
  2. edge-tts 版本升级导致 voice 列表接口失效（已知上游有过这类 breakage）；
  3. 音色选择是否在配置里真正生效（`avatar/tts voice` 读写链路）；
  4. 失败时的明确报错与重试入口，而不是静默无声。

## 六、沙箱不好用——ls 等基础命令都用不了（优先级：高）——✅ 已解决（后端）

- **真根因**：Windows 上 `subprocess.run(cmd, shell=True)` 落进 `cmd.exe`，
  它没有 `ls`/`cat`/`pwd`——不是权限、不是守卫，是 shell 选错。
- **已修（2026-10-14 第二批）**：Windows 优先路由 Git Bash（`bash.exe -c`，shell=False，
  返回体 `shell:'bash'`）；找不到 bash 时如实降级并在返回体标 `shell:'cmd'`，绝不伪装；
  POSIX 行为不变（`shell:'sh'`）；Job Object 进程上限 8→64（bash 管道要 fork 多个进程）。
- **剩余**：Windows 真机回归（装了 Git 的环境应能直接跑 `ls`/管道；没装 Git 的环境
  应看到如实的 cmd 提示而不是莫名失败）。

## 七、正常项（回归基线）

- 其他功能基本正常；模型商店正常。
- 后续每次发版以「模型商店可用 + 基础对话可用」为最低回归基线。

## 八、统一「API 配置」入口（本轮新增）——✅ 后端+UI 完成，待真机验证

- 指令族 `api:cfg | api:set [enabled|base|key|model|provider] <值> | api:test | api:chat <json>`
  （ExecuteCommand+JSON，proto 未动）；契约详见 `docs/apiContract.md`。
- 消费方：设置页选项卡、训练/蒸馏（trainer 回落）、Agent 思考（外部 API 优先）、
  语音识别（whisper 缺席时云端兜底）。
- 诚实约定：未启用时 `chat()` 回 `{ok:false, disabled:true}` 并明说「自动降级本地模型，
  不会假装在用 API」；key 永远打码回流。
- 测试：`tests/test_api_config.py` 16 例（含本地 mock OpenAI/ASR 服务的真实端到端）。

## 九、各平台通道接入是假的（优先级：高，本轮第三批）——✅ 后端已接线，待真机验证

- **原委**：`channels.py` 实现了 11 个通道类，UI 也画了一排开关，但
  `ChannelManager` 从未被真正 start；即使"start"了，RPC 用 `asyncio.run(start_all())`
  一返回就销毁事件循环，aiohttp 服务器随之而死。用户点「启动」看到成功回执，实际
  Webhook/公众号从没在监听 —— 「各平台接入一个都不是真的」的准确根因。
- **本轮已修（详见 `docs/CHANGES-2026-10-14c-fakes-to-real.md`）**：
  - 常驻事件循环线程 + `run_coroutine_threadsafe`；`start_enabled/stop_running/restart_channels`
    同步包装；`start_all` 加"已运行则跳过"守卫。
  - `_channel_config` 每次现读 `core.config.load()`，杜绝"开关点了没反应"。
  - `_reply` 正确处理 `engine.chat() -> (text, err)` 元组契约，不再回 `"('text', None)"`。
  - Webhook `_handle` 无 handler 时回落到 `_reply`，不再回 `"OK"`。
  - `_reconnect_channel` 走 `_submit` 到常驻循环，不再"永远不重连"。
  - `_SPEC` 里 dingtalk 凭据键改为 `dingtalk_access_token`（与通道实际读的一致）。
- **同一批连带修的其它"假的"**：
  - 工作流 LLM 节点同样修好 `(text, err)` 元组（此前把 `str(result)` 打进 output）。
  - `core/dsh_compat.py` 死代码 → 新 `dsh:list|available|market|parse|install|uninstall`
    RPC 指令族 + 单例；ExecuteCommand 路由元组补齐 `'dsh:'`。
  - `core/git_tool.py` 死代码 → 新 `git:status|diff|commit|branches|checkout|log`
    RPC 指令族 + 单例；ExecuteCommand 路由元组补齐 `'git:'`；默认锁定沙箱 workspace，
    所有 git 命令仍过 `exec_gate` 权限闸门。
  - `BrowserTool.search` 不再把网络故障伪装成"零结果"；异常时返回 `[{"error":...}]`，
    `browser:search` RPC op 如实上报 `ok:false + error`；`tools.web_search` 空结果
    提示改为如实描述。
  - `PluginManager` 从"每次 new 一份"改为**单一真相源**：`_get_plugin_manager()`
    优先返回 `engine.plugins`，`plugin:` 分支 / `ListPlugins` / `Enable/DisablePlugin`
    全部同源。
- **测试**：`tests/test_fakes_to_real.py` 23 例；全量 438 passed / 1 skipped。
- **仍待办**（沙箱无外网，只能等真机）：拿一份真实 Telegram/Discord/钉钉凭据，
  跑一轮收发；确认 Webhook 端口在打包版可监听、外网可达。

## 十、剩余「假的 / 未接线」（第四批后仍待办）——优先级：中，边界见 §十-末

第四批把下列**能明确证明是假**的都改成真（`docs/CHANGES-2026-10-14d-...md`）：
换人格对输出零影响、GrowthEngine 双实例、SensitiveFilter 零调用方、
插件页 8 个假按钮、设置页 3 个假外链按钮与「点了没反应也说已保存」的开关、
workflow 保存无后端同步。测试 41 例，全量 456 passed / 1 skipped。

**本批刻意没有假装修的（诚实降级，不算回归）：**

1. **子代理面板 / agent 创建器 CRUD 是纯本机数据**：后端没有 agent 的
   增/删/改/查 RPC（只有 `agent:edit|task|terminal` 三个动作族）。
   前端 UI 文案写的是「已保存」，本机持久化就是它真正语义，**没有说谎**。
   补后端 agent CRUD 属于「扩展 API 面」，需要产品决策（要不要多端同步、
   存哪儿、权限模型），不在本轮「把假的说成真」范围。
2. **~~后端类实现完整但没有调用方的组件~~（本轮已清理）**：上一轮把
   `SessionManager`、`EventBus`、`UpdateChecker`、`OfflineGuard` 一起列为「死代码」，
   这个清单**有错**——经全仓库引用核对后：
   - `EventBus`（`self.bus`）在 `_do_chat`/`_do_chat_streaming`/`_post_chat`/定时里
     持续 `emit`，并在 `report()["bus_events"]` 暴露；**在用，不能删**。
   - `UpdateChecker`(`self.updater`)、`OfflineGuard`(`self.offline`) 在 `__init__`
     实例化，并在 `health()`/`report()["network"]` 读取；`config.py` 还再导出
     `UpdateChecker` 供 `test_imports` 引用；**在用，不能删**。
   - 真正零调用方的只有：`SessionManager` 及其 `session_manager()` 惰性 getter 与
     `create_session`/`switch_session`/`list_sessions` 包装（`terminal.py` 里同名的
     `list_sessions` 是终端会话，另一回事，保留）；`XiaoLing.chat_async`；
     `XiaoLing.chat_stream_cb`（旧回调式流式，无人调，新代码用 `chat_stream` 生成器）；
     `XiaoLing.context_for_prompt`（`compressor` 本身在多处仍在用，只是这个包装没人调）。
   - **连带项**：`chat_async` 是 `RequestQueue` 的唯一生产者（`submit`/`wait`）。
     删掉它后，`RequestQueue` 的工作线程只会永久空转、`stats()` 恒为零，
     且 `self.rq` 除 `report()["queue"]`（无任何外部/Dart 消费者）与 `close()` 外
     再无引用——因此 `RequestQueue` 一并作为孤儿脚手架删除，`report()` 去掉 `queue` 键、
     `close()` 去掉 `rq.stop()`。
   本轮据实删除上述**核实为零引用**的符号（`engine.py` 净减 190 行），未动 `EventBus`/
   `UpdateChecker`/`OfflineGuard`。全量测试 456 passed / 1 skipped（与删除前基线一致）。
3. **通道端到端**（延续第九节）：沙箱无外网，`_do_reconnect` /
   Webhook 监听 / 真实凭据收发只能真机验证，本轮不敢说已经通了。
