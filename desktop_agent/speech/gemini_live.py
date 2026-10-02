"""MYRAA Gemini Live voice engine — the ONLY active voice provider.

Architecture (locked):

    Browser mic (PCM16 mono 16k, existing audio.ts)
      -> Node VoiceTransport (/live, transport only, no intelligence)
      -> Python GeminiLiveSessionManager (/voice/gemini/stream)
      -> Gemini Live API (VAD + STT + response + native audio + barge-in)
      -> MYRAA Tool Bus (allowlisted tools, authorization, finance firewall)
      -> Node -> browser playback (existing queue, epoch guards)

Ownership: VoiceSessionController (app) -> GeminiLiveSessionManager (one per
voice connection) -> GeminiLiveSession (one SDK session). No second brain, no
fallback providers, no local STT/VAD/TTS in the active path.

Security: GEMINI_API_KEY server-side only, never logged, never sent to the
renderer. Every tool call: schema validate -> PermissionManager ->
finance-firawall deny -> execute -> sanitize -> respond. Completed call IDs
are tracked so reconnects never execute twice.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


# ── Configuration (§5) ─────────────────────────────────────────────

DEFAULT_LIVE_MODEL = "gemini-3.1-flash-live-preview"
DEFAULT_LIVE_VOICE = "Aoede"


@dataclass(frozen=True)
class GeminiLiveConfig:
    enabled: bool = True
    api_key: str = ""
    model: str = DEFAULT_LIVE_MODEL
    voice: str = DEFAULT_LIVE_VOICE
    language: str = ""          # BCP-47 speech hint; "" = auto (Hinglish safe)
    temperature: float = 0.7
    max_reconnects: int = 3

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.api_key) and bool(self.model)

    def describe(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "model": self.model,
            "voice": self.voice,
            "language": self.language or "auto",
            "provider": "gemini_live",
        }


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def load_gemini_live_config() -> GeminiLiveConfig:
    return GeminiLiveConfig(
        enabled=_env_bool("GEMINI_LIVE_ENABLED", True),
        api_key=os.getenv("GEMINI_API_KEY", ""),
        model=os.getenv("GEMINI_LIVE_MODEL", DEFAULT_LIVE_MODEL),
        voice=os.getenv("GEMINI_LIVE_VOICE", DEFAULT_LIVE_VOICE),
        language=os.getenv("GEMINI_LIVE_LANGUAGE", ""),
        temperature=float(os.getenv("GEMINI_LIVE_TEMPERATURE", "0.7") or 0.7),
        max_reconnects=int(os.getenv("GEMINI_LIVE_MAX_RECONNECTS", "3") or 3),
    )


# ── Error classification (§27/28) ──────────────────────────────────

class GeminiErrorCode(str, Enum):
    OK = "OK"
    GEMINI_AUTH_ERROR = "GEMINI_AUTH_ERROR"
    GEMINI_QUOTA_ERROR = "GEMINI_QUOTA_ERROR"
    GEMINI_RATE_LIMIT = "GEMINI_RATE_LIMIT"
    GEMINI_NETWORK_ERROR = "GEMINI_NETWORK_ERROR"
    GEMINI_SESSION_ERROR = "GEMINI_SESSION_ERROR"
    GEMINI_MODEL_ERROR = "GEMINI_MODEL_ERROR"
    GEMINI_TOOL_ERROR = "GEMINI_TOOL_ERROR"
    GEMINI_AUDIO_ERROR = "GEMINI_AUDIO_ERROR"
    GEMINI_CONFIGURATION_ERROR = "GEMINI_CONFIGURATION_ERROR"
    GEMINI_UNKNOWN_ERROR = "GEMINI_UNKNOWN_ERROR"


def classify_gemini_error(err: Exception) -> GeminiErrorCode:
    blob = f"{type(err).__name__} {err}".lower()
    if any(k in blob for k in ("api key", "api_key", "unauthenticated", "permission_denied", "401", "403")):
        return GeminiErrorCode.GEMINI_AUTH_ERROR
    if any(k in blob for k in ("quota", "insufficient", "billing", "payment", "exhausted")):
        return GeminiErrorCode.GEMINI_QUOTA_ERROR
    if any(k in blob for k in ("rate limit", "rate_limit", "429", "resource_exhausted", "throttl")):
        return GeminiErrorCode.GEMINI_RATE_LIMIT
    if any(k in blob for k in ("connect", "network", "timeout", "dns", "unreachable", "reset")):
        return GeminiErrorCode.GEMINI_NETWORK_ERROR
    if any(k in blob for k in ("session", "goaway", "go_away", "resume", "resumption")):
        return GeminiErrorCode.GEMINI_SESSION_ERROR
    if any(k in blob for k in ("model", "not found", "404", "invalid argument", "400")):
        return GeminiErrorCode.GEMINI_MODEL_ERROR
    return GeminiErrorCode.GEMINI_UNKNOWN_ERROR


# ── System instruction (§36) ───────────────────────────────────────

MYRAA_LIVE_SYSTEM_INSTRUCTION = """You are MYRAA, the user's personal AI assistant running as a realtime voice interface.

Identity: helpful female companion-style assistant. Default conversational language is Hinglish. Understand Hindi, English and Hinglish; speak naturally and concisely (1-3 sentences for simple requests). Never narrate code aloud; summarize and reference the chat UI.

