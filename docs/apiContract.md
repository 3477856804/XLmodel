# 接口契约

> 三套对外契约：成长引擎的调用面（ExecuteCommand 指令族）/ 成长引擎 Python API /
> 渲染资源层 API。
> 机器可读版本见 [`apiContract.csv`](apiContract.csv) 与 [`openapi.yaml`](openapi.yaml)。
>
> **重要修订（本轮去伪存真）**：本文件此前写的 `python -m core.growth <cmd>`
> 命令行**从来不存在** —— `core/growth.py` 里没有 `__main__` 块，CLI 化的是
> `python main.py --selftest` 这类进程入口。成长引擎真正对外的调用面是
> gRPC `ExecuteCommand` 里的 `growth:` / `training:` / `model:` 指令族，
> 下面按实际代码重写。`.proto` 已冻结，扩展一律走 ExecuteCommand + JSON。

## 一、ExecuteCommand 指令族（前端唯一可用的成长接口）

调用方式：`ExecuteCommand(command="growth:distill")` → `CommandReply.output`
是 JSON 字符串。加字段不用重新生成 Dart/Python 桩代码。

| 指令 | 作用 | 关键返回 |
|---|---|---|
| `growth:persona` | 人格快照：情绪+来源、亲密度与档位，外加前端算不出的档位序号 | 快照本体 + `level_index` / `level_total` / `is_max` / `ok` |
| `growth:timeline [days]` | 按天的真实活动时间线（默认 30，上限 366） | `{ok, days, activity[], first_date}` |
| `growth:daily` | 今日目标进度 | `{ok, date, completed, goal, percent, achieved}` |
| `growth:goal <n>` | 设置每日互动目标并回显进度 | `{ok, date, completed, goal, percent, achieved}` |
| `growth:first` | 第一条成长记录日期与一起走过的天数 | `{ok, first_date, days_together}` |
| `growth:report` | 今日成长摘要（含真实经验里程碑） | `{ok, date, interactions_today, exp_earned, rounds, promotions, progress_percent, milestone, daily_goal}` |
| `growth:promotecheck` | 晋升门槛实况：够不够格、会不会被验收拦住（**只读，不写 journal**） | `{ok, paused, base_bytes, adapter_bytes, progress_percent, size_gate_met, cap{}, acceptance{}, will_run_acceptance, generation}` |
| `growth:promote [强制]` | 手动走一次合并晋升（含生成式验收）。耗时，走后台任务 | `{ok, task_id, poll, poll_result}` |
| `growth:distill` | **只读**：老师端配没配、队列积压、今日配额与费用 | `{ok, teacher{}, enabled, batch_limit, queue{}, samples_with_teacher, records_total, quota{}, note/usage}` |
| `growth:distill run [n]` | 真的去问老师（联网，走后台任务） | `{ok, task_id, poll, poll_result}` |
| `growth:distill on\|off` | 蒸馏开关（写 `growth.distill_enabled`） | `{ok, written, enabled, note}` |
| `growth:distill limit <n>` | 每轮上限（1..200，写 `growth.distill_batch_limit`） | `{ok, written, limit}` |
| `growth:status` | 成长引擎真值快照（**只读**，等价 `GrowthEngine.status()`，刷新页面不写流水） | `{ok, paused, stage, base_bytes, adapter_bytes, progress_percent, rounds, promotions, corpus_items, rank, rank_max, can_train_now, train_blockers[], config{}, last_train_at}` |
| `growth:pause [原因]` | 暂停自动成长（写状态 + 记 journal）；`should_train / train_round / check_and_promote` 三处真读 | `{ok, paused, reason, already_paused, note}` |
| `growth:resume` | 恢复自动成长，并回显「现在能不能练」 | `{ok, paused, can_train_now, train_blockers[], note}` |
| `growth:rollback` | **只读**：列出回收区可回滚代数与是否存在 | `{ok, readonly, active_gen, can_rollback, trash[], usage, note}` |
| `growth:rollback <代>` | 演练预览（`dry_run`，不搬目录不改 registry）；预览失败不带 `dry_run` | `{ok, dry_run, from_gen, target_gen, readonly, next}` |
| `growth:rollback <代> confirm` | 真的回滚（会移动模型目录，走后台任务） | `{ok, task_id, poll, poll_result}` |
| `growth:gc [保留数]` | **演练**：列出可清理旧代与释放量；刻意绕开 `GrowthEngine.gc()`，因为它无条件写 journal | `{ok, readonly, dry_run, keep_generations, trash_generations, keepers[], deletable[], freed_bytes, freed_human, stability{}, allowed, message}` |
| `growth:gc run [force]` | 真删除（后台任务；`force` 跳过稳定期约束），结果按真值补 `ok = allowed` | `{ok, task_id, poll, poll_result}` |
| `growth:purge <范围>` | 范围限 `all/trained/disliked/dpo`；**只数条数**，不执行任何 DELETE | `{ok, readonly, scope, would_remove, stats{}, warning}` |
| `growth:purge <范围> confirm` | 真删样本（不可撤销，后台任务） | `{ok, task_id, poll, poll_result}` |
| `training:checkpoint [<步数> [auto\|always\|off] [保留数]]` | 断点续训开关，读写 `config.growth`；裸调用只回显当前值与用法 | `{ok, interval, mode, keep, written?, note?}` |
| `agent:task status <id>` / `agent:task result <id>` | 轮询上面这些后台任务 | 任务状态 / 任务结果 JSON |

