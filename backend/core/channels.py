"""通信通道 - 统一管理所有外部消息通道

支持：Webhook / Telegram / Discord / 飞书 / 邮件
所有外部通道的网络调用均使用 requests，带 10 秒超时与 try-except，
失败时优雅降级（返回 False / 跳过），不阻塞主程序。
"""
import asyncio
import collections
import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import aiohttp
import requests

HTTP_TIMEOUT = 10


@dataclass
class Message:
    """统一消息模型"""
    channel: str
    sender_id: str
    sender_name: str
    content: str
    message_id: str = ""
    timestamp: float = 0.0
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ChannelBase(ABC):
    """通信通道基类"""
    name: str = "base"

    def __init__(self, config: dict):
        self.config = config or {}
        self._running = False
        self._message_handler = None
        self.engine = None

    @abstractmethod
    async def start(self): pass

    @abstractmethod
    async def stop(self): pass

    @abstractmethod
    async def send(self, to: str = "", content: str = "") -> bool: pass

    def set_message_handler(self, handler):
        self._message_handler = handler

    def set_engine(self, engine):
        self.engine = engine

    def _reply(self, text: str) -> str:
        """收到外部消息后获取机器人回复（优先 engine.chat，同步）。"""
        try:
            if self.engine is not None and hasattr(self.engine, "chat"):
                out = self.engine.chat(text)
                if asyncio.iscoroutine(out):
                    out = asyncio.get_event_loop().run_until_complete(out)
                return str(out)
        except Exception as e:
            print(f"  [{self.name}] 生成回复失败: {e}")
        return ""

    @property
    def is_running(self) -> bool:
        return self._running


# ===== Webhook（保留原有 aiohttp 真实实现）=====
class WebhookChannel(ChannelBase):
    name = "webhook"

    def __init__(self, config: dict):
        super().__init__(config)
        self.host = config.get("host", "0.0.0.0")
        self.port = config.get("port", 9000)
        self.path = config.get("path", "/webhook/xiaoling")
        self._runner = None

    async def start(self):
        from aiohttp import web
        app = web.Application()
        app.router.add_post(self.path, self._handle)
        app.router.add_get("/health", self._health)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        self._running = True
        print(f"  [Webhook] http://{self.host}:{self.port}{self.path}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
        self._runner = None
        self._running = False

    async def send(self, to: str = "", content: str = "") -> bool:
        return bool(self.config.get("callback_url"))

    async def _handle(self, request):
        from aiohttp import web
        try:
            data = await request.json()
            msg = Message(
                channel=self.name,
                sender_id=str(data.get("user_id", "unknown")),
                sender_name=data.get("user_name", "Unknown"),
                content=data.get("text", ""),
            )
            if self._message_handler:
                resp = await self._message_handler(msg)
                return web.json_response({"reply": resp})
            return web.json_response({"reply": "OK"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _health(self, request):
        from aiohttp import web
        return web.json_response({"status": "ok"})


# ===== Telegram =====
class TelegramChannel(ChannelBase):
    """Telegram Bot：sendMessage 发送 + getUpdates 长轮询接收（独立线程）。"""
    name = "telegram"
    API_BASE = "https://api.telegram.org"

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = str(config.get("bot_token", "") or "")
        self.chat_id = str(config.get("chat_id", "") or "")
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._offset = 0

    async def start(self):
        if not self.bot_token:
            print("  [Telegram] 未配置 bot_token，跳过启动")
            return
        self._stop_flag.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop, name="telegram-poll", daemon=True)
        self._thread.start()
        print("  [Telegram] 已启动（getUpdates 轮询）")

    async def stop(self):
        self._stop_flag.set()
        t = self._thread
        if t and t.is_alive():
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, t.join, 5)
        self._thread = None
        self._running = False

    async def send(self, to: str = "", content: str = "") -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_sync, to, content)

    def _send_sync(self, to: str = "", content: str = "") -> bool:
        if not self.bot_token:
            return False
        chat_id = str(to or self.chat_id or "")
        if not chat_id:
            return False
        url = f"{self.API_BASE}/bot{self.bot_token}/sendMessage"
        try:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "text": content},
                timeout=HTTP_TIMEOUT,
            )
            return r.status_code == 200
        except Exception:
            return False

    def _poll_loop(self):
        offset = self._offset
        while not self._stop_flag.is_set():
            url = f"{self.API_BASE}/bot{self.bot_token}/getUpdates"
            try:
                r = requests.get(
                    url,
                    params={"timeout": 30, "offset": offset},
                    timeout=HTTP_TIMEOUT + 30,
                )
                data = r.json()
            except Exception:
                time.sleep(3)
                continue
            if not isinstance(data, dict) or not data.get("ok"):
                time.sleep(3)
                continue
            try:
                for upd in data.get("result", []) or []:
                    offset = max(offset, int(upd.get("update_id", 0)) + 1)
                    msg = (upd.get("message")
                           or upd.get("edited_message")
                           or upd.get("channel_post")
                           or {})
                    chat = msg.get("chat", {}) or {}
                    text = msg.get("text", "")
                    if not text:
                        continue
                    reply = self._reply(text)
                    if reply:
                        self._send_sync(str(chat.get("id", "")), reply)
            except Exception as e:
                print(f"  [Telegram] 处理更新异常: {e}")
        self._offset = offset


