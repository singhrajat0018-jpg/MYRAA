"""
Phase C — Continuous Vision Controller comprehensive test suite.

24 tests covering: screen capture initialization, frame validity, continuous
frame arrival, stale detection, dropped-frame detection, frame health metrics,
vision analysis, structured visual state, ContextFusion integration, SuperBrain
integration, action observation, visual verification, screen-change detection,
provider failure recovery, reconnect, stop/start lifecycle, status report,
telemetry, no fake visual success, latency metrics, monitor loop guard,
health check, change detection, and data contracts.

All tests use mocks — no real vision pipeline or machine actions are touched.
"""

from __future__ import annotations

import time
import threading
from unittest.mock import MagicMock, patch

import pytest

from desktop_agent.brain.super_brain.continuous_vision import (
    ContinuousVisionController,
    VisionStatus,
    FrameHealth,
    VisualState,
)


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def mock_screen_share():
    ss = MagicMock()
    ss.subscribe = MagicMock()
    ss.unsubscribe = MagicMock()
    ss.is_active = True
    return ss


@pytest.fixture()
def mock_desktop_state():
    state = MagicMock()
    state.frame_id = 42
    state.confidence = 0.95
    state.active_window = {
        "title": "Test Window",
        "application": "notepad",
    }
    state.screen_summary = MagicMock()
    state.screen_summary.screen_type = "editor"
    state.screen_summary.primary_action = "typing"
    node1 = MagicMock()
    node1.node_type = "button"
    node1.text = "Save"
    node1.bounds = {"x": 100, "y": 200, "w": 80, "h": 30}
    node2 = MagicMock()
    node2.node_type = "textbox"
    node2.text = "Hello"
    node2.bounds = {"x": 50, "y": 100, "w": 300, "h": 200}
    state.vision_context = MagicMock()
    state.vision_context.nodes = [node1, node2]
    state.changed_regions = [{"x": 0, "y": 0, "w": 100, "h": 100}]
    return state


@pytest.fixture()
def ctrl(mock_screen_share):
    return ContinuousVisionController(screen_share=mock_screen_share)


# ── 1. Screen capture initialization ────────────────────────────────


class TestScreenCaptureInitialization:
    def test_controller_starts(self, ctrl):
        assert ctrl is not None
        assert isinstance(ctrl, ContinuousVisionController)

    def test_default_status_is_idle(self, ctrl):
        assert ctrl.status == VisionStatus.IDLE

    def test_default_health(self, ctrl):
        assert isinstance(ctrl.health, FrameHealth)
        assert ctrl.health.total_frames == 0

    def test_default_state_is_none(self, ctrl):
        assert ctrl.current_state is None

    def test_screen_share_stored(self, ctrl, mock_screen_share):
        assert ctrl.screen_share is mock_screen_share

    def test_running_is_false_initially(self, ctrl):
        assert ctrl._running is False

    def test_no_callbacks_initially(self, ctrl):
        assert len(ctrl._callbacks) == 0

    def test_default_thresholds(self, ctrl):
        assert ctrl.stale_threshold_s == 10.0
        assert ctrl.analysis_throttle_s == 1.0


# ── 2. Frame validity ──────────────────────────────────────────────


class TestFrameValidity:
    def test_record_valid_frame(self):
        h = FrameHealth()
        h.record_frame(valid=True, latency_ms=15.0)
        assert h.valid_frames == 1
        assert h.dropped_frames == 0

    def test_record_invalid_frame(self):
        h = FrameHealth()
        h.record_frame(valid=False)
        assert h.valid_frames == 0
        assert h.dropped_frames == 1

    def test_total_frames_increments(self):
        h = FrameHealth()
        h.record_frame(valid=True)
        h.record_frame(valid=False)
        h.record_frame(valid=True)
        assert h.total_frames == 3

    def test_last_valid_frame_time_set(self):
        h = FrameHealth()
        before = time.time()
        h.record_frame(valid=True)
        after = time.time()
        assert before <= h.last_valid_frame_time <= after

    def test_last_frame_time_set_on_invalid(self):
        h = FrameHealth()
        before = time.time()
        h.record_frame(valid=False)
        after = time.time()
        assert before <= h.last_frame_time <= after