### `model:` 族（模型商店的真实后端）

`.proto` 冻结，全部走 JSON。历史上商店只有内置 11 条 `MODEL_PRESETS`，
搜索框是前端本地字符串过滤 —— 看着像商店，其实是固定清单。下面的
`search` / `files` / `recommend` / `downloadremote` 才是真接魔搭的部分。

| 指令 | 作用 | 关键返回 |
|---|---|---|
| `model:active` | 当前活动模型（唯一真源，磁盘事实） | `{ok, available, name, text, action}` |
| `model:list` | 已安装清单（商店 + 本地登记） | `{ok, models[]}` |
| `model:use <名>` | 切换当前模型（严格匹配，不静默换错） | `{ok, message}` |
| `model:answer` | 「我是什么模型」的标准话术 | 纯文本回答 |
| `model:search <词> [页]` | **真连魔搭**搜索（`/openapi/v1/models?search=`） | `{ok, query, page, page_size, total, source, models[], error}` |
| `model:files <ns/name>` | 列远端仓库文件与 `.gguf` 清单 | `{ok, repo, files[], gguf[], error}` |
| `model:recommend` | 按本机硬件算适配/推荐（真调 `fit_models_for_hardware`） | `{ok, tier, available, why, models[], detected{}}` |
| `model:downloadremote <ns/name> [量化档]` | 后台下载远端 GGUF（复用同一套断点续传实现） | `{ok, task_id, poll, poll_result, repo, quant}` |

诚实约定：
- `search` / `files` 失败一律 `ok:false` + `error`，**不返回空列表冒充「没找到」**；
  空关键词直接拒绝，不会回全量清单。
- `recommend` 探测不到 RAM 时 `available:false`，`why` 写明原因，
  并且**强制把所有 `recommended` 置 false**（不给假推荐）。
- `downloadremote` 的仓库名必须形如 `namespace/name`，含 `..` / 反斜杠 /
  盘符一律拒绝 —— 它要拼进 URL，必须防注入防穿越。
- 下载进度真源是 `sandbox:status` 的 `progress.<repo>`（后端 `model.TASKS` 表），
  取消走 `agent:task cancel <task_id>`（协作式取消，`.part` 保留可续传）。

### `api:` 族（统一外部 API 配置——设置页「API 配置」选项卡的后端）

历史上外部 API 配置散成互不相通的两套（`training.api_*` 与 `deepseek_*`），
在任一处「配了等于没配」。现在收敛为统一存储 `config.api.{enabled,base,key,model,provider}`，
由 `core/api_config.py` 读写（纯标准库 urllib），四个消费方共享：
设置页、训练/蒸馏（`trainer.api_cfg` 在 `training.api_*` 未配时回落到这里，
`source:"unified"`）、Agent 思考（启用时外部 API 优先于本地引擎）、语音识别
（whisper 未装但 API 已配时走云端 `/audio/transcriptions`）。

| 指令 | 作用 | 关键返回 |
|---|---|---|
| `api:cfg` | 读当前配置（**key 永远打码**，明文不回流前端） | `{ok, enabled, base, has_base, key_masked, has_key, model, provider, providers[], configured, source, usage}` |
| `api:set enabled on\|off` | 总开关 | 写入后的打码快照 |
| `api:set base <url>` | 端点（必须 http/https，否则拒绝） | 同上 |
| `api:set key <密钥>` | 密钥（**空串=清除**） | 同上 |
| `api:set model <名字>` | 默认模型名 | 同上 |
| `api:set provider <名>` | 供应商标签（白名单 openai/deepseek/dashscope/moonshot/zhipu/custom） | 同上 |
| `api:test` | 对配置端点发真实最小请求验证连通性 | `{ok, ...}` 或 `{ok:false, error}` |
| `api:chat <messagesJson>` | 直接走外部 `/chat/completions`（Agent/蒸馏复用同一入口）；接受 `[{"role","content"},...]` 或裸字符串（自动包成 user） | `{ok, text, model, elapsed_ms}` 或 `{ok:false, error, disabled?}` |

