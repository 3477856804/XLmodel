#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 XIAOLING · 一键打包器（Windows / macOS / Linux）

    python3 packaging/build.py                    # 当前平台，标准版（含全部资源 + Qt + GL）
    python3 packaging/build.py --lite             # 精简版（无 torch/Qt/全量模型，软件渲染）
    python3 packaging/build.py --lite --onefile   # 单文件精简版
    python3 packaging/build.py --zip              # 额外产出可分发的压缩包
    python3 packaging/build.py --deb --appimage   # Linux 额外产出 .deb / AppImage
    python3 packaging/build.py --dmg              # macOS 额外产出 .dmg
    python3 packaging/build.py --check            # 只做环境体检

产物：dist/xiaoling[.exe | /小凌.app] + dist/manifest.json（sha256 / 体积 / 说明）
注意：PyInstaller **不支持交叉编译**——Windows 包必须在 Windows 上打，macOS 包必须在 macOS 上打；
想在一条命令里出三平台产物，用 .github/workflows/release.yml 的矩阵构建。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
# 统一后端打包配置：入口 main.py，产出 onedir（dist/backend/backend[.exe]）。
# 历史上这里指向一个早已废弃的中文目录「打包/xiaoling.spec」，该目录与旧布局
# （xl.py + 顶层 core/ + 技能/数据/脚本/）都已不存在，会让打包直接找不到 spec。
SPEC = PROJECT / 'packaging' / 'backend.spec'
DIST = PROJECT / 'dist'
WORK = PROJECT / 'build' / 'pyinstaller'

# 全工程版本号唯一来源（与 backend/core/config.py、frontend/pubspec.yaml 对齐）。
# 发布期固定为 0.0.1，禁止在各脚本里再写死数字。
VERSION = '0.0.1'

# Windows CI 控制台默认 cp1252，打印中文会 UnicodeEncodeError —— 强制 UTF-8 输出。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def log(msg=''):
    print(f'[打包] {msg}', flush=True)


def sha256(path: Path, chunk=1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def dir_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())


def human(n: float) -> str:
    for u, d in (('GB', 1024 ** 3), ('MB', 1024 ** 2), ('KB', 1024)):
        if n >= d:
            return f'{n / d:.1f} {u}'
    return f'{int(n)} B'


def target_name() -> str:
    sysname = {'Windows': 'windows', 'Darwin': 'macos', 'Linux': 'linux'}.get(platform.system(), 'unknown')
    arch = {'x86_64': 'x64', 'amd64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64',
            'armv7l': 'armv7'}.get(platform.machine().lower(), platform.machine().lower())
    return f'{sysname}-{arch}'


def check_env(lite: bool) -> dict:
    info = {'platform': target_name(), 'python': sys.version.split()[0], 'issues': [], 'warn': []}
    try:
        import PyInstaller
        info['pyinstaller'] = getattr(PyInstaller, '__version__', '?')
    except Exception:                                            # noqa: BLE001
        info['issues'].append('缺少 PyInstaller：pip install pyinstaller')
    for mod, why, need in (('OpenGL', 'GPU 渲染（GLSL）', not lite),
                           ('numpy', '渲染/记忆/数学', True),
                           ('PIL', '贴图与形象处理', True),
                           ('grpcio', 'gRPC 通信（Flutter ↔ Python）', True),
                           ('torch', '本地模型推理 + 成长闭环', not lite),
                           ('transformers', '本地模型推理', not lite),
                           ('peft', 'LoRA 训练/合并（成长闭环）', not lite)):
        try:
            __import__(mod)
            info[f'dep_{mod}'] = 'ok'
        except Exception:                                        # noqa: BLE001
            info[f'dep_{mod}'] = 'missing'
            (info['issues'] if need else info['warn']).append(f'缺少 {mod}（{why}）')
    if not (PROJECT / 'resources' / 'models').exists():
        info['issues'].append('缺少 resources/models/ 目录（角色模型）')
    return info


def run_pyinstaller(lite: bool, onefile: bool, clean: bool, icon: str | None) -> Path:
    if clean:
        for d in (DIST, WORK):
            shutil.rmtree(d, ignore_errors=True)
        log('已清理 dist/ 与 build/pyinstaller/')
    env = dict(os.environ)
    env['XIAOLING_LITE'] = '1' if lite else '0'
    env['XIAOLING_ONEFILE'] = '1' if onefile else '0'
    if icon:
        env['XIAOLING_ICON'] = icon
    cmd = [sys.executable, '-m', 'PyInstaller', str(SPEC), '--noconfirm',
           '--distpath', str(DIST), '--workpath', str(WORK)]
    log('运行：' + ' '.join(cmd))
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(PROJECT), env=env)
    if proc.returncode != 0:
        raise SystemExit(f'PyInstaller 失败（退出码 {proc.returncode}）')
    log(f'PyInstaller 完成，用时 {time.time() - t0:.0f}s')
    # backend.spec 产出 onedir：dist/backend/backend[.exe]
    if platform.system() == 'Darwin' and (DIST / 'backend.app').exists():
        return DIST / 'backend.app'
    exe_name = 'backend.exe' if platform.system() == 'Windows' else 'backend'
    for cand in (DIST / 'backend' / exe_name, DIST / exe_name):
        if cand.exists():
            return cand
    return DIST / 'backend'


