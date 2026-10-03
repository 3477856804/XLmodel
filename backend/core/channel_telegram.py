"""Telegram 通道 - 通过 Bot API 接入 Telegram"""
import asyncio
import json
from aiohttp import web, ClientSession

from .channel_base import ChannelBase, Message


class TelegramChannel(ChannelBase):
    """Telegram Bot 通道"""

    name = "telegram"

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("bot_token", "")
        self.webhook_url = config.get("webhook_url", "")
        self._offset = 0

    async def start(self):
        if not self.bot_token:
            print("  [Telegram] 未配置 bot_token，跳过启动")
            return

        # 设置 webhook
        if self.webhook_url:
            await self._set_webhook()

        self._running = True
        print(f"  [Telegram] 通道已启动")

    async def stop(self):
        self._running = False
        print("  [Telegram] 通道已停止")

    async def send(self, to: str, content: str) -> bool:
        if not self.bot_token:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with ClientSession() as session:
                async with session.post(url, json={
                    "chat_id": to,
                    "text": content,
                }) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _set_webhook(self):
        """设置 Telegram webhook"""
        url = f"https://api.telegram.org/bot{self.bot_token}/setWebhook"
        try:
            async with ClientSession() as session:
                async with session.post(url, json={
                    "url": self.webhook_url,
                }) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        print(f"  [Telegram] Webhook 已设置: {self.webhook_url}")
                    else:
                        print(f"  [Telegram] Webhook 设置失败: {data}")
        except Exception as e:
            print(f"  [Telegram] Webhook 设置异常: {e}")

    async def handle_update(self, update: dict):
        """处理 Telegram update"""
        message = update.get("message")
        if not message:
            return

        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        from_name = message.get("from", {}).get("first_name", "Unknown")

        msg = Message(
            channel=self.name,
            sender_id=chat_id,
            sender_name=from_name,
            content=text,
            message_id=str(message.get("message_id", "")),
        )

        if self._message_handler:
            response = await self._message_handler(msg)
            if response:
                await self.send(chat_id, response)

    def set_message_handler(self, handler):
        self._message_handler = handler
