"""
MYRAA Brain

Error Taxonomy

Defines ONE canonical error model for MYRAA (F6): standardized error
categories, severities, retryability, and correlation fields shared across
Node, Python, Brain, providers, tools, verification, and recovery.

This extends the original EPIC-14E taxonomy (vision/action/resource/generic
categories) with the canonical cross-service categories required by the P0
foundation hardening plan. All original members are preserved for backward
compatibility.
"""

from __future__ import annotations

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any


class ErrorCategory(Enum):
    """Standardized error categories for MYRAA subsystems."""
    # Vision and perception errors
    VISION_UNAVAILABLE = "vision_unavailable"          # Screen capture or vision system unavailable
    TARGET_UNRESOLVED = "target_unresolved"            # Target could not be resolved
    TARGET_AMBIGUOUS = "target_ambiguous"              # Multiple possible targets, ambiguous
    TARGET_STALE = "target_stale"                      # Target information is outdated
    TARGET_INVISIBLE = "target_invisible"              # Target is resolved but not visible
    TARGET_DISABLED = "target_disabled"                # Target is resolved but not enabled (for interactive elements)
    WINDOW_CHANGED = "window_changed"                  # Active window changed during operation
    COORDINATE_INVALID = "coordinate_invalid"          # Coordinates are invalid (NaN, out of bounds, etc.)

    # Action execution errors
    ACTION_TIMEOUT = "action_timeout"                  # Action execution timed out
    ACTION_REJECTED = "action_rejected"                # Action was rejected by security/policies
    VERIFICATION_FAILED = "verification_failed"        # Action verification failed
    RECOVERY_EXHAUSTED = "recovery_exhausted"          # Recovery attempts exhausted
    BROWSER_DISCONNECTED = "browser_disconnected"      # Browser session disconnected or invalid

    # Resource and system errors
    PERMISSION_REQUIRED = "permission_required"        # Action requires user permission/confirmation
    RESOURCE_EXHAUSTED = "resource_exhausted"          # System resources exhausted (memory, etc.)
    TASK_TIMEOUT = "task_timeout"                      # Overall task timed out
    SYSTEM_UNAVAILABLE = "system_unavailable"          # Subsystem or service unavailable

    # Generic errors
    UNKNOWN_ERROR = "unknown_error"                    # Unknown or unclassified error
    INVALID_INPUT = "invalid_input"                    # Invalid input parameters
    INTERNAL_ERROR = "internal_error"                  # Internal software error

    # ==========================================================
    # F6 canonical cross-service categories
    # ==========================================================
    AUTH_FAILURE = "auth_failure"                      # Authentication failed (401 / bad API key)
    RATE_LIMIT = "rate_limit"                          # Rate limited (429) - retryable with backoff
    TIMEOUT = "timeout"                                # Operation timed out (408 / 504 / wall clock)
    PROVIDER_UNAVAILABLE = "provider_unavailable"      # AI/data provider unreachable or failing (5xx)
    INVALID_REQUEST = "invalid_request"                # Malformed request / unknown tool / bad route
    VALIDATION_FAILURE = "validation_failure"          # Argument validation failed
    PERMISSION_DENIED = "permission_denied"            # Permission denied (403 / policy deny)
    CONFIRMATION_REQUIRED = "confirmation_required"    # Action needs explicit user confirmation
    TOOL_FAILURE = "tool_failure"                      # A tool handler failed cleanly (ToolError)
    VERIFICATION_FAILURE = "verification_failure"      # Post-execution verification failed
    RECOVERY_FAILURE = "recovery_failure"              # Recovery/retry exhausted without success
    CONTEXT_FAILURE = "context_failure"                # Context/brain context could not be built
    CANCELLED = "cancelled"                            # Task cancelled by user/system


