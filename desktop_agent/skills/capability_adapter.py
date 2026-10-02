"""MYRAA Skills → Super-Brain capability adapter (Phase U).

Wires the Phase I multi-agent framework (SkillOrchestrator + Workers +
AgentPlanner + Supervisor + Handoff + ConflictResolver) into the ONE
Super-Brain pipeline as a registered CapabilityEngine — the same plugin seam
used by TradingCapabilityEngine.

Specialists remain internal: externally there is only MYRAA.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from desktop_agent.brain.super_brain.capability_orchestrator import CapabilityEngine

log = logging.getLogger(__name__)

CAPABILITY_ID = "MULTI_AGENT_SKILLS"


class MultiAgentCapabilityEngine(CapabilityEngine):
    """Super-Brain capability that executes complex goals via worker teams."""

    capability_id = CAPABILITY_ID

    def __init__(self, orchestrator: Any = None) -> None:
        self._orchestrator = orchestrator

    def _ensure_orchestrator(self) -> Any:
        if self._orchestrator is None:
            from desktop_agent.skills import SkillOrchestrator

            self._orchestrator = SkillOrchestrator()
        return self._orchestrator

    def execute(self, goal: Any, context: Any) -> Dict[str, Any]:
        goal_text = getattr(goal, "text", "") or str(goal)
        ctx = dict(getattr(context, "to_dict", lambda: {})() if context is not None and hasattr(context, "to_dict") else (context if isinstance(context, dict) else {}))
        ctx.setdefault("capability", CAPABILITY_ID)
        try:
            orchestrator = self._ensure_orchestrator()
        except Exception as exc:  # noqa: BLE001
            log.warning("Multi-agent orchestrator unavailable: %s", exc)
            return {"success": False, "message": f"multi-agent unavailable: {exc}"}

        try:
            result = orchestrator.execute(goal_text, ctx)
        except Exception as exc:  # noqa: BLE001
            log.exception("Multi-agent execution failed")
            return {"success": False, "message": f"multi-agent error: {exc}"}

        status = str(result.get("status", ""))
        ok = status in ("completed", "fast")
        message = ""
        inner = result.get("result")
        if isinstance(inner, dict):
            message = str(inner.get("answer") or inner.get("summary") or "")
        elif isinstance(result.get("results"), list):
            parts = [
                str(r.get("summary") or r.get("output") or "")
                for r in result["results"]
                if isinstance(r, dict)
            ]
            message = " ".join(p for p in parts if p)[:1000]
        return {
            "success": ok,
            "capability": CAPABILITY_ID,
            "message": message or f"multi-agent plan {status}",
            "data": result,
        }
