# 更新日志

本文件记录小凌 XIAOLING 的版本变更。格式遵循「分类 + 条目」，版本号语义与  
`backend/core/config.py`（CURRENT_VERSION）、`frontend/pubspec.yaml`（version）保持一致。

## [未发布] - 2026-10-14

第二轮实测反馈（截图）：「还有好多假功能假实现」「agent 是自带功能并不是独立接口」
「左边还得加一个 api 配置的选项卡」「沙箱也是不好用，ls 等基础命令都用不了」。
详细过程见 `docs/CHANGES-2026-10-14b-unified-api-and-sandbox-shell.md`。每条同样写清
「原先假装的是什么」。

### 第五批：清理经核实的死代码（用户明确要求，先验证后动手）

上一批把 `SessionManager` / `chat_async` / `chat_stream_cb` / `context_for_prompt` /
`UpdateChecker` / `OfflineGuard` / `EventBus` 一起列入「类实现完整但没接 RPC 表面」——
这份清单**有错**。用户「把用不到的死代码直接删除」这条要求触发了逐项核查（删除不可
回退，先核对再动）：

1. **三个不是死代码，坚决留下**：
   - `EventBus`（`self.bus`）在 `_do_chat` / `_do_chat_streaming` / `_post_chat` /
     `_on_cron_fire` 里持续 `emit`（chat:before/after/post、cron:fire），并通过
     `report()["bus_events"]` 对外暴露。
   - `UpdateChecker`（`self.updater`）、`OfflineGuard`（`self.offline`）在
     `XiaoLing.__init__` 里实例化，在 `health()` 的 checks 与 `report()["network"]`
     里读取；`UpdateChecker` 还被 `core/config.py` 再导出，`test_imports` 有覆盖。
2. **五个真的零引用，删除**（全仓 grep 无调用方，无 getattr 字符串派发，无测试引用）：
   - `class SessionManager`（engine.py）+ 惰性 getter `session_manager()` + 包装方法
     `create_session` / `switch_session` / `list_sessions`。`terminal.py` 里的同名
     `list_sessions` 是终端会话，与 SessionManager 完全无关，保留不动。
   - `XiaoLing.chat_async`：全仓无调用方，走的是下面这套 `RequestQueue`。
   - `XiaoLing.chat_stream_cb`：旧回调式流式，前端与 webpanel/server 都改用
     `chat_stream` 生成器，无人调用这个包装。
   - `XiaoLing.context_for_prompt`：只是 `compressor.compress(conversation)` 的一层
     包装，`compressor` 本身在多处仍在直接使用（`_route_clear`、`dump_state`、
     `memory.py`），删除该包装方法不动 `ContextCompressor` 类。
3. **连带删除 `RequestQueue`（关键判断）**：`chat_async` 是 `self.rq.submit/wait` 的
   **唯一生产者**。删了 `chat_async` 之后，`RequestQueue.__init__` 里 spawn 的 worker
   线程会永久空转、`stats()` 恒返回零，`report()["queue"]` 变成假数字。且 `self.rq`
   在 engine.py 之外零引用、`report()["queue"]` 无 Dart 消费者（`out['queue']` 那一行
   在 server.py 是成长蒸馏 stats，另一个 dict）。所以 `RequestQueue` 一并作为孤儿
   脚手架删除；`report()` 去掉 `"queue"` 键；`close()` 去掉 `self.rq.stop()`。
4. **改动范围**：仅 `backend/core/engine.py` 一个文件，净减 190 行；未新增或删除
   import（`random` 与 `queue` 仍在其他函数用；`time`/`threading`/`deque` 也都在用）。
5. **验证**：
   - `py_compile` 通过；
   - 运行时 `hasattr(eng, 'chat_async' / 'chat_stream_cb' / 'context_for_prompt' /
     'session_manager' / 'create_session' / 'switch_session' / 'list_sessions')` 全部
     False；`hasattr(eng, 'rq')` False；模块层 `RequestQueue` / `SessionManager`
     不再存在；
   - 全量测试 `python3 -m pytest tests -q --override-ini="addopts="` →
     **456 passed, 1 skipped**（与删除前基线一致，无回归）。
6. **诚实边界**：`report()` 的 `"queue"` 键已移除。前端如有读取该键的代码，会读到
   `null`/缺字段——按 grep 全仓无 Dart 引用，本轮无破坏面。将来若真接入请求队列功能，
   需要重新引入实现而不是恢复这份脚手架。

### 第四批：换人格不生效 / 敏感词过滤器零调用 / 插件与设置页假按钮（提交前审计驱动）

用户反馈「还有什么是假的？全部修复」。第三批之后继续审计，把「类实现齐全、
就是没接到调用方」和「前端按钮只 Navigator.pop、后端连字段都没有」两类残余
假实现修成真。过程见 `docs/CHANGES-2026-10-14d-batch3-persona-growth-sensitive-plugin.md`。

1. **人格选择对模型输出零影响**：`engine.system_prompt()` 组装的 persona hint +
   suffix 从来没进模型——`ModelReplacement` 把静态 `DEFAULT_SYSTEM_PROMPT` 写死传进
   `LocalModel`。新增 `system_prompt_provider` 回调，engine→ModelReplacement→
   LocalModel 一路透传，`build_messages` 每轮现取；provider 异常退回静态串，不吞对话。
2. **GrowthEngine 双实例**：`GetStatus/GetGrowthStatus/GetTrainingStatus` 每次
   `GrowthEngine().status()` 读到「刚出厂」状态，与 `growth:` 指令族不同源。
   `_get_growth_engine()` 进程级单例（优先 `eng.growth`），三个 RPC 一律走它。
3. **SensitiveFilter 零调用方**：`_SENSITIVE_FILTER` 实例化了但对话链路没人调用，
   内置敏感词命中原样入库/回前端/进记忆与成长样本。新增 `_compliance_mask(reply)`
   接到 `_do_chat` 与 `_do_chat_streaming` 的 `_post_chat` 之前；新增 `sensitive:`
   指令族（list/check/add）接入 ExecuteCommand 路由。流式已推前端的字无法收回，
   诚实写进 docstring。
4. **插件页 8 个假按钮 + 1 个假输入框**：install/config/info/doc 四个对话框里所有
   `_dialogRow(..., () => Navigator.pop(context))` 换成真动作；后端补 `plugin:reload`
   （单件热重载 / 无参整体重载）、`plugin:installpath`（.zip/目录，路径不存在如实报错）、
   `plugin:dir`（返回真实目录，前端复制到剪贴板）。假的「自定义参数」输入框
   （值从不发后端、后端也无处落库）改成如实说明文字。
5. **设置页三个「关于」假按钮**：`_openExternal` 用 `Process.run` 开系统浏览器，
   失败退回复制剪贴板 + 明确告知；不新增 `url_launcher` 依赖。仓库地址假串
   `github.com/xiaoling/xl` 改成真实 Gitee `COSMOnb666/XLmodel`，并让「项目地址」行可点。
6. **设置页开关「点了没反应也说已保存」**：区分本机偏好（animations/sound/splash/
   autoUpdate/crash/telemetry/effects_enabled，后端 proto 无对应字段，`_persistChannels()`
   才是真来源，不再推后端）与后端字段（alwaysOnTop/autoStart/asr/tts/readAloud，push 后
   **回读** `settings()` 验证，任一环节失败如实报「后端未确认（可能离线）」）。
   上一批误加到 `options.py` 的 `ui.*` 白名单 + bool 强制转换**已回滚**——给不存在的
   字段造假通路本身就是假。
7. **workflow_builder 保存**：本机 `_persistSaved()` 即时成功 + `unawaited(_pushSaveToBackend)`
   异步走 `workflow:save`，如实弹「已同步」或「后端未确认（仅本机保存）」。

- 测试：`tests/test_fakes_to_real.py` 23 → **41 例**（R9~R13：provider、growth 单例、
  sensitive 指令族 + 对话链路必须调 `_compliance_mask`、plugin 三条新指令成功/失败、
  源码级护栏防「裸 GrowthEngine()」复发）。全量 `pytest tests -q` →
  **456 passed, 1 skipped**（415 基线 + 第三批 23 + 本批 18）。前端 4 个改动文件
  `dart format --output=none` 通过。
- 文档：`docs/CHANGES-2026-10-14d-...md` 本批说明；`KNOWN-ISSUES.md` 新增第十节；
  `apiContract.md` 补 `sensitive:` 与 `plugin:reload|installpath|dir`。
- **明确保留的已知假（不假装修好）**：子代理面板 / agent 创建器 CRUD 是纯本机数据，
  后端无对应 agent CRUD RPC（只有 `agent:edit|task|terminal` 动作族），UI 文案也没声称
  同步后端——按诚实降级保留。当时把 `SessionManager` / `chat_async` / `chat_stream_cb` /
  `context_for_prompt` / `UpdateChecker` / `OfflineGuard` / `EventBus` 一并列为
  「类实现完整但未接 RPC 表面」——这个归类有错，`UpdateChecker` / `OfflineGuard` /
  `EventBus` 实际都在 `health()` / `report()` / `emit` 里被用。第五批据实修正并删除
  真正零引用的部分（详见上面「第五批」）。

### 第三批：把「各平台接入都是假的」等一整类假实现改成真的（提交前审计驱动）

