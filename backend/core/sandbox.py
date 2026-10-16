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

import ctypes
import logging
import os
import platform
import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

try:
    # ``resource`` 是 POSIX 专有模块，Windows 上根本不存在。
    # 以前是无条件 import，打包版在 Windows 上启动时整个 core.sandbox 直接
    # 抛 ModuleNotFoundError（backend.log 里每次 sandbox:status 都报错），
    # 连带模型商店下载、路径/用量查询这些走 sandbox: 的功能全废。
    #
    # 它只被用来设置 setrlimit 资源上限，而那些调用本身全部包在 try/except 里；
    # Windows 侧改用 Job Object / ctypes 限流，不依赖本模块。故降级为可选。
    import resource
except ImportError:                       # pragma: no cover - Windows
    resource = None

try:                                    # 兼容「直接 import」与「作为包模块导入」
    from . import config as _cfg
except Exception:                       # pragma: no cover
    import config as _cfg               # type: ignore

logger = logging.getLogger('xiaoling.sandbox')

_lock = threading.RLock()

# 命令超时兜底：防止注入类提示词让工具永久挂起
MAX_EXEC_SECONDS = int(os.environ.get('XIAOLING_SANDBOX_TIMEOUT', '60'))

# 危险命令黑名单（保守清单，宁可少放行）。
# 注意：黑名单只是「第一道提示性闸门」，真正的隔离靠下面的 OS 级机制
# （Landlock + resource limits）。黑名单挡不住的，OS 级隔离来兜底。
_DENY_TOKENS = (
    'format ', 'del /f', 'rm -rf /', 'rm -rf ~', 'shutdown', 'shutdown.exe',
    'diskpart', 'mkfs', ':(){', 'chmod -r 777 /',
)

# ================================================================
# OS 级进程隔离（Landlock + resource limits）
# ================================================================
# 设计原则：**有 OS 级隔离就用，没有就明确降级，绝不假装安全**。
#
# Linux   : 优先 Landlock（路径级强制，deny-by-default），失败降级到
#           resource.setrlimit + chdir。
# macOS   : 预留 Seatbelt 钩子（本环境无法验证，失败即降级）。
# Windows : 无可用内核沙箱，降级到原有的「路径白名单 + 命令黑名单」。
#
# 每一次实际执行都会在返回值里通过 ``isolation`` 字段如实上报本次到底
# 用了哪一级隔离，UI / 日志一眼能看出是真隔离还是降级态。

# ---- 三档权限 ----
PERM_READONLY = 'readonly'   # 只能读 workspace + 系统库，不能写/建/删
PERM_DEFAULT  = 'default'    # 可读写 workspace，可执行非网络命令
PERM_FULL     = 'full'       # 完全访问（需用户确认；本函数不做隔离）
PERMISSION_LEVELS = (PERM_READONLY, PERM_DEFAULT, PERM_FULL)

# ---- 资源限制（全部可用环境变量覆盖，便于排障）----
_RLIMIT_CPU_SEC   = int(os.environ.get('XIAOLING_SANDBOX_CPU', '60'))
_RLIMIT_AS_BYTES  = int(os.environ.get('XIAOLING_SANDBOX_AS',
                                        str(512 * 1024 * 1024)))
_RLIMIT_FSIZE_BYTES = int(os.environ.get('XIAOLING_SANDBOX_FSIZE',
                                         str(10 * 1024 * 1024)))
# NPROC 不能设成一个很小的绝对数：RLIMIT_NPROC 是按「真实 UID 全系统任务数」
# 记账的，本进程和后端父进程共享同一个 UID（已有几十个任务/线程），
# 直接设成 10 会让 shell 自己都 fork 不出来（EAGAIN: Cannot fork）。
# 正确做法：以「当前 UID 任务基线 + 余量」为上限——既能挡住 fork 炸弹，
# 又不误伤正常命令。
_RLIMIT_NPROC_MARGIN = int(os.environ.get('XIAOLING_SANDBOX_NPROC_MARGIN', '32'))

# ---- Landlock 访问位（对齐 Linux uapi/linux/landlock.h）----
_LN_EXECUTE     = 1 << 0
_LN_WRITE_FILE  = 1 << 1
_LN_READ_FILE   = 1 << 2
_LN_READ_DIR    = 1 << 3
_LN_REMOVE_DIR  = 1 << 4
_LN_REMOVE_FILE = 1 << 5
_LN_MAKE_CHAR   = 1 << 6
_LN_MAKE_DIR    = 1 << 7
_LN_MAKE_REG    = 1 << 8
_LN_MAKE_SOCK   = 1 << 9
_LN_MAKE_FIFO   = 1 << 10
_LN_MAKE_SYM    = 1 << 11
_LN_REFER       = 1 << 12
_LN_TRUNCATE    = 1 << 13

_LN_READ_ONLY = _LN_EXECUTE | _LN_READ_FILE | _LN_READ_DIR
_LN_READ_WRITE = (
    _LN_READ_ONLY | _LN_WRITE_FILE | _LN_MAKE_REG | _LN_MAKE_DIR |
    _LN_MAKE_CHAR | _LN_MAKE_SOCK | _LN_MAKE_FIFO | _LN_MAKE_SYM |
    _LN_REMOVE_FILE | _LN_REMOVE_DIR | _LN_REFER | _LN_TRUNCATE
)

# 只读放行的系统目录：子进程要能 exec /bin/sh、加载动态库、读 /etc。
_SYSTEM_RO_PATHS = (
    '/usr', '/lib', '/lib64', '/bin', '/sbin', '/etc', '/run', '/dev',
)

