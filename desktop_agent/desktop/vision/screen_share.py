"""
MYRAA Phase 3.2 — ScreenShareEngine

Canonical single screen-share source for the entire MYRAA runtime.

Replaces the screenshot-per-request Vision architecture with a
continuous, low-overhead live screen stream.

Lifecycle:
    start()  → capture thread begins, first frame delivered
    stop()   → capture thread stops, resources released
    restart() → stop + start
    health() → status dict

Consumers subscribe via subscribe(callback) and receive state updates.
The engine owns ONE ScreenshotEngine instance and ONE capture thread.

Privacy:
    - raw frames never leave this module
    - no cloud upload, no memory persistence, no telemetry payload
    - consumers receive frame references, not copies, unless they request them
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

from .screenshot_engine import ScreenshotEngine, ScreenshotResult

try:
    import win32gui
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False


# ================================================================
# Screen Share Status
# ================================================================

class ScreenShareStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    ACTIVE = "active"
    DEGRADED = "degraded"
    RECOVERING = "recovering"


# ================================================================
# Screen State (lightweight)
# ================================================================

@dataclass
class ScreenState:
    """Canonical current screen state — lightweight, no image data."""
    screen_id: int = 0
    frame_id: int = 0
    timestamp: float = 0.0
    width: int = 0
    height: int = 0
    active_window_title: str = ""
    active_window_hwnd: Optional[int] = None
    active_application: str = ""
    changed: bool = False
    diff_score: float = 0.0
    freshness: str = "fresh"
    source: str = "screen_share"

    @property
    def age_s(self) -> float:
        if self.timestamp <= 0:
            return float("inf")
        return time.time() - self.timestamp


# ================================================================
# Screen Share Engine
# ================================================================

class ScreenShareEngine:
    """
    Canonical single screen-share engine for MYRAA.

    Owns:
        - ONE ScreenshotEngine (OS capture)
        - ONE capture thread
        - bounded frame buffer (latest frame only)
        - screen state (active window, change detection)
        - subscriber list

    Does NOT:
        - perform AI analysis
        - run OCR
        - do vision pipeline processing
        - store frames to disk or memory
        - send frames to cloud
    """

    def __init__(
        self,
        target_fps: int = 5,
        static_threshold: float = 0.01,
        static_frames_to_idle: int = 30,
        idle_fps: int = 1,
    ):
        self.target_fps = target_fps
        self.idle_fps = idle_fps
        self.static_threshold = static_threshold
        self.static_frames_to_idle = static_frames_to_idle

        # Capture
        self._engine: Optional[ScreenshotEngine] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Frame buffer (latest only — bounded)
        self._latest_frame: Optional[ScreenshotResult] = None
        self._frame_id: int = 0
        self._timestamp: float = 0.0
        self._interval: float = 1.0 / target_fps

        # Adaptive FPS
        self._consecutive_static: int = 0
        self._last_diff_score: float = 0.0
        self._idle_mode: bool = False

        # Screen state
        self._state = ScreenState()
        self._prev_frame_pil = None

        # Subscribers
        self._subscribers: List[Callable[[ScreenState], None]] = []
        self._subscriber_lock = threading.Lock()

        # Status
        self._status = ScreenShareStatus.STOPPED
        self._consecutive_errors: int = 0

    # ================================================================
    # Lifecycle
    # ================================================================

    def start(self) -> None:
        """Start screen sharing. Idempotent."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._status = ScreenShareStatus.STARTING
            self._engine = ScreenshotEngine()
            self._thread = threading.Thread(
                target=self._capture_loop,
                daemon=True,
                name="ScreenShare",
            )
            self._thread.start()
        log.info("ScreenShareEngine started (target_fps=%d)", self.target_fps)

    def stop(self) -> None:
        """Stop screen sharing. Idempotent."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._status = ScreenShareStatus.STOPPED
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        if self._engine:
            self._engine.close()
            self._engine = None
        log.info("ScreenShareEngine stopped")

    def restart(self) -> None:
        """Restart screen sharing."""
        self.stop()
        time.sleep(0.5)
        self.start()

    def health(self) -> Dict[str, Any]:
        """Return health status."""
        return {
            "status": self._status.value,
            "running": self._running,
            "frame_id": self._frame_id,
            "timestamp": self._timestamp,
            "age_s": self._state.age_s,
            "idle_mode": self._idle_mode,
            "diff_score": self._last_diff_score,
            "consecutive_errors": self._consecutive_errors,
            "subscribers": len(self._subscribers),
            "target_fps": self.target_fps,
            "current_interval": self._interval,
        }

    @property
    def status(self) -> ScreenShareStatus:
        return self._status

    @property
    def is_active(self) -> bool:
        return self._status == ScreenShareStatus.ACTIVE

    # ================================================================
    # Frame Access
    # ================================================================

    def latest_frame(self) -> Optional[ScreenshotResult]:
        """Get the latest captured frame (reference, not copy)."""
        with self._lock:
            return self._latest_frame

    def latest_image(self):
        """Get the latest PIL Image, or None."""
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.image

    def latest_state(self) -> ScreenState:
        """Get the current screen state."""
        return self._state

    def wait_for_first_frame(self, timeout: float = 10.0) -> bool:
        """Block until the first frame is available."""
        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                if self._latest_frame is not None:
                    return True
            time.sleep(0.05)
        return False

    # ================================================================
    # Subscribers
    # ================================================================

    def subscribe(self, callback: Callable[[ScreenState], None]) -> None:
        """Subscribe to screen state changes."""
        with self._subscriber_lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[ScreenState], None]) -> None:
        """Unsubscribe from screen state changes."""
        with self._subscriber_lock:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

    def _notify_subscribers(self, state: ScreenState) -> None:
        """Notify all subscribers of state change."""
        with self._subscriber_lock:
            subscribers = list(self._subscribers)
        for cb in subscribers:
            try:
                cb(state)
            except Exception as e:
                log.debug("Subscriber error: %s", e)

    # ================================================================
    # Adaptive FPS
    # ================================================================

    def _update_diff_score(self, score: float) -> None:
        """Update diff score and adjust FPS."""
        self._last_diff_score = score
        if score < self.static_threshold:
            self._consecutive_static += 1
        else:
            self._consecutive_static = 0

        if not self._idle_mode and self._consecutive_static >= self.static_frames_to_idle:
            self._idle_mode = True
            self._interval = 1.0 / self.idle_fps
            log.debug("ScreenShare: idle mode -> %d FPS", self.idle_fps)
        elif self._idle_mode and self._consecutive_static == 0:
            self._idle_mode = False
            self._interval = 1.0 / self.target_fps
            log.debug("ScreenShare: active mode -> %d FPS", self.target_fps)

    # ================================================================
    # Capture Loop
    # ================================================================

    def _capture_loop(self) -> None:
        """Main capture loop — captures frames and maintains state."""
        log.debug("ScreenShare capture thread started")

        while self._running:
            try:
                if self._engine is None:
                    break

                frame = self._engine.capture_screen()
                if frame is None:
                    time.sleep(0.1)
                    continue

                now = time.time()
                changed = False
                diff_score = 0.0

                # Lightweight change detection (compare PIL images)
                if self._prev_frame_pil is not None:
                    try:
                        from .frame_difference import FrameDifference
                        fd = FrameDifference()
                        result = fd.compare(self._prev_frame_pil, frame.image)
                        diff_score = result.score
                        changed = diff_score > self.static_threshold
                    except Exception:
                        changed = True
                        diff_score = 1.0

                self._update_diff_score(diff_score)
                self._prev_frame_pil = frame.image

                # Update state
                self._frame_id += 1
                self._timestamp = now

                # Get active window (lightweight)
                win_title, win_hwnd, win_app = self._get_active_window()

                self._state = ScreenState(
                    screen_id=1,
                    frame_id=self._frame_id,
                    timestamp=now,
                    width=frame.width,
                    height=frame.height,
                    active_window_title=win_title,
                    active_window_hwnd=win_hwnd,
                    active_application=win_app,
                    changed=changed,
                    diff_score=diff_score,
                    freshness="fresh",
                    source="screen_share",
                )

                # Store latest frame (bounded — latest only)
                with self._lock:
                    self._latest_frame = frame

                self._status = ScreenShareStatus.ACTIVE
                self._consecutive_errors = 0

                # Notify subscribers on change
                if changed:
                    self._notify_subscribers(self._state)

            except Exception as e:
                self._consecutive_errors += 1
                log.warning("ScreenShare capture error (%d): %s", self._consecutive_errors, e)
                if self._consecutive_errors >= 5:
                    self._status = ScreenShareStatus.DEGRADED
                time.sleep(1.0)
                continue

            time.sleep(self._interval)

    def _get_active_window(self) -> tuple:
        """Get active window title, handle, and application name."""
        if not _HAS_WIN32:
            return "", None, ""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd)
                # Extract app name from title (usually "App - Document")
                app = title.split(" - ")[0].split(" | ")[0].strip() if title else ""
                return title, hwnd, app
        except Exception:
            pass
        return "", None, ""


# ================================================================
# Singleton accessor
# ================================================================

_shared_engine: Optional[ScreenShareEngine] = None
_shared_lock = threading.Lock()


def get_screen_share_engine(**kwargs) -> ScreenShareEngine:
    """Get or create the shared ScreenShareEngine singleton."""
    global _shared_engine
    with _shared_lock:
        if _shared_engine is None:
            _shared_engine = ScreenShareEngine(**kwargs)
        return _shared_engine


def reset_screen_share_engine() -> None:
    """Reset the singleton (for testing)."""
    global _shared_engine
    with _shared_lock:
        if _shared_engine is not None:
            _shared_engine.stop()
        _shared_engine = None
