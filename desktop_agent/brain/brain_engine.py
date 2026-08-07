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
from .memory.manager import MemoryManager
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
from desktop_agent.brain.ai.router import AIRouter
from .executive.executive_controller import ExecutiveController
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
        print("\n========== BRAIN ENGINE ==========")
        print("WorkingMemory ID:", id(self.working_memory))
        print("=================================\n")

        # Runtime context

        self.context_manager = ContextManager()

        self.memory = (

            memory_manager

            if memory_manager

            else MemoryManager()

        )

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

        # TODO:
        # Executor pipeline is under migration.
        # Production execution is handled by Orchestrator.
        #
        # self.executor = Executor(
        #     tool_router=self.router
        # )

        self.cognitive_cycle = CognitiveCycle(self)

        self.semantic_parser = SemanticParser()

        self.ai_router = AIRouter()

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

        print("=" * 60)
        print("DecisionEngine instance:", self.decision)
        print("DecisionEngine class   :", self.decision.__class__)
        print("DecisionEngine module  :", self.decision.__class__.__module__)
        print("DecisionEngine file    :", self.decision.__class__.__dict__.get("__module__"))
        print("=" * 60)
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

            import traceback

            traceback.print_exc()

        return result

    def process(self, text: str, context=None):
        print("[Brain] process()")
        t0 = time.perf_counter()
        resolved_text = self._resolve_input(text)
        print(f"Resolve: {(time.perf_counter()-t0):.3f}s")
        print("[Brain] starting semantic parser")
        t1 = time.perf_counter()
        semantic_task = self._parse_semantics(
            resolved_text,
            context,
        )
        print("<<< PARSE RETURNED >>>")
        print(type(semantic_task))
        print(semantic_task)
        print("<<< ABOUT TO CALL MEMORY >>>")
        print(">>> BEFORE MEMORY RETRIEVAL")
        memory_result = self.memory_retrieval.resolve(
            resolved_text,
            self.working_memory,
        )
        print(">>> AFTER MEMORY RETRIEVAL")
        print(memory_result)

        if memory_result.handled:

            print("[Memory Retrieval] handled")

            return BrainResult(
                success=True,
                message=memory_result.response,
                metadata={
                    "source": memory_result.source,
                    "confidence": memory_result.confidence,
                },
            )
        self.brain_state.update_task(
            semantic_task
        )
        route = self.ai_router.route(semantic_task)

        print(f"[AI Router] Route = {route.name}")
        if route.name == "LLM":

            provider = self.ai_router.provider(
                semantic_task
            )

            print(
                f"[AI Router] Provider = {provider}"
            )
        print("[Brain] semantic parser finished")
        print("[Brain] starting think")
        brain_context = self.think(semantic_task)

        # ----------------------------------------------------
        # Knowledge vs Browser Decision
        # ----------------------------------------------------

        decision = self.knowledge_decision.decide(
            resolved_text
        )

        print("\n========== KNOWLEDGE DECISION ==========")
        print("Browser :", decision.use_browser)
        print("Knowledge:", decision.use_knowledge)
        print("Reason   :", decision.reason)
        print("========================================\n")

        brain_context.metadata["use_browser"] = (
            decision.use_browser
        )

        brain_context.metadata["use_knowledge"] = (
            decision.use_knowledge
        )
        print("[Brain] think finished")
        # Inject active goal into the cognitive context
        brain_context.metadata["active_goal"] = self.current_goal()
        print("[Brain] starting decision")
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
        print("[Brain] decision finished")
        print("========== SemanticTask ==========")
        print("Intent   :", semantic_task.intent)
        print("Metadata :", semantic_task.metadata)
        print("==================================")
        print(f"Semantic: {(time.perf_counter()-t1):.3f}s")

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
        print("[Brain] starting planner")
        plan = self.planner.create_plan(decision)
        print("[Brain] planner finished")
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
                },
            )

        # =====================================================
        # Executive
        # =====================================================

        print("[Brain] starting executive")

        request = self.executive.submit(plan)

        plan = request.metadata["plan"]

        print("[Brain] executive finished")

        # =====================================================
        # Execute
        # =====================================================

        t5 = time.perf_counter()

        print("[Brain] starting execute")

        result = self.orchestrator.execute(plan)

        print("[Brain] execute finished")

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

        print(f"Execute: {(time.perf_counter() - t5):.3f}s")
        print(f"TOTAL: {(time.perf_counter() - t0):.3f}s")

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

        print(

            "[Brain] Goal completed:",

            goal,

        )

        self.scheduler.complete()

        self.goals.complete()

        self.state.set_goal(None)

        if hasattr(self, "brain_state"):

            self.brain_state.update_goal(None)

    def fail_goal(self):

        goal = self.current_goal()

        if goal is None:

            return

        print(

            "[Brain] Goal failed:",

            goal,

        )

        self.goals.fail()

        self.state.set_goal(None)

    def cancel_goal(self):

        goal = self.current_goal()

        if goal is None:

            return

        print(

            "[Brain] Goal cancelled:",

            goal,

        )

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

        print("[Brain] perception updated")

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

        print("[Brain] tick()")

        self.world.update(
            self.perception.snapshot
        )

        context = self._build_runtime_context()

        self._current_context = context
        print("[Brain] context ready")

        if context is None:
            print("[Brain] context is None")
            return

        print("[Brain] running cognitive cycle")

        self.cognitive_cycle.run()

        print("[Brain] cognitive cycle finished")

        goal = self.current_goal()

        print("[Brain] goal =", goal)

        if goal is None:
            print("[Brain] no goal")
            return

        if getattr(self, "_runtime_busy", False):
            print("[Brain] runtime busy")
            return

        context.metadata["active_goal"] = goal

        self._runtime_busy = True

        try:

            result = self.process(goal, context)

            if getattr(result, "success", False):

                print("[Brain] Goal completed")

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

            # Episodic Memory
            self.memory.episodic.record(
                title=getattr(event, "title", ""),
                category="observer",
                description=getattr(event, "message", ""),
                importance=0.7,
                metadata={
                    "source": getattr(event, "source", None),
                    "severity": str(getattr(event, "severity", "")),
                    "payload": getattr(event, "payload", {}),
                },
            )

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