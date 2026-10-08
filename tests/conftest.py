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
import importlib
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
BACKEND = ROOT / 'backend'
for p in (ROOT, BACKEND):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _install_core_alias():
    """复用 main.py 里的 _install_core_alias()。

    不在这里另写一份 finder —— 两份实现容易漂移，且 main.py 那份用了
    自定义 Loader 走标准 create_module/exec_module 协议（Python 3.12+
    已移除旧式 load_module API，简单用 spec_from_loader 会报
    "'ModuleSpec' object has no attribute 'load_module'"）。
    """
    try:
        import main  # noqa: F401  # 导入即执行 _install_core_alias()
    except Exception:
        # 兜底：main.py 自身导入失败时手工装一个最小别名
        import importlib.abc
        import importlib.machinery
        import importlib.util

        class _AliasLoader(importlib.abc.Loader):
            def __init__(self, module):
                self._module = module

            def create_module(self, spec):
                return self._module

            def exec_module(self, module):
                pass

        class _Finder(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname != 'core' and not fullname.startswith('core.'):
                    return None
                try:
                    mod = importlib.import_module('backend.' + fullname)
                except Exception:
                    return None
                return importlib.machinery.ModuleSpec(
                    fullname, _AliasLoader(mod),
                    is_package=hasattr(mod, '__path__'))

        try:
            import backend.core  # noqa: F401
            sys.modules.setdefault('core', sys.modules['backend.core'])
            sys.meta_path.insert(0, _Finder())
        except Exception:
            pass


_install_core_alias()


# --------------------------------------------------------------------------
# 重构前的遗留测试：默认不收集
# --------------------------------------------------------------------------
# 这些文件针对旧架构编写，依赖已被移除的模块与签名：
#   - test_renderer.py  依赖 renderer 包（3D 渲染层已整体迁到 Flutter 端）
#   - test_growth.py    用 GrowthEngine(root, log=..., dry_run=...) 旧签名
#   - test_imports.py   硬编码 core.paths / core.system / core.persona 等旧模块名
#
# 按「绝不删文件」红线，原文件一律保留；这里只是让默认 `pytest` 不收集它们。
# 需要查看遗留用例的真实失败原因：
#     pytest tests/test_growth.py -p no:cacheprovider --override-ini="addopts="
collect_ignore = ["test_renderer.py", "test_growth.py", "test_imports.py"]