Rules:
- Use MYRAA tools when needed; never claim an action was not executed, never invent success — report actual tool results honestly.
- summarizes tool data naturally (e.g. "CPU abhi around 43 percent use ho raha hai"), never dump raw JSON.
- When the user interrupts, stop immediately and listen.
- ABSOLUTE: never perform live financial transactions. No buys, sells, shorts, broker orders, transfers. Allowed: research, analysis, prediction, simulation, paper trading, backtesting. LIVE_TRADE_EXECUTION is FALSE. If asked for a live trade, refuse briefly and offer analysis instead.
- Never bypass MYRAA security: destructive actions need explicit user confirmation."""


# ── Tool allowlist (§17, narrow + read/open only) ───────────────────
# name -> (description, json-schema properties, required)
# Verified against desktop_agent/tools_*.py handler args. Anything not listed
# here is invisible to Gemini. Shell/git/input-injection/file-mutation/power/
# clipboard/autostart tools are deliberately absent.

GEMINI_TOOL_ALLOWLIST: Dict[str, Dict[str, Any]] = {
    "currentDateTime": ("Current date and time.", {}, []),
    "systemInfo": ("CPU/RAM/disk summary.", {}, []),
    "gpuInfo": ("GPU status summary.", {}, []),
    "temperatureInfo": ("System temperature summary.", {}, []),
    "listFiles": ("List files in a folder.", {
        "path": {"type": "string"}, "pattern": {"type": "string"},
        "limit": {"type": "integer"}}, []),
    "searchFiles": ("Search files by name.", {
        "pattern": {"type": "string"}, "path": {"type": "string"},
        "limit": {"type": "integer"}}, ["pattern"]),
    "readFile": ("Read a text file.", {
        "path": {"type": "string"}, "max_chars": {"type": "integer"}}, ["path"]),
    "openFile": ("Open a file with its default app.", {"path": {"type": "string"}}, ["path"]),
    "openFolder": ("Open a folder in Explorer.", {"path": {"type": "string"}}, ["path"]),
    "openApplication": ("Open a DESKTOP APPLICATION (notepad, calculator, chrome, vs code). "
                        "Never use this for a website — use openWebsite for sites like YouTube.",
                        {"application": {"type": "string"}, "name": {"type": "string"}}, []),
    "openWebsite": ("Open a website in the user's Windows DEFAULT browser. Use this for "
                    "'open youtube', 'open google', 'open gmail', 'open github', "
                    "'open chatgpt' and for any http(s) URL. The site name may be given "
                    "as 'name'/'website' or as a full URL in 'url'.",
                    {"url": {"type": "string"}, "name": {"type": "string"},
                     "website": {"type": "string"}}, []),
    "searchWeb": ("Web search.", {"query": {"type": "string"}, "q": {"type": "string"}}, []),
    "searchGoogle": ("Google search.", {"query": {"type": "string"}, "q": {"type": "string"}}, []),
    "searchGitHub": ("GitHub search.", {"query": {"type": "string"}, "q": {"type": "string"}}, []),
    "searchYouTube": ("YouTube search.", {"query": {"type": "string"}, "q": {"type": "string"}}, []),
    "takeScreenshot": ("Capture the screen.", {}, []),
    "takeRegionScreenshot": ("Capture a screen region.", {
        "x": {"type": "integer"}, "y": {"type": "integer"},
        "width": {"type": "integer"}, "height": {"type": "integer"}}, []),
    "analyzeScreenshot": ("Capture and describe the screen.", {}, []),
    "readScreen": ("OCR the screen text.", {}, []),
    "desktopBrowserOpen": ("Open URL in the Windows default browser.", {
        "url": {"type": "string"}, "name": {"type": "string"},
        "website": {"type": "string"}}, []),
    "desktopBrowserNavigate": ("Navigate the Windows default browser.", {
        "url": {"type": "string"}, "name": {"type": "string"},
        "website": {"type": "string"}}, []),
    "desktopBrowserSearch": ("Search in MYRAA browser.", {
        "query": {"type": "string"}, "q": {"type": "string"}}, []),
}

# Hard finance/trade blocklist: even if a future tool matches, it is refused
# before authorization (§18/59). LIVE_TRADE_EXECUTION stays FALSE.
FINANCE_BLOCK_SUBSTRINGS = (
    "buy", "sell", "short", "order", "trade", "transfer", "withdraw",
    "deposit", "broker", "position", "portfolio_order", "execute_trade",
)


def _finance_blocked(name: str) -> bool:
    n = name.lower()
    return any(s in n for s in FINANCE_BLOCK_SUBSTRINGS)


def build_function_declarations() -> List[Dict[str, Any]]:
    decls = []
    for name, (desc, props, req) in GEMINI_TOOL_ALLOWLIST.items():
        if _finance_blocked(name):
            continue
        decls.append({
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props,
                           "required": req},
        })
    return decls


@dataclass
class ToolCallResult:
    call_id: str
    name: str
    ok: bool
    payload: Dict[str, Any]


class GeminiToolRouter:
    """Gemini -> MYRAA Tool Bus (§16/17/58).

    Pipeline per call: allowlist -> finance block -> schema validate ->
    PermissionManager -> execute raw handler -> sanitize -> respond.
    Completed call IDs are remembered so a reconnect/resend never executes
    twice (§26). Destructive/confirm-gated tools return a spoken confirmation
    request carrying a single-use token (existing 60s policy, unchanged).
    """

    # Bounded duplicate-call memory: Gemini may resend calls after reconnects,
    # but an unbounded dict would grow for the life of the process.
    _COMPLETED_MAX = 500

    def __init__(self):
        self._completed: Dict[str, ToolCallResult] = {}
        self._lock = __import__("threading").Lock()

    def already_done(self, call_id: str) -> Optional[ToolCallResult]:
        with self._lock:
            return self._completed.get(call_id)

    def execute(self, call_id: str, name: str, args: Dict[str, Any]) -> ToolCallResult:
        from desktop_agent.registry import (
            PermissionManager,
            TOOLS,
            TOOL_SCHEMAS,
            ValidationLayer,
        )

        with self._lock:
            if call_id in self._completed:
                log.info("[GeminiLive] duplicate tool call %s ignored", call_id)
                return self._completed[call_id]

        def _done(ok: bool, payload: Dict[str, Any]) -> ToolCallResult:
            res = ToolCallResult(call_id=call_id, name=name, ok=ok, payload=payload)
            with self._lock:
                if call_id not in self._completed and len(self._completed) >= self._COMPLETED_MAX:
                    # FIFO eviction (dicts preserve insertion order): drop oldest.
                    self._completed.pop(next(iter(self._completed)))
                self._completed[call_id] = res
            return res

        if name not in GEMINI_TOOL_ALLOWLIST or name not in TOOLS:
            return _done(False, {"error": f"Tool '{name}' is not available to voice."})
        if _finance_blocked(name):
            log.error("[GeminiLive] finance firewall blocked tool %s", name)
            return _done(False, {"error": "Live financial actions are forbidden. LIVE_TRADE_EXECUTION is FALSE."})

        try:
            valid = ValidationLayer.validate(dict(args or {}), TOOL_SCHEMAS.get(name), tool_name=name)
        except Exception as e:
            return _done(False, {"error": f"Invalid arguments for {name}: {e}"})

        try:
            decision = PermissionManager.check(name, valid)
        except Exception as e:
            return _done(False, {"error": f"Authorization failed: {e}"})
        if not decision.allowed:
            if decision.decision == "confirm":
                token = PermissionManager.mint_confirmation(name, valid)
                return _done(True, {
                    "requires_confirmation": True,
                    "confirmation_token": token,
                    "message": (f"Action '{name}' needs your explicit spoken confirmation. "
                                f"Ask the user aloud; if they confirm, call {name} again with the "
                                f"same arguments plus confirmation_token."),
                })
            return _done(False, {"error": f"Permission denied: {decision.reason}"})

        token = None
        if isinstance(valid, dict):
            token = valid.pop("confirmation_token", None)
        if token and not PermissionManager.validate_confirmation(name, valid, token):
            return _done(False, {"error": "Invalid or expired confirmation token."})
        try:
            handler = TOOLS[name]
            raw = getattr(handler, "__raw_handler__", handler)
            out = raw(valid)
            return _done(True, {"result": _sanitize(out)})
        except Exception as e:
            log.error("[GeminiLive] tool %s failed: %s", name, e)
            return _done(False, {"error": f"Tool {name} failed: {e}"})


def _sanitize(out: Any, _depth: int = 0) -> Any:
    """Strip secrets/oversize blobs from tool results before Gemini sees them."""
    if _depth > 4:
        return "[truncated]"
    if isinstance(out, dict):
        clean = {}
        for k, v in list(out.items())[:40]:
            if any(s in str(k).lower() for s in ("key", "token", "secret", "password", "auth")):
                clean[k] = "[redacted]"
            else:
                clean[k] = _sanitize(v, _depth + 1)
        return clean
    if isinstance(out, (list, tuple)):
        return [_sanitize(v, _depth + 1) for v in list(out)[:40]]
    if isinstance(out, bytes):
        return f"[binary {len(out)} bytes]"
    if out is None or isinstance(out, (bool, int, float)):
        return out
    if isinstance(out, str):
        return out if len(out) <= 4000 else out[:4000]
    s = str(out)
    return s[:4000]


# ── Metrics (§61) ──────────────────────────────────────────────────

@dataclass
class GeminiVoiceMetrics:
    sessions: int = 0
    connection_success: int = 0
    connection_failure: int = 0
    reconnects: int = 0
    interruptions: int = 0
    turns: int = 0
    tool_calls: int = 0
    duplicate_tool_calls: int = 0
    input_audio_bytes: int = 0
    output_audio_bytes: int = 0
    input_audio_chunks: int = 0        # mic chunks actually written to Gemini
    server_messages: int = 0           # messages received from Gemini Live
    dropped_audio_chunks: int = 0      # stale/not-ready audio discarded, never sent
    dead_writes_prevented: int = 0     # sends refused because state != READY
    reconnect_exhausted: int = 0       # reconnect budgets fully consumed
    event_loop_lag_events: int = 0     # keepalive-risk loop stalls (see _diag_loop)
    event_loop_max_lag_ms: int = 0     # worst observed loop lag this process
    last_error: Optional[str] = None   # most recent structured failure reason
    errors: Dict[str, int] = field(default_factory=dict)

    def error(self, code: GeminiErrorCode) -> None:
        self.errors[code.value] = self.errors.get(code.value, 0) + 1


class ConnState(str, Enum):
    """Explicit Gemini session lifecycle. Audio flows ONLY in READY."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    READY = "ready"
    DRAINING = "draining"      # GoAway received; finishing in-flight, will reconnect
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