# ===== Discord（Webhook 仅发送模式）=====
class DiscordChannel(ChannelBase):
    """Discord 自定义 Webhook：POST JSON 发送，不支持接收。"""
    name = "discord"

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = str(config.get("webhook_url", "") or "")

    async def start(self):
        if not self.webhook_url:
            print("  [Discord] 未配置 webhook_url，跳过启动")
            return
        self._running = True
        print("  [Discord] 通道已启动（仅发送模式）")

    async def stop(self):
        self._running = False

    async def send(self, to: str = "", content: str = "") -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_sync, content)

    def _send_sync(self, content: str = "") -> bool:
        if not self.webhook_url:
            return False
        try:
            r = requests.post(
                self.webhook_url,
                json={"content": content, "username": "晓灵"},
                timeout=HTTP_TIMEOUT,
            )
            return r.status_code in (200, 204)
        except Exception:
            return False


# ===== 飞书（自定义机器人 Webhook 仅发送模式）=====
class FeishuChannel(ChannelBase):
    """飞书自定义机器人 Webhook：POST msg_type=text 发送，不支持接收。"""
    name = "feishu"

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = str(config.get("webhook_url", "") or "")

    async def start(self):
        if not self.webhook_url:
            print("  [飞书] 未配置 webhook_url，跳过启动")
            return
        self._running = True
        print("  [飞书] 通道已启动（仅发送模式）")

    async def stop(self):
        self._running = False

    async def send(self, to: str = "", content: str = "") -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._send_sync, content)

    def _send_sync(self, content: str = "") -> bool:
        if not self.webhook_url:
            return False
        try:
            r = requests.post(
                self.webhook_url,
                json={"msg_type": "text", "content": {"text": content}},
                timeout=HTTP_TIMEOUT,
            )
            data = r.json() if r.headers.get(
                "Content-Type", "").startswith("application/json") else {}
            return r.status_code == 200 and data.get("code", 0) == 0
        except Exception:
            return False


# ===== 邮件（保留）=====
class EmailChannel(ChannelBase):
    name = "email"

    def __init__(self, config: dict):
        super().__init__(config)
        self.smtp_host = config.get("smtp_host", "")
        self.smtp_port = config.get("smtp_port", 465)
        self.email_addr = config.get("email_addr", "")
        self.email_password = config.get("email_password", "")

    async def start(self):
        if not self.smtp_host:
            return
        self._running = True
        print(f"  [邮件] 已启动: {self.email_addr}")

    async def stop(self):
        self._running = False

    async def send(self, to: str = "", content: str = "") -> bool:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(content, "plain", "utf-8")
        msg["From"] = self.email_addr
        msg["To"] = to
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_sync, msg)
            return True
        except Exception:
            return False

    def _send_sync(self, msg):
        import smtplib
        server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
        server.login(self.email_addr, self.email_password)
        server.sendmail(self.email_addr, [msg["To"]], msg.as_string())
        server.quit()


# ===== 通道管理器 =====
CHANNEL_REGISTRY = {
    "webhook": WebhookChannel,
    "telegram": TelegramChannel,
    "discord": DiscordChannel,
    "feishu": FeishuChannel,
    "email": EmailChannel,
}


