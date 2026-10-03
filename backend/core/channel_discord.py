"""Discord 通道 - 通过 Bot API 接入 Discord"""
import asyncio
import aiohttp

from .channel_base import ChannelBase, Message


class DiscordChannel(ChannelBase):
    """Discord Bot 通道"""

    name = "discord"

    API_BASE = "https://discord.com/api/v10"

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("bot_token", "")
        self.application_id = config.get("application_id", "")
        self._session = None

    async def start(self):
        if not self.bot_token:
            print("  [Discord] 未配置 bot_token，跳过启动")
            return

        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bot {self.bot_token}",
                "Content-Type": "application/json",
            }
        )
        self._running = True
        print(f"  [Discord] 通道已启动")

    async def stop(self):
        self._running = False
        if self._session:
            await self._session.close()
        print("  [Discord] 通道已停止")

    async def send(self, to: str, content: str) -> bool:
        """发送消息到指定频道"""
        if not self._session:
            return False

        url = f"{self.API_BASE}/channels/{to}/messages"
        try:
            async with self._session.post(url, json={"content": content}) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def handle_interaction(self, interaction: dict):
        """处理 Discord 交互（slash command）"""
        data = interaction.get("data", {})
        name = data.get("name", "")
        user = interaction.get("member", {}).get("user", {}).get("username", "Unknown")
        channel_id = str(interaction.get("channel_id", ""))

        msg = Message(
            channel=self.name,
            sender_id=channel_id,
            sender_name=user,
            content=f"/{name}",
            message_id=str(interaction.get("id", "")),
        )

        if self._message_handler:
            response = await self._message_handler(msg)
            if response:
                # 回复交互
                await self._send_interaction_response(
                    interaction.get("token", ""),
                    response,
                )

    async def _send_interaction_response(self, token: str, content: str):
        """发送交互响应"""
        url = f"{self.API_BASE}/interactions/{self._application_id}/{token}/callback"
        try:
            await self._session.post(url, json={
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {"content": content},
            })
        except Exception:
            pass

    def set_message_handler(self, handler):
        self._message_handler = handler
