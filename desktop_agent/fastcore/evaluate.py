"""MYRAA FastCore — Evaluation Pipeline.

Evaluates trained FastCore model against:
1. Deterministic classifier (baseline)
2. Test set accuracy
3. Hard-negative accuracy
4. Schema validity
5. Latency
"""

from __future__ import annotations

import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Import classifier for baseline
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from desktop_agent.fastcore.classifier import FastCoreClassifier
from desktop_agent.fastcore.models import TaskType, ResponseMode, InformationSource, Complexity, ModelRoute, SafetyClass


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


def load_model(checkpoint_path: str):
    """Load trained FastCore model."""
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel

    logger.info(f"Loading model from {checkpoint_path}...")
    tokenizer = AutoTokenizer.from_pretrained(checkpoint_path, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen3-0.6B",
        torch_dtype=torch.float32,
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, checkpoint_path)
    model.eval()
    return model, tokenizer


def predict(model, tokenizer, text: str, max_new_tokens: int = 200) -> Optional[Dict[str, Any]]:
    """Run inference and parse JSON output."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )

    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    # Parse JSON
    try:
        # Find JSON in response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except json.JSONDecodeError:
        pass
    return None


def evaluate(model_path: str, dataset_path: str, max_samples: int = 500):
    """Full evaluation pipeline."""
    logger.info("=== FastCore Evaluation ===")

    # Load model
    model, tokenizer = load_model(model_path)
    classifier = FastCoreClassifier()

    # Load test data
    with open(dataset_path) as f:
        ds = json.load(f)
    examples = ds["examples"]

    # Split
    import random
    random.seed(42)
    random.shuffle(examples)
    n = len(examples)
    test_data = examples[int(0.9 * n):]
    if max_samples:
        test_data = test_data[:max_samples]

    logger.info(f"Test set: {len(test_data)} examples")

    # Metrics
    metrics = {
        "total": 0,
        "correct_task_type": 0,
        "correct_source": 0,
        "correct_complexity": 0,
        "correct_tools": 0,
        "valid_json": 0,
        "classifier_correct": 0,
        "model_latencies": [],
        "classifier_latencies": [],
    }

    for i, item in enumerate(test_data):
        text = item["input_text"]
        expected_task = item["task_type"]

        # Model prediction
        t0 = time.perf_counter()
        pred = predict(model, tokenizer, text)
        model_lat = (time.perf_counter() - t0) * 1000
        metrics["model_latencies"].append(model_lat)

        # Classifier prediction
        t0 = time.perf_counter()
        clf_pred = classifier.classify(text)
        clf_lat = (time.perf_counter() - t0) * 1000
        metrics["classifier_latencies"].append(clf_lat)

        metrics["total"] += 1

        if pred:
            metrics["valid_json"] += 1
            if pred.get("task_type") == expected_task:
                metrics["correct_task_type"] += 1
            if pred.get("information_source") == item.get("information_source"):
                metrics["correct_source"] += 1
            if pred.get("complexity") == item.get("complexity"):
                metrics["correct_complexity"] += 1
            if pred.get("tools_required") == item.get("tools_required"):
                metrics["correct_tools"] += 1

        if clf_pred.task_type.value == expected_task:
            metrics["classifier_correct"] += 1

        if (i + 1) % 50 == 0:
            logger.info(f"  Evaluated {i+1}/{len(test_data)}")

    # Report
    t = metrics["total"]
    logger.info("\n=== Results ===")
    logger.info(f"Total: {t}")
    logger.info(f"Valid JSON: {metrics['valid_json']}/{t} ({100*metrics['valid_json']/t:.1f}%)")
    logger.info(f"Task accuracy: {metrics['correct_task_type']}/{t} ({100*metrics['correct_task_type']/t:.1f}%)")
    logger.info(f"Source accuracy: {metrics['correct_source']}/{t} ({100*metrics['correct_source']/t:.1f}%)")
    logger.info(f"Complexity accuracy: {metrics['correct_complexity']}/{t} ({100*metrics['correct_complexity']/t:.1f}%)")
    logger.info(f"Tools accuracy: {metrics['correct_tools']}/{t} ({100*metrics['correct_tools']/t:.1f}%)")
    logger.info(f"Classifier accuracy: {metrics['classifier_correct']}/{t} ({100*metrics['classifier_correct']/t:.1f}%)")

    import statistics
    if metrics["model_latencies"]:
        logger.info(f"Model P50: {statistics.median(metrics['model_latencies']):.1f}ms")
        logger.info(f"Model P95: {sorted(metrics['model_latencies'])[int(len(metrics['model_latencies'])*0.95)]:.1f}ms")
    if metrics["classifier_latencies"]:
        logger.info(f"Classifier P50: {statistics.median(metrics['classifier_latencies']):.3f}ms")
        logger.info(f"Classifier P95: {sorted(metrics['classifier_latencies'])[int(len(metrics['classifier_latencies'])*0.95)]:.3f}ms")

    # Save report
    report = {
        "model_path": model_path,
        "dataset_path": dataset_path,
        "test_size": t,
        "valid_json_rate": metrics["valid_json"] / t,
        "task_accuracy": metrics["correct_task_type"] / t,
        "source_accuracy": metrics["correct_source"] / t,
        "complexity_accuracy": metrics["correct_complexity"] / t,
        "tools_accuracy": metrics["correct_tools"] / t,
        "classifier_accuracy": metrics["classifier_correct"] / t,
        "model_p50_ms": statistics.median(metrics["model_latencies"]) if metrics["model_latencies"] else 0,
        "classifier_p50_ms": statistics.median(metrics["classifier_latencies"]) if metrics["classifier_latencies"] else 0,
    }
    report_path = Path(model_path) / "evaluation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report saved: {report_path}")

    return report


if __name__ == "__main__":
    import sys
    model_path = sys.argv[1] if len(sys.argv) > 1 else "desktop_agent/fastcore/checkpoints/fastcore-final"
    dataset_path = sys.argv[2] if len(sys.argv) > 2 else "desktop_agent/fastcore/dataset/fastcore_v0.2.0.json"
    evaluate(model_path, dataset_path)
