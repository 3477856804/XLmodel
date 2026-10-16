# -*- coding: utf-8 -*-
"""运行时环境自举（Runtime Environment Bootstrap）。

需求（老板原话）：运行程序时（含打包成 exe 之后）自动检测环境依赖：
宿主有 GPU → 下载对应的 GPU（CUDA）版 torch；没有 GPU → 下载 CPU 版；
依赖下载完成后，前端才进入主页面。

为什么单独写这个模块，而不是扩展 core/deps.py：
    core.deps 走 `python -m pip` 通道，白名单 + train 档强制确认，
    且打包态（frozen）直接拒绝（产物里没有 pip）。而本需求的核心场景
    恰恰是**打包后的 exe**——里面既没有 pip，也没有 torch（backend.spec
    明确 excludes torch 4.2G）。所以这里用纯标准库自己实现一条
    「wheel 下载 + 解压 + sys.path 注入」的通道，源码态/冻结态通用。

核心流程（worker 单线程执行，前端轮询 env:status）：
    detect_gpu → pick flavor(gpu/cpu) → pick cuda tag(按驱动 CUDA 版本)
    → build plan(torch + 依赖闭包，读 METADATA Requires-Dist 递归)
    → 下载(断点续传/缓存/sha256 可选校验) → 解压进沙箱 site-{flavor}
    → sys.path 注入 → importlib.import_module('torch') 验证
    → 写 ready 标记 → state=ready

设计取舍：
  * 版本来源：torch 本体从 download.pytorch.org 的 per-CUDA 目录页解析
    （PyPI 上没有 +cu126 这种本地标签 wheel）；其余依赖走 PyPI
    simple index（JSON API 太大，simple 页足够）。两者都可用环境变量
    换成内网镜像（XIAOLING_TORCH_INDEX / XIAOLING_PYPI_INDEX）。
  * 依赖闭包：每个 wheel 解压前先读它的 dist-info/METADATA，解析
    Requires-Dist + marker 评估（extra == "cuda" 只在 GPU 档成立）。
    已在 sys.modules / find_spec / importlib.metadata 可见且版本满足
    约束的依赖直接跳过 —— PyInstaller 的 PYZ 里通常已有
    sympy/jinja2/filelock/fsspec/networkx，能省几百 MB。
  * flavor 目录隔离：site-gpu / site-cpu 并存，切换 flavor 不删旧
    目录（红线：不主动删文件），sys.path 只注入当前 flavor。
  * import torch 用 importlib.import_module 而不是 import 语句 ——
    backend.spec 的 Analysis 会静态收集 import 语句，写死 import torch
    会把 4.2G 拖回包里。
  * 状态机对外暴露：idle/detecting/downloading/installing/ready/error。
    status() 在 idle 时自动触发 ensure_async()（幂等），所以前端何时
    首次查询都能自愈，不存在「后端没触发、前端干等」的窗口。
"""
import importlib
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import html as _html

log = logging.getLogger('runtime_env')

# ------------------------------------------------------------------ 常量

# torch wheel 源（有序 fallback），元素 = (base, 是否带 torch/ 子目录)。
#   阿里云 mirrors.aliyun.com/pytorch-wheels/<cu-tag>/（直接列 wheel，国内快）
#   官方 download.pytorch.org/whl/<cu-tag>/torch/（带子目录）
# 默认把国内镜像放前面：官方 CDN（download-r2.pytorch.org）直连在国内
# 实测只有 ~100KB/s，阿里云通常数 MB/s；海外用户可设
# XIAOLING_TORCH_INDEX=https://download.pytorch.org/whl 覆盖回官方。
def _torch_sources():
    env = os.environ.get('XIAOLING_TORCH_INDEX')
    if env:
        base = env.rstrip('/')
        return [(base, True), (base, False)]
    return [('https://mirrors.aliyun.com/pytorch-wheels', False),
            ('https://download.pytorch.org/whl', True)]

# PyPI simple index 源（其余依赖：nvidia-*、sympy 等）。
def _pypi_sources():
    env = os.environ.get('XIAOLING_PYPI_INDEX')
    if env:
        return [env.rstrip('/')]
    return ['https://pypi.org',
            'https://pypi.tuna.tsinghua.edu.cn',
            'https://mirrors.aliyun.com/pypi']

_PROBE_HOSTS = ('pypi.org', 'files.pythonhosted.org',
                'mirrors.aliyun.com', 'download.pytorch.org')

_CHUNK = 1024 * 1024          # 1MB 分块
_SOCK_TIMEOUT = 60            # 单次读超时（大文件慢网）
_DL_RETRIES = 5               # 下载中断重试次数（断点续传，不从头下）

# 磁盘预检阈值（wheel 缓存 + 解压，粗估保底）。
# 依据实测：torch 2.11.0+cu128 wheel 2.56GB，解压后 site-gpu 约 6GB，
# 峰值 ≈ 8.6GB；CPU 版 wheel ~0.2GB + 解压 ~2GB，峰值 ≈ 2.5GB。
_DISK_NEED = {'gpu': 10.0 * 1024**3, 'cpu': 3.0 * 1024**3}

# pip 包名 → import 名。None 表示「不探测，总是下载」（二进制包，
# import 名与包名不对应，且 PyInstaller 产物里不可能有）。
_IMPORT_NAME = {
    'typing-extensions': 'typing_extensions',
    'nvidia-cuda-nvcc-cu12': None,
    'nvidia-cuda-cupti-cu12': None,
    'nvidia-cuda-runtime-cu12': None,
    'nvidia-cuda-nvrtc-cu12': None,
    'nvidia-cudnn-cu12': None,
    'nvidia-cublas-cu12': None,
    'nvidia-cufft-cu12': None,
    'nvidia-curand-cu12': None,
    'nvidia-cusolver-cu12': None,
    'nvidia-cusparse-cu12': None,
    'nvidia-cusparselt-cu12': None,
    'nvidia-nccl-cu12': None,
    'nvidia-nvtx-cu12': None,
    'nvidia-nvjitlink-cu12': None,
    'nvidia-cufile-cu12': None,
    'triton': None,
}

# 驱动 CUDA 版本 → torch wheel 的 cu 标签（选不超过驱动的最高档）。
# CUDA minor version compatibility：低版本编译的 wheel 能在高版本驱动上跑，
# 所以这里取「≤ 驱动支持」的最高档，稳妥优先。
def _pick_cuda_tag(cuda_version):
    if not cuda_version:
        return None
    try:
        parts = str(cuda_version).split('.')
        major, minor = int(parts[0]), int(parts[1])
    except Exception:
        return None
    if major > 12:
        return 'cu128'          # CUDA 13.x 驱动向后兼容 CUDA 12 应用
    if major == 12:
        if minor >= 6:
            return 'cu126'
        if minor >= 4:
            return 'cu124'
        if minor >= 1:
            return 'cu121'
        return 'cu121'      # 12.0 驱动也能跑 cu121（minor 兼容）
    if major == 11 and minor >= 8:
        return 'cu118'
    return None


