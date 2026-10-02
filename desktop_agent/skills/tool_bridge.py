"""ToolBridge — safe tool execution bridge for Phase I.1 workers.

Workers use this bridge to invoke real tools through the EXISTING
ToolRegistry / dispatcher architecture.

DO NOT bypass: PermissionManager, SafetyManager, ToolRegistry, Verification.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ToolBridge:
    """Bridge between workers and the real ToolRegistry.

    Provides:
    - Safe tool dispatch through existing unified pipeline
    - Permission validation before execution
    - Result normalization into WorkerResult-compatible format
    - Verification hooks after execution
    - Error classification and retry hints
    """

    def __init__(self) -> None:
        self._tools: Optional[Dict[str, Callable]] = None
        self._dispatch_fn: Optional[Callable] = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy-load the tool registry."""
        if self._loaded:
            return
        try:
            from ..registry import TOOLS, dispatch
            self._tools = TOOLS
            self._dispatch_fn = dispatch
            self._loaded = True
            logger.info("ToolBridge loaded: %d tools available", len(TOOLS))
        except ImportError:
            logger.warning("ToolRegistry not available — tool dispatch disabled")
            self._tools = {}
            self._dispatch_fn = None
            self._loaded = True

    @property
    def available_tools(self) -> List[str]:
        self._ensure_loaded()
        return sorted(self._tools.keys()) if self._tools else []

    def has_tool(self, tool_name: str) -> bool:
        self._ensure_loaded()
        return tool_name in (self._tools or {})

    def dispatch(
        self,
        tool_name: str,
        args: Dict[str, Any],
        allowed_tools: Optional[set] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Dispatch a tool call through the unified pipeline.

        Returns (success, result_dict).
        result_dict has keys: ok, tool, result/error, meta.
        """
        self._ensure_loaded()

        # Permission: check worker is allowed to use this tool
        if allowed_tools is not None and tool_name not in allowed_tools:
            return False, {
                "ok": False,
                "tool": tool_name,
                "error": f"Worker not allowed to use tool: {tool_name}",
                "meta": {"duration_ms": 0, "denied_by": "worker_permissions"},
            }

        # Dispatch through unified pipeline
        if self._dispatch_fn is None:
            return False, {
                "ok": False,
                "tool": tool_name,
                "error": "ToolRegistry not available",
                "meta": {"duration_ms": 0},
            }

        try:
            start = time.perf_counter()
            result = self._dispatch_fn(tool_name, args)
            latency_ms = (time.perf_counter() - start) * 1000

            # Normalize result
            if isinstance(result, dict):
                if "ok" not in result:
                    # U.1.1: RAW handler output. When the registry was loaded
                    # WITHOUT the unified dispatcher (headless/library use),
                    # TOOLS entries are undecorated handlers whose plain
                    # return dicts lack the {ok, tool, meta} envelope. A
                    # successful return IS a success — exceptions would have
                    # raised ToolError and been handled below.
                    return True, {
                        "ok": True,
                        "tool": tool_name,
                        "result": result.get("result", result),
                        "meta": {"duration_ms": latency_ms},
                    }
                if "meta" not in result:
                    result["meta"] = {}
                result["meta"]["duration_ms"] = latency_ms
                ok = result.get("ok", False)
                return ok, result
            else:
                return True, {
                    "ok": True,
                    "tool": tool_name,
                    "result": result,
                    "meta": {"duration_ms": latency_ms},
                }

        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error("Tool dispatch failed: %s — %s", tool_name, exc)
            return False, {
                "ok": False,
                "tool": tool_name,
                "error": str(exc),
                "meta": {"duration_ms": latency_ms},
            }

    def check_permissions(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check tool permissions without executing."""
        self._ensure_loaded()
        try:
            from ..registry import PermissionManager
            decision = PermissionManager.check(tool_name, args)
            return {
                "allowed": decision.allowed,
                "decision": decision.decision,
                "tool": decision.tool,
                "category": decision.category,
                "reason": decision.reason,
            }
        except ImportError:
            return {"allowed": True, "decision": "allow", "reason": "PermissionManager unavailable"}

    def verify_result(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        expected_outcome: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify a tool execution result.

        Returns verification report with confidence score.
        """
        checks: List[Dict[str, Any]] = []
        ok = result.get("ok", False)

        # Check 1: Tool reported success
        checks.append({
            "check": "tool_success",
            "passed": ok,
            "evidence": f"Tool {tool_name} returned ok={ok}",
        })

        # Check 2: Result has content
        has_result = bool(result.get("result"))
        checks.append({
            "check": "has_result",
            "passed": has_result,
            "evidence": "Result payload exists" if has_result else "Empty result",
        })

        # Check 3: No errors
        has_error = bool(result.get("error"))
        checks.append({
            "check": "no_errors",
            "passed": not has_error,
            "evidence": result.get("error", "No errors"),
        })

        # Check 4: Expected outcome (if provided)
        if expected_outcome:
            result_data = result.get("result", {})
            if isinstance(result_data, dict):
                outcome_match = expected_outcome.lower() in str(result_data).lower()
            else:
                outcome_match = expected_outcome.lower() in str(result_data).lower()
            checks.append({
                "check": "expected_outcome",
                "passed": outcome_match,
                "evidence": f"Expected '{expected_outcome}' in result",
            })

        all_passed = all(c["passed"] for c in checks)
        passed_count = sum(1 for c in checks if c["passed"])
        confidence = passed_count / len(checks) if checks else 0.0

        return {
            "verified": all_passed,
            "confidence": confidence,
            "checks": checks,
            "tool": tool_name,
        }


# Global singleton
_tool_bridge: Optional[ToolBridge] = None


def get_tool_bridge() -> ToolBridge:
    """Get the global ToolBridge singleton."""
    global _tool_bridge
    if _tool_bridge is None:
        _tool_bridge = ToolBridge()
    return _tool_bridge
