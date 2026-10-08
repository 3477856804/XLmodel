"""小凌 · MCP（Model Context Protocol）客户端

健壮性设计（v0.0.1）：
  * 工具调用结果缓存：相同 (server, tool, arguments) 在 CACHE_TTL 秒内直接返回缓存；
  * 错误重试：仅网络/超时类错误按指数退避重试 MAX_RETRIES 次；参数类错误（JSON-RPC
    -32601/-32602/-32603）不重试；
  * 连接健康检查：MCPServer.ping() / MCPManager.is_connected(server_name)；
  * 配置持久化：服务器列表保存到 JSON 文件，重启后 _load_config 自动恢复；
  * 超时控制：所有 JSON-RPC 调用统一 TOOL_CALL_TIMEOUT 秒，避免挂起；
  * 日志记录：每次调用记录成功/失败与耗时（ms）。
"""
import json
import logging
import threading
import time
from pathlib import Path

import requests

from .config import DATA_DIR

logger = logging.getLogger(__name__)

MCP_CONFIG_PATH = DATA_DIR / "mcp_servers.json"

# ---- 全局可调参数 ----
TOOL_CALL_TIMEOUT = 30.0   # 所有工具调用超时（秒）
CACHE_TTL = 300.0          # 工具结果缓存时长（秒，5 分钟）
MAX_RETRIES = 2            # 网络错误额外重试次数（不含首次）


class MCPTransportError(Exception):
    """传输层错误：连接失败 / 超时 / 子进程退出 / 5xx。可重试。"""


class MCPRequestError(Exception):
    """业务请求错误：工具不存在 / 参数错误等。不可重试。"""


