#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.settings —— 设置对话框（Qt，取代旧版渲染层的 HTML 设置页）

配置项由 `core.config.DEFAULTS` 的 JSON 结构自动生成表单，因此**永不与后端脱节**：
新增配置项后设置页会自动出现对应控件。保存写回 `.star_core/xiaoling_config.json`。
"""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

LABELS = {
    'name': '名字', 'user_name': '对你的称呼', 'persona': '人格（活泼/温柔/专业）',
    'deepseek_api_key': 'DeepSeek Key（蒸馏老师）', 'teacher_model': '老师模型',
    'temperature': '温度', 'max_tokens': '最大生成长度', 'enable_voice': '语音朗读',
    'proactive': '主动搭话', 'enabled': '启用', 'model': '3D 模型文件', 'scale': '缩放',
    'focus': '视角（bust/full）', 'api_key': 'API Key', 'base_url': '接口地址',
    'edge_voice': 'Edge 音色', 'engine': '引擎', 'base_model': '基底模型档位',
    'retire_mode': '基底退役方式（delete/archive）', 'auto_check_after_train': '每轮训练后自动检查',
    'top_k': '检索条数', 'max_results': '搜索条数', 'city': '城市',
}


class SettingsDialog:
    """薄封装：按平台可用性返回 Qt 对话框实例。"""

    def __new__(cls, qt=None, parent=None):
        if qt is None:
            try:
                from PySide6 import QtWidgets
            except Exception:                                             # noqa: BLE001
                from PyQt5 import QtWidgets
        else:
            QtWidgets = qt[2]
        from core import config as config_mod

        class _Dialog(QtWidgets.QDialog):
            def __init__(self):
                super().__init__(parent)
                self.setWindowTitle('小凌 · 设置')
                self.setMinimumWidth(460)
                self.cfg = config_mod.load()
                self.fields = {}
                form = QtWidgets.QFormLayout()
                for section in ('avatar', 'model', 'growth', 'rag', 'search', 'vision',
                                'tts', 'asr', 'reminder'):
                    data = self.cfg.get(section)
                    if not isinstance(data, dict):
                        continue
                    box = QtWidgets.QGroupBox(section)
                    inner = QtWidgets.QFormLayout()
                    for key, val in data.items():
                        label = LABELS.get(key, key)
                        if isinstance(val, bool):
                            w = QtWidgets.QCheckBox()
                            w.setChecked(val)
                        elif isinstance(val, (int, float)):
                            w = QtWidgets.QLineEdit(str(val))
                        else:
                            w = QtWidgets.QLineEdit(str(val))
                        self.fields[f'{section}.{key}'] = w
                        inner.addRow(label, w)
                    box.setLayout(inner)
                    form.addRow(box)
                for key in ('name', 'user_name', 'persona', 'deepseek_api_key', 'temperature'):
                    w = QtWidgets.QLineEdit(str(self.cfg.get(key, '')))
                    self.fields[key] = w
                    form.addRow(LABELS.get(key, key), w)
                buttons = QtWidgets.QDialogButtonBox(
                    QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.save)
                buttons.rejected.connect(self.reject)
                layout = QtWidgets.QVBoxLayout(self)
                scroll = QtWidgets.QScrollArea()
                holder = QtWidgets.QWidget()
                holder.setLayout(form)
                scroll.setWidget(holder)
                scroll.setWidgetResizable(True)
                layout.addWidget(scroll)
                layout.addWidget(buttons)

            def save(self):
                for path, widget in self.fields.items():
                    parts = path.split('.')
                    if len(parts) == 1:
                        cur = self.cfg.get(parts[0])
                    else:
                        cur = self.cfg.get(parts[0], {}).get(parts[1])
                    if hasattr(widget, 'isChecked'):
                        value = widget.isChecked()
                    else:
                        raw = widget.text()
                        if isinstance(cur, bool):
                            value = raw.strip().lower() in ('1', 'true', 'yes', 'on', '是')
                        elif isinstance(cur, int):
                            value = int(float(raw or 0))
                        elif isinstance(cur, float):
                            value = float(raw or 0)
                        else:
                            value = raw
                    if len(parts) == 1:
                        self.cfg[parts[0]] = value
                    else:
                        self.cfg.setdefault(parts[0], {})[parts[1]] = value
                config_mod.save(self.cfg)
                self.accept()

        return _Dialog()
