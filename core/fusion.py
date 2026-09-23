#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小凌 · 融合层（把 core.* 能力注入 xl.py 主引擎）
==================================================

`install(globals())` 在 xl.py 末尾调用，负责：

  1. 用 `core.config` 的统一配置覆盖/补全 xl.py 的 CONFIG
  2. 把 `speak()` 接到 3D 数字人（口型 + 语音 + 气泡）
  3. 把桌宠启动换成 **3D VRM 数字人**（失败自动回退 2D 视频桌宠）
  4. 给 XiaoLing 挂上：RAG 检索 / 成长引擎 / 主动搭话 / 视觉 / 搜索 / 提醒 / 生图 / 文件箱
  5. 拦截并处理融合后的新指令（换装、跳舞、看屏幕、生图、成长进度…）
  6. 每轮蒸馏训练后自动跑一次"适配器体积检查 → 合并 → 晋升"

设计原则：**不修改 xl.py 原有逻辑**，只做外层包装（wrapper），保证老功能零回归。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from core import config as config_mod

BASE_DIR = Path(__file__).resolve().parent.parent

_STATE = {
    'installed': False,
    'avatar': None,
    'avatar_thread': None,
    'cfg': None,
    'gui_mode': False,          # 是否由 3D 窗口接管主线程
    'progress': '',             # 下载/初始化进度文本（供桌宠气泡显示）
}


def _log(msg):
    try:
        print(f'  [融合] {msg}')
    except Exception:                                                 # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
#  1. 统一配置
# --------------------------------------------------------------------------- #
def _merge_config(g):
    cfg = config_mod.load()
    _STATE['cfg'] = cfg
    target = g.get('CONFIG')
    if isinstance(target, dict):
        for k, v in cfg.items():
            if isinstance(v, dict) and isinstance(target.get(k), dict):
                merged = dict(v)
                merged.update(target[k])          # 保留用户在 xl.py 顶部的显式设置
                target[k] = merged
            else:
                target.setdefault(k, v)
    return cfg


# --------------------------------------------------------------------------- #
#  2. 数字人
# --------------------------------------------------------------------------- #
def _make_avatar(engine):
    try:
        from core.avatar import AvatarHost
    except Exception as e:                                            # noqa: BLE001
        _log(f'数字人模块不可用：{e}')
        return None
    cfg = (_STATE.get('cfg') or config_mod.load()).get('avatar', {})
    if not cfg.get('enabled', True):
        return None
    model = BASE_DIR / '角色模型' / cfg.get('model', '小凌.vrm')
    host = AvatarHost(engine=engine, model=model if model.exists() else None,
                      scale=cfg.get('scale', 1.0), focus=cfg.get('focus', 'bust'),
                      log=_log)
    return host


def ensure_avatar(engine):
    """创建 3D 数字人宿主（不开窗）。窗口必须由主线程打开，见 start_avatar。"""
    if _STATE.get('avatar'):
        return _STATE['avatar']
    host = _make_avatar(engine)
    _STATE['avatar'] = host
    return host


def start_avatar(engine, block=True):
    """启动 3D 数字人窗口。

    重要：Qt 的窗口与事件循环**必须在主线程**运行（后台线程开窗会崩/白屏）。
    因此这里默认阻塞调用方（主线程），把引擎的后台服务放到别的线程去。
    """
    host = ensure_avatar(engine)
    if host is None:
        return None
    if block:
        try:
            ok = host.start(block=True)          # 主线程：窗口 + 事件循环
            if not ok:
                _STATE['progress'] = ''
                return None
            return host
        except Exception as e:                                        # noqa: BLE001
            _log(f'数字人启动异常：{e}')
            return None
    # 非阻塞：仅创建，不显示（兼容旧调用方）
    return host


def set_progress(text):
    """写入进度文本（下载/初始化），由桌宠窗口轮询显示为气泡。"""
    _STATE['progress'] = text or ''
    host = _STATE.get('avatar')
    if host is not None:
        try:
            host.status_text = text or ''
        except Exception:                                             # noqa: BLE001
            pass