class MCPServer:
    """单个 MCP 服务器连接，支持 stdio 与 streamable-http 两种传输。"""

    PROTOCOL_VERSION = "2024-11-05"
    # JSON-RPC 业务错误码中视为「参数/调用方错误」的，不重试
    _NON_RETRY_CODES = {-32601, -32602, -32603}

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config or {}
        self.tools: list[dict] = []
        self.connected = False
        self.last_error = ""
        self._process = None
        self._msg_id = 0
        self._pending: dict[int, dict] = {}
        self._lock = threading.Lock()
        self._read_thread = None

    @property
    def transport(self) -> str:
        return self.config.get("type", "stdio")

    def connect(self) -> bool:
        """连接 MCP 服务器，完成 initialize 握手并拉取工具列表。"""
        self.last_error = ""
        t0 = time.monotonic()
        try:
            if self.transport == "stdio":
                self._connect_stdio()
            else:
                self._connect_http()
            self.connected = True
            logger.info(
                "[mcp_client] 服务器 %s 连接成功，工具数=%d，耗时%.0fms",
                self.name, len(self.tools), (time.monotonic() - t0) * 1000)
            return True
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.connected = False
            logger.warning("[mcp_client] 服务器 %s 连接失败: %s", self.name, self.last_error)
            return False

    def _connect_stdio(self):
        """启动子进程并后台读取 stdout。"""
        cmd = self.config.get("command", "")
        args = self.config.get("args", []) or []
        if not cmd:
            raise MCPRequestError("缺少 command")
        import subprocess
        self._process = subprocess.Popen(
            [cmd] + list(args),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
        self._do_handshake()

    def _connect_http(self):
        """HTTP 模式直接发请求。"""
        url = self.config.get("url", "")
        if not url:
            raise MCPRequestError("缺少 url")
        self._do_handshake()

    def _do_handshake(self):
        """发送 initialize → notifications/initialized → tools/list。"""
        init_params = {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "xiaoling", "version": "0.0.1"},
        }
        result = self._send_request("initialize", init_params)
        if result is None:
            raise MCPTransportError("initialize 无响应")
        try:
            self._send_notification("notifications/initialized", {})
        except Exception as e:
            logger.warning(f"[mcp_client] 发送 initialized 通知失败: {e}")
        tools_result = self._send_request("tools/list", {})
        tools = []
        if isinstance(tools_result, dict):
            for t in tools_result.get("tools", []):
                tools.append({
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "inputSchema": t.get("inputSchema", {}),
                })
        self.tools = tools

    def _read_loop(self):
        """从 stdio stdout 逐行读取 JSON-RPC 消息，匹配 pending 请求。"""
        if not self._process or not self._process.stdout:
            return
        try:
            for line in self._process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if "id" in msg and msg["id"] in self._pending:
                    slot = self._pending.get(msg["id"])
                    if slot is not None:
                        slot["result"] = msg.get("result")
                        slot["error"] = msg.get("error")
                        slot["event"].set()
        except (ValueError, OSError) as e:
            logger.warning(f"[mcp_client] 读取子进程输出循环退出: {e}")

    def _next_id(self) -> int:
        with self._lock:
            self._msg_id += 1
            return self._msg_id

    def _raise_for_rpc_error(self, err):
        """把 JSON-RPC error 分类为可重试 / 不可重试。"""
        if not err:
            return
        code = err.get("code") if isinstance(err, dict) else None
        message = err.get("message", err) if isinstance(err, dict) else err
        if code in self._NON_RETRY_CODES:
            raise MCPRequestError(f"JSON-RPC 业务错误(code={code}): {message}")
        raise MCPTransportError(f"JSON-RPC 服务端错误(code={code}): {message}")

    def _send_request(self, method: str, params=None, timeout: float = TOOL_CALL_TIMEOUT):
        """发送 JSON-RPC 请求并等待结果。传输错误抛 MCPTransportError。"""
        msg_id = self._next_id()
        event = threading.Event()
        slot = {"event": event, "result": None, "error": None}
        self._pending[msg_id] = slot
        try:
            msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
            if params is not None:
                msg["params"] = params
            if self.transport == "stdio":
                if not self._process or not self._process.stdin:
                    raise MCPTransportError("子进程未启动")
                try:
                    self._process.stdin.write(json.dumps(msg) + "\n")
                    self._process.stdin.flush()
                except (OSError, ValueError) as e:
                    raise MCPTransportError(f"写入 stdin 失败: {e}")
                ok = event.wait(timeout=timeout)
                if not ok:
                    raise MCPTransportError(f"{method} 等待响应超时({timeout}s)")
                self._raise_for_rpc_error(slot["error"])
                return slot["result"]
            else:
                url = self.config.get("url", "")
                headers = self.config.get("headers", {}) or {}
                try:
                    resp = requests.post(url, json=msg, headers=headers, timeout=timeout)
                    resp.raise_for_status()
                    data = resp.json()
                except requests.Timeout as e:
                    raise MCPTransportError(f"{method} HTTP 超时: {e}")
                except requests.ConnectionError as e:
                    raise MCPTransportError(f"{method} 连接失败: {e}")
                except requests.RequestException as e:
                    # 4xx 多为调用方错误，但无法精确区分时按传输错误处理（有限重试）
                    raise MCPTransportError(f"{method} HTTP 请求失败: {e}")
                except ValueError as e:
                    raise MCPTransportError(f"{method} 响应非 JSON: {e}")
                self._raise_for_rpc_error(data.get("error"))
                return data.get("result")
        finally:
            self._pending.pop(msg_id, None)

    def _send_notification(self, method: str, params=None):
        """发送 JSON-RPC 通知（无需响应）。"""
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if self.transport == "stdio":
            if self._process and self._process.stdin:
                try:
                    self._process.stdin.write(json.dumps(msg) + "\n")
                    self._process.stdin.flush()
                except (OSError, ValueError) as e:
                    logger.warning(f"[mcp_client] stdio 通知发送失败: {e}")
        else:
            url = self.config.get("url", "")
            headers = self.config.get("headers", {}) or {}
            try:
                requests.post(url, json=msg, headers=headers, timeout=10)
            except requests.RequestException as e:
                logger.warning(f"[mcp_client] HTTP 通知发送失败 {url}: {e}")

    def call_tool(self, tool_name: str, arguments: dict | None = None) -> str:
        """调用 MCP 工具，返回结果文本。传输错误抛 MCPTransportError。"""
        result = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })
        if isinstance(result, dict):
            content = result.get("content", [])
            parts = []
            for c in content:
                if isinstance(c, dict) and "text" in c:
                    parts.append(c["text"])
            if parts:
                return "\n".join(parts)
            return json.dumps(result, ensure_ascii=False)
        return str(result) if result is not None else ""

    def ping(self) -> bool:
        """轻量健康检查：服务器是否仍在响应。

        stdio：子进程未退出即视为在线；http：发起一次短超时 tools/list。
        """
        try:
            if self.transport == "stdio":
                return self._process is not None and self._process.poll() is None
            self._send_request("tools/list", {}, timeout=min(5.0, TOOL_CALL_TIMEOUT))
            return True
        except Exception as e:
            logger.debug("[mcp_client] ping %s 失败: %s", self.name, e)
            return False

    def disconnect(self):
        """断开连接，终止子进程。"""
        try:
            if self._process:
                self._process.terminate()
                try:
                    self._process.wait(timeout=3)
                except Exception:
                    self._process.kill()
        except Exception as e:
            logger.warning(f"[mcp_client] 断开连接时出错: {e}")
        finally:
            self._process = None
            self.connected = False
            self.tools = []


