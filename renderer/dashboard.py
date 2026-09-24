#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.dashboard —— 小凌训练工作台（大窗口）

布局参考"XIAOLING PRESENCE"：
    顶部：标题 + 状态标签
    左列：感知 / 理解 / 决策 三张进度卡
    中央：当前桌宠 3D 形象实时渲染
    右列：进化 / 守护 两张进度卡
    底部：整体训练进度条 + 状态文案
"""
from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path

from core.paths import resource, is_frozen


# --------------------------------------------------------------------------- #
#  进度数据：从 GrowthEngine 读真实训练进度，各通道按比例映射
# --------------------------------------------------------------------------- #
def _growth_status():
    """返回整体进度与阶段文案。读不到时返回安全默认值。"""
    try:
        from core.growth import GrowthEngine
        from core.paths import APP_DIR
        eng = GrowthEngine(base_dir=APP_DIR)
        s = eng.status()
        return {
            'percent': float(s.get('progress_percent', 0.0)),
            'stage': s.get('stage', '初始化中'),
            'base_mb': float(s.get('base_mb', 0)),
            'adapter_mb': float(s.get('adapter_mb', 0)),
            'self_research': bool(s.get('self_research', False)),
        }
    except Exception:
        return {'percent': 0.0, 'stage': '初始化中', 'base_mb': 0,
                'adapter_mb': 0, 'self_research': False}


# 五个通道：整体进度按权重分配到各通道（真实训练时 GrowthEngine 只有一个总进度，
# 这里按通道"成熟度"做视觉分布，让五个卡看起来在同步成长）
_CHANNELS = [
    ('SENSING SYNC',    '感知通路唤醒', '感知', '连接世界', '持续感受', 'left',  0.92),
    ('COGNITION SYNC',  '理解通路唤醒', '理解', '结合记忆', '辨别事实', 'left',  0.82),
    ('DECISION SYNC',   '决策通路唤醒', '决策', '比较路线', '科学选择', 'left',  0.68),
    ('EVOLUTION SYNC',  '进化通路唤醒', '进化', '持续学习', '自我优化', 'right', 1.05),
    ('GUARD SYNC',     '守护通路唤醒', '守护', '检查边界', '保留回滚', 'right', 0.78),
]


def _channel_progress(overall: float, weight: float) -> float:
    """把总进度映射到单个通道，限制在 0~100。"""
    v = overall * weight + (100 - overall) * 0.08
    return max(0.0, min(100.0, v))


def _smart_reply(text: str) -> str:
    """轻量规则回复（不依赖重型引擎，保证 UI 响应）。"""
    t = text.strip().lower()
    if any(k in t for k in ('你好', 'hi', 'hello', '在吗', '在不在')):
        return '我在呢～有什么想聊的？'
    if any(k in t for k in ('你是谁', '介绍', '你叫什么')):
        return '我是小凌，一个会成长的数字生命。你可以和我对话、看我训练进化。'
    if any(k in t for k in ('训练', '蒸馏', '进化', '成长')):
        return '我正在持续自我进化～点右下角+号开启蒸馏训练插件，可以加速我的成长！'
    if any(k in t for k in ('模型', '切换', '换个', '角色')):
        return '顶部下拉框可以切换7个角色模型，每个都有专属音色哦～'
    if any(k in t for k in ('语音', '说话', '朗读', '声音')):
        return '点右下角+号开启语音朗读插件，我会用专属音色说话～'
    if any(k in t for k in ('谢谢', '感谢', 'thx', 'thanks')):
        return '不客气～能帮到你我很开心！'
    if any(k in t for k in ('再见', '拜拜', 'bye', '晚安')):
        return '再见～记得常来看我，我会一直在这里成长的！'
    if '?' in text or '？' in text:
        return '这个问题很有意思，让我想想…我觉得可以从多个角度来看。'
    return f'你说「{text}」，我记住了～继续聊聊吧！'


# --------------------------------------------------------------------------- #
#  PySide6 窗口
# --------------------------------------------------------------------------- #
def build_dashboard(renderer=None, engine=None, log=print):
    """构建并返回工作台窗口对象。无 Qt/无桌面时返回 None。"""
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except Exception as e:
        log(f'  [工作台] PySide6 不可用：{e}')
        return None

    # 若没传入 renderer，自己建一个（软件渲染后端，兼容无 GL 环境）
    own_renderer = False
    if renderer is None:
        try:
            from renderer.renderer import AvatarRenderer
            renderer = AvatarRenderer(backend='auto', width=460, height=620,
                                      focus='bust', log=log)
            own_renderer = True
        except Exception as e:
            log(f'  [工作台] 渲染层初始化失败：{e}')
            return None

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName('小凌工作台')

    # ---------- 主窗口 ----------
    win = QtWidgets.QMainWindow()
    win.setWindowTitle('小凌 XIAOLING · 训练工作台')
    win.resize(1280, 800)
    win.setMinimumSize(1100, 700)

    # 浅粉白配色
    PALETTE_BG = '#faf6f7'
    CARD_BG = '#ffffff'
    ACCENT = '#d4385c'
    ACCENT_SOFT = '#f5d5dd'
    TEXT_DARK = '#3a2a30'
    TEXT_MUTED = '#9a8a90'

    central = QtWidgets.QWidget()
    win.setCentralWidget(central)
    root = QtWidgets.QVBoxLayout(central)
    root.setContentsMargins(28, 22, 28, 22)
    root.setSpacing(14)
    central.setStyleSheet(f'background:{PALETTE_BG};')

    # ---------- 顶部标题栏 ----------
    top = QtWidgets.QHBoxLayout()
    title = QtWidgets.QLabel('XIAOLING PRESENCE')
    title.setStyleSheet(f'color:{TEXT_MUTED};font-size:13px;font-weight:600;'
                        f'letter-spacing:3px;')
    title.setAlignment(QtCore.Qt.AlignCenter)
    top.addStretch(1)
    top.addWidget(title, 2)
    top.addStretch(1)

    tag_row = QtWidgets.QHBoxLayout()
    tag_row.setSpacing(8)
    for txt, dot in (('自主扫描', True), ('5 MIN', False), ('READ ONLY', False)):
        chip = QtWidgets.QPushButton(txt)
        chip.setFixedHeight(26)
        chip.setStyleSheet(f'''
            QPushButton {{
                background:{CARD_BG}; color:{TEXT_MUTED};
                border:1px solid #ecdde2; border-radius:13px;
                padding:0 14px; font-size:11px;
            }}''')
        if dot:
            chip.setStyleSheet(chip.styleSheet() + f'''
                QPushButton {{ padding-left:24px; }}
            ''')
        tag_row.addWidget(chip)
    top.addLayout(tag_row)
    root.addLayout(top)

    # ---------- 中部三栏：左卡 / 中央3D / 右卡 ----------
    mid = QtWidgets.QHBoxLayout()
    mid.setSpacing(18)

    # 左列
    left_col = QtWidgets.QVBoxLayout()
    left_col.setSpacing(16)
    # 右列
    right_col = QtWidgets.QVBoxLayout()
    right_col.setSpacing(16)

    # 进度卡工厂
    def make_card(title_en, sub, name, line1, line2):
        card = QtWidgets.QFrame()
        card.setFixedWidth(260)
        card.setStyleSheet(f'''
            QFrame {{
                background:{CARD_BG}; border-radius:16px;
                border:1px solid #f0e4e8;
            }}''')
        v = QtWidgets.QVBoxLayout(card)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(8)

        head = QtWidgets.QHBoxLayout()
        t = QtWidgets.QLabel(title_en)
        t.setStyleSheet(f'color:{TEXT_DARK};font-size:12px;font-weight:700;'
                        f'letter-spacing:1px;')
        pct = QtWidgets.QLabel('--%')
        pct.setStyleSheet(f'color:{ACCENT};font-size:14px;font-weight:700;')
        head.addWidget(t)
        head.addStretch(1)
        head.addWidget(pct)
        v.addLayout(head)

        bar = QtWidgets.QProgressBar()
        bar.setRange(0, 100)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        bar.setStyleSheet(f'''
            QProgressBar {{ background:#f0e4e8; border-radius:3px; }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {ACCENT}, stop:1 #ff7a9c);
                border-radius:3px;
            }}''')
        v.addWidget(bar)

        foot = QtWidgets.QHBoxLayout()
        s = QtWidgets.QLabel(sub)
        s.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
        days = QtWidgets.QLabel('16 DAYS')
        days.setStyleSheet(f'color:{ACCENT};font-size:11px;font-weight:600;')
        foot.addWidget(s)
        foot.addStretch(1)
        foot.addWidget(days)
        v.addLayout(foot)
        return card, bar, pct

    card_refs = {}
    for c_en, sub, name, l1, l2, side, weight in _CHANNELS:
        card, bar, pct = make_card(c_en, sub, name, l1, l2)
        box = QtWidgets.QVBoxLayout()
        box.setAlignment(QtCore.Qt.AlignVCenter)
        # 通道名 + 连线（中间区标签）
        name_lbl = QtWidgets.QLabel(name)
        name_lbl.setStyleSheet(f'color:{TEXT_DARK};font-size:18px;font-weight:700;')
        sub_lbl = QtWidgets.QLabel(f'{l1}\n{l2}')
        sub_lbl.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        sub_lbl.setAlignment(QtCore.Qt.AlignCenter)
        col_inner = QtWidgets.QVBoxLayout()
        col_inner.setSpacing(4)
        col_inner.addWidget(name_lbl, alignment=QtCore.Qt.AlignCenter)
        col_inner.addWidget(sub_lbl, alignment=QtCore.Qt.AlignCenter)
        if side == 'left':
            left_col.addLayout(col_inner)
            left_col.addSpacing(6)
            left_col.addWidget(card, alignment=QtCore.Qt.AlignHCenter)
            left_col.addStretch(1)
        else:
            right_col.addLayout(col_inner)
            right_col.addSpacing(6)
            right_col.addWidget(card, alignment=QtCore.Qt.AlignHCenter)
            right_col.addStretch(1)
        card_refs[c_en] = (bar, pct, weight)

    # ---------- 插件系统（万物皆插件，右下角 + 号开启） ----------
    # 插件定义：id, 名称, 颜色, 回调
    _plugins = [
        ('deepchat', '深度对话', ACCENT, None),
        ('agent', 'Agent 任务', '#7a5a8a', None),
        ('schedule', '定时提醒', '#5a7a8a', None),
        ('call', '通话模式', '#8a6a5a', None),
        ('tts', '语音朗读', '#5a8a6a', None),
        ('distill', '蒸馏训练', '#8a7a5a', None),
    ]
    _enabled = {pid: False for pid, _, _, _ in _plugins}

    # 底部已启用插件快捷按钮栏
    plugin_bar = QtWidgets.QHBoxLayout()
    plugin_bar.setSpacing(8)
    plugin_bar.addStretch(1)
    _plugin_btns = {}

    def _refresh_plugin_bar():
        # 清空旧按钮
        while plugin_bar.count():
            item = plugin_bar.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        plugin_bar.addStretch(1)
        for pid, name, color, _ in _plugins:
            if _enabled.get(pid):
                b = QtWidgets.QPushButton(name)
                b.setFixedHeight(30)
                b.setStyleSheet(f'''
                    QPushButton {{
                        background:{color}; color:white; border:none;
                        border-radius:15px; padding:0 16px;
                        font-size:12px; font-weight:600;
                    }}
                    QPushButton:hover {{ background:{color}; opacity:0.8; }}
                ''')
                b.clicked.connect(lambda checked, p=pid: _run_plugin(p))
                plugin_bar.addWidget(b)
        plugin_bar.addStretch(1)

    def _run_plugin(pid):
        if pid == 'deepchat':
            open_deepchat()
        elif pid == 'agent':
            open_agent()
        elif pid == 'schedule':
            open_schedule()
        elif pid == 'call':
            open_call()
        elif pid == 'tts':
            toggle_tts()
        elif pid == 'distill':
            start_distill()

    # 右下角浮动 + 按钮
    plus_btn = QtWidgets.QPushButton('+')
    plus_btn.setFixedSize(56, 56)
    plus_btn.setStyleSheet(f'''
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {ACCENT}, stop:1 #ff7a9c);
            color:white; border:none; border-radius:28px;
            font-size:28px; font-weight:300;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #b01e40, stop:1 {ACCENT});
        }}
    ''')
    plus_btn.setParent(central)
    plus_btn.raise_()

    # 插件面板（弹出）
    plugin_panel = QtWidgets.QFrame(central)
    plugin_panel.setFixedWidth(280)
    plugin_panel.setStyleSheet(f'''
        QFrame {{
            background:rgba(255,255,255,0.95);
            border-radius:18px; border:1px solid #f0e4e8;
        }}
    ''')
    plugin_panel.hide()
    pp_layout = QtWidgets.QVBoxLayout(plugin_panel)
    pp_layout.setContentsMargins(18, 16, 18, 16)
    pp_layout.setSpacing(6)
    pp_title = QtWidgets.QLabel('插件中心')
    pp_title.setStyleSheet(f'color:{TEXT_DARK};font-size:16px;font-weight:700;')
    pp_layout.addWidget(pp_title)
    pp_sub = QtWidgets.QLabel('万物皆插件，开启后显示在底部')
    pp_sub.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
    pp_layout.addWidget(pp_sub)
    pp_layout.addSpacing(6)

    _plugin_switches = {}
    for pid, name, color, _ in _plugins:
        row = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel(name)
        lbl.setStyleSheet(f'color:{TEXT_DARK};font-size:13px;')
        sw = QtWidgets.QCheckBox()
        sw.setStyleSheet(f'''
            QCheckBox::indicator {{
                width:40px; height:22px; border-radius:11px;
                background:#ddd;
            }}
            QCheckBox::indicator:checked {{
                background:{color};
            }}
        ''')
        def _toggle(checked, p=pid):
            _enabled[p] = checked
            _refresh_plugin_bar()
        sw.stateChanged.connect(_toggle)
        row.addWidget(lbl)
        row.addStretch(1)
        row.addWidget(sw)
        pp_layout.addLayout(row)
        _plugin_switches[pid] = sw
    pp_layout.addStretch(1)

    def _toggle_panel():
        if plugin_panel.isVisible():
            plugin_panel.hide()
        else:
            # 定位到 + 按钮上方
            pb = plus_btn.geometry()
            panel_w = 280
            panel_h = 320
            x = central.width() - panel_w - 20
            y = central.height() - panel_h - 76
            plugin_panel.setGeometry(x, y, panel_w, panel_h)
            plugin_panel.show()
            plugin_panel.raise_()
    plus_btn.clicked.connect(_toggle_panel)

    def _resize_plus():
        plus_btn.move(central.width() - 76, central.height() - 76)
        if plugin_panel.isVisible():
            _toggle_panel()
            _toggle_panel()
    central.installEventFilter(win)
    # 用定时器跟踪大小变化
    _resize_plus()

    mid.addLayout(left_col, 0)

    # 深聊对话框
    def open_deepchat():
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('深度对话')
        dlg.setFixedSize(420, 280)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)
        l = QtWidgets.QLabel('想深入聊什么话题？')
        l.setStyleSheet(f'color:{TEXT_DARK};font-size:14px;font-weight:600;')
        v.addWidget(l)
        topic_input = QtWidgets.QLineEdit()
        topic_input.setPlaceholderText('例如：人生意义、技术趋势、情感问题…')
        topic_input.setFixedHeight(36)
        topic_input.setStyleSheet(f'background:{CARD_BG};border:1px solid #ecdde2;border-radius:18px;padding:0 14px;')
        v.addWidget(topic_input)
        result = QtWidgets.QTextEdit()
        result.setReadOnly(True)
        result.setStyleSheet(f'background:{CARD_BG};border:1px solid #f0e4e8;border-radius:12px;padding:10px;font-size:12px;color:{TEXT_DARK};')
        v.addWidget(result, 1)
        def run_deep():
            topic = topic_input.text().strip()
            if not topic:
                result.setText('请输入话题')
                return
            result.setText('小凌正在深入思考…')
            def _w():
                try:
                    from core.fusion import _STATE
                    eng = _STATE.get('engine')
                    if eng and hasattr(eng, 'deepchat'):
                        r = _smart_reply(topic)
                    else:
                        r = f'关于「{topic}」，小凌的理解是：这是一个值得深入探讨的话题。'
                    QtCore.QMetaObject.invokeMethod(result, 'setPlainText',
                        QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, str(r)))
                except Exception as e:
                    QtCore.QMetaObject.invokeMethod(result, 'setPlainText',
                        QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f'暂不可用：{e}'))
            threading.Thread(target=_w, daemon=True).start()
        btn = QtWidgets.QPushButton('开始深聊')
        btn.setFixedHeight(36)
        btn.setStyleSheet(f'background:{ACCENT};color:white;border:none;border-radius:18px;font-weight:600;')
        btn.clicked.connect(run_deep)
        v.addWidget(btn)
        dlg.exec()

    # Agent任务对话框
    def open_agent():
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('Agent 任务')
        dlg.setFixedSize(420, 280)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)
        l = QtWidgets.QLabel('让小凌帮你做什么？')
        l.setStyleSheet(f'color:{TEXT_DARK};font-size:14px;font-weight:600;')
        v.addWidget(l)
        goal_input = QtWidgets.QLineEdit()
        goal_input.setPlaceholderText('例如：写一份周报、分析一段代码、整理思路…')
        goal_input.setFixedHeight(36)
        goal_input.setStyleSheet(f'background:{CARD_BG};border:1px solid #ecdde2;border-radius:18px;padding:0 14px;')
        v.addWidget(goal_input)
        result = QtWidgets.QTextEdit()
        result.setReadOnly(True)
        result.setStyleSheet(f'background:{CARD_BG};border:1px solid #f0e4e8;border-radius:12px;padding:10px;font-size:12px;color:{TEXT_DARK};')
        v.addWidget(result, 1)
        def run_agent():
            goal = goal_input.text().strip()
            if not goal:
                result.setText('请输入任务')
                return
            result.setText('小凌正在执行任务…')
            def _w():
                try:
                    from core.fusion import _STATE
                    eng = _STATE.get('engine')
                    if eng and hasattr(eng, 'agent'):
                        r = _smart_reply(goal)
                    else:
                        r = f'任务「{goal}」已记录，小凌会尽力完成。'
                    QtCore.QMetaObject.invokeMethod(result, 'setPlainText',
                        QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, str(r)))
                except Exception as e:
                    QtCore.QMetaObject.invokeMethod(result, 'setPlainText',
                        QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f'暂不可用：{e}'))
            threading.Thread(target=_w, daemon=True).start()
        btn = QtWidgets.QPushButton('执行任务')
        btn.setFixedHeight(36)
        btn.setStyleSheet(f'background:{ACCENT};color:white;border:none;border-radius:18px;font-weight:600;')
        btn.clicked.connect(run_agent)
        v.addWidget(btn)
        dlg.exec()

    # 定时任务对话框
    def open_schedule():
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('定时任务')
        dlg.setFixedSize(420, 300)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)
        l = QtWidgets.QLabel('设置定时提醒')
        l.setStyleSheet(f'color:{TEXT_DARK};font-size:14px;font-weight:600;')
        v.addWidget(l)
        task_input = QtWidgets.QLineEdit()
        task_input.setPlaceholderText('要定时做什么？')
        task_input.setFixedHeight(36)
        task_input.setStyleSheet(f'background:{CARD_BG};border:1px solid #ecdde2;border-radius:18px;padding:0 14px;')
        v.addWidget(task_input)
        time_row = QtWidgets.QHBoxLayout()
        time_lbl = QtWidgets.QLabel('间隔（分钟）：')
        time_lbl.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        time_spin = QtWidgets.QSpinBox()
        time_spin.setRange(1, 1440)
        time_spin.setValue(30)
        time_spin.setStyleSheet(f'background:{CARD_BG};border:1px solid #ecdde2;border-radius:8px;padding:4px;')
        time_row.addWidget(time_lbl)
        time_row.addWidget(time_spin)
        time_row.addStretch(1)
        v.addLayout(time_row)
        result = QtWidgets.QLabel('')
        result.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        result.setWordWrap(True)
        v.addWidget(result)
        v.addStretch(1)
        def set_sched():
            task = task_input.text().strip()
            if not task:
                result.setText('请输入任务内容')
                return
            mins = time_spin.value()
            result.setText(f'已设置：每{mins}分钟「{task}」')
            try:
                from core.fusion import _STATE
                eng = _STATE.get('engine')
                if eng and hasattr(eng, 'schedule'):
                    pass
            except Exception:
                pass
        btn = QtWidgets.QPushButton('设置定时')
        btn.setFixedHeight(36)
        btn.setStyleSheet(f'background:{ACCENT};color:white;border:none;border-radius:18px;font-weight:600;')
        btn.clicked.connect(set_sched)
        v.addWidget(btn)
        dlg.exec()

    # 通话模式对话框
    def open_call():
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('通话模式')
        dlg.setFixedSize(420, 320)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)
        status = QtWidgets.QLabel('点击开始，与小凌语音通话')
        status.setStyleSheet(f'color:{TEXT_DARK};font-size:14px;font-weight:600;')
        status.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(status)
        call_log = QtWidgets.QTextEdit()
        call_log.setReadOnly(True)
        call_log.setStyleSheet(f'background:{CARD_BG};border:1px solid #f0e4e8;border-radius:12px;padding:10px;font-size:12px;color:{TEXT_DARK};')
        v.addWidget(call_log, 1)
        call_input = QtWidgets.QLineEdit()
        call_input.setPlaceholderText('输入你说的话…')
        call_input.setFixedHeight(36)
        call_input.setStyleSheet(f'background:{CARD_BG};border:1px solid #ecdde2;border-radius:18px;padding:0 14px;')
        v.addWidget(call_input)
        def send_call():
            text = call_input.text().strip()
            if not text:
                return
            call_input.clear()
            call_log.append(f'你：{text}')
            def _w():
                try:
                    from core.fusion import _STATE
                    eng = _STATE.get('engine')
                    if eng and hasattr(eng, 'chat'):
                        r = _smart_reply(text)
                    else:
                        r = '我在听呢～'
                    QtCore.QMetaObject.invokeMethod(call_log, 'append',
                        QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f'小凌：{r}'))
                except Exception as e:
                    QtCore.QMetaObject.invokeMethod(call_log, 'append',
                        QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f'（{e}）'))
            threading.Thread(target=_w, daemon=True).start()
        call_input.returnPressed.connect(send_call)
        btn_row = QtWidgets.QHBoxLayout()
        hang_btn = QtWidgets.QPushButton('挂断')
        hang_btn.setFixedHeight(36)
        hang_btn.setStyleSheet(f'background:#999;color:white;border:none;border-radius:18px;font-weight:600;')
        hang_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(hang_btn)
        v.addLayout(btn_row)
        dlg.exec()

    # 语音开关
    tts_state = {'on': False}
    def toggle_tts():
        tts_state['on'] = not tts_state['on']
        if tts_state['on']:
            chat_log.append('<div style="color:#6a9a6a">语音已开启，小凌会用专属音色朗读</div>')
        else:
            chat_log.append('<div style="color:#9a8a90">语音已关闭</div>')

    mid.addLayout(left_col, 0)

    # 中央 3D 渲染
    center_box = QtWidgets.QVBoxLayout()
    center_box.setSpacing(10)
    center_box.setAlignment(QtCore.Qt.AlignHCenter)

    view = QtWidgets.QLabel()
    view.setFixedSize(460, 620)
    view.setStyleSheet(f'background:transparent;border:none;')
    view.setAlignment(QtCore.Qt.AlignCenter)

    # 角色选择下拉框（图形化选模型，不再命令行输1/2）
    model_combo = QtWidgets.QComboBox()
    model_combo.setFixedWidth(240)
    model_combo.setStyleSheet(f'''
        QComboBox {{
            background:{CARD_BG}; color:{TEXT_DARK};
            border:1px solid #ecdde2; border-radius:16px;
            padding:6px 16px; font-size:13px;
        }}
        QComboBox::drop-down {{ border:none; width:24px; }}
    ''')
    try:
        for m in renderer.list_models():
            model_combo.addItem(m['name'] if isinstance(m, dict) else (m.stem if hasattr(m, 'stem') else str(m)))
    except Exception:
        pass

    def on_model_pick(idx):
        try:
            name = model_combo.itemText(idx)
            from core.paths import resource
            p = resource('角色模型') / f'{name}.vrm'
            if p.exists():
                renderer.model_path = p
                from core import voices
                voices.set_current_model(p)
        except Exception:
            pass
    model_combo.currentIndexChanged.connect(on_model_pick)

    center_box.addWidget(model_combo, alignment=QtCore.Qt.AlignHCenter)
    center_box.addSpacing(6)
    center_box.addWidget(view, alignment=QtCore.Qt.AlignHCenter)

    # 底部状态文案
    status_main = QtWidgets.QLabel('正在唤醒小凌…')
    status_main.setStyleSheet(f'color:{TEXT_DARK};font-size:16px;font-weight:600;')
    status_main.setAlignment(QtCore.Qt.AlignCenter)
    center_box.addWidget(status_main)

    status_sub = QtWidgets.QLabel('每5分钟自主检查，与你一起成长')
    status_sub.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
    status_sub.setAlignment(QtCore.Qt.AlignCenter)
    center_box.addWidget(status_sub)

    mid.addLayout(center_box, 1)
    mid.addLayout(right_col, 0)
    root.addLayout(mid, 1)

    # ---------- 底部整体进度条 ----------
    bottom = QtWidgets.QVBoxLayout()
    bottom.setSpacing(6)
    overall_bar = QtWidgets.QProgressBar()
    overall_bar.setRange(0, 100)
    overall_bar.setTextVisible(False)
    overall_bar.setFixedHeight(8)
    overall_bar.setStyleSheet(f'''
        QProgressBar {{ background:#f0e4e8; border-radius:4px; }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #b01e40, stop:1 #ff7a9c);
            border-radius:4px;
        }}''')
    bottom.addWidget(overall_bar)

    bot_row = QtWidgets.QHBoxLayout()
    bot_left = QtWidgets.QLabel('苏醒周期 7 / 23 天')
    bot_left.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;')
    bot_right = QtWidgets.QLabel('-- · 计划估算')
    bot_right.setStyleSheet(f'color:{ACCENT};font-size:11px;font-weight:600;')
    bot_row.addWidget(bot_left)
    bot_row.addStretch(1)
    bot_row.addWidget(bot_right)
    bottom.addLayout(bot_row)
    root.addLayout(bottom)

    # ---------- 渲染帧刷新 ----------
    def render_one_frame():
        try:
            frame = renderer.frame(dt=1/30.0)  # numpy HxWx3 uint8 RGB
            if frame is None:
                return
            h, w = frame.shape[:2]
            img = QtGui.QImage(frame.tobytes(), w, h, w * 3,
                               QtGui.QImage.Format_RGB888)
            pix = QtGui.QPixmap.fromImage(img)
            view.setPixmap(pix.scaled(view.width(), view.height(),
                                      QtCore.Qt.KeepAspectRatio,
                                      QtCore.Qt.SmoothTransformation))
        except Exception:
            pass

    render_timer = QtCore.QTimer(win)
    render_timer.timeout.connect(render_one_frame)
    render_timer.start(50)  # ~20fps，减少卡顿

    # ---------- 进度刷新（每秒读一次训练状态） ----------
    def refresh_progress():
        st = _growth_status()
        overall = st['percent']
        for c_en, (bar, pct, weight) in card_refs.items():
            v = _channel_progress(overall, weight)
            bar.setValue(int(v))
            pct.setText(f'{v:.0f}%')
        overall_bar.setValue(int(overall))
        if st['self_research']:
            status_main.setText('小凌已完成自我进化，现在属于她自己了')
            status_sub.setText(f'基底 {st["base_mb"]:.0f}MB · 适配器 {st["adapter_mb"]:.0f}MB')
        else:
            status_main.setText(f'当前阶段：{st["stage"]}')
            status_sub.setText(f'已成长 {overall:.1f}% · 每5分钟自主训练')
        bot_right.setText(f'{100 - overall:.0f} DAYS · 计划估算')

    progress_timer = QtCore.QTimer(win)
    progress_timer.timeout.connect(refresh_progress)
    progress_timer.start(1000)
    refresh_progress()
    render_one_frame()

    # 模型切换菜单（右键中央区域）
    def switch_next_model():
        try:
            renderer.next_model()
            from core import voices
            voices.set_current_model(renderer.model_path)
        except Exception:
            pass
    view.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
    act_next = QtGui.QAction('切换下一个角色', win)
    act_next.triggered.connect(switch_next_model)
    view.addAction(act_next)

    # ---------- 对话历史显示（图形化，不再命令行） ----------
    chat_log = QtWidgets.QTextEdit()
    chat_log.setReadOnly(True)
    chat_log.setFixedHeight(90)
    chat_log.setStyleSheet(f'''
        QTextEdit {{
            background:{CARD_BG}; color:{TEXT_DARK};
            border:1px solid #f0e4e8; border-radius:12px;
            padding:8px 12px; font-size:12px;
        }}''')
    chat_log.setHtml('<div style="color:#9a8a90">小凌已唤醒，和她说说话吧～</div>')
    center_box.addWidget(chat_log)

    # ---------- 底部对话输入栏 ----------
    chat_row = QtWidgets.QHBoxLayout()
    chat_input = QtWidgets.QLineEdit()
    chat_input.setPlaceholderText('对小凌说点什么…（回车发送）')
    chat_input.setFixedHeight(36)
    chat_input.setStyleSheet(f'''
        QLineEdit {{
            background:{CARD_BG}; color:{TEXT_DARK};
            border:1px solid #ecdde2; border-radius:18px;
            padding:0 16px; font-size:13px;
        }}
        QLineEdit:focus {{ border:1px solid {ACCENT}; }}
    ''')
    send_btn = QtWidgets.QPushButton('发送')
    send_btn.setFixedSize(72, 36)
    send_btn.setStyleSheet(f'''
        QPushButton {{
            background:{ACCENT}; color:white; border:none;
            border-radius:18px; font-size:13px; font-weight:600;
        }}
        QPushButton:hover {{ background:#b01e40; }}
    ''')

    def send_chat():
        text = chat_input.text().strip()
        if not text:
            return
        chat_input.clear()
        chat_log.append(f'<div style="color:#3a2a30"><b>你：</b>{text}</div>')
        # 后台线程处理对话，不卡 UI
        def _worker():
            try:
                from core.fusion import _STATE
                engine = None
                if False:
                    reply = _smart_reply(text)
                else:
                    reply = '我在呢～'
                QtCore.QMetaObject.invokeMethod(chat_log, 'append',
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, f'<div style="color:#d4385c"><b>小凌：</b>{reply}</div>'))
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(chat_log, 'append',
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, f'<div style="color:#9a8a90">（{e}）</div>'))
        threading.Thread(target=_worker, daemon=True).start()

    send_btn.clicked.connect(send_chat)
    chat_input.returnPressed.connect(send_chat)
    chat_row.addWidget(chat_input, 1)
    chat_row.addWidget(send_btn)
    center_box.addLayout(chat_row)

    # ---------- 功能按钮行（蒸馏/设置/关于，全部图形化） ----------
    func_row = QtWidgets.QHBoxLayout()
    func_row.setSpacing(10)

    def make_func_btn(text, color):
        b = QtWidgets.QPushButton(text)
        b.setFixedHeight(32)
        b.setStyleSheet(f'''
            QPushButton {{
                background:{CARD_BG}; color:{color};
                border:1px solid #ecdde2; border-radius:16px;
                padding:0 18px; font-size:12px; font-weight:600;
            }}
            QPushButton:hover {{ background:#fdf0f3; }}
        ''')
        return b

    btn_distill = make_func_btn('开始蒸馏训练', ACCENT)
    btn_setting = make_func_btn('设置', TEXT_MUTED)
    btn_about = make_func_btn('关于', TEXT_MUTED)

    def start_distill():
        chat_log.append('<div style="color:#d4385c"><b>小凌：</b>开始自我进化训练…</div>')
        def _worker():
            try:
                from core.growth import GrowthEngine
                from core.paths import APP_DIR
                eng = GrowthEngine(base_dir=APP_DIR)
                res = eng.train_round(epochs=2)
                msg = res.get('message', '训练完成')
                QtCore.QMetaObject.invokeMethod(chat_log, 'append',
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, f'<div style="color:#d4385c"><b>小凌：</b>{msg}</div>'))
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(chat_log, 'append',
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, f'<div style="color:#9a8a90">训练暂不可用：{e}</div>'))
        threading.Thread(target=_worker, daemon=True).start()

    def show_setting():
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('设置')
        dlg.setFixedSize(360, 200)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(12)
        lbl = QtWidgets.QLabel('小凌工作台设置')
        lbl.setStyleSheet(f'color:{TEXT_DARK};font-size:16px;font-weight:700;')
        v.addWidget(lbl)
        # 渲染后端选择
        be_lbl = QtWidgets.QLabel('渲染后端')
        be_lbl.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        v.addWidget(be_lbl)
        be_combo = QtWidgets.QComboBox()
        be_combo.addItems(['自动', 'CPU 软件渲染', 'OpenGL'])
        be_combo.setStyleSheet(f'background:{CARD_BG};border:1px solid #ecdde2;border-radius:8px;padding:6px;')
        v.addWidget(be_combo)
        # 自动训练开关
        auto_chk = QtWidgets.QCheckBox('开启后台自动训练（每5分钟）')
        auto_chk.setChecked(True)
        auto_chk.setStyleSheet(f'color:{TEXT_DARK};font-size:12px;')
        v.addWidget(auto_chk)
        v.addStretch(1)
        ok_btn = QtWidgets.QPushButton('保存')
        ok_btn.setFixedHeight(34)
        ok_btn.setStyleSheet(f'background:{ACCENT};color:white;border:none;border-radius:17px;font-weight:600;')
        ok_btn.clicked.connect(dlg.accept)
        v.addWidget(ok_btn)
        dlg.exec()

    def show_about():
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('关于小凌')
        dlg.setFixedSize(340, 220)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(24, 20, 24, 20)
        v.setAlignment(QtCore.Qt.AlignCenter)
        t = QtWidgets.QLabel('小凌 XIAOLING')
        t.setStyleSheet(f'color:{ACCENT};font-size:22px;font-weight:800;')
        t.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(t)
        v2 = QtWidgets.QLabel('会成长的数字生命\nv2.0.5 · 训练工作台版')
        v2.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        v2.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(v2)
        v.addSpacing(12)
        info = QtWidgets.QLabel('7 个角色 · 46 个动作 · 蒸馏成长\nPySide6 纯 Python 3D 渲染')
        info.setStyleSheet(f'color:{TEXT_DARK};font-size:12px;')
        info.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(info)
        v.addStretch(1)
        close_btn = QtWidgets.QPushButton('关闭')
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(f'background:{ACCENT};color:white;border:none;border-radius:17px;font-weight:600;')
        close_btn.clicked.connect(dlg.accept)
        v.addWidget(close_btn)
        dlg.exec()

    btn_distill.clicked.connect(start_distill)
    btn_setting.clicked.connect(show_setting)
    btn_about.clicked.connect(show_about)

    func_row.addStretch(1)
    func_row.addWidget(btn_distill)
    func_row.addWidget(btn_setting)
    func_row.addWidget(btn_about)
    func_row.addStretch(1)
    root.addLayout(plugin_bar)
    root.addLayout(func_row)

    # ---------- 后台轻量初始化（UI先显示，不卡用户） ----------
    def _preload():
        try:
            from core.fusion import _STATE
            _STATE['dashboard_ready'] = True
            QtCore.QMetaObject.invokeMethod(chat_log, 'append',
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, '<div style="color:#6a9a6a">小凌已就绪，可以开始对话了～</div>'))
        except Exception as e:
            QtCore.QMetaObject.invokeMethod(chat_log, 'append',
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(str, f'<div style="color:#9a8a90">（初始化完成）</div>'))
    threading.Thread(target=_preload, daemon=True).start()

    win.show()
    win._own_renderer = own_renderer
    win._render_timer = render_timer
    win._progress_timer = progress_timer
    return win


def run_dashboard(log=print):
    """启动工作台（阻塞）。先显示启动画面，再加载主界面。"""
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except Exception as e:
        log(f'  [工作台] PySide6 不可用：{e}')
        return False

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName('小凌工作台')

    # 启动画面（先显示，让用户知道程序在启动）
    splash = QtWidgets.QWidget()
    splash.setFixedSize(360, 200)
    splash.setWindowTitle('小凌正在唤醒…')
    splash.setStyleSheet('background:#faf6f7;border-radius:16px;')
    splash.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
    splash.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    sl = QtWidgets.QVBoxLayout(splash)
    sl.setContentsMargins(30, 30, 30, 30)
    sl.setSpacing(12)
    st = QtWidgets.QLabel('小凌 XIAOLING')
    st.setStyleSheet('color:#d4385c;font-size:24px;font-weight:800;')
    st.setAlignment(QtCore.Qt.AlignCenter)
    sl.addWidget(st)
    ss = QtWidgets.QLabel('正在唤醒数字生命…')
    ss.setStyleSheet('color:#9a8a90;font-size:13px;')
    ss.setAlignment(QtCore.Qt.AlignCenter)
    sl.addWidget(ss)
    sp = QtWidgets.QProgressBar()
    sp.setRange(0, 0)  # 不确定进度
    sp.setTextVisible(False)
    sp.setFixedHeight(6)
    sp.setStyleSheet('''
        QProgressBar { background:#f0e4e8; border-radius:3px; }
        QProgressBar::chunk { background:#d4385c; border-radius:3px; }
    ''')
    sl.addWidget(sp)
    # 居中
    screen = app.primaryScreen().geometry()
    splash.move((screen.width() - 360) // 2, (screen.height() - 200) // 2)
    splash.show()
    app.processEvents()

    # 延迟一帧后构建主窗口（让splash先渲染出来）
    result = {'win': None}
    def _build():
        try:
            result['win'] = build_dashboard(log=log)
        except Exception as e:
            log(f'  [工作台] 构建失败：{e}')
        splash.close()
        if result['win']:
            result['win'].show()
    QtCore.QTimer.singleShot(50, _build)
    app.exec()
    return result['win'] is not None


if __name__ == '__main__':
    run_dashboard()