def get_progress():
    return _STATE.get('progress', '')


def _avatar_say(text, emotion=None):
    host = _STATE.get('avatar')
    if not host:
        return False
    try:
        return host.say(text, emotion=emotion)
    except Exception:                                                 # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
#  2.5 启动引导：GUI 模式下把"档位选择 + 基底下载"变成后台任务 + 桌宠进度
# --------------------------------------------------------------------------- #
def gui_requested(argv=None):
    """是否需要 3D 桌宠（决定窗口要不要接管主线程、要不要跳过控制台交互）。"""
    argv = list(argv if argv is not None else sys.argv[1:])
    if '--no-pet' in argv or '--avatar-only' in argv:
        return '--avatar-only' in argv
    if os.environ.get('XIAOLING_NO_AVATAR'):
        return False
    try:
        cfg = config_mod.load()
    except Exception:                                                 # noqa: BLE001
        return True
    return bool(cfg.get('avatar', {}).get('enabled', True))


def _dir_mb(path, limit=200):
    """统计目录体积（MB）——只扫指定目录，避免拖慢进度线程。"""
    total, seen = 0, 0
    try:
        for p in Path(path).rglob('*'):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
                seen += 1
                if seen >= limit:
                    break
    except Exception:                                                 # noqa: BLE001
        pass
    return total / 1024 / 1024


def _downloaded_mb():
    """已获取的基底模型体积（只看 xl.py 真实使用的两个目录，秒级完成）。"""
    import tempfile
    return (_dir_mb(Path(tempfile.gettempdir()) / 'xl_model_dl')
            + _dir_mb(BASE_DIR / '.star_core' / 'XLmodel'))


def bootstrap(select_model_on_start, ensure_base_model=None):
    """在 main() 之前调用（xl.py 的 __main__ 里）。

    · 命令行模式：保持原行为——交互式档位选择 + 控制台下载进度。
    · GUI 模式：跳过交互（档位取配置，可在设置里改），基底缺失就后台下载，
      并把进度写进 `set_progress()` → 桌宠窗口轮询后以气泡显示。
    返回 True 表示已在后台接管模型准备流程。
    """
    if not gui_requested():
        select_model_on_start()
        return False
    model_dir = BASE_DIR / '.star_core' / 'XLmodel'
    try:
        ready = any(p.is_file() and p.stat().st_size > 10 * 1024 * 1024
                    for p in model_dir.glob('*'))
    except Exception:                                                 # noqa: BLE001
        ready = False
    if ready or ensure_base_model is None:
        if ready:
            print('  [模型] 基底权重已就绪（GUI 模式：跳过控制台档位选择）')
        else:
            select_model_on_start()
        return False
    print('  [模型] 未检测到基底权重 → 后台下载中，进度会同步出现在桌宠气泡里')

    def _worker():
        stop = threading.Event()

        def _poll():
            while not stop.is_set():
                set_progress(f'正在下载基底模型… 已获取 {_downloaded_mb():.0f} MB')
                stop.wait(2.0)
        threading.Thread(target=_poll, daemon=True).start()
        try:
            ensure_base_model()
            set_progress('基底模型就绪，正在唤醒小凌…')
        except Exception as e:                                        # noqa: BLE001
            set_progress(f'模型下载中断：{type(e).__name__}（可稍后重试）')
        finally:
            stop.set()

    threading.Thread(target=_worker, daemon=True, name='model-download').start()
    return True


# --------------------------------------------------------------------------- #
#  3. 指令
# --------------------------------------------------------------------------- #
HELP_TEXT = '''
【小凌融合版 · 新增指令】
  · 3D 数字人：说「变身」/「开数字人」启动 3D 形象；「换角色」切换 VRM；「换装 <基底名>」重新生成小凌形象
  · 动作表情：「跳舞」「回到待机」「全身」「半身」「开心一点」「难过一点」
  · 感知与搜索：「看屏幕」「搜索 <关键词>」「电脑状态」
  · 生活助理：「30分钟后提醒我喝水」「生图 <描述>」「整理文件夹 <路径>」
  · 成长：说「蒸馏」自动学习；说「成长进度」看适配器体积与晋升进度
  · 记忆：「记忆检索 <关键词>」
'''


