"""
MYRAA Desktop Control V3

Live Capture Engine
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from .screenshot_engine import ScreenshotEngine, ScreenshotResult


class LiveCaptureEngine:

    def __init__(
        self,
        fps: int = 15,
    ):

        self.fps = fps
        self.interval = 1.0 / fps

        self.engine = ScreenshotEngine()

        self._thread: Optional[threading.Thread] = None

        self._running = False

        self._paused = False

        self._latest: Optional[ScreenshotResult] = None

        self._frame_number = 0

        self._timestamp = 0.0

        self._lock = threading.Lock()

    # ---------------------------------------
    # LOOP
    # ---------------------------------------

    def _capture_loop(self):

        print("[Capture] Thread started")

        while self._running:

            if self._paused:
                time.sleep(0.05)
                continue

            print("[Capture] Capturing...")

            frame = self.engine.capture_screen()

            print(
                "[Capture] Frame:",
                frame is not None
            )

            with self._lock:

                self._latest = frame

                self._frame_number += 1

                self._timestamp = time.time()

            time.sleep(self.interval)

    # ---------------------------------------
    # CONTROL
    # ---------------------------------------

    def start(self):

        if self._running:

            return

        self._running = True

        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
        )

        self._thread.start()

    def stop(self):

        self._running = False

        if self._thread:

            self._thread.join(timeout=2)

        self.engine.close()

    def is_running(self):

        return self._running

        # ---------------------------------------
    # PAUSE / RESUME
    # ---------------------------------------

    def pause(self):

        self._paused = True

    def resume(self):

        self._paused = False

    def is_paused(self):

        return self._paused

    # ---------------------------------------
    # LATEST FRAME
    # ---------------------------------------

    def latest_result(self):

        with self._lock:

            return self._latest

    def latest_image(self):

        with self._lock:

            if self._latest is None:
                return None

            return self._latest.image

    def latest_timestamp(self):

        with self._lock:

            return self._timestamp

    def frame_number(self):

        with self._lock:

            return self._frame_number

    # ---------------------------------------
    # WAIT
    # ---------------------------------------

    def wait_for_first_frame(
        self,
        timeout: float = 5.0,
    ):

        start = time.time()

        while time.time() - start < timeout:

            with self._lock:

                if self._latest is not None:
                    return True

            time.sleep(0.01)

        return False

        # ---------------------------------------
    # CALLBACKS
    # ---------------------------------------

    def set_frame_callback(
        self,
        callback,
    ):

        """
        Called every time a new frame is captured.

        callback(frame: ScreenshotResult)
        """

        self._callback = callback

    # ---------------------------------------
    # PERFORMANCE
    # ---------------------------------------

    def fps_value(self):

        return self.fps

    def capture_interval(self):

        return self.interval

    # ---------------------------------------
    # INFORMATION
    # ---------------------------------------

    def status(self):

        return {
            "running": self._running,
            "paused": self._paused,
            "fps": self.fps,
            "frame_number": self._frame_number,
            "timestamp": self._timestamp,
        }

    # ---------------------------------------
    # RESET
    # ---------------------------------------

    def reset(self):

        with self._lock:

            self._latest = None
            self._frame_number = 0
            self._timestamp = 0.0

    # ---------------------------------------
    # CONTEXT MANAGER
    # ---------------------------------------

    def __enter__(self):

        self.start()

        self.wait_for_first_frame()

        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):

        self.stop()