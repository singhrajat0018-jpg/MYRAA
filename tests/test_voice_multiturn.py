"""Multi-turn voice conversation simulation (fake transport, REAL session code).

Reproduces the reported production failure: "only ONE response, subsequent
turns die". Drives GeminiLiveSession._audio_sender + receive_loop against a
scripted FakeSDK stream for 3 turns + mid-turn interruption and asserts the
session stays alive and every turn flows.

No network, SDK, microphone, or speaker required.
"""
from __future__ import annotations

import asyncio
import types as _t


def _make_session():
    from desktop_agent.speech import gemini_live as G

    cfg = G.GeminiLiveConfig(enabled=True, api_key="k")
    events: list = []
    sess = G.GeminiLiveSession(cfg, G.GeminiToolRouter(), G.GeminiVoiceMetrics(),
                               on_event=events.append)
    return sess, events


class _ScriptedSDK:
    """Fake Gemini transport: yields a scripted multi-turn conversation.

    Script entries are (min_inputs, msg): each message is released only after
    the sender has delivered min_inputs mic chunks — this models realtime
    backpressure so the script cannot outrun the sender (and the stream must
    stay OPEN after the last turn, like production). A None message waits
    forever (idle open stream).
    """

    def __init__(self, script):
        self.script = list(script)
        self.inputs: list[bytes] = []
        self.closed = False

    async def send_realtime_input(self, **kwargs):
        audio = kwargs.get("audio")
        data = getattr(audio, "data", b"") if audio is not None else b""
        self.inputs.append(bytes(data))

    async def receive(self):
        for min_inputs, msg in self.script:
            while len(self.inputs) < min_inputs:
                await asyncio.sleep(0.001)
            if msg is None:
                await asyncio.sleep(3600)
                return
            yield msg

    async def close(self):
        self.closed = True


def _content(*, interrupted=False, in_text=None, out_text=None,
             audio_chunks=(), turn_complete=False):
    parts = []
    for chunk in audio_chunks:
        parts.append(_t.SimpleNamespace(inline_data=_t.SimpleNamespace(data=chunk),
                                        text=None))
    if out_text:
        parts.append(_t.SimpleNamespace(inline_data=None, text=out_text))
    return _t.SimpleNamespace(
        interrupted=interrupted,
        input_transcription=(_t.SimpleNamespace(text=in_text)
                             if in_text is not None else None),
        output_transcription=(_t.SimpleNamespace(text=out_text)
                              if out_text is not None else None),
        model_turn=_t.SimpleNamespace(parts=parts),
        turn_complete=turn_complete)


def _msg(content):
    return _t.SimpleNamespace(go_away=None, session_resumption_update=None,
                              tool_call=None, tool_call_cancellation=None,
                              server_content=content)


def _ready(sess, sdk):
    sess._session = sdk
    sess._state = sess._state.__class__.READY
    sess._closed = False


def test_three_turns_plus_interrupt_all_flow_through_one_session():
    sess, events = _make_session()
    script = [
        (2, _msg(_content(in_text="hello myraa"))),
        (4, _msg(_content(audio_chunks=[b"\x01" * 320], out_text="Hello!"))),
        (6, _msg(_content(audio_chunks=[b"\x02" * 320], turn_complete=True))),
        # Turn 2: user barges in mid-response.
        (10, _msg(_content(interrupted=True))),
        (12, _msg(_content(in_text="what can you do"))),
        (14, _msg(_content(audio_chunks=[b"\x03" * 320], turn_complete=True))),
        # Turn 3: normal. Stream stays OPEN afterwards (production shape).
        (16, _msg(_content(in_text="tell me something interesting"))),
        (18, _msg(_content(audio_chunks=[b"\x04" * 320], turn_complete=True))),
        (10 ** 9, None),
    ]
    sdk = _ScriptedSDK(script)
    _ready(sess, sdk)

    async def go():
        recv = asyncio.create_task(sess.receive_loop())
        sender = asyncio.create_task(sess._audio_sender())
        # Mic keeps streaming across all turns (never stops).
        for _ in range(30):
            assert sess.submit_audio(b"\x09" * 640) is True
            await asyncio.sleep(0)
        for _ in range(500):
            if len([e for e in events if e.kind == "turn_complete"]) >= 3:
                break
            await asyncio.sleep(0.01)
        recv.cancel()
        sender.cancel()
        for t in (recv, sender):
            try:
                await t
            except asyncio.CancelledError:
                pass

    asyncio.run(go())

    turns = [e for e in events if e.kind == "turn_complete"]
    assert len(turns) == 3, f"expected 3 turn_completes, got {len(turns)}"
    audios = [e for e in events if e.kind == "audio"]
    assert len(audios) == 4, f"expected 4 audio events, got {len(audios)}"
    # Generation advanced exactly once (the single interruption).
    assert sess.generation_seq == 1
    gens = {e.data.get("generation") for e in audios}
    assert gens == {"G0", "G1"}, f"audio generations leaked across turns: {gens}"
    # Session is still alive and accepting input after turn 3.
    assert sess.state.__class__.READY.value == sess.state.value
    assert sess.submit_audio(b"\x09" * 640) is True
    assert sdk.inputs, "no mic audio ever reached the transport"


