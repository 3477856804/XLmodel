# -*- coding: utf-8 -*-
"""小凌 Python 后端包。

这个文件此前并不存在，后端一直靠 Python 的**命名空间包**（namespace
package，PEP 420）侥幸工作：没有 __init__.py 时，只要目录在 sys.path 上，
`import backend.core.config` 依然能解析。

但命名空间包在 **PyInstaller 打包**下不可靠 —— 打包器拿不到明确的包边界，
容易漏收子模块，导致 `from backend.core import xxx` 在产物里 ImportError。
显式声明为常规包后，`backend.*` 这一族才能被稳定收进 PYZ。

对开发态没有任何副作用：常规包与命名空间包的导入行为在此处等价。
"""