# cu 档降级链：首选档的目录页不存在（镜像未同步该档）或没有匹配 wheel 时，
# 依次退到更低档，全部落空才报错。CUDA 13.x 驱动也可显式尝试 cu130。
_CU_TAG_ORDER = ['cu130', 'cu128', 'cu126', 'cu124', 'cu121', 'cu118']


def _cuda_tag_chain(cuda_version):
    tag = _pick_cuda_tag(cuda_version)
    if tag in _CU_TAG_ORDER:
        return _CU_TAG_ORDER[_CU_TAG_ORDER.index(tag):]
    return ['cu126', 'cu124', 'cu121', 'cu118']      # 版本未知的保守链


# ------------------------------------------------------------------ 路径

def _frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def deps_root() -> str:
    """依赖的落盘根目录。

    优先级：XIAOLING_DEPS_ROOT > XIAOLING_HOME/deps（冻结态由
    runtime_hook 指到 %LOCALAPPDATA%\\Xiaoling\\runtime）>
    源码态 <repo>/backend/.deps。
    """
    env = os.environ.get('XIAOLING_DEPS_ROOT')
    if env:
        return os.path.abspath(env)
    home = os.environ.get('XIAOLING_HOME')
    if home:
        return os.path.join(home, 'deps')
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        '.deps')


def site_dir(flavor: str) -> str:
    return os.path.join(deps_root(), 'site-%s' % flavor)


def wheels_dir() -> str:
    return os.path.join(deps_root(), 'wheels')


def _marker_path(flavor: str) -> str:
    return os.path.join(deps_root(), 'ready-%s.json' % flavor)


def _prefs_path() -> str:
    return os.path.join(deps_root(), 'prefs.json')


# ------------------------------------------------------------------ 状态

_STATE = {
    'state': 'idle',           # idle/detecting/downloading/installing/ready/error
    'phase': '',
    'percent': 0.0,
    'flavor': None,            # gpu / cpu
    'cuda_tag': None,
    'gpu': None,
    'torch_version': None,
    'cuda_ok': None,
    'bytes_done': 0,
    'bytes_total': 0,
    'speed_bps': 0.0,
    'wheels': [],              # [{name, size, done}]
    'error': None,
    'log': [],
    'started_at': None,
    'finished_at': None,
    'override': None,          # prefs.flavor_override
}
_LOCK = threading.RLock()
_WORKER = None
_TRIGGERED = False            # idle 自动触发只做一次，防止 status↔ensure_async 递归


def _set(**kw):
    with _LOCK:
        for k, v in kw.items():
            _STATE[k] = v


def _logline(msg: str):
    line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
    with _LOCK:
        _STATE['log'] = (_STATE['log'] + [line])[-60:]
    log.info(msg)


def status() -> dict:
    global _TRIGGERED
    with _LOCK:
        st = dict(_STATE)
        st['log'] = list(_STATE['log'])
        st['wheels'] = [dict(w) for w in _STATE['wheels']]
    st['state_machine'] = 'idle→detecting→downloading→installing→ready|error'
    st['deps_root'] = deps_root()
    st['site_dir'] = site_dir(st.get('flavor') or 'cpu')
    st['frozen'] = _frozen()
    st['python'] = sys.executable
    # idle 时自动触发自举（幂等）—— 前端首次查询无论早晚都能自愈。
    # 只用 _TRIGGERED 触发一次：ensure_async 内部也会 return status()，
    # 没有这道闸门会形成 status→ensure_async→status 无限递归
    # （RecursionError，前端一查 env:status 就崩）。
    if st['state'] == 'idle' and not _TRIGGERED:
        _TRIGGERED = True
        try:
            ensure_async()
        except Exception:                                     # noqa: BLE001
            pass
    return st


# ------------------------------------------------------------------ GPU 检测

def _run(cmd, timeout=12):
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=timeout, encoding='utf-8',
                            errors='replace')
        return cp.stdout or '', cp.stderr or '', cp.returncode
    except Exception:
        return '', '', -1


def _nvidia_smi_info():
    """解析 nvidia-smi：GPU 名 + 驱动版本 + 驱动支持的 CUDA 版本。

    注意两种输出格式：
      · 旧版：表头有 "CUDA Version: 12.6"
      · 新版（R580+/617.x 驱动起）：头行是
        "NVIDIA-SMI 617.42 ... CUDA UMD Version: 13.4"
    两种都要认，否则检测得到 GPU 却拿不到 CUDA 版本，被迫回退 CPU 版。
    """
    exe = shutil.which('nvidia-smi')
    if not exe:
        return None
    out, err, rc = _run([exe], timeout=15)
    if rc != 0 and not out:
        return None
    info = {'nvidia_smi': True}
    m = re.search(r'CUDA\s+(?:UMD\s+)?Version:\s*(\d+\.\d+)', out)
    if m:
        info['cuda'] = m.group(1)
    m = re.search(r'Driver Version:\s*([\d.]+)', out)
    if m:
        info['driver'] = m.group(1)
    out2, _, rc2 = _run([exe, '--query-gpu=name,driver_version',
                         '--format=csv,noheader'], timeout=10)
    if rc2 == 0 and out2.strip():
        first = out2.strip().splitlines()[0]
        parts = [p.strip() for p in first.split(',')]
        if parts and parts[0]:
            info['name'] = parts[0]
        if len(parts) > 1 and parts[1] and not info.get('driver'):
            info['driver'] = parts[1]
    return info


def _has_nvcuda() -> bool:
    if not sys.platform.startswith('win'):
        return os.path.exists('/dev/nvidiactl') or os.path.exists(
            '/proc/driver/nvidia/version')
    root = os.environ.get('SystemRoot', r'C:\Windows')
    return os.path.exists(os.path.join(root, 'System32', 'nvcuda.dll'))


