"""
MYRAA Super-Brain — Goal Understanding (B2).

Convert natural language into a structured GOAL with CONSTRAINTS,
EXPECTED_OUTPUT, SUCCESS_CRITERIA, DEADLINE, RISK and CONTEXT requirements.

This does NOT execute anything. It consumes the routing metadata already
produced by AI Manager 4.1 (TaskRoute: intent/domain/capability/output_type/
entities/topic/risk/sub_tasks/dependencies) plus the SemanticTask when present,
and packs it into a single, structured Goal model.

Example:
    "Rahul ko message karde, main 10 min late aaunga."
    -> Goal(text="Rahul ko message karde, main 10 min late aaunga.",
             action="send_message", recipient="Rahul",
             message="Main 10 min late aaunga",
             success_criteria=["message appears in target conversation as sent"])
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# SAFETY: the Super-Brain must never fabricate. These keywords only help
# classify SUCCESS CRITERIA phrasing; they never grant permissions.


@dataclass
class Goal:
    """Structured understanding of one user goal (B2)."""

    text: str
    task_id: str = ""
    action: str = ""
    domain: str = ""
    capability: str = ""
    intent: str = ""
    output_type: str = ""
    recipient: str = ""
    message: str = ""
    topic: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    success_criteria: List[str] = field(default_factory=list)
    deadline: Optional[float] = None
    risk: str = "none"
    context_requirements: List[str] = field(default_factory=list)
    confidence: float = 0.0
    is_multi: bool = False
    capability_chain: List[str] = field(default_factory=list)
    sub_goals: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[List[int]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "task_id": self.task_id,
            "action": self.action,
            "domain": self.domain,
            "capability": self.capability,
            "intent": self.intent,
            "output_type": self.output_type,
            "recipient": self.recipient,
            "message": self.message,
            "topic": list(self.topic),
            "entities": list(self.entities),
            "constraints": self.constraints,
            "expected_output": self.expected_output,
            "success_criteria": list(self.success_criteria),
            "deadline": self.deadline,
            "risk": self.risk,
            "context_requirements": list(self.context_requirements),
            "confidence": self.confidence,
            "is_multi": self.is_multi,
            "capability_chain": list(self.capability_chain),
            "sub_goals": list(self.sub_goals),
            "dependencies": self.dependencies,
        }


def _extract_entity(route, signals_entities: List[str], kinds: List[str]) -> str:
    """Best-effort entity extraction from TaskRoute metadata + entities."""
    if not route:
        return ""
    route_entities = getattr(route, "entities", []) or []
    topic = getattr(route, "topic", []) or []
    for value in route_entities + signals_entities:
        low = str(value).lower()
        if any(k in low for k in kinds):
            return str(value)
    for value in topic:
        low = str(value).lower()
        if any(k in low for k in kinds):
            return str(value)
    return ""


# Message-verb detection for the "send X" family of goals.
_SEND_VERBS = ("message", "whatsapp", "send", "bhej", "karde", "karna")
_APPS = (
    "whatsapp", "telegram", "gmail", "email", "outlook", "slack",
    "discord", "sms", "instagram",
)


def _looks_like_send(text: str) -> bool:
    low = text.lower()
    return any(v in low for v in _SEND_VERBS)


def build_goal(
    text: str,
    route: Optional[Any] = None,
    semantic_task: Optional[Any] = None,
    request_id: str = "",
) -> Goal:
    """Build a structured Goal from a request (B2).

    Reuses the existing AI Manager 4.1 route (authoritative routing) and
    SemanticTask entities. Pure extraction — never executes anything.
    """
    goal = Goal(text=text or "")
    goal.text = text or ""

    # Reuse existing task id when present (never duplicate).
    if semantic_task is not None:
        goal.task_id = str(
            getattr(semantic_task, "task_id", "") or ""
        )

    route_entities: List[str] = list(
        getattr(route, "entities", []) or []
    ) if route else []
    route_topic: List[str] = list(
        getattr(route, "topic", []) or []
    ) if route else []

    if route is not None:
        goal.intent = getattr(route, "intent", None)
        if hasattr(goal.intent, "value"):
            goal.intent = goal.intent.value
        goal.domain = getattr(route, "domain", None)
        if hasattr(goal.domain, "value"):
            goal.domain = goal.domain.value
        goal.capability = getattr(route, "capability", "") or ""
        goal.output_type = getattr(route, "output_type", None)
        if hasattr(goal.output_type, "value"):
            goal.output_type = goal.output_type.value
        goal.confidence = float(
            getattr(route, "calibrated_confidence", 0.0)
            or getattr(route, "confidence", 0.0)
        )
        risk = getattr(route, "risk_level", None)
        goal.risk = risk.value if hasattr(risk, "value") else str(risk)
        goal.context_requirements = list(
            getattr(route, "context_required", []) or []
        )
        # Multi-goal decomposition already computed by AI Manager 4.1.
        goal.is_multi = bool(getattr(route, "multi_intents", None))
        goal.sub_goals = list(getattr(route, "sub_tasks", []) or [])
        goal.dependencies = list(getattr(route, "dependencies", []) or [])
        goal.capability_chain = list(getattr(route, "capability_chain", []) or [])
        goal.topic = list(route_topic)
        goal.entities = list(route_entities)

    # SemanticTask enrichments when present (no second classifier).
    if semantic_task is not None:
        task_goal = getattr(semantic_task, "goal", None)
        if task_goal:
            goal.action = str(task_goal)
        for ent in getattr(semantic_task, "entities", []) or []:
            et = getattr(ent, "entity_type", None)
            etv = getattr(et, "value", et)
            if etv == "person":
                goal.recipient = goal.recipient or str(getattr(ent, "value", ""))
            elif etv == "message":
                goal.message = goal.message or str(getattr(ent, "value", ""))

    # Hinglish / plain-language entity extraction (deterministic, no LLM).
    low = text.lower()
    if _looks_like_send(text):
        goal.action = "send_message"
        for app in _APPS:
            if app in low:
                goal.action = f"send_message_via_{app}"
                goal.entities.append(app)
                break
        recipient = _extract_entity(route, route_entities, ["rahul", "to ", "ko "])
        if not recipient:
            # "Rahul ko message karde" -> recipient is the proper noun
            # immediately before "ko".
            m = re.search(r"\b([A-Z][a-zA-Z]{2,20})\s+ko\b", text)
            if m:
                recipient = m.group(1)
            else:
                # "message to Rahul" / "send Rahul a message"
                m = re.search(r"(?:to|ko)\s+([A-Z][a-zA-Z]{2,20})", text)
                if m and m.group(1).lower() != "message":
                    recipient = m.group(1)
        goal.recipient = recipient
        # Message body = the "10 min late" style clause after the verb.
        m = re.search(
            r"(?:karde|kar de|bhej do|bhejo|bhej|send)[,.]?\s*(.*)",
            text,
        )
        if m and m.group(1).strip():
            goal.message = m.group(1).strip()
        goal.success_criteria = [
            "message appears in target conversation as sent"
        ]
        goal.expected_output = "message sent to target conversation"

    # Generic success-criteria phrasing (deterministic).
    if not goal.success_criteria:
        if "create" in low or "bana" in low:
            goal.success_criteria = ["artifact exists with expected contents"]
            goal.expected_output = goal.expected_output or "created artifact"
        elif "open" in low or "khol" in low:
            goal.success_criteria = ["target application/window is open and visible"]
            goal.expected_output = goal.expected_output or "application opened"
        elif goal.action == "send_message":
            goal.success_criteria = [
                "message appears in target conversation as sent"
            ]

    # Deadline extraction (deterministic).
    deadline_hint = _extract_deadline(text)
    if deadline_hint is not None:
        goal.deadline = deadline_hint
        goal.constraints["deadline_source"] = "parsed_from_request"

    goal.constraints.setdefault("request_id", request_id)

    if not goal.success_criteria:
        goal.success_criteria = ["request completed and outcome verified where possible"]

    return goal


def _extract_deadline(text: str) -> Optional[float]:
    """Very small deterministic deadline parser.

    Handles "by <HH:MM>" and "<N> min/sec/hour" relative phrases.
    Returns absolute epoch time or None. Never executed, only understood.
    """
    import time as _time

    low = text.lower()
    m = re.search(r"(?:by|before|tak)\s+(\d{1,2})[:.](\d{2})", low)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        now = _time.time()
        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone.utc).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        target = today
        if target.timestamp() < now:
            target = today + timedelta(days=1)
        return target.timestamp()

    m = re.search(r"(\d+)\s*(min|minute|minutes|sec|second|seconds|hr|hour|hours)", low)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("min"):
            return _time.time() + n * 60
        if unit.startswith("sec"):
            return _time.time() + n
        return _time.time() + n * 3600

    return None