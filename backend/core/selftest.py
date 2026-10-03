#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 融合版自检
===================

一条命令体检全部子系统：

    python3 -m core.selftest           # 人类可读报告
    python3 -m core.selftest --json    # 结构化（CI/前端用）

覆盖：Python 依赖 / 基底模型 / LoRA 适配器 / 成长闭环 / 3D 渲染层 / VRM 形象 /
      VRMA 动作 / 长期记忆 / 平台配置 / 老师 Key / 磁盘占用。
"""
from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path

from core.paths import APP_DIR, RESOURCE_DIR

BASE_DIR = APP_DIR
sys.path.insert(0, str(RESOURCE_DIR))

LEVEL_ICON = {'ok': '[OK]', 'warn': '[警告]', 'fail': '[失败]', 'info': '[提示]'}


def _check_deps():
    pkgs = [('PIL', 'Pillow', True), ('numpy', 'numpy', True), ('torch', 'torch', False),
            ('transformers', 'transformers', False), ('peft', 'peft', False),
            ('cv2', 'opencv-python', False), ('sounddevice', 'sounddevice', False),
            ('pyttsx3', 'pyttsx3', False)]
    out = []
    for mod, pipname, required in pkgs:
        try:
            m = importlib.import_module(mod)
            out.append({'name': pipname, 'state': 'ok',
                        'version': getattr(m, '__version__', '')})
        except Exception:                                             # noqa: BLE001
            out.append({'name': pipname, 'state': 'fail' if required else 'warn',
                        'hint': f'pip install {pipname}'})
    return out


def _check_model():
    star = BASE_DIR / '.star_core'
    base = star / 'XLmodel'
    adp = star / 'adapter'
    def size(d):
        if not d.exists():
            return 0
        return sum(p.stat().st_size for p in d.rglob('*')
                   if p.is_file() and p.suffix.lower() in ('.safetensors', '.bin', '.pt', '.gguf'))
    b, a = size(base), size(adp)
    return {'base_bytes': b, 'adapter_bytes': a,
            'base_installed': b > 100 * 1024 * 1024,
            'progress_percent': round(a / b * 100, 2) if b else 0.0,
            'dir': str(base)}


def _check_avatar():
    """检查纯 Python 渲染层（renderer 包）是否完整可用。"""
    need = ['renderer/__init__.py', 'renderer/gltf.py', 'renderer/model.py', 'renderer/pose.py',
            'renderer/vrma.py', 'renderer/camera.py', 'renderer/gl.py', 'renderer/soft.py',
            'renderer/lipsync.py', 'renderer/renderer.py', 'renderer/window.py',
            'renderer/settings.py', 'renderer/app.py']
    missing = [f for f in need if not (BASE_DIR / f).exists()]
    legacy = [str(p.relative_to(BASE_DIR)) for p in (BASE_DIR / 'avatar').rglob('*.js')] \
        if (BASE_DIR / 'avatar').exists() else []
    try:
        from core.avatar import run_headless_probe
        probe = run_headless_probe()
    except Exception as e:                                            # noqa: BLE001
        probe = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    probe.update({'missing': missing, 'legacy_js': legacy,
                  'ok': bool(probe.get('ok')) and not missing and not legacy})
    return probe


def _check_vrm():
    models = sorted((BASE_DIR / 'models').glob('*.vrm'))
    xl = [m for m in models if m.name.startswith('小凌')]
    return {'count': len(models), 'has_xiaoling': bool(xl),
            'xiaoling': xl[0].name if xl else None,
            'xiaoling_mb': round(xl[0].stat().st_size / 1e6, 1) if xl else 0,
            'models': [m.name for m in models],
            'animations': len(list((BASE_DIR / 'animations').glob('*.vrma')))}


def _check_growth():
    try:
        from core.growth import GrowthEngine
        eng = GrowthEngine(log=lambda *a: None)
        st = eng.status()
        st['engine'] = 'ok'
        return st
    except Exception as e:                                            # noqa: BLE001
        return {'engine': 'fail', 'error': f'{type(e).__name__}: {e}'}


def _check_memory():
    try:
        from core.rag import get_rag
        return {'engine': 'ok', **get_rag().stats()}
    except Exception as e:                                            # noqa: BLE001
        return {'engine': 'fail', 'error': str(e)}


def _check_config():
    try:
        from core import config
        cfg = config.load()
        ds = cfg.get('deepseek_api_key', '')
        platforms = cfg.get('platforms', {})
        return {'ok': True, 'version': cfg.get('version'),
                'teacher_ready': bool(ds and ds != '暂未填入'),
                'platforms_enabled': [k for k, v in platforms.items() if v.get('enabled')],
                'path': str(config.CONFIG_PATH)}
    except Exception as e:                                            # noqa: BLE001
        return {'ok': False, 'error': str(e)}


def _check_disk():
    try:
        total, used, free = shutil.disk_usage(str(BASE_DIR))
        def h(n):
            return f'{n / 1024 ** 3:.1f} GB'
        return {'total': h(total), 'used': h(used), 'free': h(free),
                'project_mb': round(sum(p.stat().st_size for p in BASE_DIR.rglob('*')
                                        if p.is_file()) / 1e6, 1)}
    except Exception as e:                                            # noqa: BLE001
        return {'error': str(e)}


def run_all() -> dict:
    report = {
        'python': sys.version.split()[0],
        'deps': _check_deps(),
        'config': _check_config(),
        'model': _check_model(),
        'growth': _check_growth(),
        'avatar': _check_avatar(),
        'vrm': _check_vrm(),
        'memory': _check_memory(),
        'disk': _check_disk(),
    }
    issues = []
    for d in report['deps']:
        if d['state'] == 'fail':
            issues.append(f"缺少必需依赖 {d['name']}（{d.get('hint', '')}）")
    if not report['vrm']['has_xiaoling']:
        issues.append('未找到 小凌.vrm 形象文件（可运行 工具/xiaoling_avatar.py 生成）')
    if not report['avatar'].get('ok'):
        issues.append(f"3D 渲染层不完整：{report['avatar'].get('missing') or report['avatar'].get('error')}")
    if report['avatar'].get('legacy_js'):
        issues.append(f"发现残留 JS 渲染层文件（应删除）：{report['avatar']['legacy_js'][:3]}")
    if not report['config'].get('teacher_ready'):
        issues.append('DeepSeek 老师 Key 未配置（蒸馏学习不可用）')
    if not report['model']['base_installed']:
        issues.append('基底模型未安装（首次启动会按配置档位自动下载，或加入社区群获取）')
    report['issues'] = issues
    report['health'] = 'ok' if not issues else ('warn' if len(issues) < 3 else 'fail')
    return report


def format_report(rep: dict) -> str:
    L = []
    L.append('=' * 62)
    L.append('  小凌 · 融合版自检报告')
    L.append('=' * 62)
    L.append(f"  Python {rep['python']}   健康度：{rep['health'].upper()}")
    L.append('  —— 依赖 ——')
    for d in rep['deps']:
        L.append(f"   {LEVEL_ICON[d['state']]} {d['name']:<16}{d.get('version', '') or d.get('hint', '')}")
    L.append('  —— 配置 ——')
    c = rep['config']
    L.append(f"   配置版本 {c.get('version')}  老师Key {'已配置' if c.get('teacher_ready') else '未配置'}"
             f"  已启用平台 {c.get('platforms_enabled') or '无'}")
    L.append('  —— 模型与成长 ——')
    m, gr = rep['model'], rep['growth']
    L.append(f"   基底 {'已安装' if m['base_installed'] else '未安装'}（{m['base_bytes'] / 1e6:.0f} MB）"
             f"  适配器 {m['adapter_bytes'] / 1e6:.1f} MB  进度 {m['progress_percent']:.1f}%")
    L.append(f"   阶段：{gr.get('stage', gr.get('error', ''))}")
    L.append('  —— 形象 ——')
    v, a = rep['vrm'], rep['avatar']
    L.append(f"   小凌形象 {'[OK] ' + (v['xiaoling'] or '') if v['has_xiaoling'] else '[失败] 缺失'}"
             f"（{v['xiaoling_mb']} MB）")
    L.append(f"   VRM 共 {v['count']} 个  VRMA 动作 {v['animations']} 个")
    L.append(f"   渲染层 {'[OK] 纯 Python 就绪' if a.get('ok') else '[失败] 不完整'}"
             f"  后端 {a.get('backend', '-')}  动作 {a.get('actions', '-')} 个"
             f"  Qt {a.get('qt') or '未安装（用无头/贴图模式）'}")
    mr = rep['memory']
    L.append(f"  —— 记忆 —— {mr.get('items', '?')} 条（{mr.get('path', mr.get('error', ''))}）")
    L.append(f"  —— 磁盘 —— {rep['disk'].get('free', '?')} 可用 / 项目占用 {rep['disk'].get('project_mb', '?')} MB")
    if rep['issues']:
        L.append('  —— 待修复 ——')
        for i in rep['issues']:
            L.append(f"   • {i}")
    else:
        L.append('  [OK] 一切就绪，小凌可以出发了')
    L.append('=' * 62)
    return '\n'.join(L)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    rep = run_all()
    if '--json' in argv:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print(format_report(rep))
    return 0 if rep['health'] != 'fail' else 1


if __name__ == '__main__':
    sys.exit(main())