# Bounded mic queue: ~8s at 128ms chunks. Overflow drops OLDEST (never replay).
AUDIO_QUEUE_MAX = 64


# ── Live session (§6-9) ────────────────────────────────────────────

@dataclass
class GeminiVoiceEvent:
    kind: str   # connected|session_started|partial|final|audio|turn_complete|
                # interrupted|tool_result|go_away|resumption|error
    data: Dict[str, Any] = field(default_factory=dict)


class GeminiLiveSession:
    """ONE authoritative Gemini Live session. Transport/model-level owner."""

    CONNECT_TIMEOUT_S = 20.0

    def __init__(self, config: GeminiLiveConfig, tools: GeminiToolRouter,
                 metrics: GeminiVoiceMetrics,
                 on_event: Optional[Callable[[GeminiVoiceEvent], Any]] = None):
        self.config = config
        self.tools = tools
        self.metrics = metrics
        self.on_event = on_event
        self.session_id = f"V{uuid.uuid4().hex[:8].upper()}"
        self.turn_seq = 0
        self.generation_seq = 0
        self._session = None
        self._client = None
        # The SDK connection context MUST be retained for the session lifetime:
        # dropping it lets CPython GC close the underlying websocket instantly.
        self._connect_cm = None
        self._resumption_handle: Optional[str] = None
        self._closed = False
        self._current_turn_id = ""
        # -- connection lifecycle (single-failure convergence) --
        self._state: ConnState = ConnState.DISCONNECTED
        self._state_lock = asyncio.Lock()
        self._conn_gen = 0              # bumped on every failure; stale work dies with it
        self._failed_gens: set[int] = set()
        self._audio_queue: asyncio.Queue = asyncio.Queue(maxsize=AUDIO_QUEUE_MAX)
        self._sender_task: Optional[asyncio.Task] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._tool_tasks: set[asyncio.Task] = set()
        self._reconnect_attempts = 0
        # -- latency telemetry (monotonic; per current connection) --
        self._t_connect_start = 0.0
        self._t_connected = 0.0
        self._t_ready = 0.0
        self._t_first_input_ts = 0.0
        self._t_first_audio_ts = 0.0
        # -- per-turn timing (reset on turn_complete; §17 TTFA breakdown) --
        self._t_turn_first_input = 0.0     # first input transcript this turn
        self._t_turn_first_audio = 0.0     # first output audio this turn
        # -- activity tracking (health ages; monotonic) --
        self._last_server_event_ts = 0.0   # last message received from Gemini
        self._last_input_queued_ts = 0.0   # last mic chunk accepted into queue
        self._last_input_send_ts = 0.0     # last mic chunk actually sent to Gemini
        self._last_output_audio_ts = 0.0   # last output audio from Gemini
        # -- event-loop starvation probe (keepalive 1011 evidence, §5/6) --
        self._diag_task: Optional[asyncio.Task] = None

    # -- lifecycle ---------------------------------------------------

    def _build_config(self, resume_handle: Optional[str] = None):
        from google.genai import types

        speech_cfg = {"voice_config": {"prebuilt_voice_config": {"voice_name": self.config.voice}}}
        if self.config.language:
            speech_cfg["language_code"] = self.config.language
        # Optional blocks are sent ONLY when valid: empty session_resumption
        # ({}) and token-less sliding_window get the session cleanly closed
        # by the server. Resumption handle flows on reconnect (§23).
        session_resumption = {"handle": resume_handle} if resume_handle else None
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            temperature=self.config.temperature,
            speech_config=speech_cfg,
            system_instruction=self._system_instruction(),
            tools=[{"function_declarations": build_function_declarations()}],
            input_audio_transcription={},
            output_audio_transcription={},
            session_resumption=session_resumption,
            context_window_compression={"sliding_window": {"target_tokens": 16384}},
        )

    def _system_instruction(self) -> str:
        return MYRAA_LIVE_SYSTEM_INSTRUCTION

    @property
    def state(self) -> ConnState:
        return self._state

    @property
    def connection_generation(self) -> int:
        return self._conn_gen

    async def _set_state(self, new: ConnState) -> None:
        async with self._state_lock:
            old = self._state
            self._state = new
        if old != new:
            log.info("[GeminiLive] state %s -> %s session=%s gen=%d",
                     old.value, new.value, self.session_id, self._conn_gen)

    def _is_ready(self) -> bool:
        return self._state == ConnState.READY and not self._closed

    async def connect(self, resume_handle: Optional[str] = None) -> None:
        from google import genai

        if not self.config.configured:
            raise ValueError("GEMINI_API_KEY is not configured.")
        await self._set_state(ConnState.CONNECTING)
        self._t_connect_start = time.monotonic()
        self._client = genai.Client(api_key=self.config.api_key)
        handle = resume_handle if resume_handle is not None else self._resumption_handle
        cfg = self._build_config(handle)
        log.info("[GeminiLive] connecting model=%s", self.config.model)
        try:
            self._connect_cm = self._client.aio.live.connect(model=self.config.model, config=cfg)
            self._session = await asyncio.wait_for(
                self._connect_cm.__aenter__(), timeout=self.CONNECT_TIMEOUT_S)
        except Exception as e:
            code = classify_gemini_error(e)
            self.metrics.error(code)
            self.metrics.connection_failure += 1
            await self._set_state(ConnState.FAILED)
            log.error("[GeminiLive] connect failed: %s", code.value)
            raise
        self._t_connected = time.monotonic()
        await self._set_state(ConnState.CONNECTED)
        self.metrics.connection_success += 1
        log.info("[GeminiLive] connected model=%s session=%s", self.config.model, self.session_id)
        self._emit("connected", {"session_id": self.session_id, "model": self.config.model})
        self._start_sender()
        self._start_receiver()
        self._start_diag()
        await self._set_state(ConnState.READY)
        self._t_ready = time.monotonic()
        self._t_first_input_ts = 0.0
        self._t_first_audio_ts = 0.0
        self._emit("session_started", {"session_id": self.session_id, "model": self.config.model})

    def _start_receiver(self) -> None:
        if self._recv_task is not None and not self._recv_task.done():
            return  # exactly one receiver per session lifetime segment
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._recv_task = loop.create_task(self.receive_loop())

    async def close(self) -> None:
        await self._set_state(ConnState.CLOSING)
        self._closed = True
        self._conn_gen += 1  # invalidate all in-flight work
        await self._cancel_background_tasks()
        try:
            if self._connect_cm is not None:
                try:
                    await self._connect_cm.__aexit__(None, None, None)
                except Exception:
                    pass
                self._connect_cm = None
            elif self._session is not None:
                close = getattr(self._session, "close", None)
                if close is not None:
                    res = close()
                    if asyncio.isfuture(res) or asyncio.iscoroutine(res):
                        await res
        except Exception:
            pass
        finally:
            self._session = None
        # Drop anything buffered: a new session starts with clean audio state.
        self._drain_audio_queue("close")
        await self._set_state(ConnState.CLOSED)
        log.info("[GeminiLive] session closed session=%s", self.session_id)
        self._emit("closed", {"session_id": self.session_id})

    async def _cancel_background_tasks(self) -> None:
        current = asyncio.current_task()
        for task in list(self._tool_tasks):
            if task is not current:
                task.cancel()
        self._tool_tasks.clear()
        if self._sender_task is not None and self._sender_task is not current:
            self._sender_task.cancel()
            try:
                await self._sender_task
            except (asyncio.CancelledError, Exception):
                pass
            self._sender_task = None
        if self._recv_task is not None and self._recv_task is not current:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass
            self._recv_task = None
        if self._diag_task is not None and self._diag_task is not current:
            self._diag_task.cancel()
            self._diag_task = None
        # The reconnect task is owned separately; never cancel it from here
        # (failure handling must be able to schedule recovery).

    # -- input: bounded queue + generation-gated sender ------------------

    def submit_audio(self, pcm16_mono_16k: bytes) -> bool:
        """Enqueue one mic chunk. Non-blocking; drops when not READY or full.

        Returns True if queued. Dropped chunks are counted, never retried,
        never replayed after reconnect (fresh audio only).
        """
        if not self._is_ready():
            self.metrics.dead_writes_prevented += 1
            return False
        try:
            self._last_input_queued_ts = time.monotonic()
            self._audio_queue.put_nowait((self._conn_gen, bytes(pcm16_mono_16k)))
            return True
        except asyncio.QueueFull:
            try:
                self._audio_queue.get_nowait()  # drop OLDEST
            except asyncio.QueueEmpty:
                pass
            self.metrics.dropped_audio_chunks += 1
            try:
                self._audio_queue.put_nowait((self._conn_gen, bytes(pcm16_mono_16k)))
                return True
            except asyncio.QueueFull:
                self.metrics.dropped_audio_chunks += 1
                return False

    def _drain_audio_queue(self, reason: str) -> int:
        n = 0
        while True:
            try:
                self._audio_queue.get_nowait()
                n += 1
            except asyncio.QueueEmpty:
                break
        if n:
            self.metrics.dropped_audio_chunks += n
            log.info("[GeminiLive] dropped %d stale audio chunks (%s)", n, reason)
        return n

    def _start_sender(self) -> None:
        if self._sender_task is not None and not self._sender_task.done():
            return  # exactly one sender per session lifetime segment
        self._sender_task = asyncio.get_running_loop().create_task(self._audio_sender())

    # -- event-loop starvation probe (§5/§6: keepalive 1011 evidence) ------

    LOOP_LAG_WARN_MS = 2000.0

    def _start_diag(self) -> None:
        """ONE loop-lag probe per session (survives reconnects, read-only)."""
        if self._diag_task is not None and not self._diag_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._diag_task = loop.create_task(self._diag_loop())

    async def _diag_loop(self) -> None:
        """Detect asyncio starvation: sleep(1s) that takes much longer means
        the loop (or the GIL) was blocked — the exact condition that makes the
        websockets keepalive miss its pong deadline (1011 ping timeout)."""
        loop = asyncio.get_running_loop()
        while not self._closed:
            t0 = loop.time()
            await asyncio.sleep(1.0)
            lag_ms = (loop.time() - t0 - 1.0) * 1000.0
            if lag_ms > self.LOOP_LAG_WARN_MS:
                self.metrics.event_loop_lag_events += 1
                if round(lag_ms) > self.metrics.event_loop_max_lag_ms:
                    self.metrics.event_loop_max_lag_ms = round(lag_ms)
                log.warning(
                    "[GeminiLive] EVENT_LOOP_LAG lag_ms=%.0f session=%s "
                    "(keepalive risk — loop/GIL blocked)",
                    lag_ms, self.session_id)

    # -- health snapshot (§18; read-only) -----------------------------------

    def health(self) -> Dict[str, Any]:
        now = time.monotonic()

        def age(ts: float) -> Optional[int]:
            return round((now - ts) * 1000) if ts > 0.0 else None

        m = self.metrics
        return {
            "provider": "gemini_live",
            "state": self._state.value,
            "connection_generation": self._conn_gen,
            "session_id": self.session_id,
            "resumption_handle": bool(self._resumption_handle),
            "turns_completed": self.turn_seq,
            "reconnect_attempts": self._reconnect_attempts,
            "audio_queue_depth": self._audio_queue.qsize(),
            "audio_queue_max": AUDIO_QUEUE_MAX,
            "last_input_audio_ms_ago": age(self._last_input_queued_ts),
            "last_input_send_ms_ago": age(self._last_input_send_ts),
            "last_gemini_event_ms_ago": age(self._last_server_event_ts),
            "last_output_audio_ms_ago": age(self._last_output_audio_ts),
            "turn_first_input_to_first_audio_ms": (
                round((self._t_turn_first_audio - self._t_turn_first_input) * 1000)
                if self._t_turn_first_input and self._t_turn_first_audio else None),
            "metrics": {
                "connection_success": m.connection_success,
                "connection_failure": m.connection_failure,
                "reconnects": m.reconnects,
                "reconnect_exhausted": m.reconnect_exhausted,
                "interruptions": m.interruptions,
                "turns": m.turns,
                "input_audio_chunks": m.input_audio_chunks,
                "input_audio_bytes": m.input_audio_bytes,
                "output_audio_bytes": m.output_audio_bytes,
                "dropped_audio_chunks": m.dropped_audio_chunks,
                "dead_writes_prevented": m.dead_writes_prevented,
                "server_messages": m.server_messages,
                "event_loop_lag_events": m.event_loop_lag_events,
                "event_loop_max_lag_ms": m.event_loop_max_lag_ms,
                "last_error": m.last_error,
            },
        }

    async def _audio_sender(self) -> None:
        """Single sender task: queue -> READY-gated, generation-checked writes."""
        from google.genai import types

        while not self._closed:
            try:
                gen, pcm = await self._audio_queue.get()
            except asyncio.CancelledError:
                break
            if gen != self._conn_gen or not self._is_ready() or self._session is None:
                self.metrics.dropped_audio_chunks += 1
                continue
            try:
                await self._session.send_realtime_input(
                    audio=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000"))
                self.metrics.input_audio_bytes += len(pcm)
                self.metrics.input_audio_chunks += 1
                self._last_input_send_ts = time.monotonic()
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self._fail_once(f"audio-send: {type(e).__name__}: {e}")
                self.metrics.dropped_audio_chunks += 1

    async def send_audio(self, pcm16_mono_16k: bytes) -> bool:
        """Direct single write with full guards (storm-proof).

        Returns True if actually written. Refuses when state != READY or the
        socket is gone — callers must NEVER loop on False, just drop the chunk.
        """
        if not self._is_ready() or self._session is None:
            self.metrics.dead_writes_prevented += 1
            return False
        gen = self._conn_gen
        from google.genai import types

        try:
            await self._session.send_realtime_input(
                audio=types.Blob(data=pcm16_mono_16k, mime_type="audio/pcm;rate=16000"))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await self._fail_once(f"audio-send: {type(e).__name__}: {e}")
            return False
        if gen != self._conn_gen:
            return False  # connection recycled mid-write; treat as dropped
        self.metrics.input_audio_bytes += len(pcm16_mono_16k)
        return True

    async def speak_text(self, text: str) -> str:
        """Voice-render canonical MYRAA text through the live session.

        Explicitly intended generation-as-rendering (§15): the typed response
        stays authoritative; Gemini vocalizes it verbatim. Returns generation id.
        """
        if not self._is_ready() or self._session is None:
            raise RuntimeError("Gemini Live session is not connected.")
        from google.genai import types

        self.generation_seq += 1
        gen_id = f"G{self.generation_seq}"
        try:
            await self._session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(
                    text=f"Read aloud exactly, without changes or commentary: {text}")]),
                turn_complete=True)
        except Exception as e:
            await self._fail_once(f"speak-text: {type(e).__name__}: {e}")
            raise RuntimeError(f"Gemini Live session failed during speak-text: {e}")
        log.info("[GeminiLive] speak-text generation=%s chars=%d", gen_id, len(text))
        return gen_id

    async def send_tool_response(self, call_id: str, name: str, result: Dict[str, Any]) -> None:
        from google.genai import types

        if not self._is_ready() or self._session is None:
            self.metrics.dead_writes_prevented += 1
            return
        try:
            await self._session.send_tool_response(function_responses=[
                types.FunctionResponse(id=call_id, name=name, response=result)])
        except Exception as e:
            await self._fail_once(f"tool-response: {type(e).__name__}: {e}")

    # -- single-failure convergence + reconnect --------------------------

    async def _fail_once(self, reason: str) -> None:
        """ONE structured failure event per connection generation.

        Converges every close path (send error, receive error, ping timeout,
        1011, GoAway-drain completion): mark FAILED, bump generation (stale
        work dies), stop sender, drop stale audio, close socket quietly,
        schedule exactly one reconnect. Never raises, never storms.
        """
        async with self._state_lock:
            if self._state in (ConnState.CLOSING, ConnState.CLOSED) or self._closed:
                return
            if self._conn_gen in self._failed_gens:
                return  # this generation already handled
            if (self._reconnect_task is not None and not self._reconnect_task.done()
                    and self._state in (ConnState.FAILED, ConnState.RECONNECTING,
                                        ConnState.DRAINING)):
                # Recovery already in flight for this outage episode: a second
                # reporter (sender + receiver noticing the same dead socket).
                # Suppress — no new generation, no new log line, no new task.
                log.debug("[GeminiLive] duplicate failure report suppressed gen=%d",
                          self._conn_gen)
                return
            failed_gen = self._conn_gen
            self._failed_gens.add(failed_gen)
            self._conn_gen += 1
            self._state = ConnState.FAILED
        self.metrics.connection_failure += 1
        self.metrics.last_error = reason[:200]
        log.error("[GeminiLive] CONNECTION_FAILED reason=%s generation=%d session=%s",
                  reason[:160], failed_gen, self.session_id)
        self._emit("connection_failed", {"reason": reason[:160], "generation": failed_gen})
        # Stop the sender and the dead receiver now; fresh ones start on READY.
        # Never await our own cancellation when failing from inside those tasks.
        current = asyncio.current_task()
        if self._sender_task is not None and self._sender_task is not current:
            self._sender_task.cancel()
            self._sender_task = None
        elif self._sender_task is current:
            self._sender_task = None
        if self._recv_task is not None and self._recv_task is not current:
            self._recv_task.cancel()
            self._recv_task = None
        elif self._recv_task is current:
            self._recv_task = None
        self._drain_audio_queue("connection-failed")
        try:
            if self._connect_cm is not None:
                try:
                    await self._connect_cm.__aexit__(None, None, None)
                except Exception:
                    pass
                self._connect_cm = None
        except Exception:
            pass
        finally:
            self._session = None
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._closed:
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return  # exactly one reconnect task per failure
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._reconnect_task = loop.create_task(self._reconnect_loop())

    async def request_reconnect(self) -> None:
        """External trigger (e.g. GoAway handling, manager): one reconnect."""
        await self._fail_once("reconnect-requested")

    async def _reconnect_loop(self) -> None:
        if self._closed:
            return
        await self._set_state(ConnState.RECONNECTING)
        while not self._closed and self._reconnect_attempts < self.config.max_reconnects:
            self._reconnect_attempts += 1
            self.metrics.reconnects += 1
            delay = min(2 ** self._reconnect_attempts, 16)
            log.info("[GeminiLive] RECONNECTING attempt=%d gen=%d",
                     self._reconnect_attempts, self._conn_gen)
            self._emit("reconnecting", {"attempt": self._reconnect_attempts})
            await asyncio.sleep(delay)
            if self._closed:
                return
            try:
                await self.connect(resume_handle=self._resumption_handle)
                self._reconnect_attempts = 0
                self._failed_gens.clear()
                log.info("[GeminiLive] RECONNECTED generation=%d session=%s",
                         self._conn_gen, self.session_id)
                self._emit("reconnected", {"generation": self._conn_gen})
                return
            except asyncio.CancelledError:
                return
            except Exception as e:
                log.warning("[GeminiLive] reconnect attempt failed: %s", str(e)[:160])
        if not self._closed:
            self.metrics.reconnect_exhausted += 1
            log.error("[GeminiLive] reconnect budget exhausted attempts=%d",
                      self.config.max_reconnects)
            self._emit("error", {"code": "GEMINI_SESSION_ERROR",
                                 "message": "Gemini Live unavailable after retries.",
                                 "retryable": False})
            await self._set_state(ConnState.FAILED)

    # -- receive loop ----------------------------------------------------

    async def receive_loop(self) -> None:
        """Pump server messages until close. Emits normalized voice events.

        Runs as exactly one task (see _start_receiver). Any transport failure
        converges into _fail_once — which also triggers the single reconnect.
        Message handling itself never blocks this loop: tool calls run as
        background tasks so pongs/keepalive stay responsive.
        """
        try:
            session = self._session
            if session is None:
                return
            async for msg in session.receive():
                if self._closed:
                    break
                self.metrics.server_messages += 1
                self._last_server_event_ts = time.monotonic()
                await self._handle_message(msg)
            # A cleanly-ending stream is still a dead session: without this,
            # the sender idles, state stays READY, and no reconnect ever
            # fires — the "one response then silence" shape. Converge it into
            # the single failure path (reconnect with resumption handle).
            if not self._closed:
                await self._fail_once("receive-ended")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if not self._closed:
                await self._fail_once(
                    f"receive: {classify_gemini_error(e).value}: {type(e).__name__}: {e}")

    async def _handle_message(self, msg) -> None:
        if getattr(msg, "go_away", None) is not None:
            secs = getattr(msg.go_away, "time_left", "")
            log.info("[GeminiLive] GoAway received time_left=%s: draining then reconnect", secs)
            self._emit("go_away", {"time_left": str(secs)})
            # Server-directed migration: stop new work, reconnect with handle.
            await self._set_state(ConnState.DRAINING)
            await self._fail_once("goaway-drain")
            return
        upd = getattr(msg, "session_resumption_update", None)
        if upd is not None:
            if getattr(upd, "new_handle", None):
                self._resumption_handle = upd.new_handle
                log.info("[GeminiLive] session resumption handle updated")
                self._emit("resumption", {"resumable": bool(getattr(upd, "resumable", False))})
            return
        tc = getattr(msg, "tool_call", None)
        if tc is not None and getattr(tc, "function_calls", None):
            # Off the receive loop: tool execution + tool-response round-trip
            # must never stall pongs/keepalive (see keepalive audit).
            for fc in tc.function_calls:
                if len(self._tool_tasks) >= 8:
                    # Never hang Gemini: answer the dropped call with an error
                    # FunctionResponse so the turn completes instead of stalling.
                    log.warning("[GeminiLive] tool backlog full, rejecting call")
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        continue
                    call_id = getattr(fc, "id", None) or f"call-{uuid.uuid4().hex[:8]}"
                    name = getattr(fc, "name", "")
                    self._emit("tool_result", {"id": call_id, "name": name, "ok": False})
                    task = loop.create_task(
                        self.send_tool_response(
                            call_id, name,
                            {"error": "Tool backlog full; please retry the call."}))
                    self._tool_tasks.add(task)
                    task.add_done_callback(self._tool_tasks.discard)
                    continue
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    continue
                task = loop.create_task(self._handle_tool_call(fc))
                self._tool_tasks.add(task)
                task.add_done_callback(self._tool_tasks.discard)
            return
        tcc = getattr(msg, "tool_call_cancellation", None)
        if tcc is not None:
            log.info("[GeminiLive] tool cancellation ids=%s",
                     getattr(tcc, "ids", getattr(tcc, "id", "?")))
            return
        content = getattr(msg, "server_content", None)
        if content is None:
            return
        if getattr(content, "interrupted", False):
            self.metrics.interruptions += 1
            self.generation_seq += 1
            log.info("[GeminiLive] generation interrupted epoch=G%d", self.generation_seq)
            self._emit("interrupted", {"generation": f"G{self.generation_seq}"})
        it = getattr(content, "input_transcription", None)
        if it is not None and getattr(it, "text", ""):
            if not self._t_first_input_ts:
                self._t_first_input_ts = time.monotonic()
            if not self._t_turn_first_input:
                self._t_turn_first_input = time.monotonic()
            self._emit("partial", {"role": "user", "text": it.text})
        ot = getattr(content, "output_transcription", None)
        if ot is not None and getattr(ot, "text", ""):
            self._emit("partial", {"role": "model", "text": ot.text})
        turn = getattr(content, "model_turn", None)
        parts = getattr(turn, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                data = bytes(inline.data)
                self.metrics.output_audio_bytes += len(data)
                if not self._t_first_audio_ts:
                    self._t_first_audio_ts = time.monotonic()
                if not self._t_turn_first_audio:
                    self._t_turn_first_audio = time.monotonic()
                self._last_output_audio_ts = time.monotonic()
                self._emit("audio", {"audio": data,
                                     "generation": f"G{self.generation_seq}"})
            text = getattr(part, "text", None)
            if text:
                self._emit("partial", {"role": "model", "text": text})
        if getattr(content, "turn_complete", False):
            self.turn_seq += 1
            self.metrics.turns += 1
            turn_id = f"{self.session_id}/T{self.turn_seq}"
            listen = (f"connect={(self._t_connected - self._t_connect_start) * 1000:.0f}ms "
                      if self._t_connected and self._t_connect_start else "connect=n/a ")
            # §17 per-turn breakdown — capture→gemini lives Node-side; this is
            # gemini_turn_detection (first transcript) → first_audio → complete.
            in_to_out = (f" input->audio="
                         f"{(self._t_turn_first_audio - self._t_turn_first_input) * 1000:.0f}ms"
                         if self._t_turn_first_input and self._t_turn_first_audio else "")
            log.info("[GeminiLive] TURN_COMPLETE turn=%s %s%s",
                     turn_id, listen, in_to_out)
            # Per-turn timers reset so the next turn's metrics start clean.
            self._t_turn_first_input = 0.0
            self._t_turn_first_audio = 0.0
            self._emit("turn_complete", {"turn_id": turn_id})

    async def _handle_tool_call(self, fc) -> None:
        call_id = getattr(fc, "id", None) or f"call-{uuid.uuid4().hex[:8]}"
        name = getattr(fc, "name", "")
        args = dict(getattr(fc, "args", None) or {})
        log.info("[GeminiLive] tool call name=%s id=%s", name, call_id)
        self.metrics.tool_calls += 1
        if self.tools.already_done(call_id) is not None:
            self.metrics.duplicate_tool_calls += 1
            prev = self.tools.already_done(call_id)
            assert prev is not None
            await self.send_tool_response(call_id, name, prev.payload)
            return
        result = await asyncio.to_thread(self.tools.execute, call_id, name, args)
        log.info("[GeminiLive] tool result name=%s ok=%s", name, result.ok)
        self._emit("tool_result", {"id": call_id, "name": name, "ok": result.ok})
        # Spoken confirmations flow back as results; Gemini asks the user aloud.
        await self.send_tool_response(call_id, name, result.payload)

    def _emit(self, kind: str, data: Dict[str, Any]) -> None:
        try:
            data.setdefault("session_id", self.session_id)
            if self.on_event is not None:
                res = self.on_event(GeminiVoiceEvent(kind=kind, data=data))
                if asyncio.iscoroutine(res):
                    asyncio.get_running_loop().create_task(res)
        except Exception as e:
            log.debug("[GeminiLive] event callback failed: %s", e)

    @property
    def resumption_handle(self) -> Optional[str]:
        return self._resumption_handle


# ── Session manager: ONE owner per voice connection (§6) ─────────────

class GeminiLiveSessionManager:
    """Owns exactly one GeminiLiveSession.

    The session owns its own receive task, audio sender, and bounded
    auto-reconnect (single task, resumption handle). The manager only creates
    and drops sessions — it never duplicates pumps, senders, or reconnects.
    """

    def __init__(self, config: GeminiLiveConfig, tools: Optional[GeminiToolRouter] = None,
                 metrics: Optional[GeminiVoiceMetrics] = None,
                 on_event: Optional[Callable[[GeminiVoiceEvent], Any]] = None):
        self.config = config
        self.tools = tools or GeminiToolRouter()
        self.metrics = metrics or GeminiVoiceMetrics()
        self.on_event = on_event
        self.session: Optional[GeminiLiveSession] = None
        self._closed = False
        self._attempts = 0

    async def start(self) -> GeminiLiveSession:
        if self.session is not None:
            return self.session
        if not self.config.configured:
            raise ValueError("GEMINI_API_KEY is not configured.")
        self.metrics.sessions += 1
        sess = GeminiLiveSession(self.config, self.tools, self.metrics, self.on_event)
        await sess.connect()
        self.session = sess
        log.info("[GeminiLive] session created session=%s", sess.session_id)
        return sess

    async def reconnect(self) -> Optional[GeminiLiveSession]:
        """Explicit fresh session (bridge-level recovery).

        In-session failures already auto-reconnect inside the session with the
        resumption handle; this path replaces the session object itself and is
        used only when the session reports itself unrecoverable.
        """
        if self._closed:
            return None
        if self._attempts >= self.config.max_reconnects:
            log.error("[GeminiLive] reconnect budget exhausted")
            return None
        self._attempts += 1
        self.metrics.reconnects += 1
        delay = min(2 ** self._attempts, 16)
        log.info("[GeminiLive] reconnecting attempt=%d in %ss", self._attempts, delay)
        # Capture the resumption handle BEFORE dropping the session — after
        # close() the handle is gone and the new session would resume nothing.
        handle = self.session.resumption_handle if self.session else None
        await self._drop_session()
        self.session = None
        await asyncio.sleep(delay)
        try:
            sess = GeminiLiveSession(self.config, self.tools, self.metrics, self.on_event)
            await sess.connect(resume_handle=handle)
            self.session = sess
            self._attempts = 0
            return sess
        except Exception as e:
            log.error("[GeminiLive] reconnect failed: %s", e)
            return None

    async def _drop_session(self) -> None:
        if self.session is not None:
            try:
                await self.session.close()
            except Exception:
                pass

    def health(self) -> Dict[str, Any]:
        """Manager-level health: session snapshot + lifecycle counters."""
        m = self.metrics
        base: Dict[str, Any] = {
            "provider": "gemini_live",
            "model": self.config.model,
            "voice": self.config.voice,
            "configured": self.config.configured,
            "manager_closed": self._closed,
            "reconnect_attempts": self._attempts,
            "metrics": {
                "sessions": m.sessions,
                "connection_success": m.connection_success,
                "connection_failure": m.connection_failure,
                "reconnects": m.reconnects,
                "reconnect_exhausted": m.reconnect_exhausted,
                "interruptions": m.interruptions,
                "turns": m.turns,
                "input_audio_chunks": m.input_audio_chunks,
                "input_audio_bytes": m.input_audio_bytes,
                "output_audio_bytes": m.output_audio_bytes,
                "dropped_audio_chunks": m.dropped_audio_chunks,
                "dead_writes_prevented": m.dead_writes_prevented,
                "server_messages": m.server_messages,
                "event_loop_lag_events": m.event_loop_lag_events,
                "event_loop_max_lag_ms": m.event_loop_max_lag_ms,
                "last_error": m.last_error,
            },
        }
        if self.session is not None:
            try:
                base["session"] = self.session.health()
            except Exception:
                base["session"] = None
        return base

    async def stop(self) -> None:
        self._closed = True
        await self._drop_session()
        self.session = None
