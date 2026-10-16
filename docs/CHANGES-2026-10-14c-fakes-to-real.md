# 变更记录（第三批）：把"宣称有、其实没接线"的功能改成真的

日期：2026-10-14
提交前审计来源：子代理全仓交叉审计，确认 9 条、其中 5 条高危。
原则重申：**降级要明说，绝不假装**。本轮只动必要文件，不新增第三方依赖，
不改 `.proto`，新指令族一律走 `ExecuteCommand` + JSON。

## 1. 多通道"启动了其实在假死"——根因：asyncio.run 把循环关了

- **原先假装的是什么**：界面点「启动通道」返回成功，`channels:list` 里
  `running:true`，但 aiohttp 的 Webhook/公众号 HTTP 接收服务器实际从没在监听。
- **真根因**：RPC `_handle_channels_cmd` 用 `asyncio.run(mgr.start_all())`。
  `asyncio.run` 一返回就关闭并销毁事件循环，`AppRunner`/`TCPSite` 随循环一起死。
- **改法**：`ChannelManager` 持一个**常驻事件循环线程**（`channels-loop`, daemon），
  生命周期用 `start_enabled()/stop_running()/restart_channels()` 同步包装，内部
  `asyncio.run_coroutine_threadsafe`。RPC 层不再直接 `_aio.run(...)`。
  `start_all` 增加"已运行则跳过"守卫，避免 `set on` 时重复启动。
- **附带修掉的同批假象**：
  - 配置快照 vs 现读：`_channel_config` 改为每次从 `core.config.load()` 现读
    （此前 `channels:set` 写盘后管理器仍读构造时快照，"开关点了没反应"，
    与 security_center 双实例同一类病）。
  - `_reply` 元组契约：`engine.chat()` 返回 `(text, err)`，此前 `str(out)`
    把回复损坏成 `"('text', None)"`。现取 `out[0]`，兼容纯字符串与异常。
  - Webhook `_handle` 无 handler 时返回 `"OK"` 且不回引擎 —— 现回落到 `_reply`。
  - `_reconnect_channel` 曾把协程函数交给 `threading.Thread(target=...)` 却从不
    await，等于永远不重连 —— 现走 `_submit` 到常驻循环。
  - `channels:_SPEC` 里 dingtalk 凭据键写成 `dingtalk_webhook_url`，通道实际读
    `dingtalk_access_token`，导致"已配置"判定永远假 —— 改正键名。

## 2. 工作流 LLM 节点输出损坏（同一类元组病）

`workflow_engine._execute_node` 的 `llm` 分支 `str(self.engine.chat(...))`
同样把 `(text, err)` 打成 `"('text', None)"`。改为取 `result[0]`，兼容字符串/空值。

## 3. DSHCompat 死代码 → `dsh:` 指令族

`core/dsh_compat.py`（解析/安装/卸载/列表/GitHub 实时市场 + 精选兜底）此前**零调用方**，
"兼容 DSH 生态"只是文件里的一段代码。新增 `dsh:list|available|market|parse|install|uninstall`
RPC 分支与进程级单例 `_get_dsh_compat()`，并接入 ExecuteCommand 路由元组。
市场离线时如实降级到 curated 列表并标注 `source:"curated"`，不伪装成实时数据。

## 4. GitTool 死代码 → `git:` 指令族

`core/git_tool.py`（status/diff/commit/branches/checkout/log）此前**零调用方**。
新增 `git:status|diff|commit|branches|checkout|log` RPC 分支与单例 `_get_git_tool()`，
默认锁定沙箱 workspace，所有 git 命令仍过 `exec_gate` 权限闸门。接入路由元组。

## 5. BrowserTool.search 把网络故障伪装成"零结果"

- **原先假装的是什么**：`search()` 任何异常都 `return []`，调用方（工具/前端）
  只能显示"未找到结果"，与真正的"搜索成功但无命中"无法区分。
- **改法**：异常时返回 `[{"error": "..."}]`；正常零命中仍返回 `[]`。
  `browser:` RPC 新增 `search` op：读到 error 标记就 `ok:false` + 原因，如实上报。
- `tools.py` 的 `web_search` 空结果提示改为如实说明"联网检索与本地知识库均无命中，
  可能是离线"，不再单说"未找到"。

## 6. PluginManager 多实例 → 单一真相源

`_handle_ext_command` 的 `plugin:` 分支此前每次 `PluginManager()` 新建一份，而
`ListPlugins`/`EnablePlugin` 走引擎内 `engine.plugins`，两条路径各持内存，enable
后 market 可能看不见、钩子也不会注册到正在跑的引擎。新增 `_get_plugin_manager()`：
优先返回引擎内那一份，引擎不可用才退化为进程级单例；`plugin:` 分支、`ListPlugins`、
`_plugin_manager()` 全部同源。

## 测试

新增 `tests/test_fakes_to_real.py`（23 例）覆盖上述六类：元组契约、常驻循环
start/stop/reconnect、live-config、workflow LLM、dsh:/git: RPC 接线、路由元组、
browser search 错误标记、dingtalk 键名、plugin 单例。
全量：`pytest tests -q` → **438 passed, 1 skipped**（基线 415 + 本轮 23）。

## 仍待办（如实说明，非本轮范围）

- 通道端到端真机验证（Telegram/Discord/钉钉等真实凭据 + 收发一轮）；沙箱无外网。
- 极度简化（去注释、.md 收敛为一份、裁剪未引用文件）此前被显式推迟，未动。
- DSH 市场的 curated 列表是人工静态数据，已在字段里如实标注来源。
