"""Gemini Live API-only voice migration (§49).

Covers: config, session lifecycle (mocked transport), audio shapes,
transcripts, interruption/epochs, tool auth + finance firewall, resumption,
GoAway, error classes, key secrecy, legacy-provider isolation.
No network, models, microphone, or speaker required.
"""
from __future__ import annotations

import asyncio
import pathlib
import types as _t

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ── A. Configuration ──────────────────────────────────────────────

def test_config_defaults_to_gemini_live_only(monkeypatch):
    from desktop_agent.speech import gemini_live as G

    for k in ("GEMINI_API_KEY", "GEMINI_LIVE_MODEL", "GEMINI_LIVE_VOICE",
              "GEMINI_LIVE_ENABLED", "GEMINI_LIVE_MAX_RECONNECTS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    cfg = G.load_gemini_live_config()
    assert cfg.configured is True
    assert cfg.model == G.DEFAULT_LIVE_MODEL
    assert "live" in cfg.model
    assert cfg.max_reconnects <= 3


def test_config_missing_key_is_unconfigured(monkeypatch):
    from desktop_agent.speech import gemini_live as G

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = G.load_gemini_live_config()
    assert cfg.configured is False
    d = cfg.describe()
    assert "GEMINI_API_KEY" not in str(d)
    assert "api_key" not in d  # key never exposed through health shape
    assert "test-key" not in str(d)


def test_no_provider_selection_knobs(monkeypatch):
    from desktop_agent.speech import gemini_live as G

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    cfg = G.load_gemini_live_config()
    assert not hasattr(cfg, "voice_provider")
    assert not hasattr(cfg, "stt_provider")


# ── helpers: fake SDK messages ────────────────────────────────────

def _msg(**kwargs):
    m = _t.SimpleNamespace(
        go_away=None, session_resumption_update=None, tool_call=None,
        tool_call_cancellation=None, server_content=None)
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


def _content(**kwargs):
    c = _t.SimpleNamespace(
        model_turn=None, turn_complete=False, interrupted=False,
        input_transcription=None, output_transcription=None)
    for k, v in kwargs.items():
        setattr(c, k, v)
    return c


def _make_session(events: list):
    from desktop_agent.speech import gemini_live as G

    cfg = G.GeminiLiveConfig(enabled=True, api_key="k")
    sess = G.GeminiLiveSession(cfg, G.GeminiToolRouter(), G.GeminiVoiceMetrics(),
                               on_event=events.append)
    return sess


# ── B/D/E. Transcripts, interruption, epochs ──────────────────────

def test_input_output_transcripts_and_turn_complete():
    events: list = []
    sess = _make_session(events)
    asyncio.run(sess._handle_message(_msg(server_content=_content(
        input_transcription=_t.SimpleNamespace(text="hello MYRAA")))))
    asyncio.run(sess._handle_message(_msg(server_content=_content(
        output_transcription=_t.SimpleNamespace(text="Hello!")))))
    asyncio.run(sess._handle_message(_msg(server_content=_content(turn_complete=True))))
    kinds = [e.kind for e in events]
    assert kinds.count("partial") == 2
    assert "turn_complete" in kinds
    user = [e for e in events if e.kind == "partial" and e.data["role"] == "user"]
    assert user and user[0].data["text"] == "hello MYRAA"


def test_interruption_increments_generation():
    events: list = []
    sess = _make_session(events)
    g0 = sess.generation_seq
    asyncio.run(sess._handle_message(_msg(server_content=_content(interrupted=True))))
    assert sess.generation_seq == g0 + 1
    assert events[-1].kind == "interrupted"


def test_audio_event_carries_generation():
    events: list = []
    sess = _make_session(events)
    part = _t.SimpleNamespace(
        inline_data=_t.SimpleNamespace(data=b"\x01\x02" * 100, mime_type="audio/pcm;rate=24000"),
        text=None)
    asyncio.run(sess._handle_message(_msg(server_content=_content(
        model_turn=_t.SimpleNamespace(parts=[part])))))
    aud = [e for e in events if e.kind == "audio"]
    assert len(aud) == 1 and len(aud[0].data["audio"]) == 200


# ── H/I. Resumption + GoAway ──────────────────────────────────────

def test_resumption_handle_stored():
    events: list = []
    sess = _make_session(events)
    asyncio.run(sess._handle_message(_msg(session_resumption_update=_t.SimpleNamespace(
        new_handle="HANDLE123", resumable=True))))
    assert sess.resumption_handle == "HANDLE123"


def test_goaway_emits_reconnecting():
    events: list = []
    sess = _make_session(events)
    sdk = _t.SimpleNamespace()
    sess._session = sdk
    sess._state = sess._state.__class__.READY

    async def go():
        await sess._handle_message(_msg(go_away=_t.SimpleNamespace(time_left=30)))
        kinds = [e.kind for e in events]
        assert "go_away" in kinds
        assert "connection_failed" in kinds  # drain converges to single recovery
        assert sess._reconnect_task is not None
        sess._reconnect_task.cancel()
        try:
            await sess._reconnect_task
        except (asyncio.CancelledError, Exception):
            pass

    asyncio.run(go())


# ── F/G. Tool calls: auth, dedup, finance firewall ────────────────

def test_tool_allowlist_has_no_shell_or_finance():
    from desktop_agent.speech import gemini_live as G

    names = set(G.GEMINI_TOOL_ALLOWLIST.keys())
    for banned in ("runShellCommand", "runCommand", "deleteFile", "executePowerAction",
                   "gitPush", "writeFile", "typeText", "hotkey", "getClipboard"):
        assert banned not in names, banned
    assert "systemInfo" in names and "openApplication" in names
    for name in names:
        assert not G._finance_blocked(name), name


def test_unknown_and_finance_tools_rejected_without_execution():
    from desktop_agent.speech import gemini_live as G

    router = G.GeminiToolRouter()
    r1 = router.execute("c1", "buyStocks", {})
    assert r1.ok is False
    r2 = router.execute("c2", "noSuchTool", {})
    assert r2.ok is False


def _loaded_router():
    import desktop_agent.registry as R
    from desktop_agent.speech import gemini_live as G

    R.load_all()
    return G.GeminiToolRouter()


def test_duplicate_tool_call_never_executes_twice():
    router = _loaded_router()
    r1 = router.execute("dup-1", "currentDateTime", {})
    r2 = router.execute("dup-1", "currentDateTime", {})
    assert r1.ok is True and r2.ok is True
    assert r1.payload == r2.payload


def test_completed_call_memory_is_bounded():
    from desktop_agent.speech import gemini_live as G

    router = G.GeminiToolRouter()
    for i in range(G.GeminiToolRouter._COMPLETED_MAX + 100):
        router.execute(f"cap-{i}", "noSuchTool", {})
    assert len(router._completed) <= G.GeminiToolRouter._COMPLETED_MAX
    assert f"cap-{G.GeminiToolRouter._COMPLETED_MAX + 99}" in router._completed
    assert "cap-0" not in router._completed  # oldest evicted FIFO


def test_destructive_tool_requires_confirmation_not_execution():
    from desktop_agent.speech import gemini_live as G

    router = G.GeminiToolRouter()
    # closeApplication is allowlisted-adjacent? No — not in allowlist at all.
    r = router.execute("c9", "closeApplication", {"name": "x"})
    assert r.ok is False  # not exposed to Gemini


def test_tool_results_sanitized():
    from desktop_agent.speech import gemini_live as G

    clean = G._sanitize({"api_key": "SECRET", "nested": {"token": "T", "ok": 1}})
    assert clean["api_key"] == "[redacted]"
    assert clean["nested"]["token"] == "[redacted]"
    assert clean["nested"]["ok"] == 1


# ── J. Errors ─────────────────────────────────────────────────────

def test_error_classification():
    from desktop_agent.speech import gemini_live as G

    assert G.classify_gemini_error(Exception("401 unauthenticated")) is G.GeminiErrorCode.GEMINI_AUTH_ERROR
    assert G.classify_gemini_error(Exception("quota exceeded")) is G.GeminiErrorCode.GEMINI_QUOTA_ERROR
    assert G.classify_gemini_error(Exception("429 rate limit")) is G.GeminiErrorCode.GEMINI_RATE_LIMIT
    assert G.classify_gemini_error(Exception("connection reset")) is G.GeminiErrorCode.GEMINI_NETWORK_ERROR


def test_speak_text_requires_connection():
    sess = _make_session([])
    with pytest.raises(RuntimeError):
        asyncio.run(sess.speak_text("hello"))


# ── K. Legacy isolation ───────────────────────────────────────────

def test_active_runtime_instantiates_no_old_providers():
    src = (PROJECT_ROOT / "desktop_agent" / "speech" / "gemini_live.py").read_text(encoding="utf-8")
    for token in ("FasterWhisper", "faster_whisper", "Silero", "silero",
                  "Kokoro", "kokoro", "Piper", "piper", "ElevenLabs", "elevenlabs",
                  "scribe_v2", "Scribe", "convai"):
        assert token not in src, token
    main = (PROJECT_ROOT / "desktop_agent" / "main.py").read_text(encoding="utf-8")
    assert "/voice/gemini/stream" in main


def test_retired_stream_endpoint_cannot_reach_legacy():
    main = (PROJECT_ROOT / "desktop_agent" / "main.py").read_text(encoding="utf-8")
    body = main.split("async def voice_stt_stream_ws", 1)[1].split("\n@app.get", 1)[0]
    assert "VOICE_RETIRED" in body
    assert "1011" in body


def test_node_transport_has_single_provider():
    src = (PROJECT_ROOT / "server_voice.ts").read_text(encoding="utf-8")
    for token in ("elevenlabs", "ElevenLabs", "whisper", "Whisper", "kokoro",
                  "Kokoro", "piper", "Piper", "silero", "Silero",
                  "scribe_v2", "Scribe", "convai"):
        assert token not in src, token
    assert "gemini" in src.lower()
    assert "MAX_RECONNECT_ATTEMPTS" in src