class Severity(Enum):
    """Canonical severity levels for MYRAA errors (F6)."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Default retryability per category (None means not automatically retryable).
_RETRYABLE_CATEGORIES = {
    ErrorCategory.RATE_LIMIT: True,
    ErrorCategory.TIMEOUT: True,
    ErrorCategory.PROVIDER_UNAVAILABLE: True,
    ErrorCategory.TASK_TIMEOUT: True,
    ErrorCategory.ACTION_TIMEOUT: True,
    ErrorCategory.VERIFICATION_FAILURE: True,
    ErrorCategory.VERIFICATION_FAILED: True,
    ErrorCategory.BROWSER_DISCONNECTED: True,
    ErrorCategory.WINDOW_CHANGED: True,
    ErrorCategory.TARGET_STALE: True,
    ErrorCategory.TARGET_UNRESOLVED: True,
    # These three are graded TRANSIENT in failure_containment's class table and
    # their taxonomy constructors declare recoverable=True, so they must be
    # retryable here too — otherwise the two tables disagree and an explicit
    # "retryable" flag contradicts the failure class.
    ErrorCategory.TARGET_AMBIGUOUS: True,
    ErrorCategory.TARGET_INVISIBLE: True,
    ErrorCategory.TARGET_DISABLED: True,
    ErrorCategory.CONTEXT_FAILURE: True,
    ErrorCategory.RECOVERY_EXHAUSTED: False,
    ErrorCategory.RECOVERY_FAILURE: False,
    ErrorCategory.AUTH_FAILURE: False,
    ErrorCategory.PERMISSION_DENIED: False,
    ErrorCategory.CONFIRMATION_REQUIRED: False,
    ErrorCategory.INVALID_REQUEST: False,
    ErrorCategory.VALIDATION_FAILURE: False,
    ErrorCategory.INVALID_INPUT: False,
    ErrorCategory.PERMISSION_REQUIRED: False,
    ErrorCategory.ACTION_REJECTED: False,
    ErrorCategory.CANCELLED: False,
    ErrorCategory.INTERNAL_ERROR: False,
    ErrorCategory.RESOURCE_EXHAUSTED: False,
    ErrorCategory.SYSTEM_UNAVAILABLE: False,
    ErrorCategory.UNKNOWN_ERROR: True,
    ErrorCategory.TOOL_FAILURE: False,
}

# Default severity per category (F6).
_DEFAULT_SEVERITY = {
    ErrorCategory.AUTH_FAILURE: Severity.CRITICAL,
    ErrorCategory.PERMISSION_DENIED: Severity.ERROR,
    ErrorCategory.INTERNAL_ERROR: Severity.CRITICAL,
    ErrorCategory.RESOURCE_EXHAUSTED: Severity.CRITICAL,
    ErrorCategory.SYSTEM_UNAVAILABLE: Severity.CRITICAL,
    ErrorCategory.RECOVERY_EXHAUSTED: Severity.CRITICAL,
    ErrorCategory.RECOVERY_FAILURE: Severity.ERROR,
    ErrorCategory.PROVIDER_UNAVAILABLE: Severity.ERROR,
    ErrorCategory.VERIFICATION_FAILURE: Severity.ERROR,
    ErrorCategory.VERIFICATION_FAILED: Severity.ERROR,
    ErrorCategory.TOOL_FAILURE: Severity.ERROR,
    ErrorCategory.RATE_LIMIT: Severity.WARNING,
    ErrorCategory.TIMEOUT: Severity.WARNING,
    ErrorCategory.CANCELLED: Severity.INFO,
    ErrorCategory.CONFIRMATION_REQUIRED: Severity.INFO,
    ErrorCategory.CONTEXT_FAILURE: Severity.WARNING,
    ErrorCategory.ACTION_REJECTED: Severity.WARNING,
    ErrorCategory.TASK_TIMEOUT: Severity.WARNING,
    ErrorCategory.ACTION_TIMEOUT: Severity.WARNING,
    ErrorCategory.WINDOW_CHANGED: Severity.WARNING,
    ErrorCategory.TARGET_STALE: Severity.WARNING,
    ErrorCategory.UNKNOWN_ERROR: Severity.ERROR,
}


def category_is_retryable(category: ErrorCategory) -> bool:
    """Return whether a category is safe to automatically retry by default."""
    return _RETRYABLE_CATEGORIES.get(category, False)


def default_severity(category: ErrorCategory) -> Severity:
    """Return the default severity for a category."""
    return _DEFAULT_SEVERITY.get(category, Severity.ERROR)


# HTTP status -> canonical category (F6). Provider-facing mapping used to
# classify cross-service failures without ever leaking response internals.
HTTP_STATUS_TO_CATEGORY: dict[int, ErrorCategory] = {
    401: ErrorCategory.AUTH_FAILURE,
    403: ErrorCategory.PERMISSION_DENIED,
    404: ErrorCategory.INVALID_REQUEST,
    408: ErrorCategory.TIMEOUT,
    409: ErrorCategory.CONTEXT_FAILURE,
    429: ErrorCategory.RATE_LIMIT,
    500: ErrorCategory.PROVIDER_UNAVAILABLE,
    502: ErrorCategory.PROVIDER_UNAVAILABLE,
    503: ErrorCategory.PROVIDER_UNAVAILABLE,
    504: ErrorCategory.TIMEOUT,
}


def category_from_http_status(status: int) -> ErrorCategory:
    """Map an HTTP status code to the canonical MYRAA error category."""
    return HTTP_STATUS_TO_CATEGORY.get(status, ErrorCategory.UNKNOWN_ERROR)


@dataclass
class MYRAAError:
    """
    ONE canonical error representation for MYRAA (F6).

    Attributes:
        category: The error category from ErrorCategory
        message: Human-readable error message
        details: Optional dictionary with additional error details
        recoverable: Whether the error is potentially recoverable with retry
            (legacy name; aliases retryable for backward compatibility)
        request_id: Correlation id from the originating request
        task_id: Correlation id of the task the error belongs to
        component: Subsystem that raised the error (node, python, brain, ...)
        code: Stable machine-readable error code
        retryable: Whether this specific error is safe to retry
        severity: INFO / WARNING / ERROR / CRITICAL
        timestamp: Unix epoch when the error occurred
        provider: Provider name involved (ollama, ...)
        tool: Tool name involved
        metadata: Extra diagnostic metadata (secrets never included)
    """
    category: ErrorCategory
    message: str
    details: Optional[dict] = None
    recoverable: bool = True
    request_id: Optional[str] = None
    task_id: Optional[str] = None
    component: Optional[str] = None
    code: Optional[str] = None
    retryable: Optional[bool] = None
    severity: Optional[Severity] = None
    timestamp: Optional[float] = None
    provider: Optional[str] = None
    tool: Optional[str] = None
    metadata: Optional[dict] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = time.time()
        # retryable resolution order:
        #   1. an explicit `retryable` always wins;
        #   2. an explicit `recoverable=False` is an opt-out (never retried);
        #   3. otherwise fall back to the taxonomy's *declared* retryability for
        #      the category.
        #
        # Step 3 deliberately does NOT use the legacy `recoverable=True`
        # default. That default made every bare MYRAAError retryable, so
        # categories the taxonomy declares non-retryable (TOOL_FAILURE) were
        # silently promoted to "retryable" and the authoritative recovery
        # policy auto-retried them — violating the invariant
        # "retryable == False  =>  zero automatic retries".
        if self.retryable is None:
            if self.recoverable is False:
                self.retryable = False
            else:
                self.retryable = category_is_retryable(self.category)
        if self.severity is None:
            self.severity = default_severity(self.category)

    def to_dict(self) -> dict:
        """Convert error to the canonical dictionary representation."""
        return {
            "category": self.category.value,
            "code": self.code or self.category.value,
            "message": redact_text(self.message),
            "details": redact_value(self.details),
            "recoverable": self.recoverable,
            "retryable": self.retryable,
            "severity": self.severity.value if isinstance(self.severity, Severity) else str(self.severity),
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "component": self.component,
            "provider": self.provider,
            "tool": self.tool,
            "metadata": self.metadata,
        }

    @classmethod
    def vision_unavailable(cls, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a vision unavailable error."""
        return cls(
            category=ErrorCategory.VISION_UNAVAILABLE,
            message="Vision system is unavailable",
            details=details or {},
            recoverable=False  # Vision unavailable usually requires system restart
        )

    @classmethod
    def target_unresolved(cls, target_description: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a target unresolved error."""
        return cls(
            category=ErrorCategory.TARGET_UNRESOLVED,
            message=f"Could not resolve target: {target_description}",
            details=details or {"target_description": target_description},
            recoverable=True
        )

    @classmethod
    def target_ambiguous(cls, target_description: str, matches: int, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a target ambiguous error."""
        return cls(
            category=ErrorCategory.TARGET_AMBIGUOUS,
            message=f"Target '{target_description}' is ambiguous ({matches} matches)",
            details=details or {"target_description": target_description, "matches": matches},
            recoverable=True
        )

    @classmethod
    def target_stale(cls, target_description: str, age_seconds: float, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a target stale error."""
        return cls(
            category=ErrorCategory.TARGET_STALE,
            message=f"Target '{target_description}' is stale (age: {age_seconds:.1f}s)",
            details=details or {"target_description": target_description, "age_seconds": age_seconds},
            recoverable=True
        )

    @classmethod
    def window_changed(cls, old_window: str, new_window: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a window changed error."""
        return cls(
            category=ErrorCategory.WINDOW_CHANGED,
            message=f"Active window changed from '{old_window}' to '{new_window}'",
            details=details or {"old_window": old_window, "new_window": new_window},
            recoverable=True
        )

    @classmethod
    def coordinate_invalid(cls, x: float, y: float, reason: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a coordinate invalid error."""
        return cls(
            category=ErrorCategory.COORDINATE_INVALID,
            message=f"Invalid coordinates ({x}, {y}): {reason}",
            details=details or {"x": x, "y": y, "reason": reason},
            recoverable=False  # Invalid coordinates usually indicate programming error
        )

    @classmethod
    def action_timeout(cls, action_type: str, timeout_seconds: float, details: Optional[dict] = None) -> 'MYRAAError':
        """Create an action timeout error."""
        return cls(
            category=ErrorCategory.ACTION_TIMEOUT,
            message=f"Action '{action_type}' timed out after {timeout_seconds}s",
            details=details or {"action_type": action_type, "timeout_seconds": timeout_seconds},
            recoverable=True
        )

    @classmethod
    def action_rejected(cls, action_type: str, reason: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create an action rejected error."""
        return cls(
            category=ErrorCategory.ACTION_REJECTED,
            message=f"Action '{action_type}' rejected: {reason}",
            details=details or {"action_type": action_type, "reason": reason},
            recoverable=False  # Rejected actions usually require user intervention
        )

    @classmethod
    def verification_failed(cls, action_type: str, reason: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a verification failed error."""
        return cls(
            category=ErrorCategory.VERIFICATION_FAILED,
            message=f"Verification failed for action '{action_type}': {reason}",
            details=details or {"action_type": action_type, "reason": reason},
            recoverable=True
        )

    @classmethod
    def recovery_exhausted(cls, action_type: str, attempts: int, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a recovery exhausted error."""
        return cls(
            category=ErrorCategory.RECOVERY_EXHAUSTED,
            message=f"Recovery exhausted for action '{action_type}' after {attempts} attempts",
            details=details or {"action_type": action_type, "attempts": attempts},
            recoverable=False
        )

    @classmethod
    def browser_disconnected(cls, reason: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a browser disconnected error."""
        return cls(
            category=ErrorCategory.BROWSER_DISCONNECTED,
            message=f"Browser disconnected: {reason}",
            details=details or {"reason": reason},
            recoverable=True
        )

    @classmethod
    def permission_required(cls, action_type: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a permission required error."""
        return cls(
            category=ErrorCategory.PERMISSION_REQUIRED,
            message=f"Permission required for action: {action_type}",
            details=details or {"action_type": action_type},
            recoverable=True  # User can grant permission
        )

    @classmethod
    def resource_exhausted(cls, resource_type: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a resource exhausted error."""
        return cls(
            category=ErrorCategory.RESOURCE_EXHAUSTED,
            message=f"Resource exhausted: {resource_type}",
            details=details or {"resource_type": resource_type},
            recoverable=False  # Usually requires system intervention
        )

    @classmethod
    def task_timeout(cls, task_description: str, timeout_seconds: float, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a task timeout error."""
        return cls(
            category=ErrorCategory.TASK_TIMEOUT,
            message=f"Task '{task_description}' timed out after {timeout_seconds}s",
            details=details or {"task_description": task_description, "timeout_seconds": timeout_seconds},
            recoverable=True
        )

    @classmethod
    def system_unavailable(cls, subsystem: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create a system unavailable error."""
        return cls(
            category=ErrorCategory.SYSTEM_UNAVAILABLE,
            message=f"Subsystem unavailable: {subsystem}",
            details=details or {"subsystem": subsystem},
            recoverable=False  # Usually requires system restart
        )

    @classmethod
    def unknown_error(cls, message: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create an unknown error."""
        return cls(
            category=ErrorCategory.UNKNOWN_ERROR,
            message=message,
            details=details or {},
            recoverable=True  # Assume recoverable unless known otherwise
        )

    @classmethod
    def invalid_input(cls, field: str, value: Any, details: Optional[dict] = None) -> 'MYRAAError':
        """Create an invalid input error."""
        return cls(
            category=ErrorCategory.INVALID_INPUT,
            message=f"Invalid input for field '{field}': {value}",
            details=details or {"field": field, "value": str(value)},
            recoverable=False  # Invalid input usually requires correction
        )

    @classmethod
    def internal_error(cls, message: str, details: Optional[dict] = None) -> 'MYRAAError':
        """Create an internal error."""
        return cls(
            category=ErrorCategory.INTERNAL_ERROR,
            message=f"Internal error: {message}",
            details=details or {},
            recoverable=False  # Internal errors usually indicate bugs
        )

    # ==========================================================
    # F6 canonical factory methods
    # ==========================================================

    @classmethod
    def auth_failure(cls, message: str, provider: Optional[str] = None,
                     details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.AUTH_FAILURE,
            message=message,
            details=details or {},
            recoverable=False,
            provider=provider,
        )

    @classmethod
    def rate_limit(cls, message: str, provider: Optional[str] = None,
                   retry_after: Optional[float] = None,
                   details: Optional[dict] = None) -> 'MYRAAError':
        meta = dict(details or {})
        if retry_after is not None:
            meta["retry_after"] = retry_after
        return cls(
            category=ErrorCategory.RATE_LIMIT,
            message=message,
            details=meta,
            recoverable=True,
            provider=provider,
        )

    @classmethod
    def timeout(cls, message: str, provider: Optional[str] = None,
                details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.TIMEOUT,
            message=message,
            details=details or {},
            recoverable=True,
            provider=provider,
        )

    @classmethod
    def provider_unavailable(cls, message: str, provider: Optional[str] = None,
                             details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.PROVIDER_UNAVAILABLE,
            message=message,
            details=details or {},
            recoverable=True,
            provider=provider,
        )

    @classmethod
    def invalid_request(cls, message: str, details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.INVALID_REQUEST,
            message=message,
            details=details or {},
            recoverable=False,
        )

    @classmethod
    def validation_failure(cls, message: str, tool: Optional[str] = None,
                           details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.VALIDATION_FAILURE,
            message=message,
            details=details or {},
            recoverable=False,
            tool=tool,
        )

    @classmethod
    def permission_denied(cls, message: str, tool: Optional[str] = None,
                          details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.PERMISSION_DENIED,
            message=message,
            details=details or {},
            recoverable=False,
            tool=tool,
        )

    @classmethod
    def confirmation_required(cls, message: str, tool: Optional[str] = None,
                              details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.CONFIRMATION_REQUIRED,
            message=message,
            details=details or {},
            recoverable=False,
            tool=tool,
        )

    @classmethod
    def tool_failure(cls, message: str, tool: Optional[str] = None,
                     details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.TOOL_FAILURE,
            message=message,
            details=details or {},
            recoverable=False,
            tool=tool,
        )

    @classmethod
    def verification_failure(cls, message: str, tool: Optional[str] = None,
                             details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.VERIFICATION_FAILURE,
            message=message,
            details=details or {},
            recoverable=True,
            tool=tool,
        )

    @classmethod
    def recovery_failure(cls, message: str, tool: Optional[str] = None,
                         details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.RECOVERY_FAILURE,
            message=message,
            details=details or {},
            recoverable=False,
            tool=tool,
        )

    @classmethod
    def context_failure(cls, message: str, details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.CONTEXT_FAILURE,
            message=message,
            details=details or {},
            recoverable=True,
        )

    @classmethod
    def cancelled(cls, message: str, details: Optional[dict] = None) -> 'MYRAAError':
        return cls(
            category=ErrorCategory.CANCELLED,
            message=message,
            details=details or {},
            recoverable=False,
        )

    def with_correlation(
        self,
        request_id: Optional[str] = None,
        task_id: Optional[str] = None,
        component: Optional[str] = None,
        provider: Optional[str] = None,
        tool: Optional[str] = None,
        code: Optional[str] = None,
    ) -> 'MYRAAError':
        """Return a copy carrying correlation metadata (F6)."""
        return MYRAAError(
            category=self.category,
            message=self.message,
            details=dict(self.details or {}),
            recoverable=self.recoverable,
            request_id=request_id if request_id is not None else self.request_id,
            task_id=task_id if task_id is not None else self.task_id,
            component=component if component is not None else self.component,
            code=code if code is not None else self.code,
            retryable=self.retryable,
            severity=self.severity,
            timestamp=self.timestamp,
            provider=provider if provider is not None else self.provider,
            tool=tool if tool is not None else self.tool,
            metadata=dict(self.metadata or {}),
        )


def classify_exception(exc: Exception, *, tool: str = "", provider: str = "") -> MYRAAError:
    """Classify an arbitrary exception into a canonical MYRAAError (F6).

    Never exposes secret internals: only the exception class name and a safe
    message prefix are preserved.
    """
    name = exc.__class__.__name__.lower()
    message = str(exc) or name
    haystack = f"{name} {message}".lower()
    # Explicit HTTP status codes win over class-name heuristics (e.g. a
    # ConnectionError carrying "HTTP 403 forbidden" is a permission issue,
    # not a connectivity problem).
    import re as _re
    status_match = _re.search(r"\b(4\d\d|5\d\d)\b", haystack)
    if status_match:
        status = int(status_match.group(1))
        mapped = category_from_http_status(status)
        if mapped is not None:
            err = MYRAAError(
                category=mapped,
                message=message,
                recoverable=category_is_retryable(mapped),
                provider=provider,
            )
            if tool:
                return err.with_correlation(tool=tool)
            return err
    if any(k in haystack for k in ("api key", "apikey", "unauthorized", "credential", "invalid key", "401")):
        err = MYRAAError.auth_failure(message, provider=provider)
    elif "ratelimit" in haystack or "rate_limit" in haystack or "rate limit" in haystack or "429" in haystack:
        err = MYRAAError.rate_limit(message, provider=provider)
    elif "timeout" in haystack or "timed out" in haystack or "504" in haystack:
        err = MYRAAError.timeout(message, provider=provider)
    elif "unavailable" in haystack or "disconnect" in haystack or "connection" in haystack or "offline" in haystack or "refused" in haystack:
        err = MYRAAError.provider_unavailable(message, provider=provider)
    elif "validation" in haystack:
        err = MYRAAError.validation_failure(message, tool=tool)
    elif "permission" in haystack or "access denied" in haystack or "forbidden" in haystack or "403" in haystack:
        err = MYRAAError.permission_denied(message, tool=tool)
    elif "cancel" in haystack:
        err = MYRAAError.cancelled(message)
    elif "context" in haystack:
        err = MYRAAError.context_failure(message)
    elif "tool" in haystack:
        err = MYRAAError.tool_failure(message, tool=tool)
    elif "verification" in haystack:
        err = MYRAAError.verification_failure(message, tool=tool)
    elif "recovery" in haystack or "retry" in haystack:
        err = MYRAAError.recovery_failure(message, tool=tool)
    else:
        err = MYRAAError.internal_error(message, details={"exception": exc.__class__.__name__})
    if tool:
        return err.with_correlation(tool=tool)
    return err


# ==========================================================
# Secret redaction (F6 error rule + F8 telemetry)
# ==========================================================

_REDACTION_PATTERNS = (
    r"(?i)(api[_-]?key|apikey|authorization|bearer)\s*[:=]\s*[^\s,;}\"']+",
    r"(?i)(password|passwd|pwd|client[_-]?secret|secret)\s*[:=]\s*[^\s,;}\"']+",
    r"(?i)\b(eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})",  # JWT-ish
    r"(?i)\b(sk-[a-zA-Z0-9_-]{8,})\b",                     # sk- prefixed keys
    r"(?i)\b(tvly-[a-zA-Z0-9_-]{8,})\b",                   # Tavily keys
    r"(?i)\b(AIza[a-zA-Z0-9_-]{20,})\b",                   # Google API keys
    r"(?i)(token|otp|access_token|refresh_token)\s*[:=]\s*[^\s,;}\"']+",
    r"(?i)\b[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}\b",  # card numbers
)

_REDACTED = "[REDACTED]"


def redact_text(text: str) -> str:
    """Replace secret-looking substrings with [REDACTED] (F6/F8)."""
    import re
    if not text:
        return text
    result = text
    for pattern in _REDACTION_PATTERNS:
        result = re.sub(pattern, _REDACTED, result)
    return result


def redact_value(value: Any) -> Any:
    """Recursively redact secret-looking strings inside dict/list/str values."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            k_l = str(k).lower()
            if any(hint in k_l for hint in
                   ("api_key", "apikey", "key", "password", "passwd", "secret",
                    "token", "authorization", "bearer", "otp", "credential")):
                out[k] = _REDACTED
            else:
                out[k] = redact_value(v)
        return out
    if isinstance(value, (list, tuple, set)):
        return [redact_value(v) for v in value]
    return value


# Global error registry for tracking error frequencies (optional)
_error_registry: dict[str, int] = {}


def record_error(error: MYRAAError) -> None:
    """Record an error in the global registry for metrics."""
    category_key = error.category.value
    _error_registry[category_key] = _error_registry.get(category_key, 0) + 1


def get_error_registry() -> dict[str, int]:
    """Get a copy of the error registry."""
    return _error_registry.copy()


def reset_error_registry() -> None:
    """Reset the error registry."""
    global _error_registry
    _error_registry = {}