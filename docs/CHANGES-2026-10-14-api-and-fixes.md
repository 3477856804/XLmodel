# 变更记录 · 2026-10-14 · 训练模块 API 接入设置 + 完整性修复

> 操作人：MVPth（AI 专家助手）
> 项目：XLmodel-main（小凌 AI 桌面宠物）
> 红线遵守：本次操作未删除任何文件；临时产物已改 `.back` 后缀移至 `C:\Users\MVP\Desktop\delete`。

## 一、修改前备份（同目录，仅复制）

| 原文件 | 备份 |
|---|---|
| backend/core/trainer.py | trainer.py.bak-20261014 |
| backend/rpc/server.py | server.py.bak-20261014 |
| frontend/lib/pages/training_page.dart | training_page.dart.bak-20261014 |
| requirements.txt | requirements.txt.bak-20261014 |
| main.py | main.py.bak-20261014 |

## 二、新增功能：训练模块 API 接入设置接口（OpenAI 兼容端点）

**后端（backend/core/trainer.py 新增三个函数，模块尾部）：**
- `api_cfg()`：读取 `config.training.api_*`（api_enabled / api_base / api_key / api_model）。api_key 只回打码值（前4+****+后4），明文永不回流前端。
- `api_set(field, value)`：写单项设置，field ∈ enabled/base/key/model。base 做 http/https 校验，key 允许空串清除。
- `api_test(timeout=10)`：对配置端点发真实 POST `/chat/completions`（max_tokens=1）验证连通性；requests 缺席时自动降级标准库 urllib；任何失败如实返回原因，绝不伪造成功。

**gRPC 指令（backend/rpc/server.py `_handle_training_cmd` 新增子命令）：**
```
training:api                 读取当前设置（打码）
training:api on|off          启用/停用
training:api base <url>      设置端点
training:api key <密钥>      设置密钥（空串=清除）
training:api model <名字>    设置默认模型名
training:api test            真实连通性测试
```

**前端（frontend/lib/pages/training_page.dart）：**
- 「训练环境与产物」卡片底部新增「API 接入设置」入口按钮；
- 新增 `_ApiSettingsDialog` 对话框（端点/模型名/密钥三个输入框 + 启用开关 + 测试连接 + 保存），密钥留空=不改动，测试结果如实展示。

**用途说明：** 本接口只负责「接入设置的读写与连通性测试」（供后续蒸馏/验收探测/远程推理使用），不改变本地 LoRA 训练逻辑。

## 三、缺陷修复（代码审计发现）

| 级别 | 位置 | 问题 | 修复 |
|---|---|---|---|
| 高危 | trainer.py:844 | `pinned` 仅在 CPU 分支赋值，GPU 机器训练结束 finally 抛 UnboundLocalError，**覆盖真实训练结果** | try 前补 `pinned = None` |
| 高危 | trainer.py:1032 `_evaluate` | 键名 `trainable_tokens` 少下划线，弹不掉非张量键，验证 loss 永远是死代码 | 改 `_trainable_tokens` + 补 `_masked_by` |
| 高危 | requirements.txt:14 | `protobuf>=4.25.0` 与 gencode 7.35.1 不兼容，4.x 装完 import 即炸 | 改 `protobuf>=5.27`（注释说明，实跑对齐冻结清单 7.36.x） |
| 中 | requirements.txt | 代码真实依赖缺声明：psutil / jieba / huggingface_hub / modelscope | 已补；trl/bitsandbytes 以注释可选段列出 |
| 低 | main.py:138 | 优雅关闭是空壳（死 import） | 清理死 import 并注明原因 |
| 低 | server.py StartTraining | 死 import `XiaoLing as _XL` 未使用 | 清理并注明 |
| 低 | training_page.dart:1005 | 事件前缀映射缺 `[告警]`，告警被误判为 progress | 补 `'[告警]': 'warning'` |

## 四、验证记录

1. `py_compile` main.py / trainer.py / server.py 全部通过。
2. API 配置功能实测（隔离 XIAOLING_HOME）：默认值、URL 校验拒绝 ftp://、key 打码（sk-a****5678）、enabled/model 写入、未知 field 拒绝、明文不泄漏 —— 全部符合预期。
3. `api_test` 对不可达端点如实报错（URLError 10061），urllib 兜底路径生效。
4. `flutter pub get` + `dart analyze lib/pages/training_page.dart`：0 error / 0 warning（剩余 54 条 info 为存量 withOpacity 弃用提示，不在本次范围）。
5. 后端回归：pytest test_resume.py + test_imports.py（含跳过）与 test_distill.py + test_contracts.py 共 **66 passed**。

## 五、遗留事项（未改，供后续）

- `requirements.txt` 中 `sounddevice` 全仓零引用、`accelerate` 无真实 import（仅探测字符串）——是否移除请老板定夺（本仓红线不删内容，故保留）。
- `server.py` 直接启动（不经 main.py）时 `_PROJECT_ROOT` 层级会算错，属历史设计，建议后续统一入口。
- 前端 `_kindByPrefix` 采用中文前缀反推事件类型属脆弱约定，建议未来改 proto 传结构化 kind。

## 六、临时产物去向

- `.tmp_api_test_home` / `.tmp_api_test_home2`（测试用隔离 HOME）→ 移至 `C:\Users\MVP\Desktop\delete\` 并改后缀 `.back`，未删除。
