"""
F7 tests: ONE authoritative recovery & resilience layer.

Verifies desktop_agent/brain/failure_containment.py's RecoveryEngine:
- failure classification (transient/permanent/auth/config/security/resource/
  verification/cancellation)
- bounded retry + exponential backoff + jitter + retry budget
- Retry-After (429) honored
- no retry multiplication (single authoritative policy consulted everywhere)
- provider recovery: DEGRADED / COOLDOWN + fallback recommendation
- tool recovery: browser reconnect, target re-observe, file-lock bounded retry,
  verification -> replan, abort otherwise
- safe recovery: destructive/financial/system-critical tools are NEVER
  auto-retried
- wiring: CommandDispatcher error payloads carry the canonical retry decision
"""

from __future__ import annotations

import pytest

from desktop_agent.brain.failure_containment import (
    FailureClass,
    RetryAction,
    RetryBudget,
    RecoveryEngine,
    classify_failure,
    SAFE_RETRY_EXEMPT,
)
from desktop_agent.brain.error_taxonomy import (
    ErrorCategory,
    MYRAAError,
)


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------

def test_classify_failure_categories():
    assert classify_failure(MYRAAError.timeout("slow")) is FailureClass.TRANSIENT
    assert classify_failure(MYRAAError.rate_limit("429")) is FailureClass.TRANSIENT
    assert classify_failure(MYRAAError.provider_unavailable("down")) is FailureClass.TRANSIENT
    assert classify_failure(MYRAAError.auth_failure("bad key")) is FailureClass.AUTH
    assert classify_failure(MYRAAError.permission_denied("no")) is FailureClass.SECURITY
    assert classify_failure(MYRAAError.confirmation_required("confirm")) is FailureClass.SECURITY
    assert classify_failure(MYRAAError.validation_failure("bad arg")) is FailureClass.CONFIGURATION
    assert classify_failure(MYRAAError.invalid_request("bad req")) is FailureClass.CONFIGURATION
    assert classify_failure(MYRAAError.resource_exhausted("oom")) is FailureClass.RESOURCE
    assert classify_failure(MYRAAError.verification_failure("verify")) is FailureClass.VERIFICATION
    assert classify_failure(MYRAAError.cancelled("cancelled")) is FailureClass.CANCELLATION
    assert classify_failure(MYRAAError.internal_error("bug")) is FailureClass.PERMANENT
    assert classify_failure(MYRAAError.tool_failure("missing file")) is FailureClass.PERMANENT


def test_classify_failure_exception_and_retryable_tool():
    assert classify_failure(TimeoutError("x")) is FailureClass.TRANSIENT
    assert classify_failure(ValueError("x")) is FailureClass.PERMANENT
    err = MYRAAError(category=ErrorCategory.TOOL_FAILURE, message="flaky", retryable=True)
    assert classify_failure(err) is FailureClass.TRANSIENT


# ---------------------------------------------------------------------------
# Bounded retry + backoff + jitter + budget
# ---------------------------------------------------------------------------

def test_retry_budget_backoff_increasing():
    budget = RetryBudget(max_attempts=5, base_delay=1.0, backoff_factor=2.0, max_delay=30.0, jitter=False)
    d0 = budget.delay_for(0)
    d1 = budget.delay_for(1)
    d2 = budget.delay_for(2)
    assert d0 == 1.0
    assert d1 == 2.0
    assert d2 == 4.0
    assert budget.delay_for(10) == 30.0  # capped


def test_retry_budget_jitter_bounds():
    budget = RetryBudget(max_attempts=3, base_delay=2.0, jitter=True)
    for _ in range(200):
        d = budget.delay_for(0)
        assert 1.6 <= d <= 2.4


def test_should_retry_stops_after_max_attempts():
    eng = RecoveryEngine(budget=RetryBudget(max_attempts=2))
    err = MYRAAError.timeout("slow")
    assert eng.should_retry(err, 0).action is RetryAction.RETRY
    assert eng.should_retry(err, 1).action is RetryAction.RETRY
    assert eng.should_retry(err, 2).action is RetryAction.STOP