def _video_controller_names():
    """WMI 显卡名（nvidia-smi 缺失时的补充展示信息）。"""
    if sys.platform.startswith('win'):
        ps = ('Get-CimInstance Win32_VideoController | '
              'Select-Object -ExpandProperty Name')
        out, _, rc = _run(['powershell', '-NoProfile', '-Command', ps],
                          timeout=20)
        if rc == 0 and out.strip():
            return [l.strip() for l in out.splitlines() if l.strip()]
    else:
        out, _, rc = _run(['sh', '-c', 'lspci 2>/dev/null | grep -iE "vga|3d|display"'],
                          timeout=15)
        if rc == 0 and out.strip():
            return [l.strip() for l in out.splitlines() if l.strip()]
    return []


def detect_gpu() -> dict:
    """检测 GPU 与驱动 CUDA 版本。XIAOLING_TORCH_FLAVOR=cpu|gpu 可强制覆盖。"""
    forced = (os.environ.get('XIAOLING_TORCH_FLAVOR') or '').strip().lower()
    if forced in ('cpu', 'gpu'):
        info = {'vendor': 'forced', 'name': '手动指定（%s）' % forced,
                'cuda': None, 'driver': None, 'nvidia_smi': False,
                'forced_flavor': forced}
        if forced == 'gpu':
            smi = _nvidia_smi_info() or {}
            info.update({k: smi.get(k) for k in ('cuda', 'driver', 'name')
                         if smi.get(k)})
            info['vendor'] = 'nvidia' if smi else 'unknown'
        return info

    smi = _nvidia_smi_info()
    if smi:
        return {'vendor': 'nvidia', 'name': smi.get('name', 'NVIDIA GPU'),
                'cuda': smi.get('cuda'), 'driver': smi.get('driver'),
                'nvidia_smi': True}
    if _has_nvcuda():
        # 有 NVIDIA 驱动但没带 nvidia-smi 工具：CUDA 版本未知，保守给
        # cu121（CUDA 12.1 wheel 可在任何 CUDA 12.x 驱动上运行）。
        return {'vendor': 'nvidia',
                'name': 'NVIDIA GPU（检测到 NVIDIA 驱动，未带 nvidia-smi）',
                'cuda': None, 'driver': None, 'nvidia_smi': False}
    names = _video_controller_names()
    lower = ' | '.join(names).lower()
    vendor = 'none'
    if 'nvidia' in lower or 'geforce' in lower or 'quadro' in lower:
        vendor = 'nvidia'
    elif 'amd' in lower or 'radeon' in lower:
        vendor = 'amd'
    elif 'intel' in lower:
        vendor = 'intel'
    return {'vendor': vendor, 'name': names[0] if names else '未检测到独立 GPU',
            'cuda': None, 'driver': None, 'nvidia_smi': False}


def _pick_flavor(gpu: dict) -> str:
    forced = gpu.get('forced_flavor')
    if forced in ('cpu', 'gpu'):
        return forced
    if gpu.get('vendor') == 'nvidia':
        return 'gpu'
    return 'cpu'


# ------------------------------------------------------------------ 网络

def _has_network() -> bool:
    import socket
    for host in _PROBE_HOSTS:
        try:
            with socket.create_connection((host, 443), timeout=3.0):
                return True
        except Exception:
            continue
    return False


def _http_open(url, timeout=_SOCK_TIMEOUT, headers=None):
    req = urllib.request.Request(url, headers=headers or {
        'User-Agent': 'XiaoLing-runtime-env/1.0 (+python %s)' % sys.version.split()[0]
    })
    return urllib.request.urlopen(req, timeout=timeout)


def _http_get(url, timeout=30):
    with _http_open(url, timeout=timeout) as r:
        return r.read()


# ------------------------------------------------------------------ 版本工具

def _ver_tuple(v: str):
    v = str(v).split('+', 1)[0]          # 去 local version
    out = []
    for part in v.split('.'):
        m = re.match(r'^(\d+)(.*)$', part)
        if m:
            num, suf = int(m.group(1)), m.group(2)
            # 第三段 stage：正式版(无后缀)=1，预发布(rc/dev/a/b)=0。
            # PEP 440：1.0rc1 < 1.0。早年只留后缀字符串比较，
            # 'rc1' > '' 会让 1.0rc1 反大于 1.0。
            out.append((0, num, 0 if suf else 1, suf))
        else:
            out.append((1, 0, 0, part))     # 非数字段排后
    return tuple(out)


def _ver_cmp(a: str, b: str) -> int:
    ta, tb = _ver_tuple(a), _ver_tuple(b)
    n = max(len(ta), len(tb))
    # 补位必须是 (0,0,'')：早年用 (1,0,'')（非数字段标记）导致
    # `82.0.1 < 82` 被误判为 True —— 短版本补出的 (1,0,'') 比
    # 长版本的 (0,0,'') "大"，整个大小关系颠倒。PEP 440 语义：
    # 缺失的末段补 0，即 82 == 82.0 == 82.0.0。
    ta = ta + ((0, 0, 1, ''),) * (n - len(ta))
    tb = tb + ((0, 0, 1, ''),) * (n - len(tb))
    return (ta > tb) - (ta < tb)


def _spec_ok(version: str, spec: str) -> bool:
    """评估 PEP440 版本约束子集：== != >= <= > < ~= ，逗号分隔。"""
    spec = (spec or '').strip()
    if not spec:
        return True
    if '*' in spec:                      # 前缀匹配 1.13.*
        prefix = spec.split('*')[0].rstrip('.')
        return version.startswith(prefix)
    for clause in spec.split(','):
        clause = clause.strip()
        if not clause:
            continue
        m = re.match(r'^(==|!=|>=|<=|>|<|~=)\s*(.+)$', clause)
        if not m:
            return False
        op, ref = m.group(1), m.group(2).strip()
        c = _ver_cmp(version, ref)
        if op == '==' and c != 0:
            return False
        if op == '!=' and c == 0:
            return False
        if op == '>=' and c < 0:
            return False
        if op == '<=' and c > 0:
            return False
        if op == '>' and c <= 0:
            return False
        if op == '<' and c >= 0:
            return False
        if op == '~=':
            # ~=X.Y.Z 语义：>= X.Y.Z 且 < X.(Y+1)；~=X.Y：>= X.Y 且 < (X+1)
            if c < 0:
                return False
            parts = ref.split('.')
            try:
                if len(parts) >= 3:
                    upper = '%s.%d' % (parts[0], int(parts[1]) + 1)
                else:
                    upper = '%d' % (int(parts[0]) + 1)
            except ValueError:
                return False
            if _ver_cmp(version, upper) >= 0:
                return False
    return True


# ------------------------------------------------------------------ marker 评估