诚实约定：
- 未启用（`enabled=false`）时 `chat()` 直接 `{ok:false, disabled:true}` 并明说
  「调用方自动降级本地模型」——**不会假装在用 API**；
- `/audio/transcriptions` 端点返回空文本时如实 `ok:false`「端点返回空识别结果」。

### `system:` 族

| 指令 | 作用 | 关键返回 |
|---|---|---|
| `system:stats` | CPU/内存/磁盘真实采样 | `{available, cpu_percent, mem_percent, ...}` |
| `system:health` / `system:selftest` | 体检 | 各项真实结果 |
| `system:ports` | **3D 查看器与 gRPC 的真实监听端口** | `{ok, grpc, web, web_host, web_error?}` |

`system:ports` 存在的理由：前端原先盲扫 8765~8785 猜查看器端口。后端端口被占
会顺延，一旦顺延出扫描窗口就永远找不到（表现正是「3D 角色加载不出来」）；
更糟的是同号端口可能属于别的软件，扫过去会渲染出莫名其妙的页面。
gRPC 这条连接本身已经建立，所以由后端报真值是可靠的。

### `channels:` 族（多通道真实启停）

`core/channels.py` 的 11 个通道类此前从未被真正启动：RPC 用 `asyncio.run(start_all())`，
返回即销毁事件循环，aiohttp 接收服务器随之而死。现在生命周期跑在管理器的**常驻循环线程**上。

| 指令 | 作用 |
|---|---|
| `channels:list` | 每通道 `{enabled, configured, running, missing_credentials}`（现读磁盘配置） |
| `channels:set <名> on\|off` | 写配置并同步启停（`set on` 走 `start_enabled`，`set off` 走 `restart_channels`） |
| `channels:start` / `stop` / `restart` | 在常驻循环上启停全部/重启 |

诚实约定：dingtalk「已配置」判定用通道实际读取的 `dingtalk_access_token`；
`engine.chat()` 的 `(text, err)` 元组契约在 `_reply` 里正确取文本，绝不回 `"('text', None)"`。

### `dsh:` / `git:` 族（原死代码，现接入路由）

| 指令 | 作用 |
|---|---|
| `dsh:list` / `dsh:available` / `dsh:market` | 已装 / 可装 DSH 插件（离线如实降级到 curated，标 `source`） |
| `dsh:parse <路径>` / `dsh:install <来源>` / `dsh:uninstall <名>` | 解析 / 安装 / 卸载（安装走 `exec_gate` full 权限） |
| `git:status` / `diff` / `commit <msg>` / `branches` / `checkout <分支>` / `log [n]` | 仓库操作，默认锁定沙箱 workspace，全部过 `exec_gate` |

### `browser:search <json>`

`tool.search` 契约：网络/解析异常返回 `[{"error": ...}]`，正常零命中返回 `[]`。
RPC 读到 error 标记即 `ok:false + error`，不再把故障伪装成「未找到结果」。

### `plugin:` 族（插件全生命周期，第四批补齐）

| 指令 | 作用 |
|---|---|
| `plugin:list` / `plugin:market` / `plugin:state` | 已装 / 市场 / 启用状态快照（均走 `_get_plugin_manager()` 单一真相源） |
| `plugin:enable <名>` / `plugin:disable <名>` | 开/关，未找到插件如实 `_err` |
| `plugin:install <url或名>` | http/https 地址 → 真实下载安装；否则社区占位创建（默认关闭） |
| `plugin:installpath <绝对路径>` | 只接 `.zip` 或已存在目录；其他类型/不存在一律 `_err`（不假装成功） |
| `plugin:create <json>` | `{name,description,category,code,author}` 自定义插件 |
| `plugin:uninstall <名>` | 移入隔离区（**不真删**，红线） |
| `plugin:reload [名]` | 有名 → 热重载单件（`reload_plugin`，失败 `_err`）；无名 → 整体重载返回 `count` |
| `plugin:dir` | 返回 `plugins_dir` 真实绝对路径，前端复制到剪贴板（Flutter 无原生文件管理器 API） |

### `sensitive:` 族（内容合规过滤器，第四批从死配置接进链路）

| 指令 | 作用 |
|---|---|
| `sensitive:list` | 当前内置敏感词表；引擎未就绪时 `_err`，**不给空 list 骗人** |
| `sensitive:check <文本>` | 返回 `{hit, words, masked}` |
| `sensitive:add <词>` | 追加词 |

