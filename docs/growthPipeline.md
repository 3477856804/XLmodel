# 小凌成长管线规范（v1.1）

本规范描述**代码中真实存在**的行为与开关（原文是《小凌个人模型成长管线设计文档
v1.0》的落地对照版，那份设计稿不在仓库里，条目编号见
[`featureMapping.md`](featureMapping.md)）。所有参数都在
`.star_core/xiaoling_config.json` 的 `growth` 段（`core/config.py` 的
`CONFIG_PATH`，与内置 `DEFAULTS` 深合并后落盘）——**注意：设置页并没有成长参数的
图形入口**，`settings_page.dart` 只有置顶/开机自启/ASR/TTS/动效/更新那十几个开关，
`GrowthEngine.CONFIG_KEYS` 只被 `status()`/`report()` 回显，不做自动生成。
改这些值目前只有三条路：直接编辑配置文件、`training:checkpoint` /
`growth:distill on|off|limit` 这类专用 RPC 指令、或调用 Python API。
**唯一的例外是 `paused`**：成长页有「暂停成长 / 恢复成长」按钮（发
`growth:pause` / `growth:resume`），另外「成长运维」浮层提供回滚 / GC / 清库
三项，全部是「先演练再 confirm」两步。

## 一、闭环流程

```
用户日常对话
   ↓ engine._post_chat 记账 + 登记蒸馏队列（本地写一行，不在对话里联网）
core.GrowthStore（SQLite：输入/基底回答/老师回答/反馈/纠正/标签/质量分/训练轮次/蒸馏队列）
   ↓ 质量筛选 + 去重
   ↓ 训练组语料前：GrowthEngine.distill_round() 按队列问老师（text 蒸馏）
   ↓   ├─ 老师端未配置 → 如实跳过，一条请求都不发
   ↓   ├─ growth.distill_enabled=false → 如实跳过
   ↓   ├─ DistillThrottle：hash 缓存 + 每日限流 + 费用累计（真的被调用）
   ↓   └─ 写回 deepseek_output 并重算质量分（有老师答案是 0.20 的权重）
训练触发判定 core.GrowthEngine.should_train()
   ├─ 样本 ≥ min_samples（手动触发用 manual_min_samples）
   ├─ 距上次训练 ≥ min_interval_hours
   ├─ 设备空闲（require_device_idle 开时，_device_idle 实测负载）
   ├─ 电量/温度正常（require_power_ok 开时）
   ├─ 未暂停（growth.paused）
   └─ force=true 时以上全跳过（如实返回 forced，不做静默绕过）
   · 算力档位不参与「能不能训」，只提供 train_plan(best_device())
   ↓ 满足
LoRA 训练 core.GrowthEngine.train_round() → core.trainer.LoRATrainer.train()
   · 按档位给 batch / grad_accum / quant（cuda 4/1/fp16，mps 2/2，cpu 1/8）
   · 混入 base_mix_ratio（默认 15%）通用语料防遗忘
   · prompt 段置 IGNORE_INDEX，模板不支持时标 prompt_mask=degraded
   · checkpoint_interval>0 时按步落 stepN（权重 + optimizer.pt），
     只保留最近 checkpoint_keep 个；checkpoint_resume=auto 时按权重续训，
     声称有检查点却读不出来 → resume_denied，直接拒绝本轮而不是从头谎报
   · 损失曲线写 train_log.jsonl，轮次记账进 SQLite
   ↓
换代判定 core.GrowthEngine.check_and_promote()
   A 适配器体积 ≥ 基底体积（进度条就是 A 的比值；体积只算
     adapter_weight_bytes，不含 checkpoints/ 与 optimizer.pt，避免虚高）
   B 磁盘增长上限 cap_check()（总代数 / 总体积超线 → action=blocked）
   C 生成式验收 _acceptance_gate()（require_eval 开时才是门槛）：
     core/eval_probe.run_probes() 拿 4 条固定探针（identity×2、style×2）
     对新权重与基座各真跑一次 greedy 生成，比对人格/语气/退化复读；
     没 torch、加载失败、超时、有探针没跑全 → ok=false，拦住换代
   ↓ A 过且未被 B/C 拦住
merge_and_promote()
   ① 合并 LoRA 进基底（peft merge_and_unload，失败即清理临时目录并回滚）
   ② 校验（config + 权重可加载 + 体积合理），失败即回滚
   ③ 原基底移入 trash/（retire_mode: trash/delete/archive）
   ④ 适配器归档为种子，在新基底上重建空适配器，代数 +1
   ↓
稳定期观察：24 小时 或 100 轮对话
   ↓ 达标
gc() 真删除旧代（保留 keep_generations=2；总代数 ≤5；总体积 ≤10GB）
```

