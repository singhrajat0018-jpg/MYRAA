"""Gemini Live connection lifecycle: storm-proof sends, one reconnect,
generation guards, bounded queue, resumption, GoAway, shutdown.

No network, SDK, microphone, or speaker required (fake transport).
"""
from __future__ import annotations

import asyncio
import types as _t

import pytest


def _make_session(**cfg_kwargs):
    from desktop_agent.speech import gemini_live as G

    cfg = G.GeminiLiveConfig(enabled=True, api_key="k", **cfg_kwargs)
    events: list = []
    sess = G.GeminiLiveSession(cfg, G.GeminiToolRouter(), G.GeminiVoiceMetrics(),
                               on_event=events.append)
    return sess, events


class _FakeSDK:
    """Programmable stand-in for the SDK AsyncSession."""

    def __init__(self, fail_with=None):
        self.fail_with = fail_with
        self.writes = 0
        self.closed = False

    async def send_realtime_input(self, **kwargs):
        self.writes += 1
        if self.fail_with is not None:
            raise self.fail_with

    async def receive(self):
        if False:
            yield None

    async def close(self):
        self.closed = True


def _ready(sess, sdk):
    sess._session = sdk
    sess._state = sess._state.__class__.READY
    sess._closed = False


def _dead_socket_error():
    # Mirrors the observed runtime failure verbatim: the SDK surfaces the
    # dead socket as a failed write; convergence must not depend on the
    # exception's exact class.
    return ConnectionError(
        "sent 1011 (internal error) keepalive ping timeout; no close frame received")


# 1/2. send while READY writes once; while DISCONNECTED refuses w/o SDK touch
def test_send_ready_writes_once_and_disconnected_refuses():
    sess, _ = _make_session()
    sdk = _FakeSDK()
    _ready(sess, sdk)
    assert asyncio.run(sess.send_audio(b"\x01\x02" * 100)) is True
    assert sdk.writes == 1
    sess2, _ = _make_session()
    assert asyncio.run(sess2.send_audio(b"\x01\x02")) is False


# 3/4/5/6. THE storm test: dead socket + 100 chunks -> 1 failure, 1 reconnect, 1 write
def test_socket_failure_produces_single_failure_single_reconnect():
    sess, events = _make_session()
    sdk = _FakeSDK(fail_with=_dead_socket_error())
    _ready(sess, sdk)
    for _ in range(100):
        sess.submit_audio(b"\x01\x02" * 100)

    async def drain():
        task = asyncio.create_task(sess._audio_sender())
        # First chunk fails fast; rest must drop via guards, not writes.
        for _ in range(200):
            if sdk.writes >= 1 and sess._audio_queue.empty():
                break
            await asyncio.sleep(0.005)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(drain())
    failures = [e for e in events if e.kind == "connection_failed"]
    assert len(failures) == 1
    assert sdk.writes == 1  # only the first write touched the dead socket
    assert sess._reconnect_task is not None  # exactly one reconnect scheduled
    reconnects = [t for t in [sess._reconnect_task] if t is not None]
    assert len(reconnects) == 1
    sess._reconnect_task.cancel()


# 8. generation invalidation: stale queued chunk never written post-failure
def test_stale_generation_chunks_dropped():
    sess, events = _make_session()
    sdk = _FakeSDK(fail_with=_dead_socket_error())
    _ready(sess, sdk)
    gen0 = sess.connection_generation
    sess.submit_audio(b"\x11" * 200)

    async def drain():
        task = asyncio.create_task(sess._audio_sender())
        for _ in range(200):
            if sdk.writes >= 1 and sess._audio_queue.empty():
                break
            await asyncio.sleep(0.005)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(drain())
    assert sess.connection_generation == gen0 + 1
    assert sdk.writes == 1
    # Queue more AFTER failure but before reconnect: must drop, not write.
    for _ in range(5):
        assert sess.submit_audio(b"\x22" * 200) is False
    assert sdk.writes == 1


