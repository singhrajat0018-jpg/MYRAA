from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class EscalationReason(Enum):
    HIGH_UNCERTAINTY = "high_uncertainty"
    ARCHITECTURE_AMBIGUITY = "architecture_ambiguity"
    SECURITY_AFFECTED = "security_affected"
    MAJOR_BEHAVIOR_CHANGE = "major_behavior_change"
    FINANCIAL_BEHAVIOR = "financial_behavior"
    DESTRUCTIVE_ACTION = "destructive_action"
    UNCERTAIN_DATA = "uncertain_data"
    CONFLICTING_DIAGNOSTICS = "conflicting_diagnostics"
    CANDIDATE_NOT_CLEARLY_BETTER = "candidate_not_clearly_better"
    REPEATED_FAILURE = "repeated_failure"
    REsource_EXHAUSTION = "resource_exhaustion"


_CRITICAL_REASONS: frozenset[EscalationReason] = frozenset(
    {
        EscalationReason.SECURITY_AFFECTED,
        EscalationReason.FINANCIAL_BEHAVIOR,
        EscalationReason.DESTRUCTIVE_ACTION,
        EscalationReason.MAJOR_BEHAVIOR_CHANGE,
    }
)


@dataclass
class EscalationRequest:
    request_id: str
    reason: EscalationReason
    component: str
    description: str
    evidence: list[dict] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    recommended_option: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: Optional[str] = None


class HumanEscalation:
    _instance: HumanEscalation | None = None
    _lock_class = threading.Lock()
    _MAX_HISTORY = 50

    def __new__(cls) -> HumanEscalation:
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_fields()
            return cls._instance

    def _init_fields(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, EscalationRequest] = {}
        self._history: list[EscalationRequest] = []

    def escalate(
        self,
        reason: EscalationReason,
        component: str,
        description: str,
        evidence: list[dict] | None = None,
        options: list[str] | None = None,
        recommended: str | None = None,
    ) -> EscalationRequest:
        req = EscalationRequest(
            request_id=uuid.uuid4().hex[:12],
            reason=reason,
            component=component,
            description=description,
            evidence=evidence or [],
            options=options or [],
            recommended_option=recommended,
        )
        with self._lock:
            self._pending[req.request_id] = req
        logger.warning(
            "Escalation created: %s [%s] component=%s",
            req.request_id,
            reason.value,
            component,
        )
        return req

    def resolve(self, request_id: str, resolution: str) -> bool:
        with self._lock:
            req = self._pending.pop(request_id, None)
            if req is None:
                return False
            req.resolved = True
            req.resolution = resolution
            self._history.append(req)
            if len(self._history) > self._MAX_HISTORY:
                self._history = self._history[-self._MAX_HISTORY :]
        logger.info("Escalation %s resolved: %s", request_id, resolution)
        return True

    def get_pending(self) -> list[EscalationRequest]:
        with self._lock:
            return list(self._pending.values())

    def get_history(self, limit: int = 20) -> list[EscalationRequest]:
        with self._lock:
            return list(self._history[-limit:])

    def should_escalate(self, reason: EscalationReason, confidence: float) -> bool:
        if confidence < 0.5:
            return True
        if reason in _CRITICAL_REASONS:
            return True
        return False

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock_class:
            if cls._instance is not None:
                cls._instance._pending.clear()
                cls._instance._history.clear()
                cls._instance = None
