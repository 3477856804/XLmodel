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
    """工作台（renderer/dashboard.py）依赖的档位导入路径必须真实成立。

    这个测试此前是**假测试**：名字说「dashboard 应能正确从 launcher_ui 导入档位列表」，
    实际既没有导入 dashboard，也只是把 launcher_ui 又 import 了一遍再断言 len>=2，
    等于什么都没验证。现在真正做三件事：
      1) dashboard 里写的那条导入语句（core.launcher_ui.MODEL_PRESETS_PUBLIC）可用；
      2) renderer.dashboard 模块本身可在无 PySide6 / 无 DISPLAY 环境下导入
         （Qt 全部是函数内导入，这正是工作台能在开发模式跑的前提）；
      3) 填下拉框要用的档位检索函数对每个档位都能返回 label。
    """
    import importlib

    # dashboard.py 内部就是这么导入的（见 renderer/dashboard.py 里的 _LLM_PRESETS）
    from core.launcher_ui import MODEL_PRESETS_PUBLIC as _LLM_PRESETS, _preset_label_from_key
    assert len(_LLM_PRESETS) >= 2, f'档位表过短: {_LLM_PRESETS}'

    mod = importlib.import_module('renderer.dashboard')
    for name in ('build_dashboard', 'run_dashboard', '_growth_status', '_loss_sparkline'):
        assert hasattr(mod, name), f'renderer.dashboard 缺少 {name}'

    for p in _LLM_PRESETS:
        assert _preset_label_from_key(p['key']), f'档位 {p["key"]} 取不到 label'


def test_growth_status_uses_real_backend_keys():
    """P0-3 回归：_growth_status() 必须用 GrowthEngine.status() 的真实字段名。

    后端产出的是 base_bytes/adapter_bytes 与 base_human/adapter_human，
    **不存在** base_mb/adapter_mb。旧代码读错键 → 状态栏恒显 0MB，
    且 dashboard 里读 base_human 的地方会直接 KeyError。

    这里用 AST 提取函数内所有字典字面量的**键**来判断，而不是做字符串包含匹配
    ——否则源码注释里出现 "base_mb" 就会让测试误报。
    """
    import ast
    import inspect
    import tempfile
    import textwrap
    from pathlib import Path

    from renderer import dashboard

    src = textwrap.dedent(inspect.getsource(dashboard._growth_status))
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    keys = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)

    assert 'base_mb' not in keys and 'adapter_mb' not in keys, \
        f'_growth_status 又用了后端不存在的键: {sorted(keys)}'
    for k in ('base_bytes', 'adapter_bytes', 'base_human', 'adapter_human'):
        assert k in keys, f'_growth_status 返回字典缺少 {k}（现有键：{sorted(keys)}）'

    # 后端契约：status() 真的产出这些键（用临时目录，不碰真实 .star_core）
    from core.growth import GrowthEngine
    with tempfile.TemporaryDirectory() as td:
        st = GrowthEngine(Path(td), log=lambda *a: None, dry_run=True).status()
    for k in ('base_bytes', 'adapter_bytes', 'base_human', 'adapter_human'):
        assert k in st, f'GrowthEngine.status() 不再产出 {k}'


if __name__ == '__main__':
    test_presets_public()
    test_preset_label_lookup()
    test_apply_chosen_writes_config()
    test_is_ui_available_returns_bool()
    test_dashboard_imports_launcher_presets()
    test_growth_status_uses_real_backend_keys()
    print('全部 launcher_ui 测试通过')