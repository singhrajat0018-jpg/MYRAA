"""
MYRAA Speech - Continuous Voice Loop (Phase C).

Manages the full voice conversation lifecycle:
  LISTEN → STT → unified request → brain → execute → TTS → LISTEN

This is NOT a second voice pipeline. It is the stateful turn manager
that the Node voice bridge calls into. Node owns the audio;
this module owns the conversation state machine.

Key guarantees:
- No duplicate turns (dedup by transcript hash + timestamp window).
- No zombie tasks (session timeout + in-flight cancellation).
- Barge-in support (INTERRUPTED cancels pending execution).
- Reconnect support (DISCONNECTED → IDLE recovery).
- Thread-safe.
"""

from __future__ import annotations

import enum
import hashlib
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .voice_interface import VoiceInterface, VoiceState


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Max seconds of silence before auto-idling.
SILENCE_TIMEOUT_S: float = 30.0

# Max seconds for a single turn (brain + execution + TTS) before forced idle.
TURN_TIMEOUT_S: float = 120.0

# Dedup window: same transcript within this many seconds is dropped.
DEDUP_WINDOW_S: float = 3.0

# Max consecutive errors before forced disconnect.
MAX_CONSECUTIVE_ERRORS: int = 5

# Session timeout: auto-disconnect after this many seconds of no interaction.
SESSION_TIMEOUT_S: float = 600.0  # 10 minutes


# ---------------------------------------------------------------------------
# Turn tracking
# ---------------------------------------------------------------------------

