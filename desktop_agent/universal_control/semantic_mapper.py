"""Semantic mapping: natural language intent -> concrete UI actions.

Consumes UniversalElements from UIDiscovery (which reads from
ContinuousVisionController). Maps intents to actions via element matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .ui_element import UniversalElement, ElementType, InteractiveRole


@dataclass
class MappingResult:
    intent: str
    target_element: Optional[UniversalElement]
    action_type: str
    confidence: float
    args: dict = field(default_factory=dict)
    fallback_elements: list[UniversalElement] = field(default_factory=list)
    reasoning: str = ""


ACTION_KEYWORDS = {
    "click": ["click", "press", "tap", "hit", "choose", "select"],
    "type": ["type", "enter", "input", "write", "fill", "put"],
    "scroll": ["scroll", "swipe", "drag"],
    "toggle": ["toggle", "switch", "enable", "disable"],
    "read": ["read", "what", "show", "display", "see"],
    "open": ["open", "launch", "start", "go to"],
    "close": ["close", "exit", "quit"],
    "minimize": ["minimize", "hide"],
    "maximize": ["maximize", "fullscreen"],
    "navigate": ["navigate", "switch", "move to", "change to"],
}


class SemanticMapper:
    """Map natural language intents to concrete UI element actions."""

    def __init__(self):
        self._action_keywords = ACTION_KEYWORDS

    def map_intent(self, intent: str, elements: list[UniversalElement]) -> MappingResult:
        """Map a natural language intent to the best matching element + action."""
        intent_lower = intent.lower()
        action = self._detect_action(intent_lower)
        target_words = self._extract_target_words(intent_lower, action)
        candidates = self._score_elements(target_words, elements)

        if not candidates:
            return MappingResult(
                intent=intent, target_element=None,
                action_type=action, confidence=0.0,
                reasoning="no_matching_elements",
            )

        best = candidates[0]
        fallbacks = candidates[1:4]

        return MappingResult(
            intent=intent,
            target_element=best,
            action_type=action,
            confidence=best.confidence,
            args=self._build_args(action, best, intent),
            fallback_elements=fallbacks,
            reasoning=f"matched '{best.label}' ({best.element_type.value})",
        )

    def _detect_action(self, intent: str) -> str:
        for action, keywords in self._action_keywords.items():
            if any(kw in intent for kw in keywords):
                return action
        return "click"

    def _extract_target_words(self, intent: str, action: str) -> list[str]:
        stop = {"the", "a", "an", "this", "that", "button", "link", "menu",
                "tab", "field", "box", "for", "to", "and", "or"}
        words = re.findall(r'[a-z]+', intent)
        return [w for w in words if w not in stop and w not in
                self._action_keywords.get(action, [])]

    def _score_elements(self, target_words: list[str],
                        elements: list[UniversalElement]) -> list[UniversalElement]:
        if not target_words:
            interactive = [e for e in elements if e.role != InteractiveRole.NONE]
            return sorted(interactive, key=lambda e: e.confidence, reverse=True)

        scored = []
        for elem in elements:
            score = 0.0
            label_lower = elem.label.lower()
            text_lower = elem.text.lower()
            for word in target_words:
                if word in label_lower:
                    score += 2.0
                if word in text_lower:
                    score += 1.0
            if elem.role != InteractiveRole.NONE:
                score += 0.5
            if score > 0:
                scored.append((score * elem.confidence, elem))

        if not scored:
            input_elems = [e for e in elements if e.role == InteractiveRole.INPUT]
            if input_elems:
                scored = [(e.confidence, e) for e in input_elems]

        scored.sort(key=lambda x: x[0], reverse=True)
        return [elem for _, elem in scored]

    def _build_args(self, action: str, element: UniversalElement, intent: str) -> dict:
        args: dict = {"element_id": element.element_id}
        if action == "click":
            args["x"] = element.center_x
            args["y"] = element.center_y
        elif action == "type":
            text = self._extract_text_to_type(intent)
            args["text"] = text
            args["x"] = element.center_x
            args["y"] = element.center_y
        elif action == "scroll":
            args["direction"] = "down" if "down" in intent else "up"
        return args

    def _extract_text_to_type(self, intent: str) -> str:
        for pat in [r'type ["\'](.+?)["\']', r'enter ["\'](.+?)["\']',
                    r'input ["\'](.+?)["\']', r'fill ["\'](.+?)["\']']:
            m = re.search(pat, intent, re.IGNORECASE)
            if m:
                return m.group(1)
        return ""
