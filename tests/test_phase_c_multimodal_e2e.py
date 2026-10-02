"""
Phase C tests: Multimodal E2E integration.

Covers voice + vision + desktop + project builder + autonomy + verification
interactions through the unified Python agent.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop
from desktop_agent.speech.voice_interface import VoiceInterface, VoiceState
from desktop_agent.brain.telemetry.relay import (
    TelemetryRelay, TOOL_STARTED, TOOL_COMPLETED,
    VISION_STATE_CHANGED, VOICE_STATE_CHANGED,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cvl_with_mock():
    cvl = ContinuousVoiceLoop()
    cvl.set_execute_callback(MagicMock(return_value={"ok": True, "response": "Done"}))
    return cvl


# ---------------------------------------------------------------------------
# 1. Voice → Brain → Execute flow
# ---------------------------------------------------------------------------

class TestVoiceBrainExecute:
    def test_voice_to_execution(self):
        cvl = _make_cvl_with_mock()
        r = cvl.on_user_transcript("open notepad")
        assert r["ok"] is True
        assert "turn_id" in r

    def test_multiple_commands_sequential(self):
        cvl = _make_cvl_with_mock()
        r1 = cvl.on_user_transcript("open notepad")
        r2 = cvl.on_user_transcript("type hello")
        assert r1["ok"] is True
        assert r2["ok"] is True
        assert cvl.status()["total_turns"] == 2


# ---------------------------------------------------------------------------
# 2. Vision state changes flow through telemetry
# ---------------------------------------------------------------------------

class TestVisionTelemetryFlow:
    def test_vision_state_change_emitted(self):
        relay = TelemetryRelay(max_events=100)
        relay.emit(VISION_STATE_CHANGED, {"state": "active", "stale": False})
        events = relay.drain()
        assert len(events) == 1
        assert events[0]["event_type"] == VISION_STATE_CHANGED
        assert events[0]["payload"]["state"] == "active"

    def test_vision_stale_detection(self):
        relay = TelemetryRelay(max_events=100)
        relay.emit(VISION_STATE_CHANGED, {"state": "stale", "stale": True})
        events = relay.drain()
        assert events[0]["payload"]["stale"] is True


# ---------------------------------------------------------------------------
# 3. Voice state changes flow through telemetry
# ---------------------------------------------------------------------------

class TestVoiceTelemetryFlow:
    def test_voice_listening_emitted(self):
        relay = TelemetryRelay(max_events=100)
        relay.emit(VOICE_STATE_CHANGED, {"state": "listening"})
        events = relay.drain()
        assert events[0]["event_type"] == VOICE_STATE_CHANGED

    def test_voice_speaking_emitted(self):
        relay = TelemetryRelay(max_events=100)
        relay.emit(VOICE_STATE_CHANGED, {"state": "speaking"})
        events = relay.drain()
        assert events[0]["payload"]["state"] == "speaking"


# ---------------------------------------------------------------------------
# 4. Telemetry + Voice + Vision combined
# ---------------------------------------------------------------------------

class TestCombinedTelemetryFlow:
    def test_mixed_event_types(self):
        relay = TelemetryRelay(max_events=100)
        relay.emit(TOOL_STARTED, {"tool": "takeScreenshot"})
        relay.emit(VISION_STATE_CHANGED, {"state": "active"})
        relay.emit(VOICE_STATE_CHANGED, {"state": "listening"})
        relay.emit(TOOL_COMPLETED, {"tool": "takeScreenshot", "status": "ok"})
        events = relay.drain()
        assert len(events) == 4
        types = [e["event_type"] for e in events]
        assert TOOL_STARTED in types
        assert TOOL_COMPLETED in types

    def test_correlation_id_flows_through_all(self):
        relay = TelemetryRelay(max_events=100)
        rid = "req-vision-001"
        relay.emit(TOOL_STARTED, {"tool": "takeScreenshot"}, request_id=rid)
        relay.emit(VISION_STATE_CHANGED, {"state": "changed"}, request_id=rid)
        events = relay.drain()
        for e in events:
            assert e["request_id"] == rid


# ---------------------------------------------------------------------------
# 5. Voice interruption during vision observation
# ---------------------------------------------------------------------------

class TestVoiceVisionInterruption:
    def test_barge_in_cancels_turn(self):
        cvl = _make_cvl_with_mock()
        cvl.on_user_transcript("slow task")
        r = cvl.on_interruption()
        assert r["ok"] is True
        assert cvl.status()["total_interruptions"] == 1

    def test_resume_after_interruption(self):
        cvl = _make_cvl_with_mock()
        cvl.on_user_transcript("task1")
        cvl.on_interruption()
        r = cvl.on_user_transcript("task2")
        assert r["ok"] is True
        assert cvl.status()["total_turns"] == 2


# ---------------------------------------------------------------------------
# 6. Autonomy + vision observation telemetry
# ---------------------------------------------------------------------------

class TestAutonomyVisionTelemetry:
    def test_autonomy_state_change(self):
        relay = TelemetryRelay(max_events=100)
        relay.emit("autonomy_state_changed", {"state": "running", "goal_id": "g1"})
        events = relay.drain()
        assert events[0]["payload"]["goal_id"] == "g1"

    def test_autonomy_vision_combined(self):
        relay = TelemetryRelay(max_events=100)
        relay.emit("autonomy_state_changed", {"state": "running"})
        relay.emit(VISION_STATE_CHANGED, {"state": "monitoring"})
        events = relay.drain()
        assert len(events) == 2


# ---------------------------------------------------------------------------
# 7. Full pipeline simulation (mocked)
# ---------------------------------------------------------------------------

class TestFullPipelineSimulation:
    """Simulate a complete voice→brain→execute→verify→TTS pipeline."""

    def test_voice_command_to_tts(self):
        from unittest.mock import MagicMock
        cvl = ContinuousVoiceLoop()
        execute_results = []

        def mock_execute(transcript):
            execute_results.append(transcript)
            return {"ok": True, "response": f"Executed: {transcript}"}

        cvl.set_execute_callback(mock_execute)
        tts_log = []
        cvl.set_tts_callback(lambda text: tts_log.append(text))

        cvl.on_user_transcript("take a screenshot")
        assert len(execute_results) == 1
        assert len(tts_log) == 1
        assert "Executed:" in tts_log[0]

    def test_rapid_commands_with_dedup(self):
        cvl = _make_cvl_with_mock()
        cvl.on_user_transcript("unique command")
        r = cvl.on_user_transcript("unique command")
        assert r["ok"] is False
        assert r["error"] == "duplicate_transcript"
        assert cvl.status()["total_turns"] == 1

    def test_consecutive_error_disconnection(self):
        from unittest.mock import MagicMock
        cvl = ContinuousVoiceLoop()
        cvl.set_execute_callback(MagicMock(side_effect=RuntimeError("always fail")))

        for i in range(MAX_CONSECUTIVE_ERRORS):
            r = cvl.on_user_transcript(f"fail {i}")

        assert r.get("disconnected") is True
        assert cvl.health()["consecutive_errors"] == MAX_CONSECUTIVE_ERRORS


# ---------------------------------------------------------------------------
# 8. ApplicationContainer wiring
# ---------------------------------------------------------------------------

class TestContainerWiring:
    def test_container_has_continuous_voice_loop(self):
        from desktop_agent.core.application_container import ApplicationContainer
        container = ApplicationContainer()
        assert hasattr(container, "continuous_voice_loop")
        assert isinstance(container.continuous_voice_loop, ContinuousVoiceLoop)

    def test_container_has_continuous_vision(self):
        from desktop_agent.core.application_container import ApplicationContainer
        container = ApplicationContainer()
        assert hasattr(container, "continuous_vision")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONSECUTIVE_ERRORS = 5
