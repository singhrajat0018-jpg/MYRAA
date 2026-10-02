"""Personalization Neural Specialist — Phase F.

Uses existing Memory 2.0 (UnifiedMemoryManager) for preference intelligence.

Flow:
Memory 2.0 (preference/procedural records) -> Personalization Neural Model
-> ranked preferences, workflow recommendations, response style -> Super-Brain

DO NOT duplicate memory storage. This specialist *reads* Memory 2.0 and
produces personalization signals consumed by the brain pipeline.
"""

from __future__ import annotations

import logging
import math
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from ..model_contract import (
    ModelSpec, ModelResult, InferenceRequest, ModelDomain, ModelModality,
    LatencyClass, ModelDeployment, ModelStatus,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

@dataclass
class PersonalizationResult:
    """Structured output from the personalization specialist."""
    ranked_preferences: list[dict] = field(default_factory=list)
    recommended_workflow: Optional[dict] = None
    response_style: dict = field(default_factory=dict)
    confidence: float = 0.5
    reasoning: str = ""
    safety_overridden: bool = False


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

@dataclass
class PreferenceEntry:
    """A single preference pulled from Memory 2.0."""
    key: str = ""
    value: Any = None
    weight: float = 1.0
    source: str = ""
    recency_s: float = 0.0
    frequency: int = 1
    provenance: str = ""


@dataclass
class WorkflowPattern:
    """A successful workflow observed in memory."""
    name: str = ""
    steps: list[str] = field(default_factory=list)
    success_count: int = 0
    avg_duration_s: float = 0.0
    last_used_s: float = 0.0
    context_tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Safety boundary — personalisation must never override explicit instructions
# ---------------------------------------------------------------------------

_SAFETY_KEYWORDS = frozenset({
    "safety", "permission", "blocked", "denied", "override", "restriction",
    "critical", "emergency", "halt", "stop", "unsafe", "danger",
})

_RECENCY_WEIGHT = 0.40
_FREQ_WEIGHT = 0.35
_CONTEXT_WEIGHT = 0.25


# ---------------------------------------------------------------------------
# Specialist
# ---------------------------------------------------------------------------

class PersonalizationSpecialist:
    """Personalisation specialist model that consumes Memory 2.0 signals."""

    SPEC = ModelSpec(
        model_id="personalization_specialist_v1",
        domain=ModelDomain.PERSONALIZATION,
        version="1.0.0",
        modality=ModelModality.STRUCTURED,
        capabilities=[
            "preference_ranking",
            "workflow_recommendation",
            "response_style_adaptation",
            "interaction_pattern_learning",
        ],
        input_schema={
            "user_preferences": "list[dict]",
            "successful_workflows": "list[dict]",
            "communication_style": "dict",
            "project_patterns": "dict",
            "interaction_history": "list[dict]",
            "safety_context": "dict",
        },
        output_schema={
            "result": "PersonalizationResult",
            "confidence": "float",
        },
        latency_class=LatencyClass.FAST,
        deployment=ModelDeployment.LOCAL,
        resource_requirements={"min_memory_mb": 64},
        provider="local",
        description=(
            "Reads Memory 2.0 preference/procedural records and produces "
            "ranking, workflow, and style signals for the brain pipeline. "
            "Never overrides safety or explicit user instructions."
        ),
    )

    def __init__(self, memory_manager: Any = None):
        self._memory = memory_manager
        self._status = ModelStatus.ACTIVE
        self._health_score: float = 1.0
        self._total_calls: int = 0
        self._failures: int = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def model_id(self) -> str:
        return self.SPEC.model_id

    @property
    def status(self) -> ModelStatus:
        return self._status

    def health_score(self) -> float:
        with self._lock:
            return self._health_score

    def reset_health(self) -> None:
        with self._lock:
            self._health_score = 1.0
            self._failures = 0
            self._total_calls = 0

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def inference(self, request: InferenceRequest) -> ModelResult:
        start = time.perf_counter()
        self._total_calls += 1

        try:
            ctx = request.context
            prefs_raw: list[dict] = list(ctx.get("user_preferences", []))
            workflows_raw: list[dict] = list(ctx.get("successful_workflows", []))
            comm_style: dict = dict(ctx.get("communication_style", {}))
            project_patterns: dict = dict(ctx.get("project_patterns", {}))
            history: list[dict] = list(ctx.get("interaction_history", []))
            safety_ctx: dict = dict(ctx.get("safety_context", {}))

            if self._memory is not None:
                prefs_raw = prefs_raw or self._load_preferences()
                workflows_raw = workflows_raw or self._load_workflows()
                comm_style = comm_style or self._load_communication_style()
                project_patterns = project_patterns or self._load_project_patterns()

            safety_flag = self._check_safety_boundary(safety_ctx, prefs_raw)
            if safety_flag:
                elapsed = (time.perf_counter() - start) * 1000
                self._update_health(True)
                return ModelResult(
                    model_id=self.model_id,
                    output=PersonalizationResult(
                        safety_overridden=True,
                        reasoning="Safety boundary active - personalisation disabled.",
                    ),
                    confidence=1.0,
                    uncertainty=0.0,
                    latency_ms=elapsed,
                    timestamp=time.time(),
                    source="personalization_specialist_safety_gate",
                    version=self.SPEC.version,
                )

            prefs = [
                PreferenceEntry(**p) if isinstance(p, dict) and "key" in p
                else PreferenceEntry()
                for p in prefs_raw
            ]
            workflows = [
                WorkflowPattern(**w) if isinstance(w, dict) and "name" in w
                else WorkflowPattern()
                for w in workflows_raw
            ]

            ranked = self._rank_preferences(prefs, history, project_patterns)
            workflow_rec = self._recommend_workflow(workflows, project_patterns, history)
            style = self._adapt_response_style(comm_style, history)

            confidence = self._compute_confidence(prefs, workflows, history)
            reasoning = self._build_reasoning(ranked, workflow_rec, style, confidence)

            result = PersonalizationResult(
                ranked_preferences=ranked,
                recommended_workflow=workflow_rec,
                response_style=style,
                confidence=confidence,
                reasoning=reasoning,
                safety_overridden=False,
            )

            elapsed = (time.perf_counter() - start) * 1000
            self._update_health(True)

            return ModelResult(
                model_id=self.model_id,
                output=result,
                confidence=confidence,
                uncertainty=1.0 - confidence,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="personalization_specialist",
                version=self.SPEC.version,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            self._failures += 1
            self._update_health(False)
            log.warning("Personalization inference failed: %s", exc)
            return ModelResult(
                model_id=self.model_id,
                output=PersonalizationResult(confidence=0.0, reasoning=str(exc)),
                confidence=0.0,
                uncertainty=1.0,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="personalization_specialist_error",
                warnings=[str(exc)],
                version=self.SPEC.version,
            )

    # ------------------------------------------------------------------
    # Memory 2.0 loaders (optional — caller may also pass context directly)
    # ------------------------------------------------------------------

    def _load_preferences(self) -> list[dict]:
        try:
            records = self._memory.query(type_tag="preference", limit=100)
            out: list[dict] = []
            for r in records:
                data = getattr(r, "content", None) or getattr(r, "data", {})
                if isinstance(data, dict):
                    out.append(data)
            return out
        except Exception:
            return []

    def _load_workflows(self) -> list[dict]:
        try:
            records = self._memory.query(type_tag="procedural", limit=50)
            out: list[dict] = []
            for r in records:
                data = getattr(r, "content", None) or getattr(r, "data", {})
                if isinstance(data, dict):
                    out.append(data)
            return out
        except Exception:
            return []

    def _load_communication_style(self) -> dict:
        try:
            records = self._memory.query(type_tag="preference", limit=10)
            for r in records:
                data = getattr(r, "content", None) or getattr(r, "data", {})
                if isinstance(data, dict) and "communication_style" in data:
                    return dict(data["communication_style"])
        except Exception:
            pass
        return {}

    def _load_project_patterns(self) -> dict:
        try:
            records = self._memory.query(type_tag="project", limit=20)
            patterns: dict = {}
            for r in records:
                data = getattr(r, "content", None) or getattr(r, "data", {})
                if isinstance(data, dict):
                    patterns.update(data)
            return patterns
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Safety
    # ------------------------------------------------------------------

    @staticmethod
    def _check_safety_boundary(safety_ctx: dict, prefs: list[dict]) -> bool:
        """Return True if safety context blocks personalisation.

        Personalisation MUST NOT override:
        - Explicit safety flags in the safety context.
        - Explicit user instructions that contain safety-critical keywords.
        """
        if safety_ctx.get("safety_critical") or safety_ctx.get("block_personalisation"):
            return True

        for p in prefs:
            val = str(p.get("value", "")).lower()
            if any(kw in val for kw in _SAFETY_KEYWORDS):
                return True
        return False

    # ------------------------------------------------------------------
    # Core: preference ranking
    # ------------------------------------------------------------------

    @staticmethod
    def _rank_preferences(
        prefs: list[PreferenceEntry],
        history: list[dict],
        project_patterns: dict,
    ) -> list[dict]:
        """Score and rank preferences by weighted recency, frequency, and context fit.

        Scoring formula per preference:
            score = (recency_weight * recency_factor)
                  + (frequency_weight * log2(frequency + 1))
                  + (context_weight * context_match)
        multiplied by the preference weight.
        """
        if not prefs:
            return []

        active_tags: set[str] = set()
        for entry in history[-30:]:
            if isinstance(entry, dict):
                active_tags.update(entry.get("tags", []))
        for tags in project_patterns.values():
            if isinstance(tags, (list, set)):
                active_tags.update(tags)

        scored: list[dict] = []
        for p in prefs:
            recency_factor = 1.0 / (1.0 + (p.recency_s / 3600.0))
            freq_score = math.log2(p.frequency + 1)
            context_match = 1.0 if (p.key in active_tags or p.source in active_tags) else 0.3

            score = (
                _RECENCY_WEIGHT * recency_factor
                + _FREQ_WEIGHT * freq_score
                + _CONTEXT_WEIGHT * context_match
            ) * p.weight

            scored.append({
                "key": p.key,
                "value": p.value,
                "score": round(score, 4),
                "source": p.source,
                "provenance": p.provenance,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    # ------------------------------------------------------------------
    # Core: workflow recommendation
    # ------------------------------------------------------------------

    @staticmethod
    def _recommend_workflow(
        workflows: list[WorkflowPattern],
        project_patterns: dict,
        history: list[dict],
    ) -> Optional[dict]:
        """Pick the best workflow based on success rate, recency, and context fit."""
        if not workflows:
            return None

        best: Optional[WorkflowPattern] = None
        best_score = -1.0

        active_tags: set[str] = set()
        for entry in history[-30:]:
            if isinstance(entry, dict):
                active_tags.update(entry.get("tags", []))

        for w in workflows:
            success_rate = w.success_count / max(1, w.success_count + 1)
            recency_factor = 1.0 / (1.0 + (w.last_used_s / 86400.0))
            tag_match = sum(1 for t in w.context_tags if t in active_tags)
            context_score = min(1.0, tag_match / max(1, len(w.context_tags)))

            score = 0.50 * success_rate + 0.30 * recency_factor + 0.20 * context_score
            if score > best_score:
                best_score = score
                best = w

        if best is None:
            return None

        return {
            "name": best.name,
            "steps": best.steps,
            "success_count": best.success_count,
            "avg_duration_s": best.avg_duration_s,
            "context_tags": best.context_tags,
            "score": round(best_score, 4),
        }

    # ------------------------------------------------------------------
    # Core: response style adaptation
    # ------------------------------------------------------------------

    @staticmethod
    def _adapt_response_style(
        comm_style: dict,
        history: list[dict],
    ) -> dict:
        """Derive the preferred communication style from history and stored prefs.

        Adaptable dimensions:
        - verbosity:    "terse" | "normal" | "verbose"
        - tone:         "formal" | "neutral" | "casual"
        - language:     base language code (e.g. "en", "hi", "hi-en")
        - detail_level: "summary" | "standard" | "detailed"
        """
        style: dict = {
            "verbosity": comm_style.get("verbosity", "normal"),
            "tone": comm_style.get("tone", "neutral"),
            "language": comm_style.get("language", "en"),
            "detail_level": comm_style.get("detail_level", "standard"),
        }

        if not history:
            return style

        recent = history[-20:]

        short_replies = 0
        long_replies = 0
        total = 0
        for entry in recent:
            if not isinstance(entry, dict):
                continue
            resp_len = entry.get("response_length", 0)
            if resp_len > 0:
                total += 1
                if resp_len < 50:
                    short_replies += 1
                elif resp_len > 300:
                    long_replies += 1

        if total >= 3:
            if short_replies / total > 0.6:
                style["verbosity"] = "terse"
                style["detail_level"] = "summary"
            elif long_replies / total > 0.6:
                style["verbosity"] = "verbose"
                style["detail_level"] = "detailed"

        formal_count = 0
        casual_count = 0
        for entry in recent:
            if not isinstance(entry, dict):
                continue
            tone = entry.get("detected_tone", "")
            if tone == "formal":
                formal_count += 1
            elif tone == "casual":
                casual_count += 1

        if formal_count > casual_count and formal_count >= 2:
            style["tone"] = "formal"
        elif casual_count > formal_count and casual_count >= 2:
            style["tone"] = "casual"

        return style

    # ------------------------------------------------------------------
    # Confidence & reasoning
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_confidence(
        prefs: list[PreferenceEntry],
        workflows: list[WorkflowPattern],
        history: list[dict],
    ) -> float:
        """Estimate output confidence from data availability and consistency."""
        pref_score = min(1.0, len(prefs) / 10.0) if prefs else 0.0
        workflow_score = min(1.0, len(workflows) / 5.0) if workflows else 0.0
        history_score = min(1.0, len(history) / 20.0) if history else 0.0

        weights = [0.35, 0.30, 0.35]
        values = [pref_score, workflow_score, history_score]
        return round(sum(w * v for w, v in zip(weights, values)), 3)

    @staticmethod
    def _build_reasoning(
        ranked: list[dict],
        workflow: Optional[dict],
        style: dict,
        confidence: float,
    ) -> str:
        parts: list[str] = []

        if ranked:
            top = ranked[0]
            parts.append(
                f"Top preference: '{top.get('key', '?')}' "
                f"(score={top.get('score', 0):.3f})"
            )
        else:
            parts.append("No preference data available.")

        if workflow:
            parts.append(
                f"Recommended workflow: '{workflow.get('name', '?')}' "
                f"(score={workflow.get('score', 0):.3f})"
            )
        else:
            parts.append("No workflow pattern available.")

        tone = style.get("tone", "neutral")
        verbosity = style.get("verbosity", "normal")
        parts.append(f"Response style: {verbosity}/{tone}")

        parts.append(f"Confidence: {confidence:.3f}")
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # Health tracking
    # ------------------------------------------------------------------

    def _update_health(self, success: bool) -> None:
        with self._lock:
            self._health_score = max(
                0.0, 1.0 - (self._failures / max(1, self._total_calls))
            )
            if self._health_score < 0.3:
                self._status = ModelStatus.DEGRADED