class ChannelManager:
    """统一管理所有通信通道。

    优先从顶层扁平配置（telegram_enabled / discord_enabled / ...）读取，
    兼容旧的嵌套 channels.<name> 配置。
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.channels: Dict[str, ChannelBase] = {}
        self._message_handler = None
        self.engine = None
        # 每个通道保留最近 100 条收发消息（用于状态面板排查）
        self._msg_queues: Dict[str, "collections.deque"] = {}
        self._last_msg_time: Dict[str, float] = {}
        self._reconnect_attempts: Dict[str, int] = {}

    def _channel_config(self, name: str) -> dict:
        cfg = dict(self.config.get(name, {}) or {})
        flat = {
            "webhook": {
                "enabled": self.config.get("webhook_enabled", False),
            },
            "telegram": {
                "enabled": self.config.get("telegram_enabled", False),
                "bot_token": self.config.get("telegram_bot_token", ""),
                "chat_id": self.config.get("telegram_chat_id", ""),
            },
            "discord": {
                "enabled": self.config.get("discord_enabled", False),
                "webhook_url": self.config.get("discord_webhook_url", ""),
            },
            "feishu": {
                "enabled": self.config.get("feishu_enabled", False),
                "webhook_url": self.config.get("feishu_webhook_url", ""),
            },
        }.get(name, {})
        for k, v in flat.items():
            if k not in cfg or cfg.get(k) in (None, ""):
                cfg[k] = v
        return cfg

    async def start_all(self):
        for name, cls in CHANNEL_REGISTRY.items():
            cfg = self._channel_config(name)
            if not cfg.get("enabled", False):
                continue
            try:
                ch = cls(cfg)
                ch.set_message_handler(self._message_handler)
                if self.engine is not None:
                    ch.set_engine(self.engine)
                await ch.start()
                self.channels[name] = ch
            except Exception as e:
                print(f"  [通道] {name} 启动失败: {e}")

    async def stop_all(self):
        for ch in list(self.channels.values()):
            try:
                await ch.stop()
            except Exception:
                pass
        self.channels.clear()

    def set_engine(self, engine):
        self.engine = engine
        for ch in self.channels.values():
            ch.set_engine(engine)

    def set_message_handler(self, handler):
        self._message_handler = handler
        for ch in self.channels.values():
            ch.set_message_handler(handler)

    def list_channels(self) -> List[dict]:
        return [{"name": n, "running": c.is_running}
                for n, c in self.channels.items()]

    # ---- 通道状态监控 ----
    def get_channel_status(self) -> dict:
        """返回每个通道的状态字典：名称/enabled/connected/最后消息时间/消息数。"""
        out = {}
        for name, ch in self.channels.items():
            q = self._msg_queues.get(name)
            out[name] = {
                "name": name,
                "enabled": bool(self._channel_config(name).get("enabled", False)),
                "connected": bool(ch.is_running),
                "last_message_time": self._last_msg_time.get(name, 0.0),
                "message_count": len(q) if q else 0,
            }
        return out

    # ---- 消息队列（最近收发记录）----
    def record_message(self, channel_name: str, direction: str,
                       content: str) -> None:
        """记录一条发送/接收消息到对应通道的环形队列。"""
        q = self._msg_queues.setdefault(
            channel_name, collections.deque(maxlen=100))
        q.append({"direction": direction, "content": str(content)[:200],
                  "time": time.time()})
        self._last_msg_time[channel_name] = time.time()

    def get_recent_messages(self, channel_name: str, limit: int = 20) -> list:
        """取某通道最近的消息记录。"""
        q = self._msg_queues.get(channel_name)
        if not q:
            return []
        return list(q)[-max(1, limit):]

    # ---- 通道重连 ----
    def _reconnect_channel(self, channel_name: str) -> None:
        """对断开的通道尝试重连（最多 3 次，间隔 5 秒）。"""
        attempts = self._reconnect_attempts.get(channel_name, 0)
        if attempts >= 3:
            print(f"  [通道] {channel_name} 重连失败达上限，放弃")
            return
        cfg = self._channel_config(channel_name)
        if not cfg.get("enabled", False):
            return
        cls = CHANNEL_REGISTRY.get(channel_name)
        if cls is None:
            return

        async def _do_reconnect():
            try:
                ch = cls(cfg)
                ch.set_message_handler(self._message_handler)
                if self.engine is not None:
                    ch.set_engine(self.engine)
                await ch.start()
                self.channels[channel_name] = ch
                self._reconnect_attempts[channel_name] = 0
                print(f"  [通道] {channel_name} 重连成功")
            except Exception as e:
                self._reconnect_attempts[channel_name] = attempts + 1
                print(f"  [通道] {channel_name} 重连失败({attempts + 1}/3): {e}")
                threading.Timer(5.0, self._reconnect_channel,
                                args=[channel_name]).start()

        threading.Thread(target=_do_reconnect, daemon=True).start()
