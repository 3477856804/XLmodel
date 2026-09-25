#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.i18n —— 极简国际化（中文 / English）

用法：:

    from renderer.i18n import t, set_language
    t('wizard.title')                      # '小凌 · 环境配置向导'
    t('deps.missing', n=3)                 # 带占位符

语言取自 ``core.config`` 的 ``language`` 字段（``'zh'`` / ``'en'``，默认中文）。

设计取舍：**刻意不引入任何第三方 i18n 库**（项目要求"不引入新依赖"），
用一个普通的 dict 表实现。缺键时回退顺序是：当前语言 → 中文 → 键名本身，
所以漏翻一个键最多显示键名，不会抛异常。
"""
from __future__ import annotations

DEFAULT_LANGUAGE = 'zh'
SUPPORTED = ('zh', 'en')

_lang = DEFAULT_LANGUAGE


# --------------------------------------------------------------------------- #
#  文案表
# --------------------------------------------------------------------------- #
STRINGS: dict[str, dict[str, str]] = {
    # ---- 通用 ----
    'common.ok':            {'zh': '已就绪',        'en': 'Ready'},
    'common.missing':       {'zh': '缺失',          'en': 'Missing'},
    'common.close':         {'zh': '关闭',          'en': 'Close'},
    'common.save':          {'zh': '保存',          'en': 'Save'},
    'common.saved':         {'zh': '已保存',        'en': 'Saved'},
    'common.skip':          {'zh': '暂时跳过',      'en': 'Skip for now'},
    'common.never_show':    {'zh': '不再提醒',      'en': "Don't remind me again"},
    'common.recheck':       {'zh': '重新检测',      'en': 'Re-check'},
    'common.export_report': {'zh': '导出诊断报告',  'en': 'Export diagnostic report'},
    'common.cancel':        {'zh': '取消',          'en': 'Cancel'},
    'common.installing':    {'zh': '安装中…',       'en': 'Installing…'},
    'common.done':          {'zh': '完成',          'en': 'Done'},
    'common.failed':        {'zh': '失败',          'en': 'Failed'},
    'common.note':          {'zh': '提示',          'en': 'Note'},

    # ---- 向导外壳 ----
    'wizard.title':         {'zh': '小凌 · 环境配置向导', 'en': 'XiaoLing · Setup Wizard'},
    'wizard.subtitle':      {'zh': '下面几项配好就能直接用了，也可以先跳过（下次启动会再提醒你）。',
                             'en': 'Set these up and you are good to go. You can skip and be reminded next time.'},
    'wizard.need_setup':    {'zh': '检测到还有 {n} 项未就绪', 'en': '{n} item(s) need attention'},
    'wizard.all_ready':     {'zh': '环境已就绪，可以直接启动', 'en': 'Everything is ready'},

    # ---- 依赖页 ----
    'tab.deps':             {'zh': '依赖',          'en': 'Dependencies'},
    'tab.api':              {'zh': 'API',           'en': 'API'},
    'tab.model':            {'zh': '模型',          'en': 'Model'},
    'tab.render':           {'zh': '渲染',          'en': 'Rendering'},
    'deps.header':          {'zh': '运行依赖',      'en': 'Runtime dependencies'},
    'deps.all_ok':          {'zh': '所有依赖都已就绪', 'en': 'All dependencies are ready'},
    'deps.missing_n':       {'zh': '缺少 {n} 个依赖', 'en': '{n} dependency(ies) missing'},
    'deps.install':         {'zh': '安装缺失依赖',  'en': 'Install missing'},
    'deps.install_torch':   {'zh': '安装 PyTorch',  'en': 'Install PyTorch'},
    'deps.torch_ok':        {'zh': 'PyTorch 已就绪：{ver}', 'en': 'PyTorch ready: {ver}'},
    'deps.torch_absent':    {'zh': 'PyTorch 未安装（可选，约 2.5GB）：本地推理与蒸馏训练需要它，'
                                   '不装也能聊天与显示桌宠。',
                             'en': 'PyTorch not installed (optional, ~2.5GB): needed for local inference '
                                   'and distillation training. Chatting and the pet work without it.'},
    'deps.torch_recommend': {'zh': '检测到 {gpu} → 推荐 {variant}',
                             'en': 'Detected {gpu} → recommend {variant}'},
    'deps.torch_cpu':       {'zh': '未检测到 NVIDIA GPU → 只能装 CPU 版',
                             'en': 'No NVIDIA GPU detected → CPU build only'},
    'deps.mirror':          {'zh': '使用国内镜像源（推荐）', 'en': 'Use China mirror (recommended)'},
    'deps.mirror_official': {'zh': '官方源',        'en': 'Official'},
    'deps.venv_hint':       {'zh': '当前不在虚拟环境中，建议创建 venv 隔离依赖（不强制）',
                             'en': 'Not running inside a virtualenv; a venv is recommended (not required)'},
    'deps.log':             {'zh': '安装日志',      'en': 'Install log'},
    'deps.no_auto':         {'zh': 'XL_NO_AUTO_DEPS=1：已禁用一切自动安装',
                             'en': 'XL_NO_AUTO_DEPS=1: all automatic installs disabled'},

    # ---- API 页 ----
    'api.header':           {'zh': 'DeepSeek（蒸馏老师）', 'en': 'DeepSeek (distillation teacher)'},
    'api.key':              {'zh': 'API Key',       'en': 'API Key'},
    'api.base_url':         {'zh': 'Base URL（用中转站就改这里）', 'en': 'Base URL (change this for a relay)'},
    'api.hint':             {'zh': 'Key 会写进 .star_core/xiaoling_config.json，不会进版本库。'
                                   '不填也能用，只是小凌无法向老师学习。',
                             'en': 'The key is stored in .star_core/xiaoling_config.json and is git-ignored. '
                                   'Optional — without it XiaoLing just cannot learn from the teacher.'},
    'api.key_set':          {'zh': '已配置（{n} 字符）', 'en': 'Configured ({n} chars)'},
    'api.key_unset':        {'zh': '未配置',        'en': 'Not configured'},
    'api.bad_url':          {'zh': 'Base URL 需以 http:// 或 https:// 开头', 'en': 'Base URL must start with http:// or https://'},
    'api.migrated':         {'zh': '已从历史 .env 迁移配置：{keys}（该文件可删除）',
                             'en': 'Migrated from legacy .env: {keys} (that file can be deleted)'},

    # ---- 模型页 ----
    'model.header':         {'zh': '基底模型档位',  'en': 'Base model preset'},
    'model.hint':           {'zh': '选择后写入 .star_core/model_choice.txt 并同步到配置；'
                                   '基底权重约 4.8GB，首次使用时会自动下载。',
                             'en': 'Saved to .star_core/model_choice.txt and the config. '
                                   'Base weights are ~4.8GB and download on first use.'},

    # ---- 渲染页 ----
    'render.header':        {'zh': '渲染后端',      'en': 'Render backend'},
    'render.auto':          {'zh': '自动（推荐）',  'en': 'Auto (recommended)'},
    'render.gpu':           {'zh': 'OpenGL（GPU 直绘）', 'en': 'OpenGL (GPU)'},
    'render.soft':          {'zh': 'CPU 软件光栅（最兼容）', 'en': 'CPU software raster (most compatible)'},
    'render.osmesa':        {'zh': 'OSMesa 离屏（无显示器时）', 'en': 'OSMesa offscreen (headless)'},
    'render.hint':          {'zh': '改完重启小凌生效。若桌宠不显示，先试「CPU 软件光栅」。',
                             'en': 'Restart XiaoLing to apply. If the pet does not show, try CPU software raster.'},
    'render.probe':         {'zh': '测试后端',      'en': 'Test backend'},
    'render.probe_ok':      {'zh': '后端 {name} 可用', 'en': 'Backend {name} works'},
    'render.probe_fail':    {'zh': '后端 {name} 不可用：{err}', 'en': 'Backend {name} failed: {err}'},

    # ---- GPU / 平台提示 ----
    'gpu.detected':         {'zh': '显卡：{name}（驱动 {driver}，sm_{sm}）',
                             'en': 'GPU: {name} (driver {driver}, sm_{sm})'},
    'gpu.none':             {'zh': '未检测到 NVIDIA 显卡', 'en': 'No NVIDIA GPU detected'},
    'gpu.wsl_hint':         {'zh': 'WSL2 环境：请在 Windows 侧安装 NVIDIA 驱动（建议 ≥ 570），'
                                   'WSL 内的显卡由 Windows 驱动透传。',
                             'en': 'WSL2: install the NVIDIA driver on the Windows side (>= 570); '
                                   'the GPU is passed through from Windows.'},
    'gpu.linux_hint':       {'zh': 'Linux 桌面若桌宠不显示，可能需要：'
                                   'sudo apt install libgl1 libglx-mesa0 libosmesa6 libxcb-cursor0',
                             'en': 'On Linux, if the pet does not appear you may need: '
                                   'sudo apt install libgl1 libglx-mesa0 libosmesa6 libxcb-cursor0'},

    # ---- 诊断报告 ----
    'report.title':         {'zh': '环境诊断报告',  'en': 'Diagnostic report'},
    'report.saved':         {'zh': '已导出：{path}', 'en': 'Exported: {path}'},
    'report.failed':        {'zh': '导出失败：{err}', 'en': 'Export failed: {err}'},
}


# --------------------------------------------------------------------------- #
#  接口
# --------------------------------------------------------------------------- #
def set_language(lang: str | None) -> str:
    """设置当前语言，返回生效值。无法识别时保持原值。"""
    global _lang
    if lang and str(lang).lower() in SUPPORTED:
        _lang = str(lang).lower()
    return _lang


def get_language() -> str:
    return _lang


def init_from_config() -> str:
    """从 core.config 的 language 字段初始化（启动时调一次）。"""
    try:
        from core import config as _cfg
        return set_language(_cfg.load().get('language'))
    except Exception:                                                 # noqa: BLE001
        return _lang


def t(key: str, **kw) -> str:
    """取文案。缺键回退：当前语言 → 中文 → 键名。带占位符时安全格式化。"""
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(_lang) or entry.get(DEFAULT_LANGUAGE) or key
    if kw:
        try:
            return text.format(**kw)
        except Exception:                                             # noqa: BLE001
            return text
    return text
