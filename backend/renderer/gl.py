#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renderer.gl —— 纯 Python + GLSL 的 OpenGL 渲染后端

* 顶点蒙皮在 GPU 做（骨矩阵用 uniform 数组），表情形变在 CPU 做（只更新有表情的图元）
* 上下文可来自三种"提供者"：
    1. OSMesa（离线/无 GPU 机器/服务器，llvmpipe 全软件 OpenGL，本项目已在沙箱验证）
    2. Qt 的 QOpenGLWidget（桌面宠物透明窗，Windows/macOS/Linux）
    3. 已存在的当前上下文（宿主自行创建时）
* MToon-lite 着色：基色贴图 × 颜色因子 + 两段式（明/暗）卡通阴影 + 边缘光，支持
  OPAQUE / MASK(discard) / BLEND 三种透明度模式

没有 three.js、没有浏览器、没有 JS。
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

import numpy as np

from renderer.pose import apply_morphs

VERT_SRC = """#version 330
layout(location = 0) in vec3 a_pos;
layout(location = 1) in vec3 a_nrm;
layout(location = 2) in vec2 a_uv;
layout(location = 3) in vec4 a_joints;
layout(location = 4) in vec4 a_weights;
uniform mat4 u_viewProj;
uniform mat4 u_bones[160];
uniform int u_skinned;
out vec3 v_nrm;
out vec2 v_uv;
void main() {
    vec4 p = vec4(a_pos, 1.0);
    vec3 n = a_nrm;
    if (u_skinned == 1) {
        int j0 = int(a_joints.x); int j1 = int(a_joints.y);
        int j2 = int(a_joints.z); int j3 = int(a_joints.w);
        mat4 m = a_weights.x * u_bones[j0] + a_weights.y * u_bones[j1]
               + a_weights.z * u_bones[j2] + a_weights.w * u_bones[j3];
        p = m * p;
        n = mat3(m) * n;
    }
    v_uv = a_uv;
    v_nrm = n;
    gl_Position = u_viewProj * p;
}
"""

FRAG_SRC = """#version 330
in vec3 v_nrm;
in vec2 v_uv;
uniform sampler2D u_tex;
uniform vec4 u_color;
uniform vec3 u_shade;
uniform vec3 u_light;
uniform int u_has_tex;
uniform int u_unlit;
uniform int u_rim;
uniform float u_cutoff;
out vec4 fragColor;
void main() {
    vec4 c = (u_has_tex == 1) ? texture(u_tex, v_uv) : vec4(1.0, 1.0, 1.0, 1.0);
    c *= u_color;
    if (c.a < u_cutoff) discard;
    if (u_unlit == 0) {
        vec3 n = normalize(v_nrm);
        float nl = dot(n, normalize(u_light));
        // 两段式卡通阴影（MToon 风格）
        float lit = nl > 0.28 ? 1.0 : (nl > 0.02 ? 0.72 : 0.5);
        c.rgb *= mix(u_shade, vec3(1.0), lit);
        if (u_rim == 1) {
            float rim = pow(1.0 - max(n.z * 0.5 + 0.5, 0.0), 2.4);
            c.rgb += rim * 0.10;
        }
    }
    fragColor = c;
}
"""


class GLContextError(RuntimeError):
    pass


