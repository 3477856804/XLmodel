#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.wizard —— 环境配置向导（零配置直接启动的关键一环）

设计目标：用户 `python xl.py` 就能跑，不必先跑 setup_kali.sh、不必手改配置文件。
启动时做一次**轻量**体检，缺什么就在这里用 UI 补齐：

    依赖页：缺哪些 pip 包 / 一键安装（QThread + subprocess.Popen 流式日志）/ 国内镜像
            torch 单独作为一个可选项（体积大，且默认源会给 CPU 版覆盖用户的 cu128）
    API 页：DeepSeek Key + Base URL → 写 .star_core/xiaoling_config.json（不再碰 .env）
    模型页：1B / 2B → 写 .star_core/model_choice.txt 并同步 config
    渲染页：auto / gpu / soft / osmesa → 写 config，并提供后端连通性测试

模块结构约定（与 renderer/dashboard.py 一致）：
* **模块级函数全部不依赖 Qt**（`check_env` / `console_env_summary` / `export_report` …），
  这样在没装 PySide6 的机器上也能做体检、打印指引、导出诊断报告；
* 所有 Qt 类都嵌套在 `run_wizard()` 里（QtCore/QtGui/QtWidgets 是那里的局部名）。

跨平台：Windows 不做 apt/nvidia-smi WSL 提示；启动器与 apt 建议只在 Linux/macOS 出现。
"""
from __future__ import annotations

import importlib.metadata as _md
import importlib.util as _iu
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

from renderer.i18n import t

# --------------------------------------------------------------------------- #
#  依赖清单
# --------------------------------------------------------------------------- #
#: 桌宠/界面必需的轻量依赖（与 torch 无关，可安全一键安装）
#: 第 4 项是**探测用的真实导入路径**——不能只探测顶层包名，见 _has_module 的说明。
CORE_DEPS = [
    ('PySide6', 'PySide6', '桌面窗口（桌宠 / 工作台）', 'PySide6.QtWidgets'),
    ('PIL', 'Pillow', '图像处理', 'PIL.Image'),
    ('numpy', 'numpy', '数值计算', 'numpy'),
    ('OpenGL', 'PyOpenGL', '3D 渲染', 'OpenGL.GL'),
    ('edge_tts', 'edge-tts', '在线情感语音（可选）', 'edge_tts'),
]

#: 蒸馏/本地推理引擎：**必须与 torch 一起装**，单独装没有意义
ML_DEPS = [
    ('torch', 'torch', '本地推理与 LoRA 训练（约 2.5GB）', 'torch'),
    ('transformers', 'transformers', '模型加载', 'transformers'),
    ('peft', 'peft', 'LoRA 训练', 'peft'),
    ('accelerate', 'accelerate', '显存分级与 offload', 'accelerate'),
    ('safetensors', 'safetensors', '权重读写', 'safetensors'),
]

MIRRORS = {
    'tuna': 'https://pypi.tuna.tsinghua.edu.cn/simple',
    'aliyun': 'https://mirrors.aliyun.com/pypi/simple/',
    'official': '',
}

#: QApplication 的**模块级强引用**。
#: PySide6 里若 QApplication 只有局部变量引用，run_wizard() 返回后它会被 GC，
#: 底层 C++ 对象随之销毁 —— 之后任何 QWidget 构造都会致命退出
#: （QWidget: Must construct a QApplication before a QWidget）。必须留住它。
_APP_REF: list = []


# --------------------------------------------------------------------------- #
#  体检（零 Qt、尽量零重量级 import）
# --------------------------------------------------------------------------- #
def _dist_version(dist_name: str) -> str:
    """从 dist-info 读版本，**不导入模块**（torch 导入要几秒，不能放在启动路径上）。"""
    try:
        return _md.version(dist_name)
    except Exception:                                                 # noqa: BLE001
        return ''


def _has_module(mod_name: str) -> bool:
    """探测模块**是否真的可导入**（而不是顶层包目录存在）。

    反例（本机实测）：Debian 装了 ``libpyside6-py3-6.9``（C++ 运行时）但没装
    ``python3-pyside6.qtwidgets``，于是 ``PySide6/`` 目录存在、``import PySide6``
    成功，而 ``import PySide6.QtWidgets`` 抛 ModuleNotFoundError。
    若只探测顶层包名，就会得到**假阳性**：向导误报"已就绪"，并且不会把 PySide6
    列进待装清单，用户永远修不好。所以这里探测的是 CORE_DEPS/ML_DEPS 里那条
    真实导入路径。
    """
    try:
        return _iu.find_spec(mod_name) is not None
    except Exception:                                                 # noqa: BLE001
        return False


def _in_venv() -> dict:
    return {
        'active': sys.prefix != getattr(sys, 'base_prefix', sys.prefix),
        'prefix': sys.prefix,
        'base_prefix': getattr(sys, 'base_prefix', sys.prefix),
    }


def _platform_kind() -> dict:
    sysname = platform.system()                       # 'Windows' / 'Linux' / 'Darwin'
    kind = {'Windows': 'win32', 'Linux': 'linux', 'Darwin': 'darwin'}.get(sysname, sysname.lower())
    return {'system': sysname, 'kind': kind,
            'is_windows': kind == 'win32', 'is_linux': kind == 'linux',
            'is_wsl': kind == 'linux' and 'microsoft' in platform.release().lower()}


def check_env(deep_gpu: bool = True) -> dict:
    """环境体检。不导入 torch（只用 find_spec + dist-info），因此很快。

    返回 dict：python / venv / platform / deps / ml / gpu / model / api / render
    """
    rep: dict = {
        'python': sys.version.split()[0],
        'executable': sys.executable,
        'venv': _in_venv(),
        'platform': _platform_kind(),
        'deps': [], 'ml': [],
        'api': {}, 'model': {}, 'render': {},
    }

    for mod, pkg, desc, probe in CORE_DEPS:
        rep['deps'].append({'mod': mod, 'pkg': pkg, 'desc': desc,
                            'ok': _has_module(probe), 'version': _dist_version(pkg)})
    for mod, pkg, desc, probe in ML_DEPS:
        rep['ml'].append({'mod': mod, 'pkg': pkg, 'desc': desc,
                          'ok': _has_module(probe), 'version': _dist_version(pkg)})

    # GPU：用 nvidia-smi（不依赖 torch），这样 torch 没装也能正确推荐 cu128
    if deep_gpu:
        try:
            from core.device import torch_install_plan, nvidia_smi_info
            rep['gpu'] = nvidia_smi_info()
            rep['torch_plan'] = torch_install_plan()
        except Exception as e:                                        # noqa: BLE001
            rep['gpu'] = {'found': False, 'error': f'{type(e).__name__}: {e}'}
            rep['torch_plan'] = {'index_url': '', 'variant': 'cpu', 'reason': ''}
    else:
        rep['gpu'] = {'found': False}
        rep['torch_plan'] = {'index_url': '', 'variant': 'unknown', 'reason': ''}

    # 模型权重：与 xl.py 的口径一致（任意 *.safetensors / *.bin，>10MB 即算已有）
    try:
        from core.paths import APP_DIR
        mdir = Path(APP_DIR) / '.star_core' / 'XLmodel'
        found = []
        if mdir.exists():
            for ext in ('*.safetensors', '*.bin', '*.gguf', '*.pt', '*.pth'):
                for p in mdir.glob(ext):
                    try:
                        if p.stat().st_size > 10 * 1024 * 1024:
                            found.append((p.name, p.stat().st_size))
                    except OSError:
                        pass
        rep['model'] = {'dir': str(mdir), 'files': found,
                        'ok': bool(found),
                        'bytes': sum(s for _, s in found),
                        'choice': _read_model_choice()}
    except Exception as e:                                            # noqa: BLE001
        rep['model'] = {'dir': '', 'files': [], 'ok': False, 'bytes': 0, 'choice': '',
                        'error': f'{type(e).__name__}: {e}'}

    # API Key：只报"是否已配置 + 长度"，绝不回显明文
    try:
        from core import config as _cfg
        cfg = _cfg.load()
        key = str(cfg.get('deepseek_api_key') or '')
        rep['api'] = {'configured': bool(key and key != '暂未填入'),
                      'key_len': len(key) if key != '暂未填入' else 0,
                      'base_url': cfg.get('deepseek_base_url') or '',
                      'path': str(_cfg.CONFIG_PATH)}
    except Exception as e:                                            # noqa: BLE001
        rep['api'] = {'configured': False, 'key_len': 0, 'base_url': '',
                      'path': '', 'error': f'{type(e).__name__}: {e}'}

    try:
        from core import config as _cfg
        rep['render'] = dict(_cfg.load().get('render') or {})
        rep['language'] = _cfg.load().get('language', 'zh')
    except Exception:                                                 # noqa: BLE001
        rep['render'] = {}
    return rep


def _read_model_choice() -> str:
    try:
        from core.paths import APP_DIR
        p = Path(APP_DIR) / '.star_core' / 'model_choice.txt'
        if p.exists():
            return p.read_text(encoding='utf-8').strip()
    except Exception:                                                 # noqa: BLE001
        pass
    return ''


def missing_core(rep: dict) -> list:
    return [d for d in rep.get('deps', []) if not d['ok']]


def missing_ml(rep: dict) -> list:
    return [d for d in rep.get('ml', []) if not d['ok']]


def needs_setup(rep: dict | None = None) -> bool:
    """是否值得弹向导：缺核心依赖 / 缺 API Key / 没有模型权重。"""
    rep = rep or check_env()
    return bool(missing_core(rep)) or not rep['api'].get('configured') \
        or not rep['model'].get('ok')


def env_fingerprint(rep: dict | None = None) -> str:
    """环境指纹：内容不变就不再自动弹向导（配合 wizard.skip_until_change）。"""
    rep = rep or check_env()
    parts = [
        rep['python'],
        ','.join(d['pkg'] for d in missing_core(rep)),
        ','.join(d['pkg'] for d in missing_ml(rep)),
        '1' if rep['api'].get('configured') else '0',
        '1' if rep['model'].get('ok') else '0',
    ]
    return '|'.join(parts)


def should_auto_show() -> bool:
    """启动时是否应该自动弹向导。尊重「不再提醒」与「环境没变就跳过」。"""
    try:
        from core import config as _cfg
        w = _cfg.load().get('wizard') or {}
        if w.get('never_show'):
            return False
        if not needs_setup():
            return False
        skip = str(w.get('skip_until_change') or '')
        if skip and skip == env_fingerprint():
            return False
        return True
    except Exception:                                                 # noqa: BLE001
        return False


def remember_skip() -> str:
    """用户点了「暂时跳过」：记下当前指纹，环境不变就不再自动弹。"""
    fp = env_fingerprint()
    try:
        from core import config as _cfg
        _cfg.patch({'wizard': {'skip_until_change': fp}})
    except Exception:                                                 # noqa: BLE001
        pass
    return fp


def remember_never() -> None:
    """用户点了「不再提醒」。"""
    try:
        from core import config as _cfg
        _cfg.patch({'wizard': {'never_show': True}})
    except Exception:                                                 # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
#  无 Qt 时的控制台兜底  +  诊断报告
# --------------------------------------------------------------------------- #
def console_env_summary(rep: dict | None = None) -> str:
    """没有 PySide6 时用文字把该做的事说清楚（不能只丢一句报错）。"""
    rep = rep or check_env()
    L = ['  ── 环境体检 ──', f"  Python {rep['python']}（{rep['executable']}）"]
    if not rep['venv']['active']:
        L.append('  [提示] 当前不在虚拟环境中，建议 python -m venv .venv 隔离依赖（不强制）')
    miss_c = missing_core(rep)
    miss_m = missing_ml(rep)
    L.append(f"  界面依赖：{'全部就绪' if not miss_c else '缺少 ' + '、'.join(d['pkg'] for d in miss_c)}")
    L.append(f"  蒸馏引擎：{'全部就绪' if not miss_m else '缺少 ' + '、'.join(d['pkg'] for d in miss_m)}")
    g = rep.get('gpu') or {}
    if g.get('found'):
        L.append(f"  显卡：{g.get('name')}（驱动 {g.get('driver')}，sm_{g.get('sm')}）")
    else:
        L.append('  显卡：未检测到 NVIDIA 显卡')
    if rep['platform']['is_wsl']:
        L.append('  [WSL2] 请在 Windows 侧安装 NVIDIA 驱动（建议 ≥ 570）')
    if miss_c:
        L.append('  安装界面依赖：')
        L.append(f'    "{sys.executable}" -m pip install ' + ' '.join(d['pkg'] for d in miss_c))
    if miss_m:
        plan = rep.get('torch_plan') or {}
        L.append('  安装 PyTorch（可选，约 2.5GB）：')
        if plan.get('index_url'):
            L.append(f'    "{sys.executable}" -m pip install torch --index-url {plan["index_url"]}')
            L.append(f'    （{plan.get("reason", "")}）')
        L.append(f'    "{sys.executable}" -m pip install transformers peft accelerate safetensors')
    if not rep['api'].get('configured'):
        L.append(f"  未配置 DeepSeek API Key（可选）：写进 {rep['api'].get('path')} 的 deepseek_api_key")
    if not rep['model'].get('ok'):
        L.append(f"  未检测到基底权重：放进 {rep['model'].get('dir')}（或首次启动自动下载）")
    return '\n'.join(L)


def export_report(rep: dict | None = None, out_dir: Path | str | None = None) -> Path:
    """导出环境诊断报告（方便贴群里求助）。**API Key 只写"已配置/未配置"，不含明文。**"""
    rep = rep or check_env()
    try:
        from core.paths import APP_DIR
        base = Path(out_dir) if out_dir else Path(APP_DIR)
    except Exception:                                                 # noqa: BLE001
        base = Path(out_dir) if out_dir else Path.cwd()
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"诊断报告_{time.strftime('%Y%m%d_%H%M%S')}.txt"

    L = ['=' * 64, '  小凌 · 环境诊断报告', '=' * 64,
         f"  生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
         f"  平台    ：{rep['platform']['system']}"
         + ('（WSL2）' if rep['platform']['is_wsl'] else ''),
         f"  Python  ：{rep['python']}",
         f"  解释器  ：{rep['executable']}",
         f"  虚拟环境：{'是' if rep['venv']['active'] else '否'}（prefix={rep['venv']['prefix']}）",
         '', '  ── 依赖 ──']
    for d in rep['deps'] + rep['ml']:
        L.append(f"   [{'OK' if d['ok'] else '缺失'}] {d['pkg']:<14}{d['version'] or ''}")
    g = rep.get('gpu') or {}
    L += ['', '  ── 显卡 / 算力 ──']
    if g.get('found'):
        L.append(f"   {g.get('name')}  驱动 {g.get('driver')}  sm_{g.get('sm')}")
    else:
        L.append('   未检测到 NVIDIA GPU')
    plan = rep.get('torch_plan') or {}
    if plan:
        L.append(f"   torch 建议安装源：{plan.get('variant')} {plan.get('reason', '')}")
    L += ['', '  ── 配置 ──',
          f"   DeepSeek Key：{'已配置（%d 字符，明文不导出）' % rep['api'].get('key_len', 0) if rep['api'].get('configured') else '未配置'}",
          f"   Base URL    ：{rep['api'].get('base_url', '')}",
          f"   配置文件    ：{rep['api'].get('path', '')}",
          f"   模型权重目录：{rep['model'].get('dir', '')}",
          f"   已有权重    ：{rep['model'].get('files') or '无'}",
          f"   模型档位    ：{rep['model'].get('choice') or '（未选择）'}",
          f"   渲染后端    ：{(rep.get('render') or {}).get('backend', 'auto')}",
          '', '  ── 自检（core.selftest）──']
    try:
        from core.selftest import format_report, run_all
        L.append(format_report(run_all()))
    except Exception as e:                                            # noqa: BLE001
        L.append(f'   自检不可用：{type(e).__name__}: {e}')

    out.write_text('\n'.join(L), encoding='utf-8')
    return out


# --------------------------------------------------------------------------- #
#  Qt 部分
# --------------------------------------------------------------------------- #
def _pip_commands(kind: str, mirror: str, torch_index: str) -> list[list[str]]:
    """给出要执行的 pip 命令序列。

    kind='core' → 只装与 torch 无关的界面依赖
    kind='ml'   → torch（走 PyTorch 官方 index-url，**不能用 pip 镜像**）+
                  其余 ML 包（可以走镜像）
    """
    py = [sys.executable, '-m', 'pip', 'install']
    m = MIRRORS.get(mirror, '')
    if kind == 'core':
        pkgs = [d['pkg'] for d in CORE_DEPS if not _has_module(d[3])]
        if not pkgs:
            return []
        cmd = list(py) + pkgs
        if m:
            cmd += ['-i', m]
        return [cmd]
    # ML：先 torch（官方 CUDA 源），再其余（镜像）
    cmds = []
    if not _has_module('torch'):
        cmd = list(py) + ['torch']
        if torch_index:
            cmd += ['--index-url', torch_index]
        cmds.append(cmd)
    rest = [d['pkg'] for d in ML_DEPS if d['mod'] != 'torch' and not _has_module(d[3])]
    if rest:
        cmd = list(py) + rest
        if m:
            cmd += ['-i', m]
        cmds.append(cmd)
    return cmds


def run_wizard(parent=None, log=print) -> bool:
    """打开环境配置向导。返回 True 表示用户已保存/环境就绪，False 表示取消或没有 Qt。"""
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except Exception as e:                                            # noqa: BLE001
        log(f'  [向导] 没有 PySide6（{e}），改用控制台体检：')
        log(console_env_summary())
        return False

    # 启动路径上通常还没有 QApplication（融合层之后才会建）。
    # 这里先建一个：必须在主线程，且后面 fusion/桌宠会用 instance() 复用同一个。
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv[:1])
    if not _APP_REF:
        _APP_REF.append(app)          # 强引用，别让 Python 把它 GC 掉
    app.setApplicationName('小凌')

    rep = check_env()

    # ---------------------------------------------------------------- 安装线程
    class InstallWorker(QtCore.QThread):
        """QThread + subprocess.Popen：流式读 pip 输出回投 UI，可取消。"""

        line = QtCore.Signal(str)
        done = QtCore.Signal(bool, str)

        def __init__(self, cmds):
            super().__init__()
            self._cmds = cmds
            self._proc = None
            self._cancel = False

        def cancel(self):
            self._cancel = True
            p = self._proc
            if p is not None and p.poll() is None:
                try:
                    p.terminate()
                except Exception:                                     # noqa: BLE001
                    pass

        def run(self):
            ok = True
            for cmd in self._cmds:
                if self._cancel:
                    ok = False
                    self.line.emit('— 已取消 —')
                    break
                self.line.emit('$ ' + ' '.join(cmd))
                try:
                    self._proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding='utf-8', errors='replace', bufsize=1)
                    for ln in self._proc.stdout:                       # type: ignore[union-attr]
                        self.line.emit(ln.rstrip())
                        if self._cancel:
                            break
                    rc = self._proc.wait()
                except Exception as e:                                # noqa: BLE001
                    self.line.emit(f'执行失败：{type(e).__name__}: {e}')
                    rc = -1
                if self._cancel:
                    ok = False
                    self.line.emit('— 已取消 —')
                    break
                if rc != 0:
                    ok = False
                    self.line.emit(f'命令退出码 {rc}')
                    break
            self.done.emit(ok, '完成' if ok else '未完成')

    # ---------------------------------------------------------------- 主对话框
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(t('wizard.title'))
    dlg.resize(720, 620)
    dlg.setStyleSheet('QDialog{background:#faf6f7;}')
    outer = QtWidgets.QVBoxLayout(dlg)
    outer.setContentsMargins(20, 18, 20, 16)
    outer.setSpacing(10)

    head = QtWidgets.QLabel(t('wizard.title'))
    head.setStyleSheet('font-size:17px;font-weight:700;color:#3a2a30;')
    outer.addWidget(head)
    sub = QtWidgets.QLabel(t('wizard.subtitle'))
    sub.setWordWrap(True)
    sub.setStyleSheet('font-size:12px;color:#9a8a90;')
    outer.addWidget(sub)

    tabs = QtWidgets.QTabWidget()
    outer.addWidget(tabs, 1)

    state = {'rep': rep, 'worker': None}

    def _btn(text, color='#d4385c'):
        b = QtWidgets.QPushButton(text)
        b.setFixedHeight(32)
        b.setStyleSheet(f'background:{color};color:white;border:none;'
                        f'border-radius:16px;font-weight:600;padding:0 14px;')
        return b

    def _muted(text=''):
        lb = QtWidgets.QLabel(text)
        lb.setWordWrap(True)
        lb.setStyleSheet('font-size:12px;color:#3a2a30;')
        return lb

    # ------------------------------------------------------------- 依赖页
    dep_tab = QtWidgets.QWidget()
    dv = QtWidgets.QVBoxLayout(dep_tab)
    dv.setContentsMargins(14, 14, 14, 14)
    dep_status = _muted()
    dv.addWidget(dep_status)
    dep_list = QtWidgets.QListWidget()
    dep_list.setStyleSheet('background:#fff;border:1px solid #ecdde2;border-radius:8px;'
                           'font-size:12px;')
    dv.addWidget(dep_list, 1)
    mirror_chk = QtWidgets.QCheckBox(t('deps.mirror'))
    try:
        from core import config as _cfg0
        mirror_chk.setChecked((_cfg0.load().get('wizard') or {}).get('mirror', 'tuna') != 'official')
    except Exception:                                                 # noqa: BLE001
        mirror_chk.setChecked(True)
    mirror_chk.setStyleSheet('font-size:12px;color:#3a2a30;')
    dv.addWidget(mirror_chk)
    torch_hint = _muted()
    dv.addWidget(torch_hint)
    dep_log = QtWidgets.QPlainTextEdit()
    dep_log.setReadOnly(True)
    dep_log.setMaximumBlockCount(2000)
    dep_log.setStyleSheet('background:#fff;border:1px solid #ecdde2;border-radius:8px;'
                          'font-size:11px;font-family:monospace;')
    dep_log.setVisible(False)
    dv.addWidget(dep_log, 1)
    dep_row = QtWidgets.QHBoxLayout()
    btn_install = _btn(t('deps.install'))
    btn_torch = _btn(t('deps.install_torch'), '#5a7a8a')
    btn_cancel = _btn(t('common.cancel'), '#9a8a90')
    btn_cancel.setVisible(False)
    for b in (btn_install, btn_torch, btn_cancel):
        dep_row.addWidget(b)
    dep_row.addStretch(1)
    dv.addLayout(dep_row)

    def _fill_deps():
        r = state['rep']
        dep_list.clear()
        for d in r['deps'] + r['ml']:
            mark = '✅' if d['ok'] else '❌'
            item = QtWidgets.QListWidgetItem(
                f"{mark} {d['pkg']:<14}{d['version'] or '':<12}{d['desc']}")
            dep_list.addItem(item)
        mc, mm = missing_core(r), missing_ml(r)
        if not mc and not mm:
            dep_status.setText('✅ ' + t('deps.all_ok'))
        else:
            dep_status.setText('⚠ ' + t('deps.missing_n', n=len(mc) + len(mm)))
        if not r['venv']['active']:
            dep_status.setText(dep_status.text() + '\n' + t('deps.venv_hint'))
        if os.environ.get('XL_NO_AUTO_DEPS') == '1':
            dep_status.setText(dep_status.text() + '\n' + t('deps.no_auto'))
        # torch 文案
        torch_ok = _has_module('torch')
        if torch_ok:
            torch_hint.setText(t('deps.torch_ok', ver=_dist_version('torch')))
        else:
            plan = r.get('torch_plan') or {}
            g = r.get('gpu') or {}
            if g.get('found'):
                torch_hint.setText(t('deps.torch_absent') + '\n'
                                   + t('deps.torch_recommend', gpu=g.get('name', ''),
                                       variant=plan.get('variant', 'cpu')))
            else:
                torch_hint.setText(t('deps.torch_absent') + '\n' + t('deps.torch_cpu'))
        btn_install.setEnabled(bool(mc))
        btn_torch.setEnabled(bool(mm) and os.environ.get('XL_NO_AUTO_DEPS') != '1')

    def _run_install(kind):
        if getattr(sys, 'frozen', False):
            # 打包版（exe）：依赖已内嵌，sys.executable 是 exe 而不是 Python，
            # 在这里调 pip 只会得到莫名其妙的错误。直接说清楚。
            dep_log.setVisible(True)
            dep_log.appendPlainText(
                '打包版（exe）不支持在向导里安装依赖：依赖已内嵌在程序内。\n'
                '若确有缺失，请改用源码方式运行，并在源码环境里安装（或跑 setup_kali.sh）。')
            return
        if os.environ.get('XL_NO_AUTO_DEPS') == '1':
            dep_log.setVisible(True)
            dep_log.appendPlainText(t('deps.no_auto'))
            return
        mirror = 'tuna' if mirror_chk.isChecked() else 'official'
        try:
            from core import config as _cfg1
            _cfg1.patch({'wizard': {'mirror': mirror}})
        except Exception:                                             # noqa: BLE001
            pass
        plan = (state['rep'].get('torch_plan') or {})
        cmds = _pip_commands(kind, mirror, plan.get('index_url', ''))
        if not cmds:
            dep_log.setVisible(True)
            dep_log.appendPlainText('没有需要安装的包。')
            return
        dep_log.setVisible(True)
        dep_log.clear()
        btn_install.setEnabled(False)
        btn_torch.setEnabled(False)
        btn_cancel.setVisible(True)
        w = InstallWorker(cmds)
        state['worker'] = w
        w.line.connect(dep_log.appendPlainText)

        def _fin(ok, msg):
            btn_cancel.setVisible(False)
            dep_log.appendPlainText(f'=== {msg} ===')
            state['worker'] = None
            state['rep'] = check_env()
            _fill_deps()

        w.done.connect(_fin)
        w.start()

    btn_install.clicked.connect(lambda: _run_install('core'))
    btn_torch.clicked.connect(lambda: _run_install('ml'))
    btn_cancel.clicked.connect(lambda: state['worker'] and state['worker'].cancel())

    # ------------------------------------------------------------- API 页
    api_tab = QtWidgets.QWidget()
    av = QtWidgets.QVBoxLayout(api_tab)
    av.setContentsMargins(14, 14, 14, 14)
    av.addWidget(_muted(t('api.header')))
    av.addWidget(_muted(t('api.key')))
    key_edit = QtWidgets.QLineEdit()
    key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
    key_edit.setPlaceholderText('sk-...')
    key_edit.setStyleSheet('background:#fff;border:1px solid #ecdde2;border-radius:8px;padding:6px;')
    av.addWidget(key_edit)
    api_state = _muted()
    av.addWidget(api_state)
    av.addWidget(_muted(t('api.base_url')))
    url_edit = QtWidgets.QLineEdit(rep['api'].get('base_url', ''))
    url_edit.setStyleSheet('background:#fff;border:1px solid #ecdde2;border-radius:8px;padding:6px;')
    av.addWidget(url_edit)
    av.addWidget(_muted(t('api.hint')))
    av.addStretch(1)
    api_row = QtWidgets.QHBoxLayout()
    btn_save_api = _btn(t('common.save'))
    api_row.addWidget(btn_save_api)
    api_row.addStretch(1)
    av.addLayout(api_row)

    def _fill_api():
        a = state['rep']['api']
        api_state.setText(t('api.key_set', n=a.get('key_len', 0)) if a.get('configured')
                          else t('api.key_unset'))
        mig = _migrated_keys()
        if mig:
            api_state.setText(api_state.text() + '\n' + t('api.migrated', keys='、'.join(mig)))

    def _migrated_keys():
        return state.get('migrated', [])

    def _save_api():
        url = url_edit.text().strip()
        if url and not url.startswith(('http://', 'https://')):
            QtWidgets.QMessageBox.warning(dlg, t('common.note'), t('api.bad_url'))
            return
        changes = {}
        key = key_edit.text().strip()
        if key:
            changes['deepseek_api_key'] = key
        if url:
            changes['deepseek_base_url'] = url
        try:
            from core import config as _cfg2
            if changes:
                _cfg2.patch(changes)
            api_state.setText(t('common.saved'))
            key_edit.clear()
            state['rep'] = check_env()
            _fill_api()
        except Exception as e:                                        # noqa: BLE001
            QtWidgets.QMessageBox.warning(dlg, t('common.failed'), str(e))

    btn_save_api.clicked.connect(_save_api)

    # ------------------------------------------------------------- 模型页
    mdl_tab = QtWidgets.QWidget()
    mv = QtWidgets.QVBoxLayout(mdl_tab)
    mv.setContentsMargins(14, 14, 14, 14)
    mv.addWidget(_muted(t('model.header')))
    mdl_group = QtWidgets.QButtonGroup(mdl_tab)
    cur_choice = rep['model'].get('choice') or ''
    for key, label in (('自研2B模型', 'MiniCPM5-2B（约 4.8GB，默认）'),
                       ('自研1B模型', 'MiniCPM5-1B（约 2.1GB，轻量）')):
        rb = QtWidgets.QRadioButton(label)
        rb.setStyleSheet('font-size:12px;color:#3a2a30;')
        rb.setChecked(key == cur_choice or (not cur_choice and key == '自研2B模型'))
        rb.setProperty('choice_key', key)
        mdl_group.addButton(rb)
        mv.addWidget(rb)
    mdl_state = _muted()
    mv.addWidget(mdl_state)
    mv.addWidget(_muted(t('model.hint')))
    # 权重状态 + **显式下载**入口（auto_download 默认关，这里是唯一的 GUI 触发点）
    mdl_weights = _muted()
    mv.addWidget(mdl_weights)
    mdl_log = QtWidgets.QPlainTextEdit()
    mdl_log.setReadOnly(True)
    mdl_log.setMaximumBlockCount(500)
    mdl_log.setStyleSheet('background:#fff;border:1px solid #ecdde2;border-radius:8px;'
                          'font-size:11px;font-family:monospace;')
    mdl_log.setVisible(False)
    mv.addWidget(mdl_log, 1)
    mdl_row = QtWidgets.QHBoxLayout()
    btn_save_mdl = _btn(t('common.save'))
    btn_dl_mdl = _btn(t('model.download'), '#5a7a8a')
    mdl_row.addWidget(btn_save_mdl)
    mdl_row.addWidget(btn_dl_mdl)
    mdl_row.addStretch(1)
    mv.addLayout(mdl_row)

    def _human(n):
        n = float(n or 0)
        for u, d in (('GB', 1 << 30), ('MB', 1 << 20), ('KB', 1 << 10)):
            if n >= d:
                return f'{n / d:.1f} {u}'
        return f'{int(n)} B'

    def _fill_model():
        m = state['rep'].get('model') or {}
        if m.get('ok'):
            mdl_weights.setText('✅ ' + t('model.weights_ok', human=_human(m.get('bytes'))))
        else:
            mdl_weights.setText('⚠ ' + t('model.weights_missing'))
        btn_dl_mdl.setEnabled(not m.get('ok') and getattr(sys, 'frozen', False) is False)

    def _save_model():
        btn = mdl_group.checkedButton()
        if btn is None:
            return
        key = btn.property('choice_key')
        try:
            from core.paths import APP_DIR
            star = Path(APP_DIR) / '.star_core'
            star.mkdir(parents=True, exist_ok=True)
            (star / 'model_choice.txt').write_text(str(key), encoding='utf-8')
            from core import config as _cfg3
            _cfg3.patch({'model': {'base_model': key}})
            mdl_state.setText(t('common.saved') + f'：{key}')
            state['rep'] = check_env()
            _fill_model()
        except Exception as e:                                        # noqa: BLE001
            QtWidgets.QMessageBox.warning(dlg, t('common.failed'), str(e))

    def _download_model():
        """显式下载基底模型（auto_download 默认关闭后，这是 GUI 唯一的触发点）。"""
        if getattr(sys, 'frozen', False):
            QtWidgets.QMessageBox.information(dlg, t('common.note'), t('deps.no_auto'))
            return
        size = '约 4.8GB' if (mdl_group.checkedButton() is None
                             or mdl_group.checkedButton().property('choice_key') == '自研2B模型') else '约 2.1GB'
        if QtWidgets.QMessageBox.question(
                dlg, t('model.download'),
                t('model.download_confirm', size=size),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No) != QtWidgets.QMessageBox.Yes:
            return
        # 先把当前选中的档位落盘，保证下载的是用户选的档位
        _save_model()
        mdl_log.setVisible(True)
        mdl_log.appendPlainText(t('model.downloading'))
        btn_dl_mdl.setEnabled(False)

        def _worker():
            msg = None
            try:
                # 复用 xl.py 里的实现（若已加载就直接取，避免重复执行其模块级融合安装）
                mod = sys.modules.get('xl')
                if mod is None:
                    import xl as mod                    # noqa: PLC0415
                # force=True：用户在这里明确点了按钮
                okd = mod.ensure_base_model(force=True)
                msg = t('model.download_done') if okd else t('model.download_fail', msg='未完成')
            except Exception as e:                                # noqa: BLE001
                msg = t('model.download_fail', msg=f'{type(e).__name__}: {e}')
            QtCore.QMetaObject.invokeMethod(mdl_log, 'appendPlainText',
                QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, msg))
            QtCore.QMetaObject.invokeMethod(btn_dl_mdl, 'setEnabled',
                QtCore.Qt.QueuedConnection, QtCore.Q_ARG(bool, True))
            state['rep'] = check_env()          # 后台刷新报告（下次填充时生效）

        threading.Thread(target=_worker, daemon=True, name='wizard-model-download').start()

    btn_save_mdl.clicked.connect(_save_model)
    btn_dl_mdl.clicked.connect(_download_model)

    # ------------------------------------------------------------- 渲染页
    rnd_tab = QtWidgets.QWidget()
    rv = QtWidgets.QVBoxLayout(rnd_tab)
    rv.setContentsMargins(14, 14, 14, 14)
    rv.addWidget(_muted(t('render.header')))
    be_combo = QtWidgets.QComboBox()
    for val, label in (('auto', t('render.auto')), ('gpu', t('render.gpu')),
                       ('soft', t('render.soft')), ('osmesa', t('render.osmesa'))):
        be_combo.addItem(label, val)
    try:
        from core import config as _cfg4
        cur_be = ((_cfg4.load().get('render') or {}).get('backend') or 'auto')
        idx = be_combo.findData(cur_be)
        if idx >= 0:
            be_combo.setCurrentIndex(idx)
    except Exception:                                                 # noqa: BLE001
        pass
    be_combo.setStyleSheet('background:#fff;border:1px solid #ecdde2;border-radius:8px;padding:6px;')
    rv.addWidget(be_combo)
    rnd_state = _muted()
    rv.addWidget(rnd_state)
    rv.addWidget(_muted(t('render.hint')))
    if rep['platform']['is_linux'] and not rep['platform']['is_windows']:
        rv.addWidget(_muted('· ' + t('gpu.linux_hint')))
    rv.addStretch(1)
    rnd_row = QtWidgets.QHBoxLayout()
    btn_save_rnd = _btn(t('common.save'))
    btn_probe = _btn(t('render.probe'), '#5a7a8a')
    rnd_row.addWidget(btn_save_rnd)
    rnd_row.addWidget(btn_probe)
    rnd_row.addStretch(1)
    rv.addLayout(rnd_row)

    def _save_render():
        val = be_combo.currentData()
        try:
            from core import config as _cfg5
            _cfg5.patch({'render': {'backend': val}})
            os.environ['XIAOLING_RENDER_BACKEND'] = '' if val == 'auto' else str(val)
            rnd_state.setText(t('common.saved') + f'：{val}')
        except Exception as e:                                        # noqa: BLE001
            QtWidgets.QMessageBox.warning(dlg, t('common.failed'), str(e))

    def _probe():
        val = be_combo.currentData() or 'auto'
        rnd_state.setText('…')
        QtWidgets.QApplication.processEvents()
        try:
            from renderer.renderer import AvatarRenderer
            r = AvatarRenderer(backend=('auto' if val == 'auto' else val), width=80, height=100,
                               focus='bust', log=lambda *a: None)
            rnd_state.setText(t('render.probe_ok', name=r.backend_kind))
        except Exception as e:                                        # noqa: BLE001
            rnd_state.setText(t('render.probe_fail', name=val, err=f'{type(e).__name__}: {e}'))

    btn_save_rnd.clicked.connect(_save_render)
    btn_probe.clicked.connect(_probe)

    tabs.addTab(dep_tab, t('tab.deps'))
    tabs.addTab(api_tab, t('tab.api'))
    tabs.addTab(mdl_tab, t('tab.model'))
    tabs.addTab(rnd_tab, t('tab.render'))

    # ------------------------------------------------------------- 底部
    never_chk = QtWidgets.QCheckBox(t('common.never_show'))
    never_chk.setStyleSheet('font-size:12px;color:#9a8a90;')
    outer.addWidget(never_chk)
    bot = QtWidgets.QHBoxLayout()
    btn_report = _btn(t('common.export_report'), '#5a8a6a')
    btn_recheck = _btn(t('common.recheck'), '#9a8a90')
    btn_skip = _btn(t('common.skip'), '#9a8a90')
    btn_close = _btn(t('common.close'))
    for b in (btn_report, btn_recheck):
        bot.addWidget(b)
    bot.addStretch(1)
    bot.addWidget(btn_skip)
    bot.addWidget(btn_close)
    outer.addLayout(bot)

    def _report():
        try:
            p = export_report(check_env())
            QtWidgets.QMessageBox.information(dlg, t('report.title'), t('report.saved', path=str(p)))
        except Exception as e:                                        # noqa: BLE001
            QtWidgets.QMessageBox.warning(dlg, t('report.title'), t('report.failed', err=str(e)))

    def _recheck():
        state['rep'] = check_env()
        _fill_deps()
        _fill_api()
        dep_log.setVisible(True)
        dep_log.appendPlainText('=== ' + t('common.recheck') + ' ===')

    def _skip():
        if never_chk.isChecked():
            remember_never()
        else:
            remember_skip()
        dlg.reject()

    btn_report.clicked.connect(_report)
    btn_recheck.clicked.connect(_recheck)
    btn_skip.clicked.connect(_skip)
    btn_close.clicked.connect(dlg.accept)

    # 启动时先把历史 .env 迁进来（甲-1），再填 UI
    try:
        from core import config as _cfg6
        _mig = _cfg6.migrate_legacy_env(log=lambda *a: None)
        state['migrated'] = _mig.get('migrated') or []
        if state['migrated']:
            state['rep'] = check_env()
    except Exception:                                                 # noqa: BLE001
        state['migrated'] = []

    _fill_deps()
    _fill_api()
    _fill_model()

    if not rep['platform']['is_windows'] and (rep.get('gpu') or {}).get('wsl'):
        # 只在**显卡没被识别出来**时才提示装 Windows 侧驱动。
        # 之前是无条件显示，于是在"驱动正常 + 显卡已识别 + CUDA 可用"的机器上
        # 也会让用户去重装驱动，属于误导（实测 RTX 5060/驱动 592.01 也会被提示）。
        if not (rep.get('gpu') or {}).get('found'):
            dv.addWidget(_muted('ℹ ' + t('gpu.wsl_hint')))

    # ⚠️ 关闭向导不能终止整个进程：向导往往是此刻唯一的窗口，而 Qt 默认
    # quitOnLastWindowClosed=True —— 关掉最后一个窗口会让 QApplication 直接退出，
    # 后面的桌宠就没机会启动（这正是日志里"点了暂时跳过，程序自己退了"的原因）。
    # 只在向导这段时间内关掉它，返回前恢复，避免影响工作台/桌宠的原有语义。
    _prev_qolwc = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    try:
        result = bool(dlg.exec())
    finally:
        app.setQuitOnLastWindowClosed(_prev_qolwc)
    return result


def main(argv=None) -> int:
    """给 `python -m renderer.wizard` 用的入口。"""
    import argparse
    ap = argparse.ArgumentParser(description='小凌 · 环境配置向导')
    ap.add_argument('--check', action='store_true', help='只做体检并打印（不开窗）')
    ap.add_argument('--report', action='store_true', help='只导出诊断报告')
    a = ap.parse_args(argv)
    if a.check:
        print(console_env_summary())
        return 0
    if a.report:
        print(export_report())
        return 0
    return 0 if run_wizard() else 1


if __name__ == '__main__':
    sys.exit(main())