def test_should_retry_respects_total_delay_budget():
    eng = RecoveryEngine(budget=RetryBudget(max_attempts=5, base_delay=10.0, backoff_factor=2.0, max_total_delay=12.0, jitter=False))
    err = MYRAAError.timeout("slow")
    # attempt 0: delay 10s -> ok; attempt 1: cumulative 10+20=30 > 12 -> stop
    assert eng.should_retry(err, 0).action is RetryAction.RETRY
    assert eng.should_retry(err, 1).action is RetryAction.STOP


def test_retry_after_honored():
    budget = RetryBudget(base_delay=0.1, jitter=False)
    assert budget.delay_for(0, retry_after=7.5) == 7.5  # Retry-After wins
    assert budget.delay_for(0, retry_after=0.01) > 0.0  # small -> uses backoff

    err = MYRAAError.rate_limit("429", retry_after=9.0)
    eng = RecoveryEngine(budget=RetryBudget(base_delay=0.1, max_delay=30.0, jitter=False))
    decision = eng.should_retry(err, 0)
    assert decision.action is RetryAction.RETRY
    assert decision.delay_seconds == 9.0


def test_non_retryable_classes_stop():
    eng = RecoveryEngine()
    assert eng.should_retry(MYRAAError.auth_failure("bad key"), 0).action is RetryAction.STOP
    assert eng.should_retry(MYRAAError.permission_denied("no"), 0).action is RetryAction.STOP
    assert eng.should_retry(MYRAAError.confirmation_required("yes"), 0).action is RetryAction.STOP
    assert eng.should_retry(MYRAAError.internal_error("bug"), 0).action is RetryAction.STOP
    assert eng.should_retry(MYRAAError.validation_failure("bad"), 0).action is RetryAction.STOP
    assert eng.should_retry(MYRAAError.cancelled("stop"), 0).action is RetryAction.STOP


def test_verification_failure_replans_not_blind_repeat():
    eng = RecoveryEngine()
    decision = eng.should_retry(MYRAAError.verification_failure("did not land"), 0, tool="leftClick")
    assert decision.action is RetryAction.REPLAN


# ---------------------------------------------------------------------------
# Safe recovery guard
# ---------------------------------------------------------------------------

def test_safe_retry_exempt_never_auto_retries():
    eng = RecoveryEngine()
    assert "deleteFile" in SAFE_RETRY_EXEMPT
    assert "executePowerAction" in SAFE_RETRY_EXEMPT
    assert "requestPowerAction" in SAFE_RETRY_EXEMPT
    for tool in ("deleteFile", "executePowerAction", "clearClipboard", "moveFile", "runPythonScript"):
        decision = eng.should_retry(MYRAAError.timeout("blip"), 0, tool=tool)
        assert decision.action is RetryAction.STOP, tool
        assert "Safe-guard" in decision.reason


def test_safe_retry_exempt_includes_finance():
    eng = RecoveryEngine()
    decision = eng.should_retry(MYRAAError.timeout("blip"), 0, tool="stockQuote")
    assert decision.action is RetryAction.STOP


# ---------------------------------------------------------------------------
# Provider recovery
# ---------------------------------------------------------------------------

def test_provider_states_and_fallback():
    eng = RecoveryEngine(provider_degraded_threshold=2, provider_failed_threshold=3, provider_cooldown_seconds=5)
    assert eng.provider_state("nim") == "HEALTHY"
    eng.record_provider_failure("nim")
    assert eng.provider_state("nim") == "HEALTHY"
    eng.record_provider_failure("nim")
    assert eng.provider_state("nim") == "DEGRADED"
    eng.record_provider_failure("nim")
    assert eng.provider_state("nim") == "COOLDOWN"


def test_provider_fallback_skips_current_and_cooldown():
    eng = RecoveryEngine(provider_degraded_threshold=2, provider_failed_threshold=1, provider_cooldown_seconds=60)
    # nim on cooldown -> recommend gemini
    eng.record_provider_failure("nim")
    assert eng.provider_state("nim") == "COOLDOWN"
    assert eng.recommend_fallback("nim", ["nim", "gemini", "ollama"]) == "gemini"
    # current skipped
    assert eng.recommend_fallback("gemini", ["gemini", "ollama"]) == "ollama"
    # all on cooldown -> None
    eng.record_provider_failure("gemini")
    eng.record_provider_failure("ollama")
    assert eng.recommend_fallback("nim", ["nim", "gemini", "ollama"]) is None


