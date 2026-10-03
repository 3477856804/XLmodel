"""飞书通道 - 通过 Bot API 接入飞书"""
import hashlib
import json
import time

import aiohttp

from .channel_base import ChannelBase, Message


class FeishuChannel(ChannelBase):
    """飞书 Bot 通道"""

    name = "feishu"

    API_BASE = "https://open.feishu.cn/open-apis"

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        self._tenant_token = None
        self._token_expire = 0
        self._session = None

    async def start(self):
        if not self.app_id or not self.app_secret:
            print("  [飞书] 未配置 app_id/app_secret，跳过启动")
            return

        self._session = aiohttp.ClientSession()
        await self._get_tenant_token()
        self._running = True
        print(f"  [飞书] 通道已启动")

    async def stop(self):
        self._running = False
        if self._session:
            await self._session.close()
        print("  [飞书] 通道已停止")

    async def _get_tenant_token(self) -> str:
        """获取 tenant_access_token"""
        if self._tenant_token and time.time() < self._token_expire:
            return self._tenant_token

        url = f"{self.API_BASE}/auth/v3/tenant_access_token/internal"
        async with self._session.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }) as resp:
            data = await resp.json()
            if data.get("code") == 0:
                self._tenant_token = data.get("tenant_access_token", "")
                self._token_expire = time.time() + data.get("expire", 7200) - 300
                return self._tenant_token
        return ""

    async def send(self, to: str, content: str) -> bool:
        """发送消息到飞书"""
        token = await self._get_tenant_token()
        if not token:
            return False

        url = f"{self.API_BASE}/im/v1/messages?receive_id_type=chat_id"
        try:
            async with self._session.post(url,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": to,
                    "msg_type": "text",
                    "content": json.dumps({"text": content}),
                }
            ) as resp:
                data = await resp.json()
                return data.get("code") == 0
        except Exception:
            return False

    async def handle_event(self, event: dict):
        """处理飞书事件回调"""
        header = event.get("header", {})
        event_type = header.get("event_type", "")

        if event_type == "im.message.receive_v1":
            message = event.get("event", {}).get("message", {})
            sender = event.get("event", {}).get("sender", {})

            chat_id = message.get("chat_id", "")
            content = json.loads(message.get("content", "{}")).get("text", "")
            sender_id = sender.get("sender_id", {}).get("open_id", "")

            msg = Message(
                channel=self.name,
                sender_id=sender_id,
                sender_name=sender_id,
                content=content,
                message_id=message.get("message_id", ""),
            )

            if self._message_handler:
                response = await self._message_handler(msg)
                if response:
                    await self.send(chat_id, response)

    def set_message_handler(self, handler):
        self._message_handler = handler
