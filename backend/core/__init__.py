# -*- coding: utf-8 -*-
"""小凌后端 · 核心能力包。

存在理由与 backend/__init__.py 相同：把命名空间包显式声明为常规包，
让 PyInstaller 能稳定收进 core 下的全部子模块。

注意 core 下的模块彼此之间大量使用 `from core.xxx import ...`（短名导入），
开发态靠 main.py 把 backend/ 目录塞进 sys.path 解析；打包态则由 main.py
里的 `_install_core_alias()` 装一个 meta path finder，把 `core.*` 改写到
`backend.core.*`。两条路都依赖本包能被正常导入。
"""
