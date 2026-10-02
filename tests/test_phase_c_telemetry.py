"""
Phase C tests: TelemetryRelay (desktop_agent.brain.telemetry.relay).

Covers initialization, emit/drain/stream, sanitization, bounded buffer,
event counts, thread safety, listeners, and the global singleton.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from desktop_agent.brain.telemetry.relay import (
    TelemetryRelay,
    telemetry_relay,
    REQUEST_STARTED,
    TOOL_STARTED,
    TOOL_COMPLETED,
)


def _make_relay(**kwargs) -> TelemetryRelay:
    return TelemetryRelay(**kwargs)


# ---------------------------------------------------------------------------
# 1. Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_state(self):
        relay = _make_relay()
        status = relay.status()
        assert status["ok"] is True
        assert status["buffered"] == 0
        assert status["max_events"] == 500

    def test_empty_buffer(self):
        relay = _make_relay()
        assert relay.drain() == []


# ---------------------------------------------------------------------------
# 2. emit() stores event in buffer
# ---------------------------------------------------------------------------

class TestEmitStores:
    def test_emit_stores_event(self):
        relay = _make_relay()
        event = relay.emit(TOOL_STARTED, {"tool": "takeScreenshot"})
        assert event.event_type == TOOL_STARTED
        assert relay.status()["buffered"] == 1

    def test_emit_returns_relay_event(self):
        relay = _make_relay()
        event = relay.emit(REQUEST_STARTED, {"url": "/"})
        assert event.event_type == REQUEST_STARTED
        assert event.payload == {"url": "/"}


# ---------------------------------------------------------------------------
# 3. emit() sanitizes API keys from payload
# ---------------------------------------------------------------------------

class TestSanitizeAPIKeys:
    def test_api_key_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"api_key": "sk-abc123", "safe_field": "preserved"})
        events = relay.drain()
        assert events[0]["payload"]["api_key"] == "***REDACTED***"
        assert events[0]["payload"]["safe_field"] == "preserved"

    def test_gcp_api_key_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"gcpApiKey": "real-key"})
        events = relay.drain()
        assert events[0]["payload"]["gcpApiKey"] == "***REDACTED***"


# ---------------------------------------------------------------------------
# 4. emit() sanitizes tokens from payload
# ---------------------------------------------------------------------------

class TestSanitizeTokens:
    def test_token_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"token": "bearer_xyz", "tool": "x"})
        events = relay.drain()
        assert events[0]["payload"]["token"] == "***REDACTED***"

    def test_bearer_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"authorization": "Bearer tok"})
        events = relay.drain()
        assert events[0]["payload"]["authorization"] == "***REDACTED***"

    def test_password_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"password": "secret123"})
        events = relay.drain()
        assert events[0]["payload"]["password"] == "***REDACTED***"


# ---------------------------------------------------------------------------
# 5. emit() preserves correlation IDs
# ---------------------------------------------------------------------------

class TestCorrelationIDs:
    def test_preserves_request_and_task_id(self):
        relay = _make_relay()
        relay.emit(
            TOOL_STARTED,
            {"tool": "takeScreenshot"},
            request_id="req-42",
            task_id="task-99",
        )
        events = relay.drain()
        assert events[0]["request_id"] == "req-42"
        assert events[0]["task_id"] == "task-99"

    def test_default_empty_ids(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"tool": "x"})
        events = relay.drain()
        assert events[0]["request_id"] == ""
        assert events[0]["task_id"] == ""


# ---------------------------------------------------------------------------
# 6. drain() returns all events and clears buffer
# ---------------------------------------------------------------------------

class TestDrain:
    def test_drain_returns_all_and_clears(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"a": 1})
        relay.emit(TOOL_COMPLETED, {"a": 2})
        events = relay.drain()
        assert len(events) == 2
        assert events[0]["event_type"] == TOOL_STARTED
        assert events[1]["event_type"] == TOOL_COMPLETED
        assert relay.status()["buffered"] == 0

    def test_drain_returns_dicts(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"a": 1})
        events = relay.drain()
        assert isinstance(events[0], dict)
        assert "event_type" in events[0]
        assert "payload" in events[0]
        assert "timestamp" in events[0]


# ---------------------------------------------------------------------------
# 7. drain() returns empty list when no events
# ---------------------------------------------------------------------------

class TestDrainEmpty:
    def test_drain_empty(self):
        relay = _make_relay()
        assert relay.drain() == []

    def test_drain_after_double_drain(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"a": 1})
        relay.drain()
        assert relay.drain() == []


# ---------------------------------------------------------------------------
# 8. stream(count) returns last N events without clearing
# ---------------------------------------------------------------------------

class TestStream:
    def test_returns_last_n(self):
        relay = _make_relay()
        for i in range(10):
            relay.emit(TOOL_STARTED, {"i": i})
        streamed = relay.stream(count=3)
        assert len(streamed) == 3
        assert streamed[0]["payload"]["i"] == 7
        assert streamed[2]["payload"]["i"] == 9
        assert relay.status()["buffered"] == 10

    def test_stream_does_not_clear_buffer(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"a": 1})
        relay.emit(TOOL_COMPLETED, {"a": 2})
        relay.stream(count=1)
        assert relay.status()["buffered"] == 2


# ---------------------------------------------------------------------------
# 9. stream() returns all when count > buffer size
# ---------------------------------------------------------------------------

class TestStreamOverflow:
    def test_returns_all_when_count_exceeds_buffer(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"a": 1})
        relay.emit(TOOL_COMPLETED, {"a": 2})
        streamed = relay.stream(count=100)
        assert len(streamed) == 2

    def test_stream_empty_buffer(self):
        relay = _make_relay()
        assert relay.stream(count=10) == []


# ---------------------------------------------------------------------------
# 10. status() returns health dict with correct fields
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_fields(self):
        relay = _make_relay()
        s = relay.status()
        assert "ok" in s
        assert "buffered" in s
        assert "max_events" in s
        assert "event_counts" in s
        assert "uptime_seconds" in s
        assert s["uptime_seconds"] >= 0
        assert s["ok"] is True

    def test_status_reflects_counts(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {})
        relay.emit(TOOL_STARTED, {})
        relay.emit(TOOL_COMPLETED, {})
        s = relay.status()
        assert s["event_counts"][TOOL_STARTED] == 2
        assert s["event_counts"][TOOL_COMPLETED] == 1


# ---------------------------------------------------------------------------
# 11. Bounded buffer (emit 600 events, buffer stays at 500)
# ---------------------------------------------------------------------------

class TestBoundedBuffer:
    def test_emit_600_stays_at_500(self):
        relay = _make_relay(max_events=500)
        for i in range(600):
            relay.emit(TOOL_STARTED, {"i": i})
        s = relay.status()
        assert s["buffered"] == 500
        events = relay.drain()
        assert events[0]["payload"]["i"] == 100
        assert events[-1]["payload"]["i"] == 599

    def test_bounded_at_custom_max(self):
        relay = _make_relay(max_events=10)
        for i in range(25):
            relay.emit(TOOL_STARTED, {"i": i})
        assert relay.status()["buffered"] == 10
        events = relay.drain()
        assert events[0]["payload"]["i"] == 15


# ---------------------------------------------------------------------------
# 12. Event counts tracked per type
# ---------------------------------------------------------------------------

class TestEventCounts:
    def test_counts_tracked_per_type(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {})
        relay.emit(TOOL_STARTED, {})
        relay.emit(REQUEST_STARTED, {})
        s = relay.status()
        assert s["event_counts"][TOOL_STARTED] == 2
        assert s["event_counts"][REQUEST_STARTED] == 1

    def test_counts_survive_drain(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {})
        relay.drain()
        s = relay.status()
        assert s["event_counts"][TOOL_STARTED] == 1
        assert s["buffered"] == 0


# ---------------------------------------------------------------------------
# 13. Thread safety (concurrent emit)
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_emit(self):
        relay = _make_relay(max_events=2000)
        errors = []

        def worker(n):
            try:
                for i in range(200):
                    relay.emit(TOOL_STARTED, {"n": n, "i": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        s = relay.status()
        assert s["event_counts"][TOOL_STARTED] == 1000
        assert s["buffered"] == 1000

    def test_concurrent_emit_and_drain(self):
        relay = _make_relay(max_events=2000)
        errors = []

        def emitter():
            try:
                for i in range(500):
                    relay.emit(TOOL_STARTED, {"i": i})
            except Exception as e:
                errors.append(e)

        def drainer():
            try:
                for _ in range(50):
                    relay.drain()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=emitter),
            threading.Thread(target=emitter),
            threading.Thread(target=drainer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ---------------------------------------------------------------------------
# 14. Global singleton exists
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_singleton_is_instance(self):
        assert isinstance(telemetry_relay, TelemetryRelay)

    def test_singleton_has_expected_methods(self):
        assert hasattr(telemetry_relay, "emit")
        assert hasattr(telemetry_relay, "drain")
        assert hasattr(telemetry_relay, "stream")
        assert hasattr(telemetry_relay, "status")


# ---------------------------------------------------------------------------
# 15. Listener callback invoked on emit
# ---------------------------------------------------------------------------

class TestListeners:
    def test_listener_called_on_emit(self):
        relay = _make_relay()
        cb = MagicMock()
        relay.on_event(cb)
        relay.emit(TOOL_STARTED, {"tool": "x"})
        cb.assert_called_once()
        args = cb.call_args[0]
        assert args[0] == TOOL_STARTED
        assert isinstance(args[1], dict)

    def test_multiple_listeners(self):
        relay = _make_relay()
        cb1 = MagicMock()
        cb2 = MagicMock()
        relay.on_event(cb1)
        relay.on_event(cb2)
        relay.emit(TOOL_STARTED, {})
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_remove_listener(self):
        relay = _make_relay()
        cb = MagicMock()
        relay.on_event(cb)
        relay.remove_listener(cb)
        relay.emit(TOOL_STARTED, {})
        cb.assert_not_called()

    def test_listener_exception_does_not_crash(self):
        relay = _make_relay()
        bad_cb = MagicMock(side_effect=RuntimeError("boom"))
        relay.on_event(bad_cb)
        relay.emit(TOOL_STARTED, {})
        assert relay.status()["buffered"] == 1


# ---------------------------------------------------------------------------
# 16. sanitize handles nested dicts
# ---------------------------------------------------------------------------

class TestSanitizeNested:
    def test_nested_dict_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"config": {"api_key": "secret-val", "name": "ok"}})
        events = relay.drain()
        assert events[0]["payload"]["config"]["api_key"] == "***REDACTED***"
        assert events[0]["payload"]["config"]["name"] == "ok"

    def test_deeply_nested(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"a": {"b": {"token": "tok123"}}})
        events = relay.drain()
        assert events[0]["payload"]["a"]["b"]["token"] == "***REDACTED***"


# ---------------------------------------------------------------------------
# 17. sanitize handles list values
# ---------------------------------------------------------------------------

class TestSanitizeLists:
    def test_list_of_dicts(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"items": [{"api_key": "k1"}, {"name": "n1"}]})
        events = relay.drain()
        assert events[0]["payload"]["items"][0]["api_key"] == "***REDACTED***"
        assert events[0]["payload"]["items"][1]["name"] == "n1"

    def test_list_of_strings_unchanged(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"tags": ["a", "b", "c"]})
        events = relay.drain()
        assert events[0]["payload"]["tags"] == ["a", "b", "c"]

    def test_tuple_converted_to_list(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"pair": ("a", "b")})
        events = relay.drain()
        assert events[0]["payload"]["pair"] == ["a", "b"]

    def test_tuple_with_dict_element_sanitized(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"data": [{"api_key": "secret"}, "plain"]})
        events = relay.drain()
        assert events[0]["payload"]["data"][0]["api_key"] == "***REDACTED***"
        assert events[0]["payload"]["data"][1] == "plain"


# ---------------------------------------------------------------------------
# 18. no secret leakage in sanitized output
# ---------------------------------------------------------------------------

class TestNoLeakage:
    def test_no_secret_in_serialized_output(self):
        relay = _make_relay()
        payload = {
            "api_key": "sk-super-secret-key",
            "token": "bearer-xyz-123",
            "password": "hunter2",
            "secret": "do-not-tell",
            "auth": "Basic abc",
            "credential": "cred-data",
            "safe_field": "safe_value",
            "nested": {"bearer": "token123", "data": "ok"},
            "list_field": [{"api_key": "in-list"}],
        }
        relay.emit(TOOL_STARTED, payload)
        events = relay.drain()
        serialized = str(events)

        assert "sk-super-secret-key" not in serialized
        assert "bearer-xyz-123" not in serialized
        assert "hunter2" not in serialized
        assert "do-not-tell" not in serialized
        assert "cred-data" not in serialized
        assert "token123" not in serialized
        assert "in-list" not in serialized
        assert "safe_value" in serialized

    def test_clear_and_reset_drop_listeners(self):
        relay = _make_relay()
        cb = MagicMock()
        relay.on_event(cb)
        relay.emit(TOOL_STARTED, {})
        relay.reset()
        relay.emit(TOOL_STARTED, {})
        cb.assert_called_once()


# ---------------------------------------------------------------------------
# 12. Secret redaction (comprehensive)
# ---------------------------------------------------------------------------

class TestSecretRedaction:
    """Verify all secret-like keys are redacted in payloads."""

    def test_api_key_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"api_key": "sk-abc123", "tool": "test"})
        events = relay.drain()
        assert events[0]["payload"]["api_key"] == "***REDACTED***"

    def test_token_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"auth_token": "tok_123"})
        events = relay.drain()
        assert events[0]["payload"]["auth_token"] == "***REDACTED***"

    def test_password_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"password": "secret123"})
        events = relay.drain()
        assert events[0]["payload"]["password"] == "***REDACTED***"

    def test_secret_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"my_secret": "xyz"})
        events = relay.drain()
        assert events[0]["payload"]["my_secret"] == "***REDACTED***"

    def test_bearer_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"bearer_token": "abc"})
        events = relay.drain()
        assert events[0]["payload"]["bearer_token"] == "***REDACTED***"

    def test_credential_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"credential": "c1"})
        events = relay.drain()
        assert events[0]["payload"]["credential"] == "***REDACTED***"

    def test_nested_secret_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"config": {"api_key": "sk-999", "name": "ok"}})
        events = relay.drain()
        p = events[0]["payload"]
        assert p["config"]["api_key"] == "***REDACTED***"
        assert p["config"]["name"] == "ok"

    def test_list_secret_redacted(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"items": [{"token": "t1"}, {"name": "n1"}]})
        events = relay.drain()
        items = events[0]["payload"]["items"]
        assert items[0]["token"] == "***REDACTED***"
        assert items[1]["name"] == "n1"

    def test_non_secret_preserved(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"tool": "takeScreenshot", "status": "ok"})
        events = relay.drain()
        assert events[0]["payload"]["tool"] == "takeScreenshot"
        assert events[0]["payload"]["status"] == "ok"

    def test_none_value_preserved(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"key": None})
        events = relay.drain()
        assert events[0]["payload"]["key"] is None

    def test_int_value_preserved(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"count": 42})
        events = relay.drain()
        assert events[0]["payload"]["count"] == 42


# ---------------------------------------------------------------------------
# 13. Correlation IDs
# ---------------------------------------------------------------------------

class TestCorrelationIDs:
    """Verify request_id and task_id flow through the relay."""

    def test_request_id_preserved(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"tool": "test"}, request_id="req-abc")
        events = relay.drain()
        assert events[0]["request_id"] == "req-abc"

    def test_task_id_preserved(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {"tool": "test"}, task_id="task-xyz")
        events = relay.drain()
        assert events[0]["task_id"] == "task-xyz"

    def test_both_ids_preserved(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {}, request_id="r1", task_id="t1")
        events = relay.drain()
        assert events[0]["request_id"] == "r1"
        assert events[0]["task_id"] == "t1"

    def test_default_empty_ids(self):
        relay = _make_relay()
        relay.emit(TOOL_STARTED, {})
        events = relay.drain()
        assert events[0]["request_id"] == ""
        assert events[0]["task_id"] == ""


# ---------------------------------------------------------------------------
# 14. Event type constants
# ---------------------------------------------------------------------------

class TestEventTypes:
    """Verify the expected event type constants exist."""

    def test_all_event_types_tuple(self):
        from desktop_agent.brain.telemetry.relay import ALL_EVENT_TYPES
        assert len(ALL_EVENT_TYPES) == 14

    def test_event_type_values(self):
        from desktop_agent.brain.telemetry.relay import (
            REQUEST_STARTED, ROUTE_SELECTED, MEMORY_RETRIEVED,
            PLAN_CREATED, TOOL_STARTED, TOOL_COMPLETED,
            VERIFICATION_STARTED, VERIFICATION_COMPLETED,
            RECOVERY_STARTED, AUTONOMY_STATE_CHANGED,
            VISION_STATE_CHANGED, VOICE_STATE_CHANGED,
            TASK_COMPLETED, TASK_FAILED,
        )
        assert all(isinstance(v, str) for v in [
            REQUEST_STARTED, ROUTE_SELECTED, MEMORY_RETRIEVED,
            PLAN_CREATED, TOOL_STARTED, TOOL_COMPLETED,
            VERIFICATION_STARTED, VERIFICATION_COMPLETED,
            RECOVERY_STARTED, AUTONOMY_STATE_CHANGED,
            VISION_STATE_CHANGED, VOICE_STATE_CHANGED,
            TASK_COMPLETED, TASK_FAILED,
        ])
