"""
MYRAA Application Container

Single composition root for the entire application.

Creates every long-lived singleton exactly once.
"""

from __future__ import annotations

from desktop_agent.brain.blackboard.blackboard import Blackboard
from desktop_agent.brain.decision.decision_engine import DecisionEngine
from desktop_agent.brain.execution_brain import ExecutionBrain
from desktop_agent.brain.planner.planner import Planner

from desktop_agent.brain.planner.execution.bootstrap import (
    ExecutionBootstrap,
)

from desktop_agent.brain.planner.execution.dispatcher import (
    Dispatcher,
)

from desktop_agent.brain.orchestrator.orchestrator import (
    Orchestrator,
)

from desktop_agent.brain.brain_engine import (
    BrainEngine,
)

from desktop_agent.desktop.vision.vision_manager import (
    VisionManager,
)

from desktop_agent.desktop.vision.screen_share import (
    ScreenShareEngine,
    get_screen_share_engine,
)

from desktop_agent.runtime.runtime_manager import (
    RuntimeManager,
)


class _SyncFallbackDispatcher:
    """Minimal sync dispatcher matching CommandDispatcher interface.

    Used when no external dispatcher is provided (tests/headless).
    Delegates to the ActionRegistry for tool lookup.
    """

    def __init__(self, registry=None):
        self._registry = registry

    def dispatch(self, req):
        """Sync dispatch matching CommandDispatcher.dispatch(ExecuteRequest) -> ExecuteResponse."""
        from desktop_agent.main import ExecuteRequest, ExecuteResponse
        from desktop_agent.registry import TOOLS

        tool_name = getattr(req, "tool", "") or ""
        args = getattr(req, "args", {}) or {}

        if tool_name in TOOLS:
            try:
                result = TOOLS[tool_name](**args)
                return ExecuteResponse(ok=True, tool=tool_name, result=result)
            except Exception as exc:
                return ExecuteResponse(ok=False, tool=tool_name, error=str(exc))
        return ExecuteResponse(ok=False, tool=tool_name, error=f"unknown tool: {tool_name}")


