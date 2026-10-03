"""邮件通道 - SMTP 收发邮件"""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.parser import BytesParser
from email.policy import default

from .channel_base import ChannelBase, Message


class EmailChannel(ChannelBase):
    """邮件通道"""

    name = "email"

    def __init__(self, config: dict):
        super().__init__(config)
        self.smtp_host = config.get("smtp_host", "")
        self.smtp_port = config.get("smtp_port", 465)
        self.imap_host = config.get("imap_host", "")
        self.email_addr = config.get("email_addr", "")
        self.email_password = config.get("email_password", "")
        self._check_task = None

    async def start(self):
        if not self.smtp_host or not self.email_addr:
            print("  [邮件] 未配置 SMTP，跳过启动")
            return

        self._running = True
        # 启动邮件检查循环
        if self.imap_host:
            self._check_task = asyncio.create_task(self._check_emails_loop())
        print(f"  [邮件] 通道已启动: {self.email_addr}")

    async def stop(self):
        self._running = False
        if self._check_task:
            self._check_task.cancel()
        print("  [邮件] 通道已停止")

    async def send(self, to: str, content: str) -> bool:
        """发送邮件"""
        msg = MIMEText(content, "plain", "utf-8")
        msg["From"] = self.email_addr
        msg["To"] = to
        msg["Subject"] = Header("小凌", "utf-8").encode()

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_sync, msg)
            return True
        except Exception:
            return False

    def _send_sync(self, msg):
        """同步发送邮件"""
        server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
        server.login(self.email_addr, self.email_password)
        server.sendmail(self.email_addr, [msg["To"]], msg.as_string())
        server.quit()

    async def _check_emails_loop(self):
        """定时检查新邮件"""
        while self._running:
            try:
                await self._check_new_emails()
            except Exception:
                pass
            await asyncio.sleep(60)  # 每分钟检查一次

    async def _check_new_emails(self):
        """检查新邮件"""
        # 简化版：实际需要 imaplib
        pass

    def set_message_handler(self, handler):
        self._message_handler = handler