def test_clean_receive_stream_end_converges_to_recovery():
    """A silently-ending server stream must NOT look like a healthy session.

    Before the fix, receive_loop simply returned: sender kept running, state
    stayed READY, no event fired — the exact "one response then silence while
    everything looks alive" shape. After the fix it converges into _fail_once
    (single reconnect path), which the test observes as connection_failed.
    """
    sess, events = _make_session()
    sdk = _ScriptedSDK([])  # stream ends immediately, no error
    _ready(sess, sdk)

    async def go():
        done = asyncio.create_task(asyncio.sleep(0))
        await done
        sess._reconnect_task = done  # done task: recovery scheduled, not run
        await sess.receive_loop()

    asyncio.run(go())
    assert any(e.kind == "connection_failed" for e in events), \
        "clean stream end produced no failure event (silent death)"


def _long_script(turns, interrupts=()):
    """Programmatic N-turn script with mid-turn interruptions.

    Returns (script, expected_generations): each turn contributes one audio
    event + one turn_complete; each interruption advances the generation.
    """
    script = []
    n = 0
    for i in range(turns):
        n += 2
        script.append((n, _msg(_content(in_text=f"turn {i}"))))
        if i in interrupts:
            n += 2
            script.append((n, _msg(_content(interrupted=True))))
        n += 2
        script.append((n, _msg(_content(audio_chunks=[bytes([i + 1]) * 160],
                                        turn_complete=True))))
    script.append((10 ** 9, None))  # stream stays OPEN (production shape)
    return script, {f"G{g}" for g in range(len(interrupts) + 1)}


def _run_conversation(script, mic_chunks):
    sess, events = _make_session()
    sdk = _ScriptedSDK(script)
    _ready(sess, sdk)

    async def go():
        recv = asyncio.create_task(sess.receive_loop())
        sender = asyncio.create_task(sess._audio_sender())
        for _ in range(mic_chunks):
            assert sess.submit_audio(b"\x09" * 640) is True
            await asyncio.sleep(0)
        # Sender keeps draining while the scripted stream plays out.
        for _ in range(2000):
            if len([e for e in events if e.kind == "turn_complete"]) >= _turns_in(script):
                break
            await asyncio.sleep(0.005)
            # Keep mic alive for long runs (never stops mid-conversation).
            assert sess.submit_audio(b"\x09" * 640) is True
        recv.cancel()
        sender.cancel()
        for t in (recv, sender):
            try:
                await t
            except asyncio.CancelledError:
                pass

    asyncio.run(go())
    return sess, events, sdk


def _turns_in(script):
    return sum(1 for _, m in script
               if m is not None and getattr(getattr(m, "server_content", None),
                                            "turn_complete", False))


def test_ten_consecutive_turns_no_dupes_session_survives():
    script, gens = _long_script(10)
    sess, events, sdk = _run_conversation(script, 60)
    turns = [e for e in events if e.kind == "turn_complete"]
    audios = [e for e in events if e.kind == "audio"]
    assert len(turns) == 10, f"expected 10 turn_completes, got {len(turns)}"
    assert len(audios) == 10, f"expected 10 audio events, got {len(audios)}"
    # Streaming order: each turn's audio precedes its turn_complete.
    for i in range(10):
        ai = events.index(audios[i])
        ti = events.index(turns[i])
        assert ai < ti, f"turn {i}: audio not streamed before completion"
    assert {e.data.get("generation") for e in audios} == gens == {"G0"}
    assert sess.state.__class__.READY.value == sess.state.value
    assert sess.submit_audio(b"\x09" * 640) is True
    assert len(sdk.inputs) >= 60  # every submitted chunk reached transport


def test_triple_interruption_isolates_generations_then_continues():
    script, gens = _long_script(6, interrupts=(1, 3, 4))
    sess, events, sdk = _run_conversation(script, 90)
    turns = [e for e in events if e.kind == "turn_complete"]
    audios = [e for e in events if e.kind == "audio"]
    assert len(turns) == 6, f"expected 6 turn_completes, got {len(turns)}"
    assert len(audios) == 6, f"expected 6 audio events, got {len(audios)}"
    assert sess.generation_seq == 3
    assert {e.data.get("generation") for e in audios} == gens
    # Post-interruption turns still complete on the SAME session.
    assert sess.state.__class__.READY.value == sess.state.value
    assert sess.submit_audio(b"\x09" * 640) is True


def test_twenty_turns_two_interruptions_session_stable():
    # Long-run shape: 20 consecutive turns, interruptions mid-run, one
    # session, no duplication, no leak of generations, still READY after.
    script, gens = _long_script(20, interrupts=(5, 12))
    sess, events, sdk = _run_conversation(script, 150)
    turns = [e for e in events if e.kind == "turn_complete"]
    audios = [e for e in events if e.kind == "audio"]
    assert len(turns) == 20, f"expected 20 turn_completes, got {len(turns)}"
    assert len(audios) == 20, f"expected 20 audio events, got {len(audios)}"
    assert sess.generation_seq == 2
    assert {e.data.get("generation") for e in audios} == gens
    assert sess.state.__class__.READY.value == sess.state.value
    assert sess.submit_audio(b"\x09" * 640) is True
    # Bounded internals after a long run: no accumulation.
    assert sess._audio_queue.qsize() <= 64
    assert len(sess._tool_tasks) == 0


def test_reconnect_loop_passes_resumption_handle_and_resets_budget():
    sess, events = _make_session()
    sess._resumption_handle = "h1"
    seen = {}

    async def fake_connect(resume_handle=None):
        seen["handle"] = resume_handle
        sess._session = object()
        await sess._set_state(sess._state.__class__.READY)

    sess.connect = fake_connect  # type: ignore[method-assign]
    asyncio.run(sess._reconnect_loop())
    assert seen.get("handle") == "h1"
    assert sess._reconnect_attempts == 0
    assert any(e.kind == "reconnecting" for e in events)
    assert any(e.kind == "reconnected" for e in events)