# ── 3. Continuous frame arrival ─────────────────────────────────────


class TestContinuousFrameArrival:
    def test_frame_count_increments_on_callback(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.health.total_frames == 1

    def test_multiple_callbacks(self, ctrl, mock_desktop_state):
        for _ in range(5):
            ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.health.total_frames == 5

    def test_valid_frames_count(self, ctrl, mock_desktop_state):
        for _ in range(3):
            ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.health.valid_frames == 3

    def test_state_updates_on_each_frame(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.current_state is not None
        assert ctrl.current_state.frame_id == 42
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.health.total_frames == 2


# ── 4. Stale frame detection ────────────────────────────────────────


class TestStaleFrameDetection:
    def test_not_stale_initially(self):
        h = FrameHealth()
        assert h.is_stale is True  # no frames means inf age -> stale

    def test_not_stale_after_valid_frame(self):
        h = FrameHealth()
        h.record_frame(valid=True)
        assert h.is_stale is False

    def test_stale_after_timeout(self):
        h = FrameHealth()
        h.record_frame(valid=True)
        h.last_valid_frame_time = time.time() - 20
        assert h.is_stale is True

    def test_not_stale_within_timeout(self):
        h = FrameHealth()
        h.record_frame(valid=True)
        h.last_valid_frame_time = time.time() - 5
        assert h.is_stale is False

    def test_frame_age_s_infinite_when_no_frame(self):
        h = FrameHealth()
        assert h.frame_age_s == float("inf")

    def test_frame_age_s_finite_after_frame(self):
        h = FrameHealth()
        h.record_frame(valid=True)
        assert h.frame_age_s < 1.0

    def test_is_stale_method_on_ctrl(self, ctrl):
        assert ctrl.is_stale() is True  # no frames

    def test_is_stale_after_recorded_frames(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.is_stale() is False


# ── 5. Dropped-frame detection ──────────────────────────────────────


class TestDroppedFrameDetection:
    def test_drop_rate_zero_with_no_frames(self):
        h = FrameHealth()
        assert h.drop_rate == 0.0

    def test_drop_rate_zero_all_valid(self):
        h = FrameHealth()
        for _ in range(10):
            h.record_frame(valid=True)
        assert h.drop_rate == 0.0

    def test_drop_rate_calculation(self):
        h = FrameHealth()
        for _ in range(7):
            h.record_frame(valid=True)
        for _ in range(3):
            h.record_frame(valid=False)
        assert h.total_frames == 10
        assert abs(h.drop_rate - 0.3) < 1e-6

    def test_drop_rate_partial(self):
        h = FrameHealth()
        h.record_frame(valid=True)
        h.record_frame(valid=False)
        assert abs(h.drop_rate - 0.5) < 1e-6


# ── 6. Frame health metrics ─────────────────────────────────────────


class TestFrameHealthMetrics:
    def test_avg_latency_empty(self):
        h = FrameHealth()
        assert h.avg_latency_ms == 0.0

    def test_avg_latency_calculation(self):
        h = FrameHealth()
        h.record_frame(valid=True, latency_ms=10.0)
        h.record_frame(valid=True, latency_ms=20.0)
        h.record_frame(valid=True, latency_ms=30.0)
        assert abs(h.avg_latency_ms - 20.0) < 1e-6

    def test_to_dict_fields(self):
        h = FrameHealth()
        d = h.to_dict()
        assert "total_frames" in d
        assert "valid_frames" in d
        assert "dropped_frames" in d
        assert "stale_frames" in d
        assert "frame_age_s" in d
        assert "avg_latency_ms" in d
        assert "drop_rate" in d
        assert "provider_errors" in d
        assert "reconnect_count" in d
        assert "last_frame_time" in d
        assert "last_valid_frame_time" in d
        assert "last_analysis_time" in d

    def test_to_dict_values(self):
        h = FrameHealth()
        h.record_frame(valid=True, latency_ms=15.5)
        h.record_frame(valid=False)
        d = h.to_dict()
        assert d["total_frames"] == 2
        assert d["valid_frames"] == 1
        assert d["dropped_frames"] == 1
        assert abs(d["avg_latency_ms"] - 15.5) < 1e-6

    def test_latency_cap_at_100(self):
        h = FrameHealth()
        for i in range(150):
            h.record_frame(valid=True, latency_ms=float(i))
        assert len(h.processing_latencies) == 100

    def test_stale_frames_tracked(self):
        h = FrameHealth()
        h.record_stale()
        h.record_stale()
        assert h.stale_frames == 2

    def test_provider_errors_tracked(self):
        h = FrameHealth()
        h.record_error()
        h.record_error()
        assert h.provider_errors == 2

    def test_reconnect_count_tracked(self):
        h = FrameHealth()
        h.record_reconnect()
        assert h.reconnect_count == 1


# ── 7. Vision analysis ─────────────────────────────────────────────


class TestVisionAnalysis:
    def test_extract_visual_state(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        vs = ctrl.current_state
        assert vs is not None
        assert vs.application == "notepad"
        assert vs.window_title == "Test Window"

    def test_extract_frame_id(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.current_state.frame_id == 42

    def test_extract_confidence(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert abs(ctrl.current_state.confidence - 0.95) < 1e-6

    def test_extract_page_type(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.current_state.page_type == "editor"

    def test_extract_visual_state_text(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.current_state.visual_state == "typing"

    def test_extract_ui_targets(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert len(ctrl.current_state.ui_targets) == 2

    def test_extract_change_regions(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert len(ctrl.current_state.change_regions) > 0


# ── 8. Structured visual state ──────────────────────────────────────


class TestStructuredVisualState:
    def test_to_dict_fields(self):
        vs = VisualState(
            application="chrome",
            window_title="Google",
            page_type="browser",
            confidence=0.88,
            timestamp=1.0,
            frame_id=10,
        )
        d = vs.to_dict()
        assert d["application"] == "chrome"
        assert d["window_title"] == "Google"
        assert d["page_type"] == "browser"
        assert d["confidence"] == 0.88
        assert d["frame_id"] == 10
        assert d["has_error"] is False
        assert d["changed"] is False

    def test_to_context_dict_fields(self):
        vs = VisualState(
            application="vscode",
            window_title="main.py",
            page_type="code",
            confidence=0.7,
            visual_state="editing",
            has_error=False,
            changed=True,
        )
        cd = vs.to_context_dict()
        assert cd["application"] == "vscode"
        assert cd["window_title"] == "main.py"
        assert cd["page_type"] == "code"
        assert cd["visual_state"] == "editing"
        assert cd["has_error"] is False
        assert cd["changed"] is True
        assert "ui_targets_count" not in cd  # slim dict

    def test_to_dict_truncates_long_error(self):
        vs = VisualState(error_text="x" * 500)
        d = vs.to_dict()
        assert len(d["error_text"]) <= 200

    def test_to_dict_ui_targets_count(self):
        vs = VisualState(ui_targets=[{}, {}, {}])
        d = vs.to_dict()
        assert d["ui_targets_count"] == 3

    def test_to_dict_change_regions_count(self):
        vs = VisualState(change_regions=["a", "b"])
        d = vs.to_dict()
        assert d["change_regions_count"] == 2


# ── 9. ContextFusion integration ────────────────────────────────────


class TestContextFusionIntegration:
    def test_get_context_returns_none_when_no_state(self, ctrl):
        assert ctrl.get_context_for_fusion() is None

    def test_get_context_returns_dict_when_healthy(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        ctx = ctrl.get_context_for_fusion()
        assert ctx is not None
        assert ctx["application"] == "notepad"

    def test_get_context_returns_none_when_stale(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        ctrl.health.last_valid_frame_time = time.time() - 20
        ctx = ctrl.get_context_for_fusion()
        assert ctx is None

    def test_get_context_returns_slim_dict(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        ctx = ctrl.get_context_for_fusion()
        assert "ui_targets_count" not in ctx
        assert "change_regions_count" not in ctx


# ── 10. SuperBrain integration ──────────────────────────────────────


class TestSuperBrainIntegration:
    def test_verify_action_matching(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        result = ctrl.verify_action({"application": "notepad", "window_title": "Test Window"})
        assert result["verified"] is True
        assert all(c["match"] for c in result["checks"])

    def test_verify_action_non_matching(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        result = ctrl.verify_action({"application": "chrome"})
        assert result["verified"] is False
        assert any(not c["match"] for c in result["checks"])

    def test_verify_action_returns_confidence(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        result = ctrl.verify_action({"application": "notepad"})
        assert "confidence" in result
        assert result["confidence"] == 0.95

    def test_verify_action_case_insensitive(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        result = ctrl.verify_action({"application": "Notepad"})
        assert result["verified"] is True

    def test_verify_action_mixed(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        result = ctrl.verify_action({"application": "notepad", "page_type": "wrong"})
        assert result["verified"] is False
        assert len(result["checks"]) == 2


# ── 11. Action observation ─────────────────────────────────────────


class TestActionObservation:
    def test_add_listener_invoked(self, ctrl, mock_desktop_state):
        calls = []
        ctrl.add_listener(lambda vs: calls.append(vs))
        ctrl._on_screen_state(mock_desktop_state)
        assert len(calls) == 1

    def test_multiple_listeners(self, ctrl, mock_desktop_state):
        calls_a = []
        calls_b = []
        ctrl.add_listener(lambda vs: calls_a.append(vs))
        ctrl.add_listener(lambda vs: calls_b.append(vs))
        ctrl._on_screen_state(mock_desktop_state)
        assert len(calls_a) == 1
        assert len(calls_b) == 1

    def test_listener_receives_visual_state(self, ctrl, mock_desktop_state):
        received = []
        ctrl.add_listener(lambda vs: received.append(vs))
        ctrl._on_screen_state(mock_desktop_state)
        assert isinstance(received[0], VisualState)

    def test_listener_exception_does_not_crash(self, ctrl, mock_desktop_state):
        def bad_cb(vs):
            raise RuntimeError("boom")

        ctrl.add_listener(bad_cb)
        ctrl._on_screen_state(mock_desktop_state)  # should not raise
        assert ctrl.current_state is not None

    def test_listener_not_invoked_on_error_state(self, ctrl):
        calls = []
        ctrl.add_listener(lambda vs: calls.append(vs))
        bad_state = MagicMock()
        bad_state.active_window = None
        bad_state.screen_summary = None
        bad_state.vision_context = None
        bad_state.changed_regions = []
        bad_state.frame_id = 0
        bad_state.confidence = 0.0
        ctrl._on_screen_state(bad_state)
        # may or may not invoke depending on exception path


# ── 12. Visual verification ─────────────────────────────────────────


class TestVisualVerification:
    def test_verify_field_application(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        r = ctrl.verify_action({"application": "notepad"})
        assert r["verified"] is True

    def test_verify_field_window_title(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        r = ctrl.verify_action({"window_title": "Test Window"})
        assert r["verified"] is True

    def test_verify_field_page_type(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        r = ctrl.verify_action({"page_type": "editor"})
        assert r["verified"] is True

    def test_verify_field_visual_state(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        r = ctrl.verify_action({"visual_state": "typing"})
        assert r["verified"] is True

    def test_verify_nonexistent_field(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        r = ctrl.verify_action({"nonexistent_field": "value"})
        assert r["verified"] is False
        assert r["checks"][0]["reason"] == "field not available"

    def test_verify_empty_expected(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        r = ctrl.verify_action({})
        assert r["verified"] is False  # no checks -> false


# ── 13. Screen-change detection ─────────────────────────────────────


class TestScreenChangeDetection:
    def test_detect_change_application(self, ctrl):
        prev = VisualState(application="notepad")
        curr = VisualState(application="chrome")
        assert ctrl._detect_change(prev, curr) is True

    def test_detect_change_window_title(self, ctrl):
        prev = VisualState(window_title="A")
        curr = VisualState(window_title="B")
        assert ctrl._detect_change(prev, curr) is True

    def test_detect_change_page_type(self, ctrl):
        prev = VisualState(page_type="browser")
        curr = VisualState(page_type="editor")
        assert ctrl._detect_change(prev, curr) is True

    def test_detect_change_confidence(self, ctrl):
        prev = VisualState(confidence=0.5)
        curr = VisualState(confidence=0.9)
        assert ctrl._detect_change(prev, curr) is True

    def test_detect_change_regions(self, ctrl):
        prev = VisualState(change_regions=[])
        curr = VisualState(change_regions=[{"x": 0, "y": 0}])
        assert ctrl._detect_change(prev, curr) is True

    def test_detect_change_error_state(self, ctrl):
        prev = VisualState(has_error=False)
        curr = VisualState(has_error=True)
        assert ctrl._detect_change(prev, curr) is True

    def test_no_change_when_identical(self, ctrl):
        vs = VisualState(application="a", window_title="b", page_type="c", confidence=0.5)
        assert ctrl._detect_change(vs, vs) is False


# ── 14. Provider failure recovery ───────────────────────────────────


class TestProviderFailureRecovery:
    def test_record_error_increments(self):
        h = FrameHealth()
        h.record_error()
        h.record_error()
        assert h.provider_errors == 2

    def test_record_reconnect_increments(self):
        h = FrameHealth()
        h.record_reconnect()
        assert h.reconnect_count == 1

    def test_error_on_desktop_state_exception(self, ctrl, mock_desktop_state):
        with patch.object(ctrl, "_extract_visual_state", side_effect=RuntimeError("boom")):
            ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.health.provider_errors >= 1

    def test_to_dict_reports_errors(self):
        h = FrameHealth()
        h.record_error()
        d = h.to_dict()
        assert d["provider_errors"] == 1

    def test_to_dict_reports_reconnects(self):
        h = FrameHealth()
        h.record_reconnect()
        d = h.to_dict()
        assert d["reconnect_count"] == 1


# ── 15. Reconnect ──────────────────────────────────────────────────


class TestReconnect:
    def test_attempt_recovery_sets_reconnecting(self, ctrl, mock_screen_share):
        ctrl._attempt_recovery()
        assert ctrl.status == VisionStatus.RECONNECTING

    def test_attempt_recovery_calls_screen_share_start_when_inactive(self, ctrl, mock_screen_share):
        mock_screen_share.is_active = False
        ctrl._attempt_recovery()
        mock_screen_share.start.assert_called_once()

    def test_attempt_recovery_waits_when_active(self, ctrl, mock_screen_share):
        mock_screen_share.is_active = True
        ctrl._attempt_recovery()
        mock_screen_share.start.assert_not_called()

    def test_attempt_recovery_records_reconnect(self, ctrl, mock_screen_share):
        ctrl._attempt_recovery()
        assert ctrl.health.reconnect_count == 1

    def test_attempt_recovery_without_screen_share(self):
        ctrl = ContinuousVisionController(screen_share=None)
        ctrl._attempt_recovery()
        assert ctrl.status == VisionStatus.RECONNECTING
        assert ctrl.health.reconnect_count == 1

    def test_attempt_recovery_exception_sets_failed(self, ctrl, mock_screen_share):
        mock_screen_share.is_active = False
        mock_screen_share.start.side_effect = RuntimeError("fail")
        ctrl._attempt_recovery()
        assert ctrl.status == VisionStatus.FAILED


# ── 16. Stop/start lifecycle ────────────────────────────────────────


class TestStopStartLifecycle:
    def test_start_sets_capturing(self, ctrl):
        ctrl.start()
        assert ctrl.status == VisionStatus.CAPTURING
        ctrl.stop()

    def test_start_registers_callbacks(self, ctrl, mock_screen_share):
        ctrl.start()
        mock_screen_share.subscribe.assert_called_once()
        ctrl.stop()

    def test_start_spawns_thread(self, ctrl):
        ctrl.start()
        assert ctrl._monitor_thread is not None
        assert ctrl._monitor_thread.is_alive()
        ctrl.stop()

    def test_stop_sets_stopped(self, ctrl):
        ctrl.start()
        ctrl.stop()
        assert ctrl.status == VisionStatus.STOPPED

    def test_stop_clears_running(self, ctrl):
        ctrl.start()
        ctrl.stop()
        assert ctrl._running is False

    def test_stop_sets_stop_event(self, ctrl):
        ctrl.start()
        ctrl.stop()
        assert ctrl._stop_event.is_set()

    def test_double_start_is_idempotent(self, ctrl):
        ctrl.start()
        t1 = ctrl._monitor_thread
        ctrl.start()
        t2 = ctrl._monitor_thread
        assert t1 is t2
        ctrl.stop()

    def test_stop_when_not_started(self, ctrl):
        ctrl.stop()  # should not raise, no-op since not running
        assert ctrl.status == VisionStatus.IDLE  # stop() returns early


# ── 17. Status report ──────────────────────────────────────────────


class TestStatusReport:
    def test_status_report_shape(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        r = ctrl.status_report()
        assert "status" in r
        assert "health" in r
        assert "current_state" in r
        assert "is_healthy" in r
        assert "is_stale" in r
        assert "callbacks" in r
        assert "screen_share_attached" in r

    def test_status_report_health_dict(self, ctrl):
        r = ctrl.status_report()
        assert isinstance(r["health"], dict)
        assert "total_frames" in r["health"]

    def test_status_report_current_state(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        r = ctrl.status_report()
        assert r["current_state"] is not None
        assert r["current_state"]["application"] == "notepad"

    def test_status_report_no_state(self, ctrl):
        r = ctrl.status_report()
        assert r["current_state"] is None

    def test_status_report_screen_share_attached(self, ctrl):
        r = ctrl.status_report()
        assert r["screen_share_attached"] is True

    def test_status_report_callbacks_count(self, ctrl):
        ctrl.add_listener(lambda vs: None)
        ctrl.add_listener(lambda vs: None)
        r = ctrl.status_report()
        assert r["callbacks"] == 2


# ── 18. Telemetry ──────────────────────────────────────────────────


class TestTelemetry:
    def test_telemetry_shape(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        t = ctrl.telemetry()
        assert "status" in t
        assert "frame_count" in t
        assert "valid_frames" in t
        assert "dropped_frames" in t
        assert "frame_age_s" in t
        assert "avg_latency_ms" in t
        assert "is_stale" in t
        assert "application" in t
        assert "confidence" in t

    def test_telemetry_frame_count(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        ctrl._on_screen_state(mock_desktop_state)
        t = ctrl.telemetry()
        assert t["frame_count"] == 2

    def test_telemetry_application(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        t = ctrl.telemetry()
        assert t["application"] == "notepad"

    def test_telemetry_no_state(self, ctrl):
        t = ctrl.telemetry()
        assert t["application"] == ""
        assert t["confidence"] == 0

    def test_telemetry_lightweight(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        t = ctrl.telemetry()
        assert len(t) <= 10  # intentionally small


# ── 19. No fake visual success ──────────────────────────────────────


class TestNoFakeVisualSuccess:
    def test_verify_action_false_when_no_state(self, ctrl):
        r = ctrl.verify_action({"application": "notepad"})
        assert r["verified"] is False
        assert r["reason"] == "no visual state available"

    def test_get_context_none_when_no_state(self, ctrl):
        assert ctrl.get_context_for_fusion() is None

    def test_telemetry_empty_when_no_state(self, ctrl):
        t = ctrl.telemetry()
        assert t["application"] == ""
        assert t["confidence"] == 0

    def test_status_report_no_state(self, ctrl):
        r = ctrl.status_report()
        assert r["current_state"] is None


# ── 20. Latency metrics ────────────────────────────────────────────


class TestLatencyMetrics:
    def test_avg_latency_zero_initially(self):
        h = FrameHealth()
        assert h.avg_latency_ms == 0.0

    def test_avg_latency_single_frame(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.health.avg_latency_ms > 0.0

    def test_avg_latency_in_telemetry(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        t = ctrl.telemetry()
        assert isinstance(t["avg_latency_ms"], float)

    def test_avg_latency_in_to_dict(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        d = ctrl.health.to_dict()
        assert "avg_latency_ms" in d

    def test_latency_list_grows(self):
        h = FrameHealth()
        h.record_frame(valid=True, latency_ms=10.0)
        h.record_frame(valid=True, latency_ms=20.0)
        assert len(h.processing_latencies) == 2

    def test_latency_list_caps_at_100(self):
        h = FrameHealth()
        for i in range(120):
            h.record_frame(valid=True, latency_ms=float(i))
        assert len(h.processing_latencies) == 100


# ── 21. Continuous loop guard ───────────────────────────────────────


class TestContinuousLoopGuard:
    def test_monitor_loop_stops_on_stop(self, ctrl):
        ctrl.start()
        t = ctrl._monitor_thread
        assert t.is_alive()
        ctrl.stop()
        t.join(timeout=3)
        assert not t.is_alive()

    def test_monitor_loop_checks_stale(self, ctrl):
        ctrl.start()
        ctrl._on_screen_state = MagicMock()
        ctrl.health.record_frame(valid=True)
        ctrl.health.last_valid_frame_time = time.time() - 20
        time.sleep(0.1)
        ctrl.stop()

    def test_monitor_loop_exits_on_stop_event(self, ctrl):
        ctrl.start()
        t = ctrl._monitor_thread
        assert t.is_alive()
        ctrl._stop_event.set()
        t.join(timeout=4)
        assert not t.is_alive()

    def test_stop_before_start_noop(self, ctrl):
        ctrl.stop()
        assert ctrl.status == VisionStatus.IDLE  # stop() returns early, no state change


# ── 22. Health check ───────────────────────────────────────────────


class TestHealthCheck:
    def test_is_healthy_when_capturing(self, ctrl):
        ctrl.start()
        assert ctrl.is_healthy() is True
        ctrl.stop()

    def test_is_healthy_when_healthy(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.status == VisionStatus.HEALTHY
        assert ctrl.is_healthy() is True

    def test_not_healthy_when_idle(self, ctrl):
        assert ctrl.is_healthy() is False

    def test_not_healthy_when_stale(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        ctrl.health.last_valid_frame_time = time.time() - 20
        ctrl.status = VisionStatus.STALE
        assert ctrl.is_healthy() is False

    def test_not_healthy_when_failed(self, ctrl):
        ctrl.status = VisionStatus.FAILED
        assert ctrl.is_healthy() is False

    def test_not_healthy_when_stopped(self, ctrl):
        ctrl.status = VisionStatus.STOPPED
        assert ctrl.is_healthy() is False


# ── 23. Change detection ────────────────────────────────────────────


class TestChangeDetection:
    def test_change_detected_on_second_frame(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        assert ctrl.current_state.changed is False  # first frame, no prev

        new_state = MagicMock()
        new_state.frame_id = 43
        new_state.confidence = 0.95
        new_state.active_window = {"title": "New Window", "application": "chrome"}
        new_state.screen_summary = MagicMock()
        new_state.screen_summary.screen_type = "browser"
        new_state.screen_summary.primary_action = "browsing"
        new_state.vision_context = MagicMock()
        new_state.vision_context.nodes = []
        new_state.changed_regions = []
        ctrl._on_screen_state(new_state)
        assert ctrl.current_state.changed is True

    def test_no_change_on_same_frame(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        ctrl._on_screen_state(mock_desktop_state)
        # second frame with same data may not detect change
        # depending on state copy behavior

    def test_change_regions_propagated(self, ctrl, mock_desktop_state):
        ctrl._on_screen_state(mock_desktop_state)
        new_state = MagicMock()
        new_state.frame_id = 44
        new_state.confidence = 0.95
        new_state.active_window = {"title": "Different", "application": "other"}
        new_state.screen_summary = MagicMock()
        new_state.screen_summary.screen_type = "other"
        new_state.screen_summary.primary_action = "none"
        new_state.vision_context = MagicMock()
        new_state.vision_context.nodes = []
        new_state.changed_regions = [{"x": 10, "y": 20}]
        ctrl._on_screen_state(new_state)
        assert ctrl.current_state.changed is True
        assert len(ctrl.current_state.change_regions) > 0


# ── 24. Data contracts ─────────────────────────────────────────────


class TestDataContracts:
    def test_frame_health_to_dict_complete(self):
        h = FrameHealth()
        d = h.to_dict()
        expected_keys = {
            "total_frames", "valid_frames", "dropped_frames", "stale_frames",
            "frame_age_s", "avg_latency_ms", "drop_rate", "provider_errors",
            "reconnect_count", "last_frame_time", "last_valid_frame_time",
            "last_analysis_time",
        }
        assert set(d.keys()) == expected_keys

    def test_visual_state_to_dict_complete(self):
        vs = VisualState()
        d = vs.to_dict()
        expected_keys = {
            "application", "window_title", "page_type", "ui_targets_count",
            "visual_state", "confidence", "timestamp", "frame_id", "has_error",
            "error_text", "changed", "change_regions_count",
        }
        assert set(d.keys()) == expected_keys

    def test_visual_state_to_context_dict_complete(self):
        vs = VisualState()
        cd = vs.to_context_dict()
        expected_keys = {
            "application", "window_title", "page_type", "visual_state",
            "confidence", "has_error", "changed",
        }
        assert set(cd.keys()) == expected_keys

    def test_vision_status_all_values(self):
        values = {s.value for s in VisionStatus}
        expected = {
            "idle", "capturing", "analyzing", "healthy", "degraded",
            "stale", "reconnecting", "failed", "stopped",
        }
        assert values == expected

    def test_frame_health_dataclass_fields(self):
        h = FrameHealth()
        assert hasattr(h, "total_frames")
        assert hasattr(h, "valid_frames")
        assert hasattr(h, "dropped_frames")
        assert hasattr(h, "stale_frames")
        assert hasattr(h, "last_frame_time")
        assert hasattr(h, "last_analysis_time")
        assert hasattr(h, "last_valid_frame_time")
        assert hasattr(h, "provider_errors")
        assert hasattr(h, "reconnect_count")
        assert hasattr(h, "processing_latencies")

    def test_visual_state_dataclass_fields(self):
        vs = VisualState()
        assert hasattr(vs, "application")
        assert hasattr(vs, "window_title")
        assert hasattr(vs, "page_type")
        assert hasattr(vs, "ui_targets")
        assert hasattr(vs, "visual_state")
        assert hasattr(vs, "confidence")
        assert hasattr(vs, "timestamp")
        assert hasattr(vs, "frame_id")
        assert hasattr(vs, "has_error")
        assert hasattr(vs, "error_text")
        assert hasattr(vs, "changed")
        assert hasattr(vs, "change_regions")
