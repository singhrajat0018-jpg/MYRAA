"""
MYRAA Brain Engine

Top-level cognitive controller.

Responsibilities
----------------
- Receive user intent
- Build BrainContext
- Coordinate perception, memory and reasoning
- Generate execution plans
- Delegate execution to the Execution Orchestrator
"""

from __future__ import annotations
from desktop_agent.brain.context_manager import ContextManager
from desktop_agent.brain.executive.execution_coordinator import (
    ExecutionCoordinator,
)
import threading
import logging
import time
from typing import Optional
from desktop_agent.brain.blackboard.blackboard import Blackboard
from .thinking.thinking_engine import ThinkingEngine
from .knowledge.knowledge_decision import (
    KnowledgeDecisionEngine,
)
from desktop_agent.brain.memory.retrieval_engine import (
    MemoryRetrievalEngine,
)
from .perception import Perception
from .world_model import WorldModel
from .reasoning_engine import ReasoningEngine
from .models import BrainResult
from .autonomy.autonomy_loop import AutonomyLoop
from .memory.unified_manager import UnifiedMemoryManager
from .memory.memory_commands import MemoryCommandEngine
from .working_memory.working_memory import WorkingMemory
from .cognition.evaluator import CognitiveEvaluator
from .context.brain_context import BrainContext
from .context.context_resolver import ContextResolver
from .cognition.cognitive_cycle import CognitiveCycle
from .orchestrator.orchestrator import Orchestrator
from .attention.attention_engine import AttentionEngine
from .state.brain_state import BrainState, CognitiveState
from .state.goal_manager import GoalManager
from .reasoning.pipeline import ReasoningPipeline
from .decision.decision_engine import DecisionEngine
from .planner.planner import Planner
from .goals.goal_scheduler import GoalScheduler
from .executive.executor import Executor
from .reflection.reflection_engine import ReflectionEngine
from .semantic.semantic_parser import SemanticParser
from .cognition.intent_classifier import IntentClassifier
from desktop_agent.brain.thinking.thinking_engine import (
    ThinkingEngine,
)

from desktop_agent.brain.thinking.confidence_engine import (
    ConfidenceItem,
    ConfidenceSource,
)

from desktop_agent.brain.thinking.metacognition import (
    Metacognition,
)
from .cognition.cognitive_state_manager import CognitiveStateManager
from .autonomy.autonomy_manager import AutonomyManager
from desktop_agent.brain.ai.ai_manager import AIManager
from desktop_agent.brain.semantic.semantic_models import Intent
from .executive.executive_controller import ExecutiveController
from .router.response_router import (
    ResearchHandoff,
    ResponseRouteType,
    ResponseRouter,
)
from .research.research_router import ResearchRouter
log = logging.getLogger(__name__)

