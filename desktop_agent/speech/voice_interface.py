"""
MYRAA Speech - Voice Interface (Phase C).

Concrete voice interface adapter that provides Python-side state management
for the Node voice bridge. Actual STT/TTS happens on the Node side;
this module exposes a stateful surface that Node can call into and query.

Thread-safe. No external dependencies.
"""

from __future__ import annotations

import enum
import threading
import time
from typing import Any, Callable, Dict, List, Optional


class VoiceState(enum.Enum):
    """Possible states of the voice interface."""

    IDLE = "idle"
    CONNECTING = "connecting"
    READY = "ready"
    LISTENING = "listening"
    USER_SPEAKING = "user_speaking"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    RECONNECTING = "reconnecting"
    DEGRADED = "degraded"
    ERROR = "error"
    DISCONNECTED = "disconnected"
    STOPPING = "stopping"


class VoiceInterface:
    """
    Python-side state manager for the voice pipeline.

    This is NOT a second voice pipeline. It is an adapter that the Node
    voice bridge can call into.  The actual audio processing (STT/TTS)
    lives on the Node side; this class tracks which state the conversation
    is in and exposes hooks for the rest of the Python agent.

    Usage::

        vi = VoiceInterface()
        vi.start_listening()
        result = vi.process_transcript("open notepad")
        vi.speak("Done.")
        vi.stop_listening()
    """

    # Valid transitions: from_state -> set of allowed to_states.
    _TRANSITIONS: Dict[VoiceState, set] = {
        VoiceState.IDLE: {VoiceState.CONNECTING, VoiceState.LISTENING, VoiceState.DISCONNECTED, VoiceState.ERROR},
        VoiceState.CONNECTING: {VoiceState.READY, VoiceState.ERROR, VoiceState.DISCONNECTED, VoiceState.DEGRADED},
        VoiceState.READY: {VoiceState.LISTENING, VoiceState.DISCONNECTED, VoiceState.ERROR},
        VoiceState.LISTENING: {
            VoiceState.IDLE,
            VoiceState.USER_SPEAKING,
            VoiceState.PROCESSING,
            VoiceState.INTERRUPTED,
            VoiceState.ERROR,
            VoiceState.DISCONNECTED,
        },
        VoiceState.USER_SPEAKING: {
            VoiceState.PROCESSING,
            VoiceState.LISTENING,
            VoiceState.INTERRUPTED,
        },
        VoiceState.PROCESSING: {
            VoiceState.SPEAKING,
            VoiceState.IDLE,
            VoiceState.INTERRUPTED,
            VoiceState.ERROR,
            VoiceState.DISCONNECTED,
        },
        VoiceState.SPEAKING: {
            VoiceState.IDLE,
            VoiceState.LISTENING,
            VoiceState.USER_SPEAKING,
            VoiceState.INTERRUPTED,
            VoiceState.ERROR,
            VoiceState.DISCONNECTED,
        },
        VoiceState.INTERRUPTED: {VoiceState.IDLE, VoiceState.LISTENING, VoiceState.ERROR, VoiceState.RECONNECTING},
        VoiceState.RECONNECTING: {VoiceState.READY, VoiceState.DEGRADED, VoiceState.ERROR, VoiceState.DISCONNECTED},
        VoiceState.DEGRADED: {VoiceState.IDLE, VoiceState.CONNECTING, VoiceState.DISCONNECTED},
        VoiceState.ERROR: {VoiceState.IDLE, VoiceState.DISCONNECTED, VoiceState.RECONNECTING},
        VoiceState.DISCONNECTED: {VoiceState.IDLE, VoiceState.CONNECTING},
        VoiceState.STOPPING: {VoiceState.IDLE, VoiceState.DISCONNECTED},
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: VoiceState = VoiceState.IDLE
        self._error_count: int = 0
        self._last_interaction: float = 0.0
        self._state_history: List[Dict[str, Any]] = []
        self._listeners: List[Callable[[VoiceState, VoiceState], None]] = []
        self._transcript_buffer: str = ""

    # ------------------------------------------------------------------
    # State property
    # ------------------------------------------------------------------

    @property
    def state(self) -> VoiceState:
        """Current voice state."""
        with self._lock:
            return self._state

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _transition(self, new_state: VoiceState) -> None:
        """Internal: validate and apply a state transition."""
        old = self._state
        allowed = self._TRANSITIONS.get(old, set())
        if new_state not in allowed:
            return
        self._state = new_state
        now = time.time()
        self._last_interaction = now
        self._state_history.append(
            {"from": old.value, "to": new_state.value, "timestamp": now}
        )
        # Keep history bounded.
        if len(self._state_history) > 200:
            self._state_history = self._state_history[-100:]

        for cb in list(self._listeners):
            try:
                cb(old, new_state)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_listening(self) -> None:
        """Transition to LISTENING state."""
        with self._lock:
            self._transition(VoiceState.LISTENING)

    def stop_listening(self) -> None:
        """Return to IDLE from any state that allows it."""
        with self._lock:
            self._transition(VoiceState.IDLE)

    def process_transcript(self, text: str) -> Dict[str, Any]:
        """Accept a transcript from Node, transition to PROCESSING.

        Returns a stub result dict.  The actual command execution happens
        through the existing brain pipeline; this method just manages voice
        state and buffers the transcript for downstream consumers.
        """
        with self._lock:
            self._transcript_buffer = text
            self._transition(VoiceState.PROCESSING)

        return {
            "ok": True,
            "state": self._state.value,
            "transcript": text,
            "timestamp": time.time(),
        }

    def speak(self, text: str) -> None:
        """Enter SPEAKING state (Node sends TTS audio externally)."""
        with self._lock:
            self._transition(VoiceState.SPEAKING)

    def interrupt(self) -> None:
        """Interrupt current speech or processing."""
        with self._lock:
            self._transition(VoiceState.INTERRUPTED)

    def set_error(self, message: str = "") -> None:
        """Transition to ERROR and bump error counter."""
        with self._lock:
            self._error_count += 1
            self._transition(VoiceState.ERROR)

    def disconnect(self) -> None:
        """Mark the voice pipe as disconnected."""
        with self._lock:
            self._transition(VoiceState.DISCONNECTED)

    def reconnect(self) -> None:
        """Recover from DISCONNECTED back to IDLE."""
        with self._lock:
            self._transition(VoiceState.IDLE)

    def connecting(self) -> None:
        """Transition to CONNECTING state."""
        with self._lock:
            self._transition(VoiceState.CONNECTING)

    def ready(self) -> None:
        """Transition to READY state."""
        with self._lock:
            self._transition(VoiceState.READY)

    def user_speaking(self) -> None:
        """Transition to USER_SPEAKING state."""
        with self._lock:
            self._transition(VoiceState.USER_SPEAKING)

    def reconnecting(self) -> None:
        """Transition to RECONNECTING state."""
        with self._lock:
            self._transition(VoiceState.RECONNECTING)

    def degraded(self) -> None:
        """Transition to DEGRADED state."""
        with self._lock:
            self._transition(VoiceState.DEGRADED)

    def stopping(self) -> None:
        """Transition to STOPPING state."""
        with self._lock:
            self._transition(VoiceState.STOPPING)

    def reset(self) -> None:
        """Force-reset to IDLE regardless of current state."""
        with self._lock:
            old = self._state
            self._state = VoiceState.IDLE
            self._transcript_buffer = ""
            self._state_history.append(
                {"from": old.value, "to": VoiceState.IDLE.value, "timestamp": time.time()}
            )
            for cb in list(self._listeners):
                try:
                    cb(old, VoiceState.IDLE)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Health / introspection
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """Return a health-check dict for Node polling."""
        with self._lock:
            return {
                "state": self._state.value,
                "error_count": self._error_count,
                "last_interaction": self._last_interaction,
                "transcript_buffer": self._transcript_buffer,
                "history_length": len(self._state_history),
            }

    def get_history(self, count: int = 20) -> List[Dict[str, Any]]:
        """Return the last *count* state transitions."""
        with self._lock:
            return list(self._state_history)[-count:]

    # ------------------------------------------------------------------
    # Listener API
    # ------------------------------------------------------------------

    def on_state_change(self, callback: Callable[[VoiceState, VoiceState], None]) -> None:
        """Register a callback: callback(old_state, new_state)."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable) -> None:
        """Remove a previously registered callback."""
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass
