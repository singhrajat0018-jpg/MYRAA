"""Disagreement Engine -- handles conflicting specialist model outputs.

When specialist models produce contradictory results (e.g. bullish vs bearish,
high confidence vs low confidence), this engine analyzes the disagreement,
determines severity, inspects evidence quality, and recommends an action.

Must NOT blindly choose majority -- inspects evidence and confidence.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ..model_contract import ModelResult


class DisagreementSeverity(Enum):
    """Severity levels for model disagreement."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendedAction(Enum):
    """Actions the super-brain can take when disagreement occurs."""
    USE_HIGHEST_CONFIDENCE = "use_highest_confidence"
    REQUEST_ADDITIONAL_MODEL = "request_additional_model"
    LOWER_CONFIDENCE = "lower_confidence"
    ESCALATE_TO_SUPER_BRAIN = "escalate_to_super_brain"
    BLOCK_DECISION = "block_decision"


@dataclass
class ConflictingOutput:
    """Describes one side of a disagreement."""
    model_id: str
    output: Any
    confidence: float
    uncertainty: float
    evidence_summary: str
    stance: str  # e.g. "bullish", "bearish", "positive", "negative"


@dataclass
class DisagreementReport:
    """Complete analysis of a disagreement between specialist models."""
    has_disagreement: bool = False
    severity: DisagreementSeverity = DisagreementSeverity.NONE
    conflicting_outputs: list[ConflictingOutput] = field(default_factory=list)
    evidence_quality: float = 0.0
    recommended_action: RecommendedAction = RecommendedAction.USE_HIGHEST_CONFIDENCE
    confidence_gap: float = 0.0
    outlier_count: int = 0
    total_models: int = 0
    analysis_notes: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "has_disagreement": self.has_disagreement,
            "severity": self.severity.value,
            "recommended_action": self.recommended_action.value,
            "confidence_gap": round(self.confidence_gap, 3),
            "evidence_quality": round(self.evidence_quality, 3),
            "outlier_count": self.outlier_count,
            "total_models": self.total_models,
            "conflicting_count": len(self.conflicting_outputs),
            "analysis_notes": self.analysis_notes,
        }

class DisagreementEngine:
    """Analyzes disagreement between specialist model outputs.

    Thread-safe singleton. Does NOT blindly choose majority -- inspects
    evidence quality, confidence, uncertainty, and source reliability.
    """

    _instance: Optional[DisagreementEngine] = None
    _lock_class = threading.Lock()

    # severity thresholds (on 0-1 disagreement scale)
    _THRESHOLD_LOW = 0.15
    _THRESHOLD_MEDIUM = 0.35
    _THRESHOLD_HIGH = 0.60
    _THRESHOLD_CRITICAL = 0.80

    def __new__(cls, *args: Any, **kwargs: Any) -> DisagreementEngine:
        if cls._instance is None:
            with cls._lock_class:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._analysis_count: int = 0
        self._lock = threading.Lock()
        self._initialized = True

    @classmethod
    def new(cls) -> DisagreementEngine:
        return cls()

    @property
    def analysis_count(self) -> int:
        return self._analysis_count

    def analyze_disagreement(self, results: list[ModelResult]) -> DisagreementReport:
        """Analyze disagreement between specialist model outputs.

        Inspects evidence and confidence rather than blindly choosing majority.
        """
        with self._lock:
            self._analysis_count += 1

        if not results or len(results) < 2:
            return DisagreementReport(
                has_disagreement=False,
                severity=DisagreementSeverity.NONE,
                recommended_action=RecommendedAction.USE_HIGHEST_CONFIDENCE,
                total_models=len(results),
            )

        # compute disagreement metrics
        confidence_gap = self._compute_confidence_gap(results)
        output_divergence = self._compute_output_divergence(results)
        stance_groups = self._group_by_stance(results)
        evidence_quality = self._assess_evidence_quality(results)

        # overall disagreement score
        n_stances = len(stance_groups)
        if n_stances <= 1:
            disagreement_score = output_divergence
        else:
            disagreement_score = min(1.0, (
                confidence_gap * 0.3
                + output_divergence * 0.3
                + min(1.0, (n_stances - 1) * 0.2)
                + evidence_quality * 0.2
            ))

        severity = self._classify_severity(disagreement_score)
        has_disagreement = severity != DisagreementSeverity.NONE

        # build conflicting outputs list
        conflicting = self._build_conflicting_outputs(results, stance_groups)

        # detect outliers
        outlier_count = self._count_outliers(results)

        # determine recommended action
        action = self._recommend_action(
            severity, confidence_gap, evidence_quality, outlier_count, len(results),
        )

        # analysis notes
        notes = self._generate_notes(
            severity, confidence_gap, evidence_quality, stance_groups, outlier_count,
        )

        return DisagreementReport(
            has_disagreement=has_disagreement,
            severity=severity,
            conflicting_outputs=conflicting,
            evidence_quality=round(evidence_quality, 3),
            recommended_action=action,
            confidence_gap=round(confidence_gap, 3),
            outlier_count=outlier_count,
            total_models=len(results),
            analysis_notes=notes,
        )

    def _compute_confidence_gap(self, results: list[ModelResult]) -> float:
        """Compute the gap between highest and lowest confidence."""
        if not results:
            return 0.0
        confidences = [r.confidence for r in results]
        return max(confidences) - min(confidences)

    def _compute_output_divergence(self, results: list[ModelResult]) -> float:
        """Measure how much outputs diverge from each other."""
        if len(results) < 2:
            return 0.0

        # try to extract numeric signals from outputs
        numeric_values: list[float] = []
        for r in results:
            o = r.output
            if isinstance(o, (int, float)):
                numeric_values.append(float(o))
            elif hasattr(o, "trend_score"):
                numeric_values.append(float(o.trend_score))
            elif hasattr(o, "pattern_score"):
                numeric_values.append(float(o.pattern_score))
            elif hasattr(o, "confidence"):
                numeric_values.append(float(o.confidence))
            elif isinstance(o, dict):
                for key in ("trend_score", "signal", "confidence", "score"):
                    if key in o and isinstance(o[key], (int, float)):
                        numeric_values.append(float(o[key]))
                        break

        if len(numeric_values) >= 2:
            spread = max(numeric_values) - min(numeric_values)
            return min(1.0, spread)

        # string-based fallback
        str_outputs = [str(r.output)[:200] for r in results]
        unique = len(set(str_outputs))
        return min(1.0, (unique - 1) / max(len(results) - 1, 1))

    def _group_by_stance(self, results: list[ModelResult]) -> dict[str, list[ModelResult]]:
        """Group results by their directional stance."""
        groups: dict[str, list[ModelResult]] = {
            "positive": [], "negative": [], "neutral": [],
        }

        for r in results:
            stance = self._determine_stance(r)
            groups[stance].append(r)

        return {k: v for k, v in groups.items() if v}

    def _determine_stance(self, result: ModelResult) -> str:
        """Classify a result's directional stance."""
        o = result.output
        if o is None:
            return "neutral"

        # check for trend_score field (TradingAnalysis pattern)
        if hasattr(o, "trend_score"):
            if o.trend_score > 0.6:
                return "positive"
            elif o.trend_score < 0.4:
                return "negative"
            return "neutral"

        # check for pattern_score (TradingAnalysis)
        if hasattr(o, "pattern_score") and hasattr(o, "risk_signal"):
            signal = o.pattern_score * 0.6 + (1.0 - o.risk_signal) * 0.4
            if signal > 0.6:
                return "positive"
            elif signal < 0.4:
                return "negative"
            return "neutral"

        # dict-based output
        if isinstance(o, dict):
            for key in ("trend_score", "signal", "sentiment"):
                if key in o and isinstance(o[key], (int, float)):
                    val = float(o[key])
                    if val > 0.6:
                        return "positive"
                    elif val < 0.4:
                        return "negative"
                    return "neutral"

        return "neutral"

    def _assess_evidence_quality(self, results: list[ModelResult]) -> float:
        """Assess overall quality of evidence across all models.

        Higher quality means the disagreement is more meaningful and
        less likely due to noisy/poor inputs.
        """
        if not results:
            return 0.0

        scores: list[float] = []
        for r in results:
            score = 0.5

            # confidence contributes
            score += r.confidence * 0.2

            # low uncertainty is good evidence
            score += (1.0 - r.uncertainty) * 0.15

            # quality field
            score += r.quality * 0.15

            # warnings reduce quality
            if r.warnings:
                score -= len(r.warnings) * 0.05

            # fresh data is better evidence
            age_s = time.time() - r.timestamp
            if age_s < 30:
                score += 0.1
            elif age_s > 300:
                score -= 0.1

            scores.append(max(0.0, min(1.0, score)))

        return sum(scores) / len(scores)

    def _classify_severity(self, disagreement_score: float) -> DisagreementSeverity:
        """Map disagreement score to severity level."""
        if disagreement_score < self._THRESHOLD_LOW:
            return DisagreementSeverity.NONE
        elif disagreement_score < self._THRESHOLD_MEDIUM:
            return DisagreementSeverity.LOW
        elif disagreement_score < self._THRESHOLD_HIGH:
            return DisagreementSeverity.MEDIUM
        elif disagreement_score < self._THRESHOLD_CRITICAL:
            return DisagreementSeverity.HIGH
        return DisagreementSeverity.CRITICAL

    def _count_outliers(self, results: list[ModelResult]) -> int:
        """Count results that are statistical outliers."""
        if len(results) < 3:
            return 0

        confidences = [r.confidence for r in results]
        mean_c = sum(confidences) / len(confidences)
        variance = sum((c - mean_c) ** 2 for c in confidences) / len(confidences)
        std = variance ** 0.5

        if std < 0.01:
            return 0

        return sum(1 for c in confidences if abs(c - mean_c) > 1.5 * std)

    def _build_conflicting_outputs(
        self, results: list[ModelResult], stance_groups: dict[str, list[ModelResult]],
    ) -> list[ConflictingOutput]:
        """Build the list of conflicting outputs from each stance group."""
        conflicting: list[ConflictingOutput] = []

        for stance, group in stance_groups.items():
            if len(group) <= 1:
                continue
            for r in group:
                evidence = self._summarize_evidence(r)
                conflicting.append(ConflictingOutput(
                    model_id=r.model_id,
                    output=r.output,
                    confidence=r.confidence,
                    uncertainty=r.uncertainty,
                    evidence_summary=evidence,
                    stance=stance,
                ))

        return conflicting

    def _summarize_evidence(self, result: ModelResult) -> str:
        """Produce a brief evidence summary for a result."""
        parts: list[str] = []
        parts.append(f"confidence={result.confidence:.2f}")
        parts.append(f"uncertainty={result.uncertainty:.2f}")

        if result.warnings:
            parts.append(f"warnings={len(result.warnings)}")

        o = result.output
        if o is not None:
            if hasattr(o, "regime"):
                parts.append(f"regime={o.regime}")
            if hasattr(o, "patterns_detected") and o.patterns_detected:
                parts.append(f"patterns={o.patterns_detected[:3]}")
            if hasattr(o, "scene_description") and o.scene_description:
                parts.append(f"scene={o.scene_description[:50]}")

        return "; ".join(parts)

    def _recommend_action(
        self,
        severity: DisagreementSeverity,
        confidence_gap: float,
        evidence_quality: float,
        outlier_count: int,
        total_models: int,
    ) -> RecommendedAction:
        """Determine the recommended action based on disagreement analysis.

        Must NOT blindly choose majority -- inspects evidence and confidence.
        """
        # CRITICAL: block decisions
        if severity == DisagreementSeverity.CRITICAL:
            return RecommendedAction.BLOCK_DECISION

        # HIGH severity
        if severity == DisagreementSeverity.HIGH:
            if evidence_quality < 0.4:
                return RecommendedAction.BLOCK_DECISION
            if outlier_count > 0:
                return RecommendedAction.REQUEST_ADDITIONAL_MODEL
            return RecommendedAction.ESCALATE_TO_SUPER_BRAIN

        # MEDIUM severity
        if severity == DisagreementSeverity.MEDIUM:
            if confidence_gap > 0.4 and evidence_quality > 0.6:
                return RecommendedAction.USE_HIGHEST_CONFIDENCE
            if outlier_count >= total_models // 2:
                return RecommendedAction.REQUEST_ADDITIONAL_MODEL
            return RecommendedAction.LOWER_CONFIDENCE

        # LOW severity
        if severity == DisagreementSeverity.LOW:
            if confidence_gap > 0.3:
                return RecommendedAction.USE_HIGHEST_CONFIDENCE
            return RecommendedAction.LOWER_CONFIDENCE

        # NONE
        return RecommendedAction.USE_HIGHEST_CONFIDENCE

    def _generate_notes(
        self,
        severity: DisagreementSeverity,
        confidence_gap: float,
        evidence_quality: float,
        stance_groups: dict[str, list[ModelResult]],
        outlier_count: int,
    ) -> list[str]:
        """Generate human-readable analysis notes."""
        notes: list[str] = []

        n_stances = len(stance_groups)
        if n_stances >= 3:
            notes.append(f"Three distinct stances detected: {list(stance_groups.keys())}")
        elif n_stances == 2:
            notes.append(
                f"Two-way disagreement: {list(stance_groups.keys())} "
                f"(sizes: {[len(v) for v in stance_groups.values()]})"
            )

        if confidence_gap > 0.4:
            notes.append(f"Large confidence gap: {confidence_gap:.2f} -- strong disagreement")
        elif confidence_gap > 0.2:
            notes.append(f"Moderate confidence gap: {confidence_gap:.2f}")

        if evidence_quality < 0.3:
            notes.append("Low evidence quality -- disagreement may stem from poor inputs")
        elif evidence_quality > 0.7:
            notes.append("High evidence quality -- disagreement is substantively meaningful")

        if outlier_count > 0:
            notes.append(f"{outlier_count} outlier(s) detected -- may be noise")

        if severity == DisagreementSeverity.CRITICAL:
            notes.append("CRITICAL severity -- recommend blocking decision until resolved")
        elif severity == DisagreementSeverity.HIGH:
            notes.append("HIGH severity -- recommend escalation or additional model")
        elif severity == DisagreementSeverity.MEDIUM:
            notes.append("MEDIUM severity -- lower confidence in combined output")

        return notes

    def recommend_action(self, report: DisagreementReport) -> RecommendedAction:
        """Convenience wrapper to get the recommended action from a report."""
        return report.recommended_action

    def reset(self) -> None:
        """Reset counters -- useful for tests."""
        with self._lock:
            self._analysis_count = 0

    @classmethod
    def reset_singleton(cls) -> None:
        with cls._lock_class:
            cls._instance = None
