"""AI Manager 4.1 — confidence calibration support.

Pure measurement / fitting helpers for the calibrated confidence layer
(Phase 5/6). The AI Manager keeps its existing heuristic confidence for
compatibility and adds a *separate* statistically-calibrated layer on top.

- :func:`platt_fit` fits a logistic map raw/route score -> probability on a
  DEVELOPMENT split (never on held-out).
- :func:`platt_transform` applies the fitted map.
- Brier score, Expected Calibration Error (ECE), accuracy-by-bucket and
  false high/low-confidence rates are computed for reporting.

This module contains no routing logic and no benchmark-specific branches.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple


# ---------------------------------------------------------------------------
# Platt (logistic) calibration
# ---------------------------------------------------------------------------

def platt_transform(raw: float, a: float = 1.0, b: float = 0.0) -> float:
    """Map a raw score in [0,1] through the logistic calibration curve."""
    try:
        z = a * float(raw) + b
        z = max(min(z, 50.0), -50.0)
        return 1.0 / (1.0 + math.exp(-z))
    except Exception:
        return raw


def platt_fit(pairs: Sequence[Tuple[float, int]], iters: int = 60,
              lr: float = 0.1) -> Tuple[float, float]:
    """Fit (a, b) for Platt scaling by gradient descent on log-loss.

    ``pairs`` is a sequence of (raw_score, label) where label is 1 when the
    routed result was correct. Returns (a, b).
    """
    if not pairs:
        return 1.0, 0.0
    a = 1.0
    b = 0.0
    n = len(pairs)
    # Standardize raw scores to reduce conditioning problems.
    raws = [float(r) for r, _ in pairs]
    mean = sum(raws) / n
    std = (sum((r - mean) ** 2 for r in raws) / n) ** 0.5 or 1.0

    def p(x: float) -> float:
        z = a * ((x - mean) / std) + b
        z = max(min(z, 50.0), -50.0)
        return 1.0 / (1.0 + math.exp(-z))

    for _ in range(iters):
        grad_a = 0.0
        grad_b = 0.0
        for raw, label in pairs:
            x = (float(raw) - mean) / std
            p_i = p(float(raw))
            err = p_i - label
            grad_a += err * x
            grad_b += err
        a -= lr * grad_a / n
        b -= lr * grad_b / n
    return a, b


# ---------------------------------------------------------------------------
# Calibration metrics
# ---------------------------------------------------------------------------

def brier_score(y_true: Sequence[int], probs: Sequence[float]) -> float:
    """Mean squared error between binary labels and predicted probabilities."""
    if not y_true:
        return 0.0
    return sum((p - int(y)) ** 2 for p, y in zip(probs, y_true)) / len(y_true)


def expected_calibration_error(y_true: Sequence[int], probs: Sequence[float],
                               bins: int = 10) -> float:
    """ECE: mean |accuracy(bin) - mean_conf(bin)| weighted by bin size."""
    if not y_true:
        return 0.0
    edges = [i / bins for i in range(bins + 1)]
    total = len(y_true)
    ece = 0.0
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        idx = [j for j, p in enumerate(probs) if lo <= p < (1.0001 if hi >= 1.0 else hi)]
        if not idx:
            continue
        acc = sum(1 for j in idx if int(y_true[j]) == 1) / len(idx)
        conf = sum(probs[j] for j in idx) / len(idx)
        ece += (len(idx) / total) * abs(acc - conf)
    return ece


def accuracy_by_bucket(y_true: Sequence[int], probs: Sequence[float],
                       bins: int = 10) -> List[dict]:
    """Per-bucket accuracy, mean confidence and count (for reporting)."""
    out = []
    edges = [i / bins for i in range(bins + 1)]
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        idx = [j for j, p in enumerate(probs) if lo <= p < (1.0001 if hi >= 1.0 else hi)]
        if not idx:
            out.append({"bucket": f"[{lo:.1f},{hi:.1f})", "n": 0,
                        "accuracy": None, "mean_confidence": None})
            continue
        acc = sum(1 for j in idx if int(y_true[j]) == 1) / len(idx)
        conf = sum(probs[j] for j in idx) / len(idx)
        out.append({"bucket": f"[{lo:.1f},{hi:.1f})", "n": len(idx),
                    "accuracy": round(acc, 4), "mean_confidence": round(conf, 4)})
    return out


def false_high_confidence_rate(y_true: Sequence[int], probs: Sequence[float],
                               threshold: float = 0.8) -> float:
    """Rate at which incorrect routes are emitted with high confidence."""
    high = [(int(y), float(p)) for y, p in zip(y_true, probs) if p >= threshold]
    if not high:
        return 0.0
    return sum(1 for y, _ in high if y == 0) / len(high)


def false_low_confidence_rate(y_true: Sequence[int], probs: Sequence[float],
                              threshold: float = 0.3) -> float:
    """Rate at which correct routes are emitted with low confidence."""
    low = [(int(y), float(p)) for y, p in zip(y_true, probs) if p < threshold]
    if not low:
        return 0.0
    return sum(1 for y, _ in low if y == 1) / len(low)


def bucket_accuracy(y_true: Sequence[int], probs: Sequence[float]) -> float:
    """Overall binary accuracy of the calibrated decision (>=0.5 => correct)."""
    if not y_true:
        return 0.0
    hits = sum(1 for y, p in zip(y_true, probs) if (p >= 0.5) == (int(y) == 1))
    return hits / len(y_true)