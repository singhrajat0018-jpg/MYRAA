"""
MYRAA Super-Brain — Capability Orchestrator (B7), Tool Strategy (B9),
Engine Plugin Seams (B19), and Computer-Use Readiness interfaces (B18).

The AI Manager 4.1 is the ROUTING AUTHORITY (decides WHAT). This orchestrator
consumes its TaskRoute (capability, execution_mode, reasoning_depth, freshness,
risk, tools_required, alternatives, confidence) and decides the EXECUTION
STRATEGY — which registered tool(s) to invoke, with what inputs, expected
output, risk and fallback.

REUSES the existing tool_resolver (capability -> registered tools) and does NOT
create a second capability registry. Engine plugin seams (Research/Trading/NX/
Creation) are mockable boundaries until those engines are fully implemented.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from desktop_agent.brain.ai.tool_resolver import resolve as resolve_tools
from desktop_agent.brain.ai.tool_resolver import is_resolvable

log = logging.getLogger(__name__)


# Real-tool fallbacks for capability-owned stages whose dedicated engine is not
# yet registered (B19). These are the ACTUAL registered tools that best express
# the stage today; never fabricate a tool id.
#
# GENERAL_INTELLIGENCE_ENGINE intentionally has NO fallback tool.  A general
# intelligence request must NEVER be silently escalated to searchWeb.  When no
# specialized engine is registered for this capability, the orchestrator returns
# a no-tool strategy and the pre-dispatch guard blocks any tool execution.
_CAPABILITY_FALLBACK_TOOL = {
    "PHONE_ENGINE": "typeText",
    "VOICE_ENGINE": "typeText",
    "RESEARCH_PIPELINE": "searchWeb",
    "TRADING_ENGINE": "searchWeb",
    "FINANCIAL_ENGINE": "searchWeb",
    "DOCUMENT_ENGINE": "createFile",
    "CREATION_ENGINE": "createFile",
    "PRESENTATION_ENGINE": "createFile",
    "SPREADSHEET_ENGINE": "createFile",
    "CODING_ENGINE": "writeCodeFile",
    "COMPUTER_USE_ENGINE": "openApplication",
    "DESKTOP_ENGINE": "openApplication",
    "FILES_ENGINE": "createFile",
    "FILE_MANAGEMENT_ENGINE": "createFile",
}


# ==========================================================
# B9: Tool strategy
# ==========================================================

@dataclass
class ToolStrategy:
    """Structured tool strategy for one step (B9)."""

    tool: str
    why: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    risk: str = "none"
    verification_method: str = "unverified"
    fallback: str = ""
    requires_confirmation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "why": self.why,
            "inputs": self.inputs,
            "expected_output": self.expected_output,
            "risk": self.risk,
            "verification_method": self.verification_method,
            "fallback": self.fallback,
            "requires_confirmation": self.requires_confirmation,
        }


# ==========================================================
# B19: Engine plugin seams (mockable boundaries)
# ==========================================================

class CapabilityEngine:
    """Base contract for a specialized capability engine (B19).

    Specialized engines (ResearchEngine, TradingEngine, NXEngine, CreationEngine)
    plug in later. Until then, the Super-Brain falls back to a structured
    bounded response or a mocked boundary in tests.
    """

    capability_id: str = ""

    def execute(self, goal: Any, context: Any) -> Dict[str, Any]:
        raise NotImplementedError


class CapabilityEngineRegistry:
    """Holds available specialized engines (B19). Never executes them here."""

    def __init__(self) -> None:
        self._engines: Dict[str, CapabilityEngine] = {}

    def register(self, engine: CapabilityEngine) -> None:
        self._engines[engine.capability_id] = engine

    def get(self, capability_id: str) -> Optional[CapabilityEngine]:
        return self._engines.get(capability_id)

    def has(self, capability_id: str) -> bool:
        return capability_id in self._engines

    def ids(self) -> List[str]:
        return list(self._engines.keys())


# ==========================================================
# B18: Computer-use readiness (interfaces only)
# ==========================================================

@dataclass
class ComputerUseStep:
    """One derived action for goal-based computer use (B18)."""

    action: str          # open_application, resolve_contact, type_text, ...
    target: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    verify: str = ""


@dataclass
class ComputerUsePlan:
    """Goal -> derived computer-use sequence (B18).

    Example for "Rahul ko message karde, main 10 min late aaunga.":
      open/focus WhatsApp
      find Rahul
      resolve contact
      open chat
      compose
      send
      verify
    """

    goal: str = ""
    steps: List[ComputerUseStep] = field(default_factory=list)
    is_supported: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "is_supported": self.is_supported,
            "steps": [s.__dict__ for s in self.steps],
        }


class ComputerUsePlanner:
    """
    Prepares the INTERFACES for universal goal-based computer use (B18).

    Produces a ComputerUsePlan for goal families we can express today. The full
    autonomous computer-use engine is NOT built here — this only derives the
    step sequence so downstream consumers can execute/verify it later.
    """

    def plan(self, goal: Any) -> ComputerUsePlan:
        action = (getattr(goal, "action", "") or "").lower()
        text = (getattr(goal, "text", "") or "").lower()
        recipient = getattr(goal, "recipient", "") or ""
        message = getattr(goal, "message", "") or ""

        if "send" in action and recipient:
            return ComputerUsePlan(
                goal=goal.text,
                is_supported=True,
                steps=[
                    ComputerUseStep("open_or_focus_app", "whatsapp", {"app": "whatsapp"}),
                    ComputerUseStep("find_contact", recipient, {"contact": recipient}),
                    ComputerUseStep("resolve_contact", recipient, {"contact": recipient}),
                    ComputerUseStep("open_chat", recipient, {"contact": recipient}),
                    ComputerUseStep("compose_message", recipient, {"text": message}),
                    ComputerUseStep("send_message", recipient, {}),
                    ComputerUseStep("verify_sent", recipient, {}, verify="message in conversation"),
                ],
            )
        return ComputerUsePlan(goal=goal.text, is_supported=False)


# ==========================================================
# B7: Capability Orchestrator
# ==========================================================

class CapabilityOrchestrator:
    """
    Consumes the AI Manager 4.1 TaskRoute and a Goal to produce a concrete
    ToolStrategy / execution strategy per capability stage (B7/B9).
    """

    def __init__(
        self,
        engine_registry: Optional[CapabilityEngineRegistry] = None,
        permission_manager: Optional[Any] = None,
    ) -> None:
        self.engines = engine_registry or CapabilityEngineRegistry()
        self.permission_manager = permission_manager
        self._tool_strategies: List[ToolStrategy] = []

    # ------------------------------------------------------------------

    def strategy_for(
        self,
        capability: str,
        goal: Any,
        route: Optional[Any] = None,
    ) -> ToolStrategy:
        """Pick a concrete tool strategy for a capability stage (B9).

        PRE-DISPATCH GUARD: If the canonical route declares tools_required=False,
        this returns a no-tool strategy. No downstream layer may override this.
        """
        cap = capability or getattr(goal, "capability", "") or ""

        # ── Pre-dispatch guard (safety invariant) ──
        # If TaskRouter determined no tools are needed, honour that.
        tools_required = getattr(route, "tools_required", None)
        route_meta = getattr(route, "metadata", {}) or {}
        if tools_required is False or route_meta.get("tools_required") is False:
            return ToolStrategy(
                tool="",
                why=f"pre-dispatch guard: route tools_required=False for capability {cap}",
                inputs={},
                expected_output=getattr(goal, "expected_output", ""),
                risk="none",
                verification_method="unverified",
                fallback="direct response — no tools allowed by route policy",
                requires_confirmation=False,
            )

        if self.engines.has(cap):
            return ToolStrategy(
                tool=f"engine::{cap}",
                why=f"delegated to specialized engine {cap} (B19)",
                inputs={"goal": getattr(goal, "text", "")},
                expected_output=getattr(goal, "expected_output", ""),
                risk=str(getattr(goal, "risk", "none")),
                verification_method="engine_verified",
                fallback="fallback to general LLM reasoning",
            )

        
        # Resolve the capability to real registered tools (existing resolver).
        candidates = self._resolve_capability_tools(cap, goal, route)
        if not candidates:
            # B19: capability-owned stage with no engine registered -> use the
            # real registered fallback tool that best expresses the stage.
            fallback_tool = _CAPABILITY_FALLBACK_TOOL.get(cap, "")
            if fallback_tool and is_resolvable(fallback_tool):
                candidates = [fallback_tool]
            elif cap == "GENERAL_INTELLIGENCE_ENGINE":
                # GENERAL_INTELLIGENCE_ENGINE has no fallback tool by design.
                # A general request must not be silently escalated to searchWeb.
                # Return a no-tool strategy; the pre-dispatch guard will block.
                return ToolStrategy(
                    tool="",
                    why=f"GENERAL_INTELLIGENCE_ENGINE has no fallback tool — direct response required",
                    inputs={},
                    expected_output=getattr(goal, "expected_output", ""),
                    risk="none",
                    verification_method="unverified",
                    fallback="direct LLM response — no web search",
                    requires_confirmation=False,
                )
        if candidates:
            tool = candidates[0]
            # Check if we should use a canonical ID directly instead of the resolved tool
            if route and hasattr(route, "tools_required") and route.tools_required:
                # Take the first tools_required item
                first_tool = route.tools_required[0]
                # Check if it's a canonical ID that maps to multiple tools (indicating a tool set)
                if is_resolvable(first_tool):
                    resolved = resolve_tools(first_tool)
                    # If it resolves to multiple tools, pick the BEST actual registered tool
                    # based on goal context instead of passing the canonical ID to the dispatcher
                    # (the CommandDispatcher only knows registered tool names, not canonical IDs).
                    if len(resolved) > 1:
                        tool = self._pick_best_tool(resolved, goal)
            return ToolStrategy(
                tool=tool,
                why=f"USING NEW LOGIC: candidates={candidates} first_tool={first_tool if 'first_tool' in locals() else 'not_set'} tool={tool} resolved from capability {cap} via existing tool_resolver",
                inputs=self._inputs_for(tool, goal),
                expected_output=getattr(goal, "expected_output", ""),
                risk=str(getattr(goal, "risk", "none")),
                verification_method=self._verify_method(cap, tool),
                fallback=self._fallback_for(cap, [tool]),
                requires_confirmation=self._needs_confirmation(tool, goal),
            )

        # Generic fallback: structured multiToolTask with goal metadata.
        return ToolStrategy(
            tool="multiToolTask",
            why=f"generic capability execution for {cap or 'unknown'}",
            inputs={
                "goal": getattr(goal, "text", ""),
                "capability": cap,
            },
            expected_output=getattr(goal, "expected_output", ""),
            risk=str(getattr(goal, "risk", "none")),
            verification_method="unverified",
            fallback="clarify or replan",
        )

    # ------------------------------------------------------------------

    def strategy_for_plan(
        self,
        master_plan: Any,
        route: Optional[Any] = None,
    ) -> List[ToolStrategy]:
        """Strategies for every step of a MasterPlan (B7/B9).

        Rewrites each step's CUSTOM tool_name (the `capability::<CAP>` marker)
        to a REAL registered tool so the existing Orchestrator -> CommandDispatcher
        path can execute it. Never fabricates tool ids.
        """
        strategies = []
        goal = master_plan.goal
        for step in master_plan.steps:
            cap = goal.capability
            sub_meta = step.parameters.get("parameters", {}) if step.parameters else {}
            sub_cap = sub_meta.get("capability") or cap
            strategy = self.strategy_for(sub_cap, goal, route)
            strategy.inputs = dict(strategy.inputs)
            # A step that already carries a REAL registered tool (computer-use
            # flow) has concrete parameters; only attach the goal-level metadata.
            existing = step.parameters.get("tool_name") or ""
            if existing and is_resolvable(existing):
                strategy.inputs = {"step_id": step.id, "goal": goal.text}
            else:
                strategy.inputs.update({"step_id": step.id, "goal": goal.text})
            self._rewrite_step_tool(step, strategy)
            strategies.append(strategy)
        self._tool_strategies = strategies
        return strategies

    @property
    def tool_strategies(self) -> List[ToolStrategy]:
        return list(self._tool_strategies)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pick_best_tool(self, candidates: List[str], goal: Any) -> str:
        """Pick the best actual registered tool from a list of candidates.

        When a canonical ID (like 'desktop_tool') resolves to multiple real
        tools, select the one most likely to satisfy the user's goal based
        on keyword matching.  Falls back to the first candidate.
        """
        goal_text = getattr(goal, "text", "") or ""
        lower = goal_text.lower()

        # Keyword -> preferred tool mapping (order matters: first match wins).
        keyword_tool_map = [
            (["youtube", "video"], "openWebsite"),
            (["website", "url", "http", "browse"], "openWebsite"),
            (["browser", "chrome", "firefox", "edge"], "openWebsite"),
            (["search", "google", "find", "look up"], "searchWeb"),
            (["close"], "closeApplication"),
            (["minimize"], "minimizeWindow"),
            (["maximize"], "maximizeWindow"),
            (["restore"], "restoreWindow"),
            (["switch", "activate"], "activateWindow"),
            (["open", "launch", "start", "run"], "openApplication"),
        ]

        for keywords, preferred in keyword_tool_map:
            if any(kw in lower for kw in keywords):
                if preferred in candidates:
                    return preferred

        return candidates[0] if candidates else "openApplication"

    def _resolve_capability_tools(
        self,
        capability: str,
        goal: Any,
        route: Optional[Any],
    ) -> List[str]:
        """Existing tool_resolver (capability/registered tools)."""
        # Canonical ids from AI Manager 4.1 capability registry / route tools.
        route_tools = list(getattr(route, "tools_required", []) or [])
        candidates: List[str] = []
        for entry in list(route_tools) + [capability]:
            if is_resolvable(entry):
                candidates.extend(resolve_tools(entry))
        # Dedupe preserving order.
        seen = set()
        unique = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        return unique

    def _rewrite_step_tool(self, step: Any, strategy: ToolStrategy) -> None:
        """Point a plan step's CUSTOM tool_name at a real registered tool."""
        if strategy.tool.startswith("engine::"):
            # Engine not registered -> do not fabricate; keep the marker.
            return
        if not step.parameters:
            return
        params = step.parameters.get("parameters", {})
        if isinstance(params, dict):
            # Merge deterministic arg mapping into the step's own params so the
            # CommandDispatcher validation (e.g. typeText -> text) succeeds.
            merged = dict(params)
            for key, value in strategy.inputs.items():
                if key in ("step_id", "goal"):
                    continue
                if key not in merged or not merged[key]:
                    merged[key] = value
            step.parameters["parameters"] = merged
        # A step that already carries a REAL registered tool (e.g. the
        # computer-use flow's openApplication/typeText/pressKey) must not be
        # overwritten by the capability-level fallback tool.
        existing = step.parameters.get("tool_name") or ""
        if existing and is_resolvable(existing):
            return
        step.parameters["tool_name"] = strategy.tool

    def _inputs_for(self, tool: str, goal: Any) -> Dict[str, Any]:
        """Map a goal to tool-specific args (deterministic; never executed)."""
        text = getattr(goal, "text", "") or ""
        action = getattr(goal, "action", "") or ""
        message = getattr(goal, "message", "") or ""
        recipient = getattr(goal, "recipient", "") or ""
        inputs: Dict[str, Any] = {}
        low_tool = tool.lower()

        if "search" in low_tool or tool in ("searchWeb", "searchGoogle", "searchYouTube"):
            inputs["query"] = text
        elif tool in ("typeText", "pasteClipboard"):
            inputs["text"] = message or text
        elif tool in ("createFile", "writeCodeFile", "createPythonFile"):
            inputs["path"] = ""
            inputs["content"] = text
            inputs["goal"] = text
        elif tool == "openApplication":
            inputs["application"] = recipient or text
        elif tool == "desktopAutomation" or tool == "multiToolTask":
            inputs["goal"] = text
            inputs["capability"] = getattr(goal, "capability", "")
        elif "power" in low_tool:
            inputs["action"] = "none"
        else:
            inputs["goal"] = text
        return inputs

    def _verify_method(self, capability: str, tool: str) -> str:
        cap = capability or ""
        if cap in ("RESEARCH_PIPELINE", "TRADING_ENGINE", "FINANCIAL_ENGINE"):
            return "evidence"
        if cap in ("DOCUMENT_ENGINE", "CREATION_ENGINE", "PRESENTATION_ENGINE",
                   "SPREADSHEET_ENGINE", "CODING_ENGINE", "FILES_ENGINE"):
            return "deterministic"
        if "search" in tool:
            return "evidence"
        if "open" in tool or "activate" in tool or "switch" in tool:
            return "deterministic"
        return "unverified"

    def _fallback_for(self, capability: str, candidates: List[str]) -> str:
        if len(candidates) > 1:
            return f"fallback to {candidates[1]}"
        cap = capability or ""
        if cap == "RESEARCH_PIPELINE":
            return "fallback research provider -> general LLM reasoning"
        if cap in ("TRADING_ENGINE", "FINANCIAL_ENGINE"):
            return "advisory fallback with uncertainty; never execute trades"
        return "replan with simpler capability or clarify"

    def _needs_confirmation(self, tool: str, goal: Any) -> bool:
        """Whether this tool needs the P0 PermissionManager confirmation flow."""
        low = tool.lower()
        destructive = ("delete", "remove", "execute", "power", "shutdown", "restart")
        financial = ("trade", "buy", "sell", "order", "transfer")
        text = (getattr(goal, "text", "") or "").lower()
        if any(k in low for k in destructive):
            return True
        if any(k in text for k in financial):
            return True
        return False