"""
MYRAA Brain

Failure Containment Manager

Implements failure containment to isolate failing subsystems and prevent
crashing unrelated MYRAA features.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FailureContainmentManager:
    """
    Tracks failure counts per subsystem and provides health status.

    Subsystems can be: 'vision', 'target_resolution', 'action_execution',
    'browser', 'finance', 'perception', etc.
    """

    def __init__(self):
        """Initialize the failure containment manager."""
        self._failure_counts: dict[str, int] = {}
        self._lock = threading.RLock()
        # Thresholds for health states
        self._degraded_threshold = 3
        self._failed_threshold = 5

    def record_failure(self, subsystem: str) -> None:
        """
        Record a failure for a subsystem.

        Args:
            subsystem: Name of the subsystem (e.g., 'vision', 'browser')
        """
        with self._lock:
            self._failure_counts[subsystem] = self._failure_counts.get(subsystem, 0) + 1

    def record_success(self, subsystem: str) -> None:
        """
        Record a success for a subsystem, resetting its failure count.

        Args:
            subsystem: Name of the subsystem
        """
        with self._lock:
            if subsystem in self._failure_counts:
                del self._failure_counts[subsystem]

    def get_health(self, subsystem: str) -> str:
        """
        Get the health status of a subsystem.

        Args:
            subsystem: Name of the subsystem

        Returns:
            Health status: 'HEALTHY', 'DEGRADED', or 'FAILED'
        """
        with self._lock:
            count = self._failure_counts.get(subsystem, 0)
            if count >= self._failed_threshold:
                return "FAILED"
            elif count >= self._degraded_threshold:
                return "DEGRADED"
            else:
                return "HEALTHY"

    def is_healthy(self, subsystem: str) -> bool:
        """
        Check if a subsystem is healthy.

        Args:
            subsystem: Name of the subsystem

        Returns:
            True if subsystem is HEALTHY, False otherwise
        """
        return self.get_health(subsystem) == "HEALTHY"

    def is_degraded_or_worse(self, subsystem: str) -> bool:
        """
        Check if a subsystem is degraded or failed.

        Args:
            subsystem: Name of the subsystem

        Returns:
            True if subsystem is DEGRADED or FAILED
        """
        health = self.get_health(subsystem)
        return health in ["DEGRADED", "FAILED"]

    def is_failed(self, subsystem: str) -> bool:
        """
        Check if a subsystem is failed.

        Args:
            subsystem: Name of the subsystem

        Returns:
            True if subsystem is FAILED
        """
        return self.get_health(subsystem) == "FAILED"

    def get_all_health(self) -> dict[str, str]:
        """
        Get health status for all tracked subsystems.

        Returns:
            Dictionary mapping subsystem names to health status
        """
        with self._lock:
            return self._failure_counts.copy()

    def reset_subsystem(self, subsystem: str) -> None:
        """
        Reset failure count for a subsystem.

        Args:
            subsystem: Name of the subsystem
        """
        with self._lock:
            if subsystem in self._failure_counts:
                del self._failure_counts[subsystem]


# Global instance for use across the application
failure_containment_manager = FailureContainmentManager()


# ==========================================================
# F7: ONE authoritative recovery & resilience layer.
#
# This is the single place that decides WHETHER to retry and HOW LONG to
# wait. All existing retry mechanisms (orchestrator RetryEngine, planner
# RetryPolicy, execution RetryManager, action_executor backoff) execute
# operations; this engine is the ONE policy that authorizes retries, so a
# failure is never retried N times at the Brain layer AND M times at the
# provider layer AND K times in recovery (no retry multiplication).
# ==========================================================

class FailureClass(str, Enum):
    """Class of a failure, used to drive recovery decisions."""
    TRANSIENT = "transient"          # Will likely succeed on retry (timeout, rate limit, blip)
    PERMANENT = "permanent"          # Will NOT succeed on retry (bad request, missing file)
    AUTH = "auth"                    # Needs credentials/user action (401, bad API key)
    CONFIGURATION = "configuration"  # Needs config change before retry
    SECURITY = "security"            # Permission / confirmation / policy
    RESOURCE = "resource"            # Resource exhaustion (memory, disk) - bounded retry
    VERIFICATION = "verification"    # Action ran but verification failed -> replan/re-observe
    CANCELLATION = "cancellation"    # Task cancelled by user/system - never auto-retry


class RetryAction(str, Enum):
    RETRY = "retry"                  # Wait, then retry the same operation
    STOP = "stop"                    # Do not retry; surface the error
    COOLDOWN = "cooldown"            # Subsystem degraded; wait longer before any retry
    REPLAN = "replan"                # Do not blind-repeat; re-plan / re-observe then retry


class RetryBudget:
    """Bounded retry policy: exponential backoff + jitter + total budget."""

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 30.0,
        max_total_delay: float = 30.0,
        jitter: bool = True,
    ) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay = max(0.0, float(base_delay))
        self.backoff_factor = max(1.0, float(backoff_factor))
        self.max_delay = max(0.0, float(max_delay))
        self.max_total_delay = max(0.0, float(max_total_delay))
        self.jitter = bool(jitter)

    def delay_for(self, attempt: int, *, retry_after: float | None = None) -> float:
        """Compute the exponential-backoff delay for the given attempt (0-indexed).

        Honors the server-provided ``retry_after`` (Retry-After, HTTP 429)
        as a floor.
        """
        if attempt < 0:
            return 0.0
        delay = self.base_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            import random
            delay *= random.uniform(0.8, 1.2)
        if retry_after is not None:
            delay = max(delay, float(retry_after))
        return delay

    def cumulative_delay(self, attempts: int, *, retry_after: float | None = None) -> float:
        """Total expected delay if ``attempts`` retries are performed."""
        total = 0.0
        for i in range(max(0, attempts)):
            total += self.delay_for(i, retry_after=retry_after)
        return total


@dataclass
class RetryDecision:
    action: RetryAction
    delay_seconds: float = 0.0
    attempts_remaining: int = 0
    reason: str = ""


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------

_FAILURE_CLASS_BY_CATEGORY = {
    "rate_limit": FailureClass.TRANSIENT,
    "timeout": FailureClass.TRANSIENT,
    "provider_unavailable": FailureClass.TRANSIENT,
    "system_unavailable": FailureClass.TRANSIENT,
    "browser_disconnected": FailureClass.TRANSIENT,
    "action_timeout": FailureClass.TRANSIENT,
    "task_timeout": FailureClass.TRANSIENT,
    "context_failure": FailureClass.TRANSIENT,
    "vision_unavailable": FailureClass.TRANSIENT,
    "target_unresolved": FailureClass.TRANSIENT,
    "target_ambiguous": FailureClass.TRANSIENT,
    "target_stale": FailureClass.TRANSIENT,
    "target_invisible": FailureClass.TRANSIENT,
    "target_disabled": FailureClass.TRANSIENT,
    "window_changed": FailureClass.TRANSIENT,
    "coordinate_invalid": FailureClass.TRANSIENT,
    "auth_failure": FailureClass.AUTH,
    "permission_denied": FailureClass.SECURITY,
    "permission_required": FailureClass.SECURITY,
    "confirmation_required": FailureClass.SECURITY,
    "action_rejected": FailureClass.SECURITY,
    "invalid_request": FailureClass.CONFIGURATION,
    "invalid_input": FailureClass.CONFIGURATION,
    "validation_failure": FailureClass.CONFIGURATION,
    "resource_exhausted": FailureClass.RESOURCE,
    "verification_failed": FailureClass.VERIFICATION,
    "verification_failure": FailureClass.VERIFICATION,
    "recovery_failure": FailureClass.PERMANENT,
    "recovery_exhausted": FailureClass.PERMANENT,
    "cancelled": FailureClass.CANCELLATION,
    "internal_error": FailureClass.PERMANENT,
    "unknown_error": FailureClass.PERMANENT,
    "tool_failure": FailureClass.PERMANENT,
}


def classify_failure(error: Any) -> FailureClass:
    """Classify a canonical MYRAAError (or arbitrary exception) into a FailureClass."""
    from .error_taxonomy import ErrorCategory, MYRAAError, classify_exception

    if isinstance(error, MYRAAError):
        category = getattr(error.category, "value", str(error.category))
        # An explicitly retryable tool failure is treated as transient.
        if category in ("tool_failure", "unknown_error") and getattr(error, "retryable", False):
            return FailureClass.TRANSIENT
        return _FAILURE_CLASS_BY_CATEGORY.get(category, FailureClass.PERMANENT)

    if isinstance(error, ErrorCategory):
        return _FAILURE_CLASS_BY_CATEGORY.get(error.value, FailureClass.PERMANENT)

    if isinstance(error, Exception):
        myraa = classify_exception(error)
        return classify_failure(myraa)

    return FailureClass.PERMANENT


# ---------------------------------------------------------------------------
# Safe recovery guard: never auto-retry destructive / financial / system-critical
# ---------------------------------------------------------------------------

SAFE_RETRY_EXEMPT = frozenset({
    # Destructive (data loss)
    "deleteFile",
    "clearClipboard",
    "moveFile",
    "renameFile",
    # System power / critical
    "requestPowerAction",
    "executePowerAction",
    "closeApplication",
    "closeWindow",
    # Arbitrary code execution
    "runPythonScript",
    # Finance (advisory-only, but never auto-retried)
    "stockQuote",
    "niftyAnalysis",
    "portfolioAnalysis",
})

# Tool family -> recovery strategy keywords (checked after classification).
_TOOL_RECOVERY_OVERRIDES = {
    "browser": "reconnect_browser",
    "target": "re_observe_target",
    "window": "re_observe_target",
    "screenshot": "re_observe_target",
    "screen": "re_observe_target",
    "vision": "re_observe_target",
    "file": "bounded_retry_file_lock",
}


class RecoveryEngine:
    """THE authoritative recovery engine (F7).

    Reuses FailureContainmentManager for subsystem health; provides a single
    bounded retry policy, provider DEGRADED/COOLDOWN + fallback, and per-tool
    recovery strategies.
    """

    def __init__(
        self,
        budget: RetryBudget | None = None,
        containment: FailureContainmentManager | None = None,
        *,
        provider_cooldown_seconds: float = 30.0,
        provider_degraded_threshold: int = 3,
        provider_failed_threshold: int = 5,
    ) -> None:
        self.budget = budget or RetryBudget()
        self.containment = containment or failure_containment_manager
        self.provider_cooldown_seconds = float(provider_cooldown_seconds)
        self.provider_degraded_threshold = int(provider_degraded_threshold)
        self.provider_failed_threshold = int(provider_failed_threshold)
        self._provider_failures: dict[str, int] = {}
        self._provider_cooldown_until: dict[str, float] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # The ONE retry policy
    # ------------------------------------------------------------------

    def should_retry(
        self,
        error: Any,
        attempt: int,
        *,
        tool: str = "",
        subsystem: str | None = None,
    ) -> RetryDecision:
        """Decide the recovery action for a failure. This is the single
        authoritative policy consulted by every layer (no per-layer policies)."""
        fcls = classify_failure(error)

        # Safe-guard: destructive/financial/system-critical tools are NEVER
        # auto-retried, regardless of classification.
        if tool and tool in SAFE_RETRY_EXEMPT:
            return RetryDecision(
                action=RetryAction.STOP,
                reason=f"Safe-guard: '{tool}' is destructive/system-critical; no auto-retry.",
            )

        # Absolute opt-out: an error explicitly marked non-retryable is NEVER
        # retried, whatever its failure class.
        #
        # This contract is what every lower layer relies on
        # ("retryable == False  =>  zero automatic retries"). Previously only
        # the failure-class table was consulted, so a TIMEOUT-class error built
        # with retryable=False was still returned as RETRY.
        if getattr(error, "retryable", None) is False:
            return RetryDecision(
                action=RetryAction.STOP,
                attempts_remaining=0,
                reason="Error is explicitly marked non-retryable.",
            )

        if fcls in (FailureClass.CANCELLATION, FailureClass.AUTH,
                    FailureClass.SECURITY, FailureClass.PERMANENT,
                    FailureClass.CONFIGURATION):
            return RetryDecision(
                action=RetryAction.STOP,
                reason=f"Failure class '{fcls.value}' is not retryable.",
            )

        if attempt >= self.budget.max_attempts:
            return RetryDecision(
                action=RetryAction.STOP,
                reason="Retry budget exceeded (max attempts reached).",
            )

        retry_after = None
        details = getattr(error, "details", None) or {}
        if isinstance(details, dict) and details.get("retry_after") is not None:
            retry_after = float(details["retry_after"])

        delay = self.budget.delay_for(attempt, retry_after=retry_after)

        # Total-delay budget: reject the retry if it would blow the budget.
        if self.budget.cumulative_delay(attempt + 1, retry_after=retry_after) > self.budget.max_total_delay:
            return RetryDecision(
                action=RetryAction.STOP,
                reason="Retry budget exceeded (total delay).",
            )

        # Subsystem containment: if the subsystem is FAILED, cool down.
        sub = subsystem or self._subsystem_for(tool)
        if sub and self.containment.is_failed(sub):
            return RetryDecision(
                action=RetryAction.COOLDOWN,
                delay_seconds=delay,
                attempts_remaining=max(0, self.budget.max_attempts - attempt - 1),
                reason=f"Subsystem '{sub}' is FAILED; cooling down.",
            )

        action = RetryAction.REPLAN if fcls == FailureClass.VERIFICATION else RetryAction.RETRY
        return RetryDecision(
            action=action,
            delay_seconds=delay,
            attempts_remaining=max(0, self.budget.max_attempts - attempt - 1),
            reason=f"{action.value} after {fcls.value} failure (attempt {attempt + 1}).",
        )

    # ------------------------------------------------------------------
    # Subsystem accounting (reuses the containment manager)
    # ------------------------------------------------------------------

    @staticmethod
    def _subsystem_for(tool: str) -> str:
        if not tool:
            return ""
        if tool.startswith("desktopBrowser"):
            return "browser"
        if tool.startswith(("takeScreenshot", "saveScreenshot", "analyzeScreenshot", "readScreen")):
            return "vision"
        if "Power" in tool:
            return "power"
        if tool.startswith(("create", "read", "rename", "delete", "move", "list", "searchFiles")):
            return "filesystem"
        return "action_execution"

    def record_failure(self, tool: str, error: Any = None) -> None:
        self.containment.record_failure(self._subsystem_for(tool))

    def record_success(self, tool: str) -> None:
        self.containment.record_success(self._subsystem_for(tool))

    # ------------------------------------------------------------------
    # Provider recovery: DEGRADED / COOLDOWN + fallback
    # ------------------------------------------------------------------

    def record_provider_failure(self, provider: str) -> str:
        """Record a provider failure; returns the new state."""
        with self._lock:
            count = self._provider_failures.get(provider, 0) + 1
            self._provider_failures[provider] = count
            if count >= self.provider_failed_threshold:
                self._provider_cooldown_until[provider] = time.time() + self.provider_cooldown_seconds
            return self._provider_state(provider, count)

    def record_provider_success(self, provider: str) -> str:
        """Record a provider success; resets its failure/cooldown state."""
        with self._lock:
            self._provider_failures.pop(provider, None)
            self._provider_cooldown_until.pop(provider, None)
            return "HEALTHY"

    def _provider_state(self, provider: str, count: int | None = None) -> str:
        if provider in self._provider_cooldown_until:
            if self._provider_cooldown_until[provider] > time.time():
                return "COOLDOWN"
            self._provider_cooldown_until.pop(provider, None)
        count = self._provider_failures.get(provider, 0) if count is None else count
        if count >= self.provider_failed_threshold:
            return "COOLDOWN"
        if count >= self.provider_degraded_threshold:
            return "DEGRADED"
        return "HEALTHY"

    def provider_state(self, provider: str) -> str:
        with self._lock:
            return self._provider_state(provider)

    def recommend_fallback(
        self,
        current_provider: str,
        available: list[str],
    ) -> str | None:
        """Recommend a fallback provider (skip current + COOLDOWN ones)."""
        with self._lock:
            for name in available:
                if name == current_provider:
                    continue
                if self._provider_state(name) == "COOLDOWN":
                    continue
                return name
        return None

    # ------------------------------------------------------------------
    # Tool recovery strategies
    # ------------------------------------------------------------------

    def tool_recovery_strategy(self, tool: str, error: Any = None) -> str:
        """Map a failed tool to a concrete recovery strategy.

        - browser refocus/retry for default-browser tools (no engine owned)
        - target re-observation for vision/window/target tools
        - bounded file-lock retry for filesystem tools
        - replan for verification failures
        - abort for anything not recoverable
        """
        if not tool:
            return "abort"
        for keyword, strategy in _TOOL_RECOVERY_OVERRIDES.items():
            if keyword in tool.lower():
                return strategy
        fcls = classify_failure(error) if error is not None else FailureClass.PERMANENT
        if fcls == FailureClass.VERIFICATION:
            return "replan"
        if fcls in (FailureClass.TRANSIENT, FailureClass.RESOURCE):
            return "retry"
        return "abort"


# Global authoritative recovery engine (singleton, mirrors failure_containment_manager).
recovery_engine = RecoveryEngine()