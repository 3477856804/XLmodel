# -*- coding: utf-8 -*-
"""小凌 · 自有沙箱环境。

为什么要有沙箱
==============
用户从模型商店下载的 GGUF 动辄几个 GB，工具执行（终端、文件读写、插件）也
需要一个可控范围。如果这些都落在程序所在目录，会立刻遇到三个问题：

    1) 程序装到 Program Files 写不进去，下到一半失败；
    2) 升级覆盖安装就把用户辛苦下载的模型一起抹掉；
    3) 工具可以任意读写整个磁盘，一旦提示词被注入就是实打实的安全事故。

所以沙箱统一收敛到**本机用户数据目录**：

    Windows   %LOCALAPPDATA%\\Xiaoling\\
    Linux     $XDG_DATA_HOME 或 ~/.local/share/xiaoling/
    macOS     ~/Library/Application Support/Xiaoling/
    Android   交给 Termux 侧的实现（本模块不参与）

目录结构
========
    <沙箱根>/
    ├── runtime/            ← APP_DIR（XIAOLING_HOME），后端的所有可写数据
    │   ├── .star_core/     ← 配置、记忆、插件
    │   │   └── models/     ← 模型商店下载的 GGUF / HF 模型放这里
    │   └── data/           ← 聊天记录、截图、成长日志
    ├── workspace/          ← 工具（终端 / 文件 / 插件）的默认工作区
    ├── tmp/                ← 临时文件
    └── logs/               ← 审计与运行日志

``runtime`` 这一层的划分是为了避开 Flutter：Windows 版 Flutter 的 Release 产物
自带一个 ``data/`` 目录（app.so、icudtl.dat、flutter_assets），若让后端数据也写到
程序根目录，两者会撞名混在一起。见 packaging/runtime_hook.py。

关键约定
========
* **模型目录必须复用 ``config.STAR_DIR/"models"``** —— LocalModel 就是用这个路径
  做 store_dir 的。沙箱自己再立一个 models 目录会导致"下载成功了但列表里看不见"。
* 工具执行一律以 ``workspace/`` 为 cwd，且只放行沙箱内的路径。
* 绝对路径逃逸（``..``、盘符、家目录外的路径）一律拒绝，且不提供删除能力
  （项目红线：任何情况下不删除文件，需要移除的走 core/quarantine）。
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

try:                                    # 兼容「直接 import」与「作为包模块导入」
    from . import config as _cfg
except Exception:                       # pragma: no cover
    import config as _cfg               # type: ignore

_lock = threading.RLock()

# 命令超时兜底：防止注入类提示词让工具永久挂起
MAX_EXEC_SECONDS = int(os.environ.get('XIAOLING_SANDBOX_TIMEOUT', '60'))

# 危险命令黑名单（保守清单，宁可少放行）
_DENY_TOKENS = (
    'format ', 'del /f', 'rm -rf /', 'rm -rf ~', 'shutdown', 'shutdown.exe',
    'diskpart', 'mkfs', ':(){', 'chmod -r 777 /',
)


# ---------------------------------------------------------------- 路径
def root() -> Path:
    """沙箱根目录。可用 XIAOLING_SANDBOX_ROOT 覆盖（打包时由 runtime_hook 设定）。"""
    env = os.environ.get('XIAOLING_SANDBOX_ROOT')
    if env:
        return Path(env).expanduser().resolve()
    return _cfg.app_dir()


def workspace_dir() -> Path:
    return root() / 'workspace'


def tmp_dir() -> Path:
    return root() / 'tmp'


def logs_dir() -> Path:
    return root() / 'logs'


def models_dir() -> Path:
    """模型存放目录 —— 必须与 LocalModel 的 store_dir 完全一致。

    LocalModel 用的是 ``STAR_DIR / "models"``，这里若返回别的路径，会出现
    "下载完成但模型列表看不到" 的经典不一致问题。
    """
    return _cfg.STAR_DIR / 'models'


def _mk(p: Path) -> None:
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def ensure() -> dict:
    """建立沙箱目录结构。幂等，可反复调用。返回路径快照。"""
    with _lock:
        for d in (root(), workspace_dir(), tmp_dir(), logs_dir(),
                  models_dir(), _cfg.STAR_DIR, _cfg.DATA_DIR):
            _mk(d)
        return paths()


def paths() -> dict:
    return {
        'root': str(root()),
        'workspace': str(workspace_dir()),
        'tmp': str(tmp_dir()),
        'logs': str(logs_dir()),
        'models': str(models_dir()),
        'app_dir': str(_cfg.app_dir()),
        'platform': platform.system().lower(),
    }


# ---------------------------------------------------------------- 用量
def _dir_bytes(p: Path, cap: int = 20000) -> tuple:
    """统计目录体积。（文件数，字节数）遍历上限 cap，避免扫几 GB 时卡死。"""
    n = size = 0
    if not p.exists():
        return 0, 0
    try:
        for f in p.rglob('*'):
            if f.is_file():
                try:
                    size += f.stat().st_size
                except OSError:
                    continue
                n += 1
                if n > cap:
                    break
    except OSError:
        pass
    return n, size


def _human(n: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} PB'


def usage() -> dict:
    """沙箱内各区域的体积（供 UI 显示"沙箱占了多少空间"）。"""
    with _lock:
        nf, nb = _dir_bytes(models_dir())
        root_n, root_b = _dir_bytes(root())
        try:
            total, used, free = shutil.disk_usage(str(root()))
        except Exception:
            total = used = free = 0
        return {
            'models_count': nf,
            'models_bytes': nb,
            'models_human': _human(nb),
            'sandbox_bytes': root_b,
            'sandbox_human': _human(root_b),
            'sandbox_files': root_n,
            'disk_free_bytes': free,
            'disk_free_human': _human(free),
            'disk_total_human': _human(total),
        }


# ---------------------------------------------------------------- 路径白名单
def is_path_allowed(p: str | Path) -> bool:
    """目标路径是否落在沙箱内。工具执行前的第一道闸门。"""
    try:
        t = Path(p).expanduser()
        if not t.is_absolute():
            t = (workspace_dir() / t)
        t = t.resolve()
        for base in (workspace_dir(), tmp_dir(), models_dir(),
                     _cfg.STAR_DIR, _cfg.DATA_DIR, root()):
            try:
                b = Path(base).resolve()
                if t == b or b in t.parents:
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def guard_path(p: str | Path) -> Path:
    """白名单检查，不通过直接抛 PermissionError（调用方负责转成友好提示）。"""
    t = Path(p).expanduser()
    if not t.is_absolute():
        t = workspace_dir() / t
    t = t.resolve()
    if not is_path_allowed(t):
        raise PermissionError(
            f'路径超出沙箱范围，已拒绝：{t}\n'
            f'允许的范围：{root()}')
    return t


# ---------------------------------------------------------------- 执行
def run(command: str, timeout: int | None = None, cwd: str | None = None) -> dict:
    """在沙箱内执行一条命令。

    * cwd 固定为 workspace/（除非显式给出且通过白名单）
    * 只看黑名单不够，超时是第二道保险 —— 注入类提示词最爱让命令永久挂起
    * **不提供任何删除能力**（项目红线）
    """
    ensure()
    cmd = (command or '').strip()
    if not cmd:
        return {'ok': False, 'error': '命令为空'}

    low = cmd.lower()
    for tok in _DENY_TOKENS:
        if tok in low:
            return {'ok': False, 'error': f'危险命令已被沙箱拦截：{tok.strip()}'}

    work = Path(cwd) if cwd else workspace_dir()
    try:
        work = guard_path(work)
    except PermissionError as e:
        return {'ok': False, 'error': str(e)}
    if not work.is_dir():
        work = workspace_dir()

    secs = timeout or MAX_EXEC_SECONDS
    env = dict(os.environ)
    env['XIAOLING_SANDBOX'] = '1'
    try:
        cp = subprocess.run(
            cmd, shell=True, cwd=str(work), env=env,
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=secs,
        )
        return {
            'ok': cp.returncode == 0,
            'code': cp.returncode,
            'stdout': (cp.stdout or '')[:20000],
            'stderr': (cp.stderr or '')[:8000],
            'cwd': str(work),
        }
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': f'命令超时（>{secs}s），已终止'}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def write_file(rel: str, content: str) -> dict:
    """在沙箱 workspace 里写文件（供让小凌做"开发"类任务使用）。"""
    try:
        t = workspace_dir() / rel
        t = guard_path(t)
        if t.exists() and t.is_dir():
            return {'ok': False, 'error': f'目标是目录：{t}'}
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(content, encoding='utf-8')
        return {'ok': True, 'path': str(t), 'bytes': len(content.encode('utf-8'))}
    except PermissionError as e:
        return {'ok': False, 'error': str(e)}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def read_file(rel: str) -> dict:
    try:
        t = Path(rel)
        if not t.is_absolute():
            t = workspace_dir() / rel
        t = guard_path(t)
        if not t.is_file():
            return {'ok': False, 'error': f'不存在或不是文件：{t}'}
        s = t.read_text(encoding='utf-8', errors='replace')
        return {'ok': True, 'path': str(t), 'content': s[:200000]}
    except PermissionError as e:
        return {'ok': False, 'error': str(e)}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def list_dir(rel: str = '') -> dict:
    try:
        t = workspace_dir() if not rel else (workspace_dir() / rel)
        t = guard_path(t)
        if not t.is_dir():
            return {'ok': False, 'error': f'不是目录：{t}'}
        items = []
        for p in sorted(t.iterdir(), key=lambda x: x.name.lower())[:500]:
            items.append({
                'name': p.name,
                'dir': p.is_dir(),
                'size': (p.stat().st_size if p.is_file() else 0),
            })
        return {'ok': True, 'path': str(t), 'items': items}
    except PermissionError as e:
        return {'ok': False, 'error': str(e)}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


# ---------------------------------------------------------------- 状态
def model_progress() -> dict:
    """正在下载的模型进度快照（model.py 会往 TASKS 里写）。"""
    try:
        from . import model as _model
        tasks = getattr(_model, 'TASKS', None)
        if isinstance(tasks, dict):
            return {k: dict(v) for k, v in tasks.items()}
    except Exception:
        pass
    return {}


def status() -> dict:
    """给 UI 的完整状态包：路径 + 用量 + 下载进度。"""
    ensure()
    u = usage()
    return {
        'started': True,
        'supported': True,
        'paths': paths(),
        'usage': u,
        'progress': model_progress(),
        'updated': datetime.now().isoformat(timespec='seconds'),
    }


if __name__ == '__main__':      # 手动巡检：python -m backend.core.sandbox
    import json
    print(json.dumps(status(), ensure_ascii=False, indent=2))
