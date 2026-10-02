"""AI Manager 4.1 — bounded context fusion.

ContextSnapshot is a small, bounded, relevance-based view of the world the AI
Manager may consume when routing. It is deliberately NOT the whole conversation
or whole memory: only fields that are actually available are filled, and the
AI Manager only uses them to resolve deictic references ("open that",
"same as before", "continue the previous task") or to tighten domain confidence.

This module owns no routing logic — it is a pure data container plus the
reference-detection helpers consumed by :class:`AIManager`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContextSnapshot:
    """Bounded relevance-based context available at routing time.

    Only information that is actually available should be populated. The AI
    Manager must never receive entire memory or entire conversation history.
    """

    conversation_relevance: str = ""
    active_task: Optional[str] = None
    project: Optional[str] = None
    active_app: Optional[str] = None
    screen_summary: Optional[str] = None
    browser_summary: Optional[str] = None
    memory_hits: List[str] = field(default_factory=list)
    world_state: Optional[str] = None
    portfolio: Optional[str] = None
    previous_request: Optional[str] = None
    previous_route: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_relevance": self.conversation_relevance,
            "active_task": self.active_task,
            "project": self.project,
            "active_app": self.active_app,
            "screen_summary": self.screen_summary,
            "browser_summary": self.browser_summary,
            "memory_hits": list(self.memory_hits),
            "world_state": self.world_state,
            "portfolio": self.portfolio,
            "previous_request": self.previous_request,
            "previous_route": self.previous_route,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Reference mention classification (bounded; no giant dictionary)
# ---------------------------------------------------------------------------


class ReferenceKind:
    OPEN = "open_reference"          # "open that", "show it", "close the window"
    SAME_AS_BEFORE = "same_as_before"  # "same as before", "like last time"
    CONTINUE_PREVIOUS = "continue_previous"  # "continue", "resume the task"
    IMPROVE_PREVIOUS = "improve_previous"    # "make the previous one better"
    REPEAT = "repeat"                # "do it again", "repeat that"
    WORST_PERFORMER = "worst_performer"  # "analyze the worst performer"
    NONE = "none"


def detect_reference_mention(text_lower: str) -> str:
    """Return the ReferenceKind of a deictic/elliptical request (or NONE)."""
    t = text_lower.strip()
    if any(w in t for w in ("worst performer", "worst performer in", "worst stock", "worst holding")):
        return ReferenceKind.WORST_PERFORMER
    if any(p in t for p in ("same as before", "same as previous", "same as last",
                            "like before", "like last", "same as earlier",
                            "jaise pehle", "same same", "pehle jaisa")):
        return ReferenceKind.SAME_AS_BEFORE
    if any(p in t for p in ("continue the previous task", "continue previous task",
                            "resume the task", "resume previous", "continue the task",
                            "continue", "resume", "aage badhao", "jari rakho")):
        return ReferenceKind.CONTINUE_PREVIOUS
    if any(p in t for p in ("make the previous one better", "make previous better",
                            "improve the previous", "make it better", "improve it",
                            "better than before", "make the previous one", "the previous one better")):
        return ReferenceKind.IMPROVE_PREVIOUS
    if any(p in t for p in ("do it again", "repeat that", "repeat it", "again do it",
                            "same again", "ek baar phir")):
        return ReferenceKind.REPEAT
    # Open references: a tool verb + a deictic target with no concrete entity.
    verbs = ("open", "close", "show", "display", "read", "minimize", "maximize",
             "switch", "activate", "focus", "launch", "kholo", "khol", "dikhao", "dikha",
             "chalao", "band karo", "band kar", "delete", "remove", "move", "copy", "rename")
    if any(t.startswith(v) or (" " + v + " ") in (" " + t + " ") for v in verbs):
        words = set(t.split())
        # True deictic pronouns ("open that", "show it") are always references.
        deictic_pronouns = words & {"that", "it", "this", "these", "those",
                                    "them", "one", "same"}
        if deictic_pronouns:
            return ReferenceKind.OPEN
        # Window/tab management acts on the ACTIVE window/tab — always
        # actionable, never a reference ("maximize the window", "close the tab").
        active_window_verbs = ("close", "maximize", "minimize", "restore",
                               "switch", "focus", "activate")
        if any(f"the {n}" in t for n in ("window", "tab")) and any(
                v in t for v in active_window_verbs):
            return ReferenceKind.NONE
        # Bare nouns like "file" in "read my file" are concrete requests, NOT
        # references. Only a *definite* noun phrase ("the file", "that tab")
        # signals a reference to previously-mentioned context.
        definite_phrase = any(
            phrase in t for phrase in (
                "the file", "the document", "the window", "the tab", "the app",
                "the application", "the folder", "the website", "the page",
                "the site", "the previous", "the last", "the report",
                "that file", "this file", "that document", "this document",
                "that window", "this window", "that tab", "that app",
                "that folder", "that page", "that website", "that report",
            )
        )
        if definite_phrase:
            return ReferenceKind.OPEN
    return ReferenceKind.NONE


def resolve_open_target(snapshot: "ContextSnapshot") -> Optional[str]:
    """Pick a bounded target for an open reference from available context."""
    if snapshot.active_app:
        return snapshot.active_app
    if snapshot.browser_summary:
        return snapshot.browser_summary
    if snapshot.screen_summary:
        return snapshot.screen_summary
    if snapshot.active_task:
        return snapshot.active_task
    if snapshot.previous_request:
        return snapshot.previous_request
    return None


def resolve_previous(snapshot: "ContextSnapshot") -> Optional[Dict[str, Any]]:
    """Return the previous route summary (if any) for continuation references."""
    if snapshot.previous_route:
        return snapshot.previous_route
    if snapshot.active_task:
        return {"task": snapshot.active_task}
    return None