"""
Screen Observer
----------------
Provides continuous screen vision capabilities for MYRAA.
Captures screen frames and emits events for processing.
"""

from __future__ import annotations

import time
import logging
import threading
from typing import Optional, List, Callable
from queue import Queue, Empty

import numpy as np
import win32gui
import win32process

from ..event import ObserverEvent, EventType, EventSeverity
from .base_observer import BaseObserver
from desktop_agent.desktop.vision.screen_share import ScreenShareEngine
from desktop_agent.desktop.vision.frame_difference import FrameDifference
from desktop_agent.desktop.vision.ocr_engine import OCREngine
from desktop_agent.desktop.vision.ocr_backends.tesseract_backend import TesseractBackend as TesseractOCR


class ScreenObserver(BaseObserver):
    """
    Observes the user's screen and emits events for:
    - Screen frames captured
    - Significant screen changes detected
    - OCR results when text changes significantly
    - Application/window context changes

    Phase 3.3: Consumes ScreenShareEngine (single capture authority).
    Does NOT own a capture engine or capture thread.
    """

    log = logging.getLogger(__name__)

    def __init__(
        self,
        name: str = "screen_observer",
        process_fps: int = 4,
        change_threshold: float = 0.02,
        ocr_interval: float = 5.0,
        screen_share: Optional[ScreenShareEngine] = None,
    ) -> None:
        super().__init__(name)

        # Processing settings
        self.process_fps = process_fps
        self.process_interval = 1.0 / process_fps

        # Change detection
        self.change_threshold = change_threshold
        self.ocr_interval = ocr_interval

        # Components — consume ScreenShareEngine
        self._screen_share = screen_share
        self.frame_difference = FrameDifference()
        self.ocr_engine = OCREngine(TesseractOCR())

        # State tracking
        self._last_frame: Optional[np.ndarray] = None
        self._last_process_time = 0.0
        self._last_ocr_time = 0.0
        self._last_frame_time = 0.0
        self._last_ocr_text = ""
        self._last_window_title = ""
        self._last_window_hwnd = None
        self._frame_count = 0
        self._processed_count = 0

        # Threading — NO capture thread (ScreenShareEngine handles capture)
        self._process_thread: Optional[threading.Thread] = None

        # Event queue for observer pattern with bounded size to prevent memory buildup
        self._event_queue: Queue[ObserverEvent] = Queue(maxsize=500)

        # Control flags
        self._running = False
        self._process_active = False

        # Callbacks for external integration
        self._frame_callback: Optional[Callable] = None
        self._change_callback: Optional[Callable] = None

    # --------------------------------------------------
    # BaseObserver Implementation
    # --------------------------------------------------

    def start(self) -> None:
        """Start the screen observer. Consumes ScreenShareEngine."""
        if self._running:
            return

        self._running = True
        self._process_active = True

        # Start processing thread only (no capture thread)
        self._process_thread = threading.Thread(
            target=self._process_loop,
            daemon=True,
            name=f"{self.name}_process"
        )
        self._process_thread.start()

    def stop(self) -> None:
        """Stop the screen observer."""
        if not self._running:
            return

        self._running = False
        self._process_active = False

        if self._process_thread:
            self._process_thread.join(timeout=2.0)

    def poll(self) -> list:
        """
        Poll for events. This is called by the ObserverManager.
        Returns a list of events since the last poll.
        """
        events = []
        try:
            while True:
                event = self._event_queue.get_nowait()
                events.append(event)
        except Empty:
            pass
        self.log.debug("poll() returning %d events", len(events))
        return events

    # --------------------------------------------------
    # Internal Loops
    # --------------------------------------------------

    def _process_loop(self) -> None:
        """Processing loop — reads frames from ScreenShareEngine."""
        while self._running and self._process_active:
            try:
                # Read frame from ScreenShareEngine (single capture authority)
                if self._screen_share is None:
                    time.sleep(0.5)
                    continue

                frame = self._screen_share.latest_image()
                if frame is not None:
                    frame_array = np.array(frame)
                    frame_timestamp = time.time()
                    self._process_frame(frame_array, frame_timestamp)

                time.sleep(self.process_interval)
            except Exception as e:
                # Log error but continue running
                self.log.debug("Process error: %s", e)
                time.sleep(self.process_interval)

    def _process_frame(self, frame_array: np.ndarray, frame_timestamp: float) -> None:
        """Process a single frame for changes and emit appropriate events."""
        current_time = time.time()
        self._frame_count += 1

        # Get current window title and hwnd for context
        window_title, window_hwnd = self._get_active_window_info()

        # Check if enough time has passed since last processing
        if current_time - self._last_process_time < self.process_interval:
            return

        self._last_process_time = current_time
        self._processed_count += 1

        # Detect significant changes from last frame
        change_detected = False
        change_score = 0.0

        if self._last_frame is not None:
            try:
                # Calculate frame difference
                change_score = self.frame_difference.calculate_difference(
                    self._last_frame, frame_array
                )
                change_detected = change_score > self.change_threshold
            except Exception:
                change_detected = True  # Assume change on error

        # Update last frame
        self._last_frame = frame_array.copy()
        self._last_frame_time = frame_timestamp

        # Emit frame captured event (always)
        frame_event = ObserverEvent(
            source=self.name,
            event_type=EventType.CUSTOM,
            title="Screen Frame Captured",
            message=f"Captured screen frame ({frame_array.shape[1]}x{frame_array.shape[0]})",
            severity=EventSeverity.INFO,
            timestamp=current_time,
            data={
                "frame_width": frame_array.shape[1],
                "frame_height": frame_array.shape[0],
                "frame_count": self._frame_count,
                "processed_count": self._processed_count,
                "change_detected": change_detected,
                "change_score": change_score,
                "window_title": window_title,
                "window_hwnd": window_hwnd
            }
        )
        self._emit_event(frame_event)

        # If significant change detected, emit change event and consider OCR
        if change_detected:
            change_event = ObserverEvent(
                source=self.name,
                event_type=EventType.CUSTOM,
                title="Screen Change Detected",
                message=f"Significant screen change detected (score: {change_score:.3f})",
                severity=EventSeverity.MEDIUM,
                timestamp=current_time,
                data={
                    "change_score": change_score,
                    "change_threshold": self.change_threshold,
                    "window_title": window_title,
                    "window_hwnd": window_hwnd,
                    "frame_dimensions": f"{frame_array.shape[1]}x{frame_array.shape[0]}"
                }
            )
            self._emit_event(change_event)

            # Check if we should run OCR (based on time and window title changes)
            should_ocr = (
                current_time - self._last_ocr_time > self.ocr_interval or
                window_title != self._last_window_title or
                window_hwnd != self._last_window_hwnd
            )

            if should_ocr:
                self._run_ocr_if_needed(frame_array, window_title, window_hwnd, current_time)

        # Update window tracking
        if window_title != self._last_window_title or window_hwnd != self._last_window_hwnd:
            window_event = ObserverEvent(
                source=self.name,
                event_type=EventType.CUSTOM,
                title="Window Context Changed",
                message=f"Active window changed to: {window_title}",
                severity=EventSeverity.LOW,
                timestamp=current_time,
                data={
                    "window_title": window_title,
                    "window_hwnd": window_hwnd,
                    "previous_title": self._last_window_title,
                    "previous_hwnd": self._last_window_hwnd
                }
            )
            self._emit_event(window_event)
            self._last_window_title = window_title
            self._last_window_hwnd = window_hwnd

    def _get_active_window_info(self) -> tuple[str, Optional[int]]:
        """Get the title and handle of the active window."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd)
                return title, hwnd
            else:
                return "", None
        except Exception:
            return "", None

    def _calculate_text_change(self, old_text: str, new_text: str) -> float:
        """Calculate similarity between two text strings."""
        if not old_text and not new_text:
            return 0.0
        if not old_text or not new_text:
            return 1.0

        # Simple character-based similarity
        longer = max(len(old_text), len(new_text))
        if longer == 0:
            return 0.0

        # Count matching characters at same positions
        matches = sum(1 for i in range(min(len(old_text), len(new_text)))
                     if old_text[i] == new_text[i])

        return 1.0 - (matches / longer)

    def _emit_event(self, event: ObserverEvent) -> None:
        """Emit an event to the observer's event queue."""
        try:
            self._event_queue.put_nowait(event)
            # Debug logging for event emission
            self.log.debug("Emitted event: %s", event.title)
        except Exception:
            # If queue is full, we drop the event (latest-frame-wins for events too)
            pass

    # --------------------------------------------------
    # Public Interface
    # --------------------------------------------------

    def set_frame_callback(self, callback: Callable) -> None:
        """Set callback for frame events (for direct integration)."""
        self._frame_callback = callback

    def set_change_callback(self, callback: Callable) -> None:
        """Set callback for change events (for direct integration)."""
        self._change_callback = callback

    def _run_ocr_if_needed(self, frame_array: np.ndarray, window_title: str, window_hwnd: Optional[int], timestamp: float) -> None:
        """Run OCR on frame if warranted and emit results."""
        try:
            # Run OCR (this will use the existing OCREngine)
            ocr_text = self.ocr_engine.extract_text(frame_array)

            # Only emit if text changed significantly
            if ocr_text.strip() and ocr_text.strip() != self._last_ocr_text.strip():
                text_change_score = self._calculate_text_change(
                    self._last_ocr_text, ocr_text
                )

                if text_change_score > 0.3:  # Significant text change
                    ocr_event = ObserverEvent(
                        source=self.name,
                        event_type=EventType.CUSTOM,
                        title="Screen Text Updated",
                        message=f"OCR detected text change in window: {window_title}",
                        severity=EventSeverity.INFO,
                        timestamp=timestamp,
                        data={
                            "ocr_text": ocr_text[:500],  # Limit text length
                            "text_length": len(ocr_text),
                            "window_title": window_title,
                            "window_hwnd": window_hwnd,
                            "change_score": text_change_score
                        }
                    )
                    self._emit_event(ocr_event)
                    self._last_ocr_text = ocr_text

            self._last_ocr_time = timestamp

        except Exception as e:
            # OCR failed gracefully - don't emit error event to avoid spam
            self.log.debug("OCR error: %s", e)

    def get_status(self) -> dict:
        """Get current observer status for monitoring."""
        return {
            "name": self.name,
            "running": self._running,
            "process_fps": self.process_fps,
            "frame_count": self._frame_count,
            "processed_count": self._processed_count,
            "screen_share_active": self._screen_share is not None and self._screen_share.is_active,
        }

    