`_compliance_mask(reply)` 已接到 `engine._do_chat` 与 `_do_chat_streaming` 的
`_post_chat` 之前：返回前端、写进 conversation、进记忆库与成长样本的都是打码后文本。
诚实边界：流式已实时推给前端的 token 无法收回，本步只保证「落库/回流」干净。
过滤器异常时原样返回，绝不吞回复。


`training:` 族其余子命令（详见 `rpc/server.py::_handle_training_cmd` 文档串）：
`status` / `env` / `adapter` / `history` / `cancel` / `live` / `mergestatus` /
`export` / `gguf` / `probe` / `acceptance`。其中 `export`、`gguf`、`probe` 是长任务，
同样返回 `task_id`。

约定：长耗时操作**不阻塞**对话线程，立刻返回 `task_id` 与两条轮询指令；
只读指令不发网络、不写文件、不记 journal。

### gRPC 一元 RPC 的真实行为（`.proto` 冻结，只改实现不改契约）

- **`SwitchModel(path)`**：同时写 `model.path`（渲染器读）与 `avatar.model`
  （`ListModels` 按 basename 排默认形象时读）。此前只写 `model.path`，而全链路没有
  任何地方按它选 3D 形象 ——「切换成功」只是回包假象，重启必回默认形象。
  回归点：切形象 → 重启 → `bootstrap.models` 第一条应为用户刚选的那个。
- **沙箱执行返回体的 `shell` 字段**（`core.sandbox.run` → `exec_gate` 透传）：
  Windows 找到 Git Bash → `'bash'`（命令经 `bash.exe -c`，shell=False，`ls`/管道可用）；
  Windows 没找到 bash → `'cmd'`（如实降级，POSIX 命令本就不可用，**不伪装**）；
  POSIX → `'sh'`。前端/调用方据此判断「命令跑在什么 shell 里」，
  失败时不再靠猜。

## 二、成长引擎 Python API（`core.growth.GrowthEngine`）

```python
from core.growth import GrowthEngine
eng = GrowthEngine()                            # dry_run=True 可无 torch 演练
eng.status(); eng.report(); eng.samples_report()
eng.should_train(manual=False, force=False)     # → {ok, reasons[], details{}}
eng.train_round(epochs, batch_size, lr, corpus, min_quality)   # 训练前自动蒸馏
eng.after_training_round(manual=False, force=False)  # 触发校验 → 训练 → 自动检查
eng.check_and_promote(force=False)              # → action ∈ promoted/grow/skip/blocked/promote_failed
eng.merge_and_promote(retire_mode=None, keep_backup=False)
eng.pause(reason=""); eng.resume(); eng.bump_dialogue(n=1)
eng.rollback(gen=None); eng.gc(keep=None, force=False); eng.export(dest)
eng.store.purge(scope)             # all / trained / disliked / dpo
eng.register_for_distill(record_id, prompt)     # 对话路径：只写本地队列
eng.distill_round(limit=None, max_attempts=3, time_budget=None)  # 真正联网问老师
eng.journal(event, **fields); eng.recent_journal(limit=20)
eng.grow_rank(new_rank=None)   # 有实现、无调用方；只改配置不重排权重

eng.store       # core.growth.GrowthStore（SQLite 数据仓库 + 蒸馏队列）
eng.throttle    # core.growth.DistillThrottle（缓存/限流/成本）
eng.teacher     # core.growth.TeacherClient（OpenAI 兼容文本请求）
eng.lifecycle   # core.growth.ModelLifecycle（退役/GC/回滚/导出）
eng.rank        # core.growth.RankManager（读写 adapter_config.json 的 r）
eng.trainer     # core.trainer.LoRATrainer（真训练内核）
```

注意：`GrowthStore` / `DistillThrottle` / `ModelLifecycle` / `RankManager`
全都在 `core/growth.py` 里，**不存在** `core/growth_store.py`、`core/throttle.py`、
`core/lifecycle.py`、`core/rank.py`、`core/eval.py`、`core/device.py`、
`core/peft_train.py`、`core/rag.py`、`core/selftest.py` 这些模块。
`eng.evaluate()` 与 `eng.simulate()` 也不存在（旧文档里的这两条已删）。

## 三、渲染资源层 API（`backend/renderer/stage.py`）

画面由 Flutter 端绘制（`flutter_inappwebview`：Windows WebView2 / macOS WKWebView），
后端这一层只管**资源与状态**，没有 `render_frame()`：