def _marker_ok(marker: str, *, gpu_flavor: bool) -> bool:
    """评估 wheel METADATA 里的 Requires-Dist marker（常见子集）。

    支持：extra == "cuda" / platform_system == "Windows" / os_name == "nt" /
    sys_platform == "win32" / python_version < "3.13" / implementation_name，
    and / or 组合（and 优先）。无法解析的项按 False 处理（宁可少下一个
    Linux-only 的 triton，也不把几百 MB 拖回来）。
    """
    marker = (marker or '').strip()
    if not marker:
        return True

    def term(tok: str):
        tok = tok.strip().strip('()')
        m = re.match(r'^([a-z_]+)\s*(==|!=|>=|<=|>|<)\s*["\']([^"\']*)["\']$',
                     tok)
        if not m:
            return None
        var, op, val = m.group(1), m.group(2), m.group(3)
        if var == 'extra':
            actual = 'cuda' if gpu_flavor else ''
        elif var == 'platform_system':
            actual = {'win32': 'Windows', 'linux': 'Linux',
                      'darwin': 'Darwin'}.get(sys.platform, '')
        elif var == 'os_name':
            actual = {'win32': 'nt', 'linux': 'posix',
                      'darwin': 'posix'}.get(sys.platform, '')
        elif var == 'sys_platform':
            actual = sys.platform
        elif var == 'python_version':
            actual = '%d.%d' % sys.version_info[:2]
        elif var == 'implementation_name':
            actual = sys.implementation.name
        else:
            return None
        if op == '==':
            return actual == val
        if op == '!=':
            return actual != val
        return _spec_ok(actual, op + val)

    # or 拆层，and 优先
    for or_part in re.split(r'\s+or\s+', marker):
        parts = re.split(r'\s+and\s+', or_part)
        results = [term(p) for p in parts]
        if any(r is None for r in results):
            continue
        if all(results):
            return True
    return False


def _split_req(req: str):
    """'nvidia-cublas-cu12==12.6.3.1; extra == "cuda"' → (pkg, spec, marker)。"""
    req = req.strip()
    name_part, _, marker = req.partition(';')
    m = re.match(r'^([A-Za-z0-9._-]+)\s*(\[[^\]]*\])?\s*(.*)$', name_part.strip())
    if not m:
        return None, '', ''
    pkg = m.group(1)
    spec = (m.group(3) or '').strip()
    return pkg, spec, marker.strip()


# ------------------------------------------------------------------ wheel 源解析

def _platform_tags():
    """可接受的平台 tag（有序）。'any' 必须包含——sympy/filelock/
    typing-extensions/networkx/jinja2 等纯 Python 依赖是 py3-none-any，
    漏掉它这些包一个都解析不到，torch 的依赖闭包就断了。"""
    if sys.platform.startswith('win'):
        return ['win_amd64', 'win32', 'any']
    if sys.platform == 'darwin':
        return ['macosx_11_0_arm64', 'macosx_10_9_x86_64', 'any']
    return ['manylinux_2_28_x86_64', 'manylinux_2_17_x86_64',
            'manylinux2014_x86_64', 'linux_x86_64', 'any']


def _py_tags():
    """可接受的 python tag（**不要带尾随连字符**——_tag_in 会统一包
    '-tag-'；带尾随 '-' 的 'py3-none-' 会被包成 '-py3-none--' 双横线，
    导致所有 py3-none-* 纯 Python wheel 全部匹配失败）。"""
    vi = sys.version_info
    return ['cp%d%d-cp%d%d' % (vi.major, vi.minor, vi.major, vi.minor),
            'cp%d%d-abi3' % (vi.major, vi.minor),
            'py3-none', 'py2.py3-none']


def _tag_in(low: str, tag: str) -> bool:
    """tag 三明治匹配：'-cp313-cp313-' 或结尾 '-win_amd64.whl'。

    必须用三明治而不能用子串：否则 'cp313-cp313' 会误中自由线程版的
    'cp313-cp313t'（GIL 解释器 import 会直接 ABI 不匹配失败）。
    """
    return ('-' + tag + '-') in low or low.endswith('-' + tag + '.whl')


def _wheel_matches(filename: str, *, local_tag: str):
    """按 python tag + 平台 tag 过滤；local_tag 为 '+cu126'/''/'+cpu'。"""
    low = filename.lower()
    if not low.endswith('.whl'):
        return False
    if not any(_tag_in(low, t) for t in _py_tags()):
        return False
    if not any(_tag_in(low, t) for t in _platform_tags()):
        return False
    if local_tag:
        if local_tag == '+cpu':
            return '+cpu' in low
        return ('+' + local_tag[1:]) in low
    return '+cpu' in low or not re.search(r'\+(cu\d+|rocm[\d.]+)', low)


def _href_name(href: str) -> str:
    """目录页 href → 规范文件名。

    两个坑，顺序不能反：
      1) 镜像页（阿里云）把 '+' 编码成 HTML 实体 &#43; —— 必须先
         html.unescape。若先 split('#')（本想切 PyPI 的 #sha256=
         fragment），会把 &#43; 里的 '#' 当成 fragment 分隔符，切出
         'torch-2.14.1&' 这种残名，所有本地标签 wheel 全部匹配失败。
      2) unescape 之后才 split('#') 去 fragment，最后 unquote 处理
         %2B 之类的百分号编码。
    """
    raw = _html.unescape(href)
    raw = raw.split('/')[-1]
    raw = raw.split('#')[0]
    return urllib.parse.unquote(raw)


def _select_torch_wheel(flavor: str, cuda_tag):
    """从 torch wheel 源（官方 → 阿里云镜像 fallback）解析 torch wheel。

    返回 (url, version, filename, size)。GPU 档必须带 +cuXXX 本地标签；
    CPU 档必须 +cpu。取满足条件的最大版本。
    """
    if flavor == 'gpu' and cuda_tag:
        local = '+' + cuda_tag
    else:
        local = '+cpu'
    pref = (os.environ.get('XIAOLING_TORCH_VERSION') or '').strip()
    errors = []
    for base, with_sub in _torch_sources():
        leaf = ('%s/torch/' % (cuda_tag or 'cpu')) if with_sub \
            else ('%s/' % (cuda_tag or 'cpu'))
        index = '%s/%s' % (base, leaf)
        try:
            html = _http_get(index, timeout=45).decode('utf-8', 'replace')
        except Exception as e:                            # noqa: BLE001
            errors.append('%s: %s' % (base, e))
            continue
        hrefs = re.findall(r'href="([^"]+\.whl)[^"]*"', html)
        best = None
        for href in hrefs:
            name = _href_name(href)
            if not _wheel_matches(name, local_tag=local):
                continue
            m = re.match(r'^torch-([0-9][^-]*?)(\+[^-]*)?-', name)
            if not m:
                continue
            ver = m.group(1)
            if pref and ver != pref:
                continue
            if 'rc' in ver or 'dev' in ver:
                continue
            if best is None or _ver_cmp(ver, best[1]) > 0:
                best = (urllib.parse.urljoin(index, _html.unescape(href)),
                        ver, name)
        if best is None:
            errors.append('%s: 无匹配 wheel' % base)
            continue
        # HEAD 拿大小
        size = None
        try:
            with _http_open(best[0], timeout=30) as r:
                size = int(r.headers.get('Content-Length') or 0) or None
        except Exception:                                 # noqa: BLE001
            pass
        return best[0], best[1], best[2], size
    raise RuntimeError(
        '所有 torch 源均失败（%s）：%s'
        % (' → '.join(_torch_sources()), ' | '.join(errors[:4])))


