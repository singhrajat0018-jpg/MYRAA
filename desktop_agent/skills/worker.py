"""Worker — bounded capability executor for MYRAA.

Workers execute tasks with:
- scoped context
- scoped tools
- scoped permissions
- resource limits
- timeout
- cancellation
- retry budget

Workers report structured results and never independently redefine user goals.
"""

from __future__ import annotations

import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class WorkerStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    WAITING = "waiting"


@dataclass
class WorkerContract:
    """Canonical input contract for a worker.

    Defines: input, context, task, permissions, tools, constraints, deadline.
    """
    task_id: str
    task_description: str
    skill_id: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)
    allowed_permissions: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    deadline_seconds: float = 30.0
    retry_budget: int = 2
    priority: int = 5  # 1=highest, 10=lowest
    timeout_seconds: float = 60.0
    depends_on: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "skill_id": self.skill_id,
            "input_data": self.input_data,
            "context": self.context,
            "allowed_tools": self.allowed_tools,
            "allowed_permissions": self.allowed_permissions,
            "constraints": self.constraints,
            "deadline_seconds": self.deadline_seconds,
            "retry_budget": self.retry_budget,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "depends_on": self.depends_on,
        }


@dataclass
class WorkerResult:
    """Canonical output from a worker.

    Includes: result, status, evidence, confidence, artifacts, errors, latency, side_effects.
    """
    status: WorkerStatus
    task_id: str
    skill_id: str
    result: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    side_effects: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def is_success(self) -> bool:
        return self.status == WorkerStatus.COMPLETED and len(self.errors) == 0

    @property
    def is_failure(self) -> bool:
        return self.status in (WorkerStatus.FAILED, WorkerStatus.TIMED_OUT)

    @property
    def is_retryable(self) -> bool:
        return self.status == WorkerStatus.FAILED and len(self.errors) < 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "task_id": self.task_id,
            "skill_id": self.skill_id,
            "result": self.result,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "warnings": self.warnings,
            "latency_ms": self.latency_ms,
            "side_effects": self.side_effects,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class Worker(ABC):
    """Base class for bounded capability executors.

    Workers are NOT brains. They are scoped executors that follow contracts.
    """

    def __init__(
        self,
        worker_id: str,
        skill_id: str,
        allowed_tools: Optional[List[str]] = None,
        allowed_permissions: Optional[List[str]] = None,
        max_retries: int = 2,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.worker_id = worker_id
        self.skill_id = skill_id
        self.allowed_tools = set(allowed_tools or [])
        self.allowed_permissions = set(allowed_permissions or [])
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.status = WorkerStatus.IDLE
        self._cancel_event = threading.Event()
        self._result: Optional[WorkerResult] = None

    @abstractmethod
    def execute(self, contract: WorkerContract) -> WorkerResult:
        """Execute the task defined in the contract.

        Must return a WorkerResult. Override in subclasses.
        """
        ...

    def can_handle(self, contract: WorkerContract) -> bool:
        """Check if this worker can handle the given contract."""
        if contract.skill_id != self.skill_id:
            return False
        for tool in contract.allowed_tools:
            if tool not in self.allowed_tools:
                return False
        return True

    def cancel(self) -> bool:
        """Request cancellation."""
        self._cancel_event.set()
        self.status = WorkerStatus.CANCELLED
        return True

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def reset(self) -> None:
        """Reset worker for reuse."""
        self.status = WorkerStatus.IDLE
        self._cancel_event.clear()
        self._result = None

    def _make_result(
        self,
        status: WorkerStatus,
        result: Dict[str, Any] = None,
        evidence: List[str] = None,
        confidence: float = 0.5,
        errors: List[str] = None,
        warnings: List[str] = None,
        latency_ms: float = 0.0,
    ) -> WorkerResult:
        return WorkerResult(
            status=status,
            task_id="",
            skill_id=self.skill_id,
            result=result or {},
            evidence=evidence or [],
            confidence=confidence,
            errors=errors or [],
            warnings=warnings or [],
            latency_ms=latency_ms,
        )