用户反馈「还有好多功能都是假的用不了，各平台接入一个都不是真的」。子代理全仓交叉审计
确认 9 条、5 条高危。本轮逐条接线，过程见 `docs/CHANGES-2026-10-14c-fakes-to-real.md`：

1. **多通道假死**：`ChannelManager` 生命周期改跑常驻事件循环线程（此前 RPC 用
   `asyncio.run(start_all())`，返回即销毁循环，aiohttp 服务器从没真正监听）；
   `_channel_config` 现读磁盘配置（此前读构造快照，「开关点了没反应」）；
   `_reply` 正确处理 `engine.chat()` 的 `(text,err)` 元组；Webhook 无 handler 时回落引擎；
   `_reconnect_channel` 走常驻循环（此前协程丢给线程从不 await，永远不重连）；
   dingtalk 凭据键名改对。
2. **工作流 LLM 节点**：同样修好 `(text,err)` 元组，不再把 `"('text', None)"` 写进 output。
3. **DSHCompat 死代码** → 新 `dsh:` 指令族 + 单例，接入 ExecuteCommand 路由。
4. **GitTool 死代码** → 新 `git:` 指令族 + 单例（默认锁沙箱 workspace，全过 exec_gate），接入路由。
5. **BrowserTool.search 伪装零结果** → 网络故障返回 `[{"error":...}]`，`browser:search` RPC 如实上报。
6. **PluginManager 多实例** → `_get_plugin_manager()` 单一真相源（优先 `engine.plugins`）。

- 测试：新增 `tests/test_fakes_to_real.py` 23 例；全量 `pytest tests -q` →
  **438 passed, 1 skipped**（上轮基线 415 + 本轮 23）。
- 文档：`KNOWN-ISSUES.md` 新增第九节；`apiContract.md` 补 `channels:`/`dsh:`/`git:`/`browser:search`。
- **仍待真机验证（不说成已完成）**：通道端到端收发需真实凭据 + 外网，沙箱无法验证。

### 沙箱「ls 都用不了」——根因是 shell 选错，不是权限

- Windows 上 `subprocess.run(cmd, shell=True)` 落进 `cmd.exe`，它没有 `ls`/`cat`/`pwd`。
  此前多轮修复都没碰到这一层。
- `_posix_run_args(cmd, plat)` 统一路由：Windows 找到 Git Bash → `bash.exe -c` +
  shell=False，返回体标 `shell:'bash'`（探测进程内缓存，只跑一次）；找不到 bash →
  如实降级并标 `shell:'cmd'`，**不伪装**；POSIX 不变（`shell:'sh'`）。
  `exec_gate` 透传 `shell` 字段；Job Object `ActiveProcessLimit` 8→64
  （bash 管道 `a|b|c` 要 fork bash 本体 + 每个管道成员）。
- 测试 +5 例（`tests/test_sandbox_degraded_guard.py`）。

### 统一「API 配置」入口（设置页新选项卡）——修掉「配了等于没配」

- 原先外部 API 配置散成互不相通的两套（`training.api_*` 与 `deepseek_*`）。
  收敛为 `config.api.{enabled,base,key,model,provider}`，新模块 `core/api_config.py`
  （纯标准库 urllib）：`cfg()` 打码快照 / `set_field()` 校验写入 / `chat()` 真连
  `/chat/completions` / `test()` 真实连通性 / `transcribe()` 手拼 multipart 调
  `/audio/transcriptions`。gRPC：`api:cfg|set|test|chat`（ExecuteCommand+JSON，proto 未动）。
- 四个消费方：设置页「API 配置」选项卡（开关+供应商+端点+密钥打码+模型名+测试连接）、
  `trainer.api_cfg()` 在 `training.api_*` 未配时回落统一配置（`source:"unified"`）、
  `agent._llm_think` 外部 API 优先（失败记日志回退本地，不静默冒充）、
  `ASR.available()` whisper 缺席 + API 已配时走云端识别。
- 诚实约定：未启用时 `chat()` 回 `{ok:false, disabled:true}` 并明说「自动降级本地模型，
  不会假装在用 API」；明文 key 永不回流前端；空识别结果如实报错。
- 如实说明的边界：**whisper 未装不再挡识别**（可走 API），但**后端麦克风录音仍需
  `pip install pyaudio`** —— 这是环境缺依赖，本轮没有绕过。

### 3D 形象「切换不生效」——老问题的逻辑层真根因

- `SwitchModel` 原先只写 `model.path`，而全链路**没有任何地方**按它选形象；
  `ListModels` 排默认形象读的是 `avatar.model` ——「切换成功」只是回包假象，
  重启必回默认形象。现在两个键都写（`model.path` 兼容渲染器，`avatar.model` 供 bootstrap）。
- dashboard 原先**没有任何形象切换入口**：新增 `_avatarSwitcher` 芯片切换器
  （乐观更新 + 失败回滚 + toast）。沙箱无 Flutter SDK/WebGL，最终画面与持久化仍需真机回归。

### Agent 内置化（「agent 是自带功能并不是独立接口」）

- 聊天输入条新增 `_agentToggle`：开启后消息走 `_sendAgent` → `pb.AgentRequest` 流式订阅，
  按 🧭计划 / 🔧工具 / ↳结果 / ⚠️错误 逐行渲染；`Completer` 存入 `_agentCompleter`，
  停止按钮取消订阅并 resolve await（修掉「中断后卡死在生成中」的隐患），dispose 兜底。
- 独立 agent_page 保留为高级视图，不再是唯一入口。

### 表情包：假按钮换成真面板（零依赖）

- 原先表情按钮点击无任何实现。现为 Dart `\u{...}` 码点内置 4 组（常用/表情/手势/符号）
  底部弹层面板，文本默认符号补 U+FE0F 强制彩色，点击插入光标处（含 offset 钳制）。
- 踩坑如实记录：Dart **不支持相邻字符串字面量拼接**；heredoc 写入会吞变体选择符，
  最终用 Python 程序化生成。

### 音色（纠正用户前提）

- 用户怀疑「音色模型没拉下来」。**事实**：当前 TTS 走 edge-tts，是**云端**服务，
  本地不存在「音色模型」实体，「拉取模型」这个修复方向不成立。真方向：网络/代理可达性、
  edge-tts 版本、voice 配置读写链路。已写入 `docs/KNOWN-ISSUES.md` 第五节。

### 训练 API（如实标注归属）

- `training:api` 指令族与训练页对话框是**用户自己的提交 5e076ad** 先落地的；
  本轮的贡献是统一入口 + `trainer.api_cfg()` 回落，让设置页配一次训练/蒸馏就能用。

### 验证

- 全量回归：`python3 -m pytest tests -q --override-ini="addopts="` →
  **394 passed, 1 skipped**（上轮基线 373 + 本轮 21：api_config 16 例 + 沙箱 5 例）。
  api_config 测试含真端到端：本地起 mock OpenAI / mock `/audio/transcriptions` 服务，
  断言真实 HTTP 交互与 multipart 字节；whisper 缺失用 `builtins.__import__` 猴补丁模拟。
- 文档同步：`KNOWN-ISSUES.md` 全量更新状态；`apiContract.md` 新增 `api:` 族与
  SwitchModel/`shell` 字段真实行为；`apiContract.csv` 16 新行（顺带修掉 5 行历史遗留的
  未加引号逗号）；`openapi.yaml` 新增 3 路径 + 2 schema（yaml 解析通过）；
  `features.json` 新增 4 条（均如实标 partial/done）。
- **待真机验证（明确不说成已完成）**：沙箱无 Flutter SDK，四个页面的 Dart 改动只过了
  `dart format` 解析校验 —— API 选项卡、形象切换器、Agent 模式、表情面板都未在真机上点过。

## [未发布] - 2026-10-13

本轮针对「有好多东西都是假的」这一反馈，逐条查实并修掉五处：3D 形象、后端连接、
沙箱、硬件推荐、模型商店。下面每条都写清「原先假装的是什么」。

### 3D 形象（「加载不到人物 3D 模型」）

- **根因不在渲染代码，在 `.gitignore`**：原先写的是 `resources/models/`（排除整个目录）。
  Git 对被忽略的**目录**不会进入，因此下面的 `!` 例外规则永远不生效 ——
  形象资源从来没有进过版本库，`viewer.html` 每次都是 404。
  改为 `resources/models/*` 并把 `!resources/models/小凌.vrm` / `!resources/models/README.md`
  放到所有模型忽略规则**之后**（最后匹配的规则生效），只放行这两个文件，
  用户自己丢进来的其它模型仍然一律不入库。
- **必须说明：用户提到的「历史里那几个人物 3D 模型」并不存在**。翻遍 Gitee 与 GitHub
  两个远端的全部提交历史（`git rev-list --all` + 逐提交 `ls-tree` + 对象类型遍历），
  没有任何一个 `.vrm` / `.glb` / `.fbx` 曾被提交或删除过 —— 是「没有」，不是「没找」。
  因此改为用仓库自有管线真实生成形象并入库：
  `scripts/xiaoling_avatar.py build --base <vrm> --face resources/materials/xiaoling.png`
  （纯 numpy + Pillow 的 glTF 编辑器 `scripts/vrm_lib.py`，离屏光栅校验 `scripts/vrm_preview.py`）。
  基底来自 ModelScope `oleehu/vrm-models`，授权与再生命令写在 `resources/models/README.md`。
  产物 `resources/models/小凌.vrm`（18,468,076 字节）实测：glTF 2.0 二进制、声明长度与实际
  字节数一致、179 节点 / 54 人形骨骼 / 11 网格 / 18 表情、场景图与 accessor 零越界。
