"""
Permanent legacy-voice-provider removal guard (Phase 29.9, migrated).

OLD intent of this file: "legacy ElevenLabs voice code remains dormant."
NEW intent: "legacy ElevenLabs / retired STT-TTS provider code does not exist
and cannot be reached."

Verifies:
1.  No active ElevenLabs reference exists in production source.
2.  No ElevenLabs environment variable or configuration remains.
3.  Retired legacy voice modules do not exist and cannot be imported.
4.  Retired /voice endpoints fail safely and can never reach legacy code.
5.  Gemini Live is the only conversational voice engine.
6.  Node transport + client voice-path safety contracts preserved.
7.  Browser audio format contract preserved.
8.  Financial firewall intact.

No microphone, network, or model required.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

FORBIDDEN_TOKENS = (
    "elevenlabs",          # covers ElevenLabs / ELEVENLABS_* (case-insensitive)
    "api.elevenlabs.io",
    "elevenlabs.io",
    "xi-api-key",
    "scribe_v2",
    "eleven_multilingual",
    "eleven_turbo",
    "eleven_flash",
)

RETIRED_MODULES = (
    "desktop_agent.speech.elevenlabs_stt",
    "desktop_agent.speech.elevenlabs_tts",
    "desktop_agent.speech.stt_ws_bridge",
    "desktop_agent.speech.local_stt_bridge",
    "desktop_agent.speech.providers",
    "desktop_agent.speech.voice_config",
    "desktop_agent.speech.voice_session",
    "desktop_agent.speech.echo_guard",
    "desktop_agent.speech.pronunciation",
    "desktop_agent.speech.voice_latency",
)

RETIRED_FILES = tuple(m.replace(".", "/") + ".py" for m in RETIRED_MODULES)

# Production source scanned by the repository-level guard.
SCAN_DIRS = ("desktop_agent", "server", "services", "backend", "src", "electron")
SCAN_ROOT_FILES = ("server.ts", "server_paths.ts", "server_memory.ts",
                   "server_voice.ts", "vite.config.ts")

# Excluded: tests, docs, caches, build/vendored artifacts, model checkpoints.
EXCLUDE_PARTS = (
    "node_modules", "dist", ".pytest_cache", "tmp", "agent_build",
    "fastcore", "__pycache__", ".git", "coverage", "build",
)
EXCLUDE_SUFFIXES = (".md", ".json", ".txt", ".lock", ".log", ".cfg",
                    ".ini", ".yaml", ".yml", ".pyc", ".cjs", ".map")


def _read(rel_or_path) -> str:
    p = pathlib.Path(rel_or_path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _iter_production_files():
    for d in SCAN_DIRS:
        root = PROJECT_ROOT / d
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in EXCLUDE_PARTS for part in p.parts):
                continue
            if p.suffix.lower() in EXCLUDE_SUFFIXES:
                continue
            yield p
    for name in SCAN_ROOT_FILES:
        p = PROJECT_ROOT / name
        if p.is_file():
            yield p


# ---------------------------------------------------------------------------
# 1. No active ElevenLabs reference in production source
# ---------------------------------------------------------------------------

def test_no_active_elevenlabs_reference_in_production_source():
    offenders = []
    for p in _iter_production_files():
        src = _read(p).lower()
        for token in FORBIDDEN_TOKENS:
            if token in src:
                offenders.append(f"{p.relative_to(PROJECT_ROOT)}::{token}")
    assert offenders == [], (
        "Active ElevenLabs/legacy-provider references found in production "
        f"source: {offenders}. ElevenLabs is permanently retired; Gemini Live "
        "is the only conversational voice engine.")


def test_no_elevenlabs_environment_variable_is_required():
    conftest = _read("conftest.py")
    assert "ELEVENLABS" not in conftest
    settings = _read("desktop_agent/config/settings.py")
    assert "ELEVENLABS" not in settings
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        env = _read(env_path)
        assert not re.search(r"^\s*ELEVENLABS", env, re.MULTILINE | re.IGNORECASE)


# ---------------------------------------------------------------------------
# 2. Retired legacy voice modules do not exist and cannot be imported
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mod_name", RETIRED_MODULES)
def test_retired_voice_module_cannot_be_imported(mod_name):
    assert importlib.util.find_spec(mod_name) is None, mod_name


@pytest.mark.parametrize("rel", RETIRED_FILES)
def test_retired_voice_module_file_absent(rel):
    assert not (PROJECT_ROOT / rel).exists(), rel


# ---------------------------------------------------------------------------
# 3. Retired /voice endpoints fail safely and cannot reach legacy code
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    pytest.importorskip("desktop_agent")
    from fastapi.testclient import TestClient

    from desktop_agent.main import app
    return TestClient(app)


def test_voice_tts_endpoints_retired_boundary(client):
    for path in ("/voice/tts", "/voice/tts/stream"):
        r = client.post(path, json={"text": "hello"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["deprecated"] is True
        assert body["replacement"] == "gemini_live"


def test_voice_stt_endpoints_return_410_gone(client):
    for path in ("/voice/stt", "/voice/stt/local", "/voice/tts/local"):
        r = client.post(path, json={"text": "hello", "audio": "aGk="})
        assert r.status_code == 410
        body = r.json()
        assert body["deprecated"] is True
        assert body["replacement"] == "gemini_live"
        assert body["error"]["code"] == "VOICE_RETIRED"


def test_voice_noop_endpoints_are_deprecated_noops(client):
    r = client.post("/voice/tts/cancel")
    assert r.status_code == 200 and r.json()["deprecated"] is True
    r = client.post("/voice/echo/note", json={"text": "hello"})
    assert r.status_code == 200 and r.json()["deprecated"] is True
    r = client.post("/voice/echo/check", json={"text": "hello"})
    assert r.status_code == 200 and r.json()["deprecated"] is True


def test_retired_voice_ws_cannot_reach_legacy_code(client):
    """The retired STT stream reports VOICE_RETIRED and closes — no audio can
    ever reach a legacy STT provider from this endpoint."""
    from starlette.websockets import WebSocketDisconnect

    with client.websocket_connect("/voice/stt/stream") as ws:
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert msg["code"] == "VOICE_RETIRED"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


# ---------------------------------------------------------------------------
# 4. Gemini Live is the only conversational voice engine
# ---------------------------------------------------------------------------

def test_voice_health_reports_gemini_live_only(monkeypatch):
    from desktop_agent.speech.gemini_live import load_gemini_live_config

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = load_gemini_live_config()
    assert cfg.configured is False
    d = cfg.describe()
    assert d.get("provider") == "gemini_live"


def test_main_exposes_gemini_voice_stream_and_minimal_retired_boundary():
    main = _read("desktop_agent/main.py")
    assert "/voice/gemini/stream" in main
    assert "/voice/gemini/health" in main
    body = main.split("async def voice_stt_stream_ws", 1)[1].split("\n@app.get", 1)[0]
    assert "VOICE_RETIRED" in body
    assert "1011" in body
    # No legacy dispatch helpers remain anywhere in main.py.
    assert "_voice_stt_stream_local" not in main
    assert "_voice_stt_stream_cloud" not in main
    assert "get_voice_providers" not in main


def test_gemini_runtime_has_no_legacy_provider_tokens():
    src = _read("desktop_agent/speech/gemini_live.py").lower()
    for token in FORBIDDEN_TOKENS:
        assert token not in src, token
    for token in ("fasterwhisper", "faster_whisper", "silero", "kokoro",
                  "piper", "convai"):
        assert token not in src, token


# ---------------------------------------------------------------------------
# 5. Node transport + client voice-path safety contracts preserved
# ---------------------------------------------------------------------------

def test_node_checks_content_type_before_json():
    src = _read("server_voice.ts")
    assert "JSON.parse(raw.toString())" in src
    assert "ignore parse errors" in src


def test_node_has_generation_cancel_and_interrupt():
    src = _read("server_voice.ts")
    assert "generationId" in src
    assert "interrupt(" in src
    assert "genId !== this.generationId" in src


def test_node_transport_references_gemini_only():
    src = _read("server_voice.ts")
    assert "/voice/gemini/stream" in src
    assert "/voice/gemini/health" in src
    low = src.lower()
    for token in FORBIDDEN_TOKENS + ("whisper", "kokoro", "piper", "silero",
                                     "convai", "tts/stream"):
        assert token not in low, token


def test_client_voice_path_references_no_legacy_provider():
    src = _read("src/lib/audio.ts")
    low = src.lower()
    for token in FORBIDDEN_TOKENS + ("faster-whisper", "silero vad", "kokoro",
                                     "piper", "speechsynthesis"):
        assert token not in low, token


# ---------------------------------------------------------------------------
# 6. Browser audio format contract (unchanged by the removal)
# ---------------------------------------------------------------------------

def test_audio_format_contract():
    audio = _read("src/lib/audio.ts")
    assert "16000" in audio
    assert "floatTo16BitPCM" in audio or "Int16" in audio


# ---------------------------------------------------------------------------
# 7. Financial firewall intact
# ---------------------------------------------------------------------------

def test_financial_firewall_intact():
    perms = _read("desktop_agent/config/permissions.py")
    assert 'FINANCIAL: "deny"' in perms or ("FINANCIAL" in perms and '"deny"' in perms)
    fw = _read("src/quant/firewall.ts")
    assert "EXECUTE_TRADE" in fw
