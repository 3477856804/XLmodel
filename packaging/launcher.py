#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 单文件启动器

用户视角：拿到一个 `小凌.exe`，双击，界面出来。就这一步。

为什么需要一个启动器
====================
Flutter 桌面应用在 Windows 上的形态天生不是单个文件，而是：

    frontend.exe + flutter_windows.dll + data/(app.so, icudtl.dat, flutter_assets) + 各插件 dll

后端又是一整套 Python 运行时。两者合起来两百来个文件。想让用户"只双击一个 exe"，
只有两条路：一是做成自解压包（本质是压缩包 exe，体验差、每次都要解压），
二是像现在这样——exe 本体携带资源，**首次运行一次性释放到本机用户目录**，
之后直接从那里启动。

后者是商业软件的通行做法，好处很实在：
    · 用户永远只面对一个 exe；
    · 第二次起冷启动就是毫秒级（不再解压）；
    · 释放目录在 %LOCALAPPDATA%，不需要管理员权限，装到只读位置也能跑；
    · 覆盖升级 exe 会自动检测到版本变化并重新释放。

资源如何塞进 exe
================
构建时把整个运行目录打成 zip，追加到 exe 尾部（Windows PE 允许附加数据，
不影响运行）。文件最后 30 字节是定长头，**顺序必须与 build_single_exe.py 的
写入顺序严格一致**：

    [payload: zip 数据]
    [payload_len: 8B 大端][magic: 6B = b'XLPAY1'][version: 16B ASCII]  ← 末尾 30B

即尾部 30 字节内部是 [len 0:8][magic 8:14][version 14:30]。
本文件启动时从自身尾部反向解析出这段 zip，读到内存后解压。

生命周期
========
    1. 校验 / 释放资源到 %LOCALAPPDATA%\\Xiaoling\\app
    2. 静默拉起 backend.exe（CREATE_NO_WINDOW，用户看不到控制台）
    3. 拉起 frontend.exe，阻塞等待它退出
    4. 前端退出后回收后端进程，避免留下孤儿进程占着 50051
