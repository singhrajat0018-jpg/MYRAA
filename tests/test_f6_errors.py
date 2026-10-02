"""
F6 tests: ONE canonical error taxonomy across MYRAA.

Verifies the extended brain/error_taxonomy.py:
- canonical categories (auth, rate_limit, timeout, provider_unavailable,
  invalid_request, validation, permission, confirmation, tool, verification,
  recovery, context, resource, cancelled, internal)
- severity + retryable defaults per category
- HTTP status -> category mapping (401/403/408/429/5xx)
- exception classification (classify_exception)
- request_id / task_id correlation preserved on cross-service errors
- secret redaction (errors/telemetry must never leak keys)
- wiring into CommandDispatcher error responses (meta.error)
"""

from __future__ import annotations

import pytest

from desktop_agent.brain.error_taxonomy import (
    ErrorCategory,
    Severity,
    MYRAAError,
    classify_exception,
    category_is_retryable,
    default_severity,
    category_from_http_status,
    redact_text,
    redact_value,
)
from desktop_agent.registry import ToolError


# ---------------------------------------------------------------------------
# Canonical categories + defaults
# ---------------------------------------------------------------------------

def test_canonical_categories_exist():
    for expected in [
        "AUTH_FAILURE", "RATE_LIMIT", "TIMEOUT", "PROVIDER_UNAVAILABLE",
        "INVALID_REQUEST", "VALIDATION_FAILURE", "PERMISSION_DENIED",
        "CONFIRMATION_REQUIRED", "TOOL_FAILURE", "VERIFICATION_FAILURE",
        "RECOVERY_FAILURE", "CONTEXT_FAILURE", "RESOURCE_EXHAUSTED",
        "CANCELLED", "INTERNAL_ERROR",
    ]:
        assert getattr(ErrorCategory, expected, None) is not None, expected


def test_severity_enum():
    for expected in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
        assert getattr(Severity, expected, None) is not None


def test_retryable_defaults():
    assert category_is_retryable(ErrorCategory.RATE_LIMIT) is True
    assert category_is_retryable(ErrorCategory.TIMEOUT) is True
    assert category_is_retryable(ErrorCategory.PROVIDER_UNAVAILABLE) is True
    assert category_is_retryable(ErrorCategory.VERIFICATION_FAILURE) is True
    assert category_is_retryable(ErrorCategory.CONTEXT_FAILURE) is True
    # Non-retryable
    assert category_is_retryable(ErrorCategory.AUTH_FAILURE) is False
    assert category_is_retryable(ErrorCategory.PERMISSION_DENIED) is False
    assert category_is_retryable(ErrorCategory.VALIDATION_FAILURE) is False
    assert category_is_retryable(ErrorCategory.CANCELLED) is False
    assert category_is_retryable(ErrorCategory.INTERNAL_ERROR) is False
    assert category_is_retryable(ErrorCategory.CONFIRMATION_REQUIRED) is False
    assert category_is_retryable(ErrorCategory.RECOVERY_FAILURE) is False


def test_severity_defaults():
    assert default_severity(ErrorCategory.AUTH_FAILURE) is Severity.CRITICAL
    assert default_severity(ErrorCategory.INTERNAL_ERROR) is Severity.CRITICAL
    assert default_severity(ErrorCategory.RATE_LIMIT) is Severity.WARNING
    assert default_severity(ErrorCategory.TIMEOUT) is Severity.WARNING
    assert default_severity(ErrorCategory.PERMISSION_DENIED) is Severity.ERROR
    assert default_severity(ErrorCategory.CANCELLED) is Severity.INFO


def test_http_status_mapping():
    assert category_from_http_status(401) is ErrorCategory.AUTH_FAILURE
    assert category_from_http_status(403) is ErrorCategory.PERMISSION_DENIED
    assert category_from_http_status(429) is ErrorCategory.RATE_LIMIT
    assert category_from_http_status(408) is ErrorCategory.TIMEOUT
    assert category_from_http_status(500) is ErrorCategory.PROVIDER_UNAVAILABLE
    assert category_from_http_status(502) is ErrorCategory.PROVIDER_UNAVAILABLE
    assert category_from_http_status(503) is ErrorCategory.PROVIDER_UNAVAILABLE
    assert category_from_http_status(504) is ErrorCategory.TIMEOUT


# ---------------------------------------------------------------------------
# Canonical error shape
# ---------------------------------------------------------------------------

def test_myraa_error_dict_shape():
    err = MYRAAError.rate_limit("Too many requests", provider="gemini", retry_after=2.5)
    d = err.to_dict()
    for key in [
        "request_id", "task_id", "component", "category", "code", "message",
        "retryable", "severity", "timestamp", "provider", "tool", "metadata",
        "details", "recoverable",
    ]:
        assert key in d, key
    assert d["category"] == "rate_limit"
    assert d["retryable"] is True
    assert d["severity"] == "warning"
    assert d["provider"] == "gemini"
    assert d["details"]["retry_after"] == 2.5


def test_myraa_error_correlation_ids():
    err = MYRAAError.tool_failure("boom", tool="createFile")
    err = err.with_correlation(
        request_id="req-1",
        task_id="task-1",
        component="desktop_agent",
        tool="createFile",
    )
    d = err.to_dict()
    assert d["request_id"] == "req-1"
    assert d["task_id"] == "task-1"
    assert d["component"] == "desktop_agent"
    assert d["tool"] == "createFile"