- **真实浏览器里跑通**：用 chromium 执行与 `viewer.html` 相同的 import map 与同一份
  vendored 模块，加载同一份 .vrm → `parsed, hasVRM=true`，`height=1.519`，
  `meshes=11 tris=40789`，28 张贴图全部解码成功（`missing=NONE`），
  `expressionManager.getExpression('blink'/'aa'/'happy')` 均命中，
  `em.setValue('blink',1)` / `('aa',0.5)` 不抛错，`removeUnnecessaryJoints` 正常。
  说明：本沙箱无任何可用的 WebGL（所有 GL 后端均 `EGL_NOT_INITIALIZED`），
  因此**无法比对最终画面**，这一点如实记录；已用离线光栅渲染 + 浏览器解析两条路交叉验证。
- **补齐静态服务缺的两块（这是第二处"假"）**：`core/webpanel.py` 的 `_serve_file()`
  原先**完全无视 `Range` 头**、一律回 200 全量；类里也**没有 `do_HEAD`** → 501。
  现在支持 `bytes=a-b` / `bytes=a-` / `bytes=-n`，回 `206` + 精确 `Content-Range`，
  分段拼接与整文件字节级一致（续传正确性前提）；越界回 `416` + `bytes */<size>`；
  多段范围**不伪装成 206**，按 RFC 7233 允许的降级如实回整文件；`HEAD` 复用 GET 路由、
  只回头不回头体。路径穿越仍然 404。
- 新增回归测试 `tests/test_webpanel_static.py`（31 例，全绿）：Range 解析纯函数表驱动、
  真起 HTTP 服务取真文件逐段字节比对、HEAD 行为、越界与降级路径，
  以及「内置形象必须真的在仓库里且 glTF 声明长度 == 实际长度」这条静态守门。

### 后端连接

- `rpc/server.py::serve()` 不再在绑定成功前播「已启动」。实测 grpc 1.84 端口被占时
  `add_insecure_port()` 是**抛 `RuntimeError`**（不是返回 0）；现在捕获后记录 `grpc:0` + 错误、
  打印换端口/清理旧进程的具体处置、并**重新抛出**；成功则记录**真实**绑定端口。
- `main.py` 用 `threading.Event` 等真实绑定结果（最多 20 秒）再播报，失败就打印失败，
  不再出现「线程还没跑完就说后端已启动」。
- 新增 `system:ports`：返回 `{ok, grpc, web, web_host, web_error?}`，
  值来自 `webpanel.web_state()`（`_record_state()` 同时落 `data/web_port.json`，
  全端口被占的失败路径也记 `port=0` + 原因）。
- 前端 `services/viewer_port.dart` 改为**先问后端要真值**，不再盲扫 8765~8785：
  顺延出窗口就永远找不到，更糟的是同号端口可能属于别的软件，WebView 里会渲染出
  莫名其妙的页面。问不到就如实判定「没在跑」，盲扫只作最后兜底。

### 沙箱

- **诚实前提**：本机内核 5.10 → 没有 Landlock，所以「降级路径」在这里就是**默认路径**，
  不是边缘情况。原先降级只 `rlimit + chdir`，实测 `cat ../../../../etc/passwd` 直接读到内容。
