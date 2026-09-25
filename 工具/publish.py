#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 发布工具（一条命令完成：同步源码到 Gitee / 建 Release 挂 APK / 生成官网 / 部署 Cloudflare Pages）

Token 只从环境变量读，绝不写进仓库：
    export GITEE_TOKEN=xxx          # Gitee 私人令牌
    export CF_API_TOKEN=xxx         # Cloudflare API Token（Pages:Edit 权限）
    export CF_ACCOUNT_ID=xxx        # Cloudflare Account ID

用法：
    python3 工具/publish.py all                    # 全流程
    python3 工具/publish.py gitee [-m "提交说明"]   # 只同步源码到 Gitee
    python3 工具/publish.py release [--tag v0.0.2] # 只建 Release 并上传 APK
    python3 工具/publish.py site                   # 只生成官网
    python3 工具/publish.py pages [--project xiaoling]  # 只部署官网
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_SLUG = 'COSMOnb666/XLmodel'
REPO_URL = f'https://gitee.com/{REPO_SLUG}'
PAGES_PROJECT = 'xiaoling'
CF_API = 'https://api.cloudflare.com/client/v4'

# 不同步到仓库的内容（授权/体积原因）
SYNC_EXCLUDE_DIRS = {'.git', '__pycache__', '.buildozer', '.gradle', 'dist', 'build',
                     'android/bin', 'android/native/app/build', 'android/native/.gradle',
                     'android/native/app/src/main/python', 'android/native/app/src/main/assets'}
SYNC_EXCLUDE_FILES = {'xiaoling-1.0.0-android-arm64.apk'}
# 明确排除：第三方 VRM 模型（授权多为"禁止再分发"）
SYNC_EXCLUDE_GLOBS = ('角色模型/*.vrm', '*.vrm', '*.apk')


def log(msg=''):
    print(f'[发布] {msg}', flush=True)


def run(cmd, cwd=None, env=None, check=True, quiet=False):
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env,
                       capture_output=quiet, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f'命令失败：{" ".join(map(str, cmd))}\n{(r.stderr or "")[-800:]}')
    return r


def http(method: str, url: str, data=None, headers=None, timeout=120):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    try:
        return json.loads(body.decode('utf-8', 'ignore'))
    except json.JSONDecodeError:
        return {'raw': body[:400].decode('utf-8', 'ignore')}


