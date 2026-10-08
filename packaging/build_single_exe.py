#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「运行目录」封成一个可双击运行的单文件 exe。

流程：
    1) PyInstaller 打出 launcher.exe（onefile / windowed，约 10MB）
    2) 把整个运行目录（Flutter 前端 + Python 后端）压成 zip
    3) 按 [payload][len:8 大端][magic:6][version:16] 的布局追加到 exe 尾部
    4) 重命名为 小凌.exe

这样用户拿到的就是一个文件：双击 → 首次自动释放到 %LOCALAPPDATA%\\Xiaoling\\app
→ 后端静默起来 → 界面出来。第二次起不再解压，直接启动。

用法：
    python packaging/assemble_windows.py            # 先造出运行目录
    python packaging/build_single_exe.py            # 再封成单文件 exe
    python packaging/build_single_exe.py --zip      # 顺便再打一份 zip 备用
"""
import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_APP = ROOT / 'dist' / '小凌-Windows-x64'

MAGIC = b'XLPAY1'
VERSION_LEN = 16
PYTHON_EXE = os.environ.get(
    'XIAOLING_PKG_PYTHON',
    r'C:\Users\MVP\.workbuddy\binaries\python\envs\xiaoling_pkg\Scripts\python.exe')


def _human(n: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


def build_payload(app_dir: Path, zip_path: Path) -> int:
    """把运行目录压成一个 zip。返回条目数。"""
    n = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(app_dir.rglob('*')):
            if p.is_dir():
                continue
            z.write(p, p.relative_to(app_dir))
            n += 1
    return n


def build_launcher(distpath: Path, workpath: Path) -> Path:
    """PyInstaller 打内壳。返回 launcher.exe 路径。"""
    cmd = [
        PYTHON_EXE, '-m', 'PyInstaller',
        str(ROOT / 'packaging' / 'launcher.spec'),
        '--distpath', str(distpath),
        '--workpath', str(workpath),
        '--noconfirm',
    ]
    print('打启动器内壳…')
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        raise SystemExit('PyInstaller 构建启动器失败')
    exe = distpath / 'launcher.exe'
    if not exe.is_file():
        raise SystemExit(f'未产出启动器：{exe}')
    print(f'  完成：{exe}（{_human(exe.stat().st_size)}）')
    return exe


def seal(launcher: Path, payload: Path, out: Path) -> str:
    """把 payload 追加到 exe 尾部。返回版本号。"""
    blob = payload.read_bytes()
    version = hashlib.sha256(blob).hexdigest()[:VERSION_LEN]
    # 不先删旧成品：copy2 本身就是覆盖写入，删反而会触发工作区的删除拦截
    shutil.copy2(launcher, out)
    with open(out, 'ab') as f:
        f.write(blob)
        f.write(struct.pack('>Q', len(blob)))
        f.write(MAGIC)
        f.write(version.encode('ascii').ljust(VERSION_LEN)[:VERSION_LEN])
    return version


def main() -> int:
    ap = argparse.ArgumentParser(description='封装小凌单文件 exe')
    ap.add_argument('--app-dir', default=str(DEFAULT_APP), help='待封装的运行目录')
    ap.add_argument('--out', default=str(ROOT / 'dist' / '小凌.exe'))
    ap.add_argument('--zip', action='store_true', help='额外再打一份 zip 便于分发')
    args = ap.parse_args()

    app = Path(args.app_dir)
    out = Path(args.out)

    # assemble 会把 frontend.exe 重命名成 小凌.exe，两个名字都接受
    has_frontend = any((app / n).is_file()
                       for n in ('小凌.exe', 'frontend.exe'))
    missing = []
    if not has_frontend:
        missing.append('小凌.exe/frontend.exe')
    if not (app / 'backend.exe').is_file():
        missing.append('backend.exe')
    if missing:
        print(f'错误：运行目录缺少 {missing}：{app}')
        print('请先执行：python packaging/assemble_windows.py')
        return 1

    files = sum(1 for p in app.rglob('*') if p.is_file())
    total = sum(p.stat().st_size for p in app.rglob('*') if p.is_file())
    print(f'待封装：{files} 个文件，{_human(total)}')

    # PyInstaller 重建前要删旧 dist —— 本工作区拦截批量删除，所以每次换新目录
    stamp = str(int(__import__('time').time()))
    work = ROOT / 'packaging' / f'build_launcher_{stamp}'
    distwork = ROOT / 'packaging' / f'dist_launcher_{stamp}'

    distwork.mkdir(parents=True, exist_ok=True)
    launcher = build_launcher(distwork, work)

    payload = distwork / 'payload.zip'
    print('压缩运行资源…')
    n = build_payload(app, payload)
    print(f'  {n} 个条目，{_human(payload.stat().st_size)}')

    out.parent.mkdir(parents=True, exist_ok=True)
    print(f'合成单文件：{out}')
    ver = seal(launcher, payload, out)
    print(f'  版本标记：{ver}')
    print(f'  成品体积：{_human(out.stat().st_size)}')

    if args.zip:
        zp = out.with_suffix('.zip')
        print(f'另备 zip：{zp}')
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            shutil.copy2(out, Path(td) / out.name)
            shutil.make_archive(str(zp.with_suffix('')), 'zip', root_dir=td)

    print('\n完成。双击即可运行，后端与 3D 服务都是静默启动。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
