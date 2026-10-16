# 变更记录 · 2026-10-14（第二批）· 统一 API 配置 + 沙箱 shell 真修 + Agent 内置化 + 形象切换持久化 + 表情面板 + ASR API 降级

> 操作人：Qoder（AI 助手）
> 触发：用户实测反馈（截图）——「还有好多假功能假实现」「agent 是自带功能并不是独立接口」
> 「左边还得加一个 api 配置的选项卡」「沙箱也是不好用，ls 等基础命令都用不了」。
> 红线遵守：未删除任何文件；改动文件同目录留 `.bak-20261014b` 备份（已在 .gitignore 忽略范围内）；
> 未动 `.proto`、未重新生成 gRPC 桩代码（扩展全部走 ExecuteCommand + JSON）；未新增第三方依赖（纯标准库）。

## 一、修改前备份（同目录，仅复制，后缀 `.bak-20261014b`）

backend/core/{sandbox,exec_gate,agent,trainer,multimodal}.py、backend/rpc/server.py、
frontend/lib/pages/{chat,dashboard,settings}_page.dart、tests/test_sandbox_degraded_guard.py、
CHANGELOG.md、docs/{KNOWN-ISSUES,apiContract}.md、docs/{apiContract.csv,openapi.yaml}。
（backend/core/api_config.py 与 tests/test_api_config.py 为本轮新建文件，无原文件可备份。）

## 二、沙箱「ls 都用不了」——找到真根因并修掉

**根因**：`backend/core/sandbox.py` 里所有 `subprocess.run(cmd, shell=True)` 在 Windows 上
落进 `cmd.exe`，而 `cmd.exe` 根本没有 `ls` / `cat` / `pwd` 这些 POSIX 命令。这不是权限问题、
不是守卫拦截，是 shell 选错了。此前多轮「修复」都没碰到这一层，所以用户说「搞了半天」。

**修法**（`_posix_run_args(cmd, plat)` 统一路由）：
- Windows 且找到 bash（`shutil.which('bash')` + Git Bash 常见安装路径候选）→
  `[bash.exe, '-c', cmd]` + `shell=False`，返回体标 `shell:'bash'`；探测进程内只跑一次（缓存）。
- Windows 没找到 bash → 如实降级 `shell=True`（cmd.exe），返回体标 `shell:'cmd'`，
  **不伪装成 bash**（降级要明说）。
- POSIX 平台行为完全不变（`shell:'sh'`）。
- `exec_gate` 透传 `shell` 字段；三处执行路径（Job Object、subprocess 降级、PERM_FULL）全部接上。
- Job Object `ActiveProcessLimit` 8 → 64：bash 管道 `a | b | c` 会 fork bash 本体 + 每个管道成员，
  8 个上限会直接杀掉正常管道命令。

测试：`tests/test_sandbox_degraded_guard.py` 新增 5 例（POSIX 不变式、Windows→bash 路由、
Windows 无 bash 的 cmd 如实降级、bash 探测只跑一次、exec_gate shell 透传）。

## 三、新增「API 配置」统一入口（设置页左侧新选项卡）

原先外部 API 配置是**互不相通的两套**：`training.api_*`（训练页）与 `deepseek_*`（散落配置），
用户在任一处「配了等于没配」——另一条链路完全读不到。本轮收敛为统一存储
`config.api.{enabled, base, key, model, provider}`：

- 新模块 `backend/core/api_config.py`（纯标准库 urllib）：
  - `cfg()`：打码快照（明文 key 永不回流前端），含 `providers` 白名单与 `configured`；
  - `set_field()`：base 校验 http/https、provider 白名单、key 空串=清除；
  - `chat()`：真连 OpenAI 兼容 `/chat/completions`，未启用时 `ok:false, disabled:true`
    并如实说明「未启用：调用方自动降级本地模型」；
  - `test()`：真实最小连通性测试；
  - `transcribe()`：multipart `/audio/transcriptions`（标准库手拼 body，无 requests），
    空识别结果如实回 `ok:false`「端点返回空识别结果」。
- gRPC 指令族 `api:cfg | api:set <字段> <值> | api:test | api:chat <messagesJson>`
  （`_handle_api_cmd`，在拿到引擎前路由，不依赖本地模型）。
- 前端设置页新增 violet「API 配置」选项卡：总开关（诚实文案：未启用时自动降级本地模型，
  不会假装在用 API）、供应商下拉、端点/密钥（打码展示+可清除）/模型名、测试连接 + 结果横幅。
- **训练链路打通**：`trainer.api_cfg()` 优先 `training.api_*`，未配时回落到统一 `api.*`
  （`source:"unified"`）——设置页配一次，训练/蒸馏直接可用。
