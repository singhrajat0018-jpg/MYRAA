"""Voice health snapshot + generation-gated audio path (§11/§12/§18).

Covers the multi-turn robustness contract:
- health() snapshot shape and counters (read-only diagnostics),
- submit_audio refuses audio when the session is not READY,
- stale-generation audio queued before a failure is NEVER sent to a new
  connection generation (stale tasks cannot write to a new socket),
- failure convergence (one CONNECTION_FAILED per generation, last_error set).
"""
import asyncio

import pytest

from desktop_agent.speech.gemini_live import (
    AUDIO_QUEUE_MAX,
    ConnState,
    GeminiLiveConfig,
    GeminiLiveSession,
    GeminiToolRouter,
    GeminiVoiceMetrics,
)


def _make_session() -> GeminiLiveSession:
    cfg = GeminiLiveConfig(enabled=True, api_key="test-key")
    return GeminiLiveSession(cfg, GeminiToolRouter(), GeminiVoiceMetrics())


def test_health_snapshot_shape():
    s = _make_session()
    h = s.health()
    assert h["provider"] == "gemini_live"
    assert h["state"] == ConnState.DISCONNECTED.value
    assert h["connection_generation"] == 0
    assert h["session_id"].startswith("V")
    assert h["audio_queue_max"] == AUDIO_QUEUE_MAX
    assert h["last_input_audio_ms_ago"] is None
    m = h["metrics"]
    for key in ("connection_success", "connection_failure", "reconnects",
                "input_audio_chunks", "input_audio_bytes", "server_messages",
                "dropped_audio_chunks", "dead_writes_prevented",
                "event_loop_lag_events", "event_loop_max_lag_ms", "last_error"):
        assert key in m, key


def test_submit_audio_drops_when_not_ready():
    s = _make_session()
    assert s.submit_audio(b"\x00\x01") is False
    assert s.metrics.dead_writes_prevented == 1


def test_fail_once_sets_last_error_and_suppresses_duplicates():
    async def run():
        s = _make_session()
        s._state = ConnState.READY
        await s._fail_once(
            "audio-send: ConnectionClosedError: sent 1011 (internal error) "
            "keepalive ping timeout; no close frame received")
        assert s.state == ConnState.FAILED
        assert s.metrics.connection_failure == 1
        assert "keepalive" in (s.metrics.last_error or "")
        gen = s.connection_generation
        # The receiver noticing the same dead socket is a duplicate reporter:
        # no new generation, no new failure, no new reconnect task.
        await s._fail_once("receive: ConnectionClosedError")
        assert s.connection_generation == gen
        assert s.metrics.connection_failure == 1
        # Cleanup: never let the reconnect task outlive the test loop.
        if s._reconnect_task is not None:
            s._reconnect_task.cancel()
            try:
                await s._reconnect_task
            except asyncio.CancelledError:
                pass

    asyncio.run(run())


def test_sender_drops_stale_generation_audio():
    """Audio queued under an old generation must never reach a new socket."""

    async def run():
        s = _make_session()
        s._state = ConnState.READY

        class _FakeSdk:
            def __init__(self):
                self.sent = []

            async def send_realtime_input(self, audio=None):
                self.sent.append(bytes(audio.data))

        fake = _FakeSdk()
        s._session = fake
        stale_gen = s._conn_gen + 123
        s._audio_queue.put_nowait((stale_gen, b"\x01\x02"))
        task = asyncio.get_running_loop().create_task(s._audio_sender())
        await asyncio.sleep(0.05)
        s._closed = True  # stop the sender loop
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert fake.sent == []  # stale chunk was never written
        assert s.metrics.dropped_audio_chunks >= 1
        assert s.metrics.input_audio_chunks == 0

    asyncio.run(run())


def test_drain_drops_queued_stale_audio():
    async def run():
        s = _make_session()
        s._state = ConnState.READY
        s._audio_queue.put_nowait((s._conn_gen, b"\x00"))
        s._audio_queue.put_nowait((s._conn_gen, b"\x00"))
        n = s._drain_audio_queue("connection-failed")
        assert n == 2
        assert s.metrics.dropped_audio_chunks == 2
        assert s._audio_queue.empty()

    asyncio.run(run())


def test_ready_state_survives_turn_completion_semantics():
    """The turn-completion path must not move the session out of READY:
    turn handling only bumps counters — state changes happen exclusively in
    connect/_fail_once/close (audio flows ONLY in READY)."""
    s = _make_session()
    s._state = ConnState.READY
    # Simulating the counter side of a completed turn directly.
    s.turn_seq += 1
    s.metrics.turns += 1
    assert s.state == ConnState.READY
    assert s.submit_audio(b"\x00\x01") is True  # still READY → audio accepted
    assert not s._audio_queue.empty()
