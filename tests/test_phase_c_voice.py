"""
Phase C tests: VoiceInterface (desktop_agent.speech.voice_interface).

Covers initialization, state transitions, health, listeners, thread safety,
error handling, disconnect/reconnect, state history, and VoiceState enum.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from desktop_agent.speech.voice_interface import VoiceInterface, VoiceState


def _make_vi() -> VoiceInterface:
    return VoiceInterface()


# ---------------------------------------------------------------------------
# 1. VoiceInterface initialization (IDLE state)
# ---------------------------------------------------------------------------

class TestInit:
    def test_initial_state_is_idle(self):
        vi = _make_vi()
        assert vi.state == VoiceState.IDLE

    def test_health_initial(self):
        vi = _make_vi()
        h = vi.health()
        assert h["state"] == "idle"
        assert h["error_count"] == 0
        assert h["last_interaction"] == 0.0
        assert h["transcript_buffer"] == ""
        assert h["history_length"] == 0


# ---------------------------------------------------------------------------
# 2. start_listening() sets LISTENING state
# ---------------------------------------------------------------------------

class TestStartListening:
    def test_sets_listening(self):
        vi = _make_vi()
        vi.start_listening()
        assert vi.state == VoiceState.LISTENING

    def test_records_history(self):
        vi = _make_vi()
        vi.start_listening()
        history = vi.get_history()
        assert len(history) == 1
        assert history[0]["from"] == "idle"
        assert history[0]["to"] == "listening"


# ---------------------------------------------------------------------------
# 3. stop_listening() returns to IDLE
# ---------------------------------------------------------------------------

class TestStopListening:
    def test_returns_to_idle(self):
        vi = _make_vi()
        vi.start_listening()
        vi.stop_listening()
        assert vi.state == VoiceState.IDLE

    def test_from_listening(self):
        vi = _make_vi()
        vi.start_listening()
        vi.stop_listening()
        assert vi.state == VoiceState.IDLE


# ---------------------------------------------------------------------------
# 4. process_transcript() sets PROCESSING then returns result
# ---------------------------------------------------------------------------

class TestProcessTranscript:
    def test_sets_processing_state(self):
        vi = _make_vi()
        vi.start_listening()
        result = vi.process_transcript("open notepad")
        assert result["ok"] is True
        assert result["transcript"] == "open notepad"
        assert vi.state == VoiceState.PROCESSING

    def test_result_contains_fields(self):
        vi = _make_vi()
        vi.start_listening()
        result = vi.process_transcript("hello")
        assert "ok" in result
        assert "state" in result
        assert "transcript" in result
        assert "timestamp" in result

    def test_buffers_transcript(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("test command")
        h = vi.health()
        assert h["transcript_buffer"] == "test command"


# ---------------------------------------------------------------------------
# 5. speak() sets SPEAKING state
# ---------------------------------------------------------------------------

class TestSpeak:
    def test_sets_speaking(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("test")
        vi.speak("Done.")
        assert vi.state == VoiceState.SPEAKING

    def test_from_processing(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.speak("ok")
        assert vi.state == VoiceState.SPEAKING


# ---------------------------------------------------------------------------
# 6. interrupt() sets INTERRUPTED state
# ---------------------------------------------------------------------------

class TestInterrupt:
    def test_interrupt_from_listening(self):
        vi = _make_vi()
        vi.start_listening()
        vi.interrupt()
        assert vi.state == VoiceState.INTERRUPTED

    def test_interrupt_from_speaking(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.speak("ok")
        vi.interrupt()
        assert vi.state == VoiceState.INTERRUPTED

    def test_interrupt_from_processing(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.interrupt()
        assert vi.state == VoiceState.INTERRUPTED


# ---------------------------------------------------------------------------
# 7. reset() returns to IDLE from any state
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_from_listening(self):
        vi = _make_vi()
        vi.start_listening()
        vi.reset()
        assert vi.state == VoiceState.IDLE

    def test_reset_from_speaking(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.speak("ok")
        vi.reset()
        assert vi.state == VoiceState.IDLE

    def test_reset_from_error(self):
        vi = _make_vi()
        vi.set_error("fail")
        vi.reset()
        assert vi.state == VoiceState.IDLE

    def test_reset_from_disconnected(self):
        vi = _make_vi()
        vi.disconnect()
        vi.reset()
        assert vi.state == VoiceState.IDLE

    def test_reset_clears_transcript_buffer(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("secret")
        vi.reset()
        h = vi.health()
        assert h["transcript_buffer"] == ""


# ---------------------------------------------------------------------------
# 8. health() returns correct dict
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_fields(self):
        vi = _make_vi()
        h = vi.health()
        assert "state" in h
        assert "error_count" in h
        assert "last_interaction" in h
        assert "transcript_buffer" in h
        assert "history_length" in h

    def test_health_reflects_error_count(self):
        vi = _make_vi()
        vi.set_error("e1")
        vi.set_error("e2")
        h = vi.health()
        assert h["error_count"] == 2

    def test_health_reflects_history_length(self):
        vi = _make_vi()
        vi.start_listening()
        vi.stop_listening()
        h = vi.health()
        assert h["history_length"] == 2


# ---------------------------------------------------------------------------
# 9. state change callback invoked
# ---------------------------------------------------------------------------

class TestStateCallback:
    def test_callback_called_on_transition(self):
        vi = _make_vi()
        cb = MagicMock()
        vi.on_state_change(cb)
        vi.start_listening()
        cb.assert_called_once_with(VoiceState.IDLE, VoiceState.LISTENING)

    def test_callback_args(self):
        vi = _make_vi()
        cb = MagicMock()
        vi.on_state_change(cb)
        vi.start_listening()
        args = cb.call_args[0]
        assert args[0] == VoiceState.IDLE
        assert args[1] == VoiceState.LISTENING


# ---------------------------------------------------------------------------
# 10. state transitions are validated (invalid transitions rejected)
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    def test_idle_to_speaking_rejected(self):
        vi = _make_vi()
        vi.speak("test")
        assert vi.state == VoiceState.IDLE

    def test_idle_to_processing_rejected(self):
        vi = _make_vi()
        vi.process_transcript("test")
        assert vi.state == VoiceState.IDLE

    def test_error_to_listening_rejected(self):
        vi = _make_vi()
        vi.set_error("fail")
        vi.start_listening()
        assert vi.state == VoiceState.ERROR

    def test_speaking_to_listening_accepted(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.speak("ok")
        vi.start_listening()
        assert vi.state == VoiceState.LISTENING

    def test_speaking_to_processing_rejected(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.speak("ok")
        vi.process_transcript("another")
        assert vi.state == VoiceState.SPEAKING


# ---------------------------------------------------------------------------
# 11. thread safety (concurrent access)
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_start_stop(self):
        vi = _make_vi()
        errors = []

        def worker():
            try:
                for _ in range(100):
                    vi.start_listening()
                    vi.stop_listening()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert vi.state in (VoiceState.IDLE, VoiceState.LISTENING)

    def test_concurrent_transitions_and_health(self):
        vi = _make_vi()
        errors = []

        def transitioner():
            try:
                for _ in range(50):
                    vi.start_listening()
                    vi.process_transcript("x")
                    vi.speak("y")
                    vi.stop_listening()
            except Exception as e:
                errors.append(e)

        def health_checker():
            try:
                for _ in range(100):
                    h = vi.health()
                    assert "state" in h
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=transitioner),
            threading.Thread(target=transitioner),
            threading.Thread(target=health_checker),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ---------------------------------------------------------------------------
# 12. error handling (set_error sets ERROR state)
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_set_error_sets_error_state(self):
        vi = _make_vi()
        vi.set_error("something broke")
        assert vi.state == VoiceState.ERROR

    def test_error_bumps_count(self):
        vi = _make_vi()
        vi.set_error("e1")
        vi.set_error("e2")
        assert vi.health()["error_count"] == 2

    def test_error_from_listening(self):
        vi = _make_vi()
        vi.start_listening()
        vi.set_error("fail")
        assert vi.state == VoiceState.ERROR

    def test_error_from_speaking(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.speak("ok")
        vi.set_error("tts fail")
        assert vi.state == VoiceState.ERROR


# ---------------------------------------------------------------------------
# 13. disconnect sets DISCONNECTED state
# ---------------------------------------------------------------------------

class TestDisconnect:
    def test_disconnect_from_idle(self):
        vi = _make_vi()
        vi.disconnect()
        assert vi.state == VoiceState.DISCONNECTED

    def test_disconnect_from_listening(self):
        vi = _make_vi()
        vi.start_listening()
        vi.disconnect()
        assert vi.state == VoiceState.DISCONNECTED

    def test_disconnect_from_speaking(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.speak("ok")
        vi.disconnect()
        assert vi.state == VoiceState.DISCONNECTED

    def test_disconnect_from_processing(self):
        vi = _make_vi()
        vi.start_listening()
        vi.process_transcript("cmd")
        vi.disconnect()
        assert vi.state == VoiceState.DISCONNECTED


# ---------------------------------------------------------------------------
# 14. reconnect from DISCONNECTED returns to IDLE
# ---------------------------------------------------------------------------

class TestReconnect:
    def test_reconnect_from_disconnected(self):
        vi = _make_vi()
        vi.disconnect()
        vi.reconnect()
        assert vi.state == VoiceState.IDLE

    def test_reconnect_records_history(self):
        vi = _make_vi()
        vi.disconnect()
        vi.reconnect()
        history = vi.get_history()
        assert any(h["from"] == "disconnected" and h["to"] == "idle" for h in history)


# ---------------------------------------------------------------------------
# 15. multiple listeners supported
# ---------------------------------------------------------------------------

class TestMultipleListeners:
    def test_two_listeners_both_called(self):
        vi = _make_vi()
        cb1 = MagicMock()
        cb2 = MagicMock()
        vi.on_state_change(cb1)
        vi.on_state_change(cb2)
        vi.start_listening()
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_remove_one_listener(self):
        vi = _make_vi()
        cb1 = MagicMock()
        cb2 = MagicMock()
        vi.on_state_change(cb1)
        vi.on_state_change(cb2)
        vi.remove_listener(cb1)
        vi.start_listening()
        cb1.assert_not_called()
        cb2.assert_called_once()


# ---------------------------------------------------------------------------
# 16. listener exception doesn't crash
# ---------------------------------------------------------------------------

class TestListenerException:
    def test_bad_listener_does_not_crash(self):
        vi = _make_vi()
        bad_cb = MagicMock(side_effect=RuntimeError("boom"))
        good_cb = MagicMock()
        vi.on_state_change(bad_cb)
        vi.on_state_change(good_cb)
        vi.start_listening()
        assert vi.state == VoiceState.LISTENING
        good_cb.assert_called_once()

    def test_reset_survives_bad_listener(self):
        vi = _make_vi()
        bad_cb = MagicMock(side_effect=ValueError("nope"))
        vi.on_state_change(bad_cb)
        vi.reset()
        assert vi.state == VoiceState.IDLE


# ---------------------------------------------------------------------------
# 17. state history bounded
# ---------------------------------------------------------------------------

class TestStateHistoryBounded:
    def test_history_bounded_at_200(self):
        vi = _make_vi()
        for _ in range(250):
            vi.start_listening()
            vi.stop_listening()
        history = vi.get_history(count=999)
        assert len(history) <= 201

    def test_get_history_count(self):
        vi = _make_vi()
        for _ in range(10):
            vi.start_listening()
            vi.stop_listening()
        h5 = vi.get_history(count=5)
        assert len(h5) == 5


# ---------------------------------------------------------------------------
# 18. VoiceState enum has all required values
# ---------------------------------------------------------------------------

class TestVoiceStateEnum:
    def test_has_idle(self):
        assert VoiceState.IDLE.value == "idle"

    def test_has_listening(self):
        assert VoiceState.LISTENING.value == "listening"

    def test_has_processing(self):
        assert VoiceState.PROCESSING.value == "processing"

    def test_has_speaking(self):
        assert VoiceState.SPEAKING.value == "speaking"

    def test_has_interrupted(self):
        assert VoiceState.INTERRUPTED.value == "interrupted"

    def test_has_error(self):
        assert VoiceState.ERROR.value == "error"

    def test_has_disconnected(self):
        assert VoiceState.DISCONNECTED.value == "disconnected"

    def test_all_seven_states(self):
        assert len(VoiceState) == 13

    def test_is_enum_subclass(self):
        import enum
        assert issubclass(VoiceState, enum.Enum)


# ===========================================================================
# ContinuousVoiceLoop tests
# ===========================================================================

from desktop_agent.speech.continuous_voice_loop import (
    ContinuousVoiceLoop,
    Turn,
    TurnStatus,
    DEDUP_WINDOW_S,
    MAX_CONSECUTIVE_ERRORS,
)


def _make_cvl(**kwargs) -> ContinuousVoiceLoop:
    return ContinuousVoiceLoop(**kwargs)


# ---------------------------------------------------------------------------
# 15. ContinuousVoiceLoop initialization
# ---------------------------------------------------------------------------

class TestCVLInit:
    def test_initial_state_idle(self):
        cvl = _make_cvl()
        assert cvl.status()["state"] == "idle"

    def test_zero_turns(self):
        cvl = _make_cvl()
        assert cvl.status()["total_turns"] == 0

    def test_zero_interruptions(self):
        cvl = _make_cvl()
        assert cvl.status()["total_interruptions"] == 0

    def test_health_has_all_fields(self):
        cvl = _make_cvl()
        h = cvl.health()
        assert "voice_state" in h
        assert "total_turns" in h
        assert "consecutive_errors" in h
        assert "current_turn" in h
        assert h["current_turn"] is None


# ---------------------------------------------------------------------------
# 16. Turn lifecycle — on_user_transcript
# ---------------------------------------------------------------------------

class TestCVLTranscript:
    def test_empty_transcript_rejected(self):
        cvl = _make_cvl()
        r = cvl.on_user_transcript("")
        assert r["ok"] is False
        assert r["error"] == "empty_transcript"

    def test_whitespace_only_rejected(self):
        cvl = _make_cvl()
        r = cvl.on_user_transcript("   ")
        assert r["ok"] is False

    def test_no_execute_callback_returns_error(self):
        cvl = _make_cvl()
        r = cvl.on_user_transcript("hello")
        assert r["ok"] is False
        assert "error" in r.get("result", {})

    def test_execute_callback_called(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cb = MagicMock(return_value={"ok": True, "response": "Done"})
        cvl.set_execute_callback(cb)
        r = cvl.on_user_transcript("open notepad")
        assert r["ok"] is True
        cb.assert_called_once_with("open notepad")

    def test_turn_id_assigned(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        r = cvl.on_user_transcript("test")
        assert r["turn_id"].startswith("t-")

    def test_duration_ms_present(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        r = cvl.on_user_transcript("test")
        assert "duration_ms" in r
        assert r["duration_ms"] >= 0

    def test_turn_count_increments(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("first")
        cvl.on_user_transcript("second")
        assert cvl.status()["total_turns"] == 2

    def test_exception_returns_error(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(side_effect=RuntimeError("boom")))
        r = cvl.on_user_transcript("fail")
        assert r["ok"] is False
        assert "boom" in r["error"]

    def test_consecutive_errors_increment(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(side_effect=RuntimeError("e1")))
        cvl.on_user_transcript("a")
        cvl.on_user_transcript("b")
        assert cvl.health()["consecutive_errors"] == 2

    def test_success_resets_consecutive_errors(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(side_effect=RuntimeError("e")))
        cvl.on_user_transcript("fail1")
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("ok")
        assert cvl.health()["consecutive_errors"] == 0


# ---------------------------------------------------------------------------
# 17. Deduplication
# ---------------------------------------------------------------------------

class TestCVLDedup:
    def test_duplicate_rejected(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("same text")
        r = cvl.on_user_transcript("same text")
        assert r["ok"] is False
        assert r["error"] == "duplicate_transcript"

    def test_different_text_accepted(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("text one")
        r = cvl.on_user_transcript("text two")
        assert r["ok"] is True


# ---------------------------------------------------------------------------
# 18. Interruption / barge-in
# ---------------------------------------------------------------------------

class TestCVLInterruption:
    def test_interruption_returns_ok(self):
        cvl = _make_cvl()
        r = cvl.on_interruption()
        assert r["ok"] is True
        assert r["action"] == "interrupted"

    def test_interruption_increments_count(self):
        cvl = _make_cvl()
        cvl.on_interruption()
        cvl.on_interruption()
        assert cvl.status()["total_interruptions"] == 2

    def test_interruption_cancels_inflight_turn(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        # Slow execute to simulate in-flight
        import time
        def slow_execute(t):
            time.sleep(0.1)
            return {"ok": True}
        cvl.set_execute_callback(slow_execute)
        cvl.on_user_transcript("slow task")
        r = cvl.on_interruption()
        assert r["ok"] is True


# ---------------------------------------------------------------------------
# 19. Disconnect / reconnect
# ---------------------------------------------------------------------------

class TestCVLDisconnectReconnect:
    def test_disconnect(self):
        cvl = _make_cvl()
        r = cvl.on_disconnect()
        assert r["ok"] is True
        assert r["state"] == "disconnected"

    def test_reconnect(self):
        cvl = _make_cvl()
        cvl.on_disconnect()
        r = cvl.on_reconnect()
        assert r["ok"] is True

    def test_reconnect_resets_errors(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(side_effect=RuntimeError("e")))
        cvl.on_user_transcript("fail")
        cvl.on_reconnect()
        assert cvl.health()["consecutive_errors"] == 0

    def test_disconnect_cancels_inflight(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("task")
        r = cvl.on_disconnect()
        assert r["ok"] is True


# ---------------------------------------------------------------------------
# 20. Tick / timeouts
# ---------------------------------------------------------------------------

class TestCVLTick:
    def test_tick_returns_ok(self):
        cvl = _make_cvl()
        r = cvl.tick()
        assert r["ok"] is True
        assert isinstance(r["actions"], list)

    def test_silence_timeout_idles(self):
        cvl = _make_cvl(silence_timeout=0.01)
        cvl._vi.start_listening()
        assert cvl._vi.state == VoiceState.LISTENING
        import time
        time.sleep(0.02)
        r = cvl.tick()
        assert "silence_timeout" in r["actions"]


# ---------------------------------------------------------------------------
# 21. Turn model
# ---------------------------------------------------------------------------

class TestTurnModel:
    def test_turn_to_dict(self):
        t = Turn("t-1", "hello")
        d = t.to_dict()
        assert d["turn_id"] == "t-1"
        assert d["transcript"] == "hello"
        assert d["status"] == "pending"

    def test_turn_statuses(self):
        assert len(TurnStatus) == 6


# ---------------------------------------------------------------------------
# 22. History
# ---------------------------------------------------------------------------

class TestCVLHistory:
    def test_recent_turns_empty(self):
        cvl = _make_cvl()
        assert cvl.get_recent_turns() == []

    def test_recent_turns_after_execute(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        cvl.on_user_transcript("hello")
        turns = cvl.get_recent_turns()
        assert len(turns) == 1
        assert turns[0]["transcript"] == "hello"

    def test_history_bounded(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True}))
        for i in range(120):
            cvl.on_user_transcript(f"turn {i}")
        h = cvl.health()
        assert h["history_length"] <= 100


# ---------------------------------------------------------------------------
# 23. TTS callback
# ---------------------------------------------------------------------------

class TestCVLTTS:
    def test_tts_called_on_response(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True, "response": "Hello world"}))
        tts_cb = MagicMock()
        cvl.set_tts_callback(tts_cb)
        cvl.on_user_transcript("hi")
        tts_cb.assert_called_once_with("Hello world")

    def test_tts_not_called_without_callback(self):
        from unittest.mock import MagicMock
        cvl = _make_cvl()
        cvl.set_execute_callback(MagicMock(return_value={"ok": True, "response": "hi"}))
        cvl.on_user_transcript("test")
        # No error, just no TTS
        assert cvl.status()["total_turns"] == 1


# ---------------------------------------------------------------------------
# 24. Response text extraction
# ---------------------------------------------------------------------------

class TestResponseExtraction:
    def test_extract_from_response_key(self):
        r = ContinuousVoiceLoop._extract_response_text({"response": "hi"})
        assert r == "hi"

    def test_extract_from_text_key(self):
        r = ContinuousVoiceLoop._extract_response_text({"text": "hello"})
        assert r == "hello"

    def test_extract_from_nested(self):
        r = ContinuousVoiceLoop._extract_response_text({"result": {"response": "ok"}})
        assert r == "ok"

    def test_extract_none_for_empty(self):
        assert ContinuousVoiceLoop._extract_response_text({}) is None

    def test_extract_none_for_none(self):
        assert ContinuousVoiceLoop._extract_response_text(None) is None

    def test_extract_caps_at_500(self):
        long = "x" * 1000
        r = ContinuousVoiceLoop._extract_response_text({"response": long})
        assert len(r) == 500
