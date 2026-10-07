"""小凌 · MCP（Model Context Protocol）客户端"""
import json
import threading
import time
from pathlib import Path

import requests

from .config import DATA_DIR

MCP_CONFIG_PATH = DATA_DIR / "mcp_servers.json"


class MCPServer:
    """单个 MCP 服务器连接，支持 stdio 与 streamable-http 两种传输。"""

    PROTOCOL_VERSION = "2024-11-05"

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
        try:
            if self.transport == "stdio":
                self._connect_stdio()
            else:
                self._connect_http()
            self.connected = True
            return True
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.connected = False
            return False

    def _connect_stdio(self):
        """启动子进程并后台读取 stdout。"""
        cmd = self.config.get("command", "")
        args = self.config.get("args", []) or []
        if not cmd:
            raise RuntimeError("缺少 command")
        self._process = __import__("subprocess").Popen(
            [cmd] + list(args),
            stdin=__import__("subprocess").PIPE,
            stdout=__import__("subprocess").PIPE,
            stderr=__import__("subprocess").PIPE,
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
            raise RuntimeError("缺少 url")
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
            raise RuntimeError("initialize 无响应")
        try:
            self._send_notification("notifications/initialized", {})
        except Exception:
            pass
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
        except (ValueError, OSError):
            pass

    def _next_id(self) -> int:
        with self._lock:
            self._msg_id += 1
            return self._msg_id

    def _send_request(self, method: str, params=None):
        """发送 JSON-RPC 请求并等待结果。"""
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
                    raise RuntimeError("子进程未启动")
                self._process.stdin.write(json.dumps(msg) + "\n")
                self._process.stdin.flush()
                ok = event.wait(timeout=30)
                if not ok:
                    raise TimeoutError(f"{method} 超时")
                err = slot["error"]
                if err:
                    raise RuntimeError(f"{method} 错误: {err}")
                return slot["result"]
            else:
                url = self.config.get("url", "")
                headers = self.config.get("headers", {}) or {}
                resp = requests.post(url, json=msg, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                if "error" in data and data["error"]:
                    raise RuntimeError(f"{method} 错误: {data['error']}")
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
                self._process.stdin.write(json.dumps(msg) + "\n")
                self._process.stdin.flush()
        else:
            url = self.config.get("url", "")
            headers = self.config.get("headers", {}) or {}
            try:
                requests.post(url, json=msg, headers=headers, timeout=10)
            except requests.RequestException:
                pass

    def call_tool(self, tool_name: str, arguments: dict | None = None) -> str:
        """调用 MCP 工具，返回结果文本。"""
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

    def disconnect(self):
        """断开连接，终止子进程。"""
        try:
            if self._process:
                self._process.terminate()
                try:
                    self._process.wait(timeout=3)
                except Exception:
                    self._process.kill()
        except Exception:
            pass
        finally:
            self._process = None
            self.connected = False
            self.tools = []


class MCPManager:
    """管理所有 MCP 服务器连接与配置。"""

    def __init__(self, config_path: str | None = None):
        self.config_path = Path(config_path) if config_path else MCP_CONFIG_PATH
        self.servers: dict[str, MCPServer] = {}
        self._lock = threading.RLock()
        self._config: list[dict] = []
        self._load_config()

    def _load_config(self):
        """从 JSON 文件加载服务器配置。"""
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "servers" in data:
                    self._config = [s for s in data["servers"] if isinstance(s, dict)]
                elif isinstance(data, list):
                    self._config = [s for s in data if isinstance(s, dict)]
            else:
                self._config = []
        except Exception:
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
        except OSError:
            pass

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
            except Exception:
                pass
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
            except Exception:
                pass

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

    def call_tool(self, tool_full_name: str, arguments: dict | None = None) -> str:
        """根据 mcp__{server}__{tool} 格式查找并调用工具。"""
        if not tool_full_name.startswith("mcp__"):
            return "非 MCP 工具"
        parts = tool_full_name.split("__", 2)
        if len(parts) < 3:
            return "工具名格式错误，应为 mcp__{server}__{tool}"
        _, server_name, tool_name = parts[0], parts[1], parts[2]
        srv = self.servers.get(server_name)
        if srv is None or not srv.connected:
            return f"服务器 {server_name} 未连接"
        try:
            return srv.call_tool(tool_name, arguments or {})
        except Exception as e:
            return f"MCP 工具调用失败: {type(e).__name__}: {e}"

    def close(self):
        """断开所有服务器。"""
        for srv in list(self.servers.values()):
            try:
                srv.disconnect()
            except Exception:
                pass
        self.servers.clear()