_PR_SET_NO_NEW_PRIVS = 38


class _LandlockRulesetAttr(ctypes.Structure):
    _fields_ = [('handled_access_fs', ctypes.c_uint64)]


class _LandlockPathBeneath(ctypes.Structure):
    # 内核里 allowed_access(u64) 在前、parent_fd(s32) 在后，顺序不能反
    _fields_ = [('allowed_access', ctypes.c_uint64),
                ('parent_fd', ctypes.c_int32)]


def _syscall_nrs() -> tuple | None:
    """本架构上 Landlock 三个 syscall 的号。x86_64/aarch64 都是 444/445/446。"""
    m = platform.machine()
    if m in ('x86_64', 'AMD64', 'aarch64'):
        return (444, 445, 446)
    return None


def _landlock_supported() -> bool:
    """探测内核是否真的支持 Landlock（建一个 ruleset，成功即可用）。

    结果会影响 run_sandboxed 上报的 isolation 级别——只有探测成功才宣称
    用了 landlock，否则如实降级，**绝不假装安全**。
    """
    if platform.system() != 'Linux':
        return False
    nrs = _syscall_nrs()
    if nrs is None:
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        ra = _LandlockRulesetAttr(_LN_READ_ONLY)
        fd = libc.syscall(nrs[0], ctypes.byref(ra), ctypes.sizeof(ra), 0)
        if fd < 0:
            logger.info('sandbox: landlock_create_ruleset unavailable '
                        '(errno=%s), will degrade to rlimit+chdir',
                        ctypes.get_errno())
            return False
        try:
            os.close(fd)
        except OSError:
            pass
        return True
    except Exception as e:                       # noqa: BLE001
        logger.info('sandbox: landlock probe failed (%s), degrading', e)
        return False


def _apply_landlock(workspace: str, permission: str) -> bool:
    """在子进程（preexec_fn）内建立 Landlock 规则并 restrict_self。

    deny-by-default：规则集里 handled 的访问位一律默认拒绝，再显式放行
    workspace（rw 或 ro）与系统目录（ro）。任何异常都吞掉并返回 False，
    让外层回退到纯 rlimit，绝不让沙箱因子进程异常而直接崩溃。
    """
    nrs = _syscall_nrs()
    if nrs is None:
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        # 先关 no_new_privs（restrict_self 对非特权线程的前置条件）
        try:
            libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        except Exception:                       # noqa: BLE001
            pass

        # 关键语义：handled_access_fs 列的是「要管控的访问位」。只有列进去的
        # 访问位才会被 deny-by-default；没列进去的位 Landlock 根本不管、一律
        # 放行。所以无论哪档权限，ruleset 都必须 handled **全量**访问位，权限
        # 差异只体现在每条 path rule 授予的 access 上：
        #   - readonly：workspace/系统目录都只授只读 -> 任何写都被拒
        #   - default ：workspace 授读写、系统目录只读
        handled = _LN_READ_WRITE
        if permission == PERM_READONLY:
            ws_access = _LN_READ_ONLY
        else:
            ws_access = _LN_READ_WRITE

        create_nr, add_nr, restrict_nr = nrs
        ra = _LandlockRulesetAttr(handled)
        rfd = libc.syscall(create_nr, ctypes.byref(ra), ctypes.sizeof(ra), 0)
        if rfd < 0:
            return False

        def _add(path: str, access: int) -> None:
            try:
                dfd = os.open(path, os.O_PATH)
            except OSError:
                return                          # 该路径不存在，跳过即可
            try:
                pb = _LandlockPathBeneath(access, dfd)
                # 本内核实测可用的调用约定：(rfd, rule_type=1, &pb, flags=0)
                libc.syscall(add_nr, rfd, 1, ctypes.byref(pb), 0)
            except Exception:                   # noqa: BLE001
                pass
            finally:
                try:
                    os.close(dfd)
                except OSError:
                    pass

        # workspace：default 可读写 / readonly 只读
        _add(workspace, ws_access)
        # 系统库与二进制：只读可执行
        for p in _SYSTEM_RO_PATHS:
            _add(p, _LN_READ_ONLY)
        # default 档额外放行 tmp（子进程常需要临时文件）
        if permission == PERM_DEFAULT:
            _add(str(tmp_dir()), _LN_READ_WRITE)

        ret = libc.syscall(restrict_nr, rfd, 0)
        return ret == 0
    except Exception as e:                       # noqa: BLE001
        logger.info('sandbox: landlock restrict failed (%s), rlimit fallback', e)
        return False


def _count_uid_tasks() -> int:
    """统计当前真实 UID 下已有的**任务数**（进程 + 线程）。

    RLIMIT_NPROC 按「真实 UID 的所有 task（含线程）」记账，不能只数进程——
    像 Chrome 这种一个进程就开几十条线程，漏算会让上限设得过低，子进程
    连一个外部命令都 fork 不出来（EAGAIN）。这里用每个进程 status 里的
    ``Threads:`` 字段求和。读不到就返回 0（上层据此放弃降 NPROC）。
    """
    try:
        uid = os.getuid()
    except Exception:                           # noqa: BLE001
        return 0
    n = 0
    try:
        proc = Path('/proc')
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                status = (entry / 'status').read_text(errors='replace')
            except OSError:
                continue
            real_uid = None
            threads = 1
            for line in status.splitlines():
                if line.startswith('Uid:'):
                    try:
                        real_uid = int(line.split()[1])
                    except (ValueError, IndexError):
                        pass
                elif line.startswith('Threads:'):
                    try:
                        threads = int(line.split()[1])
                    except (ValueError, IndexError):
                        threads = 1
            if real_uid == uid:
                n += max(1, threads)
    except OSError:
        return 0
    return n


def _build_preexec(workspace: str, permission: str,
                   landlock_on: bool) -> "callable":
    """生成 preexec_fn：在 fork 之后、exec 之前于子进程内施加所有限制。"""
    cpu = _RLIMIT_CPU_SEC
    as_bytes = _RLIMIT_AS_BYTES
    fsize = _RLIMIT_FSIZE_BYTES

    # NPROC 上限 = 当前 UID 任务基线 + 余量（读不到就不降低，保持继承值）
    nproc_ceiling = -1
    if platform.system() == 'Linux':
        try:
            base = _count_uid_tasks()
            if base > 0:
                nproc_ceiling = base + _RLIMIT_NPROC_MARGIN
        except Exception:                       # noqa: BLE001
            nproc_ceiling = -1

    def _preexec() -> None:
        # 1) 收紧权限：禁止 setuid 提权（配合 Landlock）
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        except Exception:                       # noqa: BLE001
            pass
        # 2) 切到 workspace
        try:
            os.chdir(workspace)
        except Exception:                       # noqa: BLE001
            pass
        # 3) resource limits（全部 per-process，继承给子进程）
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
            lim = min(cpu, hard) if hard > 0 else cpu
            resource.setrlimit(resource.RLIMIT_CPU, (lim, lim))
        except Exception:                       # noqa: BLE001
            pass
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            lim = as_bytes if hard < 0 else min(as_bytes, hard)
            resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
        except Exception:                       # noqa: BLE001
            pass
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
        except Exception:                       # noqa: BLE001
            pass
        try:
            if nproc_ceiling > 0:
                soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
                lim = nproc_ceiling if hard < 0 else min(nproc_ceiling, hard)
                resource.setrlimit(resource.RLIMIT_NPROC, (lim, lim))
        except Exception:                       # noqa: BLE001
            pass
        # 4) Landlock 路径隔离（最后做，做完即不可逃逸）
        if landlock_on and permission != PERM_FULL:
            try:
                _apply_landlock(workspace, permission)
            except Exception:                   # noqa: BLE001
                pass

    return _preexec


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


def _guard_roots(work: str) -> tuple[list, list]:
    """返回 (可读写根, 只读根)，与 Landlock/Seatbelt 实际放行的范围一致。

    刻意保持和真实隔离**同一套**允许面：降级守卫不能比真隔离更严，
    否则「这台机器跑得通的命令，换台内核旧的机器就被拦」，
    用户只会认为沙箱在乱拦活。
    """
    rw = [Path(work).resolve()]
    for fn in (tmp_dir, models_dir):
        try:
            rw.append(Path(fn()).resolve())
        except Exception:                       # noqa: BLE001
            pass
    for b in (getattr(_cfg, 'STAR_DIR', None), getattr(_cfg, 'DATA_DIR', None),
              root()):
        try:
            if b:
                rw.append(Path(b).resolve())
        except Exception:                       # noqa: BLE001
            pass
    ro = [Path(p) for p in _SYSTEM_RO_PATHS]
    if platform.system() == 'Darwin':
        ro += [Path(p) for p in _MACOS_SYSTEM_RO_PATHS]
    return rw, ro


def _looks_like_path(token: str) -> bool:
    """这个 token 是否像一个文件路径（值得拿去做逃逸判定）。"""
    if not token:
        return False
    if token.startswith(('/', './', '../', '.\\', '..\\', '\\')):
        return True
    if len(token) >= 3 and token[1] == ':' and token[2] in '/\\':
        return True
    return token.startswith('~/') or token == '~'


def lexical_escape_check(command: str, work: str, permission_level: str) -> dict:
    """词法路径守卫：命令里显式出现的路径，是否落在允许范围之外。

    **仅在真实 OS 路径隔离缺席时启用**（Linux 无 Landlock / macOS 无
    sandbox-exec / 未知平台 / Windows 只有 Job Object），且 permission_level
    不是 PERM_FULL。

    允许面刻意与 Landlock 一致：workspace/tmp/models 可读写，系统目录
    （/usr /lib /bin /etc …）只读放行。所以 ``cat /etc/passwd`` 不会被本守卫
    拦下 —— 它在真隔离下本来也是允许的，拦它只会让降级模式比真隔离更严。
    真正拦的是 ``~/.ssh/id_rsa``、``/home/别人/…``、``/root/.aws/credentials``
    这类沙箱外的用户数据，以及 ``../../`` 形式的相对逃逸。

    必须说清楚：**这不是安全边界**。它只看命令字符串里的字面路径，挡得住
    误操作与简单逃逸，挡不住编码/拼接/``cd`` 之后再操作/解释器内联脚本
    （``python -c "open('/home/x/.ssh/id_rsa')"`` 就绕过去了）。因此返回体
    带 ``guard: 'lexical'``，且**绝不**因为它把 capability() 的
    path_isolation 翻成 True。

    Returns
    -------
    dict
        {'ok': bool, 'offending': [str], 'note': str, 'guard': 'lexical'}
    """
    result = {
        'ok': True,
        'offending': [],
        'note': ('词法路径守卫：只检查命令里显式出现的路径，不是安全边界，'
                 '挡不住编码/拼接/解释器内联绕过。'),
        'guard': 'lexical',
    }

    if permission_level == PERM_FULL:
        return result

    rw_roots, ro_roots = _guard_roots(work)
    work_path = rw_roots[0]

    # 按 shell 分隔符与引号切 token；引号内的路径同样要查。
    tokens = re.split(r'[\s;|&`$(){}<>"\']+', command)

    for token in tokens:
        if not _looks_like_path(token):
            continue
        try:
            expanded = Path(token.replace('\\', '/')).expanduser()
            resolved = (expanded if expanded.is_absolute()
                        else work_path / expanded)
            resolved = resolved.resolve()
        except Exception:                       # noqa: BLE001
            continue
        s = str(resolved)
        if any(s == str(r) or s.startswith(str(r) + '/') for r in rw_roots):
            continue
        if any(s == str(r) or s.startswith(str(r) + '/') for r in ro_roots):
            continue
        result['ok'] = False
        if token not in result['offending']:
            result['offending'].append(token)

    if not result['ok']:
        result['note'] = (
            f'词法路径守卫检测到沙箱外路径：{"、".join(result["offending"])}。'
            '该检查不是安全边界，只能挡住误操作与简单逃逸，挡不住刻意绕过'
            '（编码、拼接、解释器内联脚本）。'
        )

    return result


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


# ================================================================
# 跨平台隔离：macOS Seatbelt / Windows Job Object
# ================================================================
# 核心原则：**有平台原生隔离就用，没有就明确降级标注，绝不假装安全**。
#
# Linux   : Landlock（路径级强制，deny-by-default）
# macOS   : Seatbelt（sandbox-exec + .sb profile）
# Windows : Job Object（CPU / 内存 / 进程数限制，路径隔离 best-effort）
# 其他    : rlimit + chdir 或纯 subprocess


# ---- macOS 系统只读目录（Seatbelt 用）----
_MACOS_SYSTEM_RO_PATHS = (
    '/usr', '/lib', '/bin', '/sbin', '/etc', '/var', '/dev',
    '/System', '/private/etc', '/private/var',
)


def _seatbelt_available() -> bool:
    """探测 macOS sandbox-exec 是否可用。仅 Darwin 返回 True。"""
    if platform.system() != 'Darwin':
        return False
    try:
        from shutil import which
        return which('sandbox-exec') is not None
    except Exception:                           # noqa: BLE001
        return False


def _build_seatbelt_profile(workspace: str, permission: str) -> str:
    """生成 Seatbelt (.sb) profile 文本。

    三档权限映射：
      - readonly : deny-by-default，仅放行 workspace 与系统目录的只读访问
      - default  : deny-by-default，workspace 可读写，系统目录只读
      - full     : 不限制（调用方应直接走 unrestricted，不调用本函数）
    """
    lines = ['(version 1)']
    if permission == PERM_FULL:
        # full 档不应该走到这里；兜底放行一切
        lines.append('(allow default)')
        return '\n'.join(lines)

    # deny-by-default：除显式 allow 外一律拒绝
    lines.append('(deny default)')
    # 基础进程操作
    lines.append('(allow process-exec)')
    lines.append('(allow process-fork)')
    lines.append('(allow process-signal)')
    lines.append('(allow sysctl-read)')
    # 系统目录只读（可执行 + 读文件 + 读元数据）
    for p in _MACOS_SYSTEM_RO_PATHS:
        lines.append(f'(allow file-read* file-read-metadata (subpath "{p}"))')
    # workspace：readonly 只读 / default 读写
    ws = workspace.replace('\\', '/')
    if permission == PERM_READONLY:
        lines.append(f'(allow file-read* file-read-metadata (subpath "{ws}"))')
    else:
        # default：workspace 全权限读写
        lines.append(f'(allow file* (subpath "{ws}"))')
        # tmp 目录也放行（子进程常需要临时文件）
        t = str(tmp_dir()).replace('\\', '/')
        lines.append(f'(allow file* (subpath "{t}"))')
    return '\n'.join(lines)