def _cmd_help(_app, _arg):
    return HELP_TEXT.strip()


def _cmd_avatar(app, _arg):
    host = start_avatar(app)
    if not host:
        return '数字人未启用：在 .star_core/xiaoling_config.json 里把 avatar.enabled 设为 true'
    return f'3D 数字人已启动（模型：{host.model_path.name}，渲染层：{host.backend or "启动中"}）'


def _cmd_next_model(app, _arg):
    host = _STATE.get('avatar')
    if not host:
        return '数字人还没启动，先说「变身」'
    host.next_model()
    return '换好啦～'


def _cmd_dress(app, arg):
    """用形象流水线重新生成小凌（换基底模型 = 换装）。"""
    arg = (arg or '').strip()
    models = sorted((BASE_DIR / '角色模型').glob('*.vrm'))
    base = None
    if arg:
        for m in models:
            if arg in m.name:
                base = m
                break
    if base is None:
        base = BASE_DIR / '角色模型' / 'Rabbit_Peridot.vrm'
    if not base.exists():
        return f'找不到基底模型：{base}'
    face = BASE_DIR / '素材' / 'xiaoling.png'
    out = BASE_DIR / '角色模型' / '小凌.vrm'
    script = BASE_DIR / '工具' / 'xiaoling_avatar.py'
    cmd = [sys.executable, str(script), 'build', '--base', str(base), '--face', str(face),
           '--out', str(out), '--preview', str(BASE_DIR / 'preview')]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        _log(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '形象生成完成')
    except Exception as e:                                            # noqa: BLE001
        return f'换装失败：{e}'
    host = _STATE.get('avatar')
    if host:
        try:
            host.switch_model(str(out))
        except Exception as e:                                        # noqa: BLE001
            _log(f'换装后切换形象失败：{e}')
    return f'换装完成：小凌的新形象已生成（基底 {base.name}）'


def _cmd_dance(app, _arg):
    host = _STATE.get('avatar')
    if host and host.dance():
        return '好呀，看我的～'
    return '（数字人未启动，先说「变身」）'


def _cmd_focus(app, arg):
    host = _STATE.get('avatar')
    mode = 'full' if ('全' in (arg or '') or 'full' in (arg or '').lower()) else 'bust'
    if host:
        host.emit('focus', mode=mode)
    return '全身视角' if mode == 'full' else '半身视角'


def _cmd_emotion(app, arg):
    host = _STATE.get('avatar')
    name = arg or 'happy'
    if host:
        host.emit('mood', mood=name)
    return f'好，{name}'


def _cmd_screen(app, arg):
    try:
        from core import vision
        return vision.look_at_screen(arg or '帮我看看屏幕，说说我在做什么、需要注意什么')
    except Exception as e:                                            # noqa: BLE001
        return f'看屏幕失败：{e}'


def _cmd_search(app, arg):
    try:
        from core import search
        res = search.answer_with_search(arg)
        if not res['results']:
            return f'没搜到「{arg}」（可能没网）'
        lines = [f"· {r['title']}  {r['url']}" for r in res['results'][:4]]
        return f'关于「{arg}」我搜到这些：\n' + '\n'.join(lines)
    except Exception as e:                                            # noqa: BLE001
        return f'搜索失败：{e}'


def _cmd_pc(app, _arg):
    try:
        from core import perception
        return perception.describe()
    except Exception as e:                                            # noqa: BLE001
        return f'感知失败：{e}'


