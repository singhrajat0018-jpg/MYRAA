"""
MYRAA Trading Intelligence — Super-Brain Capability Integration (Part 25)

Registers the Trading Intelligence Engine as a capability under Super-Brain.
"""

from __future__ import annotations

from typing import Any, Dict

from desktop_agent.brain.super_brain.capability_orchestrator import CapabilityEngine


class TradingCapabilityEngine(CapabilityEngine):
    """Super-Brain capability for trading intelligence."""

    capability_id = "TRADING_ENGINE"

    def __init__(self, trading_engine=None):
        self._trading_engine = trading_engine

    def execute(self, goal: Any, context: Any) -> Dict[str, Any]:
        goal_text = getattr(goal, "text", str(goal))
        if self._trading_engine is None:
            return {"success": False, "message": "Trading engine not initialized"}
        try:
            result = self._trading_engine.status()
            return {
                "success": True,
                "capability": "TRADING_ENGINE",
                "message": f"Trading intelligence active: {result.get('engine', 'unknown')}",
                "data": result,
            }
        except Exception as exc:
            return {"success": False, "message": f"Trading engine error: {exc}"}
