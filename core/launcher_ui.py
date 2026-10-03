#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 全UI启动器（首次启动向导 + 模型选择）

作用：
- 替代命令行交互式档位选择，给用户一个漂亮的全屏启动器。
- 步骤：① 欢迎语 → ② 基底模型选择（看真实档位、看真实体积）→ ③ 一键下载/就绪检查
       → ④ 进入主工作台（dashboard）。
- 没 PySide6 / 没图形环境时返回 False，由上层回退到命令行流程，绝不卡死。

设计原则：
- 启动器只在主线程跑短窗口，结束后立刻返回。
- 不阻塞后台下载；下载进度写到全局状态，桌宠气泡会同步显示。
- 复用 dashboard 的视觉风格（樱花粉 + 米白 + 深红强调色），UI 一致性。
"""
from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path

# 与 dashboard.py / xl.py / fusion.py 同款的"樱花"调色板（保持视觉一致）
PALETTE_BG     = '#fef9fb'         # 更柔的米白
PALETTE_CARD   = '#ffffff'
PALETTE_TEXT   = '#2d1f25'
PALETTE_MUTED  = '#9a8a90'
PALETTE_ACCENT = '#e23b6e'         # 樱花深粉（强调色）
PALETTE_ACCENT2 = '#ff6b9d'        # 浅粉渐变
PALETTE_LINE   = '#f0e4e8'
PALETTE_OK     = '#3b8a5a'
PALETTE_WARN   = '#d39c3b'
PALETTE_SHADOW = 'rgba(226, 59, 110, 0.08)'

MODEL_PRESETS_PUBLIC = [
    {
        'key': '自研2B模型',
        'label': '自研 2B 模型',
        'sub': '端侧最强 · 推荐',
        'desc': 'MiniCPM5-2B  大语言模型 · 适合主流手机和电脑',
        'size': '约 4.8GB',
        'badge': '推荐',
        'badge_color': PALETTE_ACCENT,
    },
    {
        'key': '自研1B模型',
        'label': '自研 1B 模型',
        'sub': '轻量 · 低配设备',
        'desc': 'MiniCPM5-1B  体积更小 · 适合入门显卡 / 老旧电脑',
        'size': '约 2.1GB',
        'badge': '轻量',
        'badge_color': PALETTE_WARN,
    },
]


def _preset_label_from_key(key: str) -> str:
    for p in MODEL_PRESETS_PUBLIC:
        if p['key'] == key:
            return p['label']
    return key


def _have_qt() -> bool:
    """检测 PySide6 与图形环境。无头环境直接放弃 UI，避免崩溃。"""
    try:
        from PySide6 import QtWidgets, QtGui          # noqa: F401
    except Exception:
        return False
    # Termux / Linux 无 DISPLAY 也放弃（即使有 Qt 也开不出窗口）
    if os.environ.get('DISPLAY') is None and os.environ.get('WAYLAND_DISPLAY') is None:
        if not sys.platform.startswith('win') and not sys.platform == 'darwin':
            return False
    return True


# --------------------------------------------------------------------------- #
#  UI 实现
# --------------------------------------------------------------------------- #
def run_launcher(app_state: dict | None = None) -> str | None:
    """弹出全屏启动器，让用户选择模型档位。
    返回选中的 preset key；返回 None 表示用户取消或环境不可用。
    app_state 用来保存进度回调（写入后被桌宠/主循环读取）。
    """
    if not _have_qt():
        return None

    from PySide6 import QtCore, QtGui, QtWidgets

    # 共享状态：进度回调（写到 dict，供 fusion/dashboard 读取）
    state = app_state if isinstance(app_state, dict) else {}

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName('小凌 启动器')

    win = QtWidgets.QWidget()
    win.setWindowTitle('小凌 · 启动')
    win.resize(960, 640)
    win.setMinimumSize(820, 560)
    win.setStyleSheet(f'''
        QWidget {{
            background: qlineargradient(x1:0,y1:0,x2:0.3,y2:1,
                stop:0 #fff5f8, stop:1 #fef9fb);
        }}
    ''')

    # ----- 顶部欢迎区 -----
    title = QtWidgets.QLabel('你好，我是小凌 ')
    title.setStyleSheet(f'color:{PALETTE_TEXT};font-size:28px;font-weight:700;')
    subtitle = QtWidgets.QLabel('首次启动要先选一个基底模型——选完我会自己下载并跑起来。')
    subtitle.setStyleSheet(f'color:{PALETTE_MUTED};font-size:14px;')
    subtitle.setWordWrap(True)

    # ----- 模型选择卡片（圆角卡片） -----
    cards_box = QtWidgets.QWidget()
    cards_box.setStyleSheet(f'background:{PALETTE_CARD};border:1px solid {PALETTE_LINE};'
                            f'border-radius:18px;')
    cards_layout = QtWidgets.QVBoxLayout(cards_box)
    cards_layout.setContentsMargins(20, 18, 20, 18)
    cards_layout.setSpacing(10)
    cards_title = QtWidgets.QLabel('选择你想"自研"的基底模型')
    cards_title.setStyleSheet(f'color:{PALETTE_TEXT};font-size:15px;font-weight:700;')
    cards_layout.addWidget(cards_title)
    cards_hint = QtWidgets.QLabel('体积大的更聪明，体积小的更省资源——按你的设备选。')
    cards_hint.setStyleSheet(f'color:{PALETTE_MUTED};font-size:12px;')
    cards_layout.addWidget(cards_hint)

    radio_buttons = []
    card_buttons = []
    for preset in MODEL_PRESETS_PUBLIC:
        row = QtWidgets.QWidget()
        row.setStyleSheet(f'background:{PALETTE_BG};border:2px solid {PALETTE_LINE};'
                          f'border-radius:14px;')
        row.setFixedHeight(96)
        lay = QtWidgets.QHBoxLayout(row)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(14)

        radio = QtWidgets.QRadioButton()
        radio.setStyleSheet(f'QRadioButton::indicator {{ width:18px; height:18px; }}')
        radio_buttons.append((radio, preset))
        # 默认第一个选中
        if preset.get('badge') == '推荐':
            radio.setChecked(True)

        info = QtWidgets.QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QtWidgets.QLabel(f"{preset['label']}  "
                                    f"<span style='color:{preset['badge_color']};"
                                    f"font-size:11px;font-weight:600;'>"
                                    f"{preset['badge']}</span>")
        name_lbl.setStyleSheet(f'color:{PALETTE_TEXT};font-size:15px;font-weight:700;')
        name_lbl.setTextFormat(QtCore.Qt.RichText)
        sub_lbl = QtWidgets.QLabel(preset['desc'])
        sub_lbl.setStyleSheet(f'color:{PALETTE_MUTED};font-size:12px;')
        sub_lbl.setWordWrap(True)
        info.addWidget(name_lbl)
        info.addWidget(sub_lbl)

        size_lbl = QtWidgets.QLabel(preset['size'])
        size_lbl.setStyleSheet(f'color:{PALETTE_ACCENT};font-size:14px;font-weight:700;')

        lay.addWidget(radio)
        lay.addLayout(info, 1)
        lay.addWidget(size_lbl, 0, QtCore.Qt.AlignVCenter)

        # 点整个卡片也能选中
        def _select_from_card(checked=False, r=radio):
            r.setChecked(True)

        for w in (row, name_lbl, sub_lbl, size_lbl):
            w.mousePressEvent = lambda _e, r=radio: _select_from_card(r=r)
            w.setCursor(QtCore.Qt.PointingHandCursor)

        cards_layout.addWidget(row)
        card_buttons.append(row)

    # ----- 启动按钮 -----
    btn_go = QtWidgets.QPushButton('开始唤醒小凌 →')
    btn_go.setFixedHeight(48)
    btn_go.setCursor(QtCore.Qt.PointingHandCursor)
    btn_go.setStyleSheet(f'''
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {PALETTE_ACCENT}, stop:1 #ff7a9c);
            color:white; border:none; border-radius:24px;
            font-size:15px; font-weight:700; letter-spacing:1px;
        }}
        QPushButton:hover {{ background:{PALETTE_ACCENT}; }}
        QPushButton:disabled {{ background:#e0b8c4; color:#fff; }}
    ''')
    btn_skip = QtWidgets.QPushButton('稍后选择 / 直接启动')
    btn_skip.setFixedHeight(36)
    btn_skip.setCursor(QtCore.Qt.PointingHandCursor)
    btn_skip.setStyleSheet(f'QPushButton{{background:transparent;color:{PALETTE_MUTED};'
                           f'border:none;font-size:12px;}}'
                           f'QPushButton:hover{{color:{PALETTE_ACCENT};}}')

    progress_lbl = QtWidgets.QLabel('')
    progress_lbl.setStyleSheet(f'color:{PALETTE_MUTED};font-size:12px;')
    progress_lbl.setAlignment(QtCore.Qt.AlignCenter)
    progress_lbl.hide()

    # 底部版本号 + 成长状态
    footer = QtWidgets.QLabel('小凌 v0.0.1 · 你的专属AI正在成长中')
    footer.setStyleSheet(f'color:{PALETTE_MUTED};font-size:11px;')
    footer.setAlignment(QtCore.Qt.AlignCenter)

    # 成长进度条（示例）
    growth_bar = QtWidgets.QProgressBar()
    growth_bar.setRange(0, 100)
    growth_bar.setValue(12)  # 初始进度
    growth_bar.setTextVisible(False)
    growth_bar.setFixedHeight(4)
    growth_bar.setStyleSheet(f'''
        QProgressBar {{ background:{PALETTE_LINE}; border-radius:2px; }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {PALETTE_ACCENT}, stop:1 {PALETTE_ACCENT2});
            border-radius:2px;
        }}
    ''')

    # ----- 整体布局 -----
    root = QtWidgets.QVBoxLayout(win)
    root.setContentsMargins(40, 32, 40, 28)
    root.setSpacing(14)
    root.addWidget(title)
    root.addWidget(subtitle)
    root.addSpacing(8)
    root.addWidget(cards_box, 1)
    root.addWidget(progress_lbl)
    root.addWidget(growth_bar)
    root.addWidget(btn_go)
    root.addWidget(btn_skip, 0, QtCore.Qt.AlignCenter)
    root.addWidget(footer)

    chosen = {'key': None}

    def _on_go():
        for radio, preset in radio_buttons:
            if radio.isChecked():
                chosen['key'] = preset['key']
                break
        if chosen['key'] is None:
            chosen['key'] = MODEL_PRESETS_PUBLIC[0]['key']

        btn_go.setEnabled(False)
        btn_skip.hide()
        progress_lbl.show()
        progress_lbl.setText('正在准备基底模型，首次启动需要下载约几个 G，请稍候…')

        # 写共享状态：上层 fusion 可以读到
        state['chosen_model'] = chosen['key']
        state['launcher_done'] = True

        # 让 UI 能把"启动中…"信息显示 ~600ms 再关，给人一个反馈
        QtCore.QTimer.singleShot(600, win.close)

    def _on_skip():
        chosen['key'] = MODEL_PRESETS_PUBLIC[0]['key']
        state['launcher_done'] = True
        state['launcher_skipped'] = True
        win.close()

    btn_go.clicked.connect(_on_go)
    btn_skip.clicked.connect(_on_skip)

    # 居中显示
    win.show()
    win.raise_()
    win.activateWindow()
    QtCore.QTimer.singleShot(50, lambda: win.setFocus())
    app.exec()

    return chosen['key']


def _apply_chosen(chosen_key: str) -> None:
    """把用户选中的档位写到配置与持久化文件。"""
    if not chosen_key:
        return
    try:
        from core import config as config_mod
        cfg = config_mod.load()
        cfg['model']['base_model'] = chosen_key
        # 同步写一份兼容老代码用的 model_choice.txt
        config_mod.save(cfg)
        legacy = Path(config_mod.STAR) / 'model_choice.txt'
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(chosen_key, encoding='utf-8')
    except Exception as e:                                            # noqa: BLE001
        print(f'  [启动器] 写入配置失败：{e}')


# --------------------------------------------------------------------------- #
#  对外接口
# --------------------------------------------------------------------------- #
def select_model_on_start_ui() -> str | None:
    """UI 版的选择模型档位。返回选中的 key；失败/不可用时返回 None。
    与 xl.py 的 _select_model_on_start() 互为回退——任意一方能跑就行。
    """
    state = {'chosen_model': None, 'launcher_done': False, 'launcher_skipped': False}
    try:
        chosen = run_launcher(app_state=state)
    except Exception as e:                                            # noqa: BLE001
        print(f'  [启动器] UI 启动失败：{e}')
        return None

    if chosen is None:
        return None

    _apply_chosen(chosen)
    print(f'  [启动器] 已选择：{_preset_label_from_key(chosen)}')
    return chosen


def is_ui_available() -> bool:
    return _have_qt()


if __name__ == '__main__':
    print(select_model_on_start_ui())