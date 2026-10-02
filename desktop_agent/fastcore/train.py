"""MYRAA FastCore — Training Pipeline.

Fine-tunes Qwen3-0.6B with LoRA on the FastCore dataset.
CPU-only training with quantization-aware training.
"""

from __future__ import annotations

import json
import os
import sys
import time
import random
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from torch.utils.data import Dataset, DataLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_MODEL = "Qwen/Qwen3-0.6B"
DATASET_PATH = "desktop_agent/fastcore/dataset/fastcore_v0.2.0.json"
OUTPUT_DIR = "desktop_agent/fastcore/checkpoints"
MAX_LENGTH = 256
BATCH_SIZE = 4
LEARNING_RATE = 2e-4
NUM_EPOCHS = 3
WARMUP_STEPS = 50
GRADIENT_ACCUMULATION = 4
LORA_R = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.05
SEED = 42

# ---------------------------------------------------------------------------
# System prompt for structured output
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are FastCore, MYRAA's ultra-fast routing classifier. Given a user message, produce a JSON routing decision.

Output exactly one JSON object with these fields:
- task_type: one of [conversation, direct_knowledge, local_reasoning, current_information, web_research, desktop_action, browser_action, vision_task, file_task, trading_task, coding_task, design_task, multimodal_task]
- response_mode: one of [fast_answer, reasoning, research, action, vision, trading, coding, design, multimodal]
- information_source: one of [none, local_model, wikipedia, tavily, duckduckgo, screen, tool_execution]
- complexity: one of [trivial, simple, moderate, complex, expert]
- model_route: one of [fastcore_direct, local_small, local_large, nim_fast, nim_deep, deterministic]
- safety_class: one of [safe, needs_verification, dangerous, financial, forbidden]
- confidence: a float between 0.0 and 1.0
- tools_required: boolean
- freshness_required: boolean

No explanation. Only JSON."""


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class FastCoreDataset(Dataset):
    """PyTorch dataset for FastCore training."""

    def __init__(self, data: List[Dict[str, Any]], tokenizer, max_length: int = MAX_LENGTH):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        user_text = item["input_text"]

        # Build target JSON
        target = json.dumps({
            "task_type": item["task_type"],
            "response_mode": item["response_mode"],
            "information_source": item["information_source"],
            "complexity": item["complexity"],
            "model_route": item["model_route"],
            "safety_class": item["safety_class"],
            "confidence": item.get("confidence", 0.9),
            "tools_required": item.get("tools_required", False),
            "freshness_required": item.get("freshness_required", False),
        }, separators=(",", ":"))

        # Format as chat
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        # Tokenize prompt
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        prompt_ids = self.tokenizer.encode(prompt, add_special_tokens=False)

        # Tokenize target
        target_ids = self.tokenizer.encode(target, add_special_tokens=False)

        # Combine
        input_ids = prompt_ids + target_ids
        attention_mask = [1] * len(input_ids)

        # Labels: only supervise the target part
        labels = [-100] * len(prompt_ids) + target_ids

        # Truncate
        if len(input_ids) > self.max_length:
            input_ids = input_ids[:self.max_length]
            attention_mask = attention_mask[:self.max_length]
            labels = labels[:self.max_length]

        # Pad
        pad_len = self.max_length - len(input_ids)
        input_ids += [0] * pad_len
        attention_mask += [0] * pad_len
        labels += [-100] * pad_len

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train():
    """Main training loop."""
    from transformers import AutoTokenizer, AutoModelForCausalLM, get_linear_schedule_with_warmup
    from peft import LoraConfig, get_peft_model, TaskType

    logger.info("=== FastCore Training Pipeline ===")
    logger.info(f"Base model: {BASE_MODEL}")

    # Load tokenizer
    logger.info("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load dataset
    logger.info(f"Loading dataset from {DATASET_PATH}...")
    with open(DATASET_PATH) as f:
        ds = json.load(f)
    examples = ds["examples"]
    logger.info(f"Total examples: {len(examples)}")

    # Split 80/10/10
    random.seed(SEED)
    random.shuffle(examples)
    n = len(examples)
    train_data = examples[:int(0.8 * n)]
    val_data = examples[int(0.8 * n):int(0.9 * n)]
    test_data = examples[int(0.9 * n):]
    logger.info(f"Train: {len(train_data)}, Val: {len(val_data)}, Test: {len(test_data)}")

    # Create datasets
    train_dataset = FastCoreDataset(train_data, tokenizer)
    val_dataset = FastCoreDataset(val_data, tokenizer)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

    # Load model
    logger.info("Loading model...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float32,  # CPU needs float32
        trust_remote_code=True,
    )

    # Apply LoRA
    logger.info("Applying LoRA...")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Optimizer
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)

    # Scheduler
    total_steps = len(train_loader) * NUM_EPOCHS // GRADIENT_ACCUMULATION
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=WARMUP_STEPS, num_training_steps=total_steps
    )

    # Output dir
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Training loop
    logger.info("Starting training...")
    best_val_loss = float("inf")
    global_step = 0

    for epoch in range(NUM_EPOCHS):
        model.train()
        total_loss = 0.0
        t0 = time.time()

        for step, batch in enumerate(train_loader):
            outputs = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                labels=batch["labels"],
            )
            loss = outputs.loss / GRADIENT_ACCUMULATION
            loss.backward()
            total_loss += loss.item() * GRADIENT_ACCUMULATION

            if (step + 1) % GRADIENT_ACCUMULATION == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1

            if (step + 1) % 100 == 0:
                avg_loss = total_loss / (step + 1)
                logger.info(f"  Epoch {epoch+1}, Step {step+1}/{len(train_loader)}, Loss: {avg_loss:.4f}")

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                outputs = model(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                    labels=batch["labels"],
                )
                val_loss += outputs.loss.item()
        val_loss /= len(val_loader)

        elapsed = time.time() - t0
        logger.info(f"Epoch {epoch+1}/{NUM_EPOCHS} — Train Loss: {total_loss/len(train_loader):.4f}, Val Loss: {val_loss:.4f}, Time: {elapsed:.1f}s")

        # Save best checkpoint
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            ckpt_dir = output_dir / f"fastcore-epoch{epoch+1}"
            model.save_pretrained(str(ckpt_dir))
            tokenizer.save_pretrained(str(ckpt_dir))
            logger.info(f"  Saved checkpoint: {ckpt_dir}")

    # Save final model
    final_dir = output_dir / "fastcore-final"
    model.save_pretrained(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    logger.info(f"Saved final model: {final_dir}")

    # Save training config
    config = {
        "base_model": BASE_MODEL,
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,
        "max_length": MAX_LENGTH,
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "num_epochs": NUM_EPOCHS,
        "train_examples": len(train_data),
        "val_examples": len(val_data),
        "test_examples": len(test_data),
        "best_val_loss": best_val_loss,
        "total_steps": global_step,
    }
    with open(final_dir / "training_config.json", "w") as f:
        json.dump(config, f, indent=2)

    logger.info("Training complete!")
    return model, tokenizer, test_data


if __name__ == "__main__":
    model, tokenizer, test_data = train()
    print(f"\nTraining complete. Test set size: {len(test_data)}")