def _run_macos_seatbelt(command: str, permission_level: str,
                         work: Path, env: dict, secs: int) -> dict:
    """macOS 上通过 sandbox-exec 施加 Seatbelt 路径隔离。

    成功时 isolation='seatbelt'；sandbox-exec 不可用或执行失败时
    降级为 rlimit+chdir（isolation='rlimit-only'）。
    """
    plat = platform.system().lower()
    ws = str(work)

    if not _seatbelt_available():
        logger.info('sandbox: sandbox-exec 不可用，降级为 rlimit-only')
        # 降级：preexec_fn 在 macOS 上仍然可用（POSIX），走 rlimit+chdir
        preexec = _build_preexec(ws, permission_level, False)
        try:
            cp = subprocess.run(
                command, shell=True, cwd=ws, env=env,
                preexec_fn=preexec,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=secs,
            )
            return {
                'ok': cp.returncode == 0,
                'code': cp.returncode,
                'stdout': (cp.stdout or '')[:20000],
                'stderr': (cp.stderr or '')[:8000],
                'cwd': ws,
                'isolation': 'rlimit-only',
                'permission': permission_level,
                'platform': plat,
            }
        except subprocess.TimeoutExpired:
            return {'ok': False, 'error': f'命令超时（>{secs}s），已终止',
                    'isolation': 'rlimit-only', 'permission': permission_level,
                    'platform': plat}
        except Exception as e:                 # noqa: BLE001
            return {'ok': False, 'error': f'{type(e).__name__}: {e}',
                    'isolation': 'rlimit-only', 'permission': permission_level,
                    'platform': plat}

    # 生成临时 .sb 文件
    sb_path = None
    try:
        import tempfile
        profile = _build_seatbelt_profile(ws, permission_level)
        fd, sb_path = tempfile.mkstemp(suffix='.sb', prefix='xl_sb_')
        try:
            os.write(fd, profile.encode('utf-8'))
        finally:
            os.close(fd)

        # sandbox-exec -f <profile> <command>
        full_cmd = f'sandbox-exec -f {sb_path} {command}'
        preexec = _build_preexec(ws, permission_level, False)
        try:
            cp = subprocess.run(
                full_cmd, shell=True, cwd=ws, env=env,
                preexec_fn=preexec,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=secs,
            )
            return {
                'ok': cp.returncode == 0,
                'code': cp.returncode,
                'stdout': (cp.stdout or '')[:20000],
                'stderr': (cp.stderr or '')[:8000],
                'cwd': ws,
                'isolation': 'seatbelt',
                'permission': permission_level,
                'platform': plat,
            }
        except subprocess.TimeoutExpired:
            return {'ok': False, 'error': f'命令超时（>{secs}s），已终止',
                    'isolation': 'seatbelt', 'permission': permission_level,
                    'platform': plat}
    except Exception as e:                     # noqa: BLE001
        logger.warning('sandbox: seatbelt 执行异常 (%s)，降级为 rlimit-only', e)
        # 发生异常时降级
        preexec = _build_preexec(ws, permission_level, False)
        try:
            cp = subprocess.run(
                command, shell=True, cwd=ws, env=env,
                preexec_fn=preexec,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=secs,
            )
            return {
                'ok': cp.returncode == 0,
                'code': cp.returncode,
                'stdout': (cp.stdout or '')[:20000],
                'stderr': (cp.stderr or '')[:8000],
                'cwd': ws,
                'isolation': 'rlimit-only',
                'permission': permission_level,
                'platform': plat,
            }
        except Exception as e2:               # noqa: BLE001
            return {'ok': False, 'error': f'{type(e2).__name__}: {e2}',
                    'isolation': 'rlimit-only', 'permission': permission_level,
                    'platform': plat}
    finally:
        # 清理临时 .sb 文件
        if sb_path:
            try:
                os.unlink(sb_path)
            except Exception:                 # noqa: BLE001
                pass


# ---- Windows Job Object ----
def _jobobject_available() -> bool:
    """探测 Windows Job Object 是否可用（仅 Windows）。"""
    if platform.system() != 'Windows':
        return False
    try:
        k32 = ctypes.windll.kernel32
        h = k32.CreateJobObjectW(None, None)
        if not h:
            return False
        k32.CloseHandle(h)
        return True
    except Exception:                           # noqa: BLE001
        return False


def _run_windows_job(command: str, permission_level: str,
                     work: Path, env: dict, secs: int) -> dict:
    """Windows 上通过 Job Object 限制 CPU 时间、内存、进程数。

    路径隔离：Windows 无原生路径沙箱，使用 cwd + 路径白名单做 best-effort。
    Job Object 不可用时降级为纯 subprocess + timeout。
    """
    plat = platform.system().lower()
    ws = str(work)
    _cmd, _shell, _shell_kind = _posix_run_args(command, platform.system())

    # Job Object 不可用 -> 降级 subprocess
    if not _jobobject_available():
        logger.info('sandbox: Windows Job Object 不可用，降级为 subprocess')
        try:
            cp = subprocess.run(
                _cmd, shell=_shell, cwd=ws, env=env,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=secs,
            )
            return {
                'ok': cp.returncode == 0,
                'code': cp.returncode,
                'stdout': (cp.stdout or '')[:20000],
                'stderr': (cp.stderr or '')[:8000],
                'cwd': ws,
                'isolation': 'subprocess',
                'permission': permission_level,
                'platform': plat,
                'shell': _shell_kind,
            }
        except subprocess.TimeoutExpired:
            return {'ok': False, 'error': f'命令超时（>{secs}s），已终止',
                    'isolation': 'subprocess', 'permission': permission_level,
                    'platform': plat}
        except Exception as e:                 # noqa: BLE001
            return {'ok': False, 'error': f'{type(e).__name__}: {e}',
                    'isolation': 'subprocess', 'permission': permission_level,
                    'platform': plat}

    # ---- Job Object 可用：创建 job + 设限制 + assign ----
    try:
        k32 = ctypes.windll.kernel32

        # 常量
        JobObjectExtendedLimitInformation = 9
        JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
        JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('PerProcessUserTimeLimit', ctypes.c_int64),
                ('PerJobUserTimeLimit', ctypes.c_int64),
                ('LimitFlags', ctypes.c_uint32),
                ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', ctypes.c_uint32),
                ('Affinity', ctypes.c_void_p),
                ('PriorityClass', ctypes.c_uint32),
                ('SchedulingClass', ctypes.c_uint32),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ('ReadOperationCount', ctypes.c_uint64),
                ('WriteOperationCount', ctypes.c_uint64),
                ('OtherOperationCount', ctypes.c_uint64),
                ('ReadTransferCount', ctypes.c_uint64),
                ('WriteTransferCount', ctypes.c_uint64),
                ('OtherTransferCount', ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ('IoInfo', IO_COUNTERS),
                ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t),
                ('PeakJobMemoryUsed', ctypes.c_size_t),
            ]

        h_job = k32.CreateJobObjectW(None, None)
        if not h_job:
            raise OSError('CreateJobObjectW failed')

        # 设置限制
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_PROCESS_TIME |
            JOB_OBJECT_LIMIT_PROCESS_MEMORY |
            JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        # CPU 时间：单位 100ns，设为 secs * 10^7 * 100
        info.BasicLimitInformation.PerProcessUserTimeLimit = int(secs * 1e7)
        # 内存上限：512MB
        info.ProcessMemoryLimit = 512 * 1024 * 1024
        # 活跃进程数上限。走 bash 时一条 `a | b | c` 会 fork 出 bash + 每个
        # 管道成员，旧值 8 会把正常命令误杀；放宽到 64 —— 仍能挡住 fork 炸弹，
        # 又不会误伤带管道的常规命令。
        info.BasicLimitInformation.ActiveProcessLimit = 64

        ret = k32.SetInformationJobObject(
            h_job, JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info))
        if not ret:
            raise OSError('SetInformationJobObject failed')

        # 启动子进程（走 bash 时 _cmd 已是 [bash, '-c', cmd]，shell=False）
        popen = subprocess.Popen(
            _cmd, shell=_shell, cwd=ws, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
        )

        # 分配到 Job Object
        try:
            # Popen._handle 在 Windows 上是进程句柄
            h_proc = int(popen._handle)
            k32.AssignProcessToJobObject(h_job, h_proc)
        except Exception:                     # noqa: BLE001
            logger.warning('sandbox: AssignProcessToJobObject 失败，进程无 job 限制')

        try:
            stdout, stderr = popen.communicate(timeout=secs)
            return {
                'ok': popen.returncode == 0,
                'code': popen.returncode,
                'stdout': (stdout or '')[:20000],
                'stderr': (stderr or '')[:8000],
                'cwd': ws,
                'isolation': 'job-object',
                'permission': permission_level,
                'platform': plat,
                'shell': _shell_kind,
            }
        except subprocess.TimeoutExpired:
            popen.kill()
            popen.communicate()
            return {'ok': False, 'error': f'命令超时（>{secs}s），已终止',
                    'isolation': 'job-object', 'permission': permission_level,
                    'platform': plat}
    except Exception as e:                     # noqa: BLE001
        logger.warning('sandbox: Job Object 执行异常 (%s)，降级为 subprocess', e)
        # 降级
        try:
            cp = subprocess.run(
                _cmd, shell=_shell, cwd=ws, env=env,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=secs,
            )
            return {
                'ok': cp.returncode == 0,
                'code': cp.returncode,
                'stdout': (cp.stdout or '')[:20000],
                'stderr': (cp.stderr or '')[:8000],
                'cwd': ws,
                'isolation': 'subprocess',
                'permission': permission_level,
                'platform': plat,
            }
        except Exception as e2:               # noqa: BLE001
            return {'ok': False, 'error': f'{type(e2).__name__}: {e2}',
                    'isolation': 'subprocess', 'permission': permission_level,
                    'platform': plat}
    finally:
        try:
            if 'h_job' in dir():
                k32.CloseHandle(h_job)
        except Exception:                     # noqa: BLE001
            pass


# ---- 命令执行：跨平台 shell 选择 ----
# 根因：subprocess.run(cmd, shell=True) 在 Windows 上走的是 cmd.exe，而
# cmd.exe 没有 ls/cat/pwd/grep 这些 POSIX 命令（对应的是 dir/type/...）。
# Agent 与沙箱里跑的几乎全是 POSIX 风格命令，用户在 Windows 上实测就是
# 「ls 等基础命令都用不了」。修法：Windows 上优先找 Git for Windows 自带的
# bash.exe（装了 Git 基本就有），用它解释 POSIX 命令；找不到再退回 cmd.exe，
# 并在返回体里如实标注用的是哪个 shell，绝不假装 ls 能跑。
_WIN_BASH_CANDIDATES = (
    # 常见安装位置；shutil.which 命中不了时再逐个探。
    r'C:\Program Files\Git\bin\bash.exe',
    r'C:\Program Files (x86)\Git\bin\bash.exe',
    r'C:\Program Files\Git\usr\bin\bash.exe',
)
_win_bash_cache: str | None = None
_win_bash_resolved = False


def _find_windows_bash() -> str | None:
    """定位一个可用的 POSIX shell（bash.exe）。结果缓存，只探一次。"""
    global _win_bash_cache, _win_bash_resolved
    if _win_bash_resolved:
        return _win_bash_cache
    _win_bash_resolved = True
    found = shutil.which('bash')
    if not found:
        for cand in _WIN_BASH_CANDIDATES:
            if os.path.isfile(cand):
                found = cand
                break
    _win_bash_cache = found
    if found:
        logger.info('sandbox: Windows 使用 POSIX shell 解释命令：%s', found)
    else:
        logger.warning('sandbox: Windows 未找到 bash.exe，退回 cmd.exe —— '
                       'ls/cat/pwd 等 POSIX 命令将不可用（这是真实限制，不是 bug）。'
                       '装 Git for Windows 即可让基础命令可用。')
    return found


def _posix_run_args(cmd: str, plat: str) -> tuple:
    """返回 (command, shell, shell_kind) —— 让 POSIX 命令在 Windows 上也能跑。

    - POSIX（Linux/Darwin/其他）：``(cmd, True, 'sh')`` —— 默认 /bin/sh。
    - Windows 且有 bash：``([bash, '-c', cmd], False, 'bash')``。
    - Windows 且无 bash：``(cmd, True, 'cmd')`` —— 只能 cmd.exe，ls/cat/pwd
      会失败；返回体里带 shell 字段如实说明用的哪个解释器，绝不假装能跑。
    """
    if plat == 'Windows':
        bash = _find_windows_bash()
        if bash:
            return [bash, '-c', cmd], False, 'bash'
        return cmd, True, 'cmd'
    return cmd, True, 'sh'


