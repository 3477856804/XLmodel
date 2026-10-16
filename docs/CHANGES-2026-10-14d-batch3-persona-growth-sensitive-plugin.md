# 2026-10-14 第四批：把「换人格不生效 / 敏感词过滤器零调用 / 假按钮」改成真的

上一批（`CHANGES-2026-10-14c-fakes-to-real.md`）已经把 channels / workflow / dsh / git /
browser / plugin 六个「宣称有、其实没接线」的假功能修成真的。这一批继续把剩下的
同类问题清干净，覆盖后端 3 处、前端 3 处，全部落到能跑、有回归测试的程度。

**元规则仍然是：降级要明说，绝不假装。**

---

## 后端

### 1) 人格选择根本没作用到模型输出（system_prompt 组装链路）

**症状**：`XiaoLing.system_prompt()`（`backend/core/engine.py:1427`）里
组装了 `DEFAULT_SYSTEM_PROMPT + persona_presets.hint_for(cfg.persona) +
self.persona.prompt_suffix()`，看起来一切齐全。但 `ModelReplacement`
在 `__init__` 里被硬编码塞了 `system_prompt=DEFAULT_SYSTEM_PROMPT`，
`LocalModel.build_messages()` 只读那个静态串。**换一个预设、说一句提示词
完全不变**——因为 persona hint 与 prompt_suffix 从来没进模型。

**修复**：把「每轮现取」的 `system_prompt_provider` 回调一路从 engine
透传到 `ModelReplacement`，再到 `LocalModel.build_messages`：

- `engine.py`：`ModelReplacement(..., system_prompt_provider=self.system_prompt)`
- `model.py::ModelReplacement.__init__`：新增形参并持有；
  `get_model()` 内构造 `LocalModel` 时 `system_prompt_provider=self.system_prompt_provider`
- `model.py::LocalModel.__init__`：新增 `system_prompt_provider=None`；
  `build_messages` 里 **provider 优先**，取到即用；异常/空返回才退回
  `self.system_prompt` 静态串；两者都没有时仍给内置默认人格

**诚实边界**：provider 抛异常时退回静态串，绝不吞掉整轮对话。

### 2) GrowthEngine 双实例：RPC 每次 new，throttle/暂停/队列全是「刚出厂」

**症状**：`GetStatus` / `GetGrowthStatus` / `GetTrainingStatus` 三个 RPC
都写成 `GrowthEngine().status()`。`growth:` 指令族走的是 `eng.growth`（引擎
持有的那份内存对象），而每次 new 出来的 GrowthEngine **读不到 throttle
cache / 暂停标志 / 蒸馏队列**——用户在 UI 看到「一切正常」，实际后端可能已经
暂停或节流。三份状态，谁也不是真相。

**修复**：`_get_growth_engine()` 进程级单例：优先复用 `_get_engine().growth`，
engine 未就绪时退回一个进程级 `_growth_engine_singleton`（带 `threading.Lock`）。
三个 status RPC 一律走这个入口。加了源码级回归测试
`test_get_status_rpcs_use_singleton` 与 `test_no_fresh_growth_engine_in_status_rpcs`
兜住未来「不小心又写了一次裸 GrowthEngine()」。

### 3) SensitiveFilter：类都实例化了，全仓零调用方

**症状**：`_SENSITIVE_FILTER = SensitiveFilter()` 存在于 `engine.py:375`，
`check_sensitive` 和 `add_sensitive_word` 方法都实现了，但——
**对话链路里没有一处调用**。回复真出现内置敏感词也照样原样入库、原样
显示给前端、原样进记忆库与成长样本。过滤器只是配置里的装饰品。

**修复**：
- `engine._compliance_mask(reply)`：`_post_chat` 之前打码，返回给前端 +
  写进 conversation + 进记忆库 + 成长样本的都是打码后的文本。
  过滤器异常时原样返回，绝不吞回复。
- 流式路径的诚实边界已在 docstring 说明：token 已实时推给前端，这一步
  只能保证「落库/回流」的文本干净，无法收回已经显示出去的字。要真正
  阻止生成需要在输入侧设策略——那是更大的合规产品决策，不在本次接线范围。
- `_handle_ext_command` 新增 `sensitive:` 指令族：
  - `sensitive:list` 返回当前词表
  - `sensitive:check <文本>` 返回 `{hit, words, masked}`
  - `sensitive:add <词>` 追加词
  - 引擎不可用时如实 `_err`，不给空 list 骗人
- 路由元组加入 `'sensitive:'`，否则前端 `sensitive:*` 全掉到 fusion 未知指令。