# 9/17. queue boundedness: overflow drops oldest, keeps newest
def test_audio_queue_bounded_drop_oldest():
    sess, _ = _make_session()
    sdk = _FakeSDK()
    _ready(sess, sdk)
    for i in range(200):
        sess.submit_audio(bytes([i % 256]) * 64)
    assert sess._audio_queue.qsize() <= 64
    assert sess.metrics.dropped_audio_chunks > 0


# 7. duplicate reconnect prevention: two failures -> still one task
def test_duplicate_failures_single_reconnect_task():
    sess, _ = _make_session()
    sdk = _FakeSDK(fail_with=_dead_socket_error())
    _ready(sess, sdk)

    async def go():
        await sess._fail_once("boom-1")
        first = sess._reconnect_task
        await sess._fail_once("boom-2")
        assert sess._reconnect_task is first
        first.cancel()
        try:
            await first
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(go())
    assert sess.metrics.connection_failure == 1


# 11. reconnect uses stored resumption handle
def test_reconnect_uses_resumption_handle():
    sess, _ = _make_session()
    sess._resumption_handle = "HANDLE-X"
    seen = {}

    async def fake_connect(resume_handle=None):
        seen["handle"] = resume_handle
        # Simulate a working connect without SDK.
        from desktop_agent.speech import gemini_live as G

        sess._session = _FakeSDK()
        await sess._set_state(G.ConnState.READY)

    sess.connect = fake_connect  # type: ignore[method-assign]

    async def go():
        await sess._fail_once("test")
        task = sess._reconnect_task
        assert task is not None
        await task

    asyncio.run(go())
    assert seen.get("handle") == "HANDLE-X"


# 12. GoAway -> draining -> reconnect scheduled
def test_goaway_triggers_draining_reconnect():
    sess, events = _make_session()
    sdk = _FakeSDK()
    _ready(sess, sdk)

    async def go():
        await sess._handle_message(_t.SimpleNamespace(
            go_away=_t.SimpleNamespace(time_left=10),
            session_resumption_update=None, tool_call=None,
            tool_call_cancellation=None, server_content=None))
        assert sess._reconnect_task is not None
        sess._reconnect_task.cancel()
        try:
            await sess._reconnect_task
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(go())
    assert events[0].kind == "go_away"


# 10/13/14. normal + application shutdown: CLOSED, no reconnect
def test_close_is_clean_with_no_reconnect():
    sess, events = _make_session()
    sdk = _FakeSDK()
    _ready(sess, sdk)

    async def go():
        await sess.close()

    asyncio.run(go())
    from desktop_agent.speech import gemini_live as G

    assert sess.state == G.ConnState.CLOSED
    assert sess._reconnect_task is None
    assert any(e.kind == "closed" for e in events)


# 6b. DIRECT send_audio storm: 100 sequential direct writes to a dead socket
# -> exactly 1 SDK write, 1 failure event, 1 reconnect task, 99 refusals.
def test_direct_send_audio_storm_single_write():
    sess, events = _make_session()
    sdk = _FakeSDK(fail_with=_dead_socket_error())
    _ready(sess, sdk)

    async def go():
        results = []
        for _ in range(100):
            results.append(await sess.send_audio(b"\x01\x02" * 100))
        return results

    results = asyncio.run(go())
    assert results[0] is False  # the failing write reports failure, not success
    assert all(r is False for r in results)
    assert sdk.writes == 1  # only the first call touched the dead socket
    failures = [e for e in events if e.kind == "connection_failed"]
    assert len(failures) == 1
    assert sess._reconnect_task is not None
    sess._reconnect_task.cancel()
    try:
        asyncio.run(sess._reconnect_task)
    except (asyncio.CancelledError, Exception):
        pass


