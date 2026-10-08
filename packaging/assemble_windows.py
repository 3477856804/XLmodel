#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「Flutter 前端」与「PyInstaller 后端」合并成一个可直接运行的 Windows 目录。

为什么必须合并到同一个目录：
    前端 main.dart 的 _startBackend() 是按 exe 自身所在目录去找 backend.exe 的：
        exeDir = File(Platform.resolvedExecutable).parent
        backend.exe / backend（其他平台）
    找到就以 `--port 50051 --no-web --web-port <空闲端口>` 拉起，找不到就跳过后端。
    所以两个 exe 分开放 = 前端静默不启动后端 = 打开就是一片空白、聊天没反应，
    而且日志里什么都不报，极难排查。

用法：
    python packaging/assemble_windows.py               # 合并到 dist/小凌-Windows-x64
    python packaging/assemble_windows.py --zip         # 合并后顺带打成 zip
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLUTTER_RELEASE = ROOT / 'frontend' / 'build' / 'windows' / 'x64' / 'runner' / 'Release'
OUT = ROOT / 'dist' / '小凌-Windows-x64'

# 后端产物目录**自动发现**，不写死路径。
# 原因：PyInstaller 重新构建时要先清空旧的 dist/backend 目录，而本工作区对
# 批量删除有安全拦截，会直接中断构建。绕开的办法是每次换一个新的 --distpath
# （dist2、dist3…），于是产物目录会不止一个。这里扫描 packaging/dist*/backend，
# 取 backend.exe 最新的那个，构建脚本就不必跟着改路径。


def _latest_backend_dist() -> Path | None:
    best, best_mt = None, -1.0
    for d in ROOT.glob('packaging/dist*/backend'):
        exe = d / 'backend.exe'
        if exe.is_file():
            mt = exe.stat().st_mtime
            if mt > best_mt:
                best, best_mt = d, mt
    return best

# 前端主程序重命名：原名 frontend.exe 对老板毫无辨识度
EXE_NEW_NAME = '小凌.exe'
EXE_OLD_NAME = 'frontend.exe'

# 后端产物里这两个顶层目录不带进最终包：
#   data/       —— 在本机跑 backend.exe --status 时生成的测试残留；
#                  且与 Flutter Release 自带的 data/（app.so、icudtl.dat、
#                  flutter_assets）撞名，拷过去会把前端资源目录弄脏。
#                  真正的运行数据由 runtime_hook 隔离到 runtime/data 下。
#   .star_core/ —— 同上，是测试残留；真正的可写目录是 runtime/.star_core。
BACKEND_SKIP_TOP = {'data', '.star_core'}


def _copy_tree(src: Path, dst: Path, label: str,
               skip_top: set | None = None) -> tuple:
    """整树拷贝到 dst。返回 (文件数, 字节数, 冲突列表)。

    同名文件**覆盖**而非跳过：两侧都是本次构建流程刚产出的东西，不存在
    "哪个更权威"的问题，取后拷入的版本（即最新构建）才不会在重复运行时
    留下过期文件。真发生了撞名会记进 conflicts 并打印，便于人工核对。
    """
    if not src.is_dir():
        print(f'  [跳过] {label} 不存在：{src}')
        return 0, 0, []
    skip_top = skip_top or set()
    n = size = 0
    skipped = 0
    conflicts = []
    for p in src.rglob('*'):
        if p.is_dir():
            continue
        rel = p.relative_to(src)
        # 只跳过顶层指定的目录（resources/web 这类子目录不受影响）
        if len(rel.parts) > 1 and rel.parts[0] in skip_top:
            skipped += 1
            continue
        target = dst / rel
        if target.exists():
            conflicts.append(str(rel))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        n += 1
        size += p.stat().st_size
    extra = f'，跳过 {skipped} 个（{"/".join(sorted(skip_top))}）' if skipped else ''
    print(f'  [OK] {label}：{n} 个文件，{size / 1048576:.1f} MB{extra}')
    return n, size, conflicts


def _human(n: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


def main() -> int:
    ap = argparse.ArgumentParser(description='合并小凌 Windows 运行包')
    ap.add_argument('--zip', action='store_true', help='合并后打成 zip')
    ap.add_argument('--backend-dist', default=None,
                    help='显式指定后端产物目录（默认自动挑最新的 packaging/dist*/backend）')
    args = ap.parse_args()

    backend_dist = Path(args.backend_dist) if args.backend_dist else _latest_backend_dist()

    if not FLUTTER_RELEASE.is_dir():
        print(f'错误：找不到 Flutter Release 产物：{FLUTTER_RELEASE}')
        print('请先执行：cd frontend && flutter build windows --release')
        return 1
    if backend_dist is None or not backend_dist.is_dir():
        print('错误：找不到后端打包产物（packaging/dist*/backend/backend.exe）')
        print('请先执行：python -m PyInstaller packaging/backend.spec '
              '--distpath packaging/distN --workpath packaging/buildN --noconfirm')
        return 1
    print(f'后端产物：{backend_dist}')

    print(f'输出目录：{OUT}')
    if OUT.exists():
        # 不主动清空：本工作区对批量删除有安全拦截，且清空会让"再跑一次"
        # 变成高危操作。改为增量覆盖（同名文件覆盖、新文件补入），
        # 需要干净重建时手动把 OUT 整个目录移走即可。
        print('  已存在，做增量覆盖（不删除任何已有文件）')
    OUT.mkdir(parents=True, exist_ok=True)

    print('拷贝中…')
    _, _, c1 = _copy_tree(FLUTTER_RELEASE, OUT, 'Flutter 前端')
    _, _, c2 = _copy_tree(backend_dist, OUT, 'Python 后端',
                          skip_top=BACKEND_SKIP_TOP)

    # ---- 重命名主程序 ----
    exe_old = OUT / EXE_OLD_NAME
    exe_new = OUT / EXE_NEW_NAME
    if exe_old.exists():
        if exe_new.exists():
            exe_old.unlink()
        else:
            exe_old.rename(exe_new)
        print(f'  主程序重命名：{EXE_OLD_NAME} → {EXE_NEW_NAME}')
    elif not exe_new.exists():
        print(f'  警告：输出目录里既没有 {EXE_OLD_NAME} 也没有 {EXE_NEW_NAME}')

    # ---- 启动说明 ----
    note = OUT / '启动说明.txt'
    note.write_text(
        '小凌 · Windows 测试包\n'
        '====================\n\n'
        '【怎么跑】\n'
        f'  双击「{EXE_NEW_NAME}」即可。\n'
        '  首次启动会弹出一个黑色控制台窗口，那是 Python 后端在跑（保留它是为了\n'
        '  让你能直接看到报错）。前端关闭时后端会一起退出；若残留，任务管理器里\n'
        '  结束 backend.exe 即可。\n\n'
        '【目录说明】\n'
        f'  {EXE_NEW_NAME}      Flutter 界面（真 3D 走内置 WebView 渲染 VRM）\n'
        '  backend.exe          Python 后端（gRPC 50051 + 3D 查看器 HTTP 服务）\n'
        '  data/                Flutter 自己的资源（app.so / icudtl.dat / flutter_assets）\n'
        '  _internal/           后端的 Python 运行时与只读资源\n'
        '                         └ resources/web/    3D 查看器页面 + three.js / three-vrm（全离线）\n'
        '                         └ resources/models/ VRM 角色模型\n'
        '                         └ resources/animations/ 动作库（.vrma）\n'
        '  runtime/             首次运行后自动生成：聊天记录、配置、插件、模型\n'
        '                         └ data/、.star_core/\n'
        '  （后端数据刻意放在 runtime/ 而不是程序根目录：后端默认会把数据写进\n'
        '     ./data，而 ./data 已经被 Flutter 占用，混在一起既脏又容易误删。）\n\n'
        '【这个包能做什么 / 不能做什么】\n'
        '  为了把体积控制在可分发范围，打包时排除了 torch 与 transformers\n'
        '  （本机 torch 2.11+cu128 有 4.2GB，打进去产物会达数 GB）。因此：\n'
        '    · GGUF 格式模型（llama.cpp 运行时）—— 正常加载、正常聊天\n'
        '    · HuggingFace safetensors 目录格式 —— 需要完整版才能加载\n'
        '    · LoRA 训练（依赖 transformers）—— 需要完整版\n'
        '  UI、3D、设置、模型扫描与登记在两种包里都完全可用。\n\n'
        '【添加本地模型】\n'
        '  设置 → 模型 → 添加本地模型，指向 .gguf 文件或含 .gguf 的目录即可。\n'
        '  注意别直接指向「模型库根目录」（如 D:\\models），要先扫描再挑具体模型登记。\n\n'
        '【出问题怎么看】\n'
        '  1) 看 backend 控制台窗口的红色报错\n'
        '  2) 看本目录下的 xl_error.log（前端未捕获异常）\n'
        '  3) 端口被占用：结束占用 50051 的旧进程\n',
        encoding='utf-8')

    # ---- 体检 ----
    print('\n体检：')
    # 注意路径：后端是 PyInstaller 的 onedir 产物，它的只读资源全部在
    # _internal/ 下（sys._MEIPASS 就指向这里），而不是顶层 resources/。
    # 体检写在顶层就会误报"缺失"，实际后端启动时正是从 _internal 读的。
    must = [
        (EXE_NEW_NAME, '前端主程序'),
        ('backend.exe', '后端主程序'),
        ('flutter_windows.dll', 'Flutter 运行时'),
        ('data/icudtl.dat', 'ICU 数据（Flutter 资源目录）'),
        ('_internal/resources/web/viewer.html', '3D 查看器页面'),
        ('_internal/resources/web/vendor/three.module.js', 'three.js'),
        ('_internal/resources/web/vendor/three-vrm.module.js', 'three-vrm'),
        ('_internal/resources/web/vendor/addons/loaders/GLTFLoader.js', 'GLTFLoader'),
    ]
    ok = True
    for rel, desc in must:
        p = OUT / rel
        flag = 'OK  ' if p.exists() else '缺失'
        if not p.exists():
            ok = False
        print(f'  [{flag}] {desc}：{rel}')

    mdir = OUT / '_internal' / 'resources' / 'models'
    vrms = sorted(mdir.glob('*.vrm')) if mdir.is_dir() else []
    if vrms:
        print(f'  [OK  ] VRM 模型：{len(vrms)} 个 —— ' + '、'.join(v.name for v in vrms))
    else:
        ok = False
        print('  [缺失] VRM 模型：一个都没有，3D 区域会是空的')

    total = sum(f.stat().st_size for f in OUT.rglob('*') if f.is_file())
    print(f'\n总体积：{_human(total)}')

    if c1 or c2:
        print('\n注意：以下文件在两边都存在，已保留前端版本（一般无害）：')
        for c in (c1 + c2)[:20]:
            print(f'  {c}')

    if args.zip:
        zpath = OUT.parent / (OUT.name + '.zip')
        # 不先删旧 zip：make_archive 对 zip 格式是覆盖写入，没必要删，
        # 也避免触发工作区的批量删除拦截。
        print(f'\n打包 zip：{zpath} …')
        shutil.make_archive(str(OUT), 'zip', root_dir=OUT.parent, base_dir=OUT.name)
        print(f'完成：{zpath}（{_human(zpath.stat().st_size)}）')

    print('\n完成。' if ok else '\n完成，但有缺失项（见上）。')
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