### 4) plugin: 三个假按钮对应的后端补齐

前端「重启插件 / 卸载插件 / 从本地路径导入 / 打开插件目录」四个 dialog
row 之前只 `Navigator.pop`，什么都不做。后端补齐：

- `plugin:reload [名]`：有参数走 `pmgr.reload_plugin(name)`（热重载单件），
  无参数走 `pmgr.reload()` 整体重载并返回 `count`。重载失败必须如实 `_err`。
- `plugin:installpath <绝对路径>`：只接 `.zip` 或已存在的目录，其他一律
  报错。用户从文件管理器复制路径粘贴进来即可，跨平台都不依赖 GUI 选择器。
- `plugin:dir`：返回 `pmgr.plugins_dir` 真实字符串，前端复制到剪贴板。

## 前端

### 1) settings_page 三个「关于」按钮：从「功能开发中」到真实外链

新增 `_repoUrl` 常量（Gitee 交付仓库）+ `_openExternal(url)`：桌面
Linux 走 `xdg-open`、macOS 走 `open`、Windows 走 `cmd /c start`；任一
步失败退回**复制到剪贴板 + 明确告知**，不假装打开。Android 上
`Process.run` 拿不到这些二进制，直接走剪贴板兜底。GitHub/文档/反馈三个
`_aboutLink` 都传入 `url: _repoUrl`；「项目地址」行的字符串值也改成真实
`gitee.com/COSMOnb666/XLmodel`，并让它可点击（`_aboutRow` 新增
`VoidCallback? onTap` 参数，非空时套 `_Pressable`）。

### 2) settings_page 开关：从「点了没反应也说已保存」到「按真实结果弹提示」

`_pushToggleToBackend` 之前不管后端有没有收到都返回 `true`，
SnackBar 一律「设置已保存」。分类修复：

- **本机偏好**（animations / sound / splash / autoUpdate / crash /
  telemetry / effects_enabled）：这些是 UI 本地设置，后端 proto 里
  根本没有对应字段，`_ALLOWED_PATHS` 也不允许 `ui.animations`。
  **本机 `_persistChannels()` 落盘才是真来源，不再推后端**。
  之前误加了 `ui.*` 白名单和 bool 强制转换（`options.py`）——
  **该改动已回滚**，因为它本身就是在给不存在的字段造假通路。
- **后端字段**（alwaysOnTop / autoStart / asr / tts / readAloud）：
  push 后必须**回读** `settings()` 验证。任一环节失败返回 `false`，
  SnackBar 如实说「已改本机设置，后端未确认（可能离线）」。
- **未知 key**：如实返回 `false`。

撤销按钮同样会重新 push，保持状态一致。

### 3) plugins_page 八个假按钮全部接真后端

`_showInstallDialog / _showConfigDialog / _showInfoDialog /
_showDocDialog` 里的 `_dialogRow(..., () => Navigator.pop(context))`
八个假动作全部改成真动作：

- 从本地路径导入 → `_promptInstall(localPath: true)`：弹输入框，
  走 `plugin:installpath <路径>`
- 从 URL 安装 → `_promptInstall()`：走 `plugin:install <url>`（真下载）
- 打开插件目录 → `_showPluginDir()`：拿 `plugin:dir` 返回的绝对路径
  复制到剪贴板（Flutter 无原生文件管理器 API，不新增依赖就不假装）
- 重启插件 → `_pluginAction(plugin, 'reload', ...)`
- 卸载插件 → `_pluginAction(plugin, 'uninstall', ..., destructive: true)`
  带二次确认，卸载后端会移入隔离区不真删（红线：绝不删除）
- 查看源码 → `_showPluginDir()`
- 反馈问题 / 完整 API 文档 → `_openExternal(_pluginRepoUrl)`

新增 `_runPluginCmd / _feedback / _promptInstall / _pluginAction /
_showPluginDir / _openExternal`。`_showConfigDialog` 里那个假的
「自定义参数」输入框（值从来不发后端、后端也没地方落库）已换成如实
说明文字：**参数由 plugin.json / manifest.json 定义，改完点重启**。

### 4) workflow_builder：本机保存 → 同步后端 + 反馈

`_saveWorkflow` 拆成两半：本机 `_persistSaved()` 立即成功，然后
`unawaited(_pushSaveToBackend(name))` 走 `workflow:save <json>`。
异步回来后弹「已同步到后端」或「后端未确认（仅本机保存）」，不
假装后端确认过。

## 测试

`tests/test_fakes_to_real.py` 从 23 例扩到 41 例，覆盖：

