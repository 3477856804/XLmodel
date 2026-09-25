# 接口契约

> 三套对外契约：成长引擎 CLI / 成长引擎 Python API / 渲染层 API。
> 机器可读版本见 [`接口契约.csv`](接口契约.csv) 与 [`openapi.yaml`](openapi.yaml)。

## 一、成长引擎 CLI（`python -m core.growth <cmd>`）

| 命令 | 作用 | 关键返回 |
|---|---|---|
| `status` / `report` | 成长状态与人类可读报告 | 进度百分比、触发条件、生命周期摘要 |
| `trigger [--manual]` | 只判定「现在能不能训练」 | `{ok, reasons[], details{}}` |
| `train [--epochs N] [--manual] [--force]` | 训练一轮 + 自动检查 | `{train, gate, check}` |
| `check [--force]` | 三条件评估 → 晋升或升 rank | `action ∈ promoted/rank_up/grow/skip/blocked` |
| `simulate` | 干跑完整晋升流程（不动真模型） | 同上，`simulated: true` |
| `pause` / `resume` | 暂停 / 恢复成长 | `{ok, paused}` |
| `rank [--rank N]` | 查看或升 LoRA rank | `{rank, rank_to, size_before/after}` |
| `eval` | 跑晋升三条件评估 | `{A, B, C, pass, simulated}` |
| `rollback [--gen N]` | 回滚到指定代 | `{ok, from_gen, target_gen}` |
| `gc [--keep N] [--force]` | 清理旧代（含稳定期校验） | `{deleted[], freed_human}` |
| `export --path X.zip` | 导出自己的模型 | `{ok, path, files, human}` |
| `samples` | 样本 / 蒸馏 / 损失曲线摘要 | 文本 |
| `lifecycle` | 代数登记与磁盘概览 | 文本 |

## 二、成长引擎 Python API（`core.growth.GrowthEngine`）

```python
from core.growth import GrowthEngine
eng = GrowthEngine(log=print)                   # dry_run=True 可无 torch 演练
eng.status(); eng.report()                      # 状态 / 报告
eng.should_train(manual=False, force=False)     # → {ok, reasons[], details{}}
eng.after_training_round(epochs=2, manual=True) # 触发校验 → 训练 → 自动检查
eng.check_and_promote(force=False)              # 三条件 → 晋升 / 升 rank
eng.pause(); eng.resume(); eng.bump_dialogue()  # 用户控制
eng.evaluate(); eng.grow_rank(); eng.rollback(gen=None)
eng.gc(keep=None, dry_run=False, force=False); eng.export(dest)
eng.store        # core.growth_store.GrowthStore（SQLite 数据仓库）
eng.throttle     # core.throttle.DistillThrottle（缓存/限流/成本）
eng.lifecycle    # core.lifecycle.ModelLifecycle（退役/GC/回滚/导出）
```

## 三、渲染层 API（`renderer/renderer.py`）

| 方法 | 说明 |
|---|---|
| `AvatarRenderer.load(vrm_path)` | 加载 VRM，建立骨骼/蒙皮/表情结构 |
| `set_action(vrma_path)` / `list_animations()` | 动作切换与枚举 |
| `set_expression(name, weight)` | 表情形变（14 组） |
| `set_lips(timeline)` | 口型时间轴驱动 |
| `render_frame()` | 出图（GL 或软件光栅，后端自适应） |
| `camera.front() / turn(deg)` | 正面朝向 / 转身 |

## 四、错误与降级约定

| 场景 | 约定 |
|---|---|
| 缺 torch/peft | 训练/合并返回 `ok:false` 并给出安装提示；评估返回 `requires_torch`（**不算通过**） |
| 无 GPU | 走 CPU 或 4bit 部分层，训练由算力档位决定是否触发 |
| 无 GL | 渲染自动降到 numpy 光栅；无 Qt 降到 Tkinter / 命令行 |
| 合并失败 | 校验不通过即回滚，原基底保持完好（原子替换） |
| 用户暂停 | 所有自动训练入口立即静默跳过 |
