#!/usr/bin/env python3
"""
AI Manager 4.1 benchmark evaluator.

Pipeline:
  development split  -> fit Platt calibration (writes calibration_params.json)
  held-out split     -> full metrics (never used for fitting)

Metrics: intent/domain/capability/output/execution-mode/reasoning-depth/
freshness/risk accuracy, tool precision/recall, Brier + ECE (raw vs
calibrated), bucket table, false high/low-confidence rates, latency
p50/p95/p99, decision accuracy, multi-intent precision/recall, reference
resolution accuracy, and per-category + Hinglish breakdowns.
"""

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_agent.brain.ai import AIManager  # noqa: E402
from desktop_agent.brain.ai.calibration import (  # noqa: E402
    platt_fit, platt_transform, brier_score, expected_calibration_error,
    accuracy_by_bucket, false_high_confidence_rate,
    false_low_confidence_rate, bucket_accuracy,
)
from desktop_agent.brain.ai.context_snapshot import ContextSnapshot  # noqa: E402
from desktop_agent.brain.ai.tool_resolver import resolve as resolve_tool_id  # noqa: E402

HERE = Path(__file__).resolve().parent
CALIB_PARAMS = Path(__file__).resolve().parents[1] / "desktop_agent" / "brain" / "ai" / "calibration_params.json"

_DEFAULT_SNAPSHOT = ContextSnapshot(
    conversation_relevance="user has been analyzing nifty trend",
    active_task="analyze nifty trend",
    active_app="Notepad",
    browser_summary="chrome with a stock analysis tab open",
    portfolio="reliance, tcs, infosys, hdfc bank",
    previous_request="analyze nifty trend",
    previous_route={"intent": "TRADING_ANALYSIS", "domain": "TRADING",
                    "output_type": "MARKET_ANALYSIS", "capability": "TRADING_ENGINE"},
)


def _snapshot_for(item: Dict) -> Optional[ContextSnapshot]:
    if item.get("category") == "CONTEXTUAL":
        return _DEFAULT_SNAPSHOT
    return None


def _load(name: str) -> List[Dict]:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def _acc(pred: str, expected: str) -> int:
    return 1 if pred == expected else 0


def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 2) if den else 0.0


