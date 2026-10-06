"""示例插件 - hello_world"""

def on_message(message: str) -> str:
    """消息钩子：收到用户消息时触发"""
    if "你好" in message or "hello" in message.lower():
        return "你好呀！我是插件 hello_world 说的话～"
    return message