def _resolve_torch(flavor: str, cuda_version):
    """定位 torch wheel：cu 档降级链 × 源 fallback 的矩阵搜索。"""
    if flavor == 'gpu':
        tags = _cuda_tag_chain(cuda_version)
    else:
        tags = [None]
    errors = []
    for tag in tags:
        try:
            return _select_torch_wheel('gpu' if tag else 'cpu', tag)
        except Exception as e:                            # noqa: BLE001
            errors.append('%s: %s' % (tag or 'cpu', e))
    raise RuntimeError('未能定位 torch wheel：%s' % ' | '.join(errors[:4]))


def _resolve_pypi_wheel(pkg: str, spec: str):
    """从 PyPI simple index（官方 → 国内镜像 fallback）解析满足 spec 的
    最大版本 wheel。返回 (url, version, filename, size) 或 None。"""
    errors = []
    for base in _pypi_sources():
        index = '%s/simple/%s/' % (base, pkg)
        try:
            html = _http_get(index, timeout=45).decode('utf-8', 'replace')
        except Exception as e:                            # noqa: BLE001
            errors.append('%s: %s' % (base, e))
            continue
        hrefs = re.findall(r'href="([^"]+)"', html)
        best = None
        for href in hrefs:
            name = _href_name(href)
            if not _wheel_matches(name, local_tag=''):
                continue
            stem = name[:-4] if name.lower().endswith('.whl') else name
            parts = stem.split('-')
            if len(parts) < 2:
                continue
            ver = parts[1]
            if re.search(r'(a|b|rc|dev)\d*$', ver):       # 跳过预发布
                continue
            if not _spec_ok(ver, spec):
                continue
            if best is None or _ver_cmp(ver, best[1]) > 0:
                best = (urllib.parse.urljoin(index, _html.unescape(href)),
                        ver, name)
        if best is not None:
            size = None
            try:
                with _http_open(best[0], timeout=30) as r:
                    size = int(r.headers.get('Content-Length') or 0) or None
            except Exception:                             # noqa: BLE001
                pass
            return best[0], best[1], best[2], size
        errors.append('%s: 无匹配 wheel' % base)
    return None


# ------------------------------------------------------------------ 下载