def bundle_root(app: Path) -> Path:
    """返回"整个程序包"的根：目录版是 dist/backend/，单文件版是那个可执行文件本身。"""
    if app.is_file() and app.parent.name in ('xiaoling', 'backend') and any(app.parent.iterdir()):
        return app.parent
    return app


def _copy_app(app: Path, dest_parent: Path) -> Path:
    root = bundle_root(app)
    dest_parent.mkdir(parents=True, exist_ok=True)
    target = dest_parent / root.name
    if root.is_file():
        shutil.copy2(root, target)
    else:
        shutil.copytree(root, target)
    return target


def make_zip(app: Path, tag='') -> Path:
    tmp = PROJECT / 'build' / f'xiaoling-{target_name()}{tag}'
    shutil.rmtree(tmp, ignore_errors=True)
    _copy_app(app, tmp)
    root = bundle_root(app)
    exe = ('xiaoling' + ('.exe' if platform.system() == 'Windows' else '')
           if root.is_file() else f"{root.name}/xiaoling" + ('.exe' if platform.system() == 'Windows' else ''))
    (tmp / 'README-运行说明.txt').write_text(
        '小凌 XIAOLING 便携版\n===================\n'
        f'1) 运行 {exe}\n'
        '2) 首次启动若缺基底模型会自动下载（进度显示在桌宠气泡与控制台）\n'
        '3) 数据目录：本目录下的 .star_core/（记忆 / LoRA 适配器 / 成长日志 / 配置都在这里）\n'
        '4) 想整体迁移：直接搬走整个文件夹（.star_core 跟着走）\n'
        '5) 无 GPU 时自动使用 Mesa 软件 GL；再不行退化到 numpy 光栅\n',
        encoding='utf-8')
    out = DIST / f'xiaoling-{target_name()}{tag}.zip'
    out.unlink(missing_ok=True)
    shutil.make_archive(str(out.with_suffix('')), 'zip', root_dir=str(tmp.parent), base_dir=tmp.name)
    log(f'便携包：{out}（{human(out.stat().st_size)}）')
    return out


def make_targz(app: Path, tag='') -> Path:
    tmp = PROJECT / 'build' / f'xiaoling-{target_name()}{tag}'
    shutil.rmtree(tmp, ignore_errors=True)
    _copy_app(app, tmp)
    out = DIST / f'xiaoling-{target_name()}{tag}.tar.gz'
    subprocess.run(['tar', '-czf', str(out), '-C', str(tmp.parent), tmp.name], check=True)
    log(f'Linux 便携包：{out}（{human(out.stat().st_size)}）')
    return out


def make_deb(app: Path) -> Path | None:
    if not shutil.which('dpkg-deb'):
        log('跳过 .deb：未安装 dpkg-deb')
        return None
    root = PROJECT / 'build' / 'deb'
    shutil.rmtree(root, ignore_errors=True)
    (root / 'DEBIAN').mkdir(parents=True)
    os.chmod(root, 0o755)
    os.chmod(root / 'DEBIAN', 0o755)
    _copy_app(app, root / 'opt')
    arch = 'arm64' if platform.machine() in ('aarch64', 'arm64') else 'amd64'
    (root / 'DEBIAN/control').write_text(
        f'Package: xiaoling\nVersion: {VERSION}\nSection: utils\nPriority: optional\n'
        f'Architecture: {arch}\nMaintainer: XIAOLING <xiaoling@local>\n'
        'Depends: libosmesa6 | libgl1, libgl1-mesa-dri | libglx-mesa0\n'
        'Description: 小凌 XIAOLING - 3D digital companion (pure Python)\n',
        encoding='utf-8')
    (root / 'usr/share/applications').mkdir(parents=True, exist_ok=True)
    desktop = PROJECT / 'packaging/linux/xiaoling.desktop'
    if desktop.exists():
        shutil.copy(desktop, root / 'usr/share/applications/xiaoling.desktop')
    (root / 'usr/bin').mkdir(parents=True, exist_ok=True)
    launcher = root / 'usr/bin/xiaoling'
    launcher.write_text(f'#!/bin/sh\nexec /opt/{app.name}/{app.name} "$@"\n', encoding='utf-8')
    launcher.chmod(0o755)
    out = DIST / f'xiaoling_{VERSION}_{arch}.deb'
    subprocess.run(['dpkg-deb', '--build', str(root), str(out)], check=True)
    log(f'Debian 包：{out}（{human(out.stat().st_size)}）')
    return out


