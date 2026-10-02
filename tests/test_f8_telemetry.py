"""
F8 tests: observability & telemetry.

Verifies desktop_agent/brain/metrics.py's TelemetryCollector + redaction:
- canonical telemetry fields (request_id, task_id, timestamp, component,
  route, intent, domain, capability, execution_mode, reasoning_depth, provider,
  model, tool, status, latency, verification_status, recovery_attempts,
  fallback, error_category)
- derived metrics (request/success/failure counts, error rate, active tasks,
  provider/tool latency histograms, verification failures, recovery/fallback)
- automatic secret redaction in telemetry events
- bounded ring buffer (no unbounded memory growth)
- correlation ids preserved
- wiring: CommandDispatcher records a telemetry event per request
"""

from __future__ import annotations

import pytest

from desktop_agent.brain.metrics import (
    TelemetryEvent,
    TelemetryCollector,
    telemetry,
    metrics_collector,
    record_system_metrics,
)


@pytest.fixture(autouse=True)
def _reset_telemetry():
    telemetry._events.clear()
    telemetry._active_tasks.clear()
    metrics_collector.reset()
    yield


# ---------------------------------------------------------------------------
# Telemetry event shape
# ---------------------------------------------------------------------------

def test_telemetry_event_all_fields():
    ev = TelemetryEvent(
        request_id="req-1", task_id="task-1", component="desktop_agent",
        route="/execute", intent="open app", domain="desktop",
        capability="application", execution_mode="direct",
        reasoning_depth="shallow", provider="gemini", model="gemini-3",
        tool="openApplication", status="ok", latency_ms=12.5,
        verification_status="verified", recovery_attempts=2, fallback="ollama",
        error_category="",
    )
    d = ev.to_dict()
    for key in [
        "request_id", "task_id", "timestamp", "component", "route", "intent",
        "domain", "capability", "execution_mode", "reasoning_depth", "provider",
        "model", "tool", "status", "latency_ms", "verification_status",
        "recovery_attempts", "fallback", "error_category",
    ]:
        assert key in d, key
    assert d["request_id"] == "req-1"
    assert d["tool"] == "openApplication"


def test_telemetry_event_redacts_secrets():
    ev = TelemetryEvent(request_id="r", component="provider", provider="gemini", model="x")
    d = ev.to_dict()
    assert "api_key" not in str(d)  # nothing leaked by default


def test_telemetry_record_redaction():
    collector = TelemetryCollector()
    collector.record(
        request_id="req-secret",
        tool="readFile",
        status="error",
        error_category="auth_failure",
        intent="api_key=sk-abcdef12345678 password=hunter2",
    )
    events = collector.get_recent()
    assert len(events) == 1
    blob = str(events[0])
    assert "sk-abcdef12345678" not in blob
    assert "hunter2" not in blob


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def test_derived_metrics_counts():
    collector = TelemetryCollector()
    collector.record(request_id="a", tool="systemInfo", status="ok", latency_ms=5)
    collector.record(request_id="b", tool="systemInfo", status="error", error_category="timeout", latency_ms=9)
    collector.record(request_id="c", tool="systemInfo", status="error", error_category="timeout", latency_ms=7)
    summary = collector.summary()
    assert summary["requests_total"] == 3
    assert summary["requests_ok"] == 1
    assert summary["requests_error"] == 2
    assert summary["errors_total"] == 2
    assert summary["error_rate_percent"] == pytest.approx(66.67, abs=0.1)
    assert metrics_collector.get_counter("errors_timeout") == 2


def test_tool_provider_latency_histograms():
    collector = TelemetryCollector()
    for _ in range(10):
        collector.record(tool="leftClick", provider="nim", latency_ms=100)
    assert metrics_collector.get_histogram_average("tool_latency_leftClick") == pytest.approx(100.0)
    assert metrics_collector.get_histogram_average("provider_latency_nim") == pytest.approx(100.0)
    assert metrics_collector.get_histogram_percentile("tool_latency_leftClick", 95) == pytest.approx(100.0)


