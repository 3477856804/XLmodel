#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pytest 入口配置。

作用只有一个：把仓库根目录放进 sys.path，让 `import core.*` / `import renderer.*`
在任何 pytest 调用方式下都成立（各测试文件自己也会插一次 sys.path，这里做兜底）。

注意：本文件不导入 torch / PySide6 / 任何重型依赖，因此没有 GPU 与桌面的
环境下也能完成收集。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
