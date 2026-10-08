#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 一次把源码推到 Gitee 与 GitHub。

Token 只从环境变量读，绝不写进仓库：

    export GITEE_TOKEN=xxxxx     # https://gitee.com/profile/personal_access_tokens
    export GITHUB_TOKEN=xxxxx    # https://github.com/settings/tokens （勾 repo）

用法：
    python tools/push_repos.py            # 建仓库（若不存在）+ 推送
    python tools/push_repos.py --dry-run  # 只看会做什么，不真的推

仓库不存在会自动创建（公开）。想建私有库加 --private。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANCH = 'main'

GITHUB_OWNER = '3477856804'          # XLmodel-release 就在该账号下
GITHUB_REPO = 'XLmodel'
GITEE_OWNER = 'COSMOnb666'           # 与 scripts/publish.py 的 REPO_SLUG 保持一致
GITEE_REPO = 'XLmodel'


def log(m=''):
    print(m, flush=True)


def api(method: str, url: str, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw.decode('utf-8', 'ignore'))
            except json.JSONDecodeError:
                return r.status, {'raw': raw[:400].decode('utf-8', 'ignore')}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode('utf-8', 'ignore'))
        except Exception:
            return e.code, {'raw': raw[:300].decode('utf-8', 'ignore')}
    except Exception as e:  # noqa: BLE001
        return 0, {'error': f'{type(e).__name__}: {e}'}


def git(args, check=True, quiet=True):
    r = subprocess.run(['git', *args], cwd=str(ROOT),
                       capture_output=quiet, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f'git {" ".join(args)} 失败：\n{(r.stderr or "")[-800:]}')
    return r


# --------------------------------------------------------------------------- 建库
def ensure_github(token: str, private: bool, dry: bool) -> str:
    url = f'https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}'
    code, info = api('GET', url, headers={'Authorization': f'Bearer {token}',
                                          'Accept': 'application/vnd+json'})
    if code == 200:
        log(f'  GitHub 仓库已存在：{info.get("html_url")}')
        return info.get('clone_url') or f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git'
    if code != 404:
        raise SystemExit(f'查询 GitHub 仓库失败：{code} {info}')
    if dry:
        log(f'  [dry-run] 将创建 GitHub 仓库 {GITHUB_OWNER}/{GITHUB_REPO}')
        return f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git'
    payload = json.dumps({'name': GITHUB_REPO, 'private': private,
                          'description': '小凌 XIAOLING — 会成长的全平台 AI 数字生命',
                          'auto_init': False}).encode()
    code, info = api('POST', 'https://api.github.com/user/repos', data=payload,
                     headers={'Authorization': f'Bearer {token}',
                              'Accept': 'application/vnd+json',
                              'Content-Type': 'application/json'})
    if code not in (200, 201):
        raise SystemExit(f'创建 GitHub 仓库失败：{code} {info}')
    log(f'  GitHub 仓库已创建：{info.get("html_url")}')
    return info.get('clone_url') or f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}.git'


def ensure_gitee(token: str, private: bool, dry: bool) -> str:
    base = 'https://gitee.com/api/v5'
    code, info = api('GET', f'{base}/repos/{GITEE_OWNER}/{GITEE_REPO}'
                     f'?access_token={token}')
    if code == 200 and info.get('full_name'):
        log(f'  Gitee 仓库已存在：{info.get("html_url")}')
        return f'https://gitee.com/{GITEE_OWNER}/{GITEE_REPO}.git'
    if dry:
        log(f'  [dry-run] 将创建 Gitee 仓库 {GITEE_OWNER}/{GITEE_REPO}')
        return f'https://gitee.com/{GITEE_OWNER}/{GITEE_REPO}.git'
    data = urllib.parse.urlencode({
        'access_token': token, 'name': GITEE_REPO,
        'description': '小凌 XIAOLING — 会成长的全平台 AI 数字生命',
        'private': 'true' if private else 'false',
        'auto_init': 'false',
    }).encode()
    code, info = api('POST', f'{base}/user/repos', data=data,
                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
    if code not in (200, 201):
        raise SystemExit(f'创建 Gitee 仓库失败：{code} {info}')
    log(f'  Gitee 仓库已创建：{info.get("html_url")}')
    return f'https://gitee.com/{GITEE_OWNER}/{GITEE_REPO}.git'


def push(remote: str, url_with_token: str, dry: bool):
    """把 token 临时塞进 remote URL 推送，推完立刻改回干净地址。"""
    plain = git(['remote', 'get-url', remote], check=False).stdout.strip() \
        if git(['remote', 'get-url', remote], check=False).returncode == 0 else None
    if dry:
        log(f'  [dry-run] 将推送 {BRANCH} → {remote}')
        return
    git(['remote', 'set-url', remote, url_with_token])
    try:
        r = subprocess.run(['git', 'push', '-u', remote, f'{BRANCH}:{BRANCH}'],
                           cwd=str(ROOT), capture_output=True, text=True)
        if r.returncode != 0:
            log(f'  推送 {remote} 失败：\n{(r.stderr or r.stdout)[-800:]}')
            log('  提示：若提示 Gitee 默认分支是 master，可再跑一次 '
                f'`git push {remote} {BRANCH}:master`')
        else:
            log(f'  已推送 {remote}')
    finally:
        if plain:
            git(['remote', 'set-url', remote, plain], check=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--private', action='store_true', help='建私有仓库')
    a = ap.parse_args()

    gh = os.environ.get('GITHUB_TOKEN', '').strip()
    gt = os.environ.get('GITEE_TOKEN', '').strip()
    if not gh and not gt:
        raise SystemExit('需要至少一个 token：GITHUB_TOKEN 或 GITEE_TOKEN（见文件头注释）')

    # 本地还没提交就先别推
    st = git(['status', '--porcelain']).stdout.strip()
    if st:
        log(f'[警告] 工作区有未提交改动（{len(st.splitlines())} 项），将只推送已提交内容')

    if gh:
        log('GitHub:')
        clone = ensure_github(gh, a.private, a.dry_run)
        safe = clone.replace('https://', f'https://{GITHUB_OWNER}:{gh}@')
        push('github', safe, a.dry_run)
    else:
        log('跳过 GitHub（未设 GITHUB_TOKEN）')

    if gt:
        log('Gitee:')
        clone = ensure_gitee(gt, a.private, a.dry_run)
        safe = clone.replace('https://gitee.com/',
                             f'https://{urllib.parse.quote(GITEE_OWNER)}:{gt}@gitee.com/')
        push('gitee', safe, a.dry_run)
    else:
        log('跳过 Gitee（未设 GITEE_TOKEN）')

    log()
    log('完成。别忘了在 GitHub 仓库 Settings → Secrets 里配 CF_API_TOKEN / CF_ACCOUNT_ID，')
    log('否则 .github/workflows/deploy-pages.yml 部署官网会失败。')


if __name__ == '__main__':
    main()