def make_appimage(app: Path) -> Path | None:
    tool = shutil.which('appimagetool') or shutil.which('appimagetool-x86_64.AppImage')
    if not tool:
        log('跳过 AppImage：未找到 appimagetool（可从 AppImageKit 下载）')
        return None
    root = PROJECT / 'build' / 'AppDir'
    shutil.rmtree(root, ignore_errors=True)
    _copy_app(app, root / 'usr/bin')
    for f in ('AppRun', 'xiaoling.desktop', 'xiaoling.png'):
        src = PROJECT / 'packaging/linux' / f
        if src.exists():
            shutil.copy(src, root / f)
    (root / 'AppRun').chmod(0o755)
    out = DIST / f'xiaoling-{target_name()}.AppImage'
    subprocess.run([tool, str(root), str(out)], check=True)
    out.chmod(0o755)
    log(f'AppImage：{out}（{human(out.stat().st_size)}）')
    return out


def make_dmg(app: Path) -> Path | None:
    if not shutil.which('hdiutil'):
        log('跳过 dmg：仅 macOS 支持')
        return None
    out = DIST / f'xiaoling-{VERSION}.dmg'
    subprocess.run(['hdiutil', 'create', '-volname', '小凌 XIAOLING', '-srcfolder', str(app),
                    '-ov', '-format', 'UDZO', str(out)], check=True)
    log(f'DMG：{out}（{human(out.stat().st_size)}）')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='小凌一键打包器')
    ap.add_argument('--lite', action='store_true', help='精简版（不带 torch/Qt/全量模型）')
    ap.add_argument('--onefile', action='store_true', help='单文件模式（建议配合 --lite）')
    ap.add_argument('--clean', action='store_true', help='打包前清理 dist/ 与构建缓存')
    ap.add_argument('--zip', action='store_true', help='额外产出便携压缩包')
    ap.add_argument('--appimage', action='store_true', help='Linux 额外产出 AppImage')
    ap.add_argument('--deb', action='store_true', help='Linux 额外产出 .deb')
    ap.add_argument('--dmg', action='store_true', help='macOS 额外产出 .dmg')
    ap.add_argument('--icon', default=None, help='图标（.ico/.icns/.png）')
    ap.add_argument('--check', action='store_true', help='只做环境体检')
    a = ap.parse_args(argv)

    log(f"目标平台：{target_name()}｜Python {sys.version.split()[0]}"
        f"｜模式：{'精简' if a.lite else '标准'}{'（单文件）' if a.onefile else '（目录）'}")
    info = check_env(a.lite)
    for k in ('pyinstaller', 'dep_OpenGL', 'dep_numpy', 'dep_PIL', 'dep_grpcio', 'dep_torch',
              'dep_transformers', 'dep_peft'):
        if k in info:
            log(f'  {k:18s} {info[k]}')
    for w in info['warn']:
        log(f'  [警告] {w}')
    for i in info['issues']:
        log(f'  x {i}')
    if a.check:
        print(json.dumps(info, ensure_ascii=False, indent=1))
        return 0 if not info['issues'] else 1
    if info['issues']:
        log('环境不满足打包条件（可用 --lite 跳过 Qt/torch 依赖）')
        return 1

    app = run_pyinstaller(a.lite, a.onefile, a.clean, a.icon)
    tag = '-lite' if a.lite else ''
    artifacts = [str(app)]
    want_zip = a.zip or platform.system() == 'Windows'
    if want_zip:
        artifacts.append(str(make_zip(app, tag)))
    if platform.system() == 'Linux' and not a.onefile:
        artifacts.append(str(make_targz(app, tag)))
        if a.deb:
            p = make_deb(app)
            if p:
                artifacts.append(str(p))
        if a.appimage:
            p = make_appimage(app)
            if p:
                artifacts.append(str(p))
    if platform.system() == 'Darwin' and a.dmg and not a.onefile:
        p = make_dmg(app)
        if p:
            artifacts.append(str(p))

    manifest = {'name': '小凌 XIAOLING', 'version': VERSION, 'target': target_name(),
                'mode': 'lite' if a.lite else 'full', 'onefile': a.onefile,
                'built_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'python': sys.version.split()[0],
                'artifacts': []}
    for p in artifacts:
        pp = Path(p)
        if pp.exists():
            manifest['artifacts'].append({'path': str(pp.relative_to(PROJECT)),
                                          'size': human(dir_size(pp)), 'bytes': dir_size(pp),
                                          'sha256': sha256(pp) if pp.is_file() else ''})
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                        encoding='utf-8')
    log('完成！产物：')
    for art in manifest['artifacts']:
        log(f"  · {art['path']}  {art['size']}")
    log('清单：dist/manifest.json')
    log('提示：数据目录（记忆/适配器/成长日志/配置）在可执行文件同级的 .star_core/，随文件夹迁移。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