- 新增 `core/sandbox.py::lexical_escape_check(command, work, permission_level)`，
  仅在**无 OS 级路径隔离**且非 `PERM_FULL` 时启用，已真正接进 `run_sandboxed()`
  （命中即不起子进程，返回 `guard:'lexical'` + `offending` + `note`）。
  `_guard_roots()` 刻意**镜像 Landlock 的放行面**：系统目录（`/usr /lib /bin /etc …`）只读、
  workspace/tmp/数据目录可写。因此 `cat /etc/passwd`、读 `/proc/meminfo` 是**允许通过**的 ——
  降级模式不该比真隔离更严（有一条测试专门钉住这点，否则 sysinfo 会被自己挡死）。
  挡住的是相对逃逸 `../../`、`~/.ssh/id_rsa`、他人 home、Windows `..\..\`。
- 文档与返回值都不给它好名字：`capability()` 里 `path_isolation` 仍然 `False`，
  只新增 `lexical_guard: true`；docstring 与 `note` 写明**它不是安全边界**，
  只挡误操作，挡不住编码/拼接/解释器内联脚本绕过。真机要 OS 级路径强制请上 ≥5.13 内核。
- `exec_gate._execute_desktop` 修掉丢原因的判断：原先只在 `'stdout' not in res` 时才填
  `blocked_reason`，导致「命令有部分输出但被拒」时原因被吞。现在只要 `ok` 为假就带上原因，
  并透传 `guard` / `note` / `offending`。
- 新增 `tests/test_sandbox_degraded_guard.py`（16 例，全绿），含
  「真实 Landlock 可用时绝不调用词法守卫」（spy 计数）与 capability 两条路径的诚实性。

### 硬件识别 → 模型推荐

- gRPC `ListRecommendedModels` 原先**绕过了仓库里已有的真计算**
  `fit_models_for_hardware()`，自己用 `size_mb/1024*1.5` 判能不能跑；
  `params` 用 `size_mb` 反算（0.5B 模型显示成 "469B"）、`context` 硬编码 "32K"、
  `quant` 从来没赋值。现在改为 `detect_hardware()` + `fit_models_for_hardware()`，
  如实填 params/quant/vram_gb/ram_gb/context；探测失败返回 `UNAVAILABLE` 而不是编一份。
- 新增 `model:recommend` → `recommend_for_hardware()`：返回 `tier` / `available` / `why` /
  `detected{}` / `models[]`。**RAM 探不到时 `available:false`、`why` 写明原因，
  并把所有 `recommended` 强制置 false** —— 没有依据就不推荐。
  实测本机：`available=true`、`tier=entry`、`why=RAM 8.0GB，设备档位 entry`、11 个模型中 1 个 recommended。

### 模型商店（「并没有跟魔塔社区官网一样可以搜索并下载，也并没有推荐」）

- 确认原先是假的：`list_available()` 直接返回内置 11 条 `MODEL_PRESETS`，
  前端搜索框只做 Dart 侧本地字符串过滤，**不发任何请求**（`grep openapi/v1 backend/` 零命中）。
- 后端真连魔搭（全部标准库 urllib，无新依赖）：
  `search_remote()` → `/openapi/v1/models?search=`（分页参数 `page_number`/`page_size` 实测有效，
  total 在 `data.total_count`）；`remote_model_files()` → 旧接口 `/api/v1/.../repo/files`
  （大小写敏感 `Data.Files`）；`download_remote()` 复用与内置下载**同一套**断点续传实现
  （把 `_download_gguf_http` 抽出 `_download_gguf_repo`，不复制第二份下载代码）；
  RPC 侧 `model:search` / `files` / `recommend` / `downloadremote`，
  其中 `downloadremote` 走 `_bg_start` 后台任务、进度写 `core.model.TASKS`、尊重 `cancel_event`。
  四条新指令放在 `_get_engine()` **之前**，搜索/推荐不会被迫先加载引擎。
- 修掉一个真实的续传 bug：ModelScope 续传回 **200 + 正确 `Content-Range`**（不是 206），
  旧判定 `if have and r.status != 206: have, mode = 0, "wb"` 会把已下字节作废、从头再下。
  现在 status==206，或 status==200 且 `Content-Range` 起始偏移 == 已有字节数，都算续传成功；
  服务端真的不支持 Range 时仍从 0 开始，不写坏文件。
- 诚实约定：搜索/列文件失败一律 `ok:false + error`，**不返回空列表冒充「没找到」**；
  空关键词直接拒绝，不回全量清单；`private`/`gated` 条目保留但标注；
  无 `.gguf` 的仓库直说「不是量化仓库，无法直接下载」而不是硬下。
  接口给的 `params` 是参数量整数（494032768），统一换算成 `0.5B` / `7.6B` 可读写法。
- 新增前端面板 `frontend/lib/widgets/model_remote_panel.dart`，并接进模型商店页
  （「魔搭社区：搜索 · 按硬件推荐 · 下载」一节，默认展开）：输入防抖 550ms、分页、
  展开时列真实 `.gguf` 量化档、下载后 2 秒轮询 `sandbox:status` 取真实进度、
  取消走 `agent:task cancel`。后端返回 `ok:false` 时如实显示错误 + 重试入口。
  原有内置清单上方那个搜索框改标注为「本地筛选」，避免再让人误以为它是远端搜索。
- 新增 `tests/test_model_search.py`（13 例，离线不联网）覆盖解析、空关键词不发请求、
  三种失败路径、脏数据过滤、仓库名注入/穿越拒绝、续传判定、探测失败不给假推荐。
- 真实接口实测：`model:search qwen2.5 gguf` → `ok=true, total=5200, 20 条`；
  `model:files oleehu/vrm-models` → `ok=true, 42 个文件, gguf=0`（该库确实没有 gguf）；
  `model:search`（空）与 `model:downloadremote ..` 均正确拒绝。

### 文档与验证

- `docs/apiContract.md` / `.csv` 补 `model:` 与 `system:` 两族、形象文件真实来源、
  静态服务 Range/HEAD 契约，以及三条新降级约定（gRPC 绑定失败、查看器端口全占、
  降级沙箱不是安全边界）。`docs/openapi.yaml` 新增 6 个路径与 3 个 schema（YAML 解析通过）。
  `docs/featureMapping.md` / `analysisReport.md` / `features.json` / `ARCHITECTURE.md` /
  `README.md` 同步，并把「历史里的 VRM 从未存在」写进已知边界。
- 全量回归：`python3 -m pytest tests -q --override-ini="addopts="` →
  **373 passed, 1 skipped**。
- **待真机验证（明确不说成已完成）**：本沙箱没有 Flutter SDK，新增与改动的 Dart 只过了
  `dart format --output=none` 解析校验（能解析、未改仓库既有格式），没跑 `flutter analyze`，
  也没在手机上点过 —— 魔搭面板的搜索/分页/下载/取消交互、以及 `system:ports` 问端口这条链路，
  都仍需真机复核。3D 方面沙箱无可用 WebGL，最终画面没法比对。

## [未发布] - 2026-10-12

### 模型识别

- 新增 `core.model.active_model()`：**当前活动模型的唯一真源**。以磁盘事实为准，
  按「已加载 → 严格匹配选中名 → 硬件跑得动的最优已安装模型 → 本地登记 → 空」
  五级优先级解析。此前 `selected_name` / `GetStatus.live_model` /
  `cfg['model']['base_model']` 三处各算各的，同一时刻能给出三个不同模型名。
- 聊天正确回答「你是什么模型」：新增 `is_model_identity_question()` 意图识别，
  命中即由路由用**磁盘事实**作答，不再交给模型自己猜（避免复读历史里的旧模型名
  或编造不存在的模型）。刻意做窄匹配 —— 含「帮我/写/总结/解释/下载」等干活动词的
  句子一律放行给模型，不误伤。
- 没有模型时明确显示「未安装模型」并给出模型商店引导；
  `_route_no_model()` 专门应答「模型在哪 / 怎么下载」。
- 默认模型选择改为按硬件适配度 + 模型评分 + 体积排序：原先 `find_installed(None)`
  返回目录名字母序第一个，5GB 的 Qwen3.5-9B 会输给 800MB 的 Llama-1B。
- 新增 `params_from_name()`：预设表之外的模型（如 Qwen3.5-9B-DeepSeek-V4-Flash）
  从名字解析参数量，不再被当成「无名小模型」排到最后。
- 状态栏 / `GetStatus` / 聊天页头部三处显示的模型现在口径完全一致。

### 性能

- 扫描缓存：`scan_model_dir()` 按 (路径, mtime, 大小) 缓存，模型下载完成自动失效。
  `list_installed` / `is_installed` / `find_installed` 不再每次 rglob 整个模型库。
- `detect_hardware()` 缓存 60 秒（单次约 70ms，源于 nvidia-smi / wmic 子进程）。
- `chat_stream()` 重写为**真流式**：原实现先整句生成、再逐字 `sleep 0.01~0.03s`
  吐字，一条 84 字回复白等约 1.8 秒。现在底层 token 直接推送、按 3 字聚合发帧
  （gRPC 帧数从 N 降到 N/3），首字延迟显著下降。
- 新增 `model:active` 指令（沿用项目「不改 proto」的 ExecuteCommand + JSON 惯例），
  前端 2 秒 TTL 内存缓存 + 并发请求合并，重复查询几乎零往返。
- 修正一处**副作用 bug**：流式改造初版会在 `chat_stream` 与 `_do_chat_streaming`
  里各调一次 `_route()`，而 `_route` 的部分分支有真实副作用（加提醒 / 清记忆 /
  跑训练），老板说一句「提醒我喝水」会被加两次。改为只求值一次。

### 前端

- 聊天页头部实时显示当前模型：模型名 + 参数量 + 量化 + 体积 + 已加载/待加载；
  无模型时红色提示并**可点击直达模型商店**；后端未响应时显示「正在识别模型…」
  （不谎报、不瞎猜）。点击模型行可强制重新向后端核对。
- 新增 `services/model_state.dart`：`XlModelState` 结构化状态 + 广播流，
  切模型 / 下载完成自动刷新 UI，各页面无需各自轮询 `GetStatus`。
- 动效改为**三档**（关闭 / 精简 / 完整），默认「精简」：关闭呼吸、光晕、扫光等
  **非必要**装饰动效，保留按压与状态过渡等必要反馈 —— 一刀切会让界面显得死板。
- 动画控制器按档位在**源头**启停（`XlEffects.bindAmbient`）：原先只在 build 里把
  动画值读成 0，界面静止但帧照刷；全应用 22 处 `repeat()` 对集显机器是实打实负担。
- 模型下载完成后立即失效模型状态缓存，不必等 TTL。

### 去伪存真：训练页

- **删掉三处假实现**：写死的「演练模式」徽章（`_isSimulated` / `_simBadge`，靠匹
  配 `[演练]` 前缀点亮，而 trainer 早就没有演练分支，所以永远不亮）、只改本地布尔
  量的假停止按钮、以及 `steps * 0.6` 编造的预计耗时。全部改读后端 `training:` JSON
  真值，取不到就显示「未获取」而不是猜一个。
- 停止按钮真的调 `training:cancel`，成功与失败都如实播报（包括「当前没有正在运行的
  训练任务」）；`_jsonRaw` 保证失败原因不被 `ok == true` 过滤掉。
- 训练元数据走 `training:status` / `env` / `adapter` / `history` 四条 JSON 通道：
  依赖版本、设备、可训练基座与不可用原因、适配器体积、target_modules、rank·alpha、
  可否续训，全部是磁盘与运行时事实。
- 历史条目不再用「loss 曲线是平的就判定为演练」这种猜测；改为读 `ok` / `real` /
  `cancel_reason`，区分「失败」「未产出权重」「中断」「真权重」。
- `trainer.py` 落 `elapsed_sec` / `sec_per_step` 实测值，前端「每次训练耗时」与预计
  剩余由测量驱动；首次训练没有历史时明说「首次训练：暂无实测耗时」。
- proto 没动（项目惯例）：`TrainingProgress` 只有 step/total/loss/status，事件 kind
  由 Dart 侧从 `[准备]/[环境]/[验证]/[完成]` 前缀还原，验证 loss 用正则从
  `验证 loss=X` 文本取 —— 还原不出来的返回 null，不编造。

### 去伪存真：后端静默假成功

- **修复提醒「已完成」不落盘**：`CompleteReminder` 原先直接 `r['done'] = True` 再
  调 `persona.flush()`，而 `flush()` 是 `if self._dirty: self._save()` —— 改 done 不
  会置 `_dirty`，于是磁盘从未更新、接口却报成功，重启后提醒原样复活。新增
  `ProactiveEngine.mark_done()` 走 `_notify()` 正常落盘路径，并有回归测试直接断言
  磁盘内容。
- **修复 `ResetPersona` 谎报成功**：引擎为 None（人格引擎启动失败）时也返回
  `ok=True「人格画像已重置」`。现在区分「引擎未就绪」与「人格引擎不可用」，不做
  任何改动就返回失败。
- **修复取消状态被吞**：`training:status` 读 `live_trainers()` 失败时原先静默
  `pass`，`cancel_requested` 留在 False，界面显示「训练中」而把用户已点的停止吞掉。
  现在返回 `cancel_state_error` 并打 warning，前端显示「取消状态未确认」。
- **修复终端超时被报成正常结束**：`run_command_stream` 的 `timed_out` 硬编码
  False；现在从 exec_gate 的实际结果判定。
- 继续审计 server.py 的 25 处静默吞异常：其余经核实均为**有意降级**（写指标失败不
  能让 RPC 崩、段位取不到就显示默认段位、配置写盘异常已在 `config.save` 处向外
  抛出），不改语义以免引入回归。

### 前端组件修复

- **修好七个从未编译过的 XL 组件**：`xl_button` import 了不存在的
  `tokens.dart` / `glass.dart` / `motion.dart`，`xl_dialog` / `xl_list_item` /
  `xl_segmented_control` / `xl_text_field` / `xl_toast` 写成 `'theme/theme.dart'`
  （少一层 `../`）。光改路径还不够 —— 这些组件用到的 `XlGlassMaterial` 定义在
  `tokens.dart`、`XlPalette` / `XlRadius` 在 `theme.dart`，而两模块互不 re-export，
  已按实际用到的符号补齐 import。
- `xl_loss_chart.dart` 修掉一批会真崩的问题：≤1 点时除以 `n-1` 得 NaN、
  yMin==yMax 时坐标 NaN、`context.size!` 强解包崩溃、`progress` 参数收了却没用
  （动画根本不可见）、验证曲线因 `whereType` 丢 x 轴对齐被压扁、tooltip 飞出画布。
  稀疏验证点改为按 index 定位 + 虚线连接。
- 训练页接入 `XlLossChart`，并用**稳定列表引用**喂数据：以前每次 build 现场
  `List.unmodifiable(_lossPoints)` 造新对象，widget 会误判「数据变了」而重启入场
  动画。

### 排版：对齐 Apple HIG

- **补上从没生效过的字体声明**：`typography.dart` 早就把 primary 写成 `Inter`，
  但 `pubspec.yaml` 没有 `fonts:` 段，四端全部静默回落到系统字体（Linux 上是
  DejaVu Sans）—— 「字距怪、不够利落」的主因在这里，不在样式写法。现按 OFL 打包
  Inter 子集（不含 CJK，中文走系统回落），10 个文件约 1.2MB。
- **动态光学尺寸**：HIG 里 SF Pro 随字号在 Text/Display 间自动插值。可变字体在
  Skia 各后端插值行为不一致，所以把 opsz=14 / opsz=32 各自实例化为 400–800 五档
  静态字重，由 `XlFontFamily.forSize()` 按字号显式选族（阈值 22pt 取保守余量；
  沙箱无 Flutter SDK 无法渲染比对，这一阈值需要真机复核）。
- **修正大标题字距符号反了**：Apple 的 tracking 表在 24pt 以上是**正**值且越大越
  松，而三个 display 槽位原先吃 `tighter`(-1.2) / `tight`(-0.8)，48pt 大标题挤在
  一起。新增 `XlFontFamily.trackingFor(size)` 抄 HIG 表按字号取最近邻值，
  `XlTextStyles.build` 未显式给字距时自动套用；页面里现场硬写的大字号样式用
  `TextStyle.optical` 纠正。
- 三处 9pt 文本提到 10pt（HIG 最小可读字号：iOS 11 / macOS 10）。
- `XlFontFamily.mono` 原写 `'JetBrains Mono'` —— 仓库里没有这字体、四端也不保证
  安装，是个从没生效的假声明（全仓库 24 处实际用 `'monospace'`）。改为同值。

### 配色：对齐 Apple HIG《Color》并做成三档

- **先算再改**：新增 `tools/contrast_audit.py`，直接解析 theme.dart 里的 XlPalette
  常量块，按 WCAG 2.1 相对亮度逐色对着**最差的那个面**（浅色是 surfaceLo，深色是
  surfaceHi）算比值。肉眼看 3.0 和 4.5 没区别，只有算得出来。
- **旧配色的真实成绩**（浅色模式，最差面）：orange 2.13、cyan 2.40、green 2.54、
  gold 2.74、decor 2.81、pink 2.87、red 2.97、blue 3.01、violet 3.46、text4 2.48、
  text3 3.43 —— 除了 text1/text2 全部不达 AA；深色模式只有 text4 3.90 与 decor 4.33
  两项偏低。原因很典型：浅色强调色是「把品牌色调深一点点」，没验过。
- **改后**（浅色）：orange 4.62、pink 4.63、red/blue/cyan/violet 4.61、
  green/gold/decor/text4 4.60、text3 4.97、text2 7.13；深色 text4/decor 4.61。
  每个色值由 HIG 系统色同一色相二分逼近阈值，不肉眼调。四个变体 `--strict` 全绿。
- **补上 HIG 要求的第三档**：HIG《Color》要求自定义色至少给 light / dark /
  increased contrast 三套。原先只有两套，而且 `_increasedContrast` 是个**从没接上
  线的死字段**。现在 `dark` / `darkHc` / `light` / `lightHc` 四套常量（HC 取 HIG
  增大对比档实测值，半透明底衬 alpha 同步上调），HC 档每个角色比标准档至少高约
  1.3 倍比值。
- **系统开关在桌面端根本不会亮**：`AccessibilityFeatures.highContrast` 只在
  iOS / macOS / Android 上报，Windows / Linux 恒为 false，光「跟随系统」等于没有。
  因此除接系统标志外，另加应用级三态（跟随系统 / 提高 / 标准）落在
  `XlThemeController.contrast`，持久化到 `ui_prefs.json`，设置页新增「对比度」选择行；
  `didChangeAccessibilityFeatures` 触发重建。`XlPalette.of()` 每帧重新选档，
  不依赖 ThemeExtension 的继承结果。
- **修 `copyWith` / `lerp` 两个假实现**（延续「去伪存真」）：`copyWith` 原本是
  `=> this`，`lerp` 是 `t < 0.5 ? this : other` —— 主题动画在阈值处整体跳变，任何
  调用 `copyWith` 改单色的代码静默无效。现按 105 个字段逐一实现，颜色用
  `Color.lerp`、渐变用 `LinearGradient.lerp`、标量用 `lerpDouble`。
- **语义色单一来源**：`semanticSuccess/Warning/Danger/PinkSoft/GoldSoft` 原来是
  const，与调色板字段各写各的（同一「成功」在不同主题下能给出两个色）。改为 getter
  直接委托 `green/orange/red/pink2/gold2`。
- **`btnInk` 的用法纠正**：它是品牌渐变底上的**墨色**，不是「深色模式专用文字色」。
  9 个文件里 15 处 `p.isDark ? p.btnInk : Colors.white` 全部收敛为 `p.btnInk`。
  实测旧值：浅色档 `btnInk` 是浅粉 `FFA8C8`，压在品牌渐变上只有 1.05~1.85:1
  （等于看不见），而写死的那条 `Colors.white` 分支在旧浅底上也只有 1.68~3.32:1，
  两个方向都不达标。改后：light 白墨对品牌底 6.39、对实底按钮 12.25~13.45；
  dark 深墨 5.30；两个 HC 档 8.79 / 9.08。另有两处把 btnInk 当**开关滑块背景**用，
  导致浅色模式白底白点，改为 `surfaceHi`。
- 语法高亮原先硬编码 `0xFFE8C46A`（字符串）/ `0xFFFF6FA5`（关键字）/
  `Colors.grey.withOpacity(0.5)`（注释），在浅色档的最差面上实测分别只有
  1.21 / 1.87 / 1.27~1.45:1 —— 基本等于没有高亮。现在 `code_editor` 走调色板
  （`gold` / `pink` / `text3`），四档全部 ≥4.6:1，深浅自动可用。
- `_ErrorApp`（后端起不来时唯一的界面）此前整套硬编码深色 hex；现在同样吃
  `XlPalette`，浅色系统下不再是一块突兀的黑底。
- 顺手修掉接入时踩到的**静默数据丢失**：`ui_prefs.json` 由主题控制器与语言控制器
  共用，而 `LocalStore.writeJson` 是整档覆盖 —— 切一次主题会把用户设的
  `lang` 抹掉，下次启动语言回落系统默认。改为先读后合并、只覆盖自己那两个键。

### 成长链路补全：练完的权重能不能真的用起来

参考 jingyaogong/minimind 的收尾做法（合并导出 → 生成式验收 → 断点续训），
先只做前两件，因为那是我们真正缺的环；训练本身（真 batch、梯度累积、QLoRA、
手写 DPO）我们已有实测，不需要抄。

- **新增 `core/export.py`：LoRA 合并 → 独立 HF 模型 → GGUF 通道。**
  此前训练产出的 adapter 只有推理端「加载基座 + 挂 adapter」这一条路，
  长大的人永远没法单独拿出来用，也进不了模型商店。`merge_adapter()` 用
  `PeftModel.merge_and_unload()` 产出可独立加载的模型目录，命名
  `<基座>+grown`，模型商店自动发现。诚实约定：基座**只**认
  `adapter_config.json` 里的 `base_model_name_or_path`（绝不去扫 models/
  随便找一个凑，那会把 A 的 adapter 合到 B 上，产出两边都不是的权重）；
  先算磁盘余量；写进 `.writing` 临时目录再整体改名；带
  `xiaoling_merge.json` 溯源；产出后**独立重新加载 + 真生成一次**才敢说成功，
  自检不过直接删掉产物。`find_llama_cpp()` 只探测不下载不 pip install，
  没工具时给出可执行的下一步（`XIAOLING_LLAMA_CPP`）。
- **新增 `core/eval_probe.py`：晋升前的生成式验收。**
  只看 loss 会「数字更好了，人没了」—— 小模型 LoRA 最常见的失败是灾难性
  遗忘与复读退化，而晋升恰恰是按数字做的。现在拿固定探针（认不认得自己、
  是什么做的、打招呼的语气、有没有退回通用助手腔）用同一套 greedy 解码
  对**新权重和基座各生成一次**逐条比对，并检测 n-gram 复读塌缩。
  跑不动就是 `ok=False, ran=0`，绝不给一个 0 分冒充「测过了」。
- **接线：`training:mergestatus / export / gguf / probe / acceptance` 与
  `growth:promotecheck / promote`**（沿用不改 proto 的 ExecuteCommand + JSON）。
  合并、转换、验收是长任务，一律交后台任务表立即回 `task_id` + `poll` 指令，
  不同步阻塞 RPC，也不会先回一个 `ok=true` 再慢慢失败。
- **`config.growth.require_eval` / `pass_threshold` 从此真的被读。**
  这两个键此前躺在默认配置里没有任何代码引用（写了等于没写）。现在
  `merge_and_promote()` 在**基底退役之前**过这道门：这是唯一还能无损反悔的
  时机，一旦被拦住，基底原封不动、代数不 +1、失败的中间产物移入隔离区
  （隔离区不可用才删源目录，并写 journal 说明「删了」）。开关关闭时如实
  返回「未做生成式验收，仅凭 loss 晋升」，前端据此说话。
  验收**跑不完也拦**：`verdict=pass` 但 `skipped>0`（超时只剩 1 条跑完，
  分数 1/1 看着满分）作为信息没问题，作为晋升门槛就是拿没测的那几条赌
  人格还在。

### 两个由测试逼出来的真 bug

- **`core/config.py`：`load()` 把模块级 `DEFAULTS` 的嵌套 dict 按引用交出去。**
  `_deep_merge` 只复制被 extra 覆盖的键，没覆盖的 `cfg["growth"]` 就是
  `DEFAULTS["growth"]` 本身；任何 `set_value` / `setdefault+update` 都在直接
  改默认值，同进程之后每次读配置都带着这份脏值 —— 表现为「默认值悄悄漂移」。
  写 `training:acceptance` 的回读测试时撞见，改为合并结果与 base/extra
  不共享任何嵌套 dict。
- **`core/quarantine.py`：`PENDING_ROOT` 冻结在 import 时刻。**
  与 trainer 的 `_resolve_adapter_dir()` 同一类坑。打包版的 runtime_hook 和
  测试都在运行期才设 `XIAOLING_PENDING_DIR` / HOME，冻结常量完全不生效 ——
  实测把环境变量指到临时目录后，`move_to_pending` 仍把权重写进真实
  `~/待处理`，并在真实家目录留下清单副本。改为 `pending_root()` 调用时解析；
  用户自定义过隔离区时，清单副本跟着落在隔离区里，不再自作主张往桌面写。

### 验证

- 后端全量测试通过；新增断言：真 LoRA 必须产出 `elapsed_sec` / `sec_per_step`，
  提醒完成必须落盘（含时间戳容差与「重复完成不得谎报」）。
- 新增 `tests/test_growth_export_probe.py`（真权重链路，tiny-gpt2 约 5MB）：
  训练→合并→独立重载→验收，验收**正确地**把这个随机初始化的玩具模型判为
  退化（"stairs stairs…" 0/4，verdict fail）—— 证明探针不是橡皮图章。
  GGUF 分线的「找到工具」分支用桩工具补齐（绝对路径 shebang，因为用例把
  PATH 收紧到只含桩目录）：convert→quantize 两步、缺 llama-quantize 时
  如实标 `quant_note` 而不谎报 quant、失败时带上退出码与 stderr 末行。
- 新增 `tests/test_promotion_gate.py`：门槛判定（关闭=如实「没测」/ 跑不动=拦 /
  阈值真的来自 config / 对照方是当前基底 / 跑不完=拦）、晋升后果（基底不动、
  代数不加、产物进隔离区、journal 有 promote_blocked），以及 RPC 接线的
  只读性与诚实失败。
- `python3 -m pytest tests/ -q` 全绿（1 处 skip 为真实 llama.cpp 用例，
  本机没有该工具）。
- 前端无 Flutter SDK，以 `dart format` 做解析校验 + 定向 grep 分析器输出；
  `Target of URI doesn't exist` 中相对路径报错已归零，剩余均为 `package:flutter/*`
  缺失导致的固有噪声。配色那一轮的 16 个前端文件全部通过解析。
