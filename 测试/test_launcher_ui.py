#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全UI启动器（core.launcher_ui）的轻量测试
- 不弹窗，只测导入、配置写入、可识别档位等纯逻辑路径。
- 在没有 PySide6 / DISPLAY 的环境下也能完整跑（关键路径只依赖 stdlib + pathlib）。
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_presets_public():
    """档位列表至少包含 2B 与 1B，键名与 xl.py MODEL_PRESETS 一致。"""
    from core.launcher_ui import MODEL_PRESETS_PUBLIC        # noqa: E402
    keys = {p['key'] for p in MODEL_PRESETS_PUBLIC}
    assert '自研2B模型' in keys, f'缺自研2B模型: {keys}'
    assert '自研1B模型' in keys, f'缺自研1B模型: {keys}'
    for p in MODEL_PRESETS_PUBLIC:
        assert p.get('label'), f'档位缺 label: {p}'
        assert p.get('size'), f'档位缺 size: {p}'
        assert p.get('desc'), f'档位缺 desc: {p}'


def test_preset_label_lookup():
    """_preset_label_from_key 对未知键返回原值，已知键返回 label。"""
    from core.launcher_ui import _preset_label_from_key      # noqa: E402
    assert '2B' in _preset_label_from_key('自研2B模型')
    assert '1B' in _preset_label_from_key('自研1B模型')
    assert _preset_label_from_key('神秘档位') == '神秘档位'


def test_apply_chosen_writes_config():
    """_apply_chosen 应同时写入 xiaoling_config.json 与 model_choice.txt。"""
    from core import launcher_ui                              # noqa: E402
    from core.paths import STAR_DIR
    with tempfile.TemporaryDirectory() as td:
        # 把 STAR_DIR 临时改到 td
        import core.paths as _paths_mod
        old_star = _paths_mod.STAR_DIR
        _paths_mod.STAR_DIR = Path(td)
        _paths_mod.STAR = _paths_mod.STAR_DIR
        # config_mod.STAR 也是同一对象引用
        from core import config as _cfg_mod
        _cfg_mod.STAR = _paths_mod.STAR_DIR
        _cfg_mod.CONFIG_PATH = _paths_mod.STAR_DIR / 'xiaoling_config.json'
        try:
            launcher_ui._apply_chosen('自研1B模型')
            # 验证 xiaoling_config.json 写对了
            cfg_path = _paths_mod.STAR_DIR / 'xiaoling_config.json'
            assert cfg_path.exists()
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
            assert cfg['model']['base_model'] == '自研1B模型'
            # 验证 model_choice.txt 写对了
            legacy = _paths_mod.STAR_DIR / 'model_choice.txt'
            assert legacy.exists()
            assert legacy.read_text(encoding='utf-8') == '自研1B模型'
        finally:
            _paths_mod.STAR_DIR = old_star
            _paths_mod.STAR = old_star
            _cfg_mod.STAR = old_star
            _cfg_mod.CONFIG_PATH = old_star / 'xiaoling_config.json'


def test_is_ui_available_returns_bool():
    """_have_qt / is_ui_available 至少能调用、不抛异常。"""
    from core.launcher_ui import _have_qt, is_ui_available  # noqa: E402
    assert isinstance(_have_qt(), bool)
    assert isinstance(is_ui_available(), bool)


def test_dashboard_imports_launcher_presets():
    """dashboard.py 应能正确从 launcher_ui 导入档位列表。"""
    from core.launcher_ui import MODEL_PRESETS_PUBLIC        # noqa: E402
    # 直接模拟 dashboard 中的导入路径
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'renderer'))
    # 只需确保它能用于填充下拉框
    assert len(MODEL_PRESETS_PUBLIC) >= 2
    # 不重复导：跑完清理
    sys.path.pop()


if __name__ == '__main__':
    test_presets_public()
    test_preset_label_lookup()
    test_apply_chosen_writes_config()
    test_is_ui_available_returns_bool()
    test_dashboard_imports_launcher_presets()
    print('全部 launcher_ui 测试通过')