- **R9** system_prompt provider：
  - `test_local_model_build_messages_prefers_provider`：provider 提供时
    静态串绝不出现
  - `test_local_model_falls_back_to_static_when_no_provider`
  - `test_local_model_provider_exception_does_not_break_build`
  - `test_model_replacement_threads_provider_into_local_model`：
    `get_model` 源码必须包含 `system_prompt_provider=self.system_prompt_provider`
  - `test_engine_system_prompt_reflects_persona`：模拟 persona 变化，
    断言下一轮 build_messages 立即反映
- **R10** GrowthEngine 单例：
  - `test_get_growth_engine_prefers_engine_growth`
  - `test_get_growth_engine_singleton_when_engine_absent`
  - `test_get_status_rpcs_use_singleton` / `test_no_fresh_growth_engine_in_status_rpcs`
    源码级护栏
- **R11** sensitive: 指令族：list / check / add / 引擎不可用如实报错 /
  路由元组必须包含 `'sensitive:'` / `_do_chat` + `_do_chat_streaming`
  两条链路都必须调 `_compliance_mask`
- **R12** plugin: reload / installpath / dir 三条新指令，成功与失败都如实上报

**结果**：`456 passed, 1 skipped`；`dart format --output=none` 三个前端文件通过。

## 明确留下的「已知假」

以下位置**本轮没有假装修好**，仍在 KNOWN-ISSUES 里：

- 子代理面板 / agent 创建器 / workflow 编辑器的 CRUD 是纯本机数据，
  后端没有对应的 agent CRUD RPC（有 `agent:edit / agent:task / agent:terminal`
  这三个动作族，但没有「列出/新建/删除已注册的 agent」这套接口）。
  前端 UI 也没有说这些是「同步到后端」——它写的是「已保存」，本机持久化就是
  它真正的语义。**这一项按诚实降级保留，不加假的后端字段。**
- 后端剩下的「疑似零调用」组件：`SessionManager`、`chat_async` /
  `chat_stream_cb` / `context_for_prompt`、`UpdateChecker`、`OfflineGuard`、
  `EventBus`。它们中的多数**类实现是完整的**、只是没被接到 RPC 表面；
  接线是「扩展 API 面」而不是「修复假按钮」，规模与产品决策不匹配
  本轮范围，留给下一轮。

---

## 追加修复（同批的补充审计，一次提交）

第四批提交后再扫前端审计报告，还有 3 处属于「按钮在、行为假」的残余，
一并接进真链路：

- **M3 · `_channels` 8 条旧 fallback**：第三批接线后 `_setChannel` 早已
  不再写这个 Map，只有 `_restoreLocal` 从旧 `channels.json` 读进来。
  它变成「几周前的一次快照」的假记忆——用户离线时看到某通道亮着，实际
  后端可能早就关了。删掉本地 Map 与 `channels.json` 里的 `channels` 字段
  读写，唯一真值改为后端 `channels:list`；拿不到时 UI 明确显示
  「未获取（后端未连接）」而不是显示一个假 `false`。
- **`_setChannel` 假成功**：此前失败只 `debugPrint`，UI 完全没提示；
  用户看着开关翻转又自动弹回来，什么都不知道。现改为解析后端 JSON
  `{ok,error}`，失败时 SnackBar 明确告知失败原因并说明「开关已回滚到
  后端真实状态」，与本轮其它「点了没反应也要说」的修同一手法。
- **U3 · `model_remote_panel` 静默吞轮询异常**：`_refreshProgress` 的
  `catch (_) {}` 完全静默。后端 `sandbox:status` 一旦永久不可用，UI 会停在
  「最后一次已知状态」的进度条上**假装还在下载**。加连续失败计数
  `_syncFails`，越过阈值（3 次）就在进度行如实标「同步中断（后端已无响应，
  进度停留在最后一次已知状态）」并停止轮询；新一轮下载重置计数。

**没有动的（核对后判定不是假）**：
- `security_panel` 上 `_tools` 硬编码初始 `allowed: false`：后端 `security:config`
  返回的 key 与前端 `_tools` 名称一致（`file_read/file_write/terminal/network/
  browser/git/mcp`），加载期间也有 skeleton，不构成假数据。
- `plugin_community.dart:74` / `training_page.dart:3653` /
  `notif_panel.dart:121` / `persona_panel.dart:168/642` 里的 `onTap`
  分别是「返回按钮」和「面板内层吞掉点击、避免命中外层 scrim 关闭」的
  Flutter 惯用法，不是假动作。