def test_provider_success_resets():
    eng = RecoveryEngine(provider_degraded_threshold=2, provider_failed_threshold=5)
    eng.record_provider_failure("gemini")
    eng.record_provider_failure("gemini")
    assert eng.provider_state("gemini") == "DEGRADED"
    assert eng.record_provider_success("gemini") == "HEALTHY"
    assert eng.provider_state("gemini") == "HEALTHY"


# ---------------------------------------------------------------------------
# Tool recovery strategies
# ---------------------------------------------------------------------------

def test_tool_recovery_strategies():
    eng = RecoveryEngine()
    assert eng.tool_recovery_strategy("desktopBrowserNavigate", MYRAAError.timeout("x")) == "reconnect_browser"
    assert eng.tool_recovery_strategy("takeScreenshot", MYRAAError.timeout("x")) == "re_observe_target"
    assert eng.tool_recovery_strategy("readFile", MYRAAError.resource_exhausted("lock")) == "bounded_retry_file_lock"
    assert eng.tool_recovery_strategy("leftClick", MYRAAError.verification_failure("miss")) == "replan"
    assert eng.tool_recovery_strategy("systemInfo", MYRAAError.timeout("x")) == "retry"
    assert eng.tool_recovery_strategy("systemInfo", MYRAAError.internal_error("bug")) == "abort"
    assert eng.tool_recovery_strategy("", MYRAAError.internal_error("bug")) == "abort"


# ---------------------------------------------------------------------------
# Containment integration
# ---------------------------------------------------------------------------

def test_recovery_records_into_containment():
    eng = RecoveryEngine()
    eng.record_failure("desktopBrowserOpen")
    assert eng.containment.get_health("browser") == "HEALTHY"  # 1 failure, not degraded
    for _ in range(3):
        eng.record_failure("desktopBrowserOpen")
    assert eng.containment.get_health("browser") == "DEGRADED"
    for _ in range(3):
        eng.record_failure("desktopBrowserOpen")
    assert eng.containment.get_health("browser") == "FAILED"


def test_containment_failed_triggers_cooldown():
    eng = RecoveryEngine()
    for _ in range(6):
        eng.record_failure("desktopBrowserNavigate")
    decision = eng.should_retry(MYRAAError.timeout("x"), 0, tool="desktopBrowserNavigate", subsystem="browser")
    assert decision.action is RetryAction.COOLDOWN


# ---------------------------------------------------------------------------
# CommandDispatcher wiring: canonical retry decision attached to errors
# ---------------------------------------------------------------------------

def test_dispatch_error_carries_retry_decision():
    from desktop_agent.main import CommandDispatcher, ExecuteRequest
    req = ExecuteRequest(tool="__missing_tool__", args={}, request_id="f7-req")
    resp = CommandDispatcher.dispatch(req)
    assert resp.ok is False
    err = resp.meta["error"]
    assert err["category"] == "invalid_request"
    assert "retry" in err
    assert err["retry"]["action"] == "stop"
    assert err["retry"]["reason"]


def test_dispatch_tool_failure_retry_decision():
    from desktop_agent.main import CommandDispatcher, ExecuteRequest
    req = ExecuteRequest(tool="readFile", args={"path": "C:/__f7_missing__.txt"}, request_id="f7-req2")
    resp = CommandDispatcher.dispatch(req)
    assert resp.ok is False
    err = resp.meta["error"]
    assert err["category"] == "tool_failure"
    assert "retry" in err
    assert err["retry"]["action"] == "stop"


# ---------------------------------------------------------------------------
# Regression: "retryable == False  =>  ZERO AUTOMATIC RETRIES"
#
# Defect: MYRAAError.recoverable defaults to True, and __post_init__ derived
# `retryable` from that legacy default. Every bare MYRAAError therefore became
# "retryable" — including categories the taxonomy explicitly declares
# non-retryable. classify_failure() honoured that flag for tool_failure /
# unknown_error, so the ONE authoritative recovery policy auto-retried
# failures it should have stopped on.
# ---------------------------------------------------------------------------


def test_bare_tool_failure_is_not_retryable():
    engine = RecoveryEngine()
    err = MYRAAError(category=ErrorCategory.TOOL_FAILURE, message="boom")
    assert err.retryable is False, \
        "a bare tool_failure must not inherit retryability from the legacy " \
        "recoverable=True default"
    assert classify_failure(err) is FailureClass.PERMANENT
    assert engine.should_retry(err, 0, tool="readFile").action is RetryAction.STOP