- `python3 tools/contrast_audit.py --strict` 四个变体（dark / darkHc / light /
  lightHc）全部退出码 0，作为配色改动的常驻门禁 —— 以后改色值重跑即可，不需要
  跑 Flutter。
- 新增设置项用到的 `Icons.contrast_rounded` 按 Flutter 3.47.7 的 API 文档核对存在，
  避免又是一个编译不过去的图标名。

### 断点续训：把「可续训」这三个字变成真的

抄 minimind 顺序里的第三件。此前前端写着「断点续训：已实现」，`trainer_state.json`
也确实记着 `global_step`，但那是全部——三处独立探针（tiny-gpt2 真训练）证明它
没有一处成立：

1. **恢复的是权重还是编号？** 都不恢复。`run()` 读 state 拿到 `global_step` 只用来
   把进度条数字接着往上加，LoRA 每次都是新初始化的 —— 于是「训练了 300 步」的
   报告对应一个第 0 步的模型。
2. **优化器状态根本不落盘。** 没有 `optimizer.pt`，AdamW 的动量每次归零，
   即使权重接上了，前几步的梯度也接不上。
3. **生产路径压根走不到。** proto 的 `TrainingRequest` 只有 steps / learning_rate /
   batch_size / lora_rank / dataset_name 五个字段且不能改，`StartTraining` 与成长轮
   都没法把 `save_steps`/`resume` 传进 trainer；`save_steps` 默认 0，于是永远不落检查点。

