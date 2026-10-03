"""通信通道基类 - 统一消息模型"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    """统一消息模型"""
    channel: str           # 通道名称：webhook / telegram / wechat ...
    sender_id: str         # 发送者 ID
    sender_name: str       # 发送者名称
    content: str           # 消息内容
    message_id: str = ""   # 消息 ID
    timestamp: float = 0.0
    metadata: dict = None  # 附加数据

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ChannelBase(ABC):
    """通信通道基类"""

    name: str = "base"

    def __init__(self, config: dict):
        self.config = config
        self._running = False

    @abstractmethod
    async def start(self):
        """启动通道"""
        pass

    @abstractmethod
    async def stop(self):
        """停止通道"""
        pass

    @abstractmethod
    async def send(self, to: str, content: str) -> bool:
        """发送消息"""
        pass

    async def on_message(self, message: Message):
        """收到消息的处理钩子，子类可重写"""
        pass

    @property
    def is_running(self) -> bool:
        return self._running