def _cmd_remind(app, arg):
    try:
        from core import reminder
        item = reminder.add(arg, notify=lambda m: (_avatar_say(m, 'happy'), print(f'[提醒] {m}')))
        if not item:
            return '没听懂时间，试试「30分钟后提醒我喝水」'
        host = _STATE.get('avatar')
        if host:
            host.emit('action', url=None, loop=False)
        return f"好，{item['at']} 我会提醒你：{item['text']}"
    except Exception as e:                                            # noqa: BLE001
        return f'设置提醒失败：{e}'


def _cmd_imagen(app, arg):
    try:
        from core import imagen
        p = imagen.generate(arg)
        if not p:
            return '生图需要配置 API（设置 → 生图），或指定本地管线命令'
        imagen.open_image(p)
        return f'画好啦：{p}'
    except Exception as e:                                            # noqa: BLE001
        return f'生图失败：{e}'


def _cmd_filebox(app, arg):
    try:
        from core import filebox
        target = (arg or '.').strip() or '.'
        if not Path(target).exists():
            return f'路径不存在：{target}'
        rep = filebox.scan(target)
        return (f"扫描完成：{rep['files']} 个文件 / {rep['bytes_human']}，"
                f"重复文件 {rep['duplicate_groups']} 组。"
                f"（执行整理：说「整理文件夹 {target} 执行」）")
    except Exception as e:                                            # noqa: BLE001
        return f'扫描失败：{e}'


def _cmd_growth(app, _arg=None):
    eng = getattr(app, 'growth_engine', None)
    if eng:
        return eng.report()
    try:
        from core.growth import GrowthEngine
        return GrowthEngine().report()
    except Exception as e:                                            # noqa: BLE001
        return f'成长引擎不可用：{e}'


def _cmd_rag(app, arg):
    rag = getattr(app, 'rag', None)
    if not rag:
        return 'RAG 未启用'
    hits = rag.search(arg or '', k=5)
    if not hits:
        return '记忆里没找到相关内容'
    return '记忆检索结果：\n' + '\n'.join(f"· [{h['score']}] {h['text'][:80]}" for h in hits)


COMMANDS = [
    (('变身', '开数字人', '启动数字人', '打开数字人'), _cmd_avatar),
    (('换角色', '换个角色', '下一个角色'), _cmd_next_model),
    (('换装', '换衣服', '换形象'), _cmd_dress),
    (('跳舞', '跳个舞', '来一段'), _cmd_dance),
    (('全身', '半身'), _cmd_focus),
    (('开心一点', '高兴一点', '难过一点', '生气一点'), _cmd_emotion),
    (('看屏幕', '看看屏幕', '帮我看看屏幕', '看看我的屏幕'), _cmd_screen),
    (('搜索', '搜一下', '查一下'), _cmd_search),
    (('电脑状态', '我在干什么', '我在做什么'), _cmd_pc),
    (('提醒我', '提醒一下'), _cmd_remind),
    (('生图', '画一张', '画个'), _cmd_imagen),
    (('整理文件夹', '扫描文件夹'), _cmd_filebox),
    (('成长进度', '成长报告'), _cmd_growth),
    (('记忆检索', '找找记忆'), _cmd_rag),
    (('融合帮助', '新功能', '指令帮助'), _cmd_help),
]


def try_command(app, text):
    """返回处理结果字符串；未命中返回 None。"""
    t = (text or '').strip()
    if not t:
        return None
    for keys, fn in COMMANDS:
        for k in keys:
            if t.startswith(k) or (len(t) <= 8 and k in t):
                arg = re_strip(t, k)
                try:
                    return fn(app, arg)
                except Exception as e:                                # noqa: BLE001
                    return f'指令执行失败：{e}'
    return None


def re_strip(text, key):
    import re
    return re.sub(re.escape(key), '', text, count=1).strip(' ：:，,')


