"""
Phase C: Real Provider Multimodal E2E Smoke Tests.

These tests validate the real end-to-end multimodal pipeline. They are
designed to be run manually against a live system with API keys configured.

For CI/deterministic testing, the mock-based tests at the bottom provide
coverage without real providers.

Environment prerequisites:
- GEMINI_API_KEY set in .env or secrets.json
- Python desktop agent running on 127.0.0.1:8765
- Node server running on 0.0.0.0:3000
- No firewall blocking localhost ports

To run the live smoke tests:
    python -m tests.test_phase_c_multimodal_smoke --live

To run mock-based tests only (default):
    python -m pytest tests/test_phase_c_multimodal_smoke.py -v
"""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_LIVE_MODE = "--live" in os.environ.get("PYTEST_ARGS", "") or os.environ.get("MYRAA_SMOKE_LIVE", "")

LIVE_AGENT_URL = "http://127.0.0.1:8765"
LIVE_NODE_URL = "http://127.0.0.1:3000"


def _require_live():
    """Skip if not in live smoke-test mode."""
    if not _LIVE_MODE:
        pytest.skip("Live smoke tests require --live flag or MYRAA_SMOKE_LIVE=1")


# ---------------------------------------------------------------------------
# A. Voice → Response (live)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _LIVE_MODE, reason="Requires live system")
class TestLiveVoiceResponse:
    def test_voice_transcript_endpoint(self):
        """Voice transcript → brain → execution → response."""
        import requests
        r = requests.post(
            f"{LIVE_AGENT_URL}/voice/transcript",
            json={"transcript": "what time is it"},
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert "ok" in data

    def test_voice_health(self):
        """Voice health endpoint returns valid state."""
        import requests
        r = requests.get(f"{LIVE_AGENT_URL}/voice/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "voice_state" in data
        assert "total_turns" in data

    def test_voice_interruption(self):
        """Barge-in cancels in-flight turn."""
        import requests
        r = requests.post(f"{LIVE_AGENT_URL}/voice/interrupt", timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ---------------------------------------------------------------------------
# B. Vision → Desktop/browser observation (live)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _LIVE_MODE, reason="Requires live system")
class TestLiveVisionObservation:
    def test_vision_status(self):
        """Vision pipeline status."""
        import requests
        r = requests.get(f"{LIVE_AGENT_URL}/vision/status", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "status" in data

    def test_vision_state(self):
        """Current visual state."""
        import requests
        r = requests.get(f"{LIVE_AGENT_URL}/vision/state", timeout=10)
        assert r.status_code == 200

    def test_vision_context(self):
        """Visual context for brain."""
        import requests
        r = requests.get(f"{LIVE_AGENT_URL}/vision/context", timeout=10)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# C. Voice + Vision → SuperBrain → Action → Verification (live)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _LIVE_MODE, reason="Requires live system")
class TestLiveVoiceVisionAction:
    def test_multimodal_health(self):
        """Full multimodal health check."""
        import requests
        r = requests.get(f"{LIVE_AGENT_URL}/health/multimodal", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "vision" in data
        assert "voice" in data
        assert "telemetry_relay" in data

    def test_voice_with_vision_context(self):
        """Voice command that may benefit from vision context."""
        import requests
        r = requests.post(
            f"{LIVE_AGENT_URL}/voice/transcript",
            json={"transcript": "take a screenshot"},
            timeout=60,
        )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# D. Voice + Vision → Project Builder (live)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _LIVE_MODE, reason="Requires live system")
class TestLiveProjectBuilder:
    def test_project_endpoint(self):
        """Project creation endpoint."""
        import requests
        r = requests.post(
            f"{LIVE_AGENT_URL}/project",
            json={"project_name": "smoke_test_project", "description": "E2E smoke test"},
            timeout=30,
        )
        assert r.status_code == 200

    def test_projects_list(self):
        """Project listing endpoint."""
        import requests
        r = requests.get(f"{LIVE_AGENT_URL}/projects", timeout=10)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# E. Autonomy + Vision observation (live)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _LIVE_MODE, reason="Requires live system")
class TestLiveAutonomyVision:
    def test_autonomy_status(self):
        """Autonomy controller status."""
        import requests
        r = requests.get(f"{LIVE_AGENT_URL}/autonomy/status", timeout=10)
        assert r.status_code == 200

    def test_vision_autonomy_combined_health(self):
        """Both vision and autonomy report in multimodal health."""
        import requests
        r = requests.get(f"{LIVE_AGENT_URL}/health/multimodal", timeout=10)
        data = r.json()
        assert "vision" in data
        assert "autonomy" in data


# ---------------------------------------------------------------------------
# F. Interruption during voice response (live)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _LIVE_MODE, reason="Requires live system")
class TestLiveInterruption:
    def test_interruption_during_processing(self):
        """Interruption while processing."""
        import requests
        # Start a long-running voice command
        import threading
        def long_command():
            try:
                requests.post(
                    f"{LIVE_AGENT_URL}/voice/transcript",
                    json={"transcript": "open notepad and type a long paragraph"},
                    timeout=60,
                )
            except Exception:
                pass

        t = threading.Thread(target=long_command, daemon=True)
        t.start()
        time.sleep(0.5)  # Let it start processing

        # Interrupt
        r = requests.post(f"{LIVE_AGENT_URL}/voice/interrupt", timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ---------------------------------------------------------------------------
# Mock-based tests (CI-safe, no real providers needed)
# ---------------------------------------------------------------------------

class TestMockedMultimodalPipeline:
    """CI-safe tests that validate the pipeline logic with mocks."""

    def test_voice_to_execution_mocked(self):
        from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop
        cvl = ContinuousVoiceLoop()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True, "response": "Done"}))
        r = cvl.on_user_transcript("take a screenshot")
        assert r["ok"] is True

    def test_vision_telemetry_flow_mocked(self):
        from desktop_agent.brain.telemetry.relay import TelemetryRelay, VISION_STATE_CHANGED
        relay = TelemetryRelay(max_events=100)
        relay.emit(VISION_STATE_CHANGED, {"state": "active", "stale": False})
        events = relay.drain()
        assert events[0]["event_type"] == VISION_STATE_CHANGED

    def test_voice_vision_interruption_mocked(self):
        from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop
        cvl = ContinuousVoiceLoop()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("task1")
        r = cvl.on_interruption()
        assert r["ok"] is True
        assert cvl.status()["total_interruptions"] == 1

    def test_telemetry_redaction_mocked(self):
        from desktop_agent.brain.telemetry.relay import TelemetryRelay, TOOL_STARTED
        relay = TelemetryRelay(max_events=100)
        relay.emit(TOOL_STARTED, {"api_key": "sk-secret123", "tool": "test"})
        events = relay.drain()
        assert events[0]["payload"]["api_key"] == "***REDACTED***"
        assert events[0]["payload"]["tool"] == "test"

    def test_full_pipeline_mocked(self):
        from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop
        from desktop_agent.brain.telemetry.relay import TelemetryRelay, TOOL_STARTED
        from desktop_agent.speech.voice_interface import VoiceInterface

        vi = VoiceInterface()
        relay = TelemetryRelay(max_events=100)
        cvl = ContinuousVoiceLoop(voice_interface=vi)

        results = []
        cvl.set_execute_callback(lambda t: {"ok": True, "response": f"Executed: {t}"})

        tts_log = []
        cvl.set_tts_callback(lambda text: tts_log.append(text))

        # Simulate: voice → brain → execute → telemetry → TTS
        vi.start_listening()
        relay.emit(TOOL_STARTED, {"tool": "user_command"})
        r = cvl.on_user_transcript("open notepad")

        assert r["ok"] is True
        assert len(tts_log) == 1
        assert "Executed:" in tts_log[0]

        events = relay.drain()
        assert len(events) == 1

    def test_autonomy_vision_combined_mocked(self):
        from desktop_agent.brain.telemetry.relay import TelemetryRelay
        relay = TelemetryRelay(max_events=100)
        relay.emit("autonomy_state_changed", {"state": "running", "goal_id": "g1"})
        relay.emit("vision_state_changed", {"state": "monitoring"})
        events = relay.drain()
        assert len(events) == 2

    def test_disconnection_recovery_mocked(self):
        from desktop_agent.speech.continuous_voice_loop import ContinuousVoiceLoop
        cvl = ContinuousVoiceLoop()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("before")
        cvl.on_disconnect()
        cvl.on_reconnect()
        r = cvl.on_user_transcript("after")
        assert r["ok"] is True
        assert cvl.status()["total_turns"] == 2
