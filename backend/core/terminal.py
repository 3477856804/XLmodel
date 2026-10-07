"""小凌 · 终端会话管理（TerminalManager）
==========================================

管理多个后台 shell 终端会话：
  * create()  -> 启动一个 /bin/bash (Windows 下 cmd.exe) 子进程，返回 session_id
  * write()   -> 向子进程 stdin 写入命令
  * read()    -> 生成器，持续产出子进程 stdout 输出直到会话关闭
  * close()   -> 终止子进程

后台线程逐行读取子进程 stdout 写入队列，read() 生成器从队列消费，
实现非阻塞、可持续的终端输出流。所有操作均有异常保护，会话不存在时
返回空 / False，绝不抛出。
"""
from __future__ import annotations

import os
import queue
import subprocess
import threading
import uuid


class TerminalManager:
    """多会话 shell 终端管理器。"""

    def __init__(self):
        # session_id -> {process, queue, thread, closed}
        self._sessions: dict[str, dict] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ create
    def create(self) -> str:
        """启动一个新的 shell 子进程，返回 session_id (uuid)。失败返回空串。"""
        session_id = uuid.uuid4().hex
        try:
            shell = "/bin/bash" if os.name != "nt" else "cmd.exe"
            process = subprocess.Popen(
                shell,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            q: queue.Queue = queue.Queue()
            holder = {"process": process, "queue": q,
                      "thread": None, "closed": False}

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
        """向指定会话的 stdin 写入数据并 flush。会话不存在返回 False。"""
        try:
            with self._lock:
                holder = self._sessions.get(session_id)
            if not holder:
                return False
            process = holder.get("process")
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
        """生成器：从会话输出队列逐行 yield 文本，直到 closed 且队列排空。"""
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
        """终止指定会话的子进程并标记 closed。会话不存在返回 False。"""
        try:
            with self._lock:
                holder = self._sessions.get(session_id)
            if not holder:
                return False
            process = holder.get("process")
            try:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except Exception:
                        process.kill()
            except Exception:
                pass
            with self._lock:
                holder["closed"] = True
            return True
        except Exception as e:  # noqa: BLE001
            print(f"  [Terminal] close 失败：{type(e).__name__}: {e}")
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
