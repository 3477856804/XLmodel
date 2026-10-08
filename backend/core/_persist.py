# -*- coding: utf-8 -*-
"""去抖持久化（debounced persistence）。

问题
----
原实现里，活动日志、长期记忆等在**每一次新增**时都做一次**全量序列化 +
整文件重写**（最多几千条记录）。而一次对话会触发多条新增（用户/助手/知识/
索引），导致每聊一句就把同一个 JSON 文件整块写好几遍 —— 这是典型的
"不必要全量写"，既拖慢对话响应，又放大磁盘 IO 与写磨损。

方案
----
把"立即全量落盘"改成三段式：

1. 写入时只在内存追加，并把对象标记为 dirty；
2. 距离上次落盘不足 ``interval`` 秒时**不立刻写盘**，把多次新增合并；
3. 一个守护线程每 ``interval`` 秒兜底 flush 一次所有脏对象，保证
   崩溃丢失窗口有界（≈ interval 秒）。

显式调用 ``flush()`` 仍然立即落盘（测试、关闭、清空等语义不变）。

线程模型
--------
* 注册表是进程级单例；守护线程只持有注册表锁的极短临界区；
* 真正的 flush 回调在调用方自己的锁里执行（调用方自行 RLock 可重入）；
* 任何 flush 异常都被吞掉，绝不影响对话主流程。
"""
from __future__ import annotations

import threading
import time


class _Registry:
    """进程级持久化回调注册表 + 一个兜底 flush 守护线程。"""

    def __init__(self, interval: float = 2.0):
        self._interval = interval
        self._lock = threading.RLock()
        self._callbacks: dict = {}
        self._thread: threading.Thread | None = None
        self._stop = False

    def register(self, key, flush_fn) -> None:
        try:
            with self._lock:
                self._callbacks[key] = flush_fn
                self._ensure_thread_locked()
        except Exception:
            pass

    def unregister(self, key) -> None:
        try:
            with self._lock:
                self._callbacks.pop(key, None)
        except Exception:
            pass

    def _ensure_thread_locked(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        try:
            self._thread = threading.Thread(
                target=self._loop, name="persist-flush", daemon=True)
            self._thread.start()
        except Exception:
            self._thread = None

    def _loop(self) -> None:
        while not self._stop:
            try:
                time.sleep(self._interval)
            except Exception:
                return
            try:
                with self._lock:
                    fns = list(self._callbacks.values())
            except Exception:
                fns = []
            for fn in fns:
                try:
                    fn()
                except Exception:
                    continue


_REGISTRY = _Registry(interval=2.0)


def register(key, flush_fn) -> None:
    """注册一个周期 flush 回调（通常是某对象的 flush 方法）。"""
    try:
        _REGISTRY.register(key, flush_fn)
    except Exception:
        pass


def unregister(key) -> None:
    try:
        _REGISTRY.unregister(key)
    except Exception:
        pass


class DebouncedSaver:
    """通用去抖保存器：多次 mark_dirty 合并为一次 do_save。

    Parameters
    ----------
    do_save:
        真正执行落盘的无参回调（调用方保证线程安全/可重入）。
    interval:
        最小落盘间隔（秒）。距上次落盘不足该时间时只标记 dirty。
    key:
        若提供，则把 ``flush`` 注册进进程级兜底线程。
    """

    def __init__(self, do_save, interval: float = 2.0, key=None):
        self._do_save = do_save
        self._interval = max(0.2, float(interval))
        self._dirty = False
        self._last = 0.0
        self._lock = threading.RLock()
        try:
            if key is not None:
                register(key, self.flush)
        except Exception:
            pass

    def mark_dirty(self) -> None:
        """标记脏；距上次落盘超过 interval 则立即合并落盘。"""
        try:
            with self._lock:
                self._dirty = True
                now = time.time()
                if now - self._last >= self._interval:
                    self._last = now
                    self._do_save()
                    self._dirty = False
        except Exception:
            pass

    def flush(self) -> None:
        """强制落盘（仅当 dirty）。异常不外抛。"""
        try:
            with self._lock:
                if self._dirty:
                    self._last = time.time()
                    self._do_save()
                    self._dirty = False
        except Exception:
            pass

    @property
    def is_dirty(self) -> bool:
        try:
            return self._dirty
        except Exception:
            return False