def test_verification_and_recovery_metrics():
    collector = TelemetryCollector()
    collector.record(tool="leftClick", verification_status="failed")
    collector.record(tool="leftClick", recovery_attempts=2, fallback="ollama")
    assert metrics_collector.get_counter("verifications_failed") == 1
    assert metrics_collector.get_counter("recovery_attempts_total") == 2
    assert metrics_collector.get_counter("fallbacks_ollama") == 1


def test_active_tasks_gauge():
    collector = TelemetryCollector()
    collector.start_task("task-1", tool="systemInfo")
    collector.start_task("task-2", tool="systemInfo")
    assert collector.active_tasks == 2
    assert metrics_collector.get_gauge("active_tasks") == 2
    collector.end_task("task-1")
    assert collector.active_tasks == 1


def test_bounded_ring_buffer():
    collector = TelemetryCollector(max_events=5)
    for i in range(20):
        collector.record(request_id=f"req-{i}", tool="systemInfo", status="ok")
    events = collector.get_recent()
    assert len(events) == 5  # bounded, no unbounded growth
    assert events[-1]["request_id"] == "req-19"


# ---------------------------------------------------------------------------
# Correlation across components
# ---------------------------------------------------------------------------

def test_correlation_id_preserved_across_records():
    collector = TelemetryCollector()
    collector.record(request_id="xyz-123", task_id="abc-9", component="node", route="/execute", status="ok")
    collector.record(request_id="xyz-123", task_id="abc-9", component="desktop_agent", route="/execute", status="ok")
    collector.record(request_id="xyz-123", task_id="abc-9", component="verification", status="ok")
    events = collector.get_recent()
    assert len(events) == 3
    assert all(e["request_id"] == "xyz-123" for e in events)
    assert all(e["task_id"] == "abc-9" for e in events)


# ---------------------------------------------------------------------------
# System metrics (best-effort, must never raise)
# ---------------------------------------------------------------------------

def test_record_system_metrics_never_raises():
    record_system_metrics()  # psutil optional; must not raise


# ---------------------------------------------------------------------------
# CommandDispatcher wiring
# ---------------------------------------------------------------------------

def test_dispatch_records_telemetry():
    from desktop_agent.main import CommandDispatcher, ExecuteRequest
    telemetry._events.clear()
    telemetry._active_tasks.clear()
    metrics_collector.reset()

    resp = CommandDispatcher.dispatch(ExecuteRequest(tool="systemInfo", args={}, request_id="f8-req"))
    assert resp.ok is True
    assert resp.meta["request_id"] == "f8-req"

    events = telemetry.get_recent()
    assert len(events) == 1
    assert events[0]["request_id"] == "f8-req"
    assert events[0]["tool"] == "systemInfo"
    assert events[0]["status"] == "ok"
    assert events[0]["route"] == "/execute"
    assert events[0]["component"] == "desktop_agent"
    assert events[0]["latency_ms"] >= 0
    assert metrics_collector.get_counter("requests_total") == 1


def test_dispatch_records_error_telemetry():
    from desktop_agent.main import CommandDispatcher, ExecuteRequest
    telemetry._events.clear()
    telemetry._active_tasks.clear()
    metrics_collector.reset()

    resp = CommandDispatcher.dispatch(ExecuteRequest(tool="__nope__", args={}, request_id="f8-err"))
    assert resp.ok is False

    events = telemetry.get_recent()
    assert len(events) == 1
    assert events[0]["status"] == "error"
    assert events[0]["error_category"] == "invalid_request"


def test_dispatch_records_confirmation_telemetry():
    from desktop_agent.main import CommandDispatcher, ExecuteRequest
    telemetry._events.clear()
    telemetry._active_tasks.clear()
    metrics_collector.reset()

    resp = CommandDispatcher.dispatch(ExecuteRequest(tool="createFile", args={"path": "C:/tmp/f8_test.txt", "content": "x"}, request_id="f8-conf"))
    assert resp.ok is True
    assert resp.result.get("requires_confirmation") is True

    events = telemetry.get_recent()
    assert len(events) == 1
    assert events[0]["status"] == "confirmation"