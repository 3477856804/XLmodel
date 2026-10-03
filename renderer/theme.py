#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.theme —— 小凌全局粉色少女风主题（v0.0.3 新增）

为什么要有这个文件：
    v0.0.2 里每个 UI 文件（chat_ui / startup_ui / wizard / dashboard / window）
    都在自己手写一堆 setStyleSheet，颜色 hex 散落在十几处，一改配色就要全局搜。
    这里把"奶油草莓"主题的所有色值、圆角、QSS 工厂函数收在一处，
    其他界面只调用 ``from renderer.theme import PALETTE, card_qss, primary_btn_qss ...``。

设计语言（见 小凌v0.0.3开发计划.md §1）：
    背景     #fff7f9 → #fde8ef → #fbdce6  纵向奶油渐变
    主粉     #e85a8a → #ff7aa2            按钮渐变
    卡片     白底 + 16px 圆角 + 淡粉描边
    文字     #4a3a40 主 / #b09aa2 次

纯 Qt 层，不依赖任何业务模块；无 PySide6 时 import 会失败，调用方需自行 try。
"""
from __future__ import annotations


# --------------------------------------------------------------------------- #
#  配色常量（唯一真相源）
# --------------------------------------------------------------------------- #
PALETTE = {
    # 背景（窗口/对话框底色）
    'bg_top':    '#fff7f9',   # 渐变顶端
    'bg_mid':    '#fde8ef',   # 渐变中段
    'bg_bottom': '#fbdce6',   # 渐变底端
    'bg_plain':  '#faf6f7',   # 兜底平涂（QSS 不支持渐变时用）

    # 卡片 / 输入框
    'card_bg':       '#ffffff',
    'card_border':   '#f0d4de',
    'card_border_focus': '#ff9ebb',

    # 主色（粉）
    'accent':        '#e85a8a',   # 主按钮常态
    'accent_hover':  '#ff7aa2',   # hover
    'accent_active': '#d14878',   # 按下
    'accent_soft':   '#ffe0ea',   # 淡粉填充（hover 次按钮、选中态）

    # 文字
    'text_main':     '#4a3a40',
    'text_title':    '#3a2a30',
    'text_muted':    '#b09aa2',

    # 功能色
    'ok':            '#6abf8a',
    'warn':          '#e8a83a',
    'err':           '#e05a5a',
}


# --------------------------------------------------------------------------- #
#  QSS 工厂函数
# --------------------------------------------------------------------------- #
def app_background_qss() -> str:
    """应用到 QApplication 或顶层 QWidget 的全局背景（奶油渐变）。

    注意：Qt 的 QSS 不支持垂直 linear-gradient 在 QWidget 背景上完美渲染，
    这里用兜底的淡粉色平涂 + 子控件自己加渐变。要更细腻的渐变可以在
    window 上重写 paintEvent，但 v0.0.3 先保持简单。
    """
    return f"""
        QWidget {{
            background-color: {PALETTE['bg_plain']};
            color: {PALETTE['text_main']};
            font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC",
                         "Hiragino Sans GB", sans-serif;
        }}
        QToolTip {{
            background-color: #ffffff;
            color: {PALETTE['text_main']};
            border: 1px solid {PALETTE['card_border']};
            border-radius: 6px;
            padding: 4px 8px;
        }}
        QToolTip {{ font-size: 12px; }}
    """


def card_qss(border: str | None = None) -> str:
    """白色奶油卡片：白底、淡粉描边、大圆角。

    用法：``frame.setStyleSheet(card_qss())``
    """
    b = border or PALETTE['card_border']
    return f"""
        QFrame {{
            background-color: {PALETTE['card_bg']};
            border: 1px solid {b};
            border-radius: 16px;
        }}
    """


def primary_btn_qss() -> str:
    """主按钮：粉色渐变胶囊。"""
    return f"""
        QPushButton {{
            background-color: {PALETTE['accent']};
            color: white;
            border: none;
            border-radius: 18px;
            padding: 8px 20px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {PALETTE['accent_hover']};
        }}
        QPushButton:pressed {{
            background-color: {PALETTE['accent_active']};
        }}
        QPushButton:disabled {{
            background-color: #e8c8d2;
            color: #f4e4ea;
        }}
    """


def secondary_btn_qss() -> str:
    """次按钮：白底粉描边胶囊，hover 填淡粉。"""
    return f"""
        QPushButton {{
            background-color: #ffffff;
            color: {PALETTE['accent']};
            border: 1.5px solid {PALETTE['accent']};
            border-radius: 18px;
            padding: 8px 18px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {PALETTE['accent_soft']};
        }}
        QPushButton:pressed {{
            background-color: #ffd0dd;
        }}
        QPushButton:disabled {{
            color: #d0b8c0;
            border-color: #e8d4dc;
            background-color: #faf2f5;
        }}
    """


def ghost_btn_qss() -> str:
    """幽灵按钮：无描边、灰字，hover 淡粉底。用于"退出/取消"这类弱操作。"""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {PALETTE['text_muted']};
            border: none;
            border-radius: 16px;
            padding: 8px 16px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {PALETTE['accent_soft']};
            color: {PALETTE['accent']};
        }}
    """


