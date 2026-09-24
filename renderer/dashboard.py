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

    mid.addLayout(left_col, 0)

    # 中央 3D 渲染
    center_box = QtWidgets.QVBoxLayout()
    center_box.setSpacing(10)
    center_box.setAlignment(QtCore.Qt.AlignHCenter)

    view = QtWidgets.QLabel()
    view.setFixedSize(460, 620)
    view.setStyleSheet(f'background:transparent;border:none;')
    view.setAlignment(QtCore.Qt.AlignCenter)
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
    render_timer.start(33)  # ~30fps

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

    win.show()
    win._own_renderer = own_renderer
    win._render_timer = render_timer
    win._progress_timer = progress_timer
    return win


def run_dashboard(log=print):
    """启动工作台（阻塞）。"""
    win = build_dashboard(log=log)
    if win is None:
        return False
    from PySide6 import QtWidgets
    QtWidgets.QApplication.instance().exec()
    return True


if __name__ == '__main__':
    run_dashboard()
