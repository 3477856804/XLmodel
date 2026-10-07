# 小凌成长管线规范（v1.1）

本规范是《小凌（xl.py）个人模型成长管线设计文档 v1.0》的落地对照版，
描述**代码中真实存在**的行为与开关。所有参数均可在
`.star_core/xiaoling_config.json` 的 `growth` 段调整（设置页由配置结构自动生成）。

## 一、闭环流程

```
用户日常对话
   ↓ core.fusion.chat() 全量记账
core.growth_store（SQLite：输入/基底回答/蒸馏回答/反馈/纠正/标签/质量分/训练轮次）
   ↓ 质量筛选 + 去重 + DeepSeek 蒸馏（core.throttle 节流）
训练触发判定 core.GrowthEngine.should_train()
   ├─ 样本 ≥ min_samples（手动触发用 manual_min_samples）
   ├─ 距上次训练 ≥ min_interval_hours
   ├─ 设备空闲（负载 + 常见重负载程序）
   ├─ 电量/温度正常
   ├─ 未暂停（growth.paused）
   └─ 算力档位允许训练（core.device.plan）
   ↓ 满足
LoRA 训练 core.peft_train.train_lora
   · 按档位给 batch / grad_accum / quant
   · 混入 base_mix_ratio（默认 15%）通用语料防遗忘
   · 损失曲线写 train_log.jsonl，轮次记账进 SQLite
   ↓
三条件评估 core.eval.Evaluator
   A 适配器体积 ≥ 基底体积
   B 用户专属验证集 loss_self ≤ loss_base（最多 20 条真实样本）
   C 通用基准通过率 ≥ pass_threshold（常识 20 + 通用 20 + 安全 10）
   ↓ 全过                      ↓ 仅 A 过
merge_and_promote()            grow_rank()（8→16→…→max_rank 256）
   ① merge_and_unload 合并
   ② 校验（config + 权重可加载 + 体积合理），失败即回滚
   ③ 原基底移入 trash/（retire_mode: trash/delete/archive）
   ④ 适配器归档为种子，在新基底上重建空适配器
   ↓
稳定期观察：24 小时 或 100 轮对话
   ↓ 达标
gc() 真删除旧代（保留 keep_generations=2；总代数 ≤5；总体积 ≤10GB）
```

## 二、关键默认值

| 参数 | 默认 | 含义 |
|---|---|---|
| `min_samples` / `manual_min_samples` | 500 / 20 | 自动 / 手动触发的样本门槛 |
| `min_interval_hours` | 24 | 两轮训练最小间隔 |
| `base_mix_ratio` | 0.15 | 通用语料混入比例（防遗忘） |
| `init_rank` / `max_rank` | 8 / 256 | LoRA 起始与上限 rank |
| `min_quality` | 0.5 | 进训练池的最低质量分 |
| `pass_threshold` | 0.90 | 条件 C 通用基准通过率 |
| `retire_mode` | trash | 退役方式（trash/delete/archive） |
| `keep_generations` / `max_generations` | 2 / 5 | 保留代数 / 增长上限 |
| `max_total_bytes` | 10GB | 模型总体积上限 |
| `stability_hours` / `stability_rounds` | 24 / 100 | 稳定期判定线 |
| `distill_enabled` / `distill_daily_limit` | true / 200 | 蒸馏开关 / 每日调用上限 |
| `paused` | false | 一键暂停成长 |

## 三、质量分口径（可解释、确定性、离线）

```
quality = 0.25·长度分 + 0.20·有老师回答 + 0.25·反馈分 + 0.15·有记忆标签 + 0.15·是提问
反馈分：like 1.0 / correct 0.95 / 未评 0.6 / dislike 0.1
```
分数只用于两件事：决定样本是否进训练池、排序时定优先级。

## 四、诚实边界

1. **演练 ≠ 通过**：`--dry-run` 下条件 B/C 返回模拟值并标注 `simulated: true`，
   仅用于流程校验与回归测试；真实模式下缺 torch 会返回 `requires_torch`（不算通过）。
2. **费用估算非账单**：单价默认为示例值，请按实际资费修改。
3. **`requires_eval=false`** 会跳过 B/C（仅供高级用户压测流程），默认不推荐。
