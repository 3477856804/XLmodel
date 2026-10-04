"""训练系统 - CPU LoRA 微调 + 晋升评估 + 动态升rank"""
import os
import json
import time
from pathlib import Path


class PEFTTrainer:
    """LoRA 训练器（CPU 可跑）"""

    def __init__(self, model=None, tokenizer=None, adapter_dir: str = "adapters"):
        self.model = model
        self.tokenizer = tokenizer
        self.adapter_dir = Path(adapter_dir)
        self.adapter_dir.mkdir(parents=True, exist_ok=True)

    def train(self, conversations: list, epochs: int = 1,
              batch_size: int = 1, lr: float = 1e-4, steps: int = 20):
        """LoRA 微调训练

        conversations: [{"user": "你好", "assistant": "你好呀"}, ...]
        """
        if self.model is None or self.tokenizer is None:
            print("  [训练] 模型未加载，跳过")
            return False

        try:
            import torch
            from peft import LoraConfig, get_peft_model, TaskType

            # 配置 LoRA（最小参数，CPU友好）
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=4,
                lora_alpha=8,
                lora_dropout=0.05,
                target_modules=["q_proj", "v_proj"],
            )
            model = get_peft_model(self.model, lora_config)
            model.print_trainable_parameters()

            # 优化器
            optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
            model.train()

            # 训练循环
            step = 0
            for epoch in range(epochs):
                for conv in conversations:
                    if step >= steps:
                        break
                    messages = [
                        {"role": "system", "content": "你是小凌，住在用户电脑里的AI女孩。"},
                        {"role": "user", "content": conv.get("user", "")},
                        {"role": "assistant", "content": conv.get("assistant", "")},
                    ]
                    text = self.tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=False)
                    enc = self.tokenizer(text, return_tensors="pt",
                                         truncation=True, max_length=256)
                    input_ids = enc["input_ids"]
                    labels = input_ids.clone()

                    optimizer.zero_grad()
                    outputs = model(input_ids=input_ids, labels=labels)
                    loss = outputs.loss
                    loss.backward()
                    optimizer.step()

                    step += 1
                    if step % 5 == 0:
                        print(f"  [训练] step {step}/{steps} loss={loss.item():.4f}")
                if step >= steps:
                    break

            # 保存适配器
            save_path = self.adapter_dir / f"lora_step{step}"
            model.save_pretrained(str(save_path))
            self.tokenizer.save_pretrained(str(save_path))
            print(f"  [训练] 完成，适配器保存到 {save_path}")

            # 记录训练历史
            history_file = self.adapter_dir / "history.json"
            history = []
            if history_file.exists():
                history = json.loads(history_file.read_text())
            history.append({
                "steps": step, "loss": float(loss.item()),
                "time": time.time(), "adapter": str(save_path),
            })
            history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2))
            return True

        except Exception as e:
            print(f"  [训练] 失败: {e}")
            return False

    def get_status(self):
        files = list(self.adapter_dir.glob("lora_*"))
        total_size = sum(f.stat().st_size for f in self.adapter_dir.rglob("*") if f.is_file())
        return {
            "is_training": False,
            "current_epoch": 1,
            "total_epochs": 1,
            "loss": 0.0,
            "adapter_count": len(files),
            "adapter_size_mb": round(total_size / 1024 / 1024, 1),
        }


# ===== 晋升评估 =====
def check_promotion(base_size: int, adapter_size: int, loss_self: float, loss_base: float,
                    benchmark_pass: float = 0.9) -> dict:
    cond_a = adapter_size >= base_size
    cond_b = loss_self <= loss_base
    cond_c = benchmark_pass >= 0.9
    return {
        "cond_a": cond_a,
        "cond_b": cond_b,
        "cond_c": cond_c,
        "promote": cond_a and cond_b and cond_c,
    }


# ===== 动态升 rank =====
class RankScheduler:
    def __init__(self, initial_rank: int = 4):
        self.rank = initial_rank
        self.rank_history = [initial_rank]

    def upgrade(self):
        self.rank *= 2
        self.rank_history.append(self.rank)

    def should_upgrade(self, adapter_size: int, base_size: int) -> bool:
        return adapter_size < base_size * 0.5