改动（原则：降级要明说，绝不假装）：

- **检查点是真的**：`_save_checkpoint()` 往 `adapter/checkpoints/stepN` 落
  LoRA 权重 + `optimizer.pt` + 该步的 loss 曲线快照（每步一份 `trainer_state.json`），
  全局 state 记 `latest_checkpoint` / `checkpoint_optimizer`。续训按检查点的
  **真实**步数走，并把优化器状态装回 AdamW；state 比可用检查点新时如实说明
  （`resume_behind_state`），不拿旧编号冒充新进度。
- **三条硬如实约定**：
  - 曾经落过检查点、现在读不到 → **拒绝本次训练**（`resume_denied` + `ok=False`），
    绝不拿一个随机初始化的 LoRA 按旧步数继续；
  - 旧版留下的 state（当时根本没有检查点功能）→ 明确告警并**从第 0 步重开**
    （`resume_reset`），不再沿用旧步数；判据是 state 里有没有
    `latest_checkpoint` 这个承诺，把「从来没有」和「弄丢了」分开；
  - `optimizer.pt` 缺失或装不回去 → 明说「本次只续权重、动量从头积累」，
    不宣称完整续训。
- **配置驱动的开关（不改 proto）**：新增 `config.growth.checkpoint_interval`
  （默认 0 = 完全关闭，行为与引入本功能前逐字节一致）、`checkpoint_resume`
  （auto|always|off）、`checkpoint_keep`（默认 3，钳到 1..24）。
  `trainer.checkpoint_cfg()` 在调用时读配置，读不出来按关闭处理并记 `error`，
  不猜「大概是开着的」；`_resolve_checkpoint_args()` 让显式传参永远优先，
  所以 CLI/测试里 `save_steps=2, resume=True` 的行为不变。
- **新 RPC 指令 `training:checkpoint`**（沿用 ExecuteCommand + JSON，读/写两用）：
  `training:checkpoint 50 auto 3` 开、`training:checkpoint off` 关；拒绝只给模式
  不给间隔、拒绝 `0 auto` 这种自相矛盾的组合，写不成时回「配置写入失败」而不是
  先回 `ok=true`。
- **`training:adapter` 从此报事实**：`checkpoints_usable`（真的有权重的 stepN）、
  `resume_would_use`（用与 trainer **完全相同**的选取规则算出来的那一个）、
  `optimizer_in_checkpoint`、`resumable` + `resume_blocked_reason` + `resume_hint`。
  早先它报的是目录里最新的那个，而 trainer 只会用「不高于 global_step 的最新一个」——
  等于对着一个根本不会用的检查点告诉你「可续训」。
- **修掉两个自己引入的坑**：
  - `optimizer.pt` 比 LoRA 权重还大，混进 `adapter_bytes` 后 `progress_percent`
    被虚高、并会提前触发 `adapter >= 基底` 的晋升判定。新增
    `growth.adapter_weight_bytes()`（跳过 `checkpoints/`、跳过 `optimizer.pt`、
    按 (name,size) 去重 `lora_latest` 副本），`GrowthEngine.adapter_bytes` 改用它；
    `dir_bytes()` 原样保留给「磁盘占用」口径。实测 2904 vs 59637。
  - 训练结束时那次 `write_state()` 把 `latest_checkpoint` / `checkpoint_optimizer`
    整段丢掉，等于每次跑完都把续训线索擦干净（第二次仍从 0 开始）。改为显式
    carry-forward，并有测试盯着这两个键。
- **轮换**：`_rotate_checkpoints()` 只保留最近 `checkpoint_keep` 个 stepN，
  非 stepN 目录（用户自己的备份）与最新那个永不删，删不掉时不谎报已删。
- **落盘失败不再静默**：`write_state()` 返回 bool；权重落上了但 state 写不进、
  或只有 `optimizer.pt` 失败，都会发出 `[告警]` 事件并说明「中断后无法续训 /
  只能续权重」。
- 前端训练页「可续训」一行改为 `_resumeLine()`：可续时给出「从 step6 续，
  global_step=7」+ 可用检查点列表，不可续时给出原因与开启方法。

验证：

- 新增 `tests/test_resume.py`（32 例）：配置默认值不改行为、配置驱动参数、显式
  传参优先、只给模式不给间隔要说明、两次真训练真的接上（`resumed_from step2` +
  `optimizer_restored True`）、承诺过的检查点没了→拒绝、没承诺过→告警并从 0 重开、
  state 领先于检查点→按真实步数、`_latest_checkpoint` 只认数字名且要有权重、
  曲线快照优先、优化器往返真的把动量装回来、损坏/缺失/不可读的优化器与检查点
  各自如实降级、state 写不进要报、`adapter_weight_bytes` 不虚高（==1000 而
  `dir_bytes` ≥7000）、进度百分比不被撑爆、`training:adapter` 的
  `resume_would_use` 与 trainer 同源、`training:checkpoint` 读写与参数校验、
  轮换封顶与不误删、未知 op 的提示里带上 checkpoint。