class BrainEngine:

    """
    MYRAA Cognitive Controller.
    """

    def __init__(

        self,

        orchestrator: Orchestrator,

        planner: Planner | None = None,

        decision_engine=None,

        execution_coordinator=None,

        reflection_engine=None,

        memory_manager=None,

        ai_manager=None,

        config=None,
    ):
        self.config = config
        self._lock = threading.RLock()

        # =====================================================
        # Shared Blackboard (Single Instance)
        # =====================================================

        self.blackboard = Blackboard()
        from desktop_agent.brain.state.brain_state_manager import (
            BrainStateManager,
        )

        self.brain_state = BrainStateManager()

        from desktop_agent.brain.blackboard.bridge.blackboard_bridge import (
            BlackboardBridge,
        )

        self.bridge = BlackboardBridge(

            self.blackboard,

        )

        self.perception = Perception()

        self.memory_retrieval = MemoryRetrievalEngine()

        self.world = WorldModel()

        self.planner = (

            planner

            if planner

            else Planner(

                blackboard=self.blackboard,

            )

        )

        self.executive = ExecutiveController(
            self.planner
        )



        self.cognitive_state = CognitiveStateManager()

        self.intent_classifier = IntentClassifier()

        self.working_memory = WorkingMemory()
        log.debug("========== BRAIN ENGINE ==========")
        log.debug("WorkingMemory ID: %s", id(self.working_memory))
        log.debug("=================================")

        # Runtime context

        self.memory = (

            memory_manager

            if memory_manager

            else UnifiedMemoryManager()

        )

        # M9: the unified store is the single authoritative memory. When the
        # container injects the shared instance post-construction, this points
        # at the SAME store as `self.memory_2_0`.
        if getattr(self, "memory_2_0", None) is None:

            self.memory_2_0 = self.memory

        # M10: explicit memory command engine (REMEMBER/RECALL/UPDATE/FORGET/
        # LIST/CLEAR_SCOPE) executes against the same unified store.
        self.memory_command_engine = MemoryCommandEngine(self.memory_2_0)

        self.context_manager = ContextManager(self.perception, self.blackboard, self.memory)

        self.reflection = ReflectionEngine(

            working_memory=self.working_memory,

            blackboard=self.blackboard,

        )

        if execution_coordinator is not None:

            self.execution_coordinator = execution_coordinator

        else:

            self.execution_coordinator = (

                orchestrator.execution_coordinator

            )

        self.execution_coordinator.reflection = self.reflection

        self.execution_coordinator.working_memory = (

            self.working_memory

        )

        self.execution_coordinator.blackboard = (

            self.blackboard

        )

        self.reasoning = ReasoningEngine(
            self.world
        )
        

       

        self.attention = AttentionEngine()

        self.reasoning_pipeline = ReasoningPipeline(
            self.reasoning
        )

        self.context_resolver = ContextResolver()

        # Executor pipeline is under migration.
        # Production execution is handled by Orchestrator.
        # self.executor = Executor(
        #     tool_router=self.router
        # )  # Commented out during migration - to be removed or restored after migration completes

        self.cognitive_cycle = CognitiveCycle(self)

        self.semantic_parser = SemanticParser()

        # Authoritative AI provider router (EPIC-03). Used for real LLM
        # reasoning (EPIC-04). A single container-owned instance is injected
        # when provided so the whole runtime shares ONE AI Manager authority.
        self.ai = ai_manager if ai_manager is not None else AIManager()

        # EPIC-07: authoritative CAPABILITY router. Decides which MYRAA
        # capability (LOCAL_FAST/BRAIN/RESEARCH/EXECUTION/MEMORY) should handle
        # a request. Deterministic; reuses the parsed SemanticTask. Distinct from
        # self.ai (provider selection).
        self.response_router = ResponseRouter()
        self._last_response_route = None

        # EPIC-08: RESEARCH capability (lazy — only constructed on first RESEARCH
        # request so ordinary conversation never pays for provider setup).
        self._research_router = None
        self._last_research_result = None

        self.knowledge_decision = KnowledgeDecisionEngine()

        self.decision = (

            decision_engine

            if decision_engine is not None

            else DecisionEngine()

        )

        self.cognitive_evaluator = CognitiveEvaluator()

        self.thinking = ThinkingEngine(

            blackboard=self.blackboard,

        )

        self.metacognition = Metacognition()

        # =====================================================
        # Autonomous Brain
        # =====================================================

        self.autonomy = AutonomyLoop(

            brain=self,

            planner=self.planner,

            execution_coordinator=self.execution_coordinator,

            reflection_engine=self.reflection,

            learning_engine=self.memory,

            blackboard=self.blackboard,

            fps=getattr(self.config, "brain_fps", 30),

            config=self.config,

        )     

        self.orchestrator = orchestrator

        self._current_context: Optional[BrainContext] = None
        self.autonomy_manager = AutonomyManager()
        # Runtime State
        self.state = BrainState()

        self.goals = GoalManager()
        self.scheduler = GoalScheduler()

        log.debug("=" * 60)
        log.debug("DecisionEngine instance: %s", self.decision)
        log.debug("DecisionEngine class   : %s", self.decision.__class__)
        log.debug("DecisionEngine module  : %s", self.decision.__class__.__module__)
        log.debug("DecisionEngine file    : %s", self.decision.__class__.__dict__.get("__module__"))
        log.debug("=" * 60)
    # ----------------------------------------------------

    @property
    def context(self):

        return self._current_context

        # ----------------------------------------------------

    def _build_context(

        self,

        intent,

    ) -> BrainContext:

        return BrainContext(

            perception=self.perception.snapshot,

            world=self.world.state,

            reasoning=None,

            intent=intent,

            working_memory=self.memory.working.snapshot(),

            episodic_memory=self.memory.episodic.recent(),

            semantic_memory=self.memory.semantic.snapshot(),

            execution_history=[],

            metadata={},

        )
    def _resolve_input(
        self,
        text: str,
    ):
        return self.context_resolver.resolve(
            text,
            self.working_memory,
        )

    def _parse_semantics(
        self,
        text,
        context,
    ):

        return self.semantic_parser.parse(
            text,
            context,
        )


    def think(
        self,
        task,
    ):
        """
        Build the cognitive context for the current task.
        """

        context = self._build_runtime_context()

        self._current_context = context

        return context

    def _decide(
        self,
        task,
        context,
    ):

        return self.decision.decide(
            task,
            context,
        )


    def _plan(
        self,
        decision,
    ):

        return self.planner.create_plan(
            decision
        )

    def _execute(
        self,
        plan,
    ):

        return self.orchestrator.execute(
            plan
        )

    def _post_process(
        self,
        result,
    ):

        try:

            self.reflection.record(

                action=getattr(result, "tool", "unknown"),

                success=getattr(result, "success", False),

                message=getattr(result, "message", ""),

            )

        except Exception:

            log.exception("Failed to record reflection.")

        return result

    # ----------------------------------------------------
    # EPIC-04: real LLM reasoning path
    # ----------------------------------------------------

    # Structured intents handled by the rule-based / execution path. These are
    # NOT sent to the LLM: they map to local actions or goal management.
    _NON_LLM_INTENTS = {
        Intent.OPEN_APPLICATION,
        Intent.CLOSE_APPLICATION,
        Intent.CREATE_FILE,
        Intent.CREATE_FOLDER,
        Intent.DELETE_FILE,
        Intent.MOVE_FILE,
        Intent.COPY_FILE,
        Intent.SEARCH_WEB,
        Intent.OPEN_WEBSITE,
        Intent.SET_GOAL,
        Intent.GET_GOAL,
        Intent.CLEAR_GOAL,
        Intent.ROUTER_ACTION,
    }

    def _requires_llm(
        self,
        semantic_task,
    ) -> bool:
        """
        True for language/reasoning-heavy requests. Concrete execution tasks (a
        mapped action, or a structured tool-intent) stay on the rule path.
        """
        if semantic_task.metadata.get("action"):
            return False

        return semantic_task.intent not in self._NON_LLM_INTENTS

    def _conversation_context_lines(
        self,
        context,
        max_turns: int = 6,
    ):
        """
        Extract a bounded recent-conversation window from the /brain context
        (Node-owned conversation history). Only the last few turns are included
        so the LLM prompt stays bounded.
        """
        if context is None:
            return []

        metadata = getattr(context, "metadata", None) or {}

        if not isinstance(metadata, dict):
            return []

        history = metadata.get("conversation_history")

        if not isinstance(history, (list, tuple)):
            return []

        lines = []

        for turn in history[-max_turns:]:

            if isinstance(turn, dict):
                role = turn.get("role")
                turn_text = turn.get("text", "")
            else:
                role = getattr(turn, "role", None)
                turn_text = getattr(turn, "text", "")

            if not turn_text:
                continue

            label = "User" if role == "user" else "MYRAA"
            lines.append(f"{label}: {turn_text}")

        return lines

    def _build_llm_prompt(
        self,
        text: str,
        semantic_task,
        context=None,
    ):
        """
        Smallest relevant context for the LLM: the user text, the detected
        intent, a bounded window of recent conversation history, and the current
        foreground application if known. The whole Blackboard / memory are never
        dumped into the prompt.
        """
        intent_value = getattr(
            semantic_task.intent,
            "value",
            str(semantic_task.intent),
        )

        system_prompt = (
            "You are MYRAA, a helpful Windows desktop AI assistant. "
            "Answer the user's request clearly and concisely. "
            "Never claim to have performed a computer action that was not "
            "actually executed."
        )

        lines = [
            f"Intent: {intent_value}",
        ]

        # EPIC-06: bounded recent-conversation context for continuity.
        conv_lines = self._conversation_context_lines(context)

        if conv_lines:
            lines.append("Recent conversation:")
            lines.extend(conv_lines)

        lines.append(f"User: {text}")

        try:

            current_app = self.working_memory.current_application()

            if current_app:

                lines.append(
                    f"Foreground application: {current_app}"
                )

        except Exception:
            pass

        return system_prompt, "\n".join(lines)

    def _maybe_llm_reason(
        self,
        text: str,
        semantic_task,
        context=None,
    ):
        """
        Invoke the authoritative AI provider (AIManager.route) for requests that
        genuinely benefit from LLM reasoning.

        Returns a BrainResult when the request is handled (success, or a
        controlled failure/fallback), or None to continue on the existing
        rule/execution path.

        The LLM is reasoning only: it never triggers desktop actions. Desktop
        execution stays behind ExecutionBrain -> Orchestrator -> Dispatcher.
        """
        if not self._requires_llm(semantic_task):

            return None

        system_prompt, user_prompt = self._build_llm_prompt(
            text,
            semantic_task,
            context,
        )

        try:

            raw = self.ai.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                hints={"categories": ["conversational", "local"]},
                task=semantic_task,
            )

        except Exception as exc:

            log.warning(
                "[Brain] LLM generation failed: %s",
                exc,
            )

            return BrainResult(
                success=False,
                message="AI reasoning failed: " + str(exc),
                actions=[],
                metadata={
                    "llm": True,
                    "error": str(exc),
                },
                provider="none",
            )

        output = (raw or "").strip()

        provider_name = getattr(self.ai, "_active_provider", None)
        if provider_name is not None:
            provider_name = getattr(provider_name, "name", "unknown")
        else:
            provider_name = "unknown"

        if not output:

            return BrainResult(
                success=False,
                message="AI returned an empty response.",
                actions=[],
                metadata={
                    "llm": True,
                    "provider": provider_name,
                    "empty": True,
                },
                provider=provider_name,
            )

        return BrainResult(
            success=True,
            message=output,
            actions=[],
            metadata={
                "llm": True,
                "provider": provider_name,
            },
            provider=provider_name,
        )

    def _get_research_router(self):
        if self._research_router is None:
            self._research_router = ResearchRouter()
        return self._research_router

    def _handle_research(
        self,
        text: str,
        context,
        response_route,
    ) -> BrainResult:
        """
        Run the RESEARCH capability for an EPIC-07 RESEARCH route: real provider
        research (Tavily/DDG/Wikipedia) -> bounded evidence -> AIManager synthesis
        -> ONE grounded answer. Never fabricates a current answer on failure.

        Phase 4.5: Fast-path bypass for static knowledge — if the query doesn't
        need external sources, skip research and answer directly via LLM.
        """
        handoff = response_route.metadata.get("research_handoff")
        if not isinstance(handoff, ResearchHandoff):
            handoff = ResearchHandoff(query=text, reason=response_route.reason)

        # Phase 4.5: Fast-path — skip research for static knowledge
        try:
            router = self._get_research_router()
            if not router.needs_external_source(text):
                log.debug("[Research] Fast-path: static knowledge, skipping external sources")
                # Fall through to LLM reasoning instead
                llm_result = self._maybe_llm_reason(text, None, context)
                if llm_result is not None:
                    llm_result.metadata["route"] = "BRAIN"
                    llm_result.metadata["route_reason"] = "static knowledge fast-path"
                    return llm_result
        except Exception:
            pass  # If fast-path check fails, continue with normal research
        handoff = response_route.metadata.get("research_handoff")
        if not isinstance(handoff, ResearchHandoff):
            handoff = ResearchHandoff(query=text, reason=response_route.reason)

        # EPIC-06: pass bounded conversation context into synthesis where useful.
        conversation_context = None
        try:
            meta = getattr(context, "metadata", None) or {}
            if isinstance(meta, dict):
                conversation_context = meta.get("conversation_history")
        except Exception:
            conversation_context = None

        try:
            research = self._get_research_router().research(
                handoff,
                conversation_context,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("[Research] pipeline failed: %s", exc)
            return BrainResult(
                success=False,
                message="Research unavailable: " + str(exc),
                actions=[],
                metadata={
                    "route": ResponseRouteType.RESEARCH.value,
                    "route_reason": response_route.reason,
                },
            )

        self._last_research_result = research

        if not research.success or not research.synthesized:
            # Controlled failure — do not present stale/ungrounded knowledge as
            # current information.
            reason = "; ".join(research.errors) or "no evidence retrieved"
            return BrainResult(
                success=False,
                message="Research could not produce a grounded answer. " + reason,
                actions=[],
                metadata={
                    "route": ResponseRouteType.RESEARCH.value,
                    "route_reason": response_route.reason,
                    "research": research.to_dict(),
                },
            )

        return BrainResult(
            success=True,
            message=research.synthesized,
            actions=[],
            metadata={
                # EPIC-05 gate: this is the authoritative, single user-facing answer.
                "llm": True,
                "route": ResponseRouteType.RESEARCH.value,
                "route_reason": response_route.reason,
                "research": {
                    "query": research.query,
                    "source_count": len(research.sources),
                    "providers": [p.provider for p in research.provider_results],
                    "synthesis_provider": research.synthesis_provider,
                },
            },
            provider=research.synthesis_provider,
        )

    def process(self, text: str, context=None):
        log.debug("[Brain] process()")
        t0 = time.perf_counter()
        resolved_text = self._resolve_input(text)
        log.debug("Resolve: %.3fs", time.perf_counter()-t0)

        # M10: explicit memory commands short-circuit the pipeline so they are
        # always handled deterministically, before routing or LLM paths.
        cmd_result = self.memory_command_engine.handle(text, context)
        if cmd_result is not None:
            log.debug("[Brain] MemoryCommand handled: %s", cmd_result.operation)
            return BrainResult(
                success=cmd_result.success,
                message=cmd_result.message,
                metadata={
                    "route": "MEMORY_COMMAND",
                    "command_operation": cmd_result.operation,
                    "command_affected": cmd_result.affected_ids,
                },
            )
        log.debug("[Brain] starting semantic parser")
        t1 = time.perf_counter()
        semantic_task = self._parse_semantics(
            resolved_text,
            context,
        )
        log.debug("<<< PARSE RETURNED >>>")
        log.debug("semantic_task type: %s", type(semantic_task))
        log.debug("semantic_task: %s", semantic_task)

        # ----------------------------------------------------
        # EPIC-07: authoritative CAPABILITY router. One decision authority for
        # which MYRAA capability handles this request. Deterministic, reuses the
        # parsed SemanticTask, never executes. Distinct from AIManager (provider).
        # ----------------------------------------------------
        response_route = self.response_router.route(semantic_task)
        self._last_response_route = response_route
        log.debug("[ResponseRouter] route=%s reason=%s", response_route.route.value, response_route.reason)

        log.debug("<<< ABOUT TO CALL MEMORY >>>")
        log.debug(">>> BEFORE MEMORY RETRIEVAL")
        memory_result = self.memory_retrieval.resolve(
            resolved_text,
            self.working_memory,
        )
        log.debug(">>> AFTER MEMORY RETRIEVAL")
        log.debug("memory_result: %s", memory_result)

        if memory_result.handled:

            log.debug("[Memory Retrieval] handled")

            return BrainResult(
                success=True,
                message=memory_result.response,
                metadata={
                    "source": memory_result.source,
                    "confidence": memory_result.confidence,
                    # EPIC-07: the existing memory architecture already handled
                    # this request, so it is the MEMORY capability.
                    "route": ResponseRouteType.MEMORY.value,
                    "route_reason": "existing memory retrieval handled the request",
                },
            )
        self.brain_state.update_task(
            semantic_task
        )

        # ----------------------------------------------------
        # LOCAL_FAST short-circuit. Pure conversation / small talk is
        # answered by the local fast model (Qwen3.5) alone. Returning a
        # non-LLM, un-surfaced result here prevents a second Brain answer for the
        # same request (one request -> one authoritative response).
        # ----------------------------------------------------
        if response_route.route == ResponseRouteType.LOCAL_FAST:
            return BrainResult(
                success=True,
                message="",
                actions=[],
                metadata={
                    "route": ResponseRouteType.LOCAL_FAST.value,
                    "route_reason": response_route.reason,
                },
            )

        # ----------------------------------------------------
        # EPIC-08: RESEARCH capability. Consume the EPIC-07 ResearchHandoff, run
        # the ResearchRouter (Tavily/DDG/Wikipedia), synthesize ONE grounded
        # answer via AIManager, and surface it as the single authoritative reply.
        # ----------------------------------------------------
        if response_route.route == ResponseRouteType.RESEARCH:
            return self._handle_research(
                resolved_text,
                context,
                response_route,
            )

        # ----------------------------------------------------
        # EPIC-04: real LLM reasoning path.
        # The authoritative AIManager.route() selects the provider; the LLM is a
        # reasoning layer only and never executes desktop actions. Non-LLM /
        # execution intents skip this and continue on the rule path below.
        # ----------------------------------------------------

        llm_result = self._maybe_llm_reason(
            resolved_text,
            semantic_task,
            context,
        )

        if llm_result is not None:

            # EPIC-07: stamp the authoritative route for explainability.
            llm_result.metadata["route"] = response_route.route.value
            llm_result.metadata["route_reason"] = response_route.reason

            return llm_result

        log.debug("[Brain] semantic parser finished")
        log.debug("[Brain] starting think")
        brain_context = self.think(semantic_task)

        # ----------------------------------------------------
        # Knowledge vs Browser Decision
        # ----------------------------------------------------

        decision = self.knowledge_decision.decide(
            resolved_text
        )

        log.debug("========== KNOWLEDGE DECISION ==========")
        log.debug("Browser : %s", decision.use_browser)
        log.debug("Knowledge: %s", decision.use_knowledge)
        log.debug("Reason   : %s", decision.reason)
        log.debug("========================================")

        brain_context.metadata["use_browser"] = (
            decision.use_browser
        )

        brain_context.metadata["use_knowledge"] = (
            decision.use_knowledge
        )
        log.debug("[Brain] think finished")
        # Inject active goal into the cognitive context
        brain_context.metadata["active_goal"] = self.current_goal()
        log.debug("[Brain] starting decision")
        # -------------------------------------------------
        # Update runtime context before decision
        # -------------------------------------------------

        try:

            current_app = self.working_memory.current_application()

            if current_app:
                self.context_manager.set(
                    "active_application",
                    current_app,
                )

            current_file = self.working_memory.current_file()

            if current_file:
                self.context_manager.set(
                    "active_file",
                    current_file,
                )

        except Exception:
            pass
        decision = self.decision.decide(
            semantic_task,
            brain_context,
        )       
        log.debug("[Brain] decision finished")
        log.debug("========== SemanticTask ==========")
        log.debug("Intent   : %s", semantic_task.intent)
        log.debug("Metadata : %s", semantic_task.metadata)
        log.debug("==================================")
        log.debug("Semantic: %.3fs", time.perf_counter()-t1)

        # =====================================================
        # Thinking Engine
        # =====================================================

        confidence_items = [

            ConfidenceItem(

                source=ConfidenceSource.INTENT,

                score=decision.confidence,

                explanation="Decision engine confidence.",

            )

        ]

        thinking = self.thinking.think(

            observation=resolved_text,

            required_fields={},

            confidence_inputs=confidence_items,

        )
        self.brain_state.update_thinking(

            confidence=thinking.confidence.overall,

            uncertainty=thinking.uncertainty.confidence,

        )
        trace = self.thinking.latest_trace()

        self.blackboard.write(

            "reasoning",

            "latest",

            trace,

        )

        t4 = time.perf_counter()
        if thinking.uncertainty.requires_clarification:

            return thinking.uncertainty.clarification_question
        log.debug("[Brain] starting planner")
        plan = self.planner.create_plan(decision)
        log.debug("[Brain] planner finished")
        self.brain_state.update_plan(
            plan
        )
        self.state.set_plan(plan)
        if not plan.successful or plan.total_steps == 0:
            log.warning(
                "Planner returned an empty execution plan."
            )

            return BrainResult(
                success=False,
                message="Planner could not generate an execution plan.",
                actions=[],
                metadata={
                    "planner_failed": True,
                    "reason": getattr(plan, "reason", ""),
                    # EPIC-07
                    "route": response_route.route.value,
                    "route_reason": response_route.reason,
                },
            )

        # =====================================================
        # Executive
        # =====================================================

        log.debug("[Brain] starting executive")

        request = self.executive.submit(plan)

        plan = request.metadata["plan"]

        log.debug("[Brain] executive finished")

        # =====================================================
        # Execute
        # =====================================================

        t5 = time.perf_counter()

        log.debug("[Brain] starting execute")

        result = self.orchestrator.execute(plan)

        log.debug("[Brain] execute finished")

        if result.success:

            self.complete_goal()

        else:

            self.fail_goal()
        meta = self.metacognition.evaluate(

            thinking,

            execution_success=result.success,

        )

        self.blackboard.write(

            "metacognition",

            "latest",

            meta,

        )

        log.debug("Execute: %.3fs", time.perf_counter() - t5)
        log.debug("TOTAL: %.3fs", time.perf_counter() - t0)

        # EPIC-07: stamp the authoritative route for explainability. This is an
        # EXECUTION/RESEARCH capability outcome produced by the existing
        # Orchestrator -> CommandDispatcher path (never executed by the router).
        if hasattr(result, "metadata") and isinstance(result.metadata, dict):
            result.metadata["route"] = response_route.route.value
            result.metadata["route_reason"] = response_route.reason

        return result

    def set_goal(self, goal):

        self.state.set_goal(goal)

        if hasattr(self, "brain_state"):

            self.brain_state.update_goal(goal)
    def current_goal(self):

        goal = self.scheduler.next()

        if goal is None:

            goal = self.goals.next()

        return goal


    def complete_goal(self):

        goal = self.current_goal()

        if goal is None:

            return

        log.info("[Brain] Goal completed: %s", goal)

        self.scheduler.complete()

        self.goals.complete()

        self.state.set_goal(None)

        if hasattr(self, "brain_state"):

            self.brain_state.update_goal(None)

    def fail_goal(self):

        goal = self.current_goal()

        if goal is None:

            return

        log.info("[Brain] Goal failed: %s", goal)

        self.goals.fail()

        self.state.set_goal(None)

    def cancel_goal(self):

        goal = self.current_goal()

        if goal is None:

            return

        log.info("[Brain] Goal cancelled: %s", goal)

        self.goals.cancel()

        self.state.set_goal(None)

    # ----------------------------------------------------
    # Event Integration
    # ----------------------------------------------------

    def register_execution_events(self) -> None:
        """
        Subscribe to execution events exposed by the
        execution orchestrator.
        """

        self.orchestrator.on(
            "before_plan",
            self._on_before_plan,
        )

        self.orchestrator.on(
            "after_plan",
            self._on_after_plan,
        )

        self.orchestrator.on(
            "before_step",
            self._on_before_step,
        )

        self.orchestrator.on(
            "after_step",
            self._on_after_step,
        )

        self.orchestrator.on(
            "on_failure",
            self._on_failure,
        )

        # ----------------------------------------------------

    def _on_before_plan(self, plan):

        self.memory.working.add(

            value=plan,

            category="execution_plan",

            importance=0.8,

        )


    # ----------------------------------------------------

    def _on_after_plan(

        self,

        plan,

        success: bool,

    ):

        self.memory.episodic.record(

            title="Execution Finished",

            category="execution",

            description=f"Success={success}",

            importance=0.9,

        )


    # ----------------------------------------------------

    def _on_before_step(

        self,

        step,

    ):

        self.memory.working.add(

            value=step,

            category="step",

        )


    # ----------------------------------------------------

    def _on_after_step(

        self,

        step,

        response,

    ):

        self.memory.episodic.record(

            title=step.name,

            category="completed_step",

            importance=0.7,

            metadata={

                "tool": step.action,

                "response": response,

            },

        )


    # ----------------------------------------------------

    def _on_failure(

        self,

        step,

        error,

    ):

        self.memory.episodic.record(

            title="Execution Failure",

            category="failure",

            description=str(error),

            importance=1.0,

        )

    # ----------------------------------------------------

    def learn(

        self,

        key,

        value,

    ):

        self.memory.semantic.store(

            key,

            value,

            source="brain",

        )

        # ----------------------------------------------------
    def update_perception(
        self,
        desktop_state,
    ):
        """
        Synchronize latest desktop perception.
        """

        log.debug("[Brain] perception updated")

        # -----------------------------------------
        # Perception
        # -----------------------------------------

        self.perception.update(
            desktop_state
        )

        perception = self.perception.snapshot

        self.world.update(
            perception
        )

        # -----------------------------------------
        # Blackboard
        # -----------------------------------------

        self.blackboard.write(
            "perception",
            "desktop_state",
            desktop_state,
        )

        self.blackboard.write(
            "perception",
            "snapshot",
            perception,
        )

        # -----------------------------------------
        # Runtime Cache
        # -----------------------------------------

        self._current_perception = perception

        self._current_context = self._build_runtime_context()
        # ----------------------------------------------------
    def _build_runtime_context(self) -> BrainContext:
        """
        Build BrainContext from live runtime state.
        """

        return BrainContext(

            perception=self.perception.snapshot,

            world=self.world.state,

            reasoning=None,

            intent=None,

            working_memory=self.working_memory.get_snapshot(),

            episodic_memory=self.memory.episodic,

            semantic_memory=self.memory.semantic,

            execution_history=(),

            metadata={
                "source": "vision",
            },

        )

        
    def verify(

        self,

        expected_state,

    ):

        current = self.perception.snapshot

        return current == expected_state

        # TODO:
        # Temporary duplicate.
        # Will be merged after Brain integration.

    def process_legacy(

        self,

        intent,

    ):

        context = self.think(

            intent

        )

        plan = self.plan(

            context

        )

        result = self.execute(

            plan

        )

        try:

            if semantic_task.intent.name == "ROUTER_ACTION":

                tool = semantic_task.metadata.get("action")

                params = semantic_task.metadata.get(
                    "parameters",
                    {},
                )

                if tool == "openWebsite":

                    url = params.get("url", "").lower()

                    if "youtube" in url:

                        self.working_memory.remember_entity(
                            "application",
                            "youtube",
                        )

                    elif "google" in url:

                        self.working_memory.remember_entity(
                            "application",
                            "browser",
                        )

                elif tool == "openApplication":

                    app = params.get("application")

                    if app:

                        self.working_memory.remember_entity(
                            "application",
                            app,
                        )

        except Exception:
            pass

        self.memory.episodic.record(

            title="User Request",

            category="interaction",

            description=str(intent),

        )

        return result

    def tick(self):

        log.debug("[Brain] tick()")

        self.world.update(
            self.perception.snapshot
        )

        context = self._build_runtime_context()

        self._current_context = context
        log.debug("[Brain] context ready")

        if context is None:
            log.debug("[Brain] context is None")
            return

        log.debug("[Brain] running cognitive cycle")

        self.cognitive_cycle.run()

        log.debug("[Brain] cognitive cycle finished")

        goal = self.current_goal()

        log.debug("[Brain] goal = %s", goal)

        if goal is None:
            log.debug("[Brain] no goal")
            return

        if getattr(self, "_runtime_busy", False):
            log.debug("[Brain] runtime busy")
            return

        context.metadata["active_goal"] = goal

        self._runtime_busy = True

        try:

            result = self.process(goal, context)

            if getattr(result, "success", False):

                log.debug("[Brain] Goal completed")

                self.complete_goal()

        finally:

            self._runtime_busy = False


    def working_snapshot(self):
        return self.working_memory.get_snapshot() 


    # ----------------------------------------------------
    # Observer Event Processing
    # ----------------------------------------------------

    def process_event(self, event) -> None:
        """
        Entry point for asynchronous observer events.
        """

        try:

            log.info(
                "[Brain] Observer Event: %s",
                getattr(event, "title", "Unknown"),
            )

            # Working Memory
            self.working_memory.remember_event(event)

            # Memory 2.0 (M7/M9): feed the observer event into the unified
            # store as a WORKING record so the runtime consolidation pipeline
            # has input. Since M9 the unified store is authoritative, so this
            # is the single canonical memory write for observer events.
            memory_2_0 = getattr(self, "memory_2_0", None) or self.memory
            if memory_2_0 is not None:
                memory_2_0.remember_working_event(event)

            self._on_event_received(event)

        except Exception:

            log.exception(
                "Failed to process observer event."
            )

    def _on_event_received(
        self,
        event,
    ):

        decision = self.cognitive_evaluator.evaluate(
            event
        )

        self.attention.submit(
            decision,
            event,
        )

    def _trigger_reasoning(self):
        pass

    def _trigger_planner(self):
        pass

    def _notify_user(self):
        pass


    # ----------------------------------------------------------

    def _store_event(self, event) -> None:
        """
        Store observer event into working memory.

        Later this method will also:
        - episodic memory
        - reasoning
        - proactive planning
        """

        if hasattr(self, "working_memory"):

            self.working_memory.add(
                {
                    "type": "observer",
                    "source": getattr(event, "source", None),
                    "title": getattr(event, "title", ""),
                    "message": getattr(event, "message", ""),
                    "severity": getattr(event, "severity", ""),
                    "timestamp": getattr(event, "timestamp", None),
                    "payload": getattr(event, "payload", {}),
                }
            )