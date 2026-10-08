"""小凌 · 终端会话管理（TerminalManager）
==========================================

管理多个后台 shell 终端会话：
  * create()  -> 启动一个 /bin/bash 伪终端（PTY）会话，返回 session_id
  * write()   -> 向 PTY 写入原始字节（支持 vim/htop/top 等交互式程序）
  * read()    -> 生成器，持续产出 PTY 输出直到会话关闭
  * close()   -> 关闭 PTY 文件描述符并回收子进程
  * resize()  -> 调整终端窗口尺寸（rows, cols）

基于 pty.fork() 创建真正的伪终端，支持交互式 TUI 程序、终端尺寸
调整和信号转发。后台线程通过 select 监听 PTY 文件描述符，将输出
写入队列，read() 生成器从队列消费，实现非阻塞、可持续的终端输出流。
所有操作均有异常保护，会话不存在时返回空 / False，绝不抛出。
"""
from __future__ import annotations

import os
import queue
import select
import struct
import subprocess
import threading
import uuid

# PTY 相关模块仅在 Unix 上可用；Windows 下降级到管道模式
try:
    import pty
    import fcntl
    import termios
    _PTY_AVAILABLE = os.name != "nt"
except ImportError:
    pty = None          # type: ignore
    fcntl = None        # type: ignore
    termios = None      # type: ignore
    _PTY_AVAILABLE = False


