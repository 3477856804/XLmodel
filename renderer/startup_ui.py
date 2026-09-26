#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.startup_ui —— 启动方式选择页

`xl` 的启动流程：环境配置页面（renderer/wizard.py，按需出现）
                → **启动方式选择页（本文件）**
                → 桌宠 / 对话窗口 / 命令行

为什么单独做这一页：3D 桌宠在无 GPU、软件渲染、远程/虚拟机环境里体验很差
（帧率低、鼠标交互卡），但这些环境恰恰更需要"能对话"。所以把选择权交给用户，
并允许「记住我的选择」以免每次都被问。

配置落点：``.star_core/xiaoling_config.json`` 的 ``startup.mode``
（``ask`` / ``pet`` / ``chat`` / ``cli``）。

模块级函数不依赖 Qt：无 Qt 时 ``choose_startup_mode`` 直接返回 (None, False)，
调用方按默认策略继续（不影响启动）。
"""
from __future__ import annotations

import sys

CHOICES = (
    ('pet', '启动桌宠（3D 数字人）',
     '有独立显卡、能正常开窗的环境选它。无 GPU / 软件渲染时会比较卡。'),
    ('chat', '无桌宠 · 对话窗口（推荐给 Kali / 无 GPU / 远程）',
     '轻量纯 Qt 窗口：能对话，也能当 xl 的终端用（/帮助 看指令）。不依赖 3D 渲染。'),
    ('cli', '纯命令行',
     '不弹任何窗口，直接在当前终端里对话。'),
)


def current_mode() -> str:
    """读取已保存的启动方式（ask / pet / chat / cli）。"""
    try:
        from core import config as _cfg
        m = str((_cfg.load().get('startup') or {}).get('mode') or 'ask').lower()
        return m if m in ('ask', 'pet', 'chat', 'cli') else 'ask'
    except Exception:                                                 # noqa: BLE001
        return 'ask'


def save_mode(mode: str) -> None:
    try:
        from core import config as _cfg
        _cfg.patch({'startup': {'mode': str(mode)}})
    except Exception:                                                 # noqa: BLE001
        pass


def choose_startup_mode(log=print):
    """弹出启动方式选择页。返回 (mode, remember)；没有 Qt 时返回 (None, False)。

    remember=True 表示用户勾了「记住我的选择」，调用方应把 mode 写进配置。
    """
    try:
        from PySide6 import QtCore, QtWidgets
    except Exception as e:                                            # noqa: BLE001
        log(f'  [启动页] 没有 PySide6（{e}），跳过选择，按命令行启动。')
        return None, False

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName('小凌')

    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle('小凌 · 选择启动方式')
    dlg.resize(560, 470)
    dlg.setStyleSheet('background:#faf6f7;')

    v = QtWidgets.QVBoxLayout(dlg)
    v.setContentsMargins(22, 20, 22, 18)
    v.setSpacing(10)

    head = QtWidgets.QLabel('选择启动方式')
    head.setStyleSheet('font-size:17px;font-weight:700;color:#3a2a30;')
    v.addWidget(head)
    sub = QtWidgets.QLabel('桌宠不好用（无 GPU / 软件渲染 / 远程）时，可以直接选「对话窗口」。')
    sub.setWordWrap(True)
    sub.setStyleSheet('font-size:12px;color:#9a8a90;')
    v.addWidget(sub)
    v.addSpacing(4)

    group = QtWidgets.QButtonGroup(dlg)
    default = current_mode()
    if default not in ('pet', 'chat', 'cli'):
        default = 'chat'          # 默认推荐对话窗口（对 Kali 这类环境更稳）

    _saved = default

    for key, title, desc in CHOICES:
        box = QtWidgets.QFrame()
        box.setStyleSheet('QFrame{background:#ffffff;border:1px solid #ecdde2;'
                          'border-radius:10px;}')
        bv = QtWidgets.QVBoxLayout(box)
        bv.setContentsMargins(12, 10, 12, 10)
        bv.setSpacing(3)
        rb = QtWidgets.QRadioButton(title)
        rb.setStyleSheet('font-size:13px;font-weight:600;color:#3a2a30;')
        rb.setChecked(key == _saved)
        rb.setProperty('choice_key', key)
        group.addButton(rb)
        bv.addWidget(rb)
        d = QtWidgets.QLabel(desc)
        d.setWordWrap(True)
        d.setStyleSheet('font-size:11px;color:#9a8a90;margin-left:20px;')
        bv.addWidget(d)
        v.addWidget(box)

    remember = QtWidgets.QCheckBox('记住我的选择（下次不再询问）')
    remember.setChecked(True)
    remember.setStyleSheet('font-size:12px;color:#9a8a90;')
    v.addWidget(remember)
    v.addStretch(1)

    row = QtWidgets.QHBoxLayout()

    def _btn(text, color):
        b = QtWidgets.QPushButton(text)
        b.setFixedHeight(32)
        b.setStyleSheet(f'background:{color};color:white;border:none;'
                        f'border-radius:16px;font-weight:600;padding:0 16px;')
        return b

    btn_later = _btn('每次都问', '#9a8a90')      # 保留 ask
    btn_ok = _btn('开始', '#d4385c')
    row.addStretch(1)
    row.addWidget(btn_later)
    row.addWidget(btn_ok)
    v.addLayout(row)

    result = {'mode': None, 'remember': False}

    def _accept():
        b = group.checkedButton()
        result['mode'] = (b.property('choice_key') if b else default)
        result['remember'] = bool(remember.isChecked())
        dlg.accept()

    def _keep_asking():
        result['mode'] = 'ask'
        result['remember'] = True
        dlg.accept()

    btn_ok.clicked.connect(_accept)
    btn_later.clicked.connect(_keep_asking)

    # 关掉窗口不等于退出整个程序（此时还没有别的窗口）
    prev = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    try:
        ok = dlg.exec_() if hasattr(dlg, 'exec_') else dlg.exec()
    finally:
        app.setQuitOnLastWindowClosed(prev)
    if not ok:
        return None, False
    return result['mode'], result['remember']


def main(argv=None) -> int:
    """`python -m renderer.startup_ui`：单独看看这一页。"""
    mode, remember = choose_startup_mode()
    print(f'选择：{mode}（记住：{remember}）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
