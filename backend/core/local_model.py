"""本地模型 - 加载/推理"""
from pathlib import Path


class LocalModel:
    """本地模型加载器"""

    def __init__(self, model_dir, adapter_dir=None):
        self.model_dir = Path(model_dir)
        self.adapter_dir = Path(adapter_dir) if adapter_dir else None
        self.model = None
        self.tokenizer = None
        self.device = "cpu"

    def _load(self):
        model_file = self.model_dir / "model.safetensors"
        if not model_file.exists():
            print(f"  [模型] 警告：{self.model_dir} 无有效模型权重")
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            print("  [模型] 加载基础模型...")
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), trust_remote_code=True)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = AutoModelForCausalLM.from_pretrained(
                str(self.model_dir),
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )
            self.model.eval()
            print(f"  [模型] 就绪（{self.device}）")
        except Exception as e:
            print(f"  [模型] 加载失败：{e}")

    def generate(self, prompt, max_new_tokens=256, temperature=0.7):
        if not self.model or not self.tokenizer:
            return "模型未加载"
        try:
            import torch
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    do_sample=True,
                )
            return self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        except Exception as e:
            return f"推理失败：{e}"