class MCPManager:
    """管理所有 MCP 服务器连接与配置。"""

    def __init__(self, config_path: str | None = None, auto_connect: bool = False):
        self.config_path = Path(config_path) if config_path else MCP_CONFIG_PATH
        self.servers: dict[str, MCPServer] = {}
        self._lock = threading.RLock()
        self._config: list[dict] = []
        # 工具结果缓存：key -> (expire_at, result_text)
        self._cache: dict[str, tuple[float, str]] = {}
        self._cache_lock = threading.Lock()
        self._load_config()
        if auto_connect:
            try:
                self.connect_all()
            except Exception as e:
                logger.warning(f"[mcp_client] 自动恢复连接失败: {e}")

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def _load_config(self):
        """从 JSON 文件加载服务器配置（重启后自动恢复）。"""
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "servers" in data:
                    self._config = [s for s in data["servers"] if isinstance(s, dict)]
                elif isinstance(data, list):
                    self._config = [s for s in data if isinstance(s, dict)]
            else:
                self._config = []
        except Exception as e:
            logger.warning(f"[mcp_client] 加载 MCP 配置失败，使用空配置: {e}")
            self._config = []

    def _save_config(self):
        """持久化配置到 JSON 文件。"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {"servers": list(self._config)}
            self.config_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning(f"[mcp_client] 保存 MCP 配置失败: {e}")

    # ------------------------------------------------------------------
    # 缓存
    # ------------------------------------------------------------------
    @staticmethod
    def _cache_key(server_name: str, tool_name: str, arguments: dict) -> str:
        try:
            payload = json.dumps(arguments or {}, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            payload = str(arguments)
        return f"{server_name}|{tool_name}|{payload}"

    def _cache_get(self, key: str) -> str | None:
        try:
            now = time.time()
            with self._cache_lock:
                # 顺手清理过期项
                expired = [k for k, (exp, _) in self._cache.items() if exp <= now]
                for k in expired:
                    self._cache.pop(k, None)
                item = self._cache.get(key)
                if item is None:
                    return None
                exp, result = item
                if exp <= now:
                    self._cache.pop(key, None)
                    return None
                return result
        except Exception:
            return None

    def _cache_put(self, key: str, result: str, ttl: float = CACHE_TTL):
        try:
            with self._cache_lock:
                self._cache[key] = (time.time() + ttl, result)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 服务器增删查
    # ------------------------------------------------------------------
    def add_server(self, name: str, config: dict) -> bool:
        """添加服务器配置，返回是否成功。"""
        with self._lock:
            for i, s in enumerate(self._config):
                if s.get("name") == name:
                    self._config[i] = {"name": name, **config}
                    self._save_config()
                    return True
            self._config.append({"name": name, "enabled": True, **config})
            self._save_config()
            return True

    def remove_server(self, name: str) -> bool:
        """删除服务器配置并断开连接。"""
        with self._lock:
            before = len(self._config)
            self._config = [s for s in self._config if s.get("name") != name]
            changed = len(self._config) < before
        if changed:
            self._save_config()
        if name in self.servers:
            try:
                self.servers[name].disconnect()
            except Exception as e:
                logger.warning(f"[mcp_client] 删除服务器 {name} 时断开连接失败: {e}")
            del self.servers[name]
        return changed

    def connect_server(self, name: str) -> bool:
        """连接指定服务器。"""
        cfg = None
        with self._lock:
            for s in self._config:
                if s.get("name") == name:
                    cfg = dict(s)
                    break
        if cfg is None:
            return False
        if name in self.servers and self.servers[name].connected:
            return True
        server = MCPServer(name, cfg)
        ok = server.connect()
        if ok:
            self.servers[name] = server
        return ok

    def disconnect_server(self, name: str):
        """断开指定服务器。"""
        if name in self.servers:
            self.servers[name].disconnect()
            del self.servers[name]

    def connect_all(self):
        """连接所有 enabled 的服务器。"""
        with self._lock:
            names = [s.get("name") for s in self._config
                     if s.get("enabled", True) and s.get("name")]
        for name in names:
            try:
                self.connect_server(name)
            except Exception as e:
                logger.warning(f"[mcp_client] 连接服务器 {name} 失败: {e}")

    def list_servers(self) -> list[dict]:
        """返回所有服务器状态列表。"""
        with self._lock:
            cfg_list = [dict(s) for s in self._config]
        result = []
        for cfg in cfg_list:
            name = cfg.get("name", "")
            srv = self.servers.get(name)
            result.append({
                "name": name,
                "type": cfg.get("type", "stdio"),
                "enabled": cfg.get("enabled", True),
                "connected": srv.connected if srv else False,
                "tools_count": len(srv.tools) if srv else 0,
                "last_error": srv.last_error if srv else "",
                "command": cfg.get("command", ""),
                "url": cfg.get("url", ""),
                "args": cfg.get("args", []),
            })
        return result

    def get_all_tools(self) -> list[dict]:
        """返回所有已连接服务器的工具列表。"""
        out = []
        with self._lock:
            servers = list(self.servers.items())
        for srv_name, srv in servers:
            if not srv.connected:
                continue
            for t in srv.tools:
                out.append({
                    "server": srv_name,
                    "name": t.get("name", ""),
                    "full_name": f"mcp__{srv_name}__{t.get('name', '')}",
                    "description": t.get("description", ""),
                    "inputSchema": t.get("inputSchema", {}),
                })
        return out

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    def is_connected(self, server_name: str) -> bool:
        """检查指定 MCP 服务器是否仍在响应（在线状态 + 实际探活）。"""
        srv = self.servers.get(server_name)
        if srv is None or not srv.connected:
            return False
        try:
            alive = srv.ping()
            if not alive:
                # 探活失败，标记为未连接，避免后续误用
                srv.connected = False
            return alive
        except Exception as e:
            logger.debug("[mcp_client] is_connected(%s) 异常: %s", server_name, e)
            return False

    # ------------------------------------------------------------------
    # 工具调用（缓存 + 重试 + 日志）
    # ------------------------------------------------------------------
    def call_tool(self, tool_full_name: str, arguments: dict | None = None) -> str:
        """根据 mcp__{server}__{tool} 格式查找并调用工具。

        * 命中缓存（5 分钟内相同参数）直接返回；
        * 网络/超时错误指数退避重试 MAX_RETRIES 次；
        * 参数类错误不重试，直接返回错误说明；
        * 每次调用记录成功/失败与耗时。
        """
        if not tool_full_name.startswith("mcp__"):
            return "非 MCP 工具"
        parts = tool_full_name.split("__", 2)
        if len(parts) < 3:
            return "工具名格式错误，应为 mcp__{server}__{tool}"
        _, server_name, tool_name = parts[0], parts[1], parts[2]
        args = arguments or {}

        cache_key = self._cache_key(server_name, tool_name, args)
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.info("[mcp_client] %s 命中缓存，耗时0ms", tool_full_name)
            return cached

        srv = self.servers.get(server_name)
        if srv is None or not srv.connected:
            return f"服务器 {server_name} 未连接"

        last_err = ""
        for attempt in range(1 + MAX_RETRIES):
            t0 = time.monotonic()
            try:
                result = srv.call_tool(tool_name, args)
                elapsed_ms = (time.monotonic() - t0) * 1000
                logger.info(
                    "[mcp_client] %s 调用成功(第%d次)，耗时%.0fms",
                    tool_full_name, attempt + 1, elapsed_ms)
                self._cache_put(cache_key, result)
                return result
            except MCPRequestError as e:
                # 参数/工具错误：不重试
                elapsed_ms = (time.monotonic() - t0) * 1000
                logger.warning(
                    "[mcp_client] %s 调用失败(参数错误，不重试)，耗时%.0fms: %s",
                    tool_full_name, elapsed_ms, e)
                return f"MCP 工具调用失败: {type(e).__name__}: {e}"
            except MCPTransportError as e:
                elapsed_ms = (time.monotonic() - t0) * 1000
                last_err = f"{type(e).__name__}: {e}"
                if attempt < MAX_RETRIES:
                    backoff = 2.0 ** attempt
                    logger.warning(
                        "[mcp_client] %s 传输失败(第%d次)，%.1fs 后重试: %s",
                        tool_full_name, attempt + 1, backoff, e)
                    time.sleep(backoff)
                    continue
                logger.warning(
                    "[mcp_client] %s 调用失败(重试%d次后仍失败)，总耗时%.0fms: %s",
                    tool_full_name, MAX_RETRIES,
                    (time.monotonic() - t0) * 1000, e)
                return f"MCP 工具调用失败: {last_err}"
            except Exception as e:
                elapsed_ms = (time.monotonic() - t0) * 1000
                logger.warning(
                    "[mcp_client] %s 调用异常，耗时%.0fms: %s",
                    tool_full_name, elapsed_ms, e)
                return f"MCP 工具调用失败: {type(e).__name__}: {e}"
        return f"MCP 工具调用失败: {last_err}"

    def close(self):
        """断开所有服务器。"""
        for srv in list(self.servers.values()):
            try:
                srv.disconnect()
            except Exception as e:
                logger.warning(
                    "[mcp_client] 关闭服务器 %s 失败: %s",
                    getattr(srv, "name", "?"), e)
        self.servers.clear()
        try:
            with self._cache_lock:
                self._cache.clear()
        except Exception:
            pass
