# -*- mode: python ; coding: utf-8 -*-
"""小凌 XIAOLING · PyInstaller 打包配置（兼容入口，转交 backend.spec）。

历史说明
========
本文件曾是独立配置，指向旧架构：入口 xl.py，源码目录 core/ renderer/ assets/，
以及中文目录 技能/ 数据/ 脚本/ 打包/，模型在项目根 models/、动作在根 animations/。
新架构（Flutter UI + Python gRPC 后端）落地后，这些目录与 xl.py 已全部删除，
旧 spec 一旦运行就会报 "Hidden import / 找不到 xl.py" 而失败，且无法产出可用包。

现状
====
统一打包配置为 packaging/backend.spec：入口 main.py，onedir（或 XIAOLING_ONEFILE=1
单文件），contents_directory='.'，显式登记 backend.core.* / backend.rpc.* /
backend.renderer.* 与 llama_cct 运行时，并收集 resources/web、VRM 模型、动作、
插件与 proto 契约。

本文件保留为兼容入口：任何旧文档 / 旧脚本里写的
    pyinstaller packaging/xiaoling.spec
都直接转交 backend.spec，避免两份配置漂移。版本号统一由后端 0.0.1 决定，
不在此硬编码。
"""
import os

# SPECPATH 由 PyInstaller 运行本 spec 时注入，恒为 packaging/ 目录。
# backend.spec 内部同样使用 SPECPATH 定位项目根与 runtime_hook.py，
# 因此直接在同一命名空间 exec 其内容即可，路径解析完全一致。
_BACKEND_SPEC = os.path.join(SPECPATH, 'backend.spec')
with open(_BACKEND_SPEC, 'r', encoding='utf-8') as _fh:
    exec(compile(_fh.read(), _BACKEND_SPEC, 'exec'))