# --------------------------------------------------------------------------- #
#  4. 安装（包装 xl.py 的类与函数）
# --------------------------------------------------------------------------- #
def install(g):
    if _STATE['installed']:
        return
    _STATE['installed'] = True
    try:                                  # 打包后首次运行：准备可写目录 + 拷贝种子语料
        from core.paths import ensure_seed_dirs, is_frozen
        if is_frozen():
            info = ensure_seed_dirs()
            if info['created'] or info['seeded']:
                _log(f"已准备数据目录（新建 {len(info['created'])} 个 / 种子 {info['seeded']}）")
    except Exception as e:                                            # noqa: BLE001
        _log(f'数据目录准备跳过（{e}）')
    cfg = _merge_config(g)
    _log(f"统一配置已接管（版本 {cfg.get('version')}）")

    # ---- speak：接数字人 ----
    write_speak(g)
    # ---- 桌宠 → 3D 数字人 ----
    wrap_pet_starter(g)
    # ---- XiaoLing ----
    wrap_engine_class(g)
    # ---- 蒸馏训练后自动检查 ----
    wrap_distill(g)
    # ---- 命令行参数 ----
    wrap_main(g)
    g.setdefault('FUSION_BOOTSTRAP', bootstrap)
    _log("融合层安装完成：3D 数字人 / RAG / 视觉 / 搜索 / 提醒 / 生图 / 成长闭环 已接入")
    print(HELP_TEXT)


def write_speak(g):
    orig_speak = g.get('speak')

    def speak_fused(text, force=False):
        try:
            if text and not str(text).startswith('[['):
                _avatar_say(text)
        except Exception:                                             # noqa: BLE001
            pass
        if callable(orig_speak):
            return orig_speak(text, force)
        return None
    g['speak'] = speak_fused


def _qt_missing_reason():
    """返回 None 表示 Qt 可用；否则返回缺失原因。"""
    reason = ''
    for mod in ('PySide6', 'PyQt5'):
        try:
            __import__(mod)
            return None
        except Exception as e:                                        # noqa: BLE001
            reason = f'{type(e).__name__}: {e}'
    return reason


def wrap_pet_starter(g):
    orig = g.get('_start_pet_background')

    def _start_pet_background(app):
        """3D 桌宠：主线程开窗（Qt 要求），引擎后台服务另起线程。

        只保留 3D VRM 数字人，不再提供 2D 图片桌宠兜底。
        Qt 窗口库不可用时给出安装指引并返回 False（进入纯命令行）。
        """
        cfg = _STATE.get('cfg') or config_mod.load()
        if not cfg.get('avatar', {}).get('enabled', True) or os.environ.get('XIAOLING_NO_AVATAR'):
            return False

        # 先探测 Qt：缺了就给出可执行的安装指引（不再回退图片桌宠）
        qt_missing = _qt_missing_reason()
        if qt_missing:
            print('  [桌宠] 未检测到桌面窗口库（PySide6 / PyQt5），3D 桌宠无法开窗')
            print('  [桌宠]   请执行：pip install PySide6')
            print('  [桌宠]   装完重新运行 xl.py，小凌就会以 3D 模型出现在桌面（无图片桌宠兜底）')
            return False

        host = ensure_avatar(app)
        if host is None:
            print('  [桌宠] 3D 数字人宿主创建失败（模型/渲染层异常），未启动桌宠')
            return False
        # 引擎的后台服务（看门狗/自动更新/平台机器人/网络检测）先跑起来
        _start_engine_services(app)
        cur_model = getattr(host.renderer, 'model_path', None)
        print(f'  [桌宠] 正在打开 3D 数字人窗口（模型：{Path(str(cur_model)).name}，透明置顶）…')
        if not host.start(block=True):          # ← 主线程：窗口 + 事件循环
            print('  [桌宠] 3D 窗口启动失败（非 Qt 缺失，请检查显示器/OpenGL），未启动桌宠')
            return False
        _STATE['gui_mode'] = True
        setattr(app, '_avatar_owns_main', True)
        return True
    g['_start_pet_background'] = _start_pet_background


def _start_engine_services(app):
    """等价于原 run() 里的"后台服务启动"部分，但不进入命令行输入循环（只跑一次）。"""
    if _STATE.get('services_started'):
        return
    _STATE['services_started'] = True
    for name, call in (
            ('看门狗', lambda: app._start_watchdog()),
            ('自动更新', lambda: app.updater.auto_check_on_start()),
            ('网络检测', lambda: threading.Thread(target=app.network.check_offline,
                                                args=(app,), daemon=True).start()),
            ('平台机器人', lambda: threading.Thread(target=app.platforms.start_all,
                                                  daemon=True).start())):
        try:
            call()
        except Exception as e:                                        # noqa: BLE001
            _log(f'{name} 启动跳过（{type(e).__name__}: {e}）')


def wrap_engine_class(g):
    cls = g.get('XiaoLing')
    if cls is None:
        return
    orig_init = cls.__init__
    orig_chat = cls.chat
    orig_run = getattr(cls, 'run', None)

    def __init__(self, *a, **kw):
        orig_init(self, *a, **kw)
        try:
            from core.rag import get_rag
            self.rag = get_rag()
            hits = self.rag.stats().get('items', 0)
            print(f'  [RAG] 本地向量记忆已就绪（{hits} 条）')
        except Exception:                                             # noqa: BLE001
            self.rag = None
        try:
            from core.growth import GrowthEngine
            self.growth_engine = GrowthEngine(log=_log)
            self._save_state_before = None
            print(f'  [成长] 闭环引擎就绪：{self.growth_engine.stage_text()}')
            st = self.growth_engine.state()
            if st.get('self_research'):
                print(f"  [成长] [OK] 小凌已是第 {st.get('promotions', 1)} 代纯自研模型")
        except Exception as e:                                        # noqa: BLE001
            self.growth_engine = None
            _log(f'成长引擎不可用：{e}')
        try:
            from core.reminder import pending
            ps = pending()
            if ps:
                print(f'  [提醒] {len(ps)} 个待触发提醒')
        except Exception:                                             # noqa: BLE001
            pass
        # 创建数字人宿主（不开窗！窗口由主线程在 _start_pet_background 中打开）
        cfg = _STATE.get('cfg') or config_mod.load()
        if cfg.get('avatar', {}).get('enabled', True) and not os.environ.get('XIAOLING_NO_AVATAR'):
            host = ensure_avatar(self)
            if host is not None:
                st = host.stats()
                print(f"  [数字人] 渲染后端 {st.get('backend')}｜模型 {Path(str(st.get('path', ''))).name}"
                      f"｜动作 {len(host.list_animations())} 个")
            else:
                print('  [数字人] 宿主创建失败（将回退 2D 桌宠 / 命令行）')

    def chat(self, user_input):
        # 融合指令优先
        try:
            out = try_command(self, user_input)
        except Exception:                                             # noqa: BLE001
            out = None
        if out is not None:
            print(f'\n小凌：{out}\n')
            _avatar_say(out)
            return out
        # RAG 记忆
        if getattr(self, 'rag', None):
            try:
                self.rag.add(user_input, meta={'source': 'chat', 'user': self.user_name})
            except Exception:                                         # noqa: BLE001
                pass
        result = orig_chat(self, user_input)
        try:
            if isinstance(result, str) and result:
                if getattr(self, 'rag', None):
                    self.rag.add(result[:800], meta={'source': 'xiaoling'})
                _avatar_say(result)
        except Exception:                                             # noqa: BLE001
            pass
        return result

    def growth_report(self):
        return _cmd_growth(self)

    def proactive_line(self):
        try:
            from core.proactive import ProactiveEngine
            return ProactiveEngine(engine=self, rag=getattr(self, 'rag', None)).compose()
        except Exception:                                             # noqa: BLE001
            return '在忙吗？我在这儿呢'

    def apply_config(self, cfg):
        try:
            global_config = g.get('CONFIG')
            if isinstance(global_config, dict):
                for k, v in (cfg or {}).items():
                    global_config[k] = v
        except Exception:                                             # noqa: BLE001
            pass

    def start_avatar_ui(self):
        return start_avatar(self)

    def run(self):
        """GUI 模式下主线程被 3D 窗口占用，这里直接返回（后台服务已启动）。"""
        if getattr(self, '_avatar_owns_main', False):
            print('  [小凌] 3D 桌宠已接管主线程：双击桌宠或用右键菜单与小凌对话。')
            return
        if callable(orig_run):
            return orig_run(self)
        return None

    for name, fn in (('__init__', __init__), ('chat', chat), ('growth_report', growth_report),
                     ('proactive_line', proactive_line), ('apply_config', apply_config),
                     ('start_avatar', start_avatar_ui), ('run', run)):
        setattr(cls, name, fn)


def wrap_distill(g):
    orig_run = g.get('run_distill')
    orig_train = g.get('distill_train')

    def _after_training(app, epochs):
        eng = getattr(app, 'growth_engine', None)
        if not eng:
            return
        print('\n  [成长] 每轮训练后自动检查适配器体积 …')
        try:
            res = eng.after_training_round(epochs=epochs) if False else eng.check_and_promote()
            print('  [成长] ' + res.get('message', ''))
            pct = res.get('progress_percent')
            if pct is not None:
                print(f'  [成长] 进度：{pct:.1f}% / 基底')
            if res.get('action') == 'promoted':
                _avatar_say('我完成自我进化啦，现在的我完全属于自己了！', 'happy')
                p = getattr(app, 'avatar', None)
                if p:
                    p.dance()
        except Exception as e:                                        # noqa: BLE001
            _log(f'成长检查失败：{e}')

    def run_distill_fused(app, rounds=6, epochs=2):
        out = orig_run(app, rounds, epochs) if callable(orig_run) else None
        _after_training(app, epochs)
        return out

    if callable(orig_run):
        g['run_distill'] = run_distill_fused

    if callable(orig_train):
        def distill_train_fused(epochs=2, batch_size=2, lr=1e-4):
            res = orig_train(epochs=epochs, batch_size=batch_size, lr=lr)
            for app in (getattr(_STATE.get('avatar'), 'engine', None), g.get('_APP')):
                if app is not None:
                    _after_training(app, epochs)
                    break
            return res
        g['distill_train'] = distill_train_fused


def wrap_main(g):
    orig_main = g.get('main')

    def main_fused():
        argv = sys.argv[1:]
        if '--no-avatar' in argv:
            os.environ['XIAOLING_NO_AVATAR'] = '1'
            sys.argv = [a for a in sys.argv if a != '--no-avatar']
        if '--avatar-only' in argv:
            os.environ['XIAOLING_NO_AVATAR'] = ''
            sys.argv = [a for a in sys.argv if a != '--avatar-only']
            from core.avatar import AvatarHost
            AvatarHost().start()
            return
        if '--growth' in argv:
            sys.argv = [a for a in sys.argv if a.startswith('--growth') is False]
            from core.growth import main as growth_main
            growth_main(['report'])
            return
        if '--probe' in argv:                      # 渲染层无头自检（不开窗、不下载模型）
            from core.avatar import run_headless_probe
            print(json.dumps(run_headless_probe(), ensure_ascii=False, indent=1))
            return
        if '--showcase' in argv:                   # 离线渲染形象图
            i = argv.index('--showcase')
            outdir = sys.argv[i + 1] if len(sys.argv) > i + 1 else 'preview'
            from renderer.app import PythonAvatar
            av = PythonAvatar(log=lambda m: print(m))
            print(json.dumps(av.render_showcase(outdir), ensure_ascii=False, indent=1))
            return
        if '--selftest' in argv:                   # 全系统体检
            from core.selftest import main as selftest_main
            selftest_main([])
            return
        if callable(orig_main):
            return orig_main()
        return None
    g['main'] = main_fused


if __name__ == '__main__':
    print(HELP_TEXT)