def input_qss() -> str:
    """胶囊输入框：白底、淡粉边、聚焦变粉。"""
    return f"""
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
            background-color: #ffffff;
            border: 1.5px solid {PALETTE['card_border']};
            border-radius: 12px;
            padding: 8px 12px;
            font-size: 13px;
            color: {PALETTE['text_main']};
            selection-background-color: {PALETTE['accent_soft']};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
        QSpinBox:focus, QComboBox:focus {{
            border: 1.5px solid {PALETTE['card_border_focus']};
        }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
        QComboBox QAbstractItemView {{
            background-color: #ffffff;
            border: 1px solid {PALETTE['card_border']};
            border-radius: 8px;
            selection-background-color: {PALETTE['accent_soft']};
        }}
    """


def title_qss() -> str:
    """大标题。"""
    return f"""
        font-size: 20px;
        font-weight: 700;
        color: {PALETTE['text_title']};
        letter-spacing: 1px;
    """


def subtitle_qss() -> str:
    """副标题 / 说明文字。"""
    return f"""
        font-size: 12px;
        color: {PALETTE['text_muted']};
    """


def progressbar_qss() -> str:
    """粉色进度条。"""
    return f"""
        QProgressBar {{
            background-color: #f4e4ea;
            border: none;
            border-radius: 4px;
            height: 8px;
            text-align: center;
            color: transparent;
        }}
        QProgressBar::chunk {{
            background-color: {PALETTE['accent']};
            border-radius: 4px;
        }}
    """


# --------------------------------------------------------------------------- #
#  一次性把主题套到 QApplication 上
# --------------------------------------------------------------------------- #
def apply_pink_theme(app) -> None:
    """对 QApplication 调用一次，全局套上粉色少女风。

    每个窗口仍可在自己的 setStyleSheet 里局部覆盖（QSS 就近优先）。
    """
    try:
        app.setStyleSheet(app_background_qss() + input_qss())
    except Exception:                                             # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
#  对话气泡 HTML 片段（给 chat_ui 用）
# --------------------------------------------------------------------------- #
def bubble_html(who: str, text: str, who_color: str = 'accent') -> str:
    """生成一条聊天气泡的 HTML。

    who_color: 'accent' = 小凌（粉色）; 'me' = 用户（深棕）。
    """
    safe = (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    safe = safe.replace('\n', '<br>')
    if who_color == 'accent':
        name_color = PALETTE['accent']
        bg = '#fff0f5'
    else:
        name_color = PALETTE['text_title']
        bg = '#ffffff'
    return (
        f'<div style="margin:6px 0;padding:8px 12px;background:{bg};'
        f'border-radius:12px;border:1px solid {PALETTE["card_border"]};'
        f'font-size:13px;line-height:1.5;">'
        f'<b style="color:{name_color}">{who}：</b>{safe}</div>'
    )


__all__ = [
    'PALETTE',
    'app_background_qss', 'card_qss',
    'primary_btn_qss', 'secondary_btn_qss', 'ghost_btn_qss',
    'input_qss', 'title_qss', 'subtitle_qss', 'progressbar_qss',
    'apply_pink_theme', 'bubble_html',
]
