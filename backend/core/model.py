"""模型系统 - 多模型选择 + 按跑分推荐 + 本地加载"""
import os
import threading
from pathlib import Path

# ===== 模型预设（按最小但跑分最高排序） =====
# score = MMLU平均分, size_mb = 模型大小
# 推荐策略: score/size 比值越高越推荐
MODEL_PRESETS = {
    "Qwen2.5-0.5B-Instruct": {
        "repo": "Qwen/Qwen2.5-0.5B-Instruct",
        "size_mb": 988,
        "score": 25.0,
        "desc": "最小模型，CPU秒跑，适合低配",
        "langs": "中/英",
    },
    "Qwen2.5-1.5B-Instruct": {
        "repo": "Qwen/Qwen2.5-1.5B-Instruct",
        "size_mb": 3100,
        "score": 40.0,
        "desc": "性价比最高，中文流畅",
        "langs": "中/英",
    },
    "Qwen2.5-3B-Instruct": {
        "repo": "Qwen/Qwen2.5-3B-Instruct",
        "size_mb": 6100,
        "score": 52.0,
        "desc": "能力强，需4GB内存",
        "langs": "中/英",
    },
    "Llama-3.2-1B-Instruct": {
        "repo": "meta-llama/Llama-3.2-1B-Instruct",
        "size_mb": 1300,
        "score": 39.0,
        "desc": "英文强，中文一般",
        "langs": "英/多语",
    },
    "Phi-3.5-mini-instruct": {
        "repo": "microsoft/Phi-3.5-mini-instruct",
        "size_mb": 2300,
        "score": 49.0,
        "desc": "微软小钢炮，推理快",
        "langs": "英/多语",
    },
}


def list_recommended():
    """返回按 score/size 比值排序的模型列表（最小但跑分最高优先）"""
    items = []
    for name, info in MODEL_PRESETS.items():
        ratio = info["score"] / (info["size_mb"] / 1024)  # 每GB跑分
        items.append({
            "name": name,
            "repo": info["repo"],
            "size_mb": info["size_mb"],
            "score": info["score"],
            "desc": info["desc"],
            "langs": info["langs"],
            "ratio": round(ratio, 2),
        })
    items.sort(key=lambda x: x["ratio"], reverse=True)
    return items


def get_recommended(config=None):
    """根据用户配置推荐模型
    config: {"max_size_mb": int, "lang": "zh"/"en", "has_gpu": bool}
    没有配置就返回默认推荐（最小但跑分最高）
    """
    recs = list_recommended()
    if not config:
        return recs[0] if recs else None

    max_size = config.get("max_size_mb", 10000)
    lang = config.get("lang", "zh")

    candidates = [r for r in recs if r["size_mb"] <= max_size]
    if not candidates:
        candidates = recs  # 超出限制也放最小的

    # 中文优先
    if lang == "zh":
        zh = [c for c in candidates if "中" in c["langs"]]
        if zh:
            return zh[0]
    return candidates[0]


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
    """模型商店 - 列出所有可下载模型，用户自选"""

    def __init__(self, store_dir: str = None):
        from core.paths import APP_DIR
        self.store_dir = Path(store_dir) if store_dir else Path(APP_DIR) / "models"
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def list_available(self) -> list:
        """列出所有可下载模型（按推荐排序）"""
        return list_recommended()

    def list_installed(self) -> list:
        """列出已下载的模型"""
        return [p.name for p in self.store_dir.iterdir() if p.is_dir()]

    def download(self, model_name: str) -> bool:
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


# ===== 模型加载（用户选哪个加载哪个） =====
class ModelReplacement:
    def __init__(self, model_dir=None, adapter_dir=None, selected_name=None):
        from core.paths import APP_DIR
        self.model_dir = Path(model_dir) if model_dir else Path(APP_DIR) / "models"
        self.adapter_dir = Path(adapter_dir) if adapter_dir else Path(APP_DIR) / "adapters"
        self.selected_name = selected_name  # 用户在设置里选的模型名
        self._local = None

    def _find_installed(self):
        """找到已下载的模型目录"""
        # 优先用用户选的
        if self.selected_name:
            d = self.model_dir / self.selected_name
            if d.exists() and any(d.glob("*.safetensors")):
                return d
        # 否则找任意已下载的
        for name in MODEL_PRESETS:
            d = self.model_dir / name
            if d.exists() and any(d.glob("*.safetensors")):
                return d
        return None

    def get_model(self) -> LocalModel:
        if self._local is None:
            d = self._find_installed()
            if d:
                self._local = LocalModel(str(d))
        return self._local

    def chat(self, text: str) -> str:
        m = self.get_model()
        if m is None:
            return None
        return m.generate(text)

    def status_text(self) -> str:
        m = self.get_model()
        if m is not None and m.model is not None:
            return f"已加载: {self.selected_name or '本地模型'}"
        return "等待下载模型"
