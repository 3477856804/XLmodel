"""多平台机器人适配层"""


class PlatformAdapter:
    """多平台机器人适配层"""

    def __init__(self, app=None):
        self.app = app
        self.running = {}

    def handle_message(self, text, platform, sender=""):
        """收到平台消息 → 小凌处理 → 返回回复"""
        if not text or not text.strip():
            return "嗯？我在听。"
        if self.app and hasattr(self.app, 'chat'):
            try:
                reply, _ = self.app.chat(text)
                return reply
            except Exception as e:
                return f"（处理出错：{e}）"
        return "你好呀！"

    def start_all(self):
        """启动所有已配置的平台"""
        return []

    def status_text(self):
        return "已接入平台：" + ", ".join(self.running.keys()) if self.running else "未配置平台"