def test_exception_classification():
    assert classify_exception(TimeoutError("took long")).category is ErrorCategory.TIMEOUT
    assert classify_exception(RuntimeError("api key rejected")).category is ErrorCategory.AUTH_FAILURE
    assert classify_exception(PermissionError("denied")).category is ErrorCategory.PERMISSION_DENIED
    assert classify_exception(ValueError("bad arg")).category is ErrorCategory.INTERNAL_ERROR
    assert classify_exception(RuntimeError("provider offline")).category is ErrorCategory.PROVIDER_UNAVAILABLE
    assert classify_exception(RuntimeError("task cancelled")).category is ErrorCategory.CANCELLED
    assert classify_exception(RuntimeError("verification failed")).category is ErrorCategory.VERIFICATION_FAILURE
    assert classify_exception(RuntimeError("rate limited"), tool="searchWeb").category is ErrorCategory.RATE_LIMIT
    assert classify_exception(RuntimeError("recovery failed")).category is ErrorCategory.RECOVERY_FAILURE
    err = classify_exception(RuntimeError("boom"), tool="systemInfo")
    assert err.tool == "systemInfo"


def test_classify_http_status_categories():
    # HTTP status -> canonical category, directly exercised.
    assert classify_exception(ConnectionError("HTTP 401 unauthorized")).category is ErrorCategory.AUTH_FAILURE
    assert classify_exception(ConnectionError("HTTP 403 forbidden")).category is ErrorCategory.PERMISSION_DENIED
    assert classify_exception(ConnectionError("HTTP 429 too many requests")).category is ErrorCategory.RATE_LIMIT
    assert classify_exception(ConnectionError("HTTP 500 server error")).category is ErrorCategory.PROVIDER_UNAVAILABLE
    assert classify_exception(TimeoutError("HTTP 504 gateway timeout")).category is ErrorCategory.TIMEOUT


def test_tool_error_to_canonical():
    te = ToolError("file does not exist", fatal=False)
    err = te.to_myraa_error(tool="readFile", request_id="req-x")
    assert err.category is ErrorCategory.TOOL_FAILURE
    assert err.to_dict()["request_id"] == "req-x"
    assert err.to_dict()["tool"] == "readFile"
    assert err.retryable is False


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

def test_redact_text_hides_keys_and_tokens():
    raw = "auth=sk-abcdef1234567890 token=xyzzy password=hunter2"
    out = redact_text(raw)
    assert "sk-abcdef1234567890" not in out
    assert "hunter2" not in out
    assert "[REDACTED]" in out


def test_redact_value_recursively():
    payload = {
        "api_key": "AIzaAAAAfakefakefake",
        "nested": {"authorization": "Bearer eyJxxx.abc"},
        "name": "not secret",
    }
    out = redact_value(payload)
    assert out["api_key"] == "[REDACTED]"
    assert out["nested"]["authorization"] == "[REDACTED]"
    assert out["name"] == "not secret"


def test_error_to_dict_never_contains_redacted_values():
    err = MYRAAError.auth_failure(
        "bad key sk-abcdefghijklmnop", provider="gemini",
        details={"credential_hint": "AIzaABCDEFG123456"},
    )
    blob = str(err.to_dict())
    assert "sk-abcdefghijklmnop" not in blob
    assert "AIzaABCDEFG123456" not in blob


# ---------------------------------------------------------------------------
# CommandDispatcher wiring (F6 correlation + canonical meta.error)
# ---------------------------------------------------------------------------

def _dispatch(tool: str, args: dict, request_id: str = "f6-req", task_id: str | None = "f6-task"):
    from desktop_agent.main import CommandDispatcher, ExecuteRequest
    req = ExecuteRequest(tool=tool, args=args, request_id=request_id, task_id=task_id)
    return CommandDispatcher.dispatch(req)


def test_invalid_tool_error_meta():
    resp = _dispatch("__no_such_tool__", {})
    assert resp.ok is False
    assert resp.meta["request_id"] == "f6-req"
    assert resp.meta["task_id"] == "f6-task"
    err = resp.meta["error"]
    assert err["category"] == "invalid_request"
    assert err["retryable"] is False
    assert err["severity"] == "error"
    assert err["request_id"] == "f6-req"


def test_permission_denied_error_meta():
    resp = _dispatch("deleteFile", {"path": "C:/Windows/system32/winlogon.exe"})
    assert resp.ok is False
    err = resp.meta["error"]
    assert err["category"] == "permission_denied"
    assert err["retryable"] is False
    assert err["request_id"] == "f6-req"


def test_confirmation_required_meta():
    resp = _dispatch("createFile", {"path": "C:/tmp/f6_test.txt", "content": "x"})
    assert resp.ok is True
    assert resp.result.get("requires_confirmation") is True
    assert resp.meta["requires_confirmation"] is True
    err = resp.meta["error"]
    assert err["category"] == "confirmation_required"
    assert err["retryable"] is False


def test_validation_failure_meta():
    resp = _dispatch("createFile", {})
    assert resp.ok is False
    err = resp.meta["error"]
    assert err["category"] == "tool_failure" or err["category"] == "validation_failure"
    assert err["request_id"] == "f6-req"


def test_tool_failure_meta_from_tool_error():
    resp = _dispatch("readFile", {"path": "C:/__f6_missing_file__.txt"})
    assert resp.ok is False
    err = resp.meta["error"]
    assert err["category"] == "tool_failure"
    assert err["request_id"] == "f6-req"
    assert err["task_id"] == "f6-task"


def test_request_id_preserved_across_success_too():
    resp = _dispatch("systemInfo", {})
    assert resp.ok is True
    assert resp.meta["request_id"] == "f6-req"
    assert resp.meta["task_id"] == "f6-task"