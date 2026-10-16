# -*- coding: utf-8 -*-
"""环境兼容垫片：修复 ``attr`` 命名空间被第三方包遮蔽的问题。

背景
----
某些环境里 ``~/.local/lib/python3.12/site-packages/attr.py`` 是 ``dry_attr``
这类轻量包安装的**模块文件**，它会优先于真正的 ``attrs`` 分发包所提供的
``attr`` **常规包目录** 被 Python 解析。后果是::

    import attr            # 拿到 dry_attr 的 attr.py（没有 .s / .define）
    from aiohttp... import # aiohttp 内部用 @attr.s(...) 装饰 -> AttributeError

这会让 ``backend.core.channels``（依赖 aiohttp）等模块全部 ImportError，
测试与运行时连锁失败。该问题出在**用户全局 site-packages**，不在本仓库内，
不能改用户环境；因此这里做一个**自愈式**垫片：仅当检测到 ``attr`` 被遮蔽
（缺少 ``.s``）时，按真实路径重新加载标准 ``attrs`` 包并覆盖 ``sys.modules``。

设计原则
--------
* 幂等：重复调用无副作用；
* 仅在真正出问题时才动 ``sys.modules``，干净环境下零开销；
* 动态定位真实 ``attr`` 包目录（遍历 sys.path 找含 ``__init__.py`` 的
  ``attr/`` 目录），不硬编码解释器路径，保证可移植。
"""
from __future__ import annotations

import importlib.util
import os
import sys


def _looks_broken() -> bool:
    """判断当前 import attr 是否被遮蔽成了残缺模块。"""
    try:
        import attr  # noqa: WPS433 (intentional local import)
    except Exception:
        return True
    # 标准 attrs 同时提供 .s 与 .define；dry_attr 等残缺垫片二者皆无。
    return not (hasattr(attr, "s") and hasattr(attr, "define"))


def _find_real_attr_dir() -> str | None:
    """在 sys.path 中寻找真正的 ``attr`` 常规包目录（含 __init__.py）。"""
    try:
        seen = set()
        for entry in sys.path:
            if not entry or entry in seen:
                continue
            seen.add(entry)
            cand = os.path.join(entry, "attr")
            try:
                if (os.path.isdir(cand)
                        and os.path.exists(os.path.join(cand, "__init__.py"))):
                    return cand
            except OSError:
                continue
    except Exception:
        pass
    return None


def fix_attr_shadow() -> bool:
    """若检测到 attr 被遮蔽，则恢复为标准 attrs 包。返回是否做了修复。"""
    try:
        if not _looks_broken():
            return False
        real_dir = _find_real_attr_dir()
        if not real_dir:
            return False
        init_py = os.path.join(real_dir, "__init__.py")
        spec = importlib.util.spec_from_file_location(
            "attr",
            init_py,
            submodule_search_locations=[real_dir],
        )
        if spec is None or spec.loader is None:
            return False
        mod = importlib.util.module_from_spec(spec)
        # 关键：先登记进 sys.modules，再 exec，保证 aiohttp 内部
        # `import attr` 命中此处的真实包，而不是再次命中遮蔽文件。
        sys.modules["attr"] = mod
        spec.loader.exec_module(mod)
        # 顺带把 attrs 别名也指向同一对象，避免 `import attrs` 二次踩坑。
        try:
            sys.modules.setdefault("attrs", mod)
        except Exception:
            pass
        return hasattr(mod, "s")
    except Exception:
        return False


# 导入即自愈：main.py 与 tests/conftest.py 在很早的阶段 import 本模块即可。
fix_attr_shadow()
