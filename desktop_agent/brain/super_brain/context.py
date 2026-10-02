"""
MYRAA Super-Brain — Context Fusion (B4) and Multimodal State (B17).

ContextFusion unifies: current request, AI Manager route, conversation
context, memory, project state, screen state, browser state, world model,
task state, recent tool results, previous verification results.

Priority (never inject the entire history):
  1. current request
  2. active goal
  3. current world state
  4. active task state
  5. relevant memory
  6. recent tool results
  7. older context only when needed

MultimodalObservation (B17) accepts real TEXT / VOICE / IMAGE / SCREEN /
DOCUMENT / VIDEO state where available (reusing the Modality enum from AI
Manager 4.1) and merges observations into a single bounded context.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from desktop_agent.brain.ai.ai_manager import Modality


# ==========================================================
# B17: Multimodal observation
# ==========================================================

@dataclass
class ModalityObservation:
    """One multimodal input observation merged into the world model (B17)."""

    modality: Modality = Modality.TEXT
    text: str = ""
    voice_transcript: str = ""
    image_ref: str = ""
    screen_summary: str = ""
    document_ref: str = ""
    video_ref: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def combined(self) -> str:
        """Best single textual representation for prompt-building."""
        parts = []
        if self.voice_transcript:
            parts.append(self.voice_transcript)
        if self.screen_summary:
            parts.append(f"[screen] {self.screen_summary}")
        if self.document_ref:
            parts.append(f"[document] {self.document_ref}")
        if self.text:
            parts.append(self.text)
        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modality": self.modality.name if hasattr(self.modality, "name") else str(self.modality),
            "text": self.text,
            "voice_transcript": self.voice_transcript,
            "image_ref": self.image_ref,
            "screen_summary": self.screen_summary,
            "document_ref": self.document_ref,
            "video_ref": self.video_ref,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ==========================================================
# B4: Fused context
# ==========================================================

@dataclass
class FusedContext:
    """The unified, bounded context handed to the Super-Brain (B4)."""

    request: str = ""
    goal: Optional[Any] = None
    route: Optional[Any] = None
    world: Optional[Any] = None
    world_summary: Dict[str, Any] = field(default_factory=dict)
    task: Optional[Any] = None
    memory: Dict[str, Any] = field(default_factory=dict)
    recent_tool_results: List[Dict[str, Any]] = field(default_factory=list)
    previous_verification: Dict[str, Any] = field(default_factory=dict)
    modality: ModalityObservation = field(default_factory=ModalityObservation)
    references: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request,
            "goal": self.goal.to_dict() if hasattr(self.goal, "to_dict") else self.goal,
            "world": self.world_summary,
            "memory": {k: v for k, v in self.memory.items() if not str(k).startswith("_")},
            "recent_tool_results": self.recent_tool_results[-3:],
            "previous_verification": self.previous_verification,
            "modality": self.modality.to_dict(),
            "references": self.references,
            "timestamp": self.timestamp,
        }


class ContextFusionEngine:
    """
    Unifies request + route + world + memory + task into one bounded context.

    REUSES the existing WorldModel, MemoryManager/RetrievalEngine, and
    ContextSnapshot from AI Manager 4.1. No new memory or world system.
    """

    def __init__(
        self,
        world_model: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
        memory_retrieval: Optional[Any] = None,
        context_budget_chars: int = 2500,
    ) -> None:
        self.world_model = world_model
        self.memory_manager = memory_manager
        self.memory_retrieval = memory_retrieval
        self.context_budget_chars = context_budget_chars

    # ------------------------------------------------------------------

    def fuse(
        self,
        request: str = "",
        goal: Optional[Any] = None,
        route: Optional[Any] = None,
        task: Optional[Any] = None,
        conversation_context: Optional[Any] = None,
        recent_tool_results: Optional[List[Dict[str, Any]]] = None,
        previous_verification: Optional[Dict[str, Any]] = None,
        modality: Optional[ModalityObservation] = None,
    ) -> FusedContext:
        fused = FusedContext(
            request=request,
            goal=goal,
            route=route,
            task=task,
            recent_tool_results=list(recent_tool_results or [])[-5:],
            previous_verification=dict(previous_verification or {}),
            modality=modality or ModalityObservation(),
        )

        # 3. current world state (bounded summary, never the full screen).
        if self.world_model is not None:
            try:
                fused.world = self.world_model
                fused.world_summary = self.world_model.summary()
            except Exception:
                fused.world_summary = {}

        # 5. relevant memory (bounded).
        fused.memory = self._gather_memory(request, goal)

        # 1/2/6. route + goal already captured; enrich references from the
        # AI Manager ContextSnapshot when provided (reference disambiguation).
        if conversation_context is not None:
            refs = getattr(conversation_context, "to_dict", None)
            if callable(refs):
                refs = refs()
            fused.references = dict(refs or {})

        return fused

    # ------------------------------------------------------------------

    def _gather_memory(self, request: str, goal: Optional[Any]) -> Dict[str, Any]:
        """Bounded memory pull (working snapshot + retrieval when available)."""
        out: Dict[str, Any] = {}

        if self.memory_retrieval is not None and request:
            try:
                result = self.memory_retrieval.resolve(
                    request,
                    None,
                )
                if result is not None and getattr(result, "handled", False):
                    out["retrieval_handled"] = True
                    out["retrieval_response"] = getattr(result, "response", "")
            except Exception:
                pass

        if self.memory_manager is not None:
            try:
                ctx = self.memory_manager.context()
                if isinstance(ctx, dict):
                    working = ctx.get("working", [])
                    episodic = ctx.get("episodic", [])
                    semantic = ctx.get("semantic", {})
                    out["working_recent"] = list(working)[-5:]
                    out["episodic_recent"] = list(episodic)[-3:]
                    if isinstance(semantic, dict):
                        out["semantic_keys"] = list(semantic)[:10]
            except Exception:
                pass

        return out

    def prompt_context(self, fused: FusedContext) -> str:
        """Build a bounded text block for LLM/reasoning prompts (B4)."""
        lines: List[str] = []
        budget = self.context_budget_chars
        if fused.request:
            lines.append(f"REQUEST: {fused.request[:500]}")
        if fused.goal is not None and getattr(fused.goal, "text", ""):
            lines.append(f"GOAL: {fused.goal.text[:300]}")
            if getattr(fused.goal, "constraints", None):
                lines.append(f"CONSTRAINTS: {fused.goal.constraints}")
            if getattr(fused.goal, "success_criteria", None):
                lines.append(f"SUCCESS: {fused.goal.success_criteria[:3]}")
        if fused.world_summary:
            lines.append(f"WORLD: {fused.world_summary}")
        if fused.task is not None:
            try:
                lines.append(f"TASK: {fused.task.to_dict()}")
            except Exception:
                pass
        if fused.memory.get("retrieval_response"):
            lines.append(f"MEMORY: {fused.memory['retrieval_response'][:400]}")
        if fused.recent_tool_results:
            lines.append(
                f"RECENT RESULTS: {str(fused.recent_tool_results)[:600]}"
            )
        if fused.previous_verification:
            lines.append(f"VERIFICATION: {fused.previous_verification}")

        text = "\n".join(lines)
        if len(text) > budget:
            text = text[:budget] + "\n[context truncated]"
        return text