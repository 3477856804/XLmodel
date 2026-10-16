# 功能映射：设计文档 → 代码实现

> 本表按**代码事实**逐条核对过，核对方式写在括号里。上一版把 12 个不存在的
> 模块（`core/growth_store.py`、`core/eval.py`、`core/rank.py`、`core/lifecycle.py`、
> `core/device.py`、`core/peft_train.py`、`core/rag.py`、`core/selftest.py`、
> `core/throttle.py`、`pet.py`、`renderer/dashboard.py`、`renderer/renderer.py`）
> 当成「完成」列了出来，这次全部改成真实位置，并把实现不到位的降级。
>
> 设计文档 v1.0 本身不在仓库里（`docs/` 只有本映射表与 `growthPipeline.md`），
> 条目编号沿用旧写法，便于对照，但**结论只按当前代码给**。

| 设计文档条目 | 实现位置 | 状态 |
|---|---|---|
| 原则 1 记忆与训练分层 | `core/memory.py`（即时/稳定记忆，JSON + 向量 sidecar）+ `core/growth.py`（训练数据仓库） | 完成 |
| 原则 2 删除改为退役 | `core/growth.py::ModelLifecycle`（trash 退役 + 稳定期 + 回滚）；文件真删只发生在 `gc()` 且过了稳定期 | 完成 |
| 原则 3 晋升看三条件 | `core/growth.py::check_and_promote()`（A 体积 + cap_check 磁盘上限）+ `_acceptance_gate()`→`core/eval_probe.py`（生成式验收，默认关） | **部分完成**：B「验证集 loss」只做事件上报、不参与判定；C「常识 20/通用 20/安全 10」共 50 道题从未实现，已按真实的两条门槛改写 |
| 原则 4 训练不阻塞桌宠 | `ExecuteCommand` 长任务走 `core/background_tasks.py`（`growth:promote` / `growth:distill run` / `training:export` 等，立即返回 task_id）；`StartTraining` 是 gRPC 服务端流，前端 streaming 读进度 | **部分完成**：后台任务表确实存在，但聊天里说「训练一下」走的是 `engine._route_train → after_training_round → train_round` 的**同步**路径，因此蒸馏必须带时间预算（`distill_time_budget_sec`），否则老师端一挂小凌就不回话 |
| 2.1 三层结构（即时/稳定/人格） | `core/memory.py` + LoRA 训练 + `merge_and_promote()` | 完成 |
| 2.2 四路训练数据来源 | `core/growth.py::GrowthStore`（对话 / 反馈纠正 / 老师蒸馏 `deepseek_output` / `import_jsonl`） | 完成 |
| 2.3 训练触发策略 | `GrowthEngine.should_train()`（样本、间隔、设备空闲、电量温度、未暂停；`force` 显式跳过） | 完成 |
| 2.4 灾难性遗忘防护 | `GrowthStore.write_corpus(base_mix_ratio=0.15)` 混入通用语料 + `_round_corpus()` | 完成 |
| 2.5 晋升条件 | `check_and_promote()` + `lifecycle.cap_check()` + `_acceptance_gate()` | 完成（同上，条件口径已修正） |
| 3.1 记录结构 | `core/growth.py::_SCHEMA` / `GrowthStore._COLS`（字段名与设计一致，另加 `distill_queue`） | 完成 |
| 3.2 存储分工 | SQLite（records / dpo_pairs / distill_queue / rounds / kv）+ 哈希向量 + 按月归档 JSONL | 完成 |
| 3.3 数据使用规则 | `sample_for_training()` 质量分排序、点踩生成 DPO、`prompt_hash`/向量去重、`mark_trained` 轮次标记 | 完成 |
| 3.4 DeepSeek 蒸馏节流 | `core/growth.py::TeacherClient` + `DistillThrottle`（hash 缓存 / 每日限流 / 开关 / 费用估算）**且真的被调用**：`distill_round()` 每条先过 `gate()` | 完成（此前三个节流方法零调用方，报表照打「蒸馏 API：开」；现已接通，见 `tests/test_distill.py`） |
| 3.5 隐私与用户控制 | 本地存储 + `GrowthStore.purge(scope)`（RPC `growth:purge <范围> [confirm]`）+ `export_jsonl/import_jsonl(encrypt_key)` + `list_records()` 逐条可查；API Key 只回显 `key_tail`，不外传明文 | 完成 |
| 4.1 退役流程 | `ModelLifecycle.retire()` + `stability()` + `rollback()` | 完成 |
| 4.2 磁盘策略 | `gc(keep=...)` + `keep_generations` / `max_generations` / `max_total_bytes` | 完成 |
| 4.3 目录结构 | `.star_core/{XLmodel,adapter,trash,adapter_seeds,growth}`（`config.py` 启动时创建） | 完成 |
| 5.x 成长仪表盘 | `frontend/lib/pages/growth_page.dart` / `dashboard_page.dart` + 后端 `growth:persona/timeline/daily/report` 真值接口 + `status()/samples_report()` | 完成（旧版写的 `renderer/dashboard.py` 不存在；Flutter 端**没有蒸馏按钮**，蒸馏只在后端 `growth:distill`） |
| 6.1~6.3 卸力认知 | `core/model.py`（`best_device` / `device_kwargs` / `train_plan`）+ `core/trainer.py`（真 batch + 梯度累积 + 可选量化 + 检查点） | 完成（量化只在配了 int4/int8 且装了 bitsandbytes 时生效，否则 `quant_fallback` 照实说明；没有 offload 实现） |
| 6.4 显存自动策略 | `HardwareInfo.tier()`（flagship/high/standard/entry/minimal，按显存或内存） | **部分完成**：旧文案的「<4GB 纯 CPU / 4~8GB 4bit 部分层 / >8GB 全 GPU」三档阈值没有对应代码 |
| 6.5 桌宠推荐配置 | `train_plan(device)` → cuda `4/1/fp16`、mps `2/2/none`、cpu `1/8/none`（batch/grad_accum/quant，无 offload 项） | 完成 |
| 6.6 与训练管线耦合 | `should_train()` 把 `train_plan` 写进 details（不参与放行判定）；`train_round()` 按档位覆盖 batch/accum/quant | 完成（口径修正：档位只决定「怎么训」，不决定「能不能训」） |
| 7.1 动态升 rank | `core/growth.py::RankManager`（`status()` 读 r/alpha，`grow()` 翻倍写回，上限 256） | **部分完成**：没有「旧权重复制保留、新增补零」的张量重排，也没有 safetensors 纯 numpy 读写；`GrowthEngine.grow_rank()` 零调用方（RPC/CLI/UI 都没接），改 r 后需重训才生效 |
| 7.2 多适配器堆叠 | 无 | **未实现**（`stack_info()` 不存在，全仓零命中） |
| 7.3 晋升前能力评估 | `core/eval_probe.py`（4 条探针真跑推理：identity×2 + style×2，比对新权重与基座，判退化复读/空输出）+ `training:probe` | **部分完成**：不是「内置 50 题测试集」；探针数量与类别以 `PROBES` 常量为准，跑不动/没跑全一律不通过 |
| 7.5 存储估算与 rank 上限 | `max_rank=256`，`RankManager.status()['at_limit']`；体积估算走 `adapter_weight_bytes()` | 完成（不再声称达到上限自动改用堆叠，因为堆叠没实现） |
| 7.6 无限增长防护 | `ModelLifecycle.cap_check()`（≤5 代 / ≤10GB / dry_run override）→ 晋升返回 `blocked` | 完成 |
| 7.7 用户控制权 | 暂停/恢复 `growth:pause`/`growth:resume`（成长页有按钮）、回滚 `growth:rollback`、旧代清理 `growth:gc`、样本清理 `growth:purge`（三条都是先演练再 confirm）、手动触发 `training:*`、导出 `export()` + `training:export`/`training:gguf`。逐条查看样本只有 Python 的 `GrowthStore.list_records()`，**没有 `growth:list` 指令**（旧文档这一条写错了）；`core/fusion.py` 是指令解析器 | 完成（模块归属修正：`fusion.py` 只做自然语言指令路由，通道在 `core/channels.py`；逐条审阅样本仍缺前端入口） |
| 8.1 模型商店远端搜索 | `core/model.py::search_remote()` → 魔搭 `/openapi/v1/models?search=`；RPC `model:search <词> [页]`；前端 `widgets/model_remote_panel.dart` | **后端完成、前端待真机验证**：此前商店只有内置 11 条 `MODEL_PRESETS`，搜索框是 Dart 侧本地字符串过滤，不发任何请求（看着像商店，其实是固定清单）。现在真连魔搭，分页/许可证/gated/私有都取自接口；失败一律 `ok:false + error` 并给重试入口，不返回空列表冒充「没找到」。Dart 侧只过了 `dart format` 解析校验 |
| 8.2 按硬件推荐模型 | `core/model.py::recommend_for_hardware()` → `detect_hardware()` + `fit_models_for_hardware()`（RAM/VRAM/参数量/量化档逐模型算）；RPC `model:recommend` + gRPC `ListRecommendedModels` 都改走这条真路径 | **后端完成**：旧 `ListRecommendedModels` 用 `size_mb` 反算参数量（0.5B 显示成 "469B"）、`context` 硬编码 "32K"、`can_run` 用 `size_mb/1024*1.5` 的自创公式，且从未调用已有的 `fit_models_for_hardware()`。RAM 探测失败时 `available:false` 并把所有 `recommended` 强制置 `false`，不编推荐 |
| 8.3 远端下载 | `core/model.py::download_remote()` 复用 `_download_gguf_repo()`（与内置下载同一套断点续传）；RPC `model:downloadremote` 后台任务，进度写 `core.model.TASKS`，真源是 `sandbox:status` 的 `progress.<repo>` | **完成**：仓库名校验 `namespace/name`（含 `..`/反斜杠/盘符一律拒绝，要拼进 URL）；量化档从 `model:files` 的真实 `.gguf` 列表推；协作式取消（`agent:task cancel`），`.part` 保留可续传。顺带修了续传判定：ModelScope 续传回 **200 + 正确 `Content-Range`**（不是 206），旧代码会误判成不支持而从头再下 |
| 9.1 3D 形象资源 | `resources/models/小凌.vrm`（随仓库发布）+ `scripts/xiaoling_avatar.py` / `vrm_lib.py` / `vrm_preview.py` 生成管线 | **完成**：此前形象**从未进过版本库** —— `.gitignore` 写 `resources/models/` 排除了整个目录，被忽略的目录 Git 不进入，`!` 例外永不生效（两个远端全部提交历史里没有任何 `.vrm`/`.glb`/`.fbx`，所以"从历史恢复"做不到）。改为 `resources/models/*` + 显式放行这一个文件；回归 `tests/test_webpanel_static.py` |
| 9.2 查看器静态服务 | `core/webpanel.py::_serve_file()` + `_parse_range()` + `do_HEAD`；真实端口经 `web_state()` → RPC `system:ports` 交给前端 | **完成**：旧实现无视 `Range` 一律回 200 全量、且类里没有 `do_HEAD`（→ 501），WebView 预取与分段读取就在那一步失败。现在 206/416/后缀范围/开区间都支持且字节精确对齐，多段范围如实回整文件而不伪装 206。前端 `services/viewer_port.dart` 改为先问后端真值、不再盲扫 8765~8785 |
| 10.1 沙箱路径隔离 | `core/sandbox.py`：Landlock(Linux ≥5.13) / Seatbelt(macOS) / Job Object(Windows，仅资源) / `rlimit+chdir`(兜底) | **降级为默认路径**：内核 < 5.13 就没有 Landlock，此时 `lexical_escape_check()` 词法守卫生效，挡 `../../`、`~/.ssh/…`、他人 home；返回体 `guard:'lexical'`，`capability().path_isolation` 仍 `False`（新增 `lexical_guard:true`）。它只镜像 Landlock 的放行面，`cat /etc/passwd` 是刻意放过的 —— **不是安全边界**，挡不住编码/拼接/解释器内联绕过 |
| 10.2 后端连接启动 | `rpc/server.py::serve(port, ready_event)` + `main.py` 的 `threading.Event` 握手 | **完成**：旧代码在 `add_insecure_port()` 之前就打「已启动」（实测 grpc 1.84 端口被占是抛 `RuntimeError`，不返回 0）。现在绑定失败记录 `grpc:0` + 错误、打印换端口/清旧进程的处置提示并重抛；`main.py` 等真实结果才播报 |

