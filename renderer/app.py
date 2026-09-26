#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.app —— 3D 数字人宿主（与 xl.py 引擎对接，100% Python）

取代旧版"Electron 窗口 + HTML/JS 渲染层 + HTTP/IPC 桥"的三段式结构：

    旧：Python 引擎 ──HTTP──▶ WebView ──JS(three.js)──▶ 屏幕
    新：Python 引擎 ──直接方法调用──▶ renderer.AvatarRenderer ──GLSL/Qt──▶ 屏幕

窗口层（Qt）只是"显示"，渲染与表演状态全部在 Python 进程内，零 IPC、零 web 资源。
无 Qt/无桌面时：自动退化为 **无头模式**（可离线出图）或回退 2D 视频桌宠。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from core.paths import APP_DIR, resource

BASE_DIR = APP_DIR


class PythonAvatar:
    """小凌的 3D 形象宿主。API 与原 Electron 版保持一致（emit/say/dance/idle…）。"""

    def __init__(self, engine=None, model=None, width=None, height=None, scale=1.0,
                 focus='bust', backend='auto', log=print, on_quit=None,
                 actions_dir=None, model_dir=None):
        from renderer.renderer import AvatarRenderer
        # 渲染画布尺寸：默认 420x680；精简/软件渲染模式可被环境变量调小（保证还有帧率）
        env_size = os.environ.get('XIAOLING_WINDOW_SIZE', '')
        if width is None or height is None:
            w_def, h_def = 420, 680
            if env_size and 'x' in env_size:
                try:
                    w_def, h_def = (int(v) for v in env_size.lower().split('x')[:2])
                except ValueError:
                    pass
            width = width or w_def
            height = height or h_def
        self.log = log or (lambda *a, **k: None)
        self.engine = engine
        self.on_quit = on_quit
        self.renderer = AvatarRenderer(model_path=model, backend=backend, width=width,
                                       height=height, focus=focus, log=self.log,
                                       actions_dir=actions_dir, model_dir=model_dir)
        self.renderer.scale = scale
        self.window = None
        self.backend = self.renderer.backend_kind
        self.status_text = ''            # 下载/初始化进度（桌宠气泡会显示）
        self._thread = None
        self._stop = False
        self.hide_bubble_at = 0.0
        # 初始角色 -> 绑定专属音色
        try:
            from core import voices
            voices.set_current_model(self.renderer.model_path)
        except Exception:                                            # noqa: BLE001
            pass

    # ------------------------------------------------------------------ 信息
    @property
    def model_path(self):
        return self.renderer.model_path

    @model_path.setter
    def model_path(self, p):
        self.renderer.model_path = Path(p)

    def boot_payload(self):
        return {'model': str(self.renderer.model_path),
                'models': self.renderer.list_models(),
                'animations': self.renderer.actions_list,
                'scale': self.renderer.scale, 'focus': self.renderer.focus,
                'name': '小凌', 'greeting': self.greeting(),
                'backend': self.renderer.backend_kind}

    def greeting(self):
        h = time.localtime().tm_hour
        if h < 6:
            return '这么晚还没睡呀…我陪你一会儿'
        if h < 11:
            return '早上好～今天也要加油哦'
        if h < 14:
            return '中午啦，记得吃饭'
        if h < 19:
            return '下午好，我在呢'
        return '晚上好～需要我做点什么吗'

    def list_models(self):
        return self.renderer.list_models()

    def list_animations(self):
        return self.renderer.actions_list

    def stats(self):
        return self.renderer.stats()

    # ------------------------------------------------------------------ 启动
    def start(self, block=True):
        """启动桌面宠物窗；无 Qt/无桌面时进入无头模式（返回 False 由上层回退）。"""
        try:
            from renderer.window import PetWindow
        except Exception as e:                                            # noqa: BLE001
            self.log(f'  [数字人] 窗口层不可用：{e}')
            return False
        self.window = PetWindow(self.renderer, engine=self.engine, on_quit=self.on_quit,
                                log=self.log, width=self.renderer.width,
                                height=self.renderer.height, host=self,
                                status_provider=lambda: self.status_text)
        ok = self.window.run(block=block)
        if not ok:
            return False
        self.backend = self.renderer.backend_kind
        self.log(f'  [数字人] 已启动（渲染后端：{self.renderer.backend_kind}，'
                 f'模型：{self.renderer.model_path.name}）')
        # 说明：以前这里是 run(block=False) + self._wait()，但 _wait() 轮询的
        # window._running 只在 _exec() 里才置 True，而 block=False 从不调用 _exec()
        # —— 于是事件循环根本没跑起来、窗口也没 show()，_wait() 立刻返回，
        # 主流程直接走到 app.run() 并退出（表现为"桌宠一闪/没出现，程序自己退了"）。
        # 现在把 block 透传给 run()，block=True 就老老实实阻塞在 Qt 事件循环里，
        # 这与 fusion 里 _start_pet_background 的注释（"主线程被 3D 窗口占用"）一致。
        return True

    def _wait(self):
        """已废弃：历史实现。

        原先 start(block=True) 走的是 run(block=False) + 本方法轮询 window._running，
        但 _running 只在 _exec() 里才置 True，而 block=False 从不调用 _exec() ——
        于是事件循环没跑、窗口没 show()、本方法立刻返回，主流程直接退出。
        现已改为把 block 透传给 window.run()。此方法保留仅为兼容可能有外部调用。
        """
        try:
            while not self._stop and self.window is not None and self.window._running:
                time.sleep(0.3)
        except KeyboardInterrupt:
            self.stop()

    def start_threaded(self):
        self._thread = threading.Thread(target=lambda: self.start(block=True), daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self._stop = True
        try:
            if self.window:
                QtWidgets = self.window.qt[2] if self.window.qt else None
                if QtWidgets is not None:
                    QtWidgets.QApplication.instance().quit()
        except Exception:                                                 # noqa: BLE001
            pass

    # -------------------------------------------------- 表演 API（进程内直调）
    def say(self, text, emotion=None, audio=None):
        self.renderer.say(text, emotion=emotion)
        if self.window:
            self.window.say(text)
        if audio:
            self.play_audio(audio)
        else:
            self._read_aloud_async(text, emotion)      # 阅读模式：用当前角色音色自动朗读
        self.log(f'  [数字人] {text[:40]}')
        return True

    def _read_aloud(self):
        """阅读模式开关（默认开）。配置 avatar.read_aloud 为 false 可关。"""
        try:
            from core import config
            return bool(config.load().get('avatar', {}).get('read_aloud', True))
        except Exception:                                            # noqa: BLE001
            return True

    def _read_aloud_async(self, text, emotion=None):
        if not text or len(text.strip()) < 2 or not self._read_aloud():
            return

        def _job():
            try:
                from core import tts
                path = tts.synthesize(text, emotion=emotion)
                if path:
                    self.play_audio(path)
            except Exception as e:                                    # noqa: BLE001
                self.log(f'  [语音] 朗读失败：{e}')

        threading.Thread(target=_job, daemon=True).start()

    def dance(self):
        self.renderer.dance()
        if self.window:
            self.window.say('好呀，看我的～')
        return True

    def idle(self):
        return self.renderer.idle()

    def set_mood(self, mood):
        self.renderer.set_mood(mood)
        return True

    def set_expression(self, name, weight=1.0, hold=0):
        return self.renderer.set_expression(name, weight, hold)

    def play_action(self, url_or_name, loop=False):
        return self.renderer.play_action(url_or_name, loop=loop)

    def next_model(self):
        name = self.renderer.next_model()
        if self.window:
            self.window.say(f'换好啦：{name}')
        return name

    def switch_model(self, url):
        name = self.renderer.switch_model(url)
        # 换角色 = 连专属音色一起换
        try:
            from core import voices
            info = voices.set_current_model(self.renderer.model_path)
            self.log(f'  [语音] 当前音色：{info.get("desc")}')
        except Exception:                                            # noqa: BLE001
            pass
        return name

    def set_focus(self, mode):
        self.renderer.focus = 'full' if mode == 'full' else 'bust'
        self.renderer.camera.set_focus(self.renderer.focus)
        return True

    def set_progress(self, text):
        """外部（如下载线程）写入进度；窗口会在下一帧显示为气泡。"""
        self.status_text = text or ''
        return True

    def set_scale(self, delta=0.0, absolute=None):
        if absolute is not None:
            self.renderer.scale = max(0.3, min(3.0, float(absolute)))
        else:
            self.renderer.scale = max(0.3, min(3.0, self.renderer.scale + float(delta)))
        return self.renderer.scale

    def play_audio(self, path_or_url):
        # 原本这里有一句 `tts.speak_blocking('', None) if False else None`：被 if False
        # 永久短路，且空文本 + None 情绪本身也不会发声，属于纯死代码，删除。
        p = str(path_or_url)
        if p.startswith('file://'):
            p = p[7:]
        if not Path(p).exists():
            return False
        for player in (['ffplay', '-nodisp', '-autoexit'], ['mpv', '--no-video'], ['aplay'],
                       ['afplay'], ['cmd', '/c', 'start', '']):
            from shutil import which
            if which(player[0]):
                try:
                    subprocess.Popen(player + [p], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return True
                except Exception:                                         # noqa: BLE001
                    continue
        return False

    # ------------------------------------- 兼容旧 IPC 的 emit（现在是纯 Python 调用）
    def emit(self, type_, **payload):
        t = type_
        try:
            if t == 'say':
                return self.say(payload.get('text', ''), payload.get('emotion'),
                                payload.get('audio'))
            if t == 'bubble':
                if self.window:
                    self.window.say(payload.get('text', ''))
                return True
            if t == 'hide-bubble':
                return True
            if t == 'action':
                return self.play_action(payload.get('url') or payload.get('file'),
                                        payload.get('loop', False))
            if t == 'dance':
                return self.dance()
            if t == 'idle':
                return self.idle()
            if t == 'expression':
                return self.set_expression(payload.get('name', 'happy'),
                                           payload.get('weight', 1.0),
                                           payload.get('hold', 0))
            if t == 'mood':
                return self.set_mood(payload.get('mood', 'neutral'))
            if t == 'focus':
                return self.set_focus(payload.get('mode', 'bust'))
            if t == 'scale':
                return self.set_scale(payload.get('delta', 0.1), payload.get('value'))
            if t == 'model':
                return self.switch_model(payload.get('url'))
            if t == 'audio':
                return self.play_audio(payload.get('url', ''))
            if t == 'chat-open':
                return True
            if t == 'config':
                if payload.get('scale'):
                    self.set_scale(absolute=payload['scale'])
                if payload.get('focus'):
                    self.set_focus(payload['focus'])
                return True
        except Exception as e:                                            # noqa: BLE001
            self.log(f'  [数字人] emit({t}) 失败：{e}')
        return False

    # ------------------------------------------------------------------ 对话
    def chat(self, text):
        text = (text or '').strip()
        if not text:
            return ''
        eng = self.engine
        for meth in ('chat', 'reply', 'ask', 'process'):
            fn = getattr(eng, meth, None)
            if callable(fn):
                try:
                    out = fn(text)
                    out = out if isinstance(out, str) else str(out or '')
                    self.say(out)
                    return out
                except TypeError:
                    continue
                except Exception as e:                                    # noqa: BLE001
                    self.log(f'  [数字人] 引擎对话异常：{e}')
                    break
        ans = '我在听呢～（本地模型还没就绪时，我只能这样简单回应）'
        if '跳' in text:
            self.dance()
            ans = '好呀，看我的～'
        self.say(ans)
        return ans

    def on_event(self, ev):
        ev = ev or {}
        t = ev.get('type')
        if t == 'tap':
            self.say('诶？怎么啦～')
        elif t == 'menu' and ev.get('action') == 'status':
            try:
                from core.growth import GrowthEngine
                self.say(GrowthEngine(log=lambda *a: None).report().replace('\n', '　'))
            except Exception as e:                                        # noqa: BLE001
                self.say(f'成长引擎不可用：{e}')
        elif t == 'idle':
            self.proactive()
        return True

    def proactive(self):
        text = None
        fn = getattr(self.engine, 'proactive_line', None)
        if callable(fn):
            try:
                text = fn()
            except Exception:                                             # noqa: BLE001
                text = None
        if not text:
            try:
                from core.proactive import ProactiveEngine
                text = ProactiveEngine(self).compose()
            except Exception:                                             # noqa: BLE001
                text = '在忙吗？我在这儿呢'
        self.say(text)
        return text

    # ------------------------------------------------------------ 无头/离线用途
    def headless_probe(self):
        """不依赖 Qt/窗口的自检：模型、动作、后端、渲染一帧。"""
        out = {'backend': self.renderer.backend_kind,
               'model': str(self.renderer.model_path),
               'actions': len(self.renderer.actions_list),
               'models': len(self.renderer.list_models())}
        try:
            img = self.renderer.frame(with_pose=False)
            out['frame_shape'] = list(img.shape)
            out['frame_ok'] = bool(img.size and img.std() > 1)
        except Exception as e:                                            # noqa: BLE001
            out['frame_ok'] = False
            out['error'] = f'{type(e).__name__}: {e}'
        return out

    def render_showcase(self, outdir, progress=None, fast=None):
        """离线生成形象展示图（README/文档用）。

        软件渲染后端（无 GPU）帧率低，会自动降到小画布 + 低面数，几十秒出完整套图。
        """
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        if fast is None:
            fast = self.renderer.backend_kind != 'gl'
        if fast:
            self.log('  [出图] 检测到软件渲染后端 → 使用小画布 + 低面数模式')
            self.renderer.width, self.renderer.height = 260, 420
            self.renderer.soft_renderer = None
            try:
                from renderer.soft import SoftRenderer
                self.renderer.soft_renderer = SoftRenderer(self.renderer.model, 260, 420,
                                                           max_triangles=6000)
            except Exception as e:                                        # noqa: BLE001
                self.log(f'  [出图] 低规格软渲染不可用，沿用原设置（{e}）')
        shots = []
        self.renderer.idle()
        for i in range(3):
            self.renderer.frame()
        front = self.renderer.camera.front_yaw
        shots.append(('front', dict(focus='bust', zoom=1.0, yaw=front)))
        shots.append(('head', dict(focus='bust', zoom=2.2, yaw=front)))
        shots.append(('side', dict(focus='bust', zoom=1.0, yaw=front + 55)))
        shots.append(('full', dict(focus='full', zoom=1.0, yaw=front)))
        paths = []
        for name, kw in shots:
            p = outdir / f'xiaoling_{name}.png'
            self.renderer.render_png(p, **kw)
            paths.append(str(p))
            if progress:
                progress(name)
        if self.renderer.dance():
            for i in range(40):
                self.renderer.frame()
            p = outdir / 'xiaoling_dance.png'
            self.renderer.render_png(p, focus='full', zoom=1.0)
            paths.append(str(p))
        return paths


def main(argv=None):
    import argparse
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description='小凌 3D 数字人（纯 Python 渲染）')
    ap.add_argument('--model', default=None)
    ap.add_argument('--backend', default='auto', choices=['auto', 'gl', 'soft'])
    ap.add_argument('--width', type=int, default=420)
    ap.add_argument('--height', type=int, default=680)
    ap.add_argument('--focus', default='bust')
    ap.add_argument('--probe', action='store_true', help='只做无头自检')
    ap.add_argument('--showcase', default=None, help='离线出图目录')
    ap.add_argument('--no-window', action='store_true', help='不开窗（配合 --showcase/--probe）')
    a = ap.parse_args(argv)
    av = PythonAvatar(model=a.model, backend=a.backend, width=a.width, height=a.height,
                      focus=a.focus)
    if a.showcase:
        print(json.dumps(av.render_showcase(a.showcase), ensure_ascii=False, indent=1))
        return 0
    if a.probe:
        print(json.dumps(av.headless_probe(), ensure_ascii=False, indent=1))
        return 0
    ok = av.start(block=True)
    if not ok:
        print('（当前环境没有可用窗口，请用 --showcase 离线出图；要开窗显示桌宠请先 pip install PySide6）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
