from __future__ import annotations

"""Self-Diagnostics Engine for MYRAA subsystem health monitoring.

Provides periodic or on-demand health checks across registered subsystems,
tracks per-component health history, and surfaces an overall status summary.
All checks are wrapped so a failing check never crashes the engine.
"""

import logging
import threading
import time
from collections import deque
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    UNAVAILABLE = "unavailable"
    CORRUPTED = "corrupted"
    UNKNOWN = "unknown"


class DiagnosticResult:
    """Result of a single diagnostic check."""

    __slots__ = (
        "component", "status", "timestamp", "reason",
        "evidence", "confidence", "recommended_action",
    )

    def __init__(
        self,
        component: str,
        status: HealthStatus,
        timestamp: float,
        reason: str,
        evidence: dict[str, Any] | None = None,
        confidence: float = 0.0,
        recommended_action: str = "",
    ) -> None:
        self.component = component
        self.status = status
        self.timestamp = timestamp
        self.reason = reason
        self.evidence = evidence if evidence is not None else {}
        self.confidence = max(0.0, min(1.0, confidence))
        self.recommended_action = recommended_action

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "evidence": dict(self.evidence),
            "confidence": self.confidence,
            "recommended_action": self.recommended_action,
        }

    def __repr__(self) -> str:
        return (
            f"DiagnosticResult(component={self.component!r}, "
            f"status={self.status.value}, confidence={self.confidence})"
        )


class SubsystemHealth:
    """Tracks health state and history for a single subsystem."""

    __slots__ = (
        "name", "current_status", "last_check", "history",
        "consecutive_failures", "last_transition",
    )

    def __init__(self, name: str) -> None:
        self.name = name
        self.current_status: HealthStatus = HealthStatus.UNKNOWN
        self.last_check: float = 0.0
        self.history: deque[DiagnosticResult] = deque(maxlen=100)
        self.consecutive_failures: int = 0
        self.last_transition: float = 0.0

    def record(self, result: DiagnosticResult) -> None:
        """Record a diagnostic result and update internal counters."""
        now = result.timestamp
        self.last_check = now

        if result.status != self.current_status:
            self.last_transition = now
            self.current_status = result.status

        self.history.append(result)

        if result.status in (HealthStatus.HEALTHY, HealthStatus.UNKNOWN):
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

    @property
    def is_healable(self) -> bool:
        """True when consecutive failures >= 2 and status is not HEALTHY or CORRUPTED."""
        return (
            self.consecutive_failures >= 2
            and self.current_status not in (HealthStatus.HEALTHY, HealthStatus.CORRUPTED)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "current_status": self.current_status.value,
            "last_check": self.last_check,
            "consecutive_failures": self.consecutive_failures,
            "last_transition": self.last_transition,
            "history_len": len(self.history),
            "is_healable": self.is_healable,
        }

    def __repr__(self) -> str:
        return (
            f"SubsystemHealth(name={self.name!r}, "
            f"status={self.current_status.value}, "
            f"consecutive_failures={self.consecutive_failures})"
        )