def evaluate() -> Dict:
    dev = _load("ai_manager_41_development.json")
    held = _load("ai_manager_41_held_out.json")

    # ---- 1) Fit calibration on DEVELOPMENT only ----
    fit_manager = AIManager()
    fit_pairs: List = []
    for item in dev:
        r = fit_manager.route(user_prompt=item["request"], context=_snapshot_for(item))
        label = 1 if r.intent.name == item["intent"] else 0
        fit_pairs.append((r.route_score, label))
    a, b = platt_fit(fit_pairs)
    CALIB_PARAMS.write_text(json.dumps({"a": a, "b": b, "n": len(fit_pairs)},
                                       indent=2), encoding="utf-8")
    print(f"[fit] development n={len(fit_pairs)} calibration a={a:.3f} b={b:.3f}")

    # ---- 2) Held-out evaluation with a fresh manager (loads fitted params) ----
    manager = AIManager()

    m: Dict[str, List] = {
        "intent": [], "domain": [], "capability": [], "output_type": [],
        "execution_mode": [], "reasoning_depth": [], "freshness": [],
        "risk_level": [], "tool_hit": [], "tool_exp": [], "decision": [],
        "multi": [], "multi_correct": [], "reference": [],
        "latencies": [], "route_scores": [], "calibrated": [], "y_true": [],
        "hinglish_intent": [], "hinglish_domain": [],
    }
    by_cat: Dict[str, Dict] = {}
    multi_tp = multi_fp = multi_tn = multi_fn = 0
    ref_correct = ref_total = 0

    for item in held:
        start = time.perf_counter()
        r = manager.route(user_prompt=item["request"], context=_snapshot_for(item))
        latency = (time.perf_counter() - start) * 1000
        m["latencies"].append(latency)
        m["route_scores"].append(r.route_score)
        m["calibrated"].append(r.calibrated_confidence)

        intent_ok = _acc(r.intent.name, item["intent"])
        m["intent"].append(intent_ok)
        m["y_true"].append(intent_ok)
        m["domain"].append(_acc(r.domain.name, item["domain"]))
        m["capability"].append(_acc(r.capability or "", item["capability"]))
        m["output_type"].append(_acc((r.output_type.name if r.output_type else ""), item["output_type"]))
        m["execution_mode"].append(_acc(r.execution_mode.name, item["execution_mode"]))
        m["reasoning_depth"].append(_acc(r.reasoning_depth.name, item["reasoning_depth"]))
        m["freshness"].append(_acc(r.freshness.name, item["freshness"]))
        m["risk_level"].append(_acc(r.risk_level.name, item["risk_level"]))

        expected_tools = set(item.get("tools_required") or [])
        actual_tools = set(r.tools_required or [])
        expected_real = set()
        for tid in expected_tools:
            expected_real.update(resolve_tool_id(tid) or [tid])
        m["tool_hit"].append(1 if actual_tools & expected_real else 0)
        m["tool_exp"].append(1 if expected_tools else 0)

        if item.get("expected_decision") and item["expected_decision"] != "ROUTE":
            m["decision"].append(_acc(r.decision, item["expected_decision"]))

        # Multi-intent detection
        is_multi = bool(item.get("multi_intent"))
        pred_multi = r.is_multi
        m["multi"].append(is_multi)
        if pred_multi and is_multi:
            multi_tp += 1
        elif pred_multi and not is_multi:
            multi_fp += 1
        elif not pred_multi and not is_multi:
            multi_tn += 1
        else:
            multi_fn += 1
        if is_multi and pred_multi and item["intent"] in {r.intent.name, r.primary_intent.name}:
            m["multi_correct"].append(1)
        elif not is_multi:
            m["multi_correct"].append(1)
        else:
            m["multi_correct"].append(0)

        # Reference resolution
        if item.get("reference_kind") and item["reference_kind"] != "none":
            ref_total += 1
            if r.intent.name == item["intent"] and r.domain.name == item["domain"]:
                ref_correct += 1

        if item["language"] == "HINGLISH":
            m["hinglish_intent"].append(intent_ok)
            m["hinglish_domain"].append(_acc(r.domain.name, item["domain"]))

        cat = item.get("category", "?")
        bucket = by_cat.setdefault(cat, {"n": 0, "intent": 0, "domain": 0, "lat": []})
        bucket["n"] += 1
        bucket["intent"] += intent_ok
        bucket["domain"] += _acc(r.domain.name, item["domain"])
        bucket["lat"].append(latency)

    n = len(held)
    y_true = m["y_true"]
    raw_probs = m["route_scores"]
    cal_probs = m["calibrated"]

    lat = sorted(m["latencies"])
    def _lat(q):
        if not lat:
            return 0.0
        return round(statistics.quantiles(lat, n=100)[q - 1], 3)

    report = {
        "items": n,
        "intent_accuracy": _pct(sum(m["intent"]), n),
        "domain_accuracy": _pct(sum(m["domain"]), n),
        "capability_accuracy": _pct(sum(m["capability"]), n),
        "output_type_accuracy": _pct(sum(m["output_type"]), n),
        "execution_mode_accuracy": _pct(sum(m["execution_mode"]), n),
        "reasoning_depth_accuracy": _pct(sum(m["reasoning_depth"]), n),
        "freshness_accuracy": _pct(sum(m["freshness"]), n),
        "risk_level_accuracy": _pct(sum(m["risk_level"]), n),
        "tool_hit_rate": _pct(sum(m["tool_hit"]), sum(m["tool_exp"])),
        "decision_accuracy": _pct(sum(m["decision"]), len(m["decision"])),
        "brier_raw": round(brier_score(y_true, raw_probs), 4),
        "brier_calibrated": round(brier_score(y_true, cal_probs), 4),
        "ece_raw": round(expected_calibration_error(y_true, raw_probs), 4),
        "ece_calibrated": round(expected_calibration_error(y_true, cal_probs), 4),
        "false_high_confidence_rate": round(false_high_confidence_rate(y_true, cal_probs), 4),
        "false_low_confidence_rate": round(false_low_confidence_rate(y_true, cal_probs), 4),
        "decision_accuracy_calibrated": round(bucket_accuracy(y_true, cal_probs), 4),
        "bucket_table": accuracy_by_bucket(y_true, cal_probs),
        "latency_ms_p50": _lat(50),
        "latency_ms_p95": _lat(95),
        "latency_ms_p99": _lat(99),
        "multi_intent_precision": round(multi_tp / (multi_tp + multi_fp), 4) if (multi_tp + multi_fp) else 0.0,
        "multi_intent_recall": round(multi_tp / (multi_tp + multi_fn), 4) if (multi_tp + multi_fn) else 0.0,
        "multi_route_accuracy": _pct(sum(m["multi_correct"]), n),
        "reference_resolution_accuracy": _pct(ref_correct, ref_total) if ref_total else None,
        "hinglish_intent_accuracy": _pct(sum(m["hinglish_intent"]), len(m["hinglish_intent"])),
        "hinglish_domain_accuracy": _pct(sum(m["hinglish_domain"]), len(m["hinglish_domain"])),
        "calibration_params": {"a": a, "b": b},
    }

    for cat, b in sorted(by_cat.items()):
        b["intent_accuracy"] = _pct(b["intent"], b["n"])
        b["domain_accuracy"] = _pct(b["domain"], b["n"])
        b["avg_latency_ms"] = round(sum(b["lat"]) / len(b["lat"]), 3)
        b.pop("lat", None)
        b.pop("intent", None)
        b.pop("domain", None)
    report["by_category"] = by_cat

    (HERE / "ai_manager_41_evaluation_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown(report)
    return report


def _write_markdown(r: Dict) -> None:
    lines = [
        "# AI Manager 4.1 — Held-out Evaluation Report",
        "",
        f"- Items: **{r['items']}**",
        f"- Calibration fitted on development split (a={r['calibration_params']['a']:.3f}, "
        f"b={r['calibration_params']['b']:.3f}); reported metrics are held-out only.",
        "",
        "## Routing accuracy",
        "",
        "| Dimension | Accuracy |",
        "|---|---|",
    ]
    for key, label in [("intent_accuracy", "Intent"), ("domain_accuracy", "Domain"),
                       ("capability_accuracy", "Capability"), ("output_type_accuracy", "Output type"),
                       ("execution_mode_accuracy", "Execution mode"), ("reasoning_depth_accuracy", "Reasoning depth"),
                       ("freshness_accuracy", "Freshness"), ("risk_level_accuracy", "Risk level"),
                       ("tool_hit_rate", "Tool requirement hit"), ("decision_accuracy", "Decision (CLARIFY/ABSTAIN)"),
                       ("multi_route_accuracy", "Multi-intent route correctness"),
                       ("reference_resolution_accuracy", "Reference resolution"),
                       ("hinglish_intent_accuracy", "Hinglish intent"),
                       ("hinglish_domain_accuracy", "Hinglish domain")]:
        val = r.get(key)
        if val is None:
            val = "n/a"
        lines.append(f"| {label} | {val} |")

    lines += [
        "",
        "## Calibration (held-out)",
        "",
        f"- Brier raw: **{r['brier_raw']}** vs calibrated: **{r['brier_calibrated']}**",
        f"- ECE raw: **{r['ece_raw']}** vs calibrated: **{r['ece_calibrated']}**",
        f"- False-high-confidence rate (>=0.8): **{r['false_high_confidence_rate']}**",
        f"- False-low-confidence rate (<0.3): **{r['false_low_confidence_rate']}**",
        f"- Decision accuracy (calibrated >= 0.5): **{r['decision_accuracy_calibrated']}**",
        "",
        "### Bucket table (calibrated)",
        "",
        "| Bucket | n | accuracy | mean conf |",
        "|---|---|---|---|",
    ]
    for b in r["bucket_table"]:
        acc = "-" if b["accuracy"] is None else f"{b['accuracy']:.3f}"
        conf = "-" if b["mean_confidence"] is None else f"{b['mean_confidence']:.3f}"
        lines.append(f"| {b['bucket']} | {b['n']} | {acc} | {conf} |")

    lines += [
        "",
        "## Latency",
        "",
        f"- p50: **{r['latency_ms_p50']} ms**, p95: **{r['latency_ms_p95']} ms**, "
        f"p99: **{r['latency_ms_p99']} ms**",
        "",
        "## Multi-intent decomposition",
        "",
        f"- Precision: **{r['multi_intent_precision']}**, Recall: **{r['multi_intent_recall']}**",
        "",
        "## Per-category",
        "",
        "| Category | n | intent | domain | avg lat (ms) |",
        "|---|---|---|---|---|",
    ]
    for cat, b in sorted(r["by_category"].items()):
        lines.append(f"| {cat} | {b['n']} | {b['intent_accuracy']} | {b['domain_accuracy']} | {b['avg_latency_ms']} |")

    (HERE / "ai_manager_41_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    evaluate()