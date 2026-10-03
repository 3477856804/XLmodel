#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.avatar —— 3D 数字人无头宿主（新三语言架构）

新架构下，桌面 3D 形象由 **Flutter UI** 负责显示，Python 后端只负责「渲染出一帧
像素 + 提供动作/表情/口型数据」，通过 gRPC 推给前端。本模块不再启动任何 Qt 窗口
（旧 renderer.app / renderer.window 已随 PySide6 UI 一并移除），只包装现存的
`renderer.renderer.AvatarRenderer`，供：

    · gRPC 后端取帧 / 播放动作（backend/rpc/server.py）
    · 安装脚本做无头自检（run_headless_probe）

    from core.avatar import AvatarHost
    host = AvatarHost(log=print)
    frame = host.render_frame()
"""
from __future__ import annotations

import json


class AvatarHost:
    """3D 数字人宿主：无头封装纯 numpy / OpenGL 渲染器。"""

    def __init__(self, engine=None, model=None, scale=1.0, focus='bust', log=print,
                 on_quit=None, width=420, height=680, backend='auto', **kw):
        from renderer.renderer import AvatarRenderer as _R
        self.engine = engine
        self.log = log or (lambda *a: None)
        self.on_quit = on_quit
        self._renderer = _R(model_path=model, backend=backend, width=width,
                             height=height, focus=focus, log=self.log)

    # ---- 渲染 ----
    def render_frame(self, with_pose: bool = True):
        """渲染一帧，返回 HxWx3 ndarray。"""
        return self._renderer.frame(with_pose=with_pose)

    def say(self, text: str):
        """朗读（口型联动入口；音频播放由前端/语音系统负责）。"""
        try:
            self._renderer.lipsync.play(text)
        except Exception as e:                                    # noqa: BLE001
            self.log(f'  [avatar] 口型失败：{e}')

    def dance(self, action: str = ''):
        try:
            self._renderer.play_action(action)
        except Exception as e:                                    # noqa: BLE001
            self.log(f'  [avatar] 动作播放失败：{e}')

    def next_model(self):
        """切换到下一个可用模型文件。"""
        try:
            self._renderer.switch_model(None)
        except Exception as e:                                    # noqa: BLE001
            self.log(f'  [avatar] 切换模型失败：{e}')

    def headless_probe(self) -> dict:
        """无头自检：能否渲染出有效帧、动作库数量。"""
        img = self._renderer.frame(with_pose=False)
        return {
            'frame_ok': bool(img.size and img.std() > 1),
            'actions': len(getattr(self._renderer, 'actions', []) or []),
            'backend': getattr(self._renderer, 'backend_kind', 'none'),
        }

    def quit(self):
        if self.on_quit:
            try:
                self.on_quit()
            except Exception:                                     # noqa: BLE001
                pass


def run_headless_probe(port=None):
    """自检用：不依赖 Qt/显示器，直接验证渲染层与形象资源。"""
    try:
        host = AvatarHost(log=lambda *a: None)
        probe = host.headless_probe()
        probe['qt'] = None  # 新架构无 Qt
        probe['ok'] = bool(probe.get('frame_ok')) and probe.get('actions', 0) >= 0
        return probe
    except Exception as e:                                          # noqa: BLE001
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def _qt_available():
    # 新架构已移除 Qt 桌面窗，恒为 None（保留是为了兼容老调用）。
    return None


if __name__ == '__main__':
    print(json.dumps(run_headless_probe(), ensure_ascii=False, indent=1))
