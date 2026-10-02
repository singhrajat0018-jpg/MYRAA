"""MYRAA Assistant Runtime — THE canonical entry point for every user request.

Phase U ("ONE MYRAA") unification:

    USER (text | voice | vision | file | multimodal)
        -> AssistantRuntime.handle(AssistantRequest)
            -> task identity (ONE task_id for the whole lifecycle)
            -> EventBus lifecycle events (task.created/classified/started/...)
            -> TaskRouter (front-door classifier, fast path preserved)
            -> SuperBrain (planning + capability orchestration + closed loop)
            -> canonical error normalization (F6 taxonomy)
            -> telemetry
        -> AssistantResponse

This is a COORDINATION facade, not a second brain. It owns:
- the canonical request contract (AssistantRequest)
- ONE task identity per user request (created once, referenced everywhere)
- ONE lifecycle state machine (CREATED -> ... -> COMPLETED/FAILED/CANCELLED)
- correlation: every event carries task_id + request_id + source

It does NOT replace SuperBrain, ExecutionBrain, PermissionManager,
SafetyManager, VerificationManager, Memory 2.0 or the EventBus — those remain
the canonical authorities for their domains.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ============================================================
# Canonical input types
# ============================================================

class InputType(str, enum.Enum):
    """Canonical modality of a user request."""

    TEXT = "text"
    VOICE = "voice"
    VISION = "vision"
    IMAGE = "image"
    FILE = "file"
    DOCUMENT = "document"
    MULTIMODAL = "multimodal"


# ============================================================
# Canonical task lifecycle states
# ============================================================

class TaskState(str, enum.Enum):
    CREATED = "CREATED"
    CLASSIFIED = "CLASSIFIED"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def terminal(self) -> bool:
        return self in (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        )


# ============================================================
# Canonical request contract
# ============================================================

@dataclass
class AssistantRequest:
    """The ONE request object every input modality converges into."""

    user_input: str
    input_type: InputType = InputType.TEXT
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    task_id: Optional[str] = None  # set by runtime if absent
    context: Dict[str, Any] = field(default_factory=dict)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "unknown"          # e.g. "api/chat", "local_fast", "voice_loop"
    priority: int = 5                # 1 (highest) .. 9 (lowest)
    deadline_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def normalized_input(self) -> str:
        return (self.user_input or "").strip()


# ============================================================
# Canonical response contract
# ============================================================

@dataclass
class AssistantResponse:
    """The ONE response object the runtime returns to any caller."""

    ok: bool
    task_id: str
    request_id: str
    message: str = ""
    decision: str = ""
    capability: str = ""
    route: str = ""
    task_type: str = ""
    duration_ms: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None   # canonical F6 error payload
    cancelled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "message": self.message,
            "decision": self.decision,
            "capability": self.capability,
            "route": self.route,
            "task_type": self.task_type,
            "duration_ms": round(self.duration_ms, 2),
            "result": self.result,
            "error": self.error,
            "cancelled": self.cancelled,
        }


# ============================================================
# Internal task record
# ============================================================

@dataclass
class _TaskRecord:
    task_id: str
    request_id: str
    session_id: Optional[str]
    source: str
    input_type: InputType
    user_input: str
    state: TaskState = TaskState.CREATED
    task_type: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancel_requested: bool = False
    error: Optional[Dict[str, Any]] = None

    def touch(self, state: Optional[TaskState] = None) -> None:
        if state is not None:
            self.state = state
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "source": self.source,
            "input_type": self.input_type.value,
            "user_input": self.user_input[:200],
            "state": self.state.value,
            "task_type": self.task_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "cancel_requested": self.cancel_requested,
            "error": self.error,
        }


# ============================================================
# AssistantRuntime
# ============================================================

class AssistantRuntime:
    """Canonical MYRAA request runtime.

    Parameters are the EXISTING canonical authorities; nothing here is a new
    implementation of their domain logic:

      super_brain : SuperBrain (planning/capability/closed-loop authority)
      event_bus   : Blackboard.events (the ONE EventBus)
      task_router : TaskRouter (front-door classifier) [constructed lazily]
      telemetry   : metrics collector [module global, imported lazily]
    """

    # Bounded history of finished tasks (prevents unbounded growth).
    MAX_HISTORY = 200

    def __init__(
        self,
        super_brain: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        task_router: Optional[Any] = None,
    ) -> None:
        self._super_brain = super_brain
        self._event_bus = event_bus
        self._task_router = task_router
        self._lock = threading.RLock()
        self._active: Dict[str, _TaskRecord] = {}
        self._history: List[_TaskRecord] = []

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def handle(self, request: AssistantRequest) -> AssistantResponse:
        """Process ONE user request through the unified pipeline."""
        started = time.perf_counter()

        text = request.normalized_input()
        if not text:
            resp = AssistantResponse(
                ok=False,
                task_id=request.task_id or "-",
                request_id=request.request_id or "-",
                error={
                    "category": "invalid_request",
                    "severity": "low",
                    "message": "empty user_input",
                    "recoverable": True,
                    "source": "assistant_runtime",
                },
            )
            return resp

        task = self._register(request, text)
        rid = task.request_id
        tid = task.task_id

        try:
            # ── CLASSIFY (front door: TaskRouter is THE classifier) ──
            routing = self._classify(text)
            task.touch(TaskState.CLASSIFIED)
            task.task_type = routing.task_type.name
            self._emit(
                "task.classified",
                task=task,
                task_type=routing.task_type.name,
                response_mode=routing.response_mode.name,
                tools_required=routing.tools_required,
                freshness_required=routing.freshness_required,
                confidence=routing.confidence,
            )

            # ── Cancellation checkpoint ──
            if self._cancel_requested(tid):
                return self._finish_cancelled(task, started)

            # ── FAST PATH (simple requests stay extremely fast) ──
            # CONVERSATION, DIRECT_KNOWLEDGE, and LOCAL_REASONING with
            # no tools required all bypass the full SuperBrain pipeline.
            # This is a safety invariant: if tools_required is False,
            # no tool execution may occur.
            from desktop_agent.brain.router.task_router import TaskType

            _fast_types = {
                TaskType.DIRECT_KNOWLEDGE,
                TaskType.CONVERSATION,
                TaskType.LOCAL_REASONING,
            }
            if routing.task_type in _fast_types and not routing.tools_required:
                # Phase 29.9 P0 FIX — the FAST_PATH must NEVER return
                # success=True with an empty user-visible message.
                # Generate a real response through the same Ollama provider
                # used by /brain/stream. If the model is unavailable or
                # returns empty, return an EXPLICIT structured error instead
                # of a silent blank success.
                message = ""
                try:
                    from desktop_agent.brain.ai.providers.ollama_provider import OllamaProvider

                    provider = OllamaProvider()
                    if not provider.available():
                        raise RuntimeError("Ollama is not available")
                    system_prompt = (
                        "You are MYRAA, a helpful desktop AI assistant. "
                        "Be brief and natural. One or two sentences max. "
                        "Answer the user directly with no preamble."
                    )
                    chunks: list[str] = []
                    for chunk in provider.stream_generate(  # placeholder — fixed below
                        system_prompt,
                        text,
                        is_voice=(request.input_type == InputType.VOICE),
                        intent=routing.task_type.name,
                    ):
                        if chunk:
                            chunks.append(chunk)
                    message = "".join(chunks).strip()
                    if not message:
                        raise RuntimeError("model returned empty response")
                except Exception as exc:  # noqa: BLE001 — explicit failure path
                    err = self._normalize_error(exc, request_id=rid, task_id=tid)
                    task.touch(TaskState.FAILED)
                    task.error = err
                    self._telemetry_record(
                        request_id=rid,
                        component="assistant_runtime",
                        route="fast_path",
                        status="error",
                        error_category=str(err.get("category", "")),
                        latency_ms=(time.perf_counter() - started) * 1000,
                    )
                    self._emit("task.failed", task=task, reason=str(exc))
                    return AssistantResponse(
                        ok=False,
                        task_id=tid,
                        request_id=rid,
                        message="",
                        decision="ERROR",
                        route="FAST_PATH",
                        task_type=routing.task_type.name,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        error=err,
                    )

                latency_ms = (time.perf_counter() - started) * 1000
                self._telemetry_record(
                    request_id=rid,
                    component="assistant_runtime",
                    route="fast_path",
                    status="ok",
                    latency_ms=latency_ms,
                )

                result = {
                    "success": True,
                    "message": message,
                    "decision": "FAST_ANSWER",
                    "capability": routing.task_type.name,
                    "metadata": {
                        "brain": "MYRAA",
                        "version": "MCE v2",
                        "route": "TASK_ROUTER_FAST",
                        "request_id": rid,
                        "task_id": tid,
                        "input_type": request.input_type.value,
                        "source": task.source,
                        "task_type": routing.task_type.name,
                        "response_mode": routing.response_mode.name,
                        "tools_required": routing.tools_required,
                        "freshness_required": routing.freshness_required,
                        "confidence": routing.confidence,
                        "routing_reason": routing.reasoning,
                        "routing_latency_ms": routing.estimated_latency_ms,
                    },
                }
                task.touch(TaskState.COMPLETED)
                self._emit("task.completed", task=task, decision="FAST_ANSWER")
                return AssistantResponse(
                    ok=True,
                    task_id=tid,
                    request_id=rid,
                    message=message,
                    decision="FAST_ANSWER",
                    capability=routing.task_type.name,
                    route="TASK_ROUTER_FAST",
                    task_type=routing.task_type.name,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    result=result,
                )

            # ── Cancellation checkpoint before heavy work ──
            if self._cancel_requested(tid):
                return self._finish_cancelled(task, started)

            # ── FULL PIPELINE (SuperBrain: plan -> execute -> verify) ──
            task.touch(TaskState.RUNNING)
            self._emit("task.started", task=task)

            sb_result = self._super_brain.process(
                user_request=text,
                request_id=rid,
                route=None,
            )

            inner_meta = {
                "brain": "MYRAA",
                "version": "MCE v2",
                "route": "SUPER_BRAIN",
                "request_id": rid,
                "task_id": tid,
                "input_type": request.input_type.value,
                "source": task.source,
                "execution": (
                    sb_result.execution.to_dict()
                    if hasattr(sb_result.execution, "to_dict")
                    else {}
                ),
            }

            task.touch(TaskState.COMPLETED if sb_result.success else TaskState.FAILED)
            self._telemetry_record(
                request_id=rid,
                component="assistant_runtime",
                route="super_brain",
                status="ok" if sb_result.success else "error",
                latency_ms=(time.perf_counter() - started) * 1000,
            )

            if sb_result.success:
                self._emit("task.completed", task=task, decision=sb_result.decision)
            else:
                self._emit("task.failed", task=task, reason=sb_result.message)

            return AssistantResponse(
                ok=bool(sb_result.success),
                task_id=tid,
                request_id=rid,
                message=sb_result.message,
                decision=sb_result.decision,
                capability=sb_result.capability,
                route="SUPER_BRAIN",
                task_type=task.task_type,
                duration_ms=(time.perf_counter() - started) * 1000,
                result={
                    "success": bool(sb_result.success),
                    "message": sb_result.message,
                    "decision": sb_result.decision,
                    "capability": sb_result.capability,
                    "metadata": inner_meta,
                },
            )

        except Exception as exc:  # noqa: BLE001 — normalize ALL failures
            log.exception("AssistantRuntime task %s failed", tid)
            err = self._normalize_error(exc, request_id=rid, task_id=tid)
            task.touch(TaskState.FAILED)
            task.error = err
            self._telemetry_record(
                request_id=rid,
                component="assistant_runtime",
                route="assistant_runtime",
                status="error",
                error_category=str(err.get("category", "")),
                latency_ms=(time.perf_counter() - started) * 1000,
            )
            self._emit("task.failed", task=task, reason=str(exc))
            return AssistantResponse(
                ok=False,
                task_id=tid,
                request_id=rid,
                message="",
                decision="ERROR",
                route="ASSISTANT_RUNTIME",
                task_type=task.task_type,
                duration_ms=(time.perf_counter() - started) * 1000,
                error=err,
            )

        finally:
            self._retire(task)

    # -- lifecycle introspection / control ------------------------

    def status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._active.get(task_id)
            if record is None:
                for rec in reversed(self._history):
                    if rec.task_id == task_id:
                        record = rec
                        break
            return record.to_dict() if record else None

    def active_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [rec.to_dict() for rec in self._active.values()]

    def cancel(self, task_id: str) -> Dict[str, Any]:
        """Request cooperative cancellation of a task.

        The flag is honored at pipeline checkpoints. A task already inside an
        uninterruptible tool call finishes that call, then stops.
        """
        with self._lock:
            record = self._active.get(task_id)
            if record is None:
                return {"ok": False, "error": f"Unknown or finished task '{task_id}'"}
            if record.state.terminal:
                return {"ok": False, "error": f"Task '{task_id}' already {record.state.value}"}
            record.cancel_requested = True
            record.touch()
        self._emit("task.cancel_requested", task=record)
        return {"ok": True, "task_id": task_id, "state": record.state.value}

    # ------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------

    def _register(self, request: AssistantRequest, text: str) -> _TaskRecord:
        tid = request.task_id or f"task-{uuid.uuid4().hex[:12]}"
        rid = request.request_id or tid
        record = _TaskRecord(
            task_id=tid,
            request_id=rid,
            session_id=request.session_id,
            source=request.source,
            input_type=request.input_type,
            user_input=text,
        )
        with self._lock:
            self._active[tid] = record
        self._emit("task.created", task=record)
        return record

    def _classify(self, text: str) -> Any:
        if self._task_router is None:
            from desktop_agent.brain.router.task_router import TaskRouter

            self._task_router = TaskRouter()
        return self._task_router.route(text)

    def _cancel_requested(self, task_id: str) -> bool:
        with self._lock:
            record = self._active.get(task_id)
            return bool(record and record.cancel_requested)

    def _finish_cancelled(self, task: _TaskRecord, started: float) -> AssistantResponse:
        task.touch(TaskState.CANCELLED)
        self._emit("task.cancelled", task=task)
        return AssistantResponse(
            ok=False,
            task_id=task.task_id,
            request_id=task.request_id,
            decision="CANCELLED",
            route="ASSISTANT_RUNTIME",
            task_type=task.task_type,
            cancelled=True,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    def _retire(self, task: _TaskRecord) -> None:
        with self._lock:
            self._active.pop(task.task_id, None)
            self._history.append(task)
            if len(self._history) > self.MAX_HISTORY:
                self._history = self._history[-self.MAX_HISTORY // 2:]

    def _emit(self, event: str, task: _TaskRecord, **payload: Any) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(
                event,
                task_id=task.task_id,
                request_id=task.request_id,
                session_id=task.session_id,
                source=task.source,
                input_type=task.input_type.value,
                timestamp=time.time(),
                **payload,
            )
        except Exception:  # noqa: BLE001 — events must never break tasks
            log.exception("EventBus publish failed for %s", event)

    @staticmethod
    def _telemetry_record(**kwargs: Any) -> None:
        try:
            from desktop_agent.brain.metrics import telemetry

            telemetry.record(**kwargs)
        except Exception:  # noqa: BLE001
            log.debug("telemetry record failed", exc_info=True)

    @staticmethod
    def _normalize_error(
        exc: Exception,
        request_id: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """Normalize ANY subsystem failure into the canonical F6 contract."""
        try:
            from desktop_agent.brain.error_taxonomy import classify_exception

            return (
                classify_exception(exc, tool="brain")
                .with_correlation(
                    request_id=request_id,
                    task_id=task_id,
                    component="assistant_runtime",
                )
                .to_dict()
            )
        except Exception:  # noqa: BLE001 — even error normalization can fail
            return {
                "category": "internal_error",
                "severity": "high",
                "message": str(exc),
                "recoverable": False,
                "source": "assistant_runtime",
                "request_id": request_id,
                "task_id": task_id,
                "timestamp": time.time(),
            }