- 端到端探针（`XL.train_stream` 生产链路，间隔 2/auto，跑 3 次各 3 步）：
  步号 3→5→7 连续，末次 meta `resumed_from=step4`、`optimizer_restored=True`、
  `resume_behind_state="state 记录 5 步，可用的最新检查点只有 4 步，本次从 4 步续。"`；
  `training:adapter` 报 `resumable=true / resume_would_use=step6 /
  optimizer_in_checkpoint=true`；随后 `rmtree(checkpoints)` 再训练，如实回
  `error：曾经落过检查点 …/step6，但它现在读不到了 … 无法续训。`
- 轮换探针（间隔 1、keep 2，连跑 4 次）：检查点稳定停在 2 个（[1,2]→[3,4]→
  [5,6]→[7,8]），`global_step=8`、`resume_would_use=step8`，
  `adapter_weight_bytes` 2904 而 `dir_bytes` 7.1MB —— 口径分离符合预期。
- `python3 -m pytest tests/ -q` → **244 passed, 1 skipped**（skip 仍为真实
  llama.cpp 用例）。
- 前端本机无 Flutter SDK，`_resumeLine` 用到的 `_metaText` / `_joinList` 均在
  同文件已定义（training_page.dart:239、2603），未能编译验证，需真机复核。

### 蒸馏：从一条死链路变成真链路

抄 minimind 顺序里的最后一件。审计时我先假设「改名就好」（把 UI 上的「蒸馏」
改成「数据收集」），但读完代码后选择**接通**，因为改名留不下这些证据 ——
三条独立探针（`/tmp/resume_probe/probe_distill.py`）证明这是一个完整闭环的**假象**：

1. **三个 API 配置键零读取方**。`deepseek_api_key` / `deepseek_base_url` /
   `teacher_model` 在 `backend/` 全仓只出现在默认值里，没有任何代码读它们；
   `GrowthStore.distill_samples()` 实测恒为 0 条，`deepseek_output` 列从来没人写。
2. **`DistillThrottle` 三个方法零调用方**。`check()` / `record()` / `cost()`
   写好了、有状态文件、有单测式的自洽，但训练与对话路径上没有任何一处调用它。
3. **报表却在撒谎**：`samples_report()` 照打「蒸馏 API：开｜今日 0/200｜0 元」
   ——「开」指的是配置里的布尔开关为真，与「有没有老师端、能不能发请求」无关。

改动（原则同前：降级要明说，绝不假装）：

- **明确这是文本蒸馏，不是 soft-label KD**。走 OpenAI 兼容接口只拿得到老师写出的
  文字，拿不到 logits，所以训练本质是「把老师答案当 SFT 语料」。这句写进
  `growthPipeline.md` 的诚实边界第 4 条，不冒充按词分布蒸馏。
- **`teacher_config()` 成为唯一的配置读取方**：三个键齐备、且 key 不是「暂未填入」
  这类占位符才算已配置，否则返回 `configured=False + reason` 指出缺哪一项；
  只回显 `key_len` / `key_tail`，**绝不明文返回 Key**。
- **新增 `TeacherClient`**（stdlib `urllib`，项目红线不引新依赖）：`gate()` 走
  配置→节流→缓存/真实请求，`ask()` 返回 `ok/text/from_cache/tokens_in/tokens_out/
  reason/error/cost_yuan`，解析时 `content` 优先、`text` 兜底，用量按 usage 字段计。
- **对话路径不联网**：新增 SQLite `distill_queue` 表，`engine._post_chat()` 只调
  `register_for_distill()` 写一行本地记录（重复对话、未配置、开关关掉时不入队）；
  真正的请求发生在 `train_round()` 组语料之前，或用户显式 `growth:distill run`。
- **`train_round()` 先蒸馏、后组语料**，顺序不能反：`sample_for_training()` 的优先级
  是 `corrected_output > deepseek_output > base_model_output`，先问老师本轮才吃得到。
  有测试用 monkeypatch 记录调用序列断言 `["distill", "corpus"]`。
- **`set_teacher_output()` 会重算质量分并回填 DPO**（老师答案在质量分里占 0.20），
  但**绝不覆盖已有的老师回答** —— 已经进过训练的语料不该被悄悄换掉。
- **三重约束是真的**：每轮 `distill_batch_limit`（默认 8）、每天
  `distill_daily_limit`（默认 200，由 `DistillThrottle.check()` 逐条拦）、
  单轮时间预算 `distill_time_budget_sec`（默认 20s）。时间预算这条尤其必要：
  读代码才发现 `engine._route_train → after_training_round → train_round` 是**聊天里
  的同步调用**，单次超时 12s × 8 条最坏 96 秒不回话，用户看到的是「小凌卡死了」。
  超预算就带着 `truncated` 如实收工，剩下的留在队列里下次再问。
- **失败逐条记账**：`asked / answered / from_cache / failed / gave_up /
  skipped_stale / errors / tokens / cost` 分开统计，HTTP 500 记 `failed`，
  超过 `max_attempts` 才 `gave_up`；空补全、记录已删、已有老师答案各自走不同分支，
  不整批吞掉。
- **新 RPC 指令 `growth:distill`**（仍不改 proto）：裸调用**只读**（不发网络、
  不写文件、不记 journal），`run [n]` 走后台任务返回 `task_id`，
  `on|off` 写 `growth.distill_enabled`，`limit <n>` 校验 1..200。
- **报表口径改正**：未配置时打印「蒸馏老师：未配置 — <原因>」，
  配好才打印 `model@base_url（Key …tail）` + 开关/配额/费用 + 队列积压。

### 文档去伪存真：features.json 里 12 个不存在的模块

改完代码顺手查文档，结果比代码问题更严重 —— 文档是**唯一被人当承诺读的东西**：

- `docs/features.json` 的 15 条里 **12 条 module 路径不存在**
  （`core/growth_store.py`、`core/eval.py`、`core/rank.py`、`core/lifecycle.py`、
  `core/device.py`、`core/peft_train.py`、`core/rag.py`、`core/selftest.py`、
  `core/throttle.py`、`pet.py`、`renderer/dashboard.py`、`打包/termux`）。
  现已全部改为真实位置（多数在 `core/growth.py` 一个文件里），并新增 `missing`
  状态：`pet.py`（Tkinter 2D 兜底）全仓零 tkinter 引用、从未存在，直接标 missing。
- **三条「完成」是假的，已降级为 partial**：晋升「三条件评估」的 B 验证集 loss
  只作事件上报不判定、C 通用基准（常识 20/通用 20/安全 10 共 50 题）在仓库里不存在；
  「动态升 rank」没有旧权重复制+新增补零的张量重排，且 `grow_rank()` 零调用方；
  「显存分级 <4/4~8/>8GB 三档」没有对应代码（真实实现是 `HardwareInfo.tier()` 五档 +
  `train_plan()` 的 batch/accum/quant）。`7.2 多适配器堆叠` 整条标未实现。
- 模块归属纠正：通道在 `core/channels.py`（11 个，**没有 QQ**，原先写的「微信/QQ」
  只有 weixin.qq.com 域名）而非 `core/fusion.py`（它是指令解析器）；
  记忆检索在 `core/memory.py`（JSON + 向量 sidecar，**不是 SQLite**）而非 `core/rag.py`；
  体检入口是 `python main.py --selftest` → `core/system.py`，各模块自带 `selftest()`。
- `docs/apiContract.md` 第一节写的是一个**从没存在的 CLI**（`python -m core.growth
  <cmd>` —— growth.py 没有 `__main__` 块，`GrowthEngine.simulate/evaluate` 也不存在），
  第三节写的是 `renderer/renderer.py` 的 `AvatarRenderer.render_frame()`（真类是
  `renderer/stage.py::Stage`，后端根本不做光栅化，画面在 Flutter）。全部按实际代码重写，
  并把前端唯一能用的 `ExecuteCommand` 指令族逐条列成契约表（含只读/写、后台任务、
  返回字段）。
- `docs/apiContract.csv` 与 `docs/openapi.yaml` 同步：删掉虚构的
  `core.eval.Evaluator.evaluate_all` / `core.rank.grow_lora_rank` /
  `renderer.renderer.AvatarRenderer`，`EvalResult{A,B,C}` 换成真实的
  `PromotionGate`（与 `growth:promotecheck` 字段一致），补 `DistillStatus` /
  `DistillRunResult`。CSV 现用 `csv.writer` 生成，参数里的逗号不会再把列冲开。
- `docs/growthPipeline.md` 流程图按代码重画：训练前蒸馏及其四条跳过分支、
  `checkpoint_interval/resume/keep`、`adapter_weight_bytes` 口径、换代三条真实门槛
  （体积 / 磁盘上限 / 生成式验收）、`grow_rank()` 无调用方；「三条件」段落改成
  明示「那两条在代码里不存在」。