# --------------------------------------------------------------------- 上下文
class EGLContext:
    """EGL 离屏上下文：Linux 有显卡驱动时走真 GPU（无需 X 窗口）。

    优先级：EGL（GPU）→ OSMesa（软件 GL）。驱动不全时 EGL 初始化失败自动跳过。
    可用 EGL_DEVICE_ID / EGL_PLATFORM 选择设备。
    """

    name = 'egl'

    def __init__(self, width=420, height=680):
        os.environ.setdefault('PYOPENGL_PLATFORM', 'egl')
        try:
            from OpenGL import EGL
            from OpenGL.EGL import (EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE,
                                    EGL_OPENGL_API, EGL_BLUE_SIZE, EGL_GREEN_SIZE,
                                    EGL_RED_SIZE, EGL_ALPHA_SIZE, EGL_DEPTH_SIZE,
                                    EGL_NONE, EGL_NO_DISPLAY, EGL_DEFAULT_DISPLAY,
                                    EGL_CONTEXT_CLIENT_VERSION, eglGetDisplay,
                                    eglInitialize, eglChooseConfig, eglBindAPI,
                                    eglCreateContext, eglMakeCurrent, eglCreatePbufferSurface,
                                    eglQuerySurface, eglTerminate, eglGetError)
        except Exception as e:                                        # noqa: BLE001
            raise GLContextError(f'PyOpenGL/EGL 不可用：{e}')
        self.EGL = EGL
        self.w, self.h = width, height
        display = eglGetDisplay(EGL_DEFAULT_DISPLAY)
        if display in (None, EGL_NO_DISPLAY):
            raise GLContextError('eglGetDisplay 失败')
        major, minor = EGL.EGLint(), EGL.EGLint()
        if not eglInitialize(display, major, minor):
            raise GLContextError('eglInitialize 失败（GPU 驱动/EGL 未安装？）')
        attribs = [EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
                   EGL_RENDERABLE_TYPE, EGL_OPENGL_API,
                   EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8,
                   EGL_ALPHA_SIZE, 8, EGL_DEPTH_SIZE, 24, EGL_NONE]
        config = (EGL.EGLConfig * 1)()
        n_cfg = EGL.EGLint()
        if not eglChooseConfig(display, attribs, config, 1, n_cfg) or n_cfg.value < 1:
            raise GLContextError('eglChooseConfig 失败')
        eglBindAPI(EGL_OPENGL_API)
        ctx = eglCreateContext(display, config[0], EGL.EGL_NO_CONTEXT,
                               [EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE])
        if not ctx:
            raise GLContextError('eglCreateContext 失败')
        pb_attribs = [EGL.EGL_WIDTH, width, EGL.EGL_HEIGHT, height, EGL_NONE]
        surface = eglCreatePbufferSurface(display, config[0], pb_attribs)
        if not surface:
            raise GLContextError('eglCreatePbufferSurface 失败')
        if not eglMakeCurrent(display, surface, surface, ctx):
            raise GLContextError('eglMakeCurrent 失败')
        self.display, self.surface, self.ctx = display, surface, ctx
        try:
            from OpenGL import GL
        except Exception as e:                                        # noqa: BLE001
            raise GLContextError(f'PyOpenGL/GL 不可用：{e}')
        self.GL = GL

    def make_current(self):
        from OpenGL.EGL import eglMakeCurrent
        eglMakeCurrent(self.display, self.surface, self.surface, self.ctx)

    def resize(self, w, h):
        self.w, self.h = w, h

    def read_pixels(self) -> np.ndarray:
        GL = self.GL
        GL.glFinish()
        data = GL.glReadPixels(0, 0, self.w, self.h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        arr = np.frombuffer(data, np.uint8).reshape(self.h, self.w, 4)
        return arr[::-1].copy()

    def info(self):
        GL = self.GL
        return {'backend': 'egl',
                'version': (GL.glGetString(GL.GL_VERSION) or b'?').decode(errors='replace'),
                'renderer': (GL.glGetString(GL.GL_RENDERER) or b'?').decode(errors='replace'),
                'glsl': (GL.glGetString(GL.GL_SHADING_LANGUAGE_VERSION) or b'?').decode(errors='replace')}


class OSMesaContext:
    """基于 OSMesa 的离屏上下文（llvmpipe 全软件 OpenGL，无需 X/GPU）。"""

    name = 'osmesa'

    def __init__(self, width=420, height=680):
        # 无 GPU 环境下用 Mesa 的软件光栅器：softpipe 是纯 C 实现，兼容性最好
        # （llvmpipe 在部分被虚拟化的 CPU 上会因 LLVM JIT 触发非法指令；
        #   可用 XIAOLING_GALLIUM_DRIVER=llvmpipe 覆盖，或用 GALLIVM_PERF=nopt）
        os.environ.setdefault('PYOPENGL_PLATFORM', 'osmesa')
        os.environ.setdefault('GALLIUM_DRIVER',
                              os.environ.get('XIAOLING_GALLIUM_DRIVER', 'llvmpipe'))
        # llvmpipe 的 LLVM JIT 在部分虚拟化 CPU 上会触发非法指令，关闭 JIT 优化即可绕开
        os.environ.setdefault('GALLIVM_PERF', 'nopt')
        try:
            from OpenGL import GL, osmesa
        except Exception as e:                                        # noqa: BLE001
            raise GLContextError(f'PyOpenGL/OSMesa 不可用：{e}')
        self.GL = GL
        self.osmesa = osmesa
        self.w, self.h = width, height
        self.buffer = np.zeros((height, width, 4), np.uint8)
        self.ctx = osmesa.OSMesaCreateContextExt(osmesa.OSMESA_RGBA, 24, 8, 0, None)
        if not self.ctx:
            raise GLContextError('OSMesaCreateContextExt 失败')
        if not osmesa.OSMesaMakeCurrent(self.ctx, self.buffer, GL.GL_UNSIGNED_BYTE,
                                        width, height):
            raise GLContextError('OSMesaMakeCurrent 失败')

    def make_current(self):
        self.osmesa.OSMesaMakeCurrent(self.ctx, self.buffer, self.GL.GL_UNSIGNED_BYTE,
                                      self.w, self.h)

    def resize(self, w, h):
        self.w, self.h = w, h
        self.buffer = np.zeros((h, w, 4), np.uint8)
        self.make_current()

    def read_pixels(self) -> np.ndarray:
        GL = self.GL
        GL.glFinish()
        data = GL.glReadPixels(0, 0, self.w, self.h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        arr = np.frombuffer(data, np.uint8).reshape(self.h, self.w, 4)
        return arr[::-1].copy()                       # OpenGL 原点在左下

    def info(self):
        GL = self.GL
        return {'backend': 'osmesa',
                'version': GL.glGetString(GL.GL_VERSION).decode(),
                'renderer': GL.glGetString(GL.GL_RENDERER).decode(),
                'glsl': GL.glGetString(GL.GL_SHADING_LANGUAGE_VERSION).decode()}


class ExistingContext:
    """使用调用方已经绑定的当前上下文（例如 Qt 的 QOpenGLWidget，或 EGL/WGL/GLX）。"""

    name = 'existing'

    def __init__(self, width, height, readback=True):
        import OpenGL.GL as GL
        self.GL = GL
        self.w, self.h = width, height
        self.readback = readback

    def make_current(self):
        pass

    def resize(self, w, h):
        self.w, self.h = w, h

    def read_pixels(self):
        if not self.readback:                 # Qt 直绘模式：内容已在屏幕帧缓冲，免回读
            return np.zeros((1, 1, 4), np.uint8)
        GL = self.GL
        GL.glFinish()
        data = GL.glReadPixels(0, 0, self.w, self.h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        arr = np.frombuffer(data, np.uint8).reshape(self.h, self.w, 4)
        return arr[::-1].copy()

    def info(self):
        GL = self.GL
        return {'backend': 'existing',
                'version': GL.glGetString(GL.GL_VERSION).decode(),
                'renderer': GL.glGetString(GL.GL_RENDERER).decode()}


def make_context(prefer=('egl', 'osmesa'), width=420, height=680):
    """创建离屏 GL 上下文：EGL（真 GPU）优先，OSMesa（软件 GL）兜底。"""
    forced = os.environ.get('XIAOLING_GL_CONTEXT', '').strip().lower()
    if forced in ('egl', 'osmesa'):
        prefer = (forced,)
    for kind in prefer:
        try:
            if kind == 'egl':
                return EGLContext(width, height)
            if kind == 'osmesa':
                return OSMesaContext(width, height)
        except GLContextError:
            continue
    raise GLContextError('没有可用的 OpenGL 上下文')


# --------------------------------------------------------------------- 渲染器
MAX_BONES = 160


class GLRenderer:
    """把 VRMModel 画到 OpenGL。每帧只更新骨矩阵与被改动的顶点。"""

    def __init__(self, model, context, background=(0, 0, 0, 0)):
        self.model = model
        self.ctx = context
        GL = context.GL
        self.GL = GL
        self.background = background
        self.program = self._build_program()
        self.uniforms = {n: GL.glGetUniformLocation(self.program, n) for n in
                         ('u_viewProj', 'u_bones', 'u_skinned', 'u_tex', 'u_color', 'u_shade',
                          'u_light', 'u_has_tex', 'u_unlit', 'u_rim', 'u_cutoff')}
        self.buffers = []
        self._morph_state = {}
        self._upload_all()

    # ------------------------------------------------------------ 着色器
    def _build_program(self):
        GL = self.GL

        def compile_shader(src, kind):
            sh = GL.glCreateShader(kind)
            GL.glShaderSource(sh, src)
            GL.glCompileShader(sh)
            if not GL.glGetShaderiv(sh, GL.GL_COMPILE_STATUS):
                raise GLContextError('着色器编译失败：' + GL.glGetShaderInfoLog(sh).decode())
            return sh
        vs = compile_shader(VERT_SRC, GL.GL_VERTEX_SHADER)
        fs = compile_shader(FRAG_SRC, GL.GL_FRAGMENT_SHADER)
        prog = GL.glCreateProgram()
        GL.glAttachShader(prog, vs)
        GL.glAttachShader(prog, fs)
        GL.glLinkProgram(prog)
        if not GL.glGetProgramiv(prog, GL.GL_LINK_STATUS):
            raise GLContextError('着色器链接失败：' + GL.glGetProgramInfoLog(prog).decode())
        return prog

    # ------------------------------------------------------------ 资源上传
    def _upload_all(self):
        GL = self.GL
        self.buffers = []
        for prim in self.model.primitives:
            mat = (self.model.materials[prim.material]
                   if 0 <= prim.material < len(self.model.materials) else None)
            if mat is None:
                continue
            n = len(prim.positions)
            joints = (prim.joints.astype(np.float32) if prim.joints is not None
                      else np.zeros((n, 4), np.float32))
            weights = (prim.weights.astype(np.float32) if prim.weights is not None
                       else np.zeros((n, 4), np.float32))
            if prim.weights is not None:
                s = weights.sum(1, keepdims=True)
                weights = np.divide(weights, np.maximum(s, 1e-6))
            # 顶点数据拆成两个缓冲：
            #   ① 位置独立（表情形变要逐帧局部更新，不能破坏交错布局）
            #   ② 法线/UV/骨骼索引/权重交错（静态）
            nrm_uv_j_w = np.concatenate([prim.normals, prim.uvs, joints, weights],
                                        axis=1).astype(np.float32)
            ctx_v = GL.glGenVertexArrays(1)
            GL.glBindVertexArray(ctx_v)
            vbo_pos = GL.glGenBuffers(1)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo_pos)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, prim.positions.nbytes, prim.positions,
                            GL.GL_DYNAMIC_DRAW)
            GL.glEnableVertexAttribArray(0)
            GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, GL.GL_FALSE, 12, ctypes.c_void_p(0))
            vbo = GL.glGenBuffers(1)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, nrm_uv_j_w.nbytes, nrm_uv_j_w,
                            GL.GL_DYNAMIC_DRAW)
            stride = 13 * 4                     # nrm3 + uv2 + joints4 + weights4
            for loc, size, off in ((1, 3, 0), (2, 2, 12), (3, 4, 20), (4, 4, 36)):
                GL.glEnableVertexAttribArray(loc)
                GL.glVertexAttribPointer(loc, size, GL.GL_FLOAT, GL.GL_FALSE, stride,
                                         ctypes.c_void_p(off))
            ibo = GL.glGenBuffers(1)
            GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, ibo)
            idx = prim.indices.reshape(-1).astype(np.uint32)
            GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx, GL.GL_STATIC_DRAW)
            tex = None
            if mat.texture is not None:
                img = mat.texture.astype(np.uint8)
                tex = GL.glGenTextures(1)
                GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
                GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, img.shape[1], img.shape[0], 0,
                                GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, img)
                # 不使用 mipmap：部分软件 GL（llvmpipe/旧驱动）在此处不稳定，
                # 且桌宠是小画布，双线性足够。
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT)
            GL.glBindVertexArray(0)
            self.buffers.append({'prim': prim, 'mat': mat, 'vao': ctx_v, 'vbo': vbo,
                                 'vbo_pos': vbo_pos, 'ibo': ibo, 'count': len(idx),
                                 'tex': tex, 'n': n})

    def update_morphs(self, prim_index: int, weights: dict):
        """表情形变：只重传该图元的位置（法线保持基础值，视觉差异极小）。"""
        key = (prim_index, tuple(sorted((k, round(v, 3)) for k, v in (weights or {}).items())))
        if self._morph_state.get(prim_index) == key:
            return
        self._morph_state[prim_index] = key
        buf = next((b for b in self.buffers if b['prim'].index == prim_index), None)
        if buf is None:
            return
        prim = buf['prim']
        pos, _nrm = apply_morphs(prim, weights or {})
        GL = self.GL
        pos = np.ascontiguousarray(pos, np.float32)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, buf['vbo_pos'])   # 只更新位置缓冲
        GL.glBufferSubData(GL.GL_ARRAY_BUFFER, 0, pos.nbytes, pos)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)

    # ------------------------------------------------------------ 每帧绘制
    def draw(self, pose, view_proj: np.ndarray, morph_map: dict | None = None,
             clear=True, light=(0.35, 0.45, 0.82), rim=True, force_unskinned=False):
        GL = self.GL
        pose.update_world()
        if morph_map:
            for pi, w in morph_map.items():
                self.update_morphs(pi, w)
        if clear:
            GL.glClearColor(*self.background)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glUseProgram(self.program)
        u = self.uniforms
        GL.glUniformMatrix4fv(u['u_viewProj'], 1, GL.GL_FALSE,
                              np.ascontiguousarray(view_proj.T, np.float32))
        light = np.asarray(light, np.float32)
        light = light / max(float(np.linalg.norm(light)), 1e-6)
        GL.glUniform3f(u['u_light'], *[float(x) for x in light])
        GL.glUniform1i(u['u_tex'], 0)
        GL.glUniform1i(u['u_rim'], 1 if rim else 0)

        # 半透明图元后画（远→近）
        order = sorted(self.buffers,
                       key=lambda b: 0 if b['mat'].alpha_mode != 'BLEND' else 1)
        blend_stack = [b for b in order if b['mat'].alpha_mode == 'BLEND']
        if blend_stack:
            def depth_of(b):
                # 用（未蒙皮的）图元重心深度做远→近排序：小画布下足够，且零成本
                return float(b['prim'].positions[:, 2].mean())
            blend_stack.sort(key=depth_of, reverse=True)
            order = [b for b in order if b['mat'].alpha_mode != 'BLEND'] + blend_stack

        for b in order:
            mat, prim = b['mat'], b['prim']
            skinned = (prim.joints is not None and len(self.model.skins) > 0
                       and not force_unskinned)
            mats = (self._bone_matrices(pose, 0) if skinned
                    else np.eye(4, dtype=np.float32)[None])
            nb = mats.shape[0]
            pad = np.tile(np.eye(4, dtype=np.float32), (max(MAX_BONES - nb, 0), 1, 1))
            allm = np.concatenate([mats, pad], 0)[:MAX_BONES]
            GL.glUniformMatrix4fv(u['u_bones'], MAX_BONES, GL.GL_FALSE,
                                  np.ascontiguousarray(allm.transpose(0, 2, 1).reshape(-1, 16),
                                                       np.float32))
            GL.glUniform1i(u['u_skinned'], 1 if skinned else 0)
            GL.glUniform4f(u['u_color'], float(mat.color[0]), float(mat.color[1]),
                           float(mat.color[2]), float(mat.color[3]))
            GL.glUniform3f(u['u_shade'], float(mat.shade[0]), float(mat.shade[1]),
                           float(mat.shade[2]))
            GL.glUniform1i(u['u_unlit'], 1 if mat.unlit else 0)
            GL.glUniform1f(u['u_cutoff'], float(mat.cutoff) if mat.alpha_mode == 'MASK' else 0.02)
            if b['tex'] is not None:
                GL.glActiveTexture(GL.GL_TEXTURE0)
                GL.glBindTexture(GL.GL_TEXTURE_2D, b['tex'])
                GL.glUniform1i(u['u_has_tex'], 1)
            else:
                GL.glUniform1i(u['u_has_tex'], 0)
            if mat.double_sided:
                GL.glDisable(GL.GL_CULL_FACE)
            else:
                GL.glEnable(GL.GL_CULL_FACE)
                GL.glCullFace(GL.GL_BACK)
            if mat.alpha_mode == 'BLEND':
                GL.glDepthMask(GL.GL_FALSE)
            else:
                GL.glDepthMask(GL.GL_TRUE)
            GL.glBindVertexArray(b['vao'])
            GL.glDrawElements(GL.GL_TRIANGLES, b['count'], GL.GL_UNSIGNED_INT, None)
        GL.glBindVertexArray(0)
        GL.glDepthMask(GL.GL_TRUE)

    def _bone_matrices(self, pose, skin_index):
        """返回 (N,4,4) 骨骼蒙皮矩阵（行主序）。"""
        skin = self.model.skins[skin_index] if skin_index < len(self.model.skins) else None
        if skin is None:
            return np.eye(4, dtype=np.float32)[None]
        mats = np.zeros((len(skin['joints']), 4, 4), np.float32)
        for k, node in enumerate(skin['joints']):
            m = pose.world[node] if node < len(pose.world) else self.model.rest_world[node]
            ibm = skin['ibm'][k] if skin['ibm'] is not None else np.eye(4, dtype=np.float32)
            mats[k] = m @ ibm
        return mats

    def info(self) -> dict:
        return self.ctx.info()

    def set_background(self, rgba):
        self.background = tuple(float(x) for x in rgba)