"""
import os
import shutil
import struct
import subprocess
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path

MAGIC = b'XLPAY1'
HEADER_LEN = 30          # version(16) + len(8) + magic(6)
VERSION_LEN = 16

APP_NAME = 'Xiaoling'
# assemble_windows.py 会把 frontend.exe 重命名成 小凌.exe（给用户看的名字），
# 但直接封装运行目录时可能仍是原名。两个都认，避免名字一变就起不来。
FRONTEND_CANDIDATES = ('小凌.exe', 'frontend.exe')
BACKEND = 'backend.exe'


def find_frontend(root: Path):
    for n in FRONTEND_CANDIDATES:
        p = root / n
        if p.is_file():
            return p
    return None


# ---------------------------------------------------------------- 用户目录
def user_root() -> Path:
    """本机用户根目录。Windows 之外的分支保留，方便同一套代码打全平台。"""
    if sys.platform.startswith('win'):
        base = os.environ.get('LOCALAPPDATA') or \
            os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
        return Path(base) / APP_NAME
    if sys.platform == 'darwin':
        return Path(os.path.expanduser('~')) / 'Library' / 'Application Support' / APP_NAME
    base = os.environ.get('XDG_DATA_HOME') or \
        Path(os.path.expanduser('~')) / '.local' / 'share'
    return Path(base) / APP_NAME.lower()


def app_root() -> Path:
    """释放目标目录（程序本体）。"""
    return user_root() / 'app'


# ---------------------------------------------------------------- 尾部 payload
def _self_payload() -> tuple:
    """从自身尾部取出 (version, zip_bytes)。没有 payload 时返回 (None, None)。"""
    try:
        exe = Path(sys.executable)
        size = exe.stat().st_size
        if size <= HEADER_LEN:
            return None, None
        with open(exe, 'rb') as f:
            f.seek(size - HEADER_LEN)
            tail = f.read(HEADER_LEN)
            # 布局：[len:8][magic:6][version:16]，与 build_single_exe.py 的
            # seal() 写入顺序一一对应。早期版本这里按 [version][len][magic]
            # 解析，与写入不符，导致启动器误判"没有内置资源"。
            if tail[8:14] != MAGIC:
                return None, None
            ln = struct.unpack('>Q', tail[0:8])[0]
            version = tail[14:30].decode('ascii', 'ignore').strip()
            start = size - HEADER_LEN - ln
            if start < 0 or ln <= 0:
                return None, None
            f.seek(start)
            return version, f.read(ln)
    except Exception as e:                                  # noqa: BLE001
        print(f'读取内置资源失败：{e}')
        return None, None


def _extract_payload(blob: bytes, dest: Path) -> None:
    with zipfile.ZipFile(BytesIO(blob)) as z:
        z.extractall(dest)


def ensure_extracted(version: str, blob: bytes) -> None:
    """资源缺失或版本变了才释放。返回 True 表示这次实际解压了。"""
    dest = app_root()
    marker = dest / '.appversion'
    if dest.is_dir() and marker.exists():
        try:
            if marker.read_text(encoding='utf-8').strip() == version:
                return
        except Exception:                                   # noqa: BLE001
            pass
    dest.mkdir(parents=True, exist_ok=True)
    print(f'首次运行，正在释放运行资源到 {dest} …')
    t0 = time.time()
    _extract_payload(blob, dest)
    try:
        (dest / '.appversion').write_text(version, encoding='utf-8')
    except Exception:                                       # noqa: BLE001
        pass
    print(f'完成，用时 {time.time() - t0:.1f}s')


# ---------------------------------------------------------------- 进程管理
_NO_WINDOW = 0x08000000          # CREATE_NO_WINDOW


def _backend_log():
    """后端的日志落点。

    后端是 windowed 的（没有控制台），用户看不到任何输出。若把 stdout/stderr
    丢给 DEVNULL，一旦起不来就完全无从查起 —— 这跟"静默"的目的（不打扰用户）
    并不冲突：不弹窗口，但把话说到文件里。每次启动覆盖，只保留本次记录，
    避免日志文件无限增长。
    """
    d = user_root() / 'logs'
    try:
        d.mkdir(parents=True, exist_ok=True)
        return open(d / 'backend.log', 'w', encoding='utf-8', errors='replace')
    except Exception:                                       # noqa: BLE001
        return subprocess.DEVNULL


def start_backend(root: Path):
    """静默拉起后端：无控制台窗口、无新窗口闪现。"""
    exe = root / BACKEND
    if not exe.is_file():
        print(f'警告：找不到后端 {exe}')
        return None
    creation = _NO_WINDOW if os.name == 'nt' else 0
    log = _backend_log()
    try:
        return subprocess.Popen(
            [str(exe), '--port', '50051', '--no-web'],
            cwd=str(root),
            creationflags=creation,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
        )
    except Exception as e:                                  # noqa: BLE001
        print(f'后端启动失败：{e}')
        return None


def kill_backend(proc, timeout: float = 5.0) -> None:
    """前端退出后务必带走后端，否则下次启动会因为 50051 被占而后端起不来。"""
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
    except Exception:                                       # noqa: BLE001
        try:
            proc.kill()
        except Exception:                                   # noqa: BLE001
            pass


def main() -> int:
    # 让 Python 自己的窗口尽量不出现：本启动器本身也用 windowed 方式打包
    version, blob = _self_payload()
    if blob is None:
        print('这个可执行文件没有内置运行资源，构建过程可能有误。')
        print('请把 packaging/build_single_exe.py 跑完再分发。')
        return 2

    ensure_extracted(version, blob)

    root = app_root()
    frontend = find_frontend(root)
    if frontend is None:
        print(f'错误：释放后的目录里找不到前端主程序 '
              f'({" / ".join(FRONTEND_CANDIDATES)})：{root}')
        return 3

    backend = start_backend(root)
    code = 0
    try:
        # 关键：告诉前端"后端我已经拉起来了，你别再拉一个"。
        # 前端 main.dart 的 _startBackend() 会按 exe 同目录找 backend.exe 并
        # 自行拉起 —— 两边都拉就会出现两个后端进程抢同一个 50051：
        # 一个抢到、另一个启动失败（或更糟，各跑各的导致状态不一致）。
        # 用户直接双击 frontend.exe 时没有这个变量，仍由前端自己拉起，兼容不变。
        env = dict(os.environ)
        env['XIAOLING_BACKEND_STARTED'] = '1'
        # 注意：不要在这里设 XIAOLING_HOME —— 后端自己会在 runtime_hook 里
        # 把数据根目录指向 <用户根>/runtime，与这里的 app/ 平级且互不影响。
        cp = subprocess.run([str(frontend)], cwd=str(root), env=env)
        code = cp.returncode
    except KeyboardInterrupt:
        code = 130
    finally:
        kill_backend(backend)
    return code


if __name__ == '__main__':
    sys.exit(main())