class TurnStatus(enum.Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class Turn:
    """One conversation turn — from user transcript to TTS completion."""

    __slots__ = (
        "turn_id", "transcript", "status", "created_at",
        "started_at", "completed_at", "result", "error",
    )

    def __init__(self, turn_id: str, transcript: str) -> None:
        self.turn_id = turn_id
        self.transcript = transcript
        self.status: TurnStatus = TurnStatus.PENDING
        self.created_at: float = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "transcript": self.transcript,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# ContinuousVoiceLoop
# ---------------------------------------------------------------------------

class ContinuousVoiceLoop:
    """
    Manages the continuous voice conversation lifecycle.

    The Node voice bridge calls into this class on state transitions:

        loop.on_user_transcript("open notepad")
        → loop returns a Turn with execution result
        → loop.on_turn_complete(turn_id)
        → loop enters LISTENING again

    Barge-in:
        loop.on_interruption()
        → cancels any in-flight turn
        → returns to LISTENING

    Reconnect:
        loop.on_disconnect()
        → loop.on_reconnect()
        → resets error counter, resumes
    """

    def __init__(
        self,
        voice_interface: Optional[VoiceInterface] = None,
        *,
        silence_timeout: float = SILENCE_TIMEOUT_S,
        turn_timeout: float = TURN_TIMEOUT_S,
        session_timeout: float = SESSION_TIMEOUT_S,
    ) -> None:
        self._vi = voice_interface or VoiceInterface()
        self._lock = threading.Lock()
        self._silence_timeout = silence_timeout
        self._turn_timeout = turn_timeout
        self._session_timeout = session_timeout

        # Turn tracking
        self._current_turn: Optional[Turn] = None
        self._turn_history: List[Turn] = []
        self._turn_counter: int = 0

        # Dedup
        self._recent_hashes: Dict[str, float] = {}

        # Counters
        self._total_turns: int = 0
        self._total_interruptions: int = 0
        self._consecutive_errors: int = 0
        self._last_interaction: float = time.time()
        self._session_started: float = time.time()

        # Callbacks
        self._on_execute: Optional[Callable[[str], Dict[str, Any]]] = None
        self._on_tts: Optional[Callable[[str], None]] = None
        self._on_state_change: Optional[Callable[[str, str], None]] = None

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def set_execute_callback(self, fn: Callable[[str], Dict[str, Any]]) -> None:
        """Register the function called to execute a user transcript.

        fn(transcript) → result dict with at least ``{"ok": True/False}``.
        """
        self._on_execute = fn

    def set_tts_callback(self, fn: Callable[[str], None]) -> None:
        """Register the function called to speak a response.

        fn(text) — triggers TTS on the Node side.
        """
        self._on_tts = fn

    def set_state_change_callback(
        self, fn: Callable[[str, str], None]
    ) -> None:
        """Register a callback for voice state transitions."""
        self._on_state_change = fn

    # ------------------------------------------------------------------
    # Core turn lifecycle (called by Node)
    # ------------------------------------------------------------------

    def on_user_transcript(self, transcript: str) -> Dict[str, Any]:
        """Process a user transcript through the voice loop.

        Returns a dict with the turn result or an error/status indicator.
        """
        transcript = (transcript or "").strip()
        if not transcript:
            return {"ok": False, "error": "empty_transcript"}

        # Dedup check
        h = self._hash_transcript(transcript)
        now = time.time()
        with self._lock:
            if h in self._recent_hashes:
                last = self._recent_hashes[h]
                if now - last < DEDUP_WINDOW_S:
                    return {"ok": False, "error": "duplicate_transcript"}

            self._recent_hashes[h] = now
            # Prune old hashes
            cutoff = now - DEDUP_WINDOW_S * 2
            self._recent_hashes = {
                k: v for k, v in self._recent_hashes.items() if v > cutoff
            }

        # Session timeout check
        if now - self._last_interaction > self._session_timeout:
            with self._lock:
                self._consecutive_errors = 0
            self._vi.reconnect()

        self._last_interaction = now

        # Create turn
        with self._lock:
            self._turn_counter += 1
            turn = Turn(
                turn_id=f"t-{self._turn_counter}",
                transcript=transcript,
            )
            self._current_turn = turn
            self._total_turns += 1

        # Transition to PROCESSING
        self._vi.process_transcript(transcript)

        # Mark executing
        turn.status = TurnStatus.EXECUTING
        turn.started_at = time.time()

        # Execute through brain
        try:
            if self._on_execute:
                result = self._on_execute(transcript)
            else:
                result = self._execute_default(transcript)

            turn.result = result
            turn.status = TurnStatus.COMPLETED
            with self._lock:
                self._consecutive_errors = 0

        except Exception as e:
            turn.error = str(e)
            turn.status = TurnStatus.FAILED
            with self._lock:
                self._consecutive_errors += 1

            if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                self._vi.set_error(f"Too many consecutive errors: {e}")
                return {"ok": False, "error": str(e), "disconnected": True}

            return {"ok": False, "error": str(e)}

        finally:
            turn.completed_at = time.time()
            with self._lock:
                self._turn_history.append(turn)
                if len(self._turn_history) > 100:
                    self._turn_history = self._turn_history[-50:]
                self._current_turn = None

        # TTS the response if available
        response_text = self._extract_response_text(turn.result)
        if response_text and self._on_tts:
            self._vi.speak(response_text)
            try:
                self._on_tts(response_text)
            except Exception:
                pass

        inner_ok = turn.result.get("ok", False) if isinstance(turn.result, dict) else False

        return {
            "ok": inner_ok,
            "turn_id": turn.turn_id,
            "transcript": transcript,
            "result": turn.result,
            "duration_ms": round(
                (turn.completed_at - turn.started_at) * 1000, 1
            )
            if turn.completed_at and turn.started_at
            else 0,
        }

    def on_interruption(self) -> Dict[str, Any]:
        """Handle barge-in: cancel in-flight turn, return to LISTENING."""
        with self._lock:
            self._total_interruptions += 1
            turn = self._current_turn
            if turn and turn.status == TurnStatus.EXECUTING:
                turn.status = TurnStatus.CANCELLED
                turn.completed_at = time.time()
                turn.error = "interrupted"
                self._turn_history.append(turn)
                self._current_turn = None

        self._vi.interrupt()
        # Transition back to LISTENING for the next turn
        self._vi.start_listening()

        return {"ok": True, "action": "interrupted"}

    def on_turn_complete(self) -> Dict[str, Any]:
        """Mark end of a TTS turn; transition back to LISTENING."""
        with self._lock:
            self._last_interaction = time.time()

        self._vi.start_listening()
        return {"ok": True, "state": self._vi.state.value}

    def on_disconnect(self) -> Dict[str, Any]:
        """Handle voice pipe disconnection."""
        with self._lock:
            turn = self._current_turn
            if turn and turn.status == TurnStatus.EXECUTING:
                turn.status = TurnStatus.CANCELLED
                turn.error = "disconnected"
                turn.completed_at = time.time()
                self._turn_history.append(turn)
                self._current_turn = None

        self._vi.disconnect()
        return {"ok": True, "state": "disconnected"}

    def on_reconnect(self) -> Dict[str, Any]:
        """Recover from disconnection."""
        with self._lock:
            self._consecutive_errors = 0
            self._session_started = time.time()
            self._last_interaction = time.time()

        self._vi.reconnect()
        self._vi.start_listening()
        return {"ok": True, "state": self._vi.state.value}

    # ------------------------------------------------------------------
    # Timeouts & maintenance (called periodically by Node)
    # ------------------------------------------------------------------

    def tick(self) -> Dict[str, Any]:
        """Periodic maintenance: check timeouts, clean up zombies.

        Should be called every ~5 seconds by the Node bridge.
        """
        now = time.time()
        actions: List[str] = []

        with self._lock:
            turn = self._current_turn

            # Turn timeout
            if turn and turn.status == TurnStatus.EXECUTING:
                if turn.started_at and (now - turn.started_at) > self._turn_timeout:
                    turn.status = TurnStatus.TIMED_OUT
                    turn.error = "turn_timeout"
                    turn.completed_at = now
                    self._turn_history.append(turn)
                    self._current_turn = None
                    actions.append("turn_timed_out")

            # Silence timeout — auto-idle if no interaction
            if now - self._last_interaction > self._silence_timeout:
                if self._vi.state in (VoiceState.LISTENING, VoiceState.SPEAKING):
                    self._vi.stop_listening()
                    actions.append("silence_timeout")

            # Session timeout — auto-disconnect
            if now - self._last_interaction > self._session_timeout:
                if self._vi.state != VoiceState.DISCONNECTED:
                    self._vi.disconnect()
                    actions.append("session_timeout")

            # Prune old dedup hashes
            cutoff = now - DEDUP_WINDOW_S * 4
            self._recent_hashes = {
                k: v for k, v in self._recent_hashes.items() if v > cutoff
            }

        return {"ok": True, "actions": actions}

    # ------------------------------------------------------------------
    # Health / introspection
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """Full voice-loop health report."""
        with self._lock:
            current = self._current_turn
            return {
                "voice_state": self._vi.state.value,
                "current_turn": current.to_dict() if current else None,
                "total_turns": self._total_turns,
                "total_interruptions": self._total_interruptions,
                "consecutive_errors": self._consecutive_errors,
                "session_uptime_s": round(time.time() - self._session_started, 1),
                "last_interaction_age_s": round(
                    time.time() - self._last_interaction, 1
                ),
                "history_length": len(self._turn_history),
            }

    def get_recent_turns(self, count: int = 10) -> List[Dict[str, Any]]:
        """Return the last N turns."""
        with self._lock:
            return [t.to_dict() for t in self._turn_history[-count:]]

    def status(self) -> Dict[str, Any]:
        """Lightweight status for /health endpoints."""
        return {
            "state": self._vi.state.value,
            "total_turns": self._total_turns,
            "total_interruptions": self._total_interruptions,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_transcript(text: str) -> str:
        return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]

    def _execute_default(self, transcript: str) -> Dict[str, Any]:
        """Fallback: return a stub that signals no execute callback registered."""
        return {
            "ok": False,
            "error": "No execute callback registered on ContinuousVoiceLoop",
            "transcript": transcript,
        }

    @staticmethod
    def _extract_response_text(result: Dict[str, Any]) -> Optional[str]:
        """Pull a speakable response from an execution result dict."""
        if not result:
            return None
        # Common patterns from brain/tools
        for key in ("response", "text", "message", "result"):
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                return val[:500]  # Cap TTS length
            if isinstance(val, dict):
                inner = val.get("response") or val.get("text") or val.get("message")
                if isinstance(inner, str) and inner.strip():
                    return inner[:500]
        return None
