#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.chat_ui —— 简单对话窗口（无桌宠时的 GUI 替代）

为什么需要它：Kali / 无 GPU / 软件渲染的机器上，3D 桌宠基本不可用
（帧率低、鼠标交互卡），而这些机器恰恰最需要"能对话"。
这里给一个**不依赖 3D 渲染**的轻量窗口：纯 Qt 控件，尺寸与启动器相近，
既能对话，也能当 xl 的终端用。

两种输入方式：
  · 普通文本      → 走引擎对话（``engine.chat``，融合层会先尝试识别指令）
  · 以 ``/`` 开头 → **强制**当作 xl 终端指令执行（复用 ``core.fusion.try_command``）
    例如 ``/帮助`` ``/成长报告`` ``/暂停成长`` ``/导出模型``

线程约定：对话/指令在工作线程里跑，结果通过 ``QtCore.Signal`` 回投主线程
（Qt 的 AutoConnection 会自动变成队列投递），**工作线程绝不直接碰控件**。

模块级函数不依赖 Qt，无 Qt 环境会打印命令行提示后安全返回 False。
"""
from __future__ import annotations

import sys
import threading

#: 常见叫法 → 指令表里**真实存在**的键。
#: 说明：core.fusion.COMMANDS 里帮助类指令的键是「融合帮助 / 新功能 / 指令帮助」，
#: **没有裸的「帮助」**。这里做一层别名，而不是往全局指令表里加短键 ——
#: 短键（如「帮助」）会被 try_command 的 `len<=8 and k in t` 规则误命中，
#: 把"你能帮助我吗"这种正常聊天当成指令。别名只影响本窗口，风险可控。
_CMD_ALIASES = {
    '帮助': '融合帮助',
    'help': '融合帮助',
    '?': '融合帮助',
    '指令': '融合帮助',
    '状态': '成长报告',
}


def _resolve_command(raw: str) -> str:
    """把用户输入的指令部分解析成指令表里真实存在的键。"""
    t = (raw or '').strip()
    return _CMD_ALIASES.get(t.lower() if t.isascii() else t, t)


def _status_text(engine) -> str:
    """一行状态：成长阶段 / 模型档位 / 渲染后端。取不到的项跳过，绝不抛异常。"""
    parts = []
    try:
        from core.growth import GrowthEngine
        from core.paths import APP_DIR
        st = GrowthEngine(base_dir=APP_DIR, log=lambda *a: None).status()
        if st.get('stage'):
            parts.append(str(st['stage']))
    except Exception:                                                 # noqa: BLE001
        pass
    try:
        from core import config as _cfg
        m = (_cfg.load().get('model') or {}).get('base_model')
        if m:
            parts.append(f'档位：{m}')
    except Exception:                                                 # noqa: BLE001
        pass
    try:
        from core import config as _cfg2
        be = (_cfg2.load().get('render') or {}).get('backend')
        if be:
            parts.append(f'渲染：{be}')
    except Exception:                                                 # noqa: BLE001
        pass
    return '　｜　'.join(p for p in parts if p)


def open_chat_window(engine=None, log=print) -> bool:
    """打开简单对话窗口（阻塞到用户关闭）。返回 False 表示没有 Qt。

    engine：xl.py 的 XiaoLing 实例。为 None 时仍会开窗，但不具备对话能力，
    只提示用户改用命令行版——不会崩。
    """
    try:
        from PySide6 import QtCore, QtWidgets
    except Exception as e:                                            # noqa: BLE001
        log(f'  [对话窗口] 没有 PySide6（{e}），无法开窗。')
        log('  [对话窗口] 可以继续用命令行版：直接在本终端里输入对话即可。')
        return False

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName('小凌')

    # v0.0.3：套粉色少女风主题
    try:
        from renderer.theme import (PALETTE, apply_pink_theme, card_qss,
                                    primary_btn_qss, secondary_btn_qss,
                                    ghost_btn_qss, input_qss, title_qss,
                                    subtitle_qss, bubble_html)
        apply_pink_theme(app)
    except Exception:                                             # noqa: BLE001
        PALETTE = {'accent': '#d4385c', 'text_title': '#3a2a30', 'text_muted': '#9a8a90'}
        def card_qss(): return ''
        def primary_btn_qss(): return ''
        def secondary_btn_qss(): return ''
        def ghost_btn_qss(): return ''
        def input_qss(): return ''
        def title_qss(): return ''
        def subtitle_qss(): return ''
        def bubble_html(who, text, who_color='accent'):
            safe = (str(text) or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            return f'<div><b>{who}：</b>{safe}</div>'

    class _Bridge(QtCore.QObject):
        """工作线程 → UI 的回投通道（Signal 跨线程自动排队）。"""
        reply = QtCore.Signal(str)
        failed = QtCore.Signal(str)

    bridge = _Bridge()

    win = QtWidgets.QWidget()
    win.setWindowTitle('小凌 · 对话')
    win.resize(920, 660)
    win.setStyleSheet(f'background:{PALETTE["bg_plain"]};')

    root = QtWidgets.QVBoxLayout(win)
    root.setContentsMargins(22, 18, 22, 16)
    root.setSpacing(10)

    # 顶栏：标题 + 状态
    head = QtWidgets.QLabel(' 小凌')
    head.setStyleSheet(title_qss())
    root.addWidget(head)

    stat = QtWidgets.QLabel(_status_text(engine) or '（状态读取中）')
    stat.setWordWrap(True)
    stat.setStyleSheet(subtitle_qss())
    root.addWidget(stat)

    # 对话区：白色卡片
    view = QtWidgets.QTextEdit()
    view.setReadOnly(True)
    view.setStyleSheet(
        'QTextEdit{background:#ffffff;border:1px solid '
        f'{PALETTE["card_border"]};border-radius:16px;'
        f'font-size:13px;padding:10px;}}'
        'QScrollBar:vertical{background:transparent;width:8px;}'
        'QScrollBar::handle:vertical{background:#f4c8d6;border-radius:4px;}'
    )
    root.addWidget(view, 1)

    tip = QtWidgets.QLabel('输入文字即可对话；以 / 开头的会被当作终端指令执行'
                            '（如 /帮助、/成长报告、/暂停成长）')
    tip.setWordWrap(True)
    tip.setStyleSheet(subtitle_qss())
    root.addWidget(tip)

    edit = QtWidgets.QLineEdit()
    edit.setPlaceholderText('说点什么呀～ 输入 /帮助 看全部指令…')
    edit.setStyleSheet(input_qss() + 'QLineEdit{padding:10px 14px;}')
    root.addWidget(edit)

    busy_lbl = QtWidgets.QLabel('')
    busy_lbl.setStyleSheet(subtitle_qss() + 'padding-left:4px;')
    root.addWidget(busy_lbl)

    btns = QtWidgets.QHBoxLayout()
    btns.setSpacing(8)
    root.addLayout(btns)

    btn_send = QtWidgets.QPushButton('发送 ')
    btn_send.setStyleSheet(primary_btn_qss())
    btn_send.setCursor(QtCore.Qt.PointingHandCursor)

    btn_clear = QtWidgets.QPushButton('清空')
    btn_clear.setStyleSheet(secondary_btn_qss())
    btn_growth = QtWidgets.QPushButton('成长')
    btn_growth.setStyleSheet(secondary_btn_qss())
    btn_help = QtWidgets.QPushButton('帮助')
    btn_help.setStyleSheet(secondary_btn_qss())
    btn_exit = QtWidgets.QPushButton('退出')
    btn_exit.setStyleSheet(ghost_btn_qss())

    btns.addWidget(btn_send)
    for b in (btn_clear, btn_growth, btn_help):
        btns.addWidget(b)
    btns.addStretch(1)
    btns.addWidget(btn_exit)

    def _append(who, text, kind='accent'):
        view.append(bubble_html(who, text, kind))
        sb = view.verticalScrollBar()
        sb.setValue(sb.maximum())

    _state = {'busy': False}

    def _busy(on: bool):
        _state['busy'] = bool(on)
        btn_send.setEnabled(not on)
        btn_growth.setEnabled(not on)
        btn_help.setEnabled(not on)
        edit.setReadOnly(on)
        busy_lbl.setText('小凌正在思考…' if on else '')
        if not on:
            edit.setFocus()

    def _submit(raw: str):
        text = (raw or '').strip()
        if not text or _state['busy']:
            return
        if engine is None:
            _append('小凌', '引擎还没就绪，暂时无法对话（可以改用命令行版 xl）。', 'accent')
            return
        _append('你', text, 'me')
        _busy(True)

        def _worker():
            try:
                if text.startswith('/'):
                    from core import fusion as _fusion
                    out = _fusion.try_command(engine, _resolve_command(text[1:].strip()))
                    if out is None:
                        out = f'未知指令：{text}（输入 /帮助 看全部指令）'
                else:
                    out = engine.chat(text)
                bridge.reply.emit(str(out))
            except Exception as e:                                    # noqa: BLE001
                bridge.failed.emit(f'{type(e).__name__}: {e}')

        threading.Thread(target=_worker, daemon=True, name='chat-ui').start()

    def _on_reply(text: str):
        _busy(False)
        _append('小凌', text, 'accent')
        stat.setText(_status_text(engine) or stat.text())

    def _on_failed(msg: str):
        _busy(False)
        _append('小凌', f'出错了：{msg}', 'accent')

    bridge.reply.connect(_on_reply)
    bridge.failed.connect(_on_failed)

    def _send():
        t = edit.text()
        edit.clear()
        _submit(t)

    btn_send.clicked.connect(_send)
    edit.returnPressed.connect(_send)
    btn_clear.clicked.connect(view.clear)
    btn_growth.clicked.connect(lambda: _submit('/成长报告'))
    btn_help.clicked.connect(lambda: _submit('/帮助'))
    btn_exit.clicked.connect(win.close)

    _append('小凌', '我在呢～想聊什么都可以。输入 /帮助 可以看全部指令。', 'accent')

    # 让 Ctrl+C 也能退出（Qt 事件循环不处理 Python 信号）
    try:
        import signal
        signal.signal(signal.SIGINT, lambda *_: app.quit())
        t = QtCore.QTimer(win)
        t.start(200)
        t.timeout.connect(lambda: None)
        win._sig_timer = t
    except Exception:                                                 # noqa: BLE001
        pass

    win.show()
    edit.setFocus()
    app.exec_() if hasattr(app, 'exec_') else app.exec()
    return True


def main(argv=None) -> int:
    """`python -m renderer.chat_ui`：独立开一个对话窗口（自建引擎）。"""
    engine = None
    try:
        import xl as _xl
        engine = _xl.XiaoLing()
    except Exception as e:                                            # noqa: BLE001
        print(f'  [对话窗口] 引擎创建失败，将以只读方式打开：{type(e).__name__}: {e}')
    return 0 if open_chat_window(engine) else 1


if __name__ == '__main__':
    sys.exit(main())
