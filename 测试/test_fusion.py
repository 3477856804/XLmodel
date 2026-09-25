#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""融合层回归测试：不改动 xl.py 逻辑的前提下，验证包装是否生效。"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import fusion  # noqa: E402


def _fake_globals():
    class XiaoLing:
        def __init__(self):
            self.user_name = '主人'
            self.calls = []

        def chat(self, text):
            self.calls.append(text)
            return f'引擎回复：{text}'

    def speak(text, force=False):
        speak.called.append(text)
        return True
    speak.called = []

    def _start_pet_background(app):
        return 'legacy-pet'

    def run_distill(app, rounds=6, epochs=2):
        return 'distilled'

    def distill_train(epochs=2, batch_size=2, lr=1e-4):
        return 'trained'

    def main():
        return 'main-called'

    return {'XiaoLing': XiaoLing, 'speak': speak,
            '_start_pet_background': _start_pet_background,
            'run_distill': run_distill, 'distill_train': distill_train, 'main': main,
            'CONFIG': {'name': '小凌', 'deepseek_api_key': 'sk-test', 'user_name': '主人'}}


def test_install_wraps_everything():
    fusion._STATE['installed'] = False
    fusion._STATE['avatar'] = None
    g = _fake_globals()
    import os
    os.environ['XIAOLING_NO_AVATAR'] = '1'
    fusion.install(g)
    assert g['speak'].__name__ == 'speak_fused'
    assert g['_start_pet_background'].__name__ == '_start_pet_background'
    assert g['run_distill'].__name__ == 'run_distill_fused'
    assert g['main'].__name__ == 'main_fused'
    assert g['CONFIG']['version'] == '0.0.2'
    assert g['CONFIG']['deepseek_api_key'] == 'sk-test'          # 用户显式配置不被覆盖
    print('[OK] 融合层安装 / 配置合并 / 函数包装：通过')


def test_command_interception():
    fusion._STATE['installed'] = False
    fusion._STATE['avatar'] = None
    g = _fake_globals()
    fusion.install(g)
    app = g['XiaoLing']()
    # 普通对话走原引擎
    assert app.chat('今天天气怎么样') == '引擎回复：今天天气怎么样'
    # 融合指令被拦截（不进入原引擎）
    out = app.chat('成长进度')
    assert '成长' in out and out not in app.calls
    out2 = app.chat('电脑状态')
    assert '正在' in out2 or '读不到' in out2
    assert len(app.calls) == 1
    # 帮助
    assert '3D 数字人' in app.chat('融合帮助')
    print('[OK] 融合指令拦截 / 基础对话透传：通过')


def test_speak_drives_avatar():
    fusion._STATE['installed'] = False
    g = _fake_globals()
    fusion.install(g)
    g['speak']('你好呀')
    assert g['speak'].__name__ == 'speak_fused'
    print('[OK] 语音朗读钩子（数字人口型联动入口）：通过')


def test_growth_command():
    fusion._STATE['installed'] = False
    g = _fake_globals()
    fusion.install(g)
    app = g['XiaoLing']()
    report = fusion._cmd_growth(app)
    assert '成长报告' in report
    print('[OK] 成长报告指令：通过')


if __name__ == '__main__':
    test_install_wraps_everything()
    test_command_interception()
    test_speak_drives_avatar()
    test_growth_command()
    print('全部融合层测试通过')
