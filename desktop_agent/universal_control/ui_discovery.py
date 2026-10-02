"""UI discovery — consumes existing ContinuousVisionController output.

NO screenshot capture. NO independent vision pipeline.
Reads VisualState.ui_targets and ScreenState.elements from the
authoritative vision pipeline. Falls back to OCR only when live
vision state is unavailable.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from .ui_element import UniversalElement, ElementType, InteractiveRole


@dataclass
class DiscoveryResult:
    elements: list[UniversalElement]
    discovery_time_ms: float
    source: str
    application: str = ""
    window_title: str = ""
    page_type: str = ""
    confidence: float = 0.0
    total_elements: int = 0
    interactive_count: int = 0

    def __post_init__(self):
        self.total_elements = len(self.elements)
        self.interactive_count = sum(
            1 for e in self.elements if e.role != InteractiveRole.NONE
        )


class UIDiscovery:
    """Discover UI elements by consuming existing vision pipeline output.

    Primary: reads VisualState from ContinuousVisionController
    Fallback: accepts raw OCR results when vision is unavailable
    """

    def __init__(self):
        self._lock = threading.Lock()

    def from_visual_state(self, visual_state: Any) -> DiscoveryResult:
        """Convert VisualState from ContinuousVisionController to DiscoveryResult.

        This is the PRIMARY path. VisualState is produced by the existing
        ContinuousVisionController and contains ui_targets (list of dicts
        with type, text, bounds) extracted from VisionContext's SemanticNodes.
        """
        start = time.perf_counter()
        elements = []
        ui_targets = getattr(visual_state, "ui_targets", [])
        for i, target in enumerate(ui_targets):
            if isinstance(target, dict):
                elem = UniversalElement.from_visual_state_target(target, i)
                if elem.text.strip():
                    elements.append(elem)
        elapsed = (time.perf_counter() - start) * 1000
        return DiscoveryResult(
            elements=elements,
            discovery_time_ms=elapsed,
            source="visual_state",
            application=getattr(visual_state, "application", ""),
            window_title=getattr(visual_state, "window_title", ""),
            page_type=getattr(visual_state, "page_type", ""),
            confidence=getattr(visual_state, "confidence", 0.0),
        )

    def from_screen_state(self, screen_state: Any) -> DiscoveryResult:
        """Convert ScreenState (from vision pipeline) to DiscoveryResult.

        Alternative path when ScreenState is available directly.
        """
        start = time.perf_counter()
        elements = []
        raw_elements = getattr(screen_state, "elements", [])
        for i, elem in enumerate(raw_elements):
            ue = UniversalElement.from_vision_ui_element(elem, i)
            if ue.text.strip():
                elements.append(ue)
        elapsed = (time.perf_counter() - start) * 1000
        active_win = getattr(screen_state, "active_window", None)
        return DiscoveryResult(
            elements=elements,
            discovery_time_ms=elapsed,
            source="screen_state",
            application=getattr(active_win, "application", "") if active_win else "",
            window_title=getattr(active_win, "title", "") if active_win else "",
        )

    def from_ocr_fallback(self, ocr_elements: list[dict]) -> DiscoveryResult:
        """Fallback: convert raw OCR results when live vision is unavailable.

        Only used when ContinuousVisionController state is stale/unavailable
        and explicit high-resolution inspection is required.
        """
        start = time.perf_counter()
        elements = []
        for i, raw in enumerate(ocr_elements):
            text = raw.get("text", "").strip()
            if not text or len(text) < 2:
                continue
            etype = ElementType.TEXT_LABEL
            role = InteractiveRole.NONE
            lower = text.lower()
            if lower in ("ok", "cancel", "save", "apply", "submit", "close"):
                etype = ElementType.BUTTON
                role = InteractiveRole.PRIMARY_ACTION
            elif any(kw in lower for kw in ("button", "btn")):
                etype = ElementType.BUTTON
                role = InteractiveRole.PRIMARY_ACTION
            elif any(kw in lower for kw in ("text", "input", "field")):
                etype = ElementType.TEXT_FIELD
                role = InteractiveRole.INPUT
            elements.append(UniversalElement(
                element_id=f"ocr_{i}",
                element_type=etype,
                label=text,
                confidence=raw.get("confidence", 0.7),
                x=raw.get("x", 0), y=raw.get("y", 0),
                width=raw.get("width", 100), height=raw.get("height", 30),
                text=text, role=role,
                source="ocr_fallback",
            ))
        elapsed = (time.perf_counter() - start) * 1000
        return DiscoveryResult(
            elements=elements,
            discovery_time_ms=elapsed,
            source="ocr_fallback",
        )

    def find_element(self, elements: list[UniversalElement],
                     hint: str) -> Optional[UniversalElement]:
        """Find best matching element by text/type hint."""
        hint_lower = hint.lower()
        best = None
        best_score = 0.0
        for elem in elements:
            score = 0.0
            if hint_lower in elem.text.lower():
                score += 3.0
            if hint_lower in elem.label.lower():
                score += 2.0
            if hint_lower == elem.element_type.value:
                score += 1.0
            if elem.role != InteractiveRole.NONE:
                score += 0.5
            score *= elem.confidence
            if score > best_score:
                best_score = score
                best = elem
        return best

    def find_interactive(self, elements: list[UniversalElement]) -> list[UniversalElement]:
        """Filter to only interactive elements."""
        return [e for e in elements if e.role != InteractiveRole.NONE]

    def find_by_type(self, elements: list[UniversalElement],
                     etype: ElementType) -> list[UniversalElement]:
        """Filter by element type."""
        return [e for e in elements if e.element_type == etype]