def test_explicit_retryable_opt_in_still_works():
    engine = RecoveryEngine()
    err = MYRAAError(category=ErrorCategory.TOOL_FAILURE, message="flaky", retryable=True)
    assert err.retryable is True
    assert classify_failure(err) is FailureClass.TRANSIENT
    assert engine.should_retry(err, 0, tool="readFile").action is RetryAction.RETRY


def test_explicit_retryable_opt_out_is_absolute():
    engine = RecoveryEngine()
    err = MYRAAError(category=ErrorCategory.TIMEOUT, message="slow", retryable=False)
    assert err.retryable is False
    assert engine.should_retry(err, 0, tool="readFile").action is RetryAction.STOP


def test_legacy_recoverable_false_is_an_opt_out():
    engine = RecoveryEngine()
    err = MYRAAError(category=ErrorCategory.TIMEOUT, message="slow", recoverable=False)
    assert err.retryable is False, "recoverable=False must remain a hard opt-out"
    assert engine.should_retry(err, 0, tool="readFile").action is RetryAction.STOP


def test_declared_retryable_categories_remain_retryable():
    engine = RecoveryEngine()
    # Verification failures are retryable but their recovery action is REPLAN
    # (re-verify, don't blindly repeat) — see the authoritative policy.
    for factory, expected in (
        (MYRAAError.timeout, RetryAction.RETRY),
        (MYRAAError.rate_limit, RetryAction.RETRY),
        (MYRAAError.provider_unavailable, RetryAction.RETRY),
        (MYRAAError.context_failure, RetryAction.RETRY),
        (MYRAAError.verification_failure, RetryAction.REPLAN),
    ):
        err = factory("transient")
        assert err.retryable is True, f"{factory.__name__} must stay retryable"
        assert engine.should_retry(err, 0, tool="readFile").action is expected, \
            f"{factory.__name__} should map to {expected}"


# ---------------------------------------------------------------------------
# Orchestrator RetryEngine: a non-retryable dispatch response is NEVER
# auto-retried, regardless of the retry budget (regression for the
# "recoverable=false, retryable=false yet retried" defect).
# ---------------------------------------------------------------------------


def _orchestrator_retry_engine():
    from desktop_agent.brain.orchestrator.orchestrator import RetryEngine, RetryPolicy
    import threading
    return RetryEngine(RetryPolicy(max_retries=3), threading.Event())


class _FakeMetrics:
    def increment(self, name, *a, **k):
        pass


class _FakeEventBus:
    def emit(self, *a, **k):
        pass


def test_orchestrator_does_not_retry_non_retryable_response():
    from desktop_agent.main import ExecuteResponse
    engine = _orchestrator_retry_engine()

    class _FakeStep:
        id = "s1"
        action = "readFile"

    calls = {"n": 0}

    def dispatch(step):
        calls["n"] += 1
        # A canonical non-retryable error (recovery decision action=stop).
        return ExecuteResponse(
            ok=False,
            tool="readFile",
            error="Permission denied",
            meta={"error": {"retry": {"action": "stop", "reason": "not retryable"}}},
        )

    resp = engine.execute_with_retry(_FakeStep(), dispatch, _FakeEventBus(), _FakeMetrics())
    assert resp.ok is False
    assert calls["n"] == 1, "non-retryable response must be dispatched exactly once"


def test_orchestrator_retries_retryable_response_up_to_budget():
    from desktop_agent.main import ExecuteResponse
    engine = _orchestrator_retry_engine()

    class _FakeStep:
        id = "s1"
        action = "readFile"

    calls = {"n": 0}

    def dispatch(step):
        calls["n"] += 1
        # A retryable (transient) error — recovery decision action=retry.
        return ExecuteResponse(
            ok=False,
            tool="readFile",
            error="timeout",
            meta={"error": {"retry": {"action": "retry", "reason": "transient"}}},
        )

    engine.execute_with_retry(_FakeStep(), dispatch, _FakeEventBus(), _FakeMetrics())
    # max_retries=3 → attempts 0,1,2,3 = 4 dispatch calls then give up.
    assert calls["n"] == 4