- **Agent 用 API 操作应用**：`agent.py::_llm_think` 优先级改为 外部 API（启用时）→
  本地 `engine.chat` → 空串降级规则规划；API 失败时如实记日志回退本地，不静默冒充。
- **语音识别不再死路**：`multimodal.py::ASR.available()` 在 whisper 未装但 API 已配时返回 True，
  `transcribe()` 走云端 `/audio/transcriptions`。如实说明：**后端麦克风录音仍需 pyaudio**，
  这一条没有绕过（环境缺依赖，不是代码假实现）。

测试：新增 `tests/test_api_config.py` 16 例，含**真端到端**——本地起 mock OpenAI 服务验证
chat/test 链路、mock `/audio/transcriptions` 验证 multipart 真实字节（RIFF 头进、结果出）、
`builtins.__import__` 猴补丁模拟 whisper 缺失验证降级。全量回归 394 passed, 1 skipped。

## 四、3D 形象「切换不生效」——真根因与开关补位

**根因**：`SwitchModel` 只写 `model.path`，而全链路**没有任何地方**按 `model.path` 选 3D 形象；
`ListModels` 排默认形象读的是 `avatar.model`（按文件名匹配）——于是「切换成功」只是回包里的假象，
重启后永远回到默认形象。这就是用户说的「老问题，搞了半天没弄出来」在逻辑层的真相。

**修法**：`SwitchModel` 同时写 `model.path`（兼容渲染器）与 `avatar.model`（basename，
让下次 bootstrap 的 `models.first` 就是用户刚选的那个）。

**UI 补位**：dashboard 页此前**根本没有形象切换入口**。新增 `_avatarSwitcher`（多形象时显示，
芯片式选择器），乐观更新 + 失败回滚 + toast（成功/失败都如实）。

必须说明的边界：渲染本身是否显示某个形象，受限于沙箱无 Flutter SDK / 无 WebGL，
本轮只做了后端逻辑 + Dart 解析校验；**真机验证仍欠**（形象资源链路由 4f6a228 那轮已修）。

## 五、Agent 内置化（「agent 是自带功能并不是独立接口」）

- 聊天输入条新增 `_agentToggle`（violet 开关，麦克风与聚焦按钮之间）：打开后消息走
  `_sendAgent` → `pb.AgentRequest` 流式订阅，进度按 🧭（计划）/ 🔧（执行工具）/ ↳（结果）/
  ⚠️（错误）逐行渲染，done 后落最终回复。
- 可中断：`Completer` 存入 `_agentCompleter`，停止按钮取消订阅并 resolve await
  （修掉「中断后界面卡死在生成中」的隐患）；`dispose` 取消流。
- 独立 agent_page 保留为高级视图，不作为唯一入口——符合「自带功能」的定位。

## 六、表情包从假按钮变成真面板（零依赖）

不引入任何 emoji 包：用 Dart `\u{...}` 码点字面量内置 4 组（常用/表情/手势/符号）面板，
文本默认显示的符号补 U+FE0F（VS16）强制彩色。面板为底部弹层 GridView（tab 分页，
maxCrossAxisExtent 52），点击插入光标处（含 offset 合法性钳制）。
注意教训如实记录：Dart **不支持相邻字符串字面量拼接**，`'\u{2764}' '\u{FE0F}'` 是语法错误，
必须合并为单一字面量；heredoc 写入时曾吞掉 10 个变体选择符，最终改用 Python 程序化生成。

## 七、音色（用户 premise 需要纠正——如实说明）

用户怀疑「音色模型没拉下来」。**事实**：当前 TTS 走 edge-tts，是**云端**服务，
本地不存在「音色模型」这个实体，因此「拉取模型」这个修复方向本身不成立。
真正影响音色可用性的是 edge-tts 的在线可达性与 voice 列表接口；若上一版本正常而现在不正常，
应优先排查网络/代理与 edge-tts 版本，而不是找模型文件。此结论已写入 KNOWN-ISSUES。

## 八、验证与欠账（诚实清单）

- 后端：`python3 -m pytest tests -q` → **394 passed, 1 skipped**（基线 373 + 本轮 21）。
- 前端 Dart：沙箱无 Flutter SDK，只做了 `dart format --output=none` 解析校验；
  **真机点击验证全部欠账**（API 选项卡、形象切换器、Agent 模式、表情面板）。
- 语音链路：识别（whisper 或 API）已可用；**录音仍需 `pip install pyaudio`**（环境缺依赖）。
- `data_seed.jsonl` 仍未入库（等用户决定）。
