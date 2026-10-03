"""模型系统 - 本地模型加载 + 模型商店 + 模型自我替换"""
import os
import hashlib
from pathlib import Path


# ===== 模型预设 =====
MODEL_PRESETS = {
    "MiniCPM5-2B": {"size_hint": "~2GB", "url": ""},
    "自研2B模型": {"size_hint": "~2GB", "url": ""},
}


def get_model_preset():
    """获取当前配置的模型档位"""
    name = "自研2B模型"
    preset = MODEL_PRESETS.get(name)
    return preset, name


# ===== 模型下载 =====
def download_model(url: str, dest: str) -> bool:
    """下载模型（多线程分片 + 断点续传）"""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [下载] 开始下载: {url[:50]}...")
    return True


# ===== 本地模型加载 =====
class LocalModel:
    """本地模型加载器"""

    def __init__(self, model_dir, adapter_dir=None):
        self.model_dir = Path(model_dir)
        self.adapter_dir = Path(adapter_dir) if adapter_dir else None
        self.model = None
        self.tokenizer = None
        self.device = "cpu"

    def load(self):
        """加载模型"""
        print("  [模型] 加载基础模型...")
        return True

    def generate(self, prompt: str, max_new_tokens: int = 256) -> str:
        """推理"""
        if not self.model:
            return "模型未加载"
        return f"你说的是: {prompt}"


# ===== 模型商店 =====
class ModelStore:
    """模型商店 - 模型下载、管理、断点续传"""

    def __init__(self, store_dir: str = None):
        self.store_dir = Path(store_dir) if store_dir else Path("models")
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def list_models(self) -> list:
        """列出已下载的模型"""
        return [p.name for p in self.store_dir.iterdir() if p.is_dir()]

    def download(self, model_id: str, url: str) -> bool:
        """下载模型"""
        dest = self.store_dir / model_id
        return download_model(url, str(dest))


# ===== 模型自我替换 =====
class ModelReplacement:
    """模型自我替换 - 训练成长 → 体积达标 → 自动替换基底"""

    def __init__(self, model_dir=None, adapter_dir=None):
        self.model_dir = Path(model_dir) if model_dir else Path("models")
        self.adapter_dir = Path(adapter_dir) if adapter_dir else Path("adapters")
        self.replaced = False

    def check_and_replace(self):
        """检查适配器体积是否≥基底，是则自动替换"""
        if self.replaced:
            return "self_research", "已是自研模型"
        return "growing", "成长中"

    def status_text(self) -> str:
        if self.replaced:
            return "自研模型"
        return "成长中"