class ApplicationContainer:

    def __init__(self, dispatcher=None):

        self._external_dispatcher = dispatcher

        self._build()

    # --------------------------------------------------

    def _build(self):

        self.blackboard = Blackboard()

        from desktop_agent.brain.context_manager import ContextManager

        self.context_manager = ContextManager()

        self.planner = Planner(
            blackboard=self.blackboard,
        )

        self.decision = DecisionEngine()

        if self._external_dispatcher is not None:

            self.dispatcher = self._external_dispatcher

        else:
            # The Orchestrator expects a SYNC dispatcher with the
            # CommandDispatcher interface: dispatch(ExecuteRequest) -> ExecuteResponse.
            # The async Dispatcher (planner/execution/dispatcher.py) does NOT
            # match this interface and causes infinite retries if injected.
            # Use a sync fallback that delegates to the registry.
            try:
                from desktop_agent.main import CommandDispatcher
                self.dispatcher = CommandDispatcher()
            except Exception:
                # Fallback: create a minimal sync dispatcher
                from desktop_agent.brain.planner.execution.execution_bootstrap import ExecutionBootstrap
                registry = ExecutionBootstrap().build()
                self.dispatcher = _SyncFallbackDispatcher(registry)

        self.orchestrator = Orchestrator(
            self.dispatcher,
        )

        #
        # Memory 2.0 — UnifiedMemoryManager (M7/M9).
        #
        # The unified store is the SINGLE authoritative memory. It is created
        # here first and injected into BrainEngine (as `memory`, via the
        # legacy-shaped compatibility views) and RuntimeManager (periodic
        # consolidation) so every subsystem shares ONE instance.
        #

        from desktop_agent.brain.memory.unified_manager import UnifiedMemoryManager

        self.memory_2_0 = UnifiedMemoryManager()

        #
        # Single AI Manager authority (Full Integration).
        #
        # One container-owned AIManager is shared by BrainEngine, ExecutionBrain
        # and SuperBrain so there is exactly ONE routing/provider authority.
        #

        from desktop_agent.brain.ai.ai_manager import AIManager

        self.ai_manager = AIManager()

        self.brain_engine = BrainEngine(
            orchestrator=self.orchestrator,
            planner=self.planner,
            decision_engine=self.decision,
            memory_manager=self.memory_2_0,
            ai_manager=self.ai_manager,
        )
        self.brain_engine.memory_2_0 = self.memory_2_0

        self.vision = VisionManager()

        # Canonical screen-share engine (Phase 3.2)
        self.screen_share = get_screen_share_engine()

        self.runtime = RuntimeManager(
            brain=self.brain_engine,
            vision=self.vision,
            memory_2_0=self.memory_2_0,
            screen_share=self.screen_share,
        )

        #
        # Execution Brain
        #

        self.execution_brain = ExecutionBrain(

            dispatcher=self.dispatcher,

            planner=self.planner,

            orchestrator=self.orchestrator,

            decision_engine=self.decision,

            context_manager=self.context_manager,

            blackboard=self.blackboard,

            ai_manager=self.ai_manager,

        )

        #
        # EPIC-BRAIN Phase 2: Super-Brain (coordination layer).
        #
        # Reuses existing singletons — never a second implementation.
        #

        from desktop_agent.brain.verification import VerificationManager
        from desktop_agent.brain.failure_containment import RecoveryEngine

        from desktop_agent.brain.super_brain import SuperBrain
        from desktop_agent.brain.super_brain.project_manager import ProjectManager

        self.super_brain = SuperBrain(
            ai_manager=self.ai_manager,
            orchestrator=self.orchestrator,
            verification=VerificationManager(),
            recovery=RecoveryEngine(),
            memory=self.brain_engine.memory,
            world_model=self.brain_engine.world,
            blackboard=self.blackboard,
            metacognition=self.brain_engine.metacognition,
            memory_2_0=self.memory_2_0,
        )

        self.project_manager = ProjectManager(memory_2_0=self.memory_2_0)

        #
        # Phase U: Canonical AssistantRuntime (ONE MYRAA)
        #
        # The single authoritative request pipeline. Every input modality
        # (text /brain, voice loop, future vision/file entries) converges
        # here: one task identity, one lifecycle, one EventBus event stream.
        #

        from desktop_agent.brain.assistant_runtime import AssistantRuntime

        self.assistant_runtime = AssistantRuntime(
            super_brain=self.super_brain,
            event_bus=getattr(self.blackboard, "events", None),
        )

        #
        # Phase B: Autonomy Controller
        #
        # Coordinator for long-running autonomous goals. Wraps SuperBrain,
        # adds state machine, loop guards, checkpoint persistence, control API.
        #

        from desktop_agent.brain.super_brain.autonomy_controller import (
            AutonomyController,
        )
        from desktop_agent.brain.super_brain.experience import ExperienceEngine

        self.autonomy_controller = AutonomyController(
            super_brain=self.super_brain,
            memory_2_0=self.memory_2_0,
            experience_engine=self.super_brain.experience,
            project_manager=self.project_manager,
        )

        #
        # Phase C: Continuous Vision Controller
        #
        # Wraps VisionManager with frame health, stale detection,
        # structured visual state, and ContextFusion/SuperBrain integration.
        #

        from desktop_agent.brain.super_brain.continuous_vision import (
            ContinuousVisionController,
        )

        self.continuous_vision = ContinuousVisionController(
            screen_share=self.screen_share,
            memory_2_0=self.memory_2_0,
        )

        # ------------------------------------------------------------------
        # Continuous Voice Loop (Phase C)
        # ------------------------------------------------------------------
        from desktop_agent.speech.continuous_voice_loop import (
            ContinuousVoiceLoop,
        )

        self.continuous_voice_loop = ContinuousVoiceLoop()

        # Phase U: VOICE convergence — voice turns flow through the SAME
        # AssistantRuntime as text (no separate voice decision logic).
        def _voice_execute(transcript):
            from desktop_agent.brain.assistant_runtime import (
                AssistantRequest,
                InputType,
            )

            vreq = AssistantRequest(
                user_input=transcript,
                input_type=InputType.VOICE,
                source="continuous_voice_loop",
                session_id="voice",
            )
            vresp = self.assistant_runtime.handle(vreq)
            return {
                "ok": bool(vresp.ok),
                "message": vresp.message,
                "decision": vresp.decision,
                "task_id": vresp.task_id,
                "request_id": vresp.request_id,
            }

        self.continuous_voice_loop.set_execute_callback(_voice_execute)

        # ------------------------------------------------------------------
        # Phase D: Trading Intelligence Engine + Groww Advisor
        # ------------------------------------------------------------------
        from desktop_agent.finance.trading.engine import TradingIntelligenceEngine
        from desktop_agent.finance.trading.capability import TradingCapabilityEngine

        self.trading_engine = TradingIntelligenceEngine()
        self.trading_capability = TradingCapabilityEngine(
            trading_engine=self.trading_engine,
        )
        self.super_brain.register_engine(self.trading_capability)

        # Phase U: multi-agent skills reachable through the ONE pipeline
        # (B19 engine seam — specialists stay internal to MYRAA).
        from desktop_agent.skills.capability_adapter import MultiAgentCapabilityEngine

        self.super_brain.register_engine(MultiAgentCapabilityEngine())

        # Phase D Part 2: Groww Professional Trading Advisor (Browser-First)
        from desktop_agent.finance.trading.broker.groww.browser_advisor import GrowwBrowserAdvisor

        self.groww_advisor = GrowwBrowserAdvisor(
            trading_engine=self.trading_engine,
            universal_controller=None,  # Will be set below after creating universal_controller
        )

        # ------------------------------------------------------------------
        # Universal Controller
        # ------------------------------------------------------------------
        from desktop_agent.universal_control.universal_controller import UniversalController
        from desktop_agent.registry import dispatch as registry_dispatch
        from desktop_agent.registry import STATE

        self.universal_controller = UniversalController(
            vision_controller=self.continuous_vision,
            tool_executor=registry_dispatch
        )
        # Share the ONE vision-based automation engine with tool handlers so
        # browser interaction tools (desktopBrowserClick/Type/Scroll) can
        # consume it. Execution still flows through registry_dispatch, so every
        # UC-driven action passes PermissionManager and returns to F7 on error.
        STATE.universal_controller = self.universal_controller
        # Update the groww advisor with the universal controller
        self.groww_advisor.universal_controller = self.universal_controller

        # Phase D Final: Alerts + Automation
        from desktop_agent.finance.trading.alerts.engine import AlertEngine
        from desktop_agent.finance.trading.automation.daily_close_scheduler import DailyCloseScheduler

        self.alert_engine = AlertEngine()
        self.daily_close_scheduler = DailyCloseScheduler(
            groww_advisor=self.groww_advisor,
            trading_engine=self.trading_engine,
            alert_engine=self.alert_engine,
        )

        # ------------------------------------------------------------------
        # Phase F: Neural Intelligence Engine + Specialists
        # ------------------------------------------------------------------
        from desktop_agent.neural_engine.engine import NeuralEngine
        from desktop_agent.neural_engine.specialists.vision_specialist import VisionSpecialist
        from desktop_agent.neural_engine.specialists.trading_specialist import TradingSpecialist
        from desktop_agent.neural_engine.specialists.voice_specialist import VoiceSpecialist
        from desktop_agent.neural_engine.specialists.prediction_specialist import PredictionSpecialist
        from desktop_agent.neural_engine.specialists.personalization_specialist import PersonalizationSpecialist
        from desktop_agent.neural_engine.specialists.multimodal_specialist import MultimodalSpecialist

        self.neural_engine = NeuralEngine()

        # Register all specialist models so the engine has real inference capacity
        _vision_spec = VisionSpecialist.SPEC
        _vision = VisionSpecialist(ai_manager=self.ai_manager)
        self.neural_engine.register_model(_vision_spec, _vision.inference, _vision.inference)

        _trading_spec = TradingSpecialist.SPEC
        _trading = TradingSpecialist(trading_engine=self.trading_engine)
        self.neural_engine.register_model(_trading_spec, _trading.inference, _trading.inference)

        _voice_spec = VoiceSpecialist.SPEC
        _voice = VoiceSpecialist()
        self.neural_engine.register_model(_voice_spec, _voice.inference, _voice.inference)

        _prediction_spec = PredictionSpecialist.SPEC
        _prediction = PredictionSpecialist()
        self.neural_engine.register_model(_prediction_spec, _prediction.inference, _prediction.inference)

        _personalization_spec = PersonalizationSpecialist.SPEC
        _personalization = PersonalizationSpecialist(memory_manager=self.memory_2_0)
        self.neural_engine.register_model(_personalization_spec, _personalization.inference, _personalization.inference)

        _multimodal_spec = MultimodalSpecialist.SPEC
        _multimodal = MultimodalSpecialist()
        self.neural_engine.register_model(_multimodal_spec, _multimodal.inference, _multimodal.inference)

        # ------------------------------------------------------------------
        # Phase G: Self-Healing + Self-Improvement
        # ------------------------------------------------------------------
        from desktop_agent.self_healing.manager import SelfHealingManager
        from desktop_agent.self_healing.diagnostics import DiagnosticResult, HealthStatus

        self.self_healing = SelfHealingManager()

        # Wire real diagnostic checks for core subsystems
        import time as _time

        def _check_brain():
            ok = self.brain_engine is not None
            return DiagnosticResult(
                component="brain_engine",
                status=HealthStatus.HEALTHY if ok else HealthStatus.FAILING,
                timestamp=_time.time(),
                reason="BrainEngine initialized" if ok else "BrainEngine missing",
                confidence=1.0,
            )

        def _check_memory():
            ok = self.memory_2_0 is not None
            return DiagnosticResult(
                component="memory",
                status=HealthStatus.HEALTHY if ok else HealthStatus.FAILING,
                timestamp=_time.time(),
                reason="UnifiedMemoryManager initialized" if ok else "Memory missing",
                confidence=1.0,
            )

        def _check_vision():
            ok = self.vision is not None
            return DiagnosticResult(
                component="vision",
                status=HealthStatus.HEALTHY if ok else HealthStatus.UNAVAILABLE,
                timestamp=_time.time(),
                reason="VisionManager initialized" if ok else "VisionManager missing",
                confidence=1.0,
            )

        def _check_screen_share():
            ok = self.screen_share is not None and self.screen_share.is_active
            return DiagnosticResult(
                component="screen_share",
                status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
                timestamp=_time.time(),
                reason="ScreenShareEngine active" if ok else "ScreenShareEngine not active",
                confidence=1.0,
            )

        def _check_neural():
            n_models = len(self.neural_engine._models)
            return DiagnosticResult(
                component="neural_engine",
                status=HealthStatus.HEALTHY if n_models > 0 else HealthStatus.DEGRADED,
                timestamp=_time.time(),
                reason=f"{n_models} specialists registered" if n_models else "No specialists registered",
                confidence=1.0,
                recommended_action="" if n_models else "Register specialist models",
            )

        def _check_trading():
            ok = self.trading_engine is not None
            return DiagnosticResult(
                component="trading_engine",
                status=HealthStatus.HEALTHY if ok else HealthStatus.UNAVAILABLE,
                timestamp=_time.time(),
                reason="TradingIntelligenceEngine initialized" if ok else "Not initialized",
                confidence=1.0,
            )

        def _check_self_healing():
            ok = self.self_healing is not None
            return DiagnosticResult(
                component="self_healing",
                status=HealthStatus.HEALTHY if ok else HealthStatus.FAILING,
                timestamp=_time.time(),
                reason="SelfHealingManager initialized" if ok else "Not initialized",
                confidence=1.0,
            )

        _diag = self.self_healing.diagnostics
        _diag.register_check("brain_engine", _check_brain)
        _diag.register_check("memory", _check_memory)
        _diag.register_check("vision", _check_vision)
        _diag.register_check("screen_share", _check_screen_share)
        _diag.register_check("neural_engine", _check_neural)
        _diag.register_check("trading_engine", _check_trading)
        _diag.register_check("self_healing", _check_self_healing)
        _diag.set_check_interval(120.0)
        _diag.enable()