# --------------------------------------------------------------------------- Gitee
def gitee_sync(message: str, workdir: Path | None = None, push: bool = True):
    token = os.environ.get('GITEE_TOKEN', '')
    if not token:
        raise SystemExit('缺少 GITEE_TOKEN 环境变量')
    workdir = workdir or Path(tempfile.gettempdir()) / 'gitee-repo'
    log(f'克隆/更新 {REPO_SLUG} → {workdir}')
    if not (workdir / '.git').exists():
        ok = False
        for attempt in range(3):
            r = subprocess.run(['git', 'clone', '--depth', '1', '--single-branch',
                                f'https://COSMOnb666:{token}@gitee.com/{REPO_SLUG}.git',
                                str(workdir)], capture_output=True, text=True)
            if r.returncode == 0:
                ok = True
                break
            log(f'  克隆失败（第 {attempt + 1} 次）：{(r.stderr or "").strip().splitlines()[-1:]}')
            time.sleep(5)
        if not ok:
            raise SystemExit('Gitee 克隆失败（网络或令牌问题）')
    # 拉最新
    run(['git', 'remote', 'set-url', 'origin',
         f'https://COSMOnb666:{token}@gitee.com/{REPO_SLUG}.git'], cwd=workdir, quiet=True)
    run(['git', 'pull', '--ff-only'], cwd=workdir, check=False, quiet=True)

    # 同步文件（保留 .git 与仓库里已有的 .star_core 大文件）
    log('同步项目文件…')
    copied = removed = 0
    for src in ROOT.rglob('*'):
        rel = src.relative_to(ROOT)
        parts = set(rel.parts)
        if parts & SYNC_EXCLUDE_DIRS:
            continue
        if src.name in SYNC_EXCLUDE_FILES:
            continue
        if any(rel.match(g) for g in SYNC_EXCLUDE_GLOBS):
            continue
        dst = workdir / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            shutil.copy2(src, dst)
            copied += 1
    log(f'  复制/更新 {copied} 个文件')
    # 删除仓库里已经不存在于项目的文件（.star_core、.git 除外）
    keep_top = {'.star_core', '.git', '角色模型'}
    for p in sorted(workdir.rglob('*'), reverse=True):
        rel = p.relative_to(workdir)
        if set(rel.parts) & keep_top or set(rel.parts) & SYNC_EXCLUDE_DIRS:
            continue
        if p.is_file() and not (ROOT / rel).exists():
            p.unlink()
            removed += 1
    log(f'  清理 {removed} 个已废弃文件')

    run(['git', 'add', '-A'], cwd=workdir, quiet=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=workdir).returncode == 0:
        log('没有需要提交的改动')
    else:
        run(['git', '-c', 'user.name=xiaoling', '-c', 'user.email=xiaoling@local',
             'commit', '-m', message], cwd=workdir, quiet=True)
        log(f'已提交：{message}')
    if push:
        log('推送到 Gitee…')
        r = subprocess.run(['git', 'push', 'origin', 'HEAD:master'], cwd=workdir,
                           capture_output=True, text=True)
        if r.returncode != 0:
            r = subprocess.run(['git', 'push', 'origin', 'HEAD:main'], cwd=workdir,
                               capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit('推送失败：' + (r.stderr or '')[-500:])
        log('推送完成 OK')
    return workdir


def gitee_release(tag: str, apk: Path, title: str, body: str) -> dict:
    token = os.environ['GITEE_TOKEN']
    base = f'https://gitee.com/api/v5/repos/{REPO_SLUG}'
    exists = http('GET', f'{base}/releases/tags/{tag}?access_token={token}')
    if isinstance(exists, dict) and exists.get('id'):
        rel = exists
        log(f'Release {tag} 已存在（id={rel["id"]}）')
    else:
        rel = http('POST', f'{base}/releases',
                   data=urllib.parse.urlencode({'access_token': token, 'tag_name': tag,
                                                'name': title, 'body': body,
                                                'target_commitish': 'master'}).encode(),
                   headers={'Content-Type': 'application/x-www-form-urlencoded'})
        log(f'Release 创建：{tag}（id={rel.get("id")}）')
    if not rel.get('id'):
        raise SystemExit(f'Release 创建失败：{rel}')
    # 上传 APK 附件（先删同名旧附件）
    for a in rel.get('assets', []) or []:
        if a.get('name') == apk.name:
            http('DELETE', f'{base}/releases/{rel["id"]}/attach_files/'
                 f'{a.get("id") or a.get("id")}?access_token={token}')
    boundary = '----xiaoling' + uuid.uuid4().hex
    data = apk.read_bytes()
    body_parts = []
    body_parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="access_token"\r\n\r\n{token}\r\n'.encode())
    body_parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{apk.name}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'.encode() + data + b'\r\n')
    body_parts.append(f'--{boundary}--\r\n'.encode())
    payload = b''.join(body_parts)
    res = http('POST', f'{base}/releases/{rel["id"]}/attach_files', data=payload,
               headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, timeout=600)
    url = ''
    if isinstance(res, dict):
        url = res.get('browser_download_url') or res.get('download_url') or ''
    if not url:
        url = f'{REPO_URL}/releases/download/{tag}/{apk.name}'
    log(f'APK 已上传：{url}')
    return {'tag': tag, 'release_id': rel.get('id'), 'apk_url': url}


# --------------------------------------------------------------------------- 官网
def build_site(downloads: dict | None = None) -> Path:
    sys.path.insert(0, str(ROOT / 'website'))
    import importlib
    mod = importlib.import_module('build')
    importlib.reload(mod)
    return mod.build(downloads)


def _pages_hash(data: bytes, algo: str = 'md5') -> str:
    """Cloudflare Pages 直接上传的资产哈希：32 位十六进制（与 wrangler 一致）。
    wrangler 用的是 md5；若某天官方改了算法，可用 XIAOLING_PAGES_HASH=sha256 切换。"""
    algo = os.environ.get('XIAOLING_PAGES_HASH', algo).lower()
    if algo == 'sha256':
        return hashlib.sha256(data).hexdigest()[:32]
    return hashlib.md5(data).hexdigest()


def pages_deploy(dist: Path, project: str = PAGES_PROJECT) -> dict:
    token = os.environ.get('CF_API_TOKEN', '')
    account = os.environ.get('CF_ACCOUNT_ID', '')
    if not token or not account:
        raise SystemExit('缺少 CF_API_TOKEN / CF_ACCOUNT_ID 环境变量')
    files, manifest = {}, {}
    for p in sorted(dist.rglob('*')):
        if not p.is_file():
            continue
        rel = '/' + str(p.relative_to(dist)).replace(os.sep, '/')
        data = p.read_bytes()
        if len(data) > 25 * 1024 * 1024:
            log(f'  [警告] 跳过超 25MB 的文件（Cloudflare Pages 限制）：{rel}')
            continue
        h = _pages_hash(data)
        files[h] = data
        manifest[rel] = h
    boundary = '----xiaolingdeploy' + uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="branch"\r\n\r\nmain\r\n'.encode(),
        f'--{boundary}\r\nContent-Disposition: form-data; name="manifest"\r\n'
        f'Content-Type: application/json\r\n\r\n{json.dumps(manifest)}\r\n'.encode()]
    for h, data in files.items():
        # 关键：文件分片必须带 filename（Cloudflare 按 name/filename 建立与 manifest 的映射）
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{h}"; '
                     f'filename="{h}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                     + data + b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    payload = b''.join(parts)
    url = f'{CF_API}/accounts/{account}/pages/projects/{project}/deployments'
    log(f'上传站点（{len(files)} 个文件 / {len(payload)/1024:.0f} KB）→ Pages 项目 {project}')
    res = http('POST', url, data=payload,
               headers={'Authorization': f'Bearer {token}',
                        'Content-Type': f'multipart/form-data; boundary={boundary}'}, timeout=600)
    if not res.get('success'):
        raise SystemExit(f'部署失败：{res.get("errors")}')
    dep = res['result']
    info = {'id': dep.get('id'), 'url': dep.get('url'),
            'alias': (dep.get('aliases') or [None])[0], 'created': dep.get('created_on')}
    log(f"部署完成 OK {info.get('url')}  （别名：{info.get('alias')}）")
    return info


# --------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description='小凌发布工具')
    ap.add_argument('cmd', choices=['all', 'gitee', 'release', 'site', 'pages'])
    ap.add_argument('-m', '--message', default=None, help='Gitee 提交说明')
    ap.add_argument('--tag', default='v0.0.2')
    ap.add_argument('--project', default=PAGES_PROJECT)
    ap.add_argument('--apk', default=str(ROOT / 'android/bin/xiaoling-0.0.2-android-arm64-debug.apk'))
    a = ap.parse_args(argv)
    state_file = ROOT / 'website' / 'downloads.json'

    if a.cmd in ('all', 'gitee'):
        msg = a.message or f'小凌 v0.0.2：3D 数字人 + 成长闭环 + 全平台打包（纯 Python）'
        gitee_sync(msg)
    if a.cmd in ('all', 'release'):
        apk = Path(a.apk)
        if not apk.exists():
            log(f'找不到 APK：{apk}（跳过 Release）')
        else:
            body = ('小凌 XIAOLING v0.0.2\n\n'
                    '- 3D 数字人（白裙 / 白丝 / 小凌脸），46 个 VRMA 动作\n'
                    '- 成长闭环：适配器 ≥ 基底 → merge_and_unload → 自研模型 → 基底退役 → 适配器晋升\n'
                    '- 全平台：Android APK / Windows / macOS / Linux / Termux\n'
                    '- 统一 Python：业务逻辑与 3D 渲染层全部 Python（GLSL 内联）\n')
            info = gitee_release(a.tag, apk, f'小凌 XIAOLING {a.tag}', body)
            dl = json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {}
            dl[apk.name] = info['apk_url']
            state_file.write_text(json.dumps(dl, ensure_ascii=False, indent=1), encoding='utf-8')
    if a.cmd in ('all', 'site'):
        build_site()
    if a.cmd in ('all', 'pages'):
        pages_deploy(ROOT / 'website' / 'dist', a.project)
    return 0


if __name__ == '__main__':
    sys.exit(main())
