# 功能映射：设计文档 → 代码实现

| 设计文档条目 | 实现位置 | 状态 |
|---|---|---|
| 原则 1 记忆与训练分层 | `core/rag.py`（记忆）+ `core/growth.py`（训练） | 完成 |
| 原则 2 删除改为退役 | `core/lifecycle.py`（trash + 稳定期 + 回滚） | 完成 |
| 原则 3 晋升看三条件 | `core/eval.py`（A 体积 / B 验证集 loss / C 通用基准） | 完成 |
| 原则 4 训练不阻塞桌宠 | 训练在子进程/后台线程，UI 只读进度（`renderer/dashboard.py`） | 完成 |
| 2.1 三层结构（即时/稳定/人格） | RAG 即时记忆 + LoRA 稳定偏好 + 晋升合并人格 | 完成 |
| 2.2 四路训练数据来源 | `core/growth_store.py`（对话/反馈/蒸馏/导入） | 完成 |
| 2.3 训练触发策略 | `GrowthEngine.should_train()`（5 条同时满足） | 完成 |
| 2.4 灾难性遗忘防护 | `sample_for_training(base_mix_ratio=0.15)` | 完成 |
| 2.5 晋升条件 | `Evaluator.evaluate_all()` | 完成 |
| 3.1 记录结构 | `growth_store.records` 表（字段名与文档一致） | 完成 |
| 3.2 存储分工 | SQLite + 哈希向量 + 按月归档 JSONL | 完成 |
| 3.3 数据使用规则 | 质量分排序 / 点踩生成 DPO / 去重 / 轮次标记 | 完成 |
| 3.4 DeepSeek 蒸馏节流 | `core/throttle.py`（缓存/限流/开关/成本） | 完成 |
| 3.5 隐私与用户控制 | 本地存储 + 一键清空 + 加密导出导入 + 逐条可查 | 完成 |
| 4.1 退役流程 | `ModelLifecycle.retire()` + `stability()` | 完成 |
| 4.2 磁盘策略 | `gc(keep=2)` + `keep_generations` 可配 | 完成 |
| 4.3 目录结构 | `.star_core/{XLmodel,adapter,trash,adapter_seeds,growth}` | 完成（沿用既有布局并兼容旧版） |
| 5.x 成长仪表盘 | `renderer/dashboard.py` + `GrowthEngine.status()/samples_report()` | 完成 |
| 6.1~6.3 卸力认知 | `core/device.py`（device_map=auto / 量化 / 梯度累积 / 检查点） | 完成 |
| 6.4 显存自动策略 | `core/device.plan()`（<4/4~8/>8GB 三档） | 完成 |
| 6.5 桌宠推荐配置 | `core/device.train_plan()`（batch/accum/quant/offload） | 完成 |
| 6.6 与训练管线耦合 | `should_train()` 读算力档位；显存不足自动降 batch | 完成 |
| 7.1 动态升 rank | `core/rank.py`（旧权重复制、新增补零、上限 256） | 完成 |
| 7.2 多适配器堆叠 | `core/rank.stack_info()`（备选方案的登记与排序） | 完成 |
| 7.3 晋升前能力评估 | `core/eval.py` 内置测试集（常识 20/通用 20/安全 10） | 完成 |
| 7.5 存储估算与 rank 上限 | `max_rank` 默认 256，达到上限提示改用堆叠 | 完成 |
| 7.6 无限增长防护 | `ModelLifecycle.cap_check()`（≤5 代 / ≤10GB / 可 override） | 完成 |
| 7.7 用户控制权 | 暂停、手动触发、查看删除样本、回滚、导出（`core/fusion.py` 指令） | 完成 |
