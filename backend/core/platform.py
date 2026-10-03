"""跨平台检测模块 - 业务代码不硬编码平台名，统一走这里"""
import sys
from pathlib import Path


class Platform:
    WIN = "win"
    MAC = "mac"
    LINUX = "linux"

    @staticmethod
    def current() -> str:
        if sys.platform == "win32":
            return Platform.WIN
        if sys.platform == "darwin":
            return Platform.MAC
        return Platform.LINUX

    @staticmethod
    def is_win() -> bool:
        return Platform.current() == Platform.WIN

    @staticmethod
    def is_mac() -> bool:
        return Platform.current() == Platform.MAC

    @staticmethod
    def is_linux() -> bool:
        return Platform.current() == Platform.LINUX

    @staticmethod
    def name() -> str:
        names = {Platform.WIN: "Windows", Platform.MAC: "macOS", Platform.LINUX: "Linux"}
        return names[Platform.current()]()


def get_user_data_dir() -> Path:
    """获取用户数据目录，跨平台自动定位"""
    home = Path.home()
    if Platform.is_win():
        return home / "AppData" / "Local" / "XiaoLing"
    if Platform.is_mac():
        return home / "Library" / "Application Support" / "XiaoLing"
    return home / ".local" / "share" / "xiaoling"


def get_config_dir() -> Path:
    """获取配置目录"""
    home = Path.home()
    if Platform.is_win():
        return home / "AppData" / "Roaming" / "XiaoLing"
    if Platform.is_mac():
        return home / "Library" / "Application Support" / "XiaoLing" / "config"
    return home / ".config" / "xiaoling"


def get_cache_dir() -> Path:
    """获取缓存目录"""
    home = Path.home()
    if Platform.is_win():
        return home / "AppData" / "Local" / "XiaoLing" / "cache"
    if Platform.is_mac():
        return home / "Library" / "Caches" / "XiaoLing"
    return home / ".cache" / "xiaoling"
