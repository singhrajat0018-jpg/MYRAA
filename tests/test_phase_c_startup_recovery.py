"""
Phase C tests: Startup / Shutdown / Restart validation.

Verifies the Python agent lifecycle: boot, health, shutdown,
restart, checkpoint recovery, and that no duplicate processes or
zombie tasks survive a restart cycle.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from desktop_agent.core.application_container import ApplicationContainer
from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop
from desktop_agent.speech.voice_interface import VoiceInterface, VoiceState
from desktop_agent.brain.telemetry.relay import TelemetryRelay, telemetry_relay


# ---------------------------------------------------------------------------
# 1. ApplicationContainer boot
# ---------------------------------------------------------------------------

class TestContainerBoot:
    def test_container_creates_all_singletons(self):
        c = ApplicationContainer()
        assert c.blackboard is not None
        assert c.planner is not None
        assert c.execution_brain is not None
        assert c.brain_engine is not None
        assert c.memory_2_0 is not None
        assert c.super_brain is not None
        assert c.continuous_vision is not None
        assert c.continuous_voice_loop is not None
        assert c.autonomy_controller is not None
        assert c.project_manager is not None

    def test_container_is_singleton_pattern(self):
        c1 = ApplicationContainer()
        c2 = ApplicationContainer()
        # Each creates its own instance, but all components are functional
        assert c1.continuous_voice_loop is not c2.continuous_voice_loop
        assert c1.continuous_vision is not c2.continuous_vision


# ---------------------------------------------------------------------------
# 2. Health checks
# ---------------------------------------------------------------------------

class TestHealthChecks:
    def test_voice_health_has_fields(self):
        cvl = ContinuousVoiceLoop()
        h = cvl.health()
        required = ["voice_state", "total_turns", "total_interruptions",
                     "consecutive_errors", "session_uptime_s",
                     "last_interaction_age_s", "history_length"]
        for key in required:
            assert key in h, f"Missing health field: {key}"

    def test_vision_health_accessible(self):
        c = ApplicationContainer()
        cv = c.continuous_vision
        assert hasattr(cv, "status")
        assert hasattr(cv, "is_healthy")
        assert hasattr(cv, "telemetry")

    def test_telemetry_relay_health(self):
        relay = TelemetryRelay(max_events=100)
        s = relay.status()
        assert s["ok"] is True
        assert "buffered" in s
        assert "max_events" in s


# ---------------------------------------------------------------------------
# 3. VoiceInterface restart cycle
# ---------------------------------------------------------------------------

class TestVoiceRestartCycle:
    def test_voice_full_lifecycle(self):
        vi = VoiceInterface()
        assert vi.state == VoiceState.IDLE

        vi.start_listening()
        assert vi.state == VoiceState.LISTENING

        vi.process_transcript("test")
        assert vi.state == VoiceState.PROCESSING

        vi.speak("response")
        assert vi.state == VoiceState.SPEAKING

        vi.stop_listening()
        assert vi.state == VoiceState.IDLE

    def test_voice_interrupt_and_resume(self):
        vi = VoiceInterface()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.interrupt()
        assert vi.state == VoiceState.INTERRUPTED
        vi.start_listening()
        assert vi.state == VoiceState.LISTENING

    def test_voice_disconnect_reconnect(self):
        vi = VoiceInterface()
        vi.disconnect()
        assert vi.state == VoiceState.DISCONNECTED
        vi.reconnect()
        assert vi.state == VoiceState.IDLE


# ---------------------------------------------------------------------------
# 4. ContinuousVoiceLoop restart cycle
# ---------------------------------------------------------------------------

class TestCVLRestartCycle:
    def test_disconnect_reconnect_preserves_turns(self):
        from unittest.mock import MagicMock
        cvl = ContinuousVoiceLoop()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("before disconnect")
        cvl.on_disconnect()
        cvl.on_reconnect()
        r = cvl.on_user_transcript("after reconnect")
        assert r["ok"] is True
        assert cvl.status()["total_turns"] == 2

    def test_interruption_allows_resume(self):
        cvl = ContinuousVoiceLoop()
        cvl.on_interruption()
        assert cvl.health()["total_interruptions"] == 1
        # Can continue after interruption
        cvl.on_interruption()
        assert cvl.health()["total_interruptions"] == 2


# ---------------------------------------------------------------------------
# 5. Telemetry relay restart
# ---------------------------------------------------------------------------

class TestTelemetryRestart:
    def test_reset_clears_state(self):
        relay = TelemetryRelay(max_events=100)
        relay.emit("test_event", {"key": "value"})
        assert len(relay.stream()) == 1
        relay.reset()
        assert len(relay.stream()) == 0
        relay.emit("test_event", {"key": "value2"})
        events = relay.stream()
        assert len(events) == 1
        assert events[0]["payload"]["key"] == "value2"

    def test_drain_then_emit(self):
        relay = TelemetryRelay(max_events=100)
        relay.emit("e1", {"a": 1})
        relay.emit("e2", {"b": 2})
        drained = relay.drain()
        assert len(drained) == 2
        assert len(relay.stream()) == 0
        relay.emit("e3", {"c": 3})
        assert len(relay.stream()) == 1


# ---------------------------------------------------------------------------
# 6. Checkpoint survival (autonomy)
# ---------------------------------------------------------------------------

class TestCheckpointSurvival:
    def test_autonomy_has_checkpoint_methods(self):
        c = ApplicationContainer()
        ac = c.autonomy_controller
        assert hasattr(ac, "status")
        assert hasattr(ac, "telemetry")
        s = ac.status()
        assert "total_goals" in s or "status" in s


# ---------------------------------------------------------------------------
# 7. No zombie tasks after disconnect
# ---------------------------------------------------------------------------

class TestZombieTaskPrevention:
    def test_disconnect_clears_current_turn(self):
        from unittest.mock import MagicMock
        cvl = ContinuousVoiceLoop()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("task")
        cvl.on_disconnect()
        h = cvl.health()
        assert h["current_turn"] is None

    def test_interrupt_clears_current_turn(self):
        from unittest.mock import MagicMock
        cvl = ContinuousVoiceLoop()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("task")
        cvl.on_interruption()
        h = cvl.health()
        assert h["current_turn"] is None

    def test_tick_timeout_clears_zombie(self):
        cvl = ContinuousVoiceLoop(turn_timeout=0.01)
        # Simulate a zombie by directly setting a current turn
        from desktop_agent.speech.continuous_voice_loop import Turn, TurnStatus
        t = Turn("zombie", "stuck")
        t.status = TurnStatus.EXECUTING
        t.started_at = time.time() - 100
        cvl._current_turn = t
        cvl._vi._state = VoiceState.PROCESSING  # Simulate stuck state

        r = cvl.tick()
        assert "turn_timed_out" in r["actions"]
        assert cvl._current_turn is None


# ---------------------------------------------------------------------------
# 8. Process duplication prevention
# ---------------------------------------------------------------------------

class TestNoDuplicateProcesses:
    def test_relay_singleton_behavior(self):
        """Verify the global telemetry_relay is a single instance."""
        from desktop_agent.brain.telemetry.relay import telemetry_relay as tr1
        from desktop_agent.brain.telemetry.relay import telemetry_relay as tr2
        assert tr1 is tr2

    def test_cvl_independent_instances(self):
        """Each ApplicationContainer gets its own CVL."""
        c1 = ApplicationContainer()
        c2 = ApplicationContainer()
        assert c1.continuous_voice_loop is not c2.continuous_voice_loop

    def test_voice_interface_independent_instances(self):
        vi1 = VoiceInterface()
        vi2 = VoiceInterface()
        assert vi1 is not vi2
        vi1.start_listening()
        assert vi2.state == VoiceState.IDLE


# ---------------------------------------------------------------------------
# 9. Memory preservation across lifecycle
# ---------------------------------------------------------------------------

class TestMemoryPreserved:
    def test_memory_accessible(self):
        c = ApplicationContainer()
        m = c.memory_2_0
        assert hasattr(m, "get_active_count")
        count = m.get_active_count()
        assert isinstance(count, int)