class TerminalManager:
    """多会话 shell 终端管理器（真 PTY）。"""

    def __init__(self):
        # session_id -> {pid, fd, queue, thread, closed, fallback_process}
        self._sessions: dict[str, dict] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ create
    def create(self) -> str:
        """启动一个新的 shell 伪终端会话，返回 session_id (uuid)。失败返回空串。"""
        session_id = uuid.uuid4().hex
        try:
            shell = "/bin/bash" if os.name != "nt" else "cmd.exe"
            q: queue.Queue = queue.Queue()
            holder = {"pid": None, "fd": None, "queue": q,
                      "thread": None, "closed": False, "fallback_process": None}

            if _PTY_AVAILABLE:
                # ---- 真 PTY 模式 ----
                pid, fd = pty.fork()
                if pid == 0:
                    # 子进程：执行 shell，继承 PTY 作为 stdin/stdout/stderr
                    try:
                        os.execvp(shell, [shell, "-l"])
                    except Exception:
                        os._exit(127)
                # 父进程：pid > 0，fd 是 PTY master
                holder["pid"] = pid
                holder["fd"] = fd

                def _pump():
                    try:
                        while True:
                            # select 监听 fd 是否可读，0.2s 超时以便周期性检查 closed
                            r, _, _ = select.select([fd], [], [], 0.2)
                            if not r:
                                with self._lock:
                                    if self._sessions.get(session_id, {}).get("closed"):
                                        break
                                continue
                            try:
                                chunk = os.read(fd, 4096)
                            except OSError:
                                break
                            if not chunk:
                                break
                            try:
                                q.put(chunk.decode("utf-8", errors="replace"))
                            except Exception:
                                break
                    except Exception:
                        pass
                    finally:
                        with self._lock:
                            if session_id in self._sessions:
                                self._sessions[session_id]["closed"] = True
            else:
                # ---- Windows / 降级：管道模式 ----
                process = subprocess.Popen(
                    shell,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                holder["fallback_process"] = process

                def _pump():
                    try:
                        assert process.stdout is not None
                        for line in iter(process.stdout.readline, ""):
                            if not line:
                                break
                            try:
                                q.put(line)
                            except Exception:
                                break
                    except Exception:
                        pass
                    finally:
                        try:
                            process.stdout.close()
                        except Exception:
                            pass
                        with self._lock:
                            if session_id in self._sessions:
                                self._sessions[session_id]["closed"] = True

            t = threading.Thread(target=_pump, daemon=True)
            holder["thread"] = t
            with self._lock:
                self._sessions[session_id] = holder
            t.start()
            return session_id
        except Exception as e:  # noqa: BLE001
            print(f"  [Terminal] create 失败：{type(e).__name__}: {e}")
            return ""

    # ------------------------------------------------------------------ write
    def write(self, session_id: str, data: str) -> bool:
        """向指定会话写入数据（PTY 原始字节透传）。会话不存在返回 False。"""
        try:
            with self._lock:
                holder = self._sessions.get(session_id)
            if not holder:
                return False
            fd = holder.get("fd")
            if fd is not None:
                # 真 PTY：直接写入原始字节
                os.write(fd, data.encode("utf-8"))
                return True
            # 降级管道模式
            process = holder.get("fallback_process")
            if process is None or process.stdin is None:
                return False
            if not data.endswith("\n"):
                data = data + "\n"
            process.stdin.write(data)
            process.stdin.flush()
            return True
        except Exception as e:  # noqa: BLE001
            print(f"  [Terminal] write 失败：{type(e).__name__}: {e}")
            return False

    # ------------------------------------------------------------------- read
    def read(self, session_id: str):
        """生成器：从会话输出队列逐块 yield 文本，直到 closed 且队列排空。"""
        try:
            with self._lock:
                holder = self._sessions.get(session_id)
            if not holder:
                return
            q = holder["queue"]
            while True:
                try:
                    line = q.get(timeout=0.2)
                except queue.Empty:
                    with self._lock:
                        closed = self._sessions.get(session_id, {}).get("closed", False)
                    if closed and q.empty():
                        break
                    continue
                if line:
                    yield line
                with self._lock:
                    closed = self._sessions.get(session_id, {}).get("closed", False)
                if closed and q.empty():
                    break
        except Exception as e:  # noqa: BLE001
            print(f"  [Terminal] read 失败：{type(e).__name__}: {e}")
            return

    # ------------------------------------------------------------------ close
    def close(self, session_id: str) -> bool:
        """关闭指定会话：关闭 PTY fd 并回收子进程。会话不存在返回 False。"""
        try:
            with self._lock:
                holder = self._sessions.get(session_id)
            if not holder:
                return False
            # 标记关闭，通知 pump 线程退出
            with self._lock:
                holder["closed"] = True
            # 关闭 PTY 文件描述符
            fd = holder.get("fd")
            pid = holder.get("pid")
            try:
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            except Exception:
                pass
            try:
                if pid is not None:
                    # 非阻塞回收子进程
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        pass
            except Exception:
                pass
            # 降级模式：终止管道子进程
            process = holder.get("fallback_process")
            try:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except Exception:
                        process.kill()
            except Exception:
                pass
            return True
        except Exception as e:  # noqa: BLE001
            print(f"  [Terminal] close 失败：{type(e).__name__}: {e}")
            return False

    # ------------------------------------------------------------------ resize
    def resize(self, session_id: str, rows: int = 24, cols: int = 80) -> bool:
        """调整终端窗口尺寸（PTY TIOCSWINSZ）。会话不存在返回 False。"""
        try:
            if not _PTY_AVAILABLE or fcntl is None or termios is None:
                return False
            with self._lock:
                holder = self._sessions.get(session_id)
            if not holder:
                return False
            fd = holder.get("fd")
            if fd is None:
                return False
            # struct winsize { unsigned short ws_row, ws_col, ws_xpixel, ws_ypixel; }
            winsize = struct.pack("HHHH", int(rows), int(cols), 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"  [Terminal] resize 失败：{type(e).__name__}: {e}")
            return False

    # --------------------------------------------------------------- utilities
    def list_sessions(self) -> list:
        """返回当前所有会话 id 列表。"""
        with self._lock:
            return list(self._sessions.keys())

    def shutdown(self):
        """关闭所有会话。"""
        with self._lock:
            ids = list(self._sessions.keys())
        for sid in ids:
            try:
                self.close(sid)
            except Exception:
                pass