| 方法 | 说明 |
|---|---|
| `Renderer()` / `get_renderer()` | 门面，包装 `Stage`，与 `server._get_renderer()` 契约一致 |
| `Stage.list_models()` / `describe_model(path)` | VRM/glTF 解析，给出骨骼/材质/表情元信息 |
| `Stage.switch_model(path)` / `model_path()` | 切换当前模型并落配置供前端读 |
| `Stage.list_actions()` / `play_action(path)` / `get_animation_list()` | `*.vrma`/`.bvh`/`.fbx` 动作库 |
| `Stage.set_mouth_open(level)` / `blink()` / `set_eye_target(x, y)` | 写状态供前端取，不是后端出图 |
| `Stage.state()` | 当前模型/动作/表情的完整快照 |

离线出图工具在 `scripts/vrm_preview.py`（软件光栅，校验形象用），
它不在运行时链路上，别当成交互渲染器。

### 形象文件的真实来源

`resources/web/viewer.html` 默认加载 `./models/小凌.vrm`，由
`backend/core/webpanel.py` 的 `/models/<名>` 路由吐出。**这个文件必须真的在
版本库里** —— 之前 `.gitignore` 写的是整目录排除 `resources/models/`，
导致任何 `!` 例外规则永远不生效，形象资源从来没进过版本库，
这才是「3D 人物模型加载不出来」的第一根因（不是渲染代码的问题）。

现在仓库带的是用自有管线生成的形象（见 `resources/models/README.md`）：
`scripts/xiaoling_avatar.py build --base <vrm> --face resources/materials/xiaoling.png`。

查看器静态服务必须满足（回归测试：`tests/test_webpanel_static.py`）：

| 行为 | 约定 |
|---|---|
| `GET /models/<名>` | `Content-Type: model/gltf-binary`，字节与磁盘文件完全一致 |
| `Range: bytes=a-b` | 回 `206` + 正确 `Content-Range`，数据段精确对齐（可续传前提） |
| `bytes=-n` / `bytes=a-` | 后缀范围与开区间都要支持 |
| 越界范围 | `416` + `Content-Range: bytes */<size>` |
| 多段范围 | 不实现 multipart → 如实回 `200` 整文件，**绝不伪装成 206** |
| `HEAD` | 必须实现（只回头不回头体）。原先没有 `do_HEAD` → 501，前端把服务判成不可用 |
| 路径穿越 | `../` / 绝对路径 / 盘符一律 404 |

## 四、错误与降级约定

| 场景 | 约定 |
|---|---|
| 缺 torch/peft | 训练/合并返回 `ok:false` 并给出安装提示；生成式验收返回不可用原因，**不算通过** |
| 无 GPU | `train_plan(best_device())` 给 CPU 档参数（batch 1 / grad_accum 8 / 不量化）；量化仅在显式配 int4/int8 且装了 bitsandbytes 时生效，否则记 `quant_fallback` |
| 老师端未配置 | `teacher_config()` 判缺哪一项，对话照常入库但不入队，蒸馏一条请求都不发并直说原因 |
| 外网失败/超时 | 计入 `failed`，超过 `max_attempts` 记 `gave_up`；时间预算用完明说还剩多少条 |
| 合并失败 | 校验不通过即回滚，原基底保持完好；临时产物隔离，不冒充成功 |
| 检查点丢失 | `resume_denied` 拒绝本轮训练，而不是从头跑再谎报进度 |
| 用户暂停 | 所有自动训练/晋升入口跳过并记 journal，`force` 也必须显式传 |
| gRPC 端口被占 | `add_insecure_port()` 抛 `RuntimeError`（实测 grpc 1.84 不返回 0）。`serve()` 捕获后记录 `grpc:0` + 错误、打印换端口/清旧进程的处置提示并**重新抛出**；`main.py` 等真实绑定结果（`threading.Event`）才打印「已启动」，失败就打印失败 |
| 查看器端口全被占 | `webpanel` 顺延 20 个仍失败 → `_record_state(0, host, 原因)`，`system:ports` 如实回 `web:0` + `web_error`，前端据此判定「没在跑」而不是继续盲扫 |
| 沙箱无 OS 级路径隔离 | Linux 内核 < 5.13（无 Landlock）时**降级路径就是默认路径**。此时启用 `lexical_escape_check` 词法守卫，返回体带 `guard:'lexical'`，`capability()` 里 `path_isolation` 仍然 `False`、只新增 `lexical_guard:True`。**它不是安全边界**：只镜像 Landlock 的放行面（系统目录只读、workspace/tmp 可写），所以 `cat /etc/passwd` 这类读系统文件是刻意放行的，挡不住编码/拼接/解释器内联脚本绕过 |

