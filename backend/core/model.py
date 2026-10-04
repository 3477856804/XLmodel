"""模型系统 - 本地模型加载 + 模型商店 + 模型自我替换"""
import os
import hashlib
import threading
from pathlib import Path

# ===== 模型预设 =====
MODEL_PRESETS = {
    "Qwen2.5-0.5B-Instruct": {
        "size_hint": "~1GB",
        "repo": "Qwen/Qwen2.5-0.5B-Instruct",
        "desc": "最小中文模型，CPU可跑",
    },
}


def get_model_preset():
    name = "Qwen2.5-0.5B-Instruct"
    preset = MODEL_PRESETS.get(name)
    return preset, name


# ===== 模型下载 =====
def download_model(repo_id: str, dest_dir: str):
    """从 HuggingFace 下载模型"""
    from huggingface_hub import snapshot_download
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    print(f"  [下载] {repo_id} -> {dest}")
    path = snapshot_download(
        repo_id=repo_id,
        local_dir=str(dest),
        allow_patterns=["*.json", "*.safetensors", "*.txt", "tokenizer*"],
    )
    return str(path)


# ===== 本地模型加载 =====
class LocalModel:
    """本地模型加载器（transformers）"""

    def __init__(self, model_dir, adapter_dir=None):
        self.model_dir = Path(model_dir)
        self.adapter_dir = Path(adapter_dir) if adapter_dir else None
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        self._lock = threading.Lock()

    def load(self):
        """加载模型"""
        if not self.model_dir.exists():
            print(f"  [模型] 目录不存在: {self.model_dir}")
            return False
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            print(f"  [模型] 加载 {self.model_dir} ...")
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
            self.model = AutoModelForCausalLM.from_pretrained(
                str(self.model_dir),
                torch_dtype="auto",
                device_map="cpu",
                low_cpu_mem_usage=True,
            )
            print("  [模型] 加载完成")
            return True
        except Exception as e:
            print(f"  [模型] 加载失败: {e}")
            self.model = None
            return False

    def generate(self, prompt: str, max_new_tokens: int = 128) -> str:
        """推理"""
        if self.model is None:
            if not self.load():
                return "模型未加载，请先下载模型。"
        try:
            messages = [
                {"role": "system", "content": "你是小凌，一个住在用户电脑里的AI女孩。简短友好地回答。"},
                {"role": "user", "content": prompt},
            ]
            text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
            with self._lock:
                out = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=True, temperature=0.7, top_p=0.9)
            response = self.tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            return response.strip()
        except Exception as e:
            return f"推理出错: {e}"


# ===== 模型商店 =====
class ModelStore:
    """模型商店 - 模型下载、管理、断点续传"""

    def __init__(self, store_dir: str = None):
        from core.paths import APP_DIR
        self.store_dir = Path(store_dir) if store_dir else Path(APP_DIR) / "models"
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def list_models(self) -> list:
        return [p.name for p in self.store_dir.iterdir() if p.is_dir()]

    def download(self, model_name: str, url: str = "") -> bool:
        preset = MODEL_PRESETS.get(model_name)
        if not preset:
            print(f"  [下载] 未知模型: {model_name}")
            return False
        dest = self.store_dir / model_name
        try:
            download_model(preset["repo"], str(dest))
            return True
        except Exception as e:
            print(f"  [下载] 失败: {e}")
            return False


# ===== 模型自我替换 =====
class ModelReplacement:
    def __init__(self, model_dir=None, adapter_dir=None):
        from core.paths import APP_DIR
        self.model_dir = Path(model_dir) if model_dir else Path(APP_DIR) / "models"
        self.adapter_dir = Path(adapter_dir) if adapter_dir else Path(APP_DIR) / "adapters"
        self.replaced = False
        self._local = None

    def get_model(self) -> LocalModel:
        if self._local is None:
            for name in MODEL_PRESETS:
                d = self.model_dir / name
                if d.exists() and any(d.glob("*.safetensors")):
                    self._local = LocalModel(str(d))
                    break
        return self._local

    def chat(self, text: str) -> str:
        m = self.get_model()
        if m is None:
            return None
        return m.generate(text)

    def check_and_replace(self):
        if self.replaced:
            return "self_research", "已是自研模型"
        return "growing", "成长中"

    def status_text(self) -> str:
        m = self.get_model()
        if m is not None and m.model is not None:
            return "已加载真实模型"
        return "等待下载模型"