class DiagnosticsEngine:
    """Singleton engine that runs registered health checks and tracks subsystem health.

    Example::

        engine = DiagnosticsEngine()
        engine.register_check("disk", my_disk_check)
        engine.enable()
        summary = engine.health_summary()
    """

    _instance: Optional[DiagnosticsEngine] = None
    _lock_class = threading.Lock()

    def __new__(cls) -> DiagnosticsEngine:
        with cls._lock_class:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._lock = threading.Lock()
        self._checks: Dict[str, Callable[[], DiagnosticResult]] = {}
        self._subsystems: Dict[str, SubsystemHealth] = {}
        self._check_interval: float = 60.0
        self._enabled: bool = False
        self._timer: Optional[threading.Timer] = None
        logger.info("DiagnosticsEngine initialised (interval=%.1fs)", self._check_interval)

    def register_check(self, name: str, check_fn: Callable[[], DiagnosticResult]) -> None:
        """Register a named health check callable."""
        with self._lock:
            self._checks[name] = check_fn
            if name not in self._subsystems:
                self._subsystems[name] = SubsystemHealth(name)
            logger.info("Registered health check: %s", name)

    def unregister_check(self, name: str) -> None:
        """Remove a health check by name."""
        with self._lock:
            self._checks.pop(name, None)
            logger.info("Unregistered health check: %s", name)

    def check_one(self, name: str) -> DiagnosticResult:
        """Run a single named check and record its result."""
        with self._lock:
            check_fn = self._checks.get(name)

        if check_fn is None:
            return DiagnosticResult(
                component=name,
                status=HealthStatus.UNAVAILABLE,
                timestamp=time.time(),
                reason="No check registered for component",
                confidence=1.0,
                recommended_action="Register a check for this component",
            )

        result = self._run_check(name, check_fn)

        with self._lock:
            self._get_subsystem(name).record(result)

        return result

    def check_all(self) -> List[DiagnosticResult]:
        """Run every registered check and return all results."""
        with self._lock:
            names = list(self._checks.keys())

        results: List[DiagnosticResult] = []
        for name in names:
            results.append(self.check_one(name))
        return results

    def health_summary(self) -> dict[str, Any]:
        """Return an overall status summary with per-subsystem details."""
        with self._lock:
            overall = self._compute_overall()
            per_subsystem: Dict[str, dict[str, Any]] = {}
            counts = {s.value: 0 for s in HealthStatus}

            for name, sub in self._subsystems.items():
                per_subsystem[name] = sub.to_dict()
                counts[sub.current_status.value] += 1

            return {
                "overall_status": overall.value,
                "subsystems": per_subsystem,
                "counts": counts,
                "check_interval": self._check_interval,
                "enabled": self._enabled,
                "registered_checks": list(self._checks.keys()),
            }

    def get_subsystem(self, name: str) -> SubsystemHealth:
        """Get the SubsystemHealth tracker for *name*, creating it if needed."""
        with self._lock:
            return self._get_subsystem(name)

    def set_check_interval(self, seconds: float) -> None:
        """Update the interval between automatic check cycles (in seconds)."""
        if seconds <= 0:
            raise ValueError("Check interval must be positive")
        with self._lock:
            self._check_interval = seconds
            logger.info("Check interval updated to %.1fs", seconds)

    def enable(self) -> None:
        """Enable automatic periodic checks."""
        with self._lock:
            if self._enabled:
                return
            self._enabled = True
            self._schedule_next()
            logger.info("DiagnosticsEngine enabled")

    def disable(self) -> None:
        """Disable automatic periodic checks."""
        with self._lock:
            self._enabled = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            logger.info("DiagnosticsEngine disabled")

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful in tests)."""
        with cls._lock_class:
            if cls._instance is not None:
                cls._instance.disable()
            cls._instance = None

    def _get_subsystem(self, name: str) -> SubsystemHealth:
        """Caller must hold self._lock."""
        sub = self._subsystems.get(name)
        if sub is None:
            sub = SubsystemHealth(name)
            self._subsystems[name] = sub
        return sub

    def _run_check(
        self, name: str, check_fn: Callable[[], DiagnosticResult]
    ) -> DiagnosticResult:
        """Execute *check_fn* safely -- never let an exception propagate."""
        try:
            result = check_fn()
            if not isinstance(result, DiagnosticResult):
                logger.error(
                    "Check %s returned invalid type %s, wrapping as FAILING",
                    name, type(result).__name__,
                )
                return DiagnosticResult(
                    component=name,
                    status=HealthStatus.FAILING,
                    timestamp=time.time(),
                    reason=f"Check returned invalid type {type(result).__name__}",
                    confidence=0.5,
                )
            return result
        except Exception as exc:
            logger.exception("Check %s raised an exception", name)
            return DiagnosticResult(
                component=name,
                status=HealthStatus.FAILING,
                timestamp=time.time(),
                reason=f"Check raised {type(exc).__name__}: {exc}",
                confidence=1.0,
                recommended_action="Investigate exception in check implementation",
            )

    def _compute_overall(self) -> HealthStatus:
        """Derive the worst-case overall status from all subsystems.

        Priority: CORRUPTED > FAILING > UNAVAILABLE > DEGRADED > UNKNOWN > HEALTHY.
        Caller must hold self._lock.
        """
        if not self._subsystems:
            return HealthStatus.UNKNOWN

        worst = HealthStatus.HEALTHY
        severity = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.UNKNOWN: 1,
            HealthStatus.DEGRADED: 2,
            HealthStatus.UNAVAILABLE: 3,
            HealthStatus.FAILING: 4,
            HealthStatus.CORRUPTED: 5,
        }

        for sub in self._subsystems.values():
            if severity.get(sub.current_status, 0) > severity.get(worst, 0):
                worst = sub.current_status

        return worst

    def _schedule_next(self) -> None:
        """Schedule the next automatic check cycle. Caller must hold self._lock."""
        if not self._enabled:
            return
        self._timer = threading.Timer(self._check_interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self) -> None:
        """Callback fired by the periodic timer."""
        try:
            self.check_all()
        except Exception:
            logger.exception("Unexpected error during periodic diagnostics tick")
        finally:
            with self._lock:
                self._schedule_next()