- `docs/analysisReport.md` 顶部原话是「自动生成于 2026-09-25，扫描仓库真实文件得出，
  未做任何估算」—— 这份快照本身才是最大的估算。加了醒目勘误头（保留历史内容对照），
  §3 目录树改为仓库现状（`工具/测试/打包` → `scripts/tests/packaging`），
  §4 六条不成立的能力以删除线保留并逐条给事实，§6 补两条真边界。
- `docs/stats.json` / `docs/tree.json` 用 `git ls-files` + 逐行实测重新生成，
  并写明口径（排除 gRPC/Dart 生成桩代码），不与历史数字直接比较。
- `scripts/registry.json` 原本没有任何读取方（全仓 grep 只命中它自己），里面四个命令
  全是死的（`core.filebox`、`python -m core.growth check|report`、`renderer.app --showcase`、
  `core.selftest`）。已换成实测可用的 CLI，并在文件首声明「当前没有程序读它」；
  顺带修正 `vrm_to_fbx.py` 的真实用法（Blender 风格，参数在 `--` 后面，没有 argparse）。
- README 两处「蒸馏」措辞收敛：明说是**可选的文本蒸馏**、需要自备接口，
  以及回滚/GC/清库目前只有后端 API、没有前端入口。
- **0.0.1 发布说明的勘误**（不改写历史条目，只在此记录）：那节的
  「工作台 UI：…蒸馏按钮…全部图形化」不成立，Flutter 端 `grep 蒸馏|distill`
  零命中；本轮接通的是后端链路，前端入口仍是待办。

验证：

- 新增 `tests/test_distill.py`（40 例，含一个真起 `ThreadingHTTPServer` 的老师桩，
  计次数并记录收到的 `Authorization` 头）：占位 Key 算未配置、未配置时一条请求都不发、
  三个键缺一即未配置、`_post_chat` 只登记不发网、不重复入队、开关关闭不入队、
  真请求写回 `deepseek_output` 并重算质量分、HTTP 500 → failed → 超次 gave_up、
  空补全、陈旧记录跳过、已有老师答案不再花钱、拒绝覆盖空/已有答案、点踩回填 DPO、
  时间预算截断（`truncated` / `remaining_pending` / `elapsed_sec`）、超时取配置并钳位、
  费用按 11 in / 7 out 实测、journal 只在真跑时写、`train_round` 调用顺序
  `["distill","corpus"]`、语料优先取老师答案、报表未配置文案、RPC 只读/run 后台任务/
  on-off/limit/坏子命令/未知 op、`_parse_completion` 各种形状、被拦时不建 socket、
  网络不可达 reason=`network`、`mark_distill` 拒收未知状态。
- 端到端探针（生产链路 + 后台任务）：3 条对话 → 队列 3 条待问 → `growth:distill`
  只读（桩零命中）→ `growth:distill run` → 桩被请求 3 次、
  `Authorization: Bearer sk-live-probe-abcdef9876`、记录被填上、
  训练前队列归零 answered=3、语料取自老师答案、报表与 journal 一致。
- `python3 -m pytest tests/ -q` → **284 passed, 1 skipped**（skip 仍是真实 llama.cpp
  用例）；`--collect-only` 285。
- `docs/features.json` / `apiContract.csv` / `openapi.yaml` 均通过解析校验
  （JSON load、`csv.reader` 列数全为 4、`yaml.safe_load` 8 paths / 5 schemas）。

### 成长运维：把文档里那条「待办」真的接完

文档改到最后剩一条我自己在 `analysisReport.md` §6.6 写下的话：
「暂停/回滚/GC/清库目前只有 Python API …这一条是待办，不是已完成」。
待办写在文档里不等于做了，所以把它接完 —— 用户控制自己的模型和数据，
不该依赖「会敲 Python」。

- **六条新子命令**（仍不改 `.proto`）：`growth:status`（只读真值快照）、
  `growth:pause [原因]`、`growth:resume`、`growth:rollback`、`growth:gc`、
  `growth:purge <范围>`。`rpc/server.py::_handle_growth_cmd` 一份文档串列全。
- **默认只读，破坏性动作必须显式 `confirm`**：`growth:rollback` 裸调用只列回收区，
  `growth:rollback <代>` 是 `dry_run` 演练，只有 `<代> confirm` 才搬目录；
  `growth:gc` 只演练，`growth:gc run [force]` 才真删；`growth:purge <范围>`
  只按口径数条数，`confirm` 才执行 DELETE。数错的代价是删数据，不能靠手滑。
- **一个必须绕开的坑**：`GrowthEngine.gc()` 无条件 `self.journal("gc", ...)`。
  如果「演练」也走它，前端每刷新一次成长页就往流水里塞一行，报表再把这行
  当真实事件统计。所以演练直接调 `ModelLifecycle.gc(dry_run=True)`，
  测试用 journal 行数不变来钉死这条（`test_gc_bare_is_dry_run_without_journal`、
  `test_status_is_read_only`）。
- **预览不许报假成功**：`ModelLifecycle.rollback(dry_run=True)` 失败时返回
  `{ok: False}` 且**不带** `dry_run`，早期写法会把它显示成「演练通过」。
  现在明确标注：拿不到 `dry_run` 就是没通过。
- **GC 结果补 `ok`**：`lifecycle.gc()` 只回 `allowed/deleted`，没有 `ok`；
  稳定期没过时若外层照抄「任务跑完了 = 成功」就是假成功，
  所以在 RPC 层按真值补 `ok = allowed`。
- **`status()` 补暂停来源**：新增 `pause_reason / paused_at / resumed_at` 三个字段。
  只回一个布尔值的话，界面只能说「已暂停」，用户不知道是不是自己上次点的。
- **前端入口**：成长页「成长工具」区新增「暂停成长 / 恢复成长」按钮，
  以及「成长运维」浮层（`_GrowthOpsDialog`）——回收区分代选择、GC 演练结果与
  force 开关、四种清理口径（全部 / 已训练 / 被点踩 / DPO 对）。
  确认按钮**默认禁用**，必须先演练且演练 `ok=true` 才亮；
  换清理口径时把「不可撤销」勾选作废。
  后台任务成功与否判两层（外层 `status` + `result.ok`），
  只判外层就会把「被稳定期拦住」报成成功。
- **文档同步**：`apiContract.md` 指令表新增 10 行（六条子命令的只读/演练/confirm 三态）、`apiContract.csv` 33→40 行、
  `openapi.yaml` 8→12 paths / 5→8 schemas（新增 `RollbackPreview` / `GcDryRun` /
  `PurgePreview`，字段名逐个从代码抄），`docs/stats.json` 与 `docs/tree.json` 重新实测，`growthPipeline.md` 参数表标注
  「paused 是唯一有图形入口的成长参数」，`featureMapping.md` 7.7 行
  顺手修掉一处旧错：**没有 `growth:list` 指令**，逐条查看样本只有 Python 的
  `GrowthStore.list_records()`。

### 验证（成长运维）

- `tests/test_growth_ops.py`（29 例，全部在 `_make_home` 隔离的临时 HOME 里跑）：
  暂停后 `train_round()` 真的 `skipped/paused`（不是只写了个布尔）、journal 逐次记账、
  重复暂停回显 `already_paused`、`resume` 带回 `can_train_now` 与阻塞原因、
  `status` 连点两次 journal 行数不变、回滚裸调用与演练**一个目录都没动**
  （用 `model.safetensors` 的字节前缀和 registry 状态双重断言）、
  `rollback confirm` 真的把基底换成旧代并把当代移入回收区、
  坏代数/缺失目录不报 `dry_run`、GC 演练不删文件不写 journal、
  `gc run force` 只删 `status=trash` 且 keepers 保住最新一代、
  稳定期没过时 `gc run` 的 `ok=false` 且目录仍在、
  purge 预览不删数据、`disliked`/`dpo` 口径计数正确、`confirm` 才真删、
  非法 scope 拒绝且不起后台任务、未知子命令的用法串含全部新命令、
  所有回复不含 API Key 明文。
- `python3 -m pytest tests/ -q` → **313 passed, 1 skipped**（skip 仍是真实 llama.cpp
  用例）；`--collect-only` 314；本文件单独跑 `tests/test_growth_ops.py` → 29 passed。
- 端到端探针（生产链路 + 替身任务表）：`status → pause → promotecheck(paused=true)
  → status(成长已暂停) → resume(样本不足 0/20) → rollback(回收区为空) →
  gc(稳定期未达标，allowed=false) → purge all(would_remove=0，只读) →
  非法参数两条 → 后台任务零次被起（证明预览不偷偷开工）`。
- **未验证部分如实说明**：`frontend/` 无 Flutter SDK，`growth_page.dart` 只做了
  `dart format` 解析校验（可解析、且未把仓库既有代码重排 —— 与旧文件对比
  `dart format` 会产生 1861 行改动，说明仓库用的是旧版格式化风格，
  按「不批量格式化已跟踪文件」的红线保持原样），**没有** `flutter analyze`、
  没有真机点击验证。后端 29 例通过不代表前端按钮一定可用。


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

- 修复 PyInstaller 打包后 3D 查看器黑屏：contents_directory 平铺资源，使 sys.\_MEIPASS 与资源真实位置一致
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
