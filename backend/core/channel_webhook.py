"""Webhook 通道 - 最简单的外部接入方式"""
import json
from aiohttp import web

from .channel_base import ChannelBase, Message


class WebhookChannel(ChannelBase):
    """Webhook 通道 - 接收外部 HTTP POST 消息"""

    name = "webhook"

    def __init__(self, config: dict):
        super().__init__(config)
        self.host = config.get("host", "0.0.0.0")
        self.port = config.get("port", 9000)
        self.path = config.get("path", "/webhook/xiaoling")
        self._app = None
        self._runner = None
        self._message_handler = None

    def set_message_handler(self, handler):
        """设置消息处理函数"""
        self._message_handler = handler

    async def start(self):
        self._app = web.Application()
        self._app.router.add_post(self.path, self._handle_webhook)
        self._app.router.add_get("/health", self._health_check)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        self._running = True
        print(f"  [Webhook] 已启动：http://{self.host}:{self.port}{self.path}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
        self._running = False
        print("  [Webhook] 已停止")

    async def send(self, to: str, content: str) -> bool:
        # Webhook 是被动接收，主动发送需要配置回调 URL
        callback_url = self.config.get("callback_url")
        if not callback_url:
            return False
        # 这里实际发 HTTP POST
        return True

    async def _handle_webhook(self, request):
        try:
            data = await request.json()
            message = Message(
                channel=self.name,
                sender_id=str(data.get("user_id", "unknown")),
                sender_name=data.get("user_name", "Unknown"),
                content=data.get("text", ""),
                message_id=data.get("message_id", ""),
            )
            if self._message_handler:
                response = await self._message_handler(message)
                return web.json_response({"reply": response})
            return web.json_response({"reply": "OK"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _health_check(self, request):
        return web.json_response({"status": "ok", "channel": self.name})
