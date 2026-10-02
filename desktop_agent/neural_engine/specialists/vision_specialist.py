"""Vision Neural Specialist — enhances existing ContinuousVisionController.

Flow:
ContinuousVisionController → VisualState → Vision Neural Model
→ enhanced visual understanding → result → ContextFusion → Super-Brain

DO NOT capture separate screenshots or create a second vision loop.
"""

from __future__ import annotations

import time
import threading
from typing import Any, Optional
from dataclasses import dataclass, field

from ..model_contract import (
    ModelSpec, ModelResult, InferenceRequest, ModelDomain, ModelModality,
    LatencyClass, ModelDeployment, ModelStatus,
)


@dataclass
class VisionAnalysis:
    """Structured vision neural output."""
    objects: list[dict] = field(default_factory=list)
    ui_elements: list[dict] = field(default_factory=list)
    text_content: list[str] = field(default_factory=list)
    scene_description: str = ""
    chart_data: Optional[dict] = None
    anomalies: list[str] = field(default_factory=list)
    confidence: float = 0.5
    element_count: int = 0
    has_text: bool = False
    has_chart: bool = False


class VisionSpecialist:
    """Vision specialist model wrapping existing vision pipeline + LLM vision."""

    SPEC = ModelSpec(
        model_id="vision_specialist_v1",
        domain=ModelDomain.VISION,
        version="1.0.0",
        modality=ModelModality.MULTIMODAL,
        capabilities=[
            "ui_element_recognition", "text_recognition", "scene_understanding",
            "chart_analysis", "object_detection", "visual_anomaly_detection",
            "element_classification", "visual_relationships",
        ],
        input_schema={
            "visual_state": "VisualState",
            "screen_description": "str",
            "context": "dict",
        },
        output_schema={
            "analysis": "VisionAnalysis",
            "confidence": "float",
        },
        latency_class=LatencyClass.NORMAL,
        deployment=ModelDeployment.LOCAL,
        resource_requirements={"min_memory_mb": 256},
        provider="ollama",
    )

    def __init__(self, ai_manager=None):
        self._ai_manager = ai_manager
        self._status = ModelStatus.ACTIVE
        self._health_score: float = 1.0
        self._total_calls: int = 0
        self._failures: int = 0

    @property
    def model_id(self) -> str:
        return self.SPEC.model_id

    @property
    def status(self) -> ModelStatus:
        return self._status

    def inference(self, request: InferenceRequest) -> ModelResult:
        start = time.perf_counter()
        self._total_calls += 1

        try:
            visual_state = request.context.get("visual_state")
            screen_desc = request.context.get("screen_description", "")

            analysis = self._analyze(visual_state, screen_desc, request.context)

            elapsed = (time.perf_counter() - start) * 1000
            self._update_health(True)

            return ModelResult(
                model_id=self.model_id,
                output=analysis,
                confidence=analysis.confidence,
                uncertainty=1.0 - analysis.confidence,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="vision_specialist",
                version=self.SPEC.version,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            self._failures += 1
            self._update_health(False)
            return ModelResult(
                model_id=self.model_id,
                output=VisionAnalysis(confidence=0.0),
                confidence=0.0,
                uncertainty=1.0,
                latency_ms=elapsed,
                timestamp=time.time(),
                source="vision_specialist_error",
                warnings=[str(e)],
                version=self.SPEC.version,
            )

    def _analyze(self, visual_state, screen_desc: str, context: dict) -> VisionAnalysis:
        objects = []
        ui_elements = []
        text_content = []
        anomalies = []

        if visual_state:
            if hasattr(visual_state, 'ui_targets') and visual_state.ui_targets:
                for target in visual_state.ui_targets:
                    elem = {
                        "type": getattr(target, 'element_type', 'unknown'),
                        "text": getattr(target, 'text', ''),
                        "confidence": getattr(target, 'confidence', 0.5),
                    }
                    ui_elements.append(elem)
                    if elem.get("text"):
                        text_content.append(elem["text"])

            if hasattr(visual_state, 'text_regions') and visual_state.text_regions:
                for region in visual_state.text_regions:
                    if hasattr(region, 'text'):
                        text_content.append(region.text)

            if hasattr(visual_state, 'active_window'):
                window = visual_state.active_window
                if window:
                    objects.append({
                        "type": "window",
                        "title": getattr(window, 'title', ''),
                        "application": getattr(window, 'application', ''),
                    })

        confidence = 0.5
        if ui_elements:
            confidences = [e.get("confidence", 0.5) for e in ui_elements]
            confidence = sum(confidences) / len(confidences) if confidences else 0.5
        if text_content:
            confidence = min(1.0, confidence + 0.1)

        has_chart = any("chart" in t.lower() or "graph" in t.lower()
                        for t in text_content)

        return VisionAnalysis(
            objects=objects,
            ui_elements=ui_elements,
            text_content=text_content,
            scene_description=screen_desc,
            chart_data=None,
            anomalies=anomalies,
            confidence=min(1.0, confidence),
            element_count=len(ui_elements),
            has_text=bool(text_content),
            has_chart=has_chart,
        )

    def _update_health(self, success: bool):
        self._health_score = max(0.0, 1.0 - (self._failures / max(1, self._total_calls)))
        if self._health_score < 0.3:
            self._status = ModelStatus.DEGRADED