def _download(url: str, dest: str, on_progress=None) -> str:
    """下载到 dest（.part 断点续传 + 网络抖动自动重试）。

    .part 文件名带 URL 指纹：换源（官方↔镜像）重试时旧源的部分下载
    不会被误续到新源文件后面（那会拼出损坏的 wheel）。

    重试策略（2026-10-17 冻结态实测教训）：国内镜像（阿里云
    pytorch-wheels）常有分钟级限速掐断 —— CPU 版 118MB 下到 26%
    时 60s 读超时，一次失败就让整个自举 error，前端只能干等用户点
    重试。现在单次连接的 stall 不再致命：带 Range 从 .part 断点
    重连续传，指数退避，最多 _DL_RETRIES 次。4xx（404/403 等
    永久错误，除 429）立即失败不浪费重试；5xx/超时/断连/读残缺
    才重试。已下载的字节永不丢弃。
    """
    import hashlib
    import http.client
    import socket
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = '%s.%s.part' % (dest, hashlib.md5(url.encode('utf-8')).hexdigest()[:8])
    last = None
    for attempt in range(_DL_RETRIES + 1):
        pos = os.path.getsize(part) if os.path.exists(part) else 0
        total = None
        headers = {'User-Agent': 'XiaoLing-runtime-env/1.0'}
        if pos:
            headers['Range'] = 'bytes=%d-' % pos
        try:
            with _http_open(url, timeout=_SOCK_TIMEOUT, headers=headers) as r:
                total_hdr = r.headers.get('Content-Length')
                if r.status == 206 and total_hdr:
                    total = pos + int(total_hdr)
                elif r.status == 200:
                    if pos:                    # 服务端不支持续传，从头写
                        pos = 0
                    total = int(total_hdr) if total_hdr else None
                mode = 'ab' if pos else 'wb'
                done = pos
                last_cb = 0.0
                with open(part, mode) as f:
                    while True:
                        chunk = r.read(_CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        now = time.time()
                        if on_progress and now - last_cb >= 0.25:
                            last_cb = now
                            on_progress(done, total)
                if on_progress:
                    on_progress(done, total)
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise                       # 永久错误（403/404），重试无意义
            last = e
        except (socket.timeout, TimeoutError, ConnectionError,
                http.client.HTTPException, urllib.error.URLError) as e:
            last = e
        else:
            # 本次尝试完整读完：校验大小后原子就位
            if total and os.path.getsize(part) != total:
                raise RuntimeError('下载不完整：%s（%s/%s 字节）'
                                   % (os.path.basename(dest),
                                      os.path.getsize(part), total))
            os.replace(part, dest)
            return dest
        # ---- 失败：退避后带 Range 断点重连续传 ----
        if attempt < _DL_RETRIES:
            wait = min(8.0, 1.5 * (attempt + 1))
            _logline('下载中断（%s），%.1fs 后断点续传重试（%d/%d，已保存 %s）：%s'
                     % (type(last).__name__, wait, attempt + 1, _DL_RETRIES,
                        _human(os.path.getsize(part)
                               if os.path.exists(part) else 0),
                        os.path.basename(dest)))
            time.sleep(wait)
    raise RuntimeError('下载失败（重试 %d 次后仍中断）：%s → %s'
                       % (_DL_RETRIES, os.path.basename(dest),
                          type(last).__name__))


def _cached_wheel(path: str, size):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        if size and os.path.getsize(path) != size:
            return False
        return True
    return False


# ------------------------------------------------------------------ METADATA

def _wheel_requires(wheel_path: str, *, gpu_flavor: bool):
    """读 wheel 的 Requires-Dist，按 flavor 过滤 marker。返回 [(pkg, spec)]。"""
    try:
        with zipfile.ZipFile(wheel_path) as z:
            meta = [n for n in z.namelist()
                    if n.endswith('.dist-info/METADATA')]
            if not meta:
                return []
            text = z.read(meta[0]).decode('utf-8', 'replace')
    except Exception as e:
        _logline('读取 METADATA 失败（%s）：%s' % (os.path.basename(wheel_path), e))
        return []
    out = []
    for line in text.splitlines():
        if not line.startswith('Requires-Dist:'):
            continue
        pkg, spec, marker = _split_req(line[len('Requires-Dist:'):])
        if not pkg:
            continue
        if marker and not _marker_ok(marker, gpu_flavor=gpu_flavor):
            continue
        out.append((pkg, spec))
    return out


def _already_available(pkg: str, spec: str) -> bool:
    """依赖是否已在当前环境（PYZ / site-packages / 已注入的 site-*）可见。"""
    name = _IMPORT_NAME.get(pkg, pkg.replace('-', '_'))
    if name is None:
        return False
    try:
        if importlib.util.find_spec(name) is None:
            return False
    except Exception:
        return False
    # 有模块还要看版本是否满足约束（PYZ 里的 sympy 可能旧于 torch 要求）
    if not spec:
        return True
    try:
        import importlib.metadata as md
        ver = md.version(pkg)
        return _spec_ok(ver, spec)
    except Exception:
        try:
            mod = importlib.import_module(name)
            ver = getattr(mod, '__version__', '')
            return bool(ver) and _spec_ok(ver, spec)
        except Exception:
            return True        # 查不到版本就当作满足（宁可复用）


# ------------------------------------------------------------------ 安装

def _install_wheel(wheel_path: str, flavor: str):
    dest = site_dir(flavor)
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(wheel_path) as z:
        z.extractall(dest)
    return dest


def _activate(flavor: str):
    """把 site-{flavor} 注入 sys.path 并加载 torch（幂等）。

    幂等是关键：torch 的 C 扩展（torch/_C*.pyd）内部有进程级全局的
    dispatch registry，**重复加载会 RuntimeError（Only a single
    TORCH_LIBRARY can be used to register the namespace triton）**。
    而 sys.modules.pop('torch') 只删顶层，torch._C 等子模块仍残留 ——
    早先版本 _ready_marker_ok 验证一次、worker 再 activate 一次，
    正好触发这个崩溃。现在：已加载且档位匹配 → 直接复用；档位不匹配
    → 清掉全部 torch.* 子模块再加载（flavor 切换场景，主路径是重启
    后单档位，不会冲突）。
    """
    site = site_dir(flavor)
    if site not in sys.path:
        sys.path.insert(0, site)
    existing = sys.modules.get('torch')
    if existing is not None:
        ver = getattr(existing, '__version__', '') or ''
        if ('+cpu' in ver) == (flavor == 'cpu'):
            return existing                      # 已加载且档位匹配
        for k in [k for k in list(sys.modules)
                  if k == 'torch' or k.startswith('torch.')]:
            sys.modules.pop(k, None)
    return importlib.import_module('torch')


# ------------------------------------------------------------------ ready 标记 / prefs

def _read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _prefs():
    return _read_json(_prefs_path(), {})


def _gpu_signature(gpu: dict, flavor: str, cuda_tag):
    if flavor != 'gpu':
        return 'cpu'
    return 'gpu:%s:%s' % (gpu.get('cuda') or 'unknown', cuda_tag or 'none')


def _system_torch_flavor():
    """系统/venv 里已可 import 的 torch 是哪个档位。

    源码态开发者（venv --system-site-packages）常自带 torch：档位匹配
    就直接采用，免去重复下载数 GB；不匹配（如系统是 GPU 版、当前要
    CPU 版）才走下载。返回 'gpu' / 'cpu' / None（没有或 import 失败）。
    PyPI 默认版（版本号无 +cpu/+cu 标签）就是 CUDA 构建 → gpu。

    注意：本模块注入的 site-{flavor} torch 不算「系统」——否则进程内
    已 activate 过再调 _system_torch_flavor 会把自己误判成系统已有。
    """
    mod = sys.modules.get('torch')
    if mod is not None:
        f = (getattr(mod, '__file__', '') or '').replace('\\', '/')
        if 'site-cpu/' in f or 'site-gpu/' in f:
            return None
    try:
        if importlib.util.find_spec('torch') is None:
            return None
    except Exception:                                         # noqa: BLE001
        return None
    try:
        torch = importlib.import_module('torch')
        ver = getattr(torch, '__version__', '') or ''
    except Exception:                                         # noqa: BLE001
        return None
    if '+cpu' in ver:
        return 'cpu'
    return 'gpu'


def _ready_marker_ok(flavor: str, gpu: dict) -> bool:
    """ready 标记是否有效（不 import torch——那会与 worker 后续的
    _activate 形成双加载，触发 torch C 扩展重复注册崩溃；文件在即
    视为有效，真正 import 放 _activate 一处）。"""
    marker = _read_json(_marker_path(flavor), None)
    if not isinstance(marker, dict):
        return False
    if marker.get('gpu_signature') != _gpu_signature(gpu, flavor,
                                                     marker.get('cuda_tag')):
        return False
    site = site_dir(flavor)
    return os.path.exists(os.path.join(site, 'torch', '__init__.py'))


def _write_ready_marker(flavor: str, gpu: dict, cuda_tag, version, cuda_ok):
    _write_json(_marker_path(flavor), {
        'flavor': flavor,
        'torch_version': version,
        'cuda_tag': cuda_tag,
        'cuda_ok': cuda_ok,
        'gpu_signature': _gpu_signature(gpu, flavor, cuda_tag),
        'gpu': {k: gpu.get(k) for k in ('vendor', 'name', 'cuda', 'driver')},
        'installed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    })


# ------------------------------------------------------------------ 计划构建（含下载）

def _progress_tracker():
    """维护 wheels 列表与总进度，供 _STATE 上报。"""
    st = {'wheels': [], 'done_bytes': 0, 'total_bytes': 0, 'speed': 0.0,
          '_t0': time.time(), '_d0': 0}
    lock = threading.Lock()

    def add(name, size):
        with lock:
            st['wheels'].append({'name': name, 'size': size or 0, 'done': 0})
            st['total_bytes'] += (size or 0)

    def tick(done, total, name):
        with lock:
            for w in st['wheels']:
                if w['name'] == name:
                    w['done'] = done
                    break
            st['done_bytes'] = sum(w['done'] for w in st['wheels'])
            el = max(0.001, time.time() - st['_t0'])
            st['speed'] = (st['done_bytes'] - st['_d0']) / el
            st['_t0'], st['_d0'] = time.time(), st['done_bytes']
            _set(wheels=[dict(w) for w in st['wheels']],
                 bytes_done=st['done_bytes'], bytes_total=st['total_bytes'],
                 speed_bps=st['speed'])
            # downloading 阶段占 5%~85%
            if st['total_bytes'] > 0:
                frac = min(1.0, st['done_bytes'] / st['total_bytes'])
                _set(percent=0.05 + 0.80 * frac)

    return add, tick


def build_plan(flavor: str, cuda_tag, progress, torch_hit=None) -> dict:
    """BFS 展开依赖闭包并下载全部 wheel。

    progress = (add(name,size), tick(done,total,name))
    torch_hit：调用方已解析好的 torch wheel（cu 档降级链的结果），
    避免 BFS 内部重复做源搜索。
    返回 {pkg: {'path','version','url','size','cached'}}。
    """
    wdir = wheels_dir()
    os.makedirs(wdir, exist_ok=True)
    plan = {}
    queue = [('torch', (os.environ.get('XIAOLING_TORCH_VERSION') or '').strip())]
    gpu_flavor = flavor == 'gpu'
    while queue:
        pkg, spec = queue.pop(0)
        if pkg in plan:
            continue
        if pkg != 'torch' and _already_available(pkg, spec):
            plan[pkg] = {'cached': 'system', 'version': None, 'size': 0}
            _logline('依赖已在环境中，跳过下载：%s' % pkg)
            continue
        if pkg == 'torch':
            if torch_hit is not None:
                url, ver, fname, size = torch_hit
            else:
                url, ver, fname, size = _select_torch_wheel(flavor, cuda_tag)
        else:
            hit = _resolve_pypi_wheel(pkg, spec)
            if hit is None:
                # PyPI 上没有匹配本平台的 wheel：若是 torch 声明的依赖，
                # 记日志继续（部分 nvidia 包在某些 python 版本确实缺席）。
                _logline('未找到 %s 的可用 wheel（%s），跳过' % (pkg, spec or 'latest'))
                plan[pkg] = {'cached': 'absent', 'version': None, 'size': 0}
                continue
            url, ver, fname, size = hit
        dest = os.path.join(wdir, fname)
        if _cached_wheel(dest, size):
            _logline('命中缓存：%s' % fname)
        else:
            _logline('下载 %s（%s）' % (fname,
                                       _human(size) if size else '大小未知'))
            progress[0](fname, size)
            _download(url, dest,
                      on_progress=lambda d, t, n=fname: progress[1](d, t, n))
        plan[pkg] = {'path': dest, 'version': ver, 'url': url,
                     'size': size, 'fname': fname}
        # 展开依赖闭包（只有新下载的 wheel 才需要读 METADATA）
        if not plan[pkg].get('cached'):
            for dep, dspec in _wheel_requires(dest, gpu_flavor=gpu_flavor):
                if dep not in plan:
                    queue.append((dep, dspec))
    return plan


def _human(n):
    if not n:
        return '?'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024:
            return '%.1f%s' % (n, unit)
        n /= 1024
    return '%.1fPB' % n


# ------------------------------------------------------------------ worker

def _worker(force: bool = False):
    t0 = time.time()
    try:
        _set(state='detecting', phase='检测硬件环境…', percent=0.02,
             error=None, started_at=time.time(), finished_at=None)
        _logline('开始运行时环境自举（%s）' %
                 ('强制重装' if force else '按需安装'))
        gpu = detect_gpu()
        override = _prefs().get('flavor_override')
        flavor = override if override in ('cpu', 'gpu') else _pick_flavor(gpu)
        cuda_tag = _pick_cuda_tag(gpu.get('cuda')) if flavor == 'gpu' else None
        if flavor == 'gpu' and not cuda_tag:
            _logline('检测到 NVIDIA GPU 但驱动 CUDA 版本未知/过旧，回退 CPU 版')
            flavor, cuda_tag = 'cpu', None
        _set(gpu=gpu, flavor=flavor, cuda_tag=cuda_tag, override=override)
        _logline('GPU：%s（%s）→ %s 版 torch%s' % (
            gpu.get('name') or '?', gpu.get('cuda') or 'CUDA 版本未知',
            'GPU(CUDA)' if flavor == 'gpu' else 'CPU',
            ' ' + cuda_tag if cuda_tag else ''))

        if not force and _ready_marker_ok(flavor, gpu):
            torch = _activate(flavor)
            _set(state='ready', phase='运行环境就绪', percent=1.0,
                 torch_version=torch.__version__, finished_at=time.time(),
                 error=None)
            _logline('环境已就绪：torch %s（%s 版）'
                     % (torch.__version__, flavor))
            return

        # 系统/venv 已带匹配档位的 torch（源码态常见）：直接采用。
        # 冻结态产物 excludes torch，find_spec 必然为 None，不受影响。
        if not force and _system_torch_flavor() == flavor:
            try:
                torch = importlib.import_module('torch')
                _write_ready_marker(flavor, gpu, cuda_tag,
                                    torch.__version__, None)
                _set(state='ready', phase='运行环境就绪', percent=1.0,
                     torch_version=torch.__version__,
                     finished_at=time.time(), error=None)
                _logline('采用系统已安装的 torch %s（%s 版），无需下载'
                         % (torch.__version__, flavor))
                return
            except Exception as e:                            # noqa: BLE001
                _logline('系统 torch 采用失败，继续走下载：%s' % e)

        if not _has_network():
            raise RuntimeError(
                '无法连接下载源（%s）。请检查网络后重试；内网环境可用 '
                'XIAOLING_TORCH_INDEX / XIAOLING_PYPI_INDEX 指向镜像。'
                % ', '.join(_PROBE_HOSTS))

        # 磁盘预检（按 flavor 粗估，避免下到一半爆盘）
        root = deps_root()
        os.makedirs(root, exist_ok=True)
        need = _DISK_NEED[flavor]
        try:
            free = shutil.disk_usage(root).free
        except Exception:
            free = None
        if free is not None and free < need:
            raise RuntimeError(
                '磁盘空间不足：安装 %s 版 torch 约需 %s 可用空间，当前仅 %s。'
                '请清理磁盘或设置 XIAOLING_DEPS_ROOT 到其他盘。'
                % ('GPU' if flavor == 'gpu' else 'CPU',
                   _human(need), _human(free)))

        _set(state='downloading', phase='定位 PyTorch 安装源…',
             percent=0.05)
        # cu 档降级链 × 源 fallback：首选档目录页不存在（镜像未同步）时
        # 自动退到更低档，例如 CUDA 13.4 驱动优先 cu130/cu128。
        torch_hit = _resolve_torch(flavor, gpu.get('cuda'))
        if flavor == 'gpu':
            m = re.search(r'\+(cu\d+)[-/]', torch_hit[2])
            if m:
                cuda_tag = m.group(1)          # 回读实际选中的档位
                _set(cuda_tag=cuda_tag)
        _logline('选定 torch %s（%s 档，%s）'
                 % (torch_hit[1], cuda_tag or 'cpu',
                    _human(torch_hit[3]) if torch_hit[3] else '大小未知'))
        progress = _progress_tracker()
        plan = build_plan(flavor, cuda_tag, progress, torch_hit=torch_hit)
        n_dl = sum(1 for v in plan.values() if not v.get('cached'))
        _logline('依赖闭包解析完成：共 %d 个包，需下载 %d 个'
                 % (len(plan), n_dl))

        _set(state='installing', phase='解压安装…', percent=0.86)
        done = 0
        for pkg, info in plan.items():
            if info.get('cached'):
                continue
            _install_wheel(info['path'], flavor)
            done += 1
            _set(phase='解压安装…（%d/%d）' % (done, n_dl),
                 percent=0.86 + 0.08 * (done / max(1, n_dl)))
        _logline('解压完成，共 %d 个 wheel' % n_dl)

        _set(state='installing', phase='验证导入 PyTorch…', percent=0.96)
        torch = _activate(flavor)
        cuda_ok = None
        if flavor == 'gpu':
            try:
                cuda_ok = bool(torch.cuda.is_available())
            except Exception:
                cuda_ok = False
            if not cuda_ok:
                _logline('注意：torch 已就绪但 CUDA 不可用'
                         '（可能是驱动过旧或 nvidia 依赖不全），'
                         '推理将回退 CPU')
        _write_ready_marker(flavor, gpu, cuda_tag, torch.__version__, cuda_ok)
        _set(state='ready', phase='运行环境就绪', percent=1.0,
             torch_version=torch.__version__, cuda_ok=cuda_ok,
             finished_at=time.time(), error=None)
        _logline('环境就绪：torch %s（%s 版，CUDA %s），耗时 %.0fs'
                 % (torch.__version__, flavor,
                    '可用' if cuda_ok else ('不可用' if flavor == 'gpu' else '不适用'),
                    time.time() - t0))
    except Exception as e:
        import traceback
        _logline('环境自举失败：%s' % e)
        _set(state='error', phase='环境初始化失败',
             error='%s: %s' % (type(e).__name__, e),
             error_tail=traceback.format_exc()[-1500:],
             finished_at=time.time())


def ensure_async(force: bool = False):
    """幂等触发后台自举。已有活着的 worker 就直接返回当前状态。

    真正启动新 worker 时记一条「触发来源」日志（调用栈末尾 3 帧）：
    2026-10-17 冻结态实测出现过与查询/按钮都对不上的周期性强自愈重试，
    没有这条日志就无法区分是 main.py 首启线程、前端 env:retry、还是
    别的路径触发的。诊断用，不影响行为。
    """
    global _WORKER
    started = False
    with _LOCK:
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(target=_worker, kwargs={'force': force},
                                       daemon=True, name='runtime-env-worker')
            _WORKER.start()
            started = True
    if started:
        try:
            import traceback as _tb
            frames = _tb.extract_stack()
            caller = ' ← '.join('%s:%d' % (os.path.basename(fr.filename), fr.lineno)
                                for fr in frames[-4:-1])
            _logline('自举触发来源：%s' % caller)
        except Exception:                                     # noqa: BLE001
            pass
    return status()


def ensure_ready(force: bool = False, wait: bool = True, timeout: float = 0):
    """同步等待就绪（CLI / 测试用）。wait=False 时立即返回当前状态。"""
    ensure_async(force=force)
    if not wait:
        return status()
    t0 = time.time()
    while True:
        st = status()
        if st['state'] in ('ready', 'error'):
            return st
        if timeout and time.time() - t0 > timeout:
            return st
        time.sleep(0.5)


def retry():
    """失败后重试（wheel 缓存 + .part 续传都在，不会从零开始）。"""
    with _LOCK:
        _STATE['error'] = None
    return ensure_async(force=False)


def switch_flavor(flavor):
    """切换 torch 版本档：'cpu' / 'gpu' / None（auto 按检测结果）。"""
    prefs = _prefs()
    if flavor in ('cpu', 'gpu'):
        prefs['flavor_override'] = flavor
    else:
        prefs['flavor_override'] = None
    _write_json(_prefs_path(), prefs)
    _logline('切换 torch 版本档：%s' % (flavor or '自动检测'))
    return ensure_async(force=False)


def reinstall():
    """强制重装当前档位（清 ready 标记效果）。"""
    return ensure_async(force=True)


# ------------------------------------------------------------------ CLI

def handle(sub: str) -> str:
    """deps:env 子命令（JSON 字符串返回，与 server.py 其他命令族一致）。"""
    sub = (sub or '').strip().lower()
    if sub in ('', 'status'):
        return json.dumps(status(), ensure_ascii=False, default=str)
    if sub == 'retry':
        return json.dumps(retry(), ensure_ascii=False, default=str)
    if sub in ('use-cpu', 'cpu'):
        return json.dumps(switch_flavor('cpu'), ensure_ascii=False, default=str)
    if sub in ('use-gpu', 'gpu', 'auto'):
        return json.dumps(switch_flavor(None), ensure_ascii=False, default=str)
    if sub == 'reinstall':
        return json.dumps(reinstall(), ensure_ascii=False, default=str)
    return json.dumps({'ok': False,
                       'error': '未知子命令：%s（可用：status / retry / '
                                'use-cpu / use-gpu / reinstall）' % sub},
                      ensure_ascii=False)


if __name__ == '__main__':                                  # 直接跑：CLI 自举
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    op = (sys.argv[1] if len(sys.argv) > 1 else 'status').strip().lower()
    if op in ('install', 'ensure', 'ready'):
        st = ensure_ready()
        print(json.dumps({k: st.get(k) for k in
                          ('state', 'flavor', 'torch_version', 'cuda_ok',
                           'error', 'percent')},
                         ensure_ascii=False, indent=2))
        sys.exit(0 if st['state'] == 'ready' else 1)
    print(handle(op))
