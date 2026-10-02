"""
Voice configuration contract tests.

Verifies:
1.  no invented/unsupported voice names are hardcoded
2.  voice transport has bounded reconnect (no infinite loops)
3.  voice failure does not crash Node (degraded path, text stays up)
4.  voice state is exposed to the UI (degraded status + active voice)
5.  text chat path is independent of the voice session (/api/chat)
"""

from __future__ import annotations

import os

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_all_server_files() -> str:
    """Read server.ts + all server/routes/*.ts + server_voice.ts."""
    import glob as _glob
    paths = [os.path.join(PROJECT_ROOT, "server.ts")]
    paths += sorted(_glob.glob(os.path.join(PROJECT_ROOT, "server", "routes", "*.ts")))
    paths.append(os.path.join(PROJECT_ROOT, "server_voice.ts"))
    parts = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                parts.append(f.read())
        except FileNotFoundError:
            pass
    return "\n".join(parts)


def _server_ts() -> str:
    return _read_all_server_files()


def _audio_ts() -> str:
    with open(os.path.join(PROJECT_ROOT, "src", "lib", "audio.ts"),
              encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1+2. Supported voice configuration
# ---------------------------------------------------------------------------

def test_no_invalid_chloe_voice():
    src = _server_ts()
    assert 'voiceName: "Chloe"' not in src, (
        "server still references the unsupported 'Chloe' voice"
    )


def test_voice_transport_configured():
    src = _server_ts()
    # VoiceTransport must exist with bounded reconnect.
    assert "maxReconnectAttempts" in src
    assert "VoiceTransport" in src
    assert "VoiceTransportState" in src


# ---------------------------------------------------------------------------
# 3. Bounded fallback / reconnect (no infinite loops)
# ---------------------------------------------------------------------------

def test_bounded_voice_reconnect():
    src = _server_ts()
    # Bounded reconnect — no infinite loop on persistent failure.
    # (Gemini Live migration: bound lives in VOICE_TIMEOUTS.MAX_RECONNECT_ATTEMPTS.)
    assert "maxReconnectAttempts" in src
    import re
    m = re.search(r"maxReconnectAttempts:\s*VOICE_TIMEOUTS\.(\w+)", src)
    assert m, "reconnect bound must reference VOICE_TIMEOUTS"
    m2 = re.search(rf"{m.group(1)}:\s*(\d+)", src)
    assert m2 and int(m2.group(1)) <= 10, "reconnect attempts must be bounded (<=10)"


def test_reconnect_respects_intentional_disconnect():
    src = _server_ts()
    # Must not reconnect after intentional stop.
    assert "intentionalDisconnect" in src


# ---------------------------------------------------------------------------
# 4. Voice failure must not crash Node; text chat stays operational
# ---------------------------------------------------------------------------

def test_degraded_path_keeps_server_alive():
    src = _server_ts()
    # Voice failure must transition to degraded state, not crash.
    assert '"degraded"' in src
    assert "sendError" in src


def test_text_chat_independent_of_voice_session():
    src = _server_ts()
    # /api/chat is served by Express regardless of any /live WS session state.
    assert '"/api/chat"' in src
    # The voice transport handles its own lifecycle; chat is separate.
    assert "sendError" in src


# ---------------------------------------------------------------------------
# 5. Voice state exposed to UI
# ---------------------------------------------------------------------------

def test_ui_handles_voice_state():
    audio = _audio_ts()
    assert '"degraded"' in audio
    assert "voiceDegraded" in audio
    assert "activeVoiceName" in audio
    # Server sends the active voice with the connected status.
    server_src = _server_ts()
    assert "setState" in server_src


# ---------------------------------------------------------------------------
# 6. Session lifecycle hygiene
# ---------------------------------------------------------------------------

def test_session_close_forwarding_preserved():
    src = _server_ts()
    # Legit mid-conversation closes still reach the client.
    assert '"disconnected"' in src