# 15. tool call DURING reconnect: executes safely, response dropped, no storm.
def test_tool_call_during_reconnect_safe():
    sess, events = _make_session()
    sdk = _FakeSDK(fail_with=_dead_socket_error())
    _ready(sess, sdk)
    from desktop_agent.speech import gemini_live as G

    async def go():
        await sess._fail_once("boom")
        assert sess.state in (G.ConnState.FAILED, G.ConnState.RECONNECTING)
        task = sess._reconnect_task
        # Unknown tool: allowlist refusal, no registry/desktop dependency.
        fc = _t.SimpleNamespace(id="t-reconnect-1", name="no_such_tool", args={})
        await sess._handle_tool_call(fc)
        assert sess.tools.already_done("t-reconnect-1") is not None
        # Tool response could not be sent on the dead session: dropped, counted.
        assert sess.metrics.dead_writes_prevented >= 1
        # No duplicate reconnect, no READY regression, no crash.
        assert sess._reconnect_task is task
        assert sess.state != G.ConnState.READY
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(go())
    assert len([e for e in events if e.kind == "connection_failed"]) == 1


# 16. interruption DURING reconnect: barge-in event flows, recovery untouched.
def test_interruption_during_reconnect_safe():
    sess, events = _make_session()
    sdk = _FakeSDK(fail_with=_dead_socket_error())
    _ready(sess, sdk)
    from desktop_agent.speech import gemini_live as G

    async def go():
        await sess._fail_once("boom")
        task = sess._reconnect_task
        before = sess.metrics.interruptions
        await sess._handle_message(_t.SimpleNamespace(
            go_away=None, session_resumption_update=None, tool_call=None,
            tool_call_cancellation=None,
            server_content=_t.SimpleNamespace(
                interrupted=True, input_transcription=None,
                output_transcription=None,
                model_turn=_t.SimpleNamespace(parts=[]),
                turn_complete=False)))
        assert sess.metrics.interruptions == before + 1
        assert any(e.kind == "interrupted" for e in events)
        assert sess._reconnect_task is task
        assert sess.state != G.ConnState.READY
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(go())
    assert len([e for e in events if e.kind == "connection_failed"]) == 1


# 15/16. tool call + interruption paths stay alive across failure (no crash)
def test_tool_call_off_receive_loop():
    sess, events = _make_session()
    sdk = _FakeSDK()
    _ready(sess, sdk)
    fc = _t.SimpleNamespace(id="t1", name="currentDateTime", args={})

    async def go():
        import desktop_agent.registry as R

        R.load_all()
        await sess._handle_message(_t.SimpleNamespace(
            go_away=None, session_resumption_update=None,
            tool_call=_t.SimpleNamespace(function_calls=[fc]),
            tool_call_cancellation=None, server_content=None))
        # Background task runs independently of the receive loop.
        for _ in range(100):
            if sess.tools.already_done("t1") is not None:
                break
            await asyncio.sleep(0.01)
        assert sess.tools.already_done("t1") is not None

    asyncio.run(go())


# 17. Backlog-full tool calls get an error response (never hang Gemini).
def test_tool_backlog_full_rejects_with_error_response():
    sess, events = _make_session()

    async def go():
        async def hang():
            await asyncio.sleep(3600)

        # Occupy all 8 tool slots with stuck tasks.
        for _ in range(8):
            t = asyncio.create_task(hang())
            sess._tool_tasks.add(t)
            t.add_done_callback(sess._tool_tasks.discard)

        sent = []

        async def fake_send(call_id, name, result):
            sent.append((call_id, name, result))

        sess.send_tool_response = fake_send
        fc = _t.SimpleNamespace(id="c-backlog", name="currentDateTime", args={})
        await sess._handle_message(_t.SimpleNamespace(
            go_away=None, session_resumption_update=None,
            tool_call=_t.SimpleNamespace(function_calls=[fc]),
            tool_call_cancellation=None, server_content=None))
        # Rejection task completes on its own; the real tool must NOT run.
        for _ in range(100):
            if sent:
                break
            await asyncio.sleep(0.01)
        for t in list(sess._tool_tasks):
            t.cancel()
        assert sent, "backlogged call got no FunctionResponse (Gemini would hang)"
        assert sent[0][0] == "c-backlog"
        assert "backlog" in str(sent[0][2]).lower()
        assert any(e.kind == "tool_result" and e.data.get("ok") is False
                   for e in events)
        assert sess.tools.already_done("c-backlog") is None

    asyncio.run(go())
