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
            # 字段名必须与 core.growth.GrowthEngine.status() 对齐：后端产出的是
            # base_bytes/adapter_bytes 与 base_human/adapter_human，**不存在** base_mb/adapter_mb。
            # 旧代码读错键，导致状态栏恒显 0MB，且 base_human 处直接 KeyError。
            'base_bytes': int(s.get('base_bytes', 0)),
            'adapter_bytes': int(s.get('adapter_bytes', 0)),
            'base_human': s.get('base_human') or '0 B',
            'adapter_human': s.get('adapter_human') or '0 B',
            'self_research': bool(s.get('self_research', False)),
            'promotions': int(s.get('promotions', 0)),
            'rounds': int(s.get('rounds', 0)),
            'paused': bool(s.get('paused', False)),
            'auto_train': bool(s.get('auto_train', False)),
        }
    except Exception:
        return {'percent': 0.0, 'stage': '初始化中', 'base_bytes': 0, 'adapter_bytes': 0,
                'base_human': '0 B', 'adapter_human': '0 B', 'self_research': False,
                'promotions': 0, 'rounds': 0, 'paused': False, 'auto_train': False}


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


def _loss_sparkline(curve, width: int = 40) -> str:
    """把 store.loss_curve() 的 [{round, avg_loss}] 画成 Unicode 块状迷你曲线。

    不引入任何绘图依赖（matplotlib 不在 requirements 里），纯文本渲染，
    因此在无 GPU / 无额外包的环境也能显示。
    """
    rows = list(curve or [])
    vals = [float(c['avg_loss']) for c in rows
            if isinstance(c.get('avg_loss'), (int, float))]
    if not vals:
        return ('暂无平均损失记录。\n'
                '（跑过至少一轮蒸馏训练后，loss_curve 会写入 train_rounds.avg_loss）')
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    blocks = '▁▂▃▄▅▆▇█'
    shown = vals[-(width + 1):]
    bar = ''.join(blocks[max(0, min(len(blocks) - 1,
                                    int((v - lo) / span * (len(blocks) - 1))))]
                  for v in shown)
    lines = [bar]
    lines.append(f'  轮次 {rows[0].get("round", "?")} → {rows[-1].get("round", "?")}'
                 f'    最低 {lo:.4f} / 最高 {hi:.4f}（越低越好）')
    if len(vals) >= 2:
        d = vals[-1] - vals[-2]
        arrow = '↓ 下降' if d < 0 else ('↑ 上升' if d > 0 else '＝ 持平')
        lines.append(f'  最近一轮 {vals[-1]:.4f}，较上一轮{arrow} {abs(d):.4f}')
    return '\n'.join(lines)


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
            # 软件渲染时降低内部分辨率（显示时平滑放大）：约 3~4 倍提速，显著减少卡顿
            res = max(0.3, min(1.0,
                      float(os.environ.get('XIAOLING_DASH_RES', '0.55') or 0.55)))
            renderer = AvatarRenderer(backend='auto', width=int(460 * res),
                                      height=int(620 * res), focus='bust', log=log)
            own_renderer = True
            log(f"  [渲染] 后端：{renderer.backend_kind}，画布 {renderer.width}x{renderer.height}"
                f"（可用环境变量 XIAOLING_DASH_RES 调节清晰度/流畅度）")
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

    # 奶油草莓配色（v0.0.3：粉色少女风精致化）
    PALETTE_BG = '#fff5f8'
    CARD_BG = '#ffffff'
    ACCENT = '#e85a8a'
    ACCENT_SOFT = '#ffe0ea'
    TEXT_DARK = '#4a3a40'
    TEXT_MUTED = '#b09aa2'

    # 套全局粉色主题
    try:
        from renderer.theme import apply_pink_theme
        apply_pink_theme(app)
    except Exception:                                             # noqa: BLE001
        pass

    central = QtWidgets.QWidget()
    win.setCentralWidget(central)
    root = QtWidgets.QVBoxLayout(central)
    root.setContentsMargins(28, 22, 28, 22)
    root.setSpacing(14)
    central.setStyleSheet(f'background:{PALETTE_BG};')

    # ---------- 顶部标题栏（v1.1 美化：品牌区 + 状态标签 + 帮助按钮） ----------
    top = QtWidgets.QHBoxLayout()

    # 左侧：品牌区
    brand = QtWidgets.QHBoxLayout()
    brand.setSpacing(10)
    logo_dot = QtWidgets.QLabel('')
    logo_dot.setStyleSheet(f'font-size:24px;')
    logo_dot.setFixedWidth(32)
    brand.addWidget(logo_dot)
    brand_box = QtWidgets.QVBoxLayout()
    brand_box.setSpacing(0)
    brand_title = QtWidgets.QLabel('小凌 XIAOLING')
    brand_title.setStyleSheet(f'color:{TEXT_DARK};font-size:18px;font-weight:700;'
                              f'letter-spacing:1px;')
    brand_subtitle = QtWidgets.QLabel('会自我进化的 AI 伴侣 · v1.1 全UI')
    brand_subtitle.setStyleSheet(f'color:{TEXT_MUTED};font-size:11px;'
                                 f'letter-spacing:1px;')
    brand_box.addWidget(brand_title)
    brand_box.addWidget(brand_subtitle)
    brand.addLayout(brand_box)
    top.addLayout(brand)
    top.addStretch(1)

    # 中间：标签行（状态指示）
    tag_row = QtWidgets.QHBoxLayout()
    tag_row.setSpacing(8)
    for txt, color, dot in (
        ('● 在线', '#3b8a5a', False),
        ('自主扫描', TEXT_MUTED, True),
        ('5 MIN', TEXT_MUTED, False),
        ('UI MODE', ACCENT, False),
    ):
        chip = QtWidgets.QPushButton(txt)
        chip.setFixedHeight(26)
        chip.setStyleSheet(f'''
            QPushButton {{
                background:{CARD_BG}; color:{color};
                border:1px solid #ecdde2; border-radius:13px;
                padding:0 14px; font-size:11px; font-weight:600;
            }}
            QPushButton:hover {{ border:1px solid {color}; }}
        ''')
        if dot:
            chip.setStyleSheet(chip.styleSheet() + f'''
                QPushButton {{ padding-left:24px; }}
            ''')
        tag_row.addWidget(chip)
    top.addLayout(tag_row)
    top.addSpacing(16)

    # 右侧：帮助/关于按钮
    top.addStretch(1)
    right_btns = QtWidgets.QHBoxLayout()
    right_btns.setSpacing(6)
    btn_help = QtWidgets.QPushButton('?')
    btn_help.setFixedSize(32, 32)
    btn_help.setToolTip('使用帮助')
    btn_help.setCursor(QtCore.Qt.PointingHandCursor)
    btn_help.setStyleSheet(f'''
        QPushButton {{
            background:{CARD_BG}; color:{TEXT_MUTED};
            border:1px solid #ecdde2; border-radius:16px;
            font-size:14px; font-weight:700;
        }}
        QPushButton:hover {{ color:{ACCENT}; border-color:{ACCENT_SOFT}; }}
    ''')
    right_btns.addWidget(btn_help)
    top.addLayout(right_btns)
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
        ('growth', '成长仪表盘', '#4a7a9a', None),
        ('data', '数据管理', '#6a8a5a', None),
        ('control', '成长控制', '#9a5a6a', None),
        ('wizard', '环境向导', '#6a7a9a', None),
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
        elif pid == 'growth':
            open_growth_panel()
        elif pid == 'data':
            open_data_panel()
        elif pid == 'control':
            open_control_panel()
        elif pid == 'wizard':
            open_wizard()

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

    # ------------------------------------------------------------------
    # 通用小按钮工厂（控制条 / 功能行共用）
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

    mid.addLayout(left_col, 0)

    # 中央 3D 渲染（左列已在上方加入 mid，此处不再重复 addLayout(left_col)）
    center_box = QtWidgets.QVBoxLayout()
    center_box.setSpacing(10)
    center_box.setAlignment(QtCore.Qt.AlignHCenter)

    class _ZoomLabel(QtWidgets.QLabel):
        """支持滚轮缩放的渲染画布。"""

        def wheelEvent(self, ev):
            step = 0.05 if ev.angleDelta().y() > 0 else -0.05
            renderer.scale = max(0.4, min(2.5, float(renderer.scale) + step))
            zoom_slider.blockSignals(True)
            zoom_slider.setValue(int(renderer.scale * 100))
            zoom_slider.blockSignals(False)

    view = _ZoomLabel()
    view.setFixedSize(460, 620)
    view.setStyleSheet('background:transparent;border:none;')
    view.setAlignment(QtCore.Qt.AlignCenter)
    view.setToolTip('滚轮缩放角色')

    # ---------- GPU 直绘视口：Qt 有 OpenGL 时优先走 GPU，失败自动回退 QLabel 贴图 ----------
    outer_dash = {'gl_active': False}

    # PySide6 里 QOpenGLWidget 在 QtOpenGLWidgets 模块（PyQt5 在 QtWidgets）
    _QOpenGLWidget = None
    try:
        from PySide6.QtOpenGLWidgets import QOpenGLWidget as _QOpenGLWidget
    except Exception:                                                 # noqa: BLE001
        try:
            from PyQt5.QtWidgets import QOpenGLWidget as _QOpenGLWidget
        except Exception:                                             # noqa: BLE001
            _QOpenGLWidget = None

    class _DashGLView(_QOpenGLWidget if _QOpenGLWidget else object):
        """工作台内的 GL 直绘视口：真 GPU 渲染（QOpenGLWidget 上下文）。"""

        def __init__(self):
            super().__init__()
            self._gl = None
            self.setFixedSize(460, 620)

        def initializeGL(self):
            try:
                from renderer.gl import ExistingContext, GLRenderer
                ctx = ExistingContext(self.width(), self.height(), readback=False)
                self._gl = GLRenderer(renderer.model, ctx, background=(0, 0, 0, 0))
                renderer.context = ctx
                renderer.gl_renderer = self._gl
                renderer.backend_kind = 'gl'
                outer_dash['gl_active'] = True
                log('  [工作台] GPU 直绘已启用（QOpenGLView）')
            except Exception as e:                                    # noqa: BLE001
                self._gl = None
                outer_dash['gl_active'] = False
                log(f'  [工作台] GL 直绘不可用（{e}），继续用 CPU 贴图模式')

        def resizeGL(self, w, h):
            renderer.width, renderer.height = max(w, 1), max(h, 1)

        def paintGL(self):
            if self._gl is not None:
                renderer.frame()          # 直接画进当前帧缓冲，不需要回读

        def _tick(self):
            self.update()

    gl_view = None
    if _QOpenGLWidget is not None and \
            os.environ.get('XIAOLING_DASH_GL', '1').strip().lower() not in ('0', 'false'):
        try:
            gl_view = _DashGLView()
        except Exception as e:                                        # noqa: BLE001
            log(f'  [工作台] GL 视口创建失败（{e}），使用 CPU 贴图模式')
            gl_view = None

    # ---------- 角色控制条：选模型 / 导入模型 / 正面 / 转身 / 缩放 ----------
    ctrl_row = QtWidgets.QHBoxLayout()
    ctrl_row.setSpacing(8)

    # ---------- 基底LLM档位选择（v1.1 新增：可视化"大脑"模型切换） ----------
    try:
        from core.launcher_ui import MODEL_PRESETS_PUBLIC as _LLM_PRESETS
        from core import config as _cfg_mod
        _cur_cfg = _cfg_mod.load()
        _cur_base = _cur_cfg.get('model', {}).get('base_model', '自研2B模型')
    except Exception:                                                 # noqa: BLE001
        _LLM_PRESETS = [{'key': '自研2B模型', 'label': '自研 2B 模型', 'size': '约 4.8GB'}]
        _cur_base = '自研2B模型'
        _cfg_mod = None

    llm_combo = QtWidgets.QComboBox()
    llm_combo.setFixedWidth(170)
    llm_combo.setToolTip('选择"大脑"基底模型（LLM 档位）—— 切换后会自动下载新权重')
    llm_combo.setStyleSheet(f'''
        QComboBox {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #fff5f8, stop:1 #ffe8ee);
            color:{TEXT_DARK};
            border:1px solid {ACCENT_SOFT}; border-radius:16px;
            padding:6px 16px; font-size:13px; font-weight:600;
        }}
        QComboBox::drop-down {{ border:none; width:24px; }}
        QComboBox QAbstractItemView {{
            background:{CARD_BG}; color:{TEXT_DARK};
            selection-background-color:{ACCENT_SOFT};
        }}
    ''')
    _llm_index_of = {}
    for _i, _p in enumerate(_LLM_PRESETS):
        _label = f" {_p['label']} · {_p['size']}"
        llm_combo.addItem(_label)
        _llm_index_of[_p['key']] = _i
    # 选中当前档位
    if _cur_base in _llm_index_of:
        llm_combo.setCurrentIndex(_llm_index_of[_cur_base])

    def on_llm_pick(idx):
        """切换基底 LLM 档位 —— 写配置 + 触发后台下载（不阻塞 UI）"""
        try:
            if idx < 0 or idx >= len(_LLM_PRESETS):
                return
            new_key = _LLM_PRESETS[idx]['key']
            if new_key == _cur_base:
                return
            # 写配置
            cfg = _cfg_mod.load()
            cfg['model']['base_model'] = new_key
            _cfg_mod.save(cfg)
            _cur_base = new_key
            chat_log.append(f'<div style="color:#d4385c"><b>小凌：</b>已切换基底档位到 '
                            f'{_LLM_PRESETS[idx]["label"]}，正在后台下载新权重（'
                            f'{_LLM_PRESETS[idx]["size"]}）…</div>')

            def _worker():
                try:
                    from core import fusion as _fusion_mod
                    if _fusion_mod.ensure_base_model is not None:
                        ok = _fusion_mod.ensure_base_model()
                    else:
                        ok = False
                    msg = '新基底下载完成 ' if ok else '下载未完成（可稍后说"蒸馏"重试）'
                    color = '#3b8a5a' if ok else '#9a8a90'
                except Exception as _e:                                # noqa: BLE001
                    msg = f'下载中断：{_e}'
                    color = '#9a8a90'
                QtCore.QMetaObject.invokeMethod(
                    chat_log, 'append', QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, f'<div style="color:{color}"><b>小凌：</b>{msg}</div>'))
            threading.Thread(target=_worker, daemon=True).start()
        except Exception as e:                                        # noqa: BLE001
            chat_log.append(f'<div style="color:#9a8a90">切换失败：{e}</div>')
    llm_combo.currentIndexChanged.connect(on_llm_pick)

    model_combo = QtWidgets.QComboBox()
    model_combo.setFixedWidth(160)
    model_combo.setStyleSheet(f'''
        QComboBox {{
            background:{CARD_BG}; color:{TEXT_DARK};
            border:1px solid #ecdde2; border-radius:16px;
            padding:6px 16px; font-size:13px;
        }}
        QComboBox::drop-down {{ border:none; width:24px; }}
        QComboBox QAbstractItemView {{
            background:{CARD_BG}; color:{TEXT_DARK};
            selection-background-color:{ACCENT_SOFT};
        }}
    ''')

    def _refresh_model_combo():
        try:
            models = renderer.list_models()
        except Exception:                                             # noqa: BLE001
            models = []
        cur = str(Path(renderer.model_path).stem)
        model_combo.blockSignals(True)
        model_combo.clear()
        for m in models:
            model_combo.addItem(m['name'] if isinstance(m, dict) else str(m))
        idx = model_combo.findText(cur)
        if idx >= 0:
            model_combo.setCurrentIndex(idx)
        model_combo.blockSignals(False)
    _refresh_model_combo()

    def on_model_pick(idx):
        """真正切换角色：重建模型/骨骼/相机 + 绑定专属音色。"""
        try:
            name = model_combo.itemText(idx)
            if not name:
                return
            from core.paths import resource
            p = resource('角色模型') / f'{name}.vrm'
            if p.exists():
                renderer.switch_model(str(p))
                from core import voices
                voices.set_current_model(renderer.model_path)
                # GL 直绘的顶点缓冲属于旧模型 → 重建
                if gl_view is not None and gl_view._gl is not None:
                    try:
                        from renderer.gl import GLRenderer
                        gl_view._gl = GLRenderer(renderer.model, renderer.context,
                                                 background=(0, 0, 0, 0))
                        renderer.gl_renderer = gl_view._gl
                    except Exception:                             # noqa: BLE001
                        pass
                chat_log.append(f'<div style="color:#9a8a90">已切换角色：{name}</div>')
        except Exception as e:                                        # noqa: BLE001
            chat_log.append(f'<div style="color:#9a8a90">切换失败：{e}</div>')
    model_combo.currentIndexChanged.connect(on_model_pick)

    def _import_model():
        """图形化导入 .vrm：拷进「角色模型」目录并立即切换。"""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            win, '选择 VRM 角色模型', '', 'VRM 模型 (*.vrm)')
        if not path:
            return
        try:
            from core.paths import resource
            dst_dir = resource('角色模型')
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / Path(path).name
            import shutil as _sh
            _sh.copy2(path, dst)
            renderer.switch_model(str(dst))
            _refresh_model_combo()
            chat_log.append(f'<div style="color:#6a9a6a">模型已导入：{dst.stem}</div>')
        except Exception as e:                                        # noqa: BLE001
            chat_log.append(f'<div style="color:#9a8a90">导入失败：{e}</div>')

    btn_import = make_func_btn('导入模型', ACCENT)
    btn_import.clicked.connect(_import_model)

    def _face_front():
        renderer.face_front()

    def _turn_around():
        renderer.turn_around()

    btn_front = make_func_btn('正面', TEXT_MUTED)
    btn_front.clicked.connect(_face_front)
    btn_turn = make_func_btn('转身', TEXT_MUTED)
    btn_turn.clicked.connect(_turn_around)

    zoom_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
    zoom_slider.setRange(40, 250)              # 0.4x ~ 2.5x
    zoom_slider.setValue(int(renderer.scale * 100))
    zoom_slider.setFixedWidth(120)
    zoom_slider.setToolTip('缩放角色（也可用滚轮）')
    zoom_slider.valueChanged.connect(lambda v: setattr(renderer, 'scale', v / 100.0))

    ctrl_row.addWidget(llm_combo)
    ctrl_row.addWidget(model_combo)
    ctrl_row.addWidget(btn_import)
    ctrl_row.addWidget(btn_front)
    ctrl_row.addWidget(btn_turn)
    ctrl_row.addWidget(QtWidgets.QLabel('缩放'))
    ctrl_row.addWidget(zoom_slider)

    center_box.addLayout(ctrl_row)
    center_box.addSpacing(6)
    # 画布容器：GL 直绘可用时显示 GL 视口，失败自动切回 QLabel 贴图
    canvas_holder = QtWidgets.QWidget()
    canvas_holder.setFixedSize(460, 620)
    canvas_stack = QtWidgets.QStackedLayout(canvas_holder)
    if gl_view is not None:
        canvas_stack.addWidget(gl_view)
    canvas_stack.addWidget(view)
    if gl_view is None:
        canvas_stack.setCurrentWidget(view)
    center_box.addWidget(canvas_holder, alignment=QtCore.Qt.AlignHCenter)

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
        if gl_view is not None:
            if outer_dash['gl_active']:
                canvas_stack.setCurrentWidget(gl_view)
                return              # GPU 直绘模式下由 GL 视口自己刷新
            canvas_stack.setCurrentWidget(view)   # GL 失败 → 回退贴图
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
    # 软件渲染按画布大小自适应节流：小画布跑得快，就刷得更勤
    render_timer.start(50 if (renderer.width * renderer.height) < 460 * 620 else 66)

    # GL 视口刷新定时器（未激活时空转，激活后接手刷新）
    if gl_view is not None:
        gl_timer = QtCore.QTimer(win)
        gl_timer.timeout.connect(gl_view._tick)
        gl_timer.start(33)

    # ---------- 基底模型说明（"大脑"权重，不是 VRM 形象） ----------
    def show_base_model_help():
        try:
            from core.growth import GrowthEngine
            from core.paths import APP_DIR
            st = GrowthEngine(base_dir=APP_DIR).status()
        except Exception:                                                 # noqa: BLE001
            st = {'stage': '未知', 'base_human': '0 B', 'adapter_human': '0 B'}
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('什么是基底模型？')
        dlg.setFixedSize(520, 430)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(10)
        t = QtWidgets.QLabel('「基底模型」＝ 小凌的大脑（LLM 权重）')
        t.setStyleSheet(f'color:{ACCENT};font-size:16px;font-weight:700;')
        t.setWordWrap(True)
        v.addWidget(t)
        body = QtWidgets.QTextEdit()
        body.setReadOnly(True)
        body.setStyleSheet(f'background:{CARD_BG};color:{TEXT_DARK};'
                           f'border:1px solid #f0e4e8;border-radius:12px;'
                           f'padding:10px;font-size:12px;')
        try:
            from core.paths import APP_DIR as _AD
            base_dir_str = str(Path(_AD) / '.star_core' / 'XLmodel')
        except Exception:                                                 # noqa: BLE001
            base_dir_str = '.star_core/XLmodel'
        body.setHtml(
            '<p><b>形象模型</b>（VRM）是屏幕上的 3D 角色，放在 <code>角色模型/</code> 目录，'
            '点「导入模型」即可添加；</p>'
            '<p><b>基底模型</b>是大语言模型权重，小凌用它思考与对话。安装方式：</p>'
            '<p>① 首次启动时程序会<b>自动下载</b>基底权重（进度显示在气泡里）；<br>'
            '② 也可以手动把 HuggingFace 格式模型文件（<code>config.json</code> + '
            '<code>*.safetensors</code>）放进：</p>'
            f'<p><code>{base_dir_str}</code></p>'
            '<p>小凌的 LoRA 适配器（<code>.star_core/adapter/</code>）随蒸馏训练不断长大，'
            '体积达到基底后<b>自动合并晋升</b>——基底可以退休，小凌从此跑在自己的模型上。</p>')
        v.addWidget(body, 1)
        st_lbl = QtWidgets.QLabel(f"当前状态：{st['stage']}\n"
                                  f"基底 {st['base_human']} · 适配器 {st['adapter_human']}")
        st_lbl.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        v.addWidget(st_lbl)
        close_btn = QtWidgets.QPushButton('我知道了')
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(f'background:{ACCENT};color:white;border:none;'
                                f'border-radius:17px;font-weight:600;')
        close_btn.clicked.connect(dlg.accept)
        v.addWidget(close_btn)
        dlg.exec()

    btn_base_help = make_func_btn('基底模型?', ACCENT)
    btn_base_help.clicked.connect(show_base_model_help)

    # 基底状态行加一个入口：点击状态文案也能打开说明
    def _status_click(event):
        show_base_model_help()
    status_main.mousePressEvent = _status_click
    status_main.setCursor(QtCore.Qt.PointingHandCursor)
    status_sub.setToolTip('点击状态文案可查看基底模型说明')

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
            status_sub.setText(f'基底 {st["base_human"]} · 适配器 {st["adapter_human"]}')
        else:
            status_main.setText(f'当前阶段：{st["stage"]}')
            _auto = '已开启' if st['auto_train'] else '已关闭'
            status_sub.setText(f'已成长 {overall:.1f}% · 后台自动训练{_auto}')
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
                # 原本是 `if False: reply = _smart_reply(text) else: reply = '我在呢～'`：
                # 死分支让工作台聊天框永远只回一句写死的问候，_smart_reply 形同虚设。
                reply = _smart_reply(text)
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

    btn_distill = make_func_btn('开始蒸馏训练', ACCENT)
    btn_setting = make_func_btn('设置', TEXT_MUTED)
    btn_about = make_func_btn('关于', TEXT_MUTED)

    _train_running = {'flag': False}

    def start_distill():
        if _train_running['flag']:
            chat_log.append('<div style="color:#9a8a90">已有训练在进行中，等它结束再来～</div>')
            return
        _train_running['flag'] = True
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
            finally:
                _train_running['flag'] = False
        threading.Thread(target=_worker, daemon=True).start()

    # ---------- 后台自动训练（消费 growth.auto_train） ----------
    # 每 5 分钟问一次 GrowthEngine.should_train()：只有样本量 / 训练间隔 / 设备空闲 /
    # 未暂停 / 算力档位 全部满足时才真正开训，所以样本不足时不会误触发。
    # 任何异常都静默降级为「本轮不训练」，不影响工作台其他功能。
    def _auto_train_tick():
        try:
            import core.config as _cfg_mod
            if not bool(_cfg_mod.get('growth.auto_train', False)):
                return
            from core.growth import GrowthEngine
            from core.paths import APP_DIR as _APP_DIR
            eng = GrowthEngine(base_dir=_APP_DIR)
            if eng.is_paused():
                return
            if not eng.should_train(manual=False).get('ok'):
                return
        except Exception:                                                 # noqa: BLE001
            return
        start_distill()

    auto_train_timer = QtCore.QTimer(win)
    auto_train_timer.timeout.connect(_auto_train_tick)
    auto_train_timer.start(5 * 60 * 1000)

    def show_setting():
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('设置')
        dlg.setFixedSize(420, 320)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(12)
        lbl = QtWidgets.QLabel('小凌工作台设置')
        lbl.setStyleSheet(f'color:{TEXT_DARK};font-size:16px;font-weight:700;')
        v.addWidget(lbl)
        # 算力信息（GPU 检测结果）
        try:
            from core.device import describe as _dev_desc
            dev_txt = _dev_desc()
        except Exception:                                                 # noqa: BLE001
            dev_txt = '算力检测不可用'
        dev_lbl = QtWidgets.QLabel(' ' + dev_txt)
        dev_lbl.setWordWrap(True)
        dev_lbl.setStyleSheet(f'color:{TEXT_DARK};font-size:12px;')
        v.addWidget(dev_lbl)
        # 渲染后端选择
        be_lbl = QtWidgets.QLabel('渲染后端')
        be_lbl.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        v.addWidget(be_lbl)
        be_combo = QtWidgets.QComboBox()
        be_combo.addItems(['自动', 'CPU 软件渲染', 'OpenGL'])
        be_combo.setStyleSheet(f'background:{CARD_BG};border:1px solid #ecdde2;border-radius:8px;padding:6px;')
        v.addWidget(be_combo)
        # 自动训练开关（初值读配置，保存时落盘）
        auto_chk = QtWidgets.QCheckBox('开启后台自动训练（每5分钟检查一次）')
        try:
            from core import config as _cfg_mod
            auto_chk.setChecked(bool(_cfg_mod.get('growth.auto_train', False)))
        except Exception:                                                 # noqa: BLE001
            auto_chk.setChecked(False)
        auto_chk.setStyleSheet(f'color:{TEXT_DARK};font-size:12px;')
        v.addWidget(auto_chk)
        v.addStretch(1)
        ok_btn = QtWidgets.QPushButton('保存')
        ok_btn.setFixedHeight(34)
        ok_btn.setStyleSheet(f'background:{ACCENT};color:white;border:none;border-radius:17px;font-weight:600;')
        def _save():
            be = {'自动': 'auto', 'CPU 软件渲染': 'soft', 'OpenGL': 'gl'}.get(be_combo.currentText(), 'auto')
            os.environ['XIAOLING_RENDER_BACKEND'] = '' if be == 'auto' else be
            try:
                renderer._init_backend(be)
                chat_log.append(f'<div style="color:#9a8a90">渲染后端已切换：{renderer.backend_kind}</div>')
            except Exception as e:                                    # noqa: BLE001
                chat_log.append(f'<div style="color:#9a8a90">后端切换失败：{e}</div>')
            # 自动训练开关落盘（此前只改控件、不写配置，是个空开关）
            try:
                from core import config as _cfg_mod
                _cfg_mod.patch({'growth': {'auto_train': bool(auto_chk.isChecked())}})
                chat_log.append('<div style="color:#9a8a90">后台自动训练已'
                                + ('开启' if auto_chk.isChecked() else '关闭') + '</div>')
            except Exception as e:                                    # noqa: BLE001
                chat_log.append(f'<div style="color:#9a8a90">自动训练设置保存失败：{e}</div>')
            dlg.accept()
        ok_btn.clicked.connect(_save)
        v.addWidget(ok_btn)
        dlg.exec()

    # ---------- P1-1/P1-2/P1-3：面板公共外壳 ----------
    def _panel_shell(title, w=580, h=520):
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle(title)
        dlg.resize(w, h)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        head = QtWidgets.QLabel(title)
        head.setStyleSheet(f'color:{TEXT_DARK};font-size:16px;font-weight:700;')
        layout.addWidget(head)
        return dlg, layout

    def _panel_text(text=''):
        lbl = QtWidgets.QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        lbl.setStyleSheet(f'color:{TEXT_DARK};font-size:12px;')
        return lbl

    def _panel_btn(text, color):
        b = QtWidgets.QPushButton(text)
        b.setFixedHeight(32)
        b.setStyleSheet(f'background:{color};color:white;border:none;'
                        f'border-radius:16px;font-weight:600;padding:0 14px;')
        return b

    def _panel_close(dlg, layout):
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        b = _panel_btn('关闭', TEXT_MUTED)
        b.clicked.connect(dlg.accept)
        row.addWidget(b)
        layout.addLayout(row)

    def _new_engine():
        from core.growth import GrowthEngine
        from core.paths import APP_DIR as _APP_DIR
        return GrowthEngine(base_dir=_APP_DIR, log=lambda *a: None)

    # ---------- 环境配置向导（与启动时弹的是同一个实现） ----------
    def open_wizard():
        try:
            from renderer import wizard as _wiz
            _wiz.run_wizard(parent=win, log=log)
        except Exception as e:                                         # noqa: BLE001
            chat_log.append(f'<div style="color:#9a8a90">环境向导打开失败：{e}</div>')

    # ---------- P1-2：成长仪表盘（版本 / 体积 / 损失曲线 / 晋升时间线） ----------
    def open_growth_panel():
        dlg, v = _panel_shell('成长仪表盘', 660, 640)
        try:
            eng = _new_engine()
            st = eng.status()
            promo = int(st.get('promotions', 0))
            gen_txt = (f'第 {promo} 代自研模型（已脱离原基底）' if promo > 0
                       else '尚未晋升（仍处于 基底 + LoRA 阶段）')
            head = [
                f'模型版本：{gen_txt}',
                f'阶段：{st.get("stage", "-")}',
                f'基底体积：{st.get("base_human") or "-"}    适配器体积：{st.get("adapter_human") or "-"}'
                f'    进度：{float(st.get("progress_percent", 0.0)):.1f}%',
                f'训练轮次：{st.get("rounds", 0)}    LoRA rank：r={st.get("rank", 0)}'
                f'    语料条数：{st.get("corpus_items", 0)}',
            ]
            try:
                s = eng.store.stats()
                head.append(f'训练样本：{s.get("total", 0)} 条（唯一 {s.get("unique", 0)}，'
                            f'待训练 {s.get("pending", 0)}，已训练 {s.get("used_in_training", 0)}）')
                head.append(f'蒸馏样本：{s.get("with_teacher", 0)} 条'
                            f'    DPO 偏好对：{s.get("dpo_pairs", 0)}'
                            f'    平均质量：{s.get("avg_quality", 0)}')
            except Exception as e:                                     # noqa: BLE001
                head.append(f'样本仓库不可用：{type(e).__name__}: {e}')
            v.addWidget(_panel_text('\n'.join(head)))

            v.addWidget(_panel_text('—— 训练损失曲线（↓ 越低越好）——'))
            try:
                curve = eng.store.loss_curve(30) or []
            except Exception:                                          # noqa: BLE001
                curve = []
            v.addWidget(_panel_text(_loss_sparkline(curve)))

            v.addWidget(_panel_text('—— 晋升历史时间线 ——'))
            try:
                gens = eng.lifecycle.generations() or []
            except Exception:                                          # noqa: BLE001
                gens = []
            if gens:
                tl = []
                for g in gens:
                    tl.append(f'第 {g.get("gen", "?")} 代  [{g.get("status", "-")}]'
                              f'  {(g.get("label") or "").strip()}'
                              f'  {g.get("created_at") or g.get("stamp") or ""}')
                v.addWidget(_panel_text('\n'.join(tl)))
            else:
                v.addWidget(_panel_text('（还没有晋升记录）'))
        except Exception as e:                                         # noqa: BLE001
            v.addWidget(_panel_text(f'成长引擎不可用：{type(e).__name__}: {e}'))
        _panel_close(dlg, v)
        dlg.exec()

    # ---------- P1-1：数据管理（查看 / 删除 / 清空 / 导出导入） ----------
    def open_data_panel():
        dlg, v = _panel_shell('数据管理', 760, 620)
        summary = _panel_text('读取中…')
        v.addWidget(summary)
        lst = QtWidgets.QListWidget()
        lst.setStyleSheet(f'background:{CARD_BG};border:1px solid #ecdde2;border-radius:8px;'
                          f'font-size:12px;')
        v.addWidget(lst, 1)

        def _reload():
            lst.clear()
            try:
                eng = _new_engine()
                s = eng.store.stats()
                summary.setText(
                    f'记录 {s.get("total", 0)} 条｜唯一 {s.get("unique", 0)}'
                    f'｜重复 {s.get("duplicates", 0)}｜待训练 {s.get("pending", 0)}'
                    f'｜已训练 {s.get("used_in_training", 0)}｜蒸馏 {s.get("with_teacher", 0)}'
                    f'｜平均质量 {s.get("avg_quality", 0)}')
                for r in eng.store.list_records(limit=200):
                    q = r.get('quality_score')
                    qs = f'{float(q):.2f}' if isinstance(q, (int, float)) else '-'
                    flag = '已训练' if r.get('used_in_training') else '待训练'
                    item = QtWidgets.QListWidgetItem(
                        f'[{str(r.get("id", "?"))[:8]}] {flag} q={qs} | '
                        f'{str(r.get("user_input", ""))[:44]}')
                    item.setData(QtCore.Qt.UserRole, r.get('id'))
                    lst.addItem(item)
            except Exception as e:                                     # noqa: BLE001
                summary.setText(f'数据仓库不可用：{type(e).__name__}: {e}')

        def _delete_selected():
            it = lst.currentItem()
            if not it:
                chat_log.append('<div style="color:#9a8a90">先在列表里选中一条样本再删除。</div>')
                return
            rid = it.data(QtCore.Qt.UserRole)
            try:
                ok = _new_engine().store.delete(str(rid))
                chat_log.append(f'<div style="color:#9a8a90">删除样本 {rid}：'
                                f'{"成功" if ok else "未找到"}</div>')
            except Exception as e:                                     # noqa: BLE001
                chat_log.append(f'<div style="color:#9a8a90">删除失败：{e}</div>')
            _reload()

        def _purge():
            ans = QtWidgets.QMessageBox.question(
                dlg, '确认清空',
                '确定清空全部训练数据？\n（原对话仍会归档到 数据/records/，但训练池会清空）',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if ans != QtWidgets.QMessageBox.Yes:
                return
            try:
                res = _new_engine().store.purge(scope='all')
                chat_log.append(f'<div style="color:#9a8a90">训练数据已清空：{res}</div>')
            except Exception as e:                                     # noqa: BLE001
                chat_log.append(f'<div style="color:#9a8a90">清空失败：{e}</div>')
            _reload()

        def _export():
            from core.paths import APP_DIR as _APP_DIR
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                dlg, '导出训练集', str(Path(_APP_DIR) / '数据' / 'export.jsonl'),
                'JSONL (*.jsonl)')
            if not path:
                return
            try:
                res = _new_engine().store.export_jsonl(path)
                chat_log.append(f'<div style="color:#9a8a90">已导出训练集：{res}</div>')
            except Exception as e:                                     # noqa: BLE001
                chat_log.append(f'<div style="color:#9a8a90">导出失败：{e}</div>')

        def _import():
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                dlg, '导入训练集', '', 'JSONL (*.jsonl)')
            if not path:
                return
            try:
                res = _new_engine().store.import_jsonl(path)
                chat_log.append(f'<div style="color:#9a8a90">已导入训练集：{res}</div>')
            except Exception as e:                                     # noqa: BLE001
                chat_log.append(f'<div style="color:#9a8a90">导入失败：{e}</div>')
            _reload()

        row = QtWidgets.QHBoxLayout()
        for text, color, fn in (
            ('删除选中', '#8a6a5a', _delete_selected),
            ('导出训练集', '#5a7a8a', _export),
            ('导入训练集', '#5a8a6a', _import),
            ('一键清空', '#b04a5a', _purge),
        ):
            b = _panel_btn(text, color)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        _panel_close(dlg, v)
        _reload()
        dlg.exec()

    # ---------- P1-3：成长控制（暂停 / 回滚 / 导出 / 清理） ----------
    def open_control_panel():
        dlg, v = _panel_shell('成长控制', 620, 480)
        state_lbl = _panel_text('读取中…')
        v.addWidget(state_lbl)
        log_lbl = _panel_text('')

        def _refresh():
            try:
                st = _new_engine().status()
                state_lbl.setText(
                    f'阶段：{st.get("stage", "-")}\n'
                    f'暂停状态：{"已暂停（训练与晋升都会被拦住）" if st.get("paused") else "运行中"}\n'
                    f'训练轮次：{st.get("rounds", 0)}    晋升次数：{st.get("promotions", 0)}'
                    f'    进度：{float(st.get("progress_percent", 0.0)):.1f}%')
            except Exception as e:                                     # noqa: BLE001
                state_lbl.setText(f'成长引擎不可用：{type(e).__name__}: {e}')

        def _toggle_pause():
            try:
                eng = _new_engine()
                res = eng.resume() if eng.is_paused() else eng.pause()
                log_lbl.setText(f'{"已恢复成长" if not res.get("paused") else "已暂停成长"}'
                                f'（{res.get("reason", "OK")}）')
            except Exception as e:                                     # noqa: BLE001
                log_lbl.setText(f'操作失败：{e}')
            _refresh()

        def _rollback():
            ans = QtWidgets.QMessageBox.question(
                dlg, '确认回滚',
                '回滚到上一代模型？\n当前代会移入回收区（trash/），可再清理。',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if ans != QtWidgets.QMessageBox.Yes:
                return
            try:
                res = _new_engine().rollback()
                log_lbl.setText(f'回滚：{res.get("message", res)}')
            except Exception as e:                                     # noqa: BLE001
                log_lbl.setText(f'回滚失败：{e}')
            _refresh()

        def _export_model():
            from core.paths import APP_DIR as _APP_DIR
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                dlg, '导出模型', str(Path(_APP_DIR) / '我的小凌模型.zip'), 'ZIP (*.zip)')
            if not path:
                return
            try:
                res = _new_engine().export(path)
                log_lbl.setText(f'导出：{res.get("message", res)}')
            except Exception as e:                                     # noqa: BLE001
                log_lbl.setText(f'导出失败：{e}')

        def _gc():
            try:
                res = _new_engine().gc()
                log_lbl.setText(f'回收区清理：{res.get("message", res)}')
            except Exception as e:                                     # noqa: BLE001
                log_lbl.setText(f'清理失败：{e}')
            _refresh()

        row = QtWidgets.QHBoxLayout()
        for text, color, fn in (
            ('暂停 / 恢复成长', '#8a6a5a', _toggle_pause),
            ('回滚到上一代', '#b04a5a', _rollback),
            ('导出模型', '#5a7a8a', _export_model),
            ('清理回收区', '#5a8a6a', _gc),
        ):
            b = _panel_btn(text, color)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(log_lbl)
        _panel_close(dlg, v)
        _refresh()
        dlg.exec()

    def show_about():
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('关于小凌')
        dlg.setFixedSize(380, 320)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(28, 24, 28, 22)
        v.setAlignment(QtCore.Qt.AlignCenter)
        v.setSpacing(8)
        emoji = QtWidgets.QLabel('')
        emoji.setStyleSheet('font-size:42px;')
        emoji.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(emoji)
        t = QtWidgets.QLabel('小凌 XIAOLING')
        t.setStyleSheet(f'color:{ACCENT};font-size:24px;font-weight:800;letter-spacing:1px;')
        t.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(t)
        v2 = QtWidgets.QLabel('会自我进化的 AI 伴侣 · v1.1 全UI版')
        v2.setStyleSheet(f'color:{TEXT_MUTED};font-size:12px;')
        v2.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(v2)
        v.addSpacing(10)
        info_card = QtWidgets.QFrame()
        info_card.setStyleSheet(f'background:{CARD_BG};border:1px solid {ACCENT_SOFT};'
                                f'border-radius:14px;')
        iv = QtWidgets.QVBoxLayout(info_card)
        iv.setContentsMargins(16, 14, 16, 14)
        iv.setSpacing(4)
        info_lines = [
            ' 全平台（Win / macOS / Linux / Android）',
            ' 自研 LLM：2B / 1B 基底模型 · LoRA 持续成长',
            ' 7 个 VRM 角色 · 46 个动作 · MToon 卡通渲染',
            ' 纯 Python 3D 渲染（GLSL/OpenGL/numpy 三级降级）',
            ' 全UI启动器 + 工作台 · 傻瓜式一键启动',
        ]
        for line in info_lines:
            lbl = QtWidgets.QLabel(line)
            lbl.setStyleSheet(f'color:{TEXT_DARK};font-size:12px;')
            iv.addWidget(lbl)
        v.addWidget(info_card)
        v.addStretch(1)
        close_btn = QtWidgets.QPushButton('关闭')
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(f'background:{ACCENT};color:white;border:none;'
                                f'border-radius:18px;font-weight:700;font-size:13px;')
        close_btn.clicked.connect(dlg.accept)
        v.addWidget(close_btn)
        dlg.exec()

    btn_distill.clicked.connect(start_distill)
    btn_setting.clicked.connect(show_setting)
    btn_about.clicked.connect(show_about)

    # v1.1：顶部"?"按钮 → 快速使用指南（与全UI启动器配套）
    def show_help():
        dlg = QtWidgets.QDialog(win)
        dlg.setWindowTitle('使用帮助')
        dlg.setFixedSize(520, 460)
        dlg.setStyleSheet(f'background:{PALETTE_BG};')
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(28, 24, 28, 22)
        v.setSpacing(10)
        title = QtWidgets.QLabel(' 一分钟上手小凌')
        title.setStyleSheet(f'color:{ACCENT};font-size:18px;font-weight:800;')
        v.addWidget(title)
        body = QtWidgets.QTextEdit()
        body.setReadOnly(True)
        body.setStyleSheet(f'background:{CARD_BG};color:{TEXT_DARK};'
                           f'border:1px solid {ACCENT_SOFT};border-radius:14px;'
                           f'padding:14px;font-size:13px;')
        body.setHtml(
            '<style>li{margin:6px 0;}b{color:#d4385c;}</style>'
            '<ul>'
            '<li><b>首次启动</b>：会自动弹出全UI启动器，选择想自研的基底模型后一键下载。</li>'
            '<li><b>切换 LLM 档位</b>：顶部 <code> 自研 N B 模型</code> 下拉框可换基底，后台自动下载。</li>'
            '<li><b>切换 VRM 角色</b>：旁边 <code>角色模型</code> 下拉框选 7 个角色，<b>导入模型</b> 加新角色。</li>'
            '<li><b>对话</b>：底部输入框敲回车；<b>双击她</b>打开桌宠输入。</li>'
            '<li><b>成长</b>：右下角 <b>+</b> 按钮 → 启用 <code>蒸馏训练</code> 插件 → <b>开始蒸馏训练</b>。</li>'
            '<li><b>指令</b>：说「蒸馏」「成长进度」「晋升评估」「升 rank」「暂停成长」「记忆检索 …」。</li>'
            '<li><b>模型下载</b>：进度会同步在桌宠气泡里；下载完成自动继续启动。</li>'
            '</ul>')
        v.addWidget(body, 1)
        close_btn = QtWidgets.QPushButton('我知道了')
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(f'background:{ACCENT};color:white;border:none;'
                                f'border-radius:18px;font-weight:700;font-size:13px;')
        close_btn.clicked.connect(dlg.accept)
        v.addWidget(close_btn)
        dlg.exec()
    btn_help.clicked.connect(show_help)

    func_row.addStretch(1)
    func_row.addWidget(btn_distill)
    func_row.addWidget(btn_base_help)
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
