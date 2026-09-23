#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.renderer —— 小凌 3D 数字人的统一渲染门面（纯 Python）

把「模型 + 骨骼 + 动作 + 表情 + 口型 + 弹簧骨 + 相机」组织成每帧可调用的 `frame()`：

    r = AvatarRenderer('角色模型/小凌.vrm', backend='auto')
    r.play_action('动作资产/dance_舞蹈5.vrma')
    r.say('你好呀～', emotion='happy')
    img = r.frame(dt=1/30)        # numpy RGB (H,W,3) uint8，可直接给窗口/保存 PNG

后端：
    · gl   —— OpenGL（真实 GPU；无 GPU 时 OSMesa/llvmpipe 软件 GL；Qt 窗口内直绘）
    · soft —— 纯 numpy 光栅化（连 GL 都没有时的兜底）
"""
from __future__ import annotations

import glob
import os
import math
import random
import time
from pathlib import Path

import numpy as np

from renderer.camera import OrbitCamera
from renderer.lipsync import LipSync
from renderer.model import VRMModel
from renderer.pose import Pose, SpringBones
from renderer.vrma import VRMAFile

from core.paths import APP_DIR, resource

BASE_DIR = APP_DIR

EXPRESSION_ALIASES = {
    'happy': 'Joy', 'joy': 'Joy', '开心': 'Joy', '高兴': 'Joy',
    'sad': 'Sorrow', 'sorrow': 'Sorrow', '难过': 'Sorrow', '伤心': 'Sorrow',
    'angry': 'Angry', '生气': 'Angry', 'fun': 'Fun',
    'relaxed': 'Neutral', '平静': 'Neutral', 'neutral': 'Neutral',
    'surprised': 'Surprised', '惊讶': 'Surprised',
    'blink': 'Blink', '眨眼': 'Blink',
}
DANCE_RE = ('dance', '舞', '跳')


class AvatarRenderer:
    """小凌数字人的渲染与表演状态机（与 UI/窗口解耦，可无头运行）。"""

    def __init__(self, model_path=None, backend='auto', width=420, height=680,
                 focus='bust', actions_dir=None, model_dir=None, log=print):
        self.log = log or (lambda *a, **k: None)
        self.model_dir = Path(model_dir) if model_dir else resource('角色模型')
        self.actions_dir = Path(actions_dir) if actions_dir else resource('动作资产')
        self.model_path = Path(model_path) if model_path else self._default_model()
        self.width, self.height = width, height
        self.focus = focus
        self.scale = 1.0
        self.model = VRMModel(self.model_path)
        self.pose = Pose(self.model)
        self.springs = SpringBones(self.model)
        self.camera = OrbitCamera(self.model.bbox_max[1], focus=focus)
        self.lipsync = LipSync()
        self.backend_kind = 'none'
        self.gl_renderer = None
        self.soft_renderer = None
        self.context = None
        self.clips = {}
        self.current_clip = None
        self.current_clip_path = ''
        self.clip_time = 0.0
        self.clip_loop = True
        self.actions_list = self.scan_actions()
        self._expr_state = {}
        self._expr_current = {}
        self.mood = 'neutral'
        self.talking_until = 0.0
        self._blink_timer = 2.0 + random.random() * 3
        self._blink_at = 0.0
        self._breath = 0.0
        self._frame_count = 0
        self._fps = 0.0
        self._fps_t = time.time()
        self.last_error = ''
        self._init_backend(backend)

    # ------------------------------------------------------------------ 基础
    def _default_model(self) -> Path:
        p = self.model_dir / '小凌.vrm'
        if p.exists():
            return p
        for f in sorted(self.model_dir.glob('*.vrm')):
            return f
        raise FileNotFoundError('没有可用的 VRM 模型')

    def scan_actions(self):
        out = []
        for p in sorted(glob.glob(str(self.actions_dir / '*.vrma'))):
            name = Path(p).stem
            out.append({'name': name, 'path': p,
                        'dance': any(k in name.lower() or k in name for k in DANCE_RE),
                        'idle': ('待机' in name) or ('idle' in name.lower())})
        return out

    def list_models(self):
        return [{'name': p.stem, 'path': str(p)} for p in sorted(self.model_dir.glob('*.vrm'))]

    def _init_backend(self, backend):
        forced = os.environ.get('XIAOLING_RENDER_BACKEND', '').strip().lower()
        if forced in ('gl', 'soft'):
            backend = forced
        order = ['gl', 'soft'] if backend in ('auto', 'gl') else ['soft']
        for kind in order:
            try:
                if kind == 'gl':
                    from renderer.gl import GLRenderer, make_context
                    self.context = make_context(['osmesa'], self.width, self.height)
                    self.gl_renderer = GLRenderer(self.model, self.context,
                                                  background=(0, 0, 0, 0))
                    self.backend_kind = 'gl'
                    self.log(f"  [渲染] OpenGL 后端就绪：{self.context.info()['renderer']}")
                    return
                from renderer.soft import SoftRenderer
                max_tris = int(os.environ.get('XIAOLING_SOFT_MAX_TRIS', '30000') or 30000)
                self.soft_renderer = SoftRenderer(self.model, self.width, self.height,
                                                  max_triangles=max_tris)
                self.backend_kind = 'soft'
                self.log('  [渲染] CPU 软件光栅后端就绪')
                return
            except Exception as e:                                        # noqa: BLE001
                self.last_error = f'{kind}: {type(e).__name__}: {e}'
                self.log(f'  [渲染] {kind} 后端不可用：{self.last_error}')
        self.backend_kind = 'none'

    def stats(self) -> dict:
        base = self.model.summary()
        base.update({'backend': self.backend_kind, 'fps': round(self._fps, 1),
                     'size': [self.width, self.height], 'focus': self.focus,
                     'scale': round(self.scale, 2),
                     'action': Path(self.current_clip_path).stem if self.current_clip_path else '',
                     'mood': self.mood, 'last_error': self.last_error})
        if self.gl_renderer is not None:
            base['gl'] = self.gl_renderer.info()
        if self.soft_renderer is not None:
            base['soft'] = self.soft_renderer.stats()
        return base

    # ------------------------------------------------------------------ 模型
    def switch_model(self, path):
        self.model = VRMModel(path)
        self.model_path = Path(path)
        self.pose = Pose(self.model)
        self.springs = SpringBones(self.model)
        self.camera = OrbitCamera(self.model.bbox_max[1], focus=self.focus)
        self.clips.clear()
        self.current_clip = None
        self._init_backend('gl' if self.backend_kind == 'gl' else 'soft')
        return self.model.name

    def next_model(self):
        models = self.list_models()
        if not models:
            return None
        paths = [m['path'] for m in models]
        cur_name = Path(str(self.model_path)).name
        idx = next((i for i, p in enumerate(paths) if Path(p).name == cur_name), 0)
        nxt = paths[(idx + 1) % len(paths)]
        self.switch_model(nxt)
        return Path(nxt).stem

    # ------------------------------------------------------------------ 动作
    def load_clip(self, path):
        path = str(path)
        if path not in self.clips:
            self.clips[path] = VRMAFile(path).clip(self.model)
        return self.clips[path]

    def play_action(self, path_or_name, loop=True):
        p = str(path_or_name)
        if not Path(p).exists():
            hit = next((a for a in self.actions_list
                        if a['name'] == p or p in a['name']), None)
            p = hit['path'] if hit else ''
        if not p or not Path(p).exists():
            return False
        clip = self.load_clip(p)
        if clip is None:
            return False
        self.current_clip = clip
        self.current_clip_path = p
        self.clip_time = 0.0
        self.clip_loop = bool(loop)
        return True

    def dance(self):
        dances = [a for a in self.actions_list if a['dance']]
        if not dances:
            return False
        a = random.choice(dances)
        self.log(f"  [数字人] 跳舞：{a['name']}")
        return self.play_action(a['path'], loop=True)

    def idle(self):
        idle = next((a for a in self.actions_list if a['idle']), None)
        if idle:
            return self.play_action(idle['path'], loop=True)
        self.current_clip = None
        self.current_clip_path = ''
        self.pose.reset()
        self.springs.reset()
        return True

    # -------------------------------------------------------------- 表情/口型
    def set_expression(self, name, weight=1.0, hold=0.0):
        key = EXPRESSION_ALIASES.get(str(name).lower(), name)
        self._expr_state[key] = float(weight)
        return True

    def clear_expressions(self):
        self._expr_state.clear()

    def set_mood(self, mood):
        self.mood = mood or 'neutral'
        self.clear_expressions()
        name = EXPRESSION_ALIASES.get(str(self.mood).lower())
        if name and name != 'Neutral':
            self.set_expression(name, 0.7)
        return True

    def say(self, text, emotion=None, duration=None):
        d = self.lipsync.play(text or '')
        self.talking_until = time.time() + max(d, duration or 0.0)
        if emotion:
            self.set_mood(emotion)
        return d

    # ------------------------------------------------------------------ 每帧
    def _merge_morphs(self):
        mmap: dict[int, dict[int, float]] = {}

        def add(name, weight):
            binds = (self.model.expressions.get(name)
                     or self.model.expressions.get(self.model.preset_of(name) or '') or [])
            for prim_i, tgt_i, bw in binds:
                mmap.setdefault(prim_i, {})
                mmap[prim_i][tgt_i] = mmap[prim_i].get(tgt_i, 0.0) + bw * weight

        for name, w in self._expr_state.items():
            cur = self._expr_current.get(name, 0.0)
            cur += (max(0.0, min(1.0, w)) - cur) * 0.35
            self._expr_current[name] = cur
            add(name, cur)
        for name, w in self.lipsync.weights().items():
            add(name, w)
        if self._blink_at and time.time() < self._blink_at:
            add('Blink', 1.0)
        return mmap

    def _view_proj(self):
        self.camera.zoom = self.scale
        self.camera.update()
        return self.camera.view_proj(self.width / self.height)

    def frame(self, dt=1 / 30.0, yaw=None, pitch=None, with_pose=True):
        """推进一帧并返回 RGB 图像（numpy uint8）。"""
        if yaw is not None:
            self.camera.yaw = yaw
        if pitch is not None:
            self.camera.pitch = pitch
        if with_pose:
            if self.current_clip is not None:
                self.clip_time += dt
                self.current_clip.apply(self.pose, self.clip_time, loop=self.clip_loop)
            self.springs.update(self.pose, dt)
            self.lipsync.update(dt)
            self._blink_timer -= dt
            if self._blink_timer <= 0 and not self._blink_at:
                self._blink_at = time.time() + 0.12
                self._blink_timer = 2.2 + random.random() * 3.4
            if self._blink_at and time.time() > self._blink_at:
                self._blink_at = 0.0
            chest = self.model.humanoid.get('chest')
            if chest is not None:                       # 呼吸起伏
                self._breath += dt * 2.4
                ph = math.sin(self._breath) * 0.012
                self.pose.rotation[chest] = np.array(
                    [math.sin(ph / 2), 0.0, 0.0, math.cos(ph / 2)], np.float32)
                self.pose._dirty = True
        vp = self._view_proj()
        mmap = self._merge_morphs()
        if self.backend_kind == 'gl' and self.gl_renderer is not None:
            self.context.make_current()
            self.gl_renderer.draw(self.pose, vp, morph_map=mmap, clear=True)
            img = self.context.read_pixels()[..., :3]
        elif self.backend_kind == 'soft' and self.soft_renderer is not None:
            rgb = self.soft_renderer.render(self.pose, morph_map=mmap, view_proj=vp)
            img = (rgb * 255).astype(np.uint8)
        else:
            img = np.zeros((self.height, self.width, 3), np.uint8)
        self._frame_count += 1
        if time.time() - self._fps_t > 1.0:
            self._fps = self._frame_count / (time.time() - self._fps_t)
            self._frame_count = 0
            self._fps_t = time.time()
        return img

    # ------------------------------------------------------------ 无头/离线出图
    def render_png(self, path, yaw=0.0, pitch=2.0, focus=None, zoom=None):
        """离线出图（无头模式 / 文档配图）。zoom 直接映射到角色缩放。"""
        from PIL import Image
        if focus:
            self.camera.set_focus(focus)
        if zoom:
            self.scale = float(zoom)
        img = self.frame(dt=0.0, yaw=yaw, pitch=pitch, with_pose=False)
        Image.fromarray(img).save(str(path))
        return str(path)
