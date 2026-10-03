"""通道管理器 - 统一管理所有通信通道"""
import asyncio
from typing import Dict, List, Optional

from .channel_base import ChannelBase, Message
from .channel_webhook import WebhookChannel
from .channel_telegram import TelegramChannel
from .channel_discord import DiscordChannel
from .channel_feishu import FeishuChannel
from .channel_email import EmailChannel


CHANNEL_REGISTRY = {
    "webhook": WebhookChannel,
    "telegram": TelegramChannel,
    "discord": DiscordChannel,
    "feishu": FeishuChannel,
    "email": EmailChannel,
}


class ChannelManager:
    """通道管理器 - 统一注册/启动/停止所有通道"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.channels: Dict[str, ChannelBase] = {}
        self._message_handler = None

    def register_channel(self, name: str, channel: ChannelBase):
        """注册通道"""
        self.channels[name] = channel
        if self._message_handler:
            channel.set_message_handler(self._message_handler)

    async def start_all(self):
        """启动所有已配置的通道"""
        for name, channel_cls in CHANNEL_REGISTRY.items():
            channel_config = self.config.get(name, {})
            if channel_config.get("enabled", False):
                try:
                    channel = channel_cls(channel_config)
                    channel.set_message_handler(self._message_handler)
                    await channel.start()
                    self.channels[name] = channel
                    print(f"  [通道] {name} 已启动")
                except Exception as e:
                    print(f"  [通道] {name} 启动失败: {e}")

    async def stop_all(self):
        """停止所有通道"""
        for name, channel in self.channels.items():
            try:
                await channel.stop()
            except Exception:
                pass
        self.channels.clear()
        print("  [通道] 全部已停止")

    async def broadcast(self, message: str, channels: List[str] = None):
        """广播消息到所有（或指定）通道"""
        targets = channels or list(self.channels.keys())
        for name in targets:
            if name in self.channels:
                try:
                    # 发送到默认接收者
                    await self.channels[name].send("default", message)
                except Exception:
                    pass

    def set_message_handler(self, handler):
        """设置统一消息处理器"""
        self._message_handler = handler
        for channel in self.channels.values():
            channel.set_message_handler(handler)

    def list_channels(self) -> List[dict]:
        """列出所有通道状态"""
        result = []
        for name, channel in self.channels.items():
            result.append({
                "name": name,
                "running": channel.is_running,
            })
        return result
