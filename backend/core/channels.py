"""通信通道 - 统一管理所有外部消息通道

支持：Webhook / Telegram / Discord / 飞书 / 邮件
"""
import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional

import aiohttp


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
        self.config = config
        self._running = False
        self._message_handler = None

    @abstractmethod
    async def start(self): pass

    @abstractmethod
    async def stop(self): pass

    @abstractmethod
    async def send(self, to: str, content: str) -> bool: pass

    def set_message_handler(self, handler):
        self._message_handler = handler

    @property
    def is_running(self) -> bool:
        return self._running


# ===== Webhook =====
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
        self._running = False

    async def send(self, to: str, content: str) -> bool:
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
    name = "telegram"
    API_BASE = "https://api.telegram.org"

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("bot_token", "")

    async def start(self):
        if not self.bot_token:
            return
        self._running = True
        print(f"  [Telegram] 已启动")

    async def stop(self):
        self._running = False

    async def send(self, to: str, content: str) -> bool:
        if not self.bot_token:
            return False
        url = f"{self.API_BASE}/bot{self.bot_token}/sendMessage"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json={"chat_id": to, "text": content}) as r:
                    return r.status == 200
        except Exception:
            return False


# ===== Discord =====
class DiscordChannel(ChannelBase):
    name = "discord"
    API_BASE = "https://discord.com/api/v10"

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("bot_token", "")

    async def start(self):
        if not self.bot_token:
            return
        self._running = True
        print(f"  [Discord] 已启动")

    async def stop(self):
        self._running = False

    async def send(self, to: str, content: str) -> bool:
        if not self.bot_token:
            return False
        url = f"{self.API_BASE}/channels/{to}/messages"
        try:
            async with aiohttp.ClientSession(
                headers={"Authorization": f"Bot {self.bot_token}"}
            ) as s:
                async with s.post(url, json={"content": content}) as r:
                    return r.status == 200
        except Exception:
            return False


# ===== 飞书 =====
class FeishuChannel(ChannelBase):
    name = "feishu"
    API_BASE = "https://open.feishu.cn/open-apis"

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        self._token = None
        self._token_expire = 0

    async def start(self):
        if not self.app_id:
            return
        await self._get_token()
        self._running = True
        print(f"  [飞书] 已启动")

    async def stop(self):
        self._running = False

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expire:
            return self._token
        url = f"{self.API_BASE}/auth/v3/tenant_access_token/internal"
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={
                "app_id": self.app_id, "app_secret": self.app_secret
            }) as r:
                data = await r.json()
                if data.get("code") == 0:
                    self._token = data["tenant_access_token"]
                    self._token_expire = time.time() + data.get("expire", 7200) - 300
        return self._token or ""

    async def send(self, to: str, content: str) -> bool:
        token = await self._get_token()
        if not token:
            return False
        url = f"{self.API_BASE}/im/v1/messages?receive_id_type=chat_id"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url,
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "receive_id": to,
                        "msg_type": "text",
                        "content": json.dumps({"text": content}),
                    }
                ) as r:
                    data = await r.json()
                    return data.get("code") == 0
        except Exception:
            return False


# ===== 邮件 =====
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

    async def send(self, to: str, content: str) -> bool:
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
    """统一管理所有通信通道"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.channels: Dict[str, ChannelBase] = {}
        self._message_handler = None

    async def start_all(self):
        for name, cls in CHANNEL_REGISTRY.items():
            cfg = self.config.get(name, {})
            if cfg.get("enabled", False):
                try:
                    ch = cls(cfg)
                    ch.set_message_handler(self._message_handler)
                    await ch.start()
                    self.channels[name] = ch
                except Exception as e:
                    print(f"  [通道] {name} 启动失败: {e}")

    async def stop_all(self):
        for ch in self.channels.values():
            try:
                await ch.stop()
            except Exception:
                pass
        self.channels.clear()

    def set_message_handler(self, handler):
        self._message_handler = handler
        for ch in self.channels.values():
            ch.set_message_handler(handler)

    def list_channels(self) -> List[dict]:
        return [{"name": n, "running": c.is_running} for n, c in self.channels.items()]