# ---- 平台检测 ----
def get_platform_isolation() -> str:
    """返回当前平台推荐使用的隔离类型。

    返回值之一：
      - ``"landlock"``      : Linux + Landlock 可用
      - ``"rlimit+chdir"``  : Linux 但 Landlock 不可用
      - ``"seatbelt"``      : macOS + sandbox-exec 可用
      - ``"rlimit-only"``   : macOS 但 sandbox-exec 不可用
      - ``"job-object"``    : Windows + Job Object 可用
      - ``"subprocess"``    : Windows 但 Job Object 不可用
      - ``"unknown"``       : 其他平台
    """
    plat = platform.system()
    try:
        if plat == 'Linux':
            return 'landlock' if _landlock_supported() else 'rlimit+chdir'
        if plat == 'Darwin':
            return 'seatbelt' if _seatbelt_available() else 'rlimit-only'
        if plat == 'Windows':
            return 'job-object' if _jobobject_available() else 'subprocess'
    except Exception:                           # noqa: BLE001
        pass
    return 'unknown'


# ---------------------------------------------------------------- 执行
def run_sandboxed(command: str,
                  permission_level: str = PERM_DEFAULT,
                  cwd: str | None = None,
                  timeout: int | None = None) -> dict:
    """在沙箱内执行命令，带 OS 级进程隔离。

    按平台自动选择隔离方式：
      - Linux   -> Landlock（降级 rlimit+chdir）
      - macOS   -> Seatbelt（降级 rlimit-only）
      - Windows -> Job Object（降级 subprocess）
      - 其他    -> rlimit+chdir

    Parameters
    ----------
    command : str
        要执行的 shell 命令。
    permission_level : str
        ``"readonly"`` / ``"default"`` / ``"full"`` 三档：
        - readonly : 仅可读 workspace 与系统库，禁止写/建/删
        - default  : 可读写 workspace，可执行非网络命令
        - full     : 完全访问（跳过 OS 隔离；按红线需用户另行确认）
    cwd, timeout : 同旧 :func:`run`。

    Returns
    -------
    dict
        与旧 run 相同的字段（ok/code/stdout/stderr/cwd），并额外带：
        ``isolation``（本次实际使用的隔离级别）、``permission``、
        ``platform``（当前操作系统）。
    """
    ensure()
    cmd = (command or '').strip()
    if not cmd:
        return {'ok': False, 'error': '命令为空'}

    if permission_level not in PERMISSION_LEVELS:
        permission_level = PERM_DEFAULT

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
    plat = platform.system()
    plat_lower = plat.lower()

    # ---- 词法路径守卫：仅在真实 OS 路径隔离缺席时启用 ----
    # Landlock / Seatbelt 由内核或 sandbox-exec 强制，不需要这层；
    # 其余情况（Linux 无 Landlock、macOS 无 sandbox-exec、Windows 的
    # Job Object 只管资源不管路径、未知平台）只有 chdir，`../../` 照样
    # 能读穿到 /etc/passwd —— 实测过，不是理论风险。
    # 这层挡的是误操作和简单逃逸，**不是安全边界**，返回体里如实标 guard。
    if permission_level != PERM_FULL:
        _iso = get_platform_isolation()
        _real_path_iso = _iso in ('landlock', 'seatbelt')
        if not _real_path_iso:
            chk = lexical_escape_check(cmd, str(work), permission_level)
            if not chk['ok']:
                return {
                    'ok': False,
                    'error': ('路径逃逸被拒绝（词法守卫）：'
                              + '、'.join(chk['offending'])
                              + '。当前平台无 OS 级路径隔离（'
                              + _iso + '），工作目录之外的读写已被拦下。'),
                    'stdout': '',
                    'stderr': '',
                    'code': -1,
                    'cwd': str(work),
                    'isolation': _iso,
                    'permission': permission_level,
                    'platform': plat_lower,
                    'guard': 'lexical',
                    'note': chk['note'],
                }

    env = dict(os.environ)
    env['XIAOLING_SANDBOX'] = '1'
    if permission_level in (PERM_READONLY, PERM_DEFAULT):
        env['no_proxy'] = '*'
        env['NO_PROXY'] = '*'

    # ---- full 权限：不做任何 OS 隔离 ----
    if permission_level == PERM_FULL:
        _cmd, _shell, _shell_kind = _posix_run_args(cmd, plat)
        try:
            cp = subprocess.run(
                _cmd, shell=_shell, cwd=str(work), env=env,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=secs,
            )
            return {
                'ok': cp.returncode == 0,
                'code': cp.returncode,
                'stdout': (cp.stdout or '')[:20000],
                'stderr': (cp.stderr or '')[:8000],
                'cwd': str(work),
                'isolation': 'unrestricted',
                'permission': permission_level,
                'platform': plat_lower,
                'shell': _shell_kind,
            }
        except subprocess.TimeoutExpired:
            return {'ok': False, 'error': f'命令超时（>{secs}s），已终止',
                    'isolation': 'unrestricted', 'permission': permission_level,
                    'platform': plat_lower}
        except Exception as e:                 # noqa: BLE001
            return {'ok': False, 'error': f'{type(e).__name__}: {e}',
                    'isolation': 'unrestricted', 'permission': permission_level,
                    'platform': plat_lower}

    # ---- 按平台路由 ----
    if plat == 'Linux':
        # Landlock 路径（与原实现一致）
        landlock_on = _landlock_supported()
        isolation = 'landlock' if landlock_on else 'rlimit+chdir'
        if not landlock_on:
            logger.warning('sandbox: Linux 但 Landlock 不可用，降级为 '
                           'rlimit+chdir（非完整路径隔离）')
        preexec = _build_preexec(str(work), permission_level, landlock_on)
        try:
            cp = subprocess.run(
                cmd, shell=True, cwd=str(work), env=env,
                preexec_fn=preexec,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=secs,
            )
            return {
                'ok': cp.returncode == 0,
                'code': cp.returncode,
                'stdout': (cp.stdout or '')[:20000],
                'stderr': (cp.stderr or '')[:8000],
                'cwd': str(work),
                'isolation': isolation,
                'permission': permission_level,
                'platform': plat_lower,
            }
        except subprocess.TimeoutExpired:
            return {'ok': False, 'error': f'命令超时（>{secs}s），已终止',
                    'isolation': isolation, 'permission': permission_level,
                    'platform': plat_lower}
        except Exception as e:                 # noqa: BLE001
            return {'ok': False, 'error': f'{type(e).__name__}: {e}',
                    'isolation': isolation, 'permission': permission_level,
                    'platform': plat_lower}

    elif plat == 'Darwin':
        return _run_macos_seatbelt(cmd, permission_level, work, env, secs)

    elif plat == 'Windows':
        return _run_windows_job(cmd, permission_level, work, env, secs)

    else:
        # 其他平台：纯 rlimit + chdir 或 subprocess
        logger.warning('sandbox: 未知平台 %s，使用 rlimit+chdir', plat)
        preexec = _build_preexec(str(work), permission_level, False)
        try:
            cp = subprocess.run(
                cmd, shell=True, cwd=str(work), env=env,
                preexec_fn=preexec,
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=secs,
            )
            return {
                'ok': cp.returncode == 0,
                'code': cp.returncode,
                'stdout': (cp.stdout or '')[:20000],
                'stderr': (cp.stderr or '')[:8000],
                'cwd': str(work),
                'isolation': 'rlimit+chdir',
                'permission': permission_level,
                'platform': plat_lower,
            }
        except Exception as e:                 # noqa: BLE001
            return {'ok': False, 'error': f'{type(e).__name__}: {e}',
                    'isolation': 'rlimit+chdir', 'permission': permission_level,
                    'platform': plat_lower}


