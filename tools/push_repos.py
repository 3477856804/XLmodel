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
import time
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


def gitee_login(token: str) -> str:
    """令牌所属账号名。

    Gitee 要求 HTTPS 地址里的**用户名必须是令牌本人的 login**，写仓库 owner
    会报 `remote: The token username invalid`（403）。
    本项目令牌属于 mvpth，仓库却在 COSMOnb666 名下，所以必须查一次。
    """
    code, info = api('GET', f'https://gitee.com/api/v5/user?access_token={token}')
    if code == 200 and info.get('login'):
        return info['login']
    log(f'  [警告] 取不到令牌归属（{code}），退回用仓库 owner')
    return GITEE_OWNER


def ensure_gitee(token: str, private: bool, dry: bool) -> str:
    base = 'https://gitee.com/api/v5'
    code, info = api('GET', f'{base}/repos/{GITEE_OWNER}/{GITEE_REPO}'
                     f'?access_token={token}')
    if code == 200 and info.get('full_name'):
        log(f'  Gitee 仓库已存在：{info.get("html_url")}'
            f'（{"私有" if info.get("private") else "公开"}，'
            f'默认分支 {info.get("default_branch")}）')
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


def run_git(args, **kw):
    """统一给 git 套上"能连上托管平台"的配置。

    三个坑，缺一个就推不动：
      1. 本机全局配了 http/https 代理（43.99.100.108:3128），直连 Gitee 会
         报 `TLS connect error: wrong version number`，必须绕过；
      2. Windows 默认的 schannel 后端跟 Gitee 握手会
         `SEC_E_INVALID_TOKEN`，改用 openssl 后端；
      3. HTTP/2 下偶发 `decryption failed or bad record mac` 断流，降到 1.1。
    需要代理才能上网的机器加 `--use-proxy` 覆盖。
    """
    base = ['-c', 'http.sslBackend=openssl', '-c', 'http.version=HTTP/1.1',
            '-c', 'http.postBuffer=524288000']
    if not USE_PROXY:
        base += ['-c', 'http.proxy=', '-c', 'https.proxy=']
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    return subprocess.run(['git', *base, *args], cwd=str(ROOT), env=env, **kw)


def push(url_with_token: str, label: str, dry: bool):
    """一次性推送到带 token 的 URL —— 不写进 remote，token 不会留在 .git/config。"""
    if dry:
        log(f'  [dry-run] 将推送 {BRANCH} → {label}')
        return
    last = ''
    for attempt in range(1, 4):
        r = run_git(['push', url_with_token, f'{BRANCH}:{BRANCH}'],
                    capture_output=True, text=True)
        out = (r.stderr or '') + (r.stdout or '')
        if r.returncode == 0:
            log(f'  已推送 {label}')
            log('   ' + out.strip().splitlines()[-1] if out.strip() else '')
            return
        last = out
        if 'Everything up-to-date' in out:
            log(f'  {label} 已是最新')
            return
        log(f'  第 {attempt} 次失败，3 秒后重试…')
        time.sleep(3)
    log(f'  推送 {label} 失败：\n{last[-900:]}')
    if 'fetch first' in last or 'non-fast-forward' in last:
        log('  远端有本地没有的提交。按"绝不删除文件"的原则，请先：')
        log(f'    git fetch {url_with_token} {BRANCH}')
        log('    git merge -X ours --allow-unrelated-histories FETCH_HEAD')
        log('  （远端历史会完整保留，冲突取本地）而不是直接 force push。')


USE_PROXY = False


def main():
    global USE_PROXY
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--private', action='store_true', help='建私有仓库')
    ap.add_argument('--use-proxy', action='store_true',
                    help='保留全局 http/https 代理（默认绕过，见 run_git 注释）')
    a = ap.parse_args()
    USE_PROXY = a.use_proxy

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
        push(safe, 'GitHub', a.dry_run)
    else:
        log('跳过 GitHub（未设 GITHUB_TOKEN）')

    if gt:
        log('Gitee:')
        clone = ensure_gitee(gt, a.private, a.dry_run)
        # 坑：用户名必须是**令牌本人**的 login，不是仓库 owner
        login = urllib.parse.quote(gitee_login(gt))
        safe = clone.replace('https://gitee.com/',
                             f'https://{login}:{gt}@gitee.com/')
        push(safe, 'Gitee', a.dry_run)
    else:
        log('跳过 Gitee（未设 GITEE_TOKEN）')

    log()
    log('完成。别忘了在 GitHub 仓库 Settings → Secrets 里配 CF_API_TOKEN / CF_ACCOUNT_ID，')
    log('否则 .github/workflows/deploy-pages.yml 部署官网会失败。')


if __name__ == '__main__':
    main()
