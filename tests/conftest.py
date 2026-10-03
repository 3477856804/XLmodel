#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pytest 入口配置。

把「仓库根」与「backend/」都放进 sys.path，让 `import core.*` / `import renderer.*`
在任何 pytest 调用方式下都成立（各测试文件自己也会插一次，这里做兜底）。

v0.0.1 重构后后端统一在 `backend/` 下（core/ renderer/ rpc/），模块内部用相对导入，
因此必须把 `backend/` 本身加进 sys.path，`import core.xxx` 才能解析。

注意：本文件不导入 torch / PySide6 / 任何重型依赖，因此没有 GPU 与桌面的
环境下也能完成收集。
"""
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
BACKEND = ROOT / 'backend'
for p in (ROOT, BACKEND):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