def run(command: str, timeout: int | None = None, cwd: str | None = None) -> dict:
    """在沙箱内执行一条命令（向后兼容入口）。

    与历史版本签名完全一致：内部以 ``"default"`` 权限调用
    :func:`run_sandboxed`。新代码请直接用 :func:`run_sandboxed` 并显式指定
    permission_level。

    * cwd 固定为 workspace/（除非显式给出且通过白名单）
    * 命令黑名单 + 超时是提示性闸门，真正的隔离靠 Landlock / rlimit
    * **不提供任何删除能力**（项目红线）
    """
    return run_sandboxed(command, permission_level=PERM_DEFAULT,
                         cwd=cwd, timeout=timeout)


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


def capability() -> dict:
    """返回当前平台的真实隔离能力（只读，供前端展示「本机沙箱级别」）。

    与 get_platform_isolation() 不同，本函数返回更完整的能力矩阵，
    包括路径隔离、资源限制、超时控制等维度，供前端如实展示。

    返回字段：
        platform            : str   当前平台 'linux'/'darwin'/'windows'/'unknown'
        isolation_level     : str   隔离级别（同 get_platform_isolation）
        path_isolation      : bool  是否有路径级强制隔离（Landlock/Seatbelt）
        resource_limits     : bool  是否可设置
        timeout_enforcement : bool  是否强制超时
        workspace_guard     : bool  是否有 workspace 路径白名单
        lexical_guard       : bool  降级时是否启用词法路径守卫（**不是安全边界**）
        notes               : str   补充说明（降级原因等）
    """
    plat = platform.system().lower()
    iso = get_platform_isolation()

    # 按平台填充能力矩阵
    if plat == 'linux':
        path_iso = (iso == 'landlock')
        res_lim = True
        notes = '' if path_iso else 'Landlock 不可用，降级为 rlimit+chdir（非完整路径隔离）'
    elif plat == 'darwin':
        path_iso = (iso == 'seatbelt')
        res_lim = True
        notes = '' if path_iso else 'sandbox-exec 不可用，降级为 rlimit-only'
    elif plat == 'windows':
        path_iso = False  # Windows Job Object 不做路径隔离
        res_lim = (iso == 'job-object')
        notes = '' if res_lim else 'Job Object 不可用，降级为 subprocess'
    else:
        path_iso = False
        res_lim = False
        notes = f'未知平台 {plat}，无原生隔离机制'

    return {
        'platform': plat,
        'isolation_level': iso,
        'path_isolation': path_iso,
        'resource_limits': res_lim,
        'timeout_enforcement': True,
        'workspace_guard': True,
        # 词法守卫只在真实隔离缺席时生效。它挡误操作、不挡刻意绕过，
        # 所以绝不因为它把 path_isolation 翻成 True。
        'lexical_guard': bool((not path_iso) and iso != 'unrestricted'),
        'notes': notes,
    }


if __name__ == '__main__':      # 手动巡检：python -m backend.core.sandbox
    import json
    print(json.dumps(status(), ensure_ascii=False, indent=2))
