"""
MYRAA Cognitive Engine
Response Router (EPIC-07)

ONE authoritative, deterministic decision: *which MYRAA capability should handle
a user request?*

This is a CAPABILITY router, deliberately distinct from:

- AIManager          -> "Which LLM/provider handles this reasoning request?"
- IntentRouter       -> "Which concrete tool action does this map to?"
- ResearchRouter     -> "Which web information source should be queried?" (future)
- ExecutionBrain     -> "How should an approved computer action be executed?"

The Response Router SELECTS a capability. It never executes anything.

It is deterministic and explainable. It does NOT call an LLM, a web service, or
the desktop just to decide a route: it consumes the existing ``SemanticTask``
already produced by ``SemanticParser.parse()`` (structured intent + entity
metadata) and maps it to a capability. Normal conversation stays fast.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from ..semantic.semantic_models import Intent, SemanticTask


# ==========================================================
# Route type
# ==========================================================

class ResponseRouteType(str, Enum):
    """
    The capability that should produce the user-facing response.
    """
    LOCAL_FAST = "LOCAL_FAST"       # fast conversational / local model
    BRAIN = "BRAIN"                 # deeper reasoning / interpretation
    RESEARCH = "RESEARCH"           # fresh / current web information
    EXECUTION = "EXECUTION"         # desktop / browser / system action
    MEMORY = "MEMORY"               # memory retrieval / update


# ==========================================================
# Research boundary (contract only — orchestration is a future EPIC)
# ==========================================================

@dataclass(slots=True)
class ResearchHandoff:
    """
    Smallest research boundary contract. Produced for RESEARCH routes so a future
    ResearchRouter has a stable seam to consume. No Tavily / DDG / Wikipedia
    orchestration is performed here.
    """
    query: str
    reason: str = ""
    needs_synthesis: bool = False


# ==========================================================
# Route result
# ==========================================================

@dataclass(slots=True)
class ResponseRoute:
    route: ResponseRouteType = ResponseRouteType.LOCAL_FAST
    confidence: float = 0.0
    reason: str = ""
    intent: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "intent": self.intent,
            "metadata": self.metadata,
        }


# ==========================================================
# Deterministic capability sets
# ==========================================================

# Structured intents that resolve to concrete desktop/browser/system actions.
EXECUTION_INTENTS = {
    Intent.OPEN_APPLICATION,
    Intent.CLOSE_APPLICATION,
    Intent.CREATE_FILE,
    Intent.CREATE_FOLDER,
    Intent.DELETE_FILE,
    Intent.MOVE_FILE,
    Intent.COPY_FILE,
    Intent.OPEN_WEBSITE,
    Intent.SYSTEM_CONTROL,
    Intent.PLAY_MEDIA,
    Intent.STOP_MEDIA,
    Intent.AUTOMATION,
    Intent.CODE_TASK,
    Intent.VISION,
    Intent.MULTI_STEP_TASK,
    Intent.ROUTER_ACTION,
    Intent.SEND_MESSAGE,
    Intent.SEND_EMAIL,
}

# Current-information requests (fresh web data). The semantic parser flags these
# with metadata["live_information"] = True and intent SEARCH_WEB.
RESEARCH_INTENTS = {
    Intent.SEARCH_WEB,
}

# Durable-memory / goal-management operations (long-term memory).
MEMORY_INTENTS = {
    Intent.SET_GOAL,
    Intent.GET_GOAL,
    Intent.CLEAR_GOAL,
}

# Requests that always warrant deeper reasoning.
BRAIN_INTENTS = {
    Intent.QUESTION,
}

# Lightweight deterministic signals (used only to disambiguate reasoning-heavy
# chat from plain small-talk, without any extra LLM/network call).
_REASONING_KEYWORDS = (
    "explain",
    "why",
    "how",
    "difference",
    "differs",
    "detail",
    "in detail",
    "elaborate",
    "analyze",
    "compare",
    "reason",
    "because",
    "meaning",
    "mean",
    "stand for",
    "define",
    "what is",
    "what are",
    "what does",
    "how does",
    "causes",
    "cause",
    "implication",
    "interpret",
)

_MEMORY_KEYWORDS = (
    "do you remember",
    "do you recall",
    "what did i tell",
    "what did i say",
    "remind me",
    "you told me",
    "i told you",
    "you said",
    "forget",
    "remember my",
)


class ResponseRouter:
    """
    Deterministic, explainable mapping from a parsed ``SemanticTask`` to a single
    capability route. Reuses the existing structured intent/entity classification;
    it does not add a second classifier or pay for an LLM call.
    """

    def route(self, semantic_task: SemanticTask) -> ResponseRoute:
        intent = semantic_task.intent
        meta = getattr(semantic_task, "metadata", {}) or {}
        text = (semantic_task.normalized_text or semantic_task.raw_text or "").lower().strip()

        intent_value = intent.value if hasattr(intent, "value") else str(intent)

        # ---------------------------------------------------------
        # 1. EXPLICIT EXECUTION
        #    A structured action was already mapped (tool/function/knowledge),
        #    or the intent is a concrete action.
        #
        #    EPIC-08: a request flagged live_information (news/price/market/live)
        #    must reach the RESEARCH branch below even when the parser also mapped
        #    a searchWeb/searchGoogle action. live_information is the
        #    authoritative "this needs FRESH web data" signal, so it wins over the
        #    generic desktop browser-search mapping.
        # ---------------------------------------------------------
        action = meta.get("action")
        if action and not meta.get("live_information"):
            return ResponseRoute(
                route=ResponseRouteType.EXECUTION,
                confidence=1.0,
                reason=f"structured action mapped: {action}",
                intent=intent_value,
                metadata={"action": action, "parameters": meta.get("parameters", {})},
            )

        if intent in EXECUTION_INTENTS:
            return ResponseRoute(
                route=ResponseRouteType.EXECUTION,
                confidence=0.95,
                reason=f"intent={intent_value}",
                intent=intent_value,
            )

        # ---------------------------------------------------------
        # 2. EXPLICIT RESEARCH / CURRENT INFORMATION
        #    The semantic parser already flagged live-information keywords
        #    (price/stock/news/nifty/weather/...).
        # ---------------------------------------------------------
        if intent in RESEARCH_INTENTS or meta.get("live_information"):
            # A mixed research+reasoning request is represented explicitly rather
            # than pretending it is a single simple route. Orchestration (research
            # then synthesis) is a future EPIC; here we only flag it.
            needs_synthesis = _looks_reasoning(text)
            return ResponseRoute(
                route=ResponseRouteType.RESEARCH,
                confidence=0.9,
                reason=(
                    "request requires current information"
                    + (" + synthesis" if needs_synthesis else "")
                ),
                intent=intent_value,
                metadata={
                    "live_information": meta.get("live_information", False),
                    "research_handoff": ResearchHandoff(
                        query=meta.get("query") or text,
                        reason="current-information request",
                        needs_synthesis=needs_synthesis,
                    ),
                },
            )

        # ---------------------------------------------------------
        # 3. EXPLICIT MEMORY OPERATION
        # ---------------------------------------------------------
        if intent in MEMORY_INTENTS:
            return ResponseRoute(
                route=ResponseRouteType.MEMORY,
                confidence=0.85,
                reason=f"explicit memory operation (intent={intent_value})",
                intent=intent_value,
            )

        if _has_keyword(text, _MEMORY_KEYWORDS):
            return ResponseRoute(
                route=ResponseRouteType.MEMORY,
                confidence=0.8,
                reason="explicit memory-query phrasing",
                intent=intent_value,
            )

        # ---------------------------------------------------------
        # 4. COMPLEX / AMBIGUOUS REASONING
        # ---------------------------------------------------------
        if intent in BRAIN_INTENTS:
            return ResponseRoute(
                route=ResponseRouteType.BRAIN,
                confidence=0.8,
                reason="question / reasoning-heavy intent",
                intent=intent_value,
            )

        if _looks_reasoning(text):
            return ResponseRoute(
                route=ResponseRouteType.BRAIN,
                confidence=0.7,
                reason="reasoning-heavy phrasing",
                intent=intent_value,
            )

        # ---------------------------------------------------------
        # 5. NORMAL CONVERSATION (safe fallback)
        #    Greetings, small talk, plain statements -> the fast conversation
        #    transport answers; the Brain should not re-answer.
        # ---------------------------------------------------------
        return ResponseRoute(
            route=ResponseRouteType.LOCAL_FAST,
            confidence=0.6,
            reason="normal conversation / no structured or reasoning signal",
            intent=intent_value,
        )


# ==========================================================
# Helpers
# ==========================================================

def _looks_reasoning(text: str) -> bool:
    if not text:
        return False
    return _has_keyword(text, _REASONING_KEYWORDS)


def _has_keyword(text: str, keywords: List[str]) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(k in low for k in keywords)
