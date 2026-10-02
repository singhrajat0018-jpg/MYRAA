"""Multimodal Neural Specialist -- cross-modal fusion across vision + voice + trading + other domains.

Flow:
Multiple specialist outputs + raw context -> Multimodal Neural Model
-> cross-modal insights, intent disambiguation, scene comprehension -> result -> Fusion -> Super-Brain

This specialist does NOT replace individual domain specialists. It consumes
their outputs and raw context to produce higher-level cross-modal understanding.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from ..model_contract import (
    ModelSpec, ModelResult, InferenceRequest, ModelDomain, ModelModality,
    LatencyClass, ModelDeployment, ModelStatus,
)


@dataclass
class CrossModalInsight:
    """A single insight derived from correlating multiple modalities."""
    insight_type: str
    description: str
    confidence: float
    modalities_involved: list[str] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)


@dataclass
class MultimodalAnalysis:
    """Structured multimodal neural output -- all scores in [0.0, 1.0]."""
    cross_modal_insights: list[CrossModalInsight] = field(default_factory=list)
    intent_clarity_score: float = 0.0
    scene_comprehension: dict[str, Any] = field(default_factory=dict)
    context_enhancement: dict[str, Any] = field(default_factory=dict)
    primary_domain: str = "general"
    supporting_domains: list[str] = field(default_factory=list)
    confidence: float = 0.0
    uncertainty: float = 1.0
    modality_count: int = 0
    fusion_quality: float = 0.0
    warnings: list[str] = field(default_factory=list)


class MultimodalSpecialist:
    """Multimodal neural specialist combining vision + voice + trading + other domains.

    Thread-safe singleton. Produces cross-modal insights, intent disambiguation,
    and scene comprehension from multi-domain context. Does not replace individual
    specialists -- augments their outputs with correlation analysis.
    """

    _instance: Optional[MultimodalSpecialist] = None
    _lock_class = threading.Lock()

    SPEC = ModelSpec(
        model_id="multimodal_specialist_v1",
        domain=ModelDomain.MULTIMODAL,
        version="1.0.0",
        modality=ModelModality.MULTIMODAL,
        capabilities=[
            "cross_modal_fusion",
            "context_enhancement",
            "intent_disambiguation",
            "scene_comprehension",
        ],
        input_schema={
            "visual_state": "dict",
            "transcript": "str",
            "trading_data": "dict",
            "voice_analysis": "VoiceAnalysis",
            "vision_analysis": "VisionAnalysis",
            "trading_analysis": "TradingAnalysis",
            "context": "dict",
        },
        output_schema={
            "analysis": "MultimodalAnalysis",
            "confidence": "float",
            "uncertainty": "float",
        },
        latency_class=LatencyClass.NORMAL,
        deployment=ModelDeployment.LOCAL,
        resource_requirements={"min_memory_mb": 256},
        provider="local",
        description="Cross-modal fusion specialist correlating vision, voice, trading, and contextual signals.",
    )

    _DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "trading": [
            "stock", "trade", "buy", "sell", "market", "price", "chart",
            "nifty", "sensex", "portfolio", "profit", "loss", "order",
            "hold", "position", "risk", "support", "resistance",
        ],
        "voice": [
            "listen", "say", "speak", "tell", "ask", "question",
            "volume", "mute", "music", "play", "pause",
        ],
        "vision": [
            "screen", "see", "show", "display", "window", "tab",
            "button", "click", "type", "read", "ocr", "screenshot",
        ],
        "system": [
            "open", "close", "run", "shut", "restart", "sleep",
            "brightness", "folder", "file", "copy", "paste",
        ],
    }

    def __new__(cls, *args: Any, **kwargs: Any) -> MultimodalSpecialist:
        if cls._instance is None:
            with cls._lock_class:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._status = ModelStatus.ACTIVE
        self._health_score: float = 1.0
        self._total_calls: int = 0
        self._failures: int = 0
        self._lock = threading.Lock()
        self._initialized = True

    @property
    def model_id(self) -> str:
        return self.SPEC.model_id

    @property
    def status(self) -> ModelStatus:
        return self._status

    @property
    def health_score(self) -> float:
        return self._health_score

    def inference(self, request: InferenceRequest) -> ModelResult:
        """Run multimodal cross-correlation analysis on multi-domain context."""
        start = time.perf_counter()
        with self._lock:
            self._total_calls += 1

        try:
            ctx = request.context
            analysis = self._analyze(ctx)
            elapsed = (time.perf_counter() - start) * 1000
            self._update_health(True)

            return ModelResult(
                model_id=self.model_id,
                output=analysis,
                confidence=analysis.confidence,
                uncertainty=analysis.uncertainty,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="multimodal_specialist",
                warnings=analysis.warnings,
                version=self.SPEC.version,
                metadata={
                    "primary_domain": analysis.primary_domain,
                    "insight_count": len(analysis.cross_modal_insights),
                    "modality_count": analysis.modality_count,
                },
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            with self._lock:
                self._failures += 1
            self._update_health(False)
            return ModelResult(
                model_id=self.model_id,
                output=MultimodalAnalysis(
                    confidence=0.0, uncertainty=1.0, warnings=[str(e)],
                ),
                confidence=0.0,
                uncertainty=1.0,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="multimodal_specialist_error",
                warnings=[str(e)],
                version=self.SPEC.version,
            )

    def _analyze(self, ctx: dict[str, Any]) -> MultimodalAnalysis:
        warnings: list[str] = []
        modalities = self._detect_modalities(ctx)
        primary_domain = self._classify_primary_domain(ctx, modalities)
        supporting_domains = self._find_supporting_domains(ctx, primary_domain, modalities)
        insights = self._extract_cross_modal_insights(ctx, modalities)
        intent_clarity = self._compute_intent_clarity(ctx, modalities, insights)
        scene_comp = self._compute_scene_comprehension(ctx, modalities)
        context_enh = self._compute_context_enhancement(ctx, modalities, insights)
        fusion_quality = self._compute_fusion_quality(modalities, insights)
        confidence = self._compute_confidence(modalities, insights, fusion_quality)
        uncertainty = max(0.0, 1.0 - confidence)

        if len(modalities) < 2:
            warnings.append("Fewer than 2 modalities -- limited cross-modal analysis")

        return MultimodalAnalysis(
            cross_modal_insights=insights,
            intent_clarity_score=intent_clarity,
            scene_comprehension=scene_comp,
            context_enhancement=context_enh,
            primary_domain=primary_domain,
            supporting_domains=supporting_domains,
            confidence=confidence,
            uncertainty=uncertainty,
            modality_count=len(modalities),
            fusion_quality=fusion_quality,
            warnings=warnings,
        )

    def _detect_modalities(self, ctx: dict[str, Any]) -> list[str]:
        modalities: list[str] = []
        if ctx.get("visual_state") is not None or ctx.get("vision_analysis") is not None:
            modalities.append("vision")
        if ctx.get("transcript") or ctx.get("voice_analysis") is not None:
            modalities.append("voice")
        if ctx.get("trading_data") is not None or ctx.get("trading_analysis") is not None:
            modalities.append("trading")
        for key in ("system_info", "file_context", "browser_context", "notification"):
            if ctx.get(key) is not None:
                if "system" not in modalities:
                    modalities.append("system")
                break
        return modalities

    def _classify_primary_domain(self, ctx: dict[str, Any], modalities: list[str]) -> str:
        if not modalities:
            return "general"
        transcript = ctx.get("transcript", "")
        domain_scores: dict[str, float] = {d: 0.0 for d in self._DOMAIN_KEYWORDS}

        if transcript:
            text_lower = transcript.lower()
            for domain, keywords in self._DOMAIN_KEYWORDS.items():
                matches = sum(1 for kw in keywords if kw in text_lower)
                domain_scores[domain] = matches / max(len(keywords), 1)

        modality_boost = {
            "trading": 0.3 if "trading" in modalities else 0.0,
            "voice": 0.2 if "voice" in modalities else 0.0,
            "vision": 0.2 if "vision" in modalities else 0.0,
            "system": 0.15 if "system" in modalities else 0.0,
        }
        for domain in domain_scores:
            domain_scores[domain] += modality_boost.get(domain, 0.0)

        if ctx.get("trading_analysis") is not None:
            ta = ctx["trading_analysis"]
            if hasattr(ta, "confidence") and ta.confidence > 0.6:
                domain_scores["trading"] += 0.2

        if not any(domain_scores.values()):
            return modalities[0] if modalities else "general"
        return max(domain_scores, key=domain_scores.get)  # type: ignore[arg-type]

    def _find_supporting_domains(
        self, ctx: dict[str, Any], primary: str, modalities: list[str],
    ) -> list[str]:
        supporting: list[str] = [m for m in modalities if m != primary]
        transcript = ctx.get("transcript", "")
        if transcript:
            text_lower = transcript.lower()
            for domain, keywords in self._DOMAIN_KEYWORDS.items():
                if domain == primary:
                    continue
                matches = sum(1 for kw in keywords if kw in text_lower)
                if matches >= 2 and domain not in supporting:
                    supporting.append(domain)
        return supporting

    def _extract_cross_modal_insights(
        self, ctx: dict[str, Any], modalities: list[str],
    ) -> list[CrossModalInsight]:
        insights: list[CrossModalInsight] = []

        if "vision" in modalities and "voice" in modalities:
            vi = self._insight_vision_voice_correlation(ctx)
            if vi:
                insights.append(vi)

        if "trading" in modalities and "vision" in modalities:
            ti = self._insight_trading_visual_correlation(ctx)
            if ti:
                insights.append(ti)

        if "trading" in modalities and "voice" in modalities:
            tv = self._insight_trading_voice_correlation(ctx)
            if tv:
                insights.append(tv)

        if len(modalities) >= 3:
            insights.append(CrossModalInsight(
                insight_type="multi_domain_presence",
                description=f"{len(modalities)} modalities active: {', '.join(modalities)}",
                confidence=min(1.0, 0.4 + len(modalities) * 0.15),
                modalities_involved=modalities,
            ))

        transcript = ctx.get("transcript", "")
        if transcript and "vision" in modalities:
            ref = self._insight_reference_alignment(ctx, transcript)
            if ref:
                insights.append(ref)

        return insights

    def _insight_vision_voice_correlation(self, ctx: dict[str, Any]) -> Optional[CrossModalInsight]:
        transcript = ctx.get("transcript", "")
        vision = ctx.get("vision_analysis")
        if not transcript:
            return None

        evidence: list[str] = []
        confidence = 0.5

        if vision and hasattr(vision, "text_content"):
            vision_texts = [t.lower() for t in (vision.text_content or [])]
            transcript_lower = transcript.lower()
            overlaps = sum(1 for t in vision_texts if t in transcript_lower)
            if overlaps > 0:
                confidence += 0.15
                evidence.append(f"Visual text matches transcript ({overlaps} overlaps)")

        if vision and hasattr(vision, "scene_description"):
            desc = (vision.scene_description or "").lower()
            words = set(transcript.lower().split())
            desc_words = set(desc.split())
            shared = words & desc_words
            if len(shared) >= 2:
                confidence += 0.1
                evidence.append(f"Scene context aligns with speech ({len(shared)} shared terms)")

        return CrossModalInsight(
            insight_type="vision_voice_correlation",
            description="Voice and visual context show correlated signals",
            confidence=min(1.0, confidence),
            modalities_involved=["vision", "voice"],
            supporting_evidence=evidence,
        )

    def _insight_trading_visual_correlation(self, ctx: dict[str, Any]) -> Optional[CrossModalInsight]:
        trading = ctx.get("trading_analysis")
        vision = ctx.get("vision_analysis")
        if not trading or not vision:
            return None

        evidence: list[str] = []
        confidence = 0.4

        if hasattr(vision, "has_chart") and vision.has_chart:
            confidence += 0.2
            evidence.append("Chart detected on screen while trading data present")

        if hasattr(trading, "regime") and trading.regime != "unknown":
            confidence += 0.1
            evidence.append(f"Trading regime detected: {trading.regime}")

        if hasattr(vision, "ui_elements") and vision.ui_elements:
            has_trading_ui = any(
                "chart" in str(e).lower() or "trade" in str(e).lower()
                for e in vision.ui_elements
            )
            if has_trading_ui:
                confidence += 0.15
                evidence.append("Trading-related UI elements visible on screen")

        return CrossModalInsight(
            insight_type="trading_visual_correlation",
            description="Visual context supports trading analysis",
            confidence=min(1.0, confidence),
            modalities_involved=["trading", "vision"],
            supporting_evidence=evidence,
        )

    def _insight_trading_voice_correlation(self, ctx: dict[str, Any]) -> Optional[CrossModalInsight]:
        transcript = ctx.get("transcript", "")
        trading = ctx.get("trading_analysis")
        if not transcript or not trading:
            return None

        evidence: list[str] = []
        confidence = 0.4
        text_lower = transcript.lower()
        trading_kw = self._DOMAIN_KEYWORDS["trading"]
        matches = [kw for kw in trading_kw if kw in text_lower]

        if matches:
            confidence += min(0.3, len(matches) * 0.06)
            evidence.append(f"Trading keywords in speech: {matches[:5]}")

        if hasattr(trading, "confidence") and trading.confidence > 0.6:
            confidence += 0.1
            evidence.append("Trading specialist has high confidence")

        return CrossModalInsight(
            insight_type="trading_voice_correlation",
            description="Voice mentions trading concepts aligned with market analysis",
            confidence=min(1.0, confidence),
            modalities_involved=["trading", "voice"],
            supporting_evidence=evidence,
        )

    def _insight_reference_alignment(self, ctx: dict[str, Any], transcript: str) -> Optional[CrossModalInsight]:
        vision = ctx.get("vision_analysis")
        if not vision:
            return None

        evidence: list[str] = []
        confidence = 0.3

        if hasattr(vision, "text_content") and vision.text_content:
            transcript_lower = transcript.lower()
            for text in vision.text_content:
                if text.lower() in transcript_lower or text.lower().split()[0] in transcript_lower:
                    confidence += 0.15
                    evidence.append(f"User references on-screen text: '{text[:40]}'")
                    break

        if hasattr(vision, "active_window") and vision.active_window:
            app = getattr(vision.active_window, "application", "")
            if app and app.lower() in transcript.lower():
                confidence += 0.1
                evidence.append(f"User mentions active application: {app}")

        if confidence <= 0.3:
            return None

        return CrossModalInsight(
            insight_type="reference_alignment",
            description="User speech references visible screen content",
            confidence=min(1.0, confidence),
            modalities_involved=["voice", "vision"],
            supporting_evidence=evidence,
        )

    def _compute_intent_clarity(
        self, ctx: dict[str, Any], modalities: list[str],
        insights: list[CrossModalInsight],
    ) -> float:
        score = 0.3
        transcript = ctx.get("transcript", "")

        if transcript:
            if transcript.strip().endswith("?"):
                score += 0.15
            words = transcript.split()
            if len(words) >= 3:
                score += 0.1
            if len(words) >= 8:
                score += 0.05

        if "voice" in modalities:
            voice_analysis = ctx.get("voice_analysis")
            if voice_analysis and hasattr(voice_analysis, "intent_cues"):
                cues = voice_analysis.intent_cues
                if cues:
                    best = max(cues, key=lambda c: c.confidence)
                    score += best.confidence * 0.2

        correlative = [
            i for i in insights
            if i.insight_type in (
                "vision_voice_correlation", "trading_voice_correlation", "reference_alignment",
            )
        ]
        if correlative:
            best_insight = max(corulative, key=lambda i: i.confidence)
            score += best_insight.confidence * 0.15

        return min(1.0, score)

    def _compute_scene_comprehension(self, ctx: dict[str, Any], modalities: list[str]) -> dict[str, Any]:
        scene: dict[str, Any] = {"active_modalities": modalities}

        if "vision" in modalities:
            vision = ctx.get("vision_analysis")
            if vision:
                if hasattr(vision, "scene_description"):
                    scene["description"] = vision.scene_description or ""
                if hasattr(vision, "ui_elements"):
                    scene["ui_element_count"] = len(vision.ui_elements or [])
                if hasattr(vision, "has_chart"):
                    scene["has_chart"] = vision.has_chart
                if hasattr(vision, "objects"):
                    scene["object_count"] = len(vision.objects or [])

        if "voice" in modalities:
            voice = ctx.get("voice_analysis")
            if voice:
                if hasattr(voice, "emotion"):
                    scene["speaker_emotion"] = voice.emotion.primary if voice.emotion else "neutral"
                if hasattr(voice, "has_question"):
                    scene["has_question"] = voice.has_question
                if hasattr(voice, "has_command"):
                    scene["has_command"] = voice.has_command

        if "trading" in modalities:
            trading = ctx.get("trading_analysis")
            if trading:
                if hasattr(trading, "regime"):
                    scene["market_regime"] = trading.regime
                if hasattr(trading, "risk_signal"):
                    scene["risk_level"] = "high" if trading.risk_signal > 0.7 else (
                        "medium" if trading.risk_signal > 0.4 else "low"
                    )

        return scene

    def _compute_context_enhancement(
        self, ctx: dict[str, Any], modalities: list[str],
        insights: list[CrossModalInsight],
    ) -> dict[str, Any]:
        enhancement: dict[str, Any] = {}
        correlative = [i for i in insights if i.confidence > 0.5]
        if correlative:
            enhancement["high_confidence_insights"] = [
                {"type": i.insight_type, "description": i.description}
                for i in corulative
            ]

        transcript = ctx.get("transcript", "")
        if transcript and "vision" in modalities:
            vision = ctx.get("vision_analysis")
            if vision and hasattr(vision, "text_content") and vision.text_content:
                overlapping = [
                    t for t in vision.text_content
                    if t.lower() in transcript.lower()
                ]
                if overlapping:
                    enhancement["cross_referenced_texts"] = overlapping

        if "trading" in modalities and "voice" in modalities:
            trading = ctx.get("trading_analysis")
            if trading and hasattr(trading, "patterns_detected") and trading.patterns_detected:
                enhancement["trading_patterns_for_voice"] = trading.patterns_detected

        enhancement["modality_synergy"] = len(modalities) > 1
        enhancement["modality_count"] = len(modalities)
        return enhancement

    def _compute_fusion_quality(
        self, modalities: list[str], insights: list[CrossModalInsight],
    ) -> float:
        if not modalities:
            return 0.0

        modality_score = min(1.0, len(modalities) * 0.25)
        insight_score = 0.0
        if insights:
            avg_conf = sum(i.confidence for i in insights) / len(insights)
            insight_score = avg_conf * min(1.0, len(insights) * 0.3)

        return min(1.0, (modality_score + insight_score) / 2.0)

    def _compute_confidence(
        self, modalities: list[str], insights: list[CrossModalInsight],
        fusion_quality: float,
    ) -> float:
        conf = 0.3
        conf += min(0.3, len(modalities) * 0.08)
        if insights:
            high_conf = sum(1 for i in insights if i.confidence > 0.6)
            conf += min(0.2, high_conf * 0.07)
        conf += fusion_quality * 0.2
        return min(1.0, conf)

    def _update_health(self, success: bool) -> None:
        with self._lock:
            if not success:
                self._failures += 1
            total = max(self._total_calls, 1)
            self._health_score = max(0.0, 1.0 - (self._failures / total))
            if self._health_score < 0.3:
                self._status = ModelStatus.DEGRADED
            elif self._health_score < 0.6:
                self._status = ModelStatus.TESTING
            else:
                self._status = ModelStatus.ACTIVE

    def reset(self) -> None:
        """Reset health counters -- useful for tests."""
        with self._lock:
            self._total_calls = 0
            self._failures = 0
            self._health_score = 1.0
            self._status = ModelStatus.ACTIVE

    @classmethod
    def new(cls) -> MultimodalSpecialist:
        """Factory -- returns singleton instance."""
        return cls()
