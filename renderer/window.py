#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.window —— 桌面宠物窗口（Qt，纯 Python）

两种绘制方式，自动降级：

  1. **GL 直绘**（推荐）：`QOpenGLWidget` + 复用同一份 OpenGL 上下文直接绘制，真 60fps，
     配合 `Qt.WA_TranslucentBackground` 得到透明置顶窗。
  2. **QImage 贴图**：软件光栅后端渲染成 numpy → QImage → QPainter 贴图，
     在没有可用 OpenGL 的机器上依然能跑（帧率低）。

窗口能力：无边框 / 透明 / 置顶 / 拖拽移动 / 滚轮缩放 / 右键菜单 / 双击聊天 / 气泡 + 输入框。
不再需要 HTML/CSS/JS，也不需要 Electron。
"""
from __future__ import annotations

import sys
import time

import numpy as np

WINDOW_STYLE = """
QWidget#pet { background: transparent; }
QLabel#bubble {
    background: rgba(255,255,255,0.94);
    color: #2c3345;
    border: 1px solid rgba(180,205,240,0.75);
    border-radius: 14px;
    padding: 10px 14px;
    font-size: 14px;
    line-height: 160%;
}
QLineEdit#chat {
    background: rgba(255,255,255,0.96);
    border: 1px solid rgba(180,205,240,0.8);
    border-radius: 12px;
    padding: 6px 10px;
    font-size: 14px;
    color: #2c3345;
}
QPushButton#send {
    background: #5b9dfb; color: white; border: none; border-radius: 10px; padding: 6px 14px;
}
QMenu { background: rgba(255,255,255,0.97); border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 22px; border-radius: 7px; }
QMenu::item:selected { background: rgba(91,157,251,0.16); }
"""


def _numpy_to_qimage_qt(img, QtGui):
    h, w = img.shape[:2]
    if img.shape[2] == 3:
        fmt = QtGui.QImage.Format_RGB888
        stride = w * 3
    else:
        fmt = QtGui.QImage.Format_RGBA8888
        stride = w * 4
    buf = np.ascontiguousarray(img).tobytes()
    return QtGui.QImage(buf, w, h, stride, fmt).copy()


class PetWindow:
    """把 AvatarRenderer 变成一只桌面宠物（Qt 外壳）。"""

    def __init__(self, renderer, engine=None, on_quit=None, log=print,
                 width=None, height=None, opacity=1.0, status_provider=None):
        self.renderer = renderer
        self.status_provider = status_provider
        self._last_status = ''
        self.engine = engine
        self.on_quit = on_quit
        self.log = log or (lambda *a, **k: None)
        self.width = width or renderer.width
        self.height = height or renderer.height
        self.opacity = opacity
        self.qt = None
        self.app = None
        self.widget = None
        self._drag = None
        self._last_idle_report = time.time()
        self._running = False

    # ------------------------------------------------------------------ 入口
    def run(self, block=True):
        try:
            from PySide6 import QtCore, QtGui, QtWidgets
        except Exception:                                                # noqa: BLE001
            try:
                from PyQt5 import QtCore, QtGui, QtWidgets             # noqa: N813
            except Exception as e:                                       # noqa: BLE001
                self.log(f'  [窗口] 未找到 Qt（pip install PySide6 或 PyQt5）：{e}')
                return False
        self.qt = (QtCore, QtGui, QtWidgets)
        gl_ok = self._try_gl_widget(QtCore, QtGui, QtWidgets)
        if not gl_ok:
            self._make_image_widget(QtCore, QtGui, QtWidgets)
        if block:
            return self._exec()
        return True

    def _exec(self):
        QtCore, QtGui, QtWidgets = self.qt
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.widget.show()
        self._running = True
        try:
            self.app.exec_() if hasattr(self.app, 'exec_') else self.app.exec()
        finally:
            self._running = False
        return True

    # ------------------------------------------------------------- GL 直绘窗口
    def _try_gl_widget(self, QtCore, QtGui, QtWidgets):
        if self.renderer.backend_kind != 'gl':
            return False
        try:
            class _GLWidget(QtWidgets.QOpenGLWidget):
                pass
        except Exception:                                                # noqa: BLE001
            return False
        outer = self

        class PetGLWidget(QtWidgets.QOpenGLWidget):
            def __init__(self):
                super().__init__()
                self.setWindowTitle('小凌')
                self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
                                    | QtCore.Qt.Tool)
                self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
                self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
                self.resize(outer.width, outer.height)
                self.setWindowOpacity(outer.opacity)
                self.setMouseTracking(True)
                self._bubble = QtWidgets.QLabel('', self)
                self._bubble.setObjectName('bubble')
                self._bubble.setWordWrap(True)
                self._bubble.setStyleSheet(
                    'background: rgba(255,255,255,0.94); color:#2c3345;'
                    'border:1px solid rgba(180,205,240,0.75); border-radius:14px;'
                    'padding:10px 14px; font-size:14px;')
                self._bubble.hide()
                self._bubble_timer = QtCore.QTimer(self)
                self._bubble_timer.setSingleShot(True)
                self._bubble_timer.timeout.connect(self._bubble.hide)
                self._timer = QtCore.QTimer(self)
                self._timer.timeout.connect(self._tick)
                self._timer.start(33)

            # ---- GL 生命周期 ----
            def initializeGL(self):
                try:
                    from renderer.gl import ExistingContext, GLRenderer
                    ctx = ExistingContext(self.width(), self.height())
                    self._gl = GLRenderer(outer.renderer.model, ctx, background=(0, 0, 0, 0))
                    outer.renderer.context = ctx
                    outer.renderer.gl_renderer = self._gl
                    outer.renderer.backend_kind = 'gl'
                    outer.log('  [窗口] OpenGL 直绘已启用')
                except Exception as e:                                   # noqa: BLE001
                    outer.log(f'  [窗口] GL 直绘初始化失败，改用贴图模式：{e}')
                    self._gl = None

            def resizeGL(self, w, h):
                outer.renderer.width, outer.renderer.height = max(w, 1), max(h, 1)
                if getattr(outer.renderer, 'context', None):
                    outer.renderer.context.resize(w, h)
                self._place_bubble()

            def paintGL(self):
                if self._gl is None:
                    return
                outer.renderer.frame()
                # GL 直绘：内容已经画进当前 framebuffer，无需再经过 QPainter

            def _tick(self):
                if self._gl is not None:
                    self.update()
                else:
                    self.repaint()
                outer._poll_status()
                outer._maybe_report_idle()

            def _place_bubble(self):
                w = min(300, max(self.width() - 20, 120))
                self._bubble.setFixedWidth(w)
                self._bubble.move(10, 8)
                self._bubble.adjustSize()

            def show_bubble(self, text, seconds=None):
                self._bubble.setText(str(text))
                self._place_bubble()
                self._bubble.show()
                self._bubble.raise_()
                sec = seconds or max(2.2, min(15.0, len(str(text)) * 0.18))
                self._bubble_timer.start(int(sec * 1000))

            # ---- 交互 ----
            def mousePressEvent(self, ev):
                if ev.button() == QtCore.Qt.LeftButton:
                    self._drag = (ev.globalPos(), self.pos())

            def mouseMoveEvent(self, ev):
                if self._drag:
                    delta = ev.globalPos() - self._drag[0]
                    self.move(self._drag[1] + delta)
                outer.renderer.camera.yaw = max(-60, min(60, (ev.x() / max(self.width(), 1) - 0.5) * 60))

            def mouseReleaseEvent(self, ev):
                self._drag = None

            def mouseDoubleClickEvent(self, ev):
                outer.open_chat_input(self)

            def wheelEvent(self, ev):
                step = 0.05 if ev.angleDelta().y() > 0 else -0.05
                outer.renderer.scale = max(0.3, min(3.0, outer.renderer.scale + step))

            def contextMenuEvent(self, ev):
                outer.show_menu(self, ev.globalPos())

        self.widget = PetGLWidget()
        self.widget.show_bubble = self.widget.show_bubble
        self.log('  [窗口] 透明置顶窗（GL 直绘）准备就绪')
        return True

    # --------------------------------------------------------- QImage 贴图窗口
    def _make_image_widget(self, QtCore, QtGui, QtWidgets):
        outer = self

        class PetWidget(QtWidgets.QWidget):
            def __init__(self):
                super().__init__()
                self.setObjectName('pet')
                self.setWindowTitle('小凌')
                self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
                                    | QtCore.Qt.Tool)
                self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
                self.resize(outer.width, outer.height)
                self.setStyleSheet(WINDOW_STYLE)
                self._img = None
                self._bubble = QtWidgets.QLabel('', self)
                self._bubble.setObjectName('bubble')
                self._bubble.setWordWrap(True)
                self._bubble.hide()
                self._btimer = QtCore.QTimer(self)
                self._btimer.setSingleShot(True)
                self._btimer.timeout.connect(self._bubble.hide)
                self._timer = QtCore.QTimer(self)
                self._timer.timeout.connect(self._tick)
                self._timer.start(120)                     # 软件后端帧率有限
                self._drag = None

            def _tick(self):
                img = outer.renderer.frame(dt=max(0.033, 0.12))
                self._img = _numpy_to_qimage_qt(img, QtGui)
                self.update()
                outer._poll_status()
                outer._maybe_report_idle()

            def paintEvent(self, ev):
                if self._img is None:
                    return
                p = QtGui.QPainter(self)
                p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)
                p.drawImage(0, 0, self._img)

            def show_bubble(self, text, seconds=None):
                self._bubble.setText(str(text))
                self._bubble.setFixedWidth(min(300, max(self.width() - 20, 120)))
                self._bubble.adjustSize()
                self._bubble.move(10, 8)
                self._bubble.show()
                self._btimer.start(int((seconds or 3.0) * 1000))

            def mousePressEvent(self, ev):
                if ev.button() == QtCore.Qt.LeftButton:
                    self._drag = (ev.globalPos(), self.pos())

            def mouseMoveEvent(self, ev):
                if self._drag:
                    self.move(self._drag[1] + (ev.globalPos() - self._drag[0]))

            def mouseReleaseEvent(self, ev):
                self._drag = None

            def mouseDoubleClickEvent(self, ev):
                outer.open_chat_input(self)

            def wheelEvent(self, ev):
                step = 0.05 if ev.angleDelta().y() > 0 else -0.05
                outer.renderer.scale = max(0.3, min(3.0, outer.renderer.scale + step))

            def contextMenuEvent(self, ev):
                outer.show_menu(self, ev.globalPos())

        self.widget = PetWidget()
        self.log('  [窗口] 透明置顶窗（QImage 贴图模式）准备就绪')
        return True

    # ------------------------------------------------------------------ 交互
    def open_chat_input(self, parent):
        QtCore, QtGui, QtWidgets = self.qt
        outer = self
        dlg = QtWidgets.QInputDialog(parent)
        dlg.setWindowTitle('和小凌说点什么')
        dlg.setLabelText('小凌在听：')
        dlg.setStyleSheet(WINDOW_STYLE)
        if dlg.exec_() if hasattr(dlg, 'exec_') else dlg.exec():
            text = dlg.textValue().strip()
            if text and outer.engine is not None:
                reply = getattr(outer.engine, 'chat', lambda t: '（我还没准备好）')(text)
                self.show_bubble(str(reply))

    def show_menu(self, parent, pos):
        QtCore, QtGui, QtWidgets = self.qt
        menu = QtWidgets.QMenu(parent)
        actions = [('打开对话', lambda: self.open_chat_input(parent)),
                   ('跳个舞', lambda: self.renderer.dance()),
                   ('回到待机', lambda: self.renderer.idle()),
                   ('换装（重新生成形象）', self._redress),
                   ('成长状态', self._growth),
                   ('设置', self.open_settings),
                   ('隐藏', lambda: parent.hide()),
                   ('退出', self.quit)]
        # 「切换角色」做成模型列表子菜单：列出全部 VRM，当前模型打勾，点谁切谁
        model_menu = menu.addMenu('切换角色')
        try:
            models = self.renderer.list_models()
        except Exception:                                            # noqa: BLE001
            models = []
        cur = str(getattr(self.renderer, 'model_path', ''))
        if models:
            for m in models:
                act = model_menu.addAction(m['name'])
                act.setCheckable(True)
                act.setChecked(str(m['path']) == cur)
                act.triggered.connect(lambda checked=False, p=m['path'], n=m['name']:
                                      self._switch_to_model(p, n))
        else:
            act = model_menu.addAction('（角色模型目录下没有 .vrm）')
            act.setEnabled(False)
        model_menu.addSeparator()
        nxt = model_menu.addAction('下一个角色')
        nxt.triggered.connect(self._next_model)

        for label, fn in actions:
            act = menu.addAction(label)
            act.triggered.connect(fn)
        menu.exec_(pos) if hasattr(menu, 'exec_') else menu.exec(pos)

    def _switch_to_model(self, path, name):
        try:
            self.renderer.switch_model(path)
            self.widget.show_bubble(f'换好啦：{name}')
        except Exception as e:                                            # noqa: BLE001
            self.log(f'  [窗口] 切换角色失败：{e}')
            self.widget.show_bubble(f'切换失败：{e}')

    def _next_model(self):
        name = self.renderer.next_model()
        if self.widget and hasattr(self.widget, 'show_bubble'):
            self.widget.show_bubble(f'换好啦：{name}')

    def _redress(self):
        import subprocess
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        try:
            subprocess.Popen([sys.executable, str(root / '工具' / 'xiaoling_avatar.py'), 'build',
                              '--base', str(root / '角色模型' / 'Rabbit_Peridot.vrm'),
                              '--face', str(root / '素材' / 'xiaoling.png'),
                              '--out', str(root / '角色模型' / '小凌.vrm'),
                              '--preview', str(root / 'preview')])
            self.widget.show_bubble('正在给小凌做新裙子，稍等一下～')
        except Exception as e:                                            # noqa: BLE001
            self.log(f'  [窗口] 换装失败：{e}')

    def _growth(self):
        try:
            from core.growth import GrowthEngine
            self.widget.show_bubble(GrowthEngine(log=lambda *a: None).report())
        except Exception as e:                                            # noqa: BLE001
            self.widget.show_bubble(f'成长引擎不可用：{e}')

    def open_settings(self):
        try:
            from renderer.settings import SettingsDialog
            dlg = SettingsDialog(self.qt)
            dlg.exec_() if hasattr(dlg, 'exec_') else dlg.exec()
        except Exception as e:                                            # noqa: BLE001
            self.log(f'  [窗口] 设置窗打开失败：{e}')

    def quit(self):
        if self.on_quit:
            try:
                self.on_quit()
            except Exception:                                             # noqa: BLE001
                pass
        QtCore, QtGui, QtWidgets = self.qt
        QtWidgets.QApplication.instance().quit()

    # ------------------------------------------------------------------ 事件
    def _poll_status(self):
        """把宿主写进来的进度文本（下载/初始化）显示成气泡。"""
        if not self.status_provider:
            return
        try:
            txt = self.status_provider() or ''
        except Exception:                                                 # noqa: BLE001
            return
        if txt and txt != self._last_status:
            self._last_status = txt
            if self.widget is not None and hasattr(self.widget, 'show_bubble'):
                self.widget.show_bubble(txt, seconds=8.0)

    def _maybe_report_idle(self):
        now = time.time()
        if now - self._last_idle_report > 20:
            self._last_idle_report = now
            if self.engine is not None and hasattr(self.engine, 'on_avatar_idle'):
                try:
                    self.engine.on_avatar_idle()
                except Exception:                                         # noqa: BLE001
                    pass

    def say(self, text, seconds=None):
        if self.widget is not None and hasattr(self.widget, 'show_bubble'):
            self.widget.show_bubble(text, seconds)
        return True