关于「三条件」：v1.0 设计稿写的是 A 体积 + B 用户专属验证集 loss +
C 通用基准（常识 20/通用 20/安全 10）。**那两条在代码里不存在**，本文件
不再照抄：验证 loss 只作为 TrainEvent 上报给用户看，不参与换代判定；
50 道基准题也没有实现。真正的第二、三条门槛是上面写的磁盘上限与生成式验收。

关于 `grow_rank()`：RankManager 只把 `adapter_config.json` 的 r 翻倍写回
（上限 256），不重排已有张量，改完必须重训才生效；`GrowthEngine.grow_rank()`
目前没有任何调用方（RPC/CLI/UI 都没接），换代路径里不存在「仅 A 过就自动升 rank」。

## 二、关键默认值

| 参数 | 默认 | 含义 |
|---|---|---|
| `min_samples` / `manual_min_samples` | 500 / 20 | 自动 / 手动触发的样本门槛 |
| `min_interval_hours` | 24 | 两轮训练最小间隔 |
| `base_mix_ratio` | 0.15 | 通用语料混入比例（防遗忘） |
| `init_rank` / `max_rank` | 8 / 256 | LoRA 起始与上限 rank |
| `min_quality` | 0.5 | 进训练池的最低质量分 |
| `pass_threshold` | 0.90 | 生成式验收通过率门槛（eval_probe 的 verdict 判据） |
| `retire_mode` | trash | 退役方式（trash/delete/archive） |
| `keep_generations` / `max_generations` | 2 / 5 | 保留代数 / 增长上限 |
| `max_total_bytes` | 10GB | 模型总体积上限 |
| `stability_hours` / `stability_rounds` | 24 / 100 | 稳定期判定线 |
| `distill_enabled` / `distill_daily_limit` | true / 200 | 蒸馏开关 / 每日调用上限 |
| `distill_batch_limit` | 8 | 一轮训练前最多问老师几条（费用与耗时上限） |
| `distill_timeout_sec` | 12.0 | 单次请求超时，实际钳在 1~120 秒 |
| `distill_time_budget_sec` | 20.0 | 一轮蒸馏的总时间预算，用完把剩下的留在队列里 |
| `teacher_price_in` / `teacher_price_out` | 1.0 / 2.0 | 每百万 token 单价，仅用于**估算** |
| `paused` | false | 一键暂停成长（成长页按钮发 `growth:pause`，等价于写状态 + 记 journal；`should_train`/`train_round`/`check_and_promote` 三处都读它） |

老师端本身另有三个**顶层**配置键（不在 growth 段）：`deepseek_api_key`、
`deepseek_base_url`、`teacher_model`。判据集中在 `core.growth.teacher_config()`：
三者齐备且 key 不是占位符「暂未填入」才算**已配置**。没配置时对话仍会正常
入库，但**不入蒸馏队列**，`growth:distill` 会直说缺哪一项 —— 不再出现
「蒸馏 API：开」而实际一条请求都没发的情况。

## 三、质量分口径（可解释、确定性、离线）

```
quality = 0.25·长度分 + 0.20·有老师回答 + 0.25·反馈分 + 0.15·有记忆标签 + 0.15·是提问
反馈分：like 1.0 / correct 0.95 / 未评 0.6 / dislike 0.1
```
分数只用于两件事：决定样本是否进训练池、排序时定优先级。

## 四、诚实边界

1. **演练 ≠ 通过**：`dry_run` 下不写任何文件、不合并、不晋升，返回
   `skipped: true`；`simulate_without_torch` 也只是流程演练，产物不算训练成果。
   真实模式下缺 torch/peft 会返回错误并拒绝换代（`requires_torch` 类的失败**不算通过**）。
2. **费用估算非账单**：单价默认为示例值，请按实际资费修改。
3. **`require_eval` 默认 false**，此时晋升只看体积与磁盘上限，报告里会明说
   「未做生成式验收，仅凭 loss 晋升」；开启后探针跑不动或没跑全都拦住换代。
   `pass_threshold` 只在这个开关打开时才起作用。
4. **这里的「蒸馏」是文本蒸馏，不是 soft-label KD**：走 OpenAI 兼容接口只能拿到
   老师写出的文字，拿不到它的 logits，因此训练仍是「把老师的答案当 SFT 语料」。
   按词分布蒸馏需要本地老师模型，本管线没有做，也不说成做了。
5. **蒸馏是异步且有上限的**：对话路径只登记队列，真正的请求发生在训练组语料之前
   或 `growth:distill run`；每轮最多 `distill_batch_limit` 条、每天最多
   `distill_daily_limit` 次。老师端未配置时一条都不发，报表与 RPC 直说未配置。
6. **不覆盖用户的答案**：样本优先级是 `corrected_output`（用户纠正）＞
   `deepseek_output`（老师）＞ `base_model_output`（本地）。已有老师答案的记录
   不会被重复请求覆盖 —— 已经进过训练的语料不该被悄悄换掉。
