"""
MYRAA Vision V3

Vision Manager

Coordinates the complete live vision pipeline.

Responsibilities
----------------
- Live Capture lifecycle
- Frame processing pipeline
- Desktop state updates
- Screen transition detection
- Vision event publishing

This class never performs OCR, layout analysis or
fusion directly. It only orchestrates the vision
subsystems.

Author
------
MYRAA Vision
"""

from __future__ import annotations
from .vision_pipeline import VisionPipeline
import threading
import time

from dataclasses import dataclass
from typing import Callable, List, Optional
from .image_processor import ImageProcessor
from .ocr_engine import OCREngine

# appropriate backend import bhi yahan hoga
from .desktop_state import DesktopState
from .frame_difference import FrameDifference
from .live_capture import LiveCaptureEngine
from .screen_analyzer import (
    ScreenAnalyzer,
    ScreenSummary,
)
from .screen_transition import (
    ScreenTransition,
    VisionEvent,
)
from .vision_context import (
    VisionContext,
    VisionContextBuilder,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(slots=True)
class VisionManagerConfig:

    enabled: bool = True

    target_fps: int = 15

    minimum_change: float = 0.02

    process_first_frame: bool = True

    auto_start_capture: bool = True

    debug: bool = False


# ==========================================================
# Vision Manager
# ==========================================================


class VisionManager:

    """
    Coordinates MYRAA's complete vision pipeline.
    """

    # ------------------------------------------------------

    def __init__(

        self,

        capture: Optional[LiveCaptureEngine] = None,

        frame_difference: Optional[FrameDifference] = None,

        analyzer: Optional[ScreenAnalyzer] = None,

        context_builder: Optional[VisionContextBuilder] = None,

        transition: Optional[ScreenTransition] = None,

        config: Optional[VisionManagerConfig] = None,

    ):

        self.config = config or VisionManagerConfig()

        # ------------------------------------------
        # Core engines
        # ------------------------------------------

        self.capture = capture or LiveCaptureEngine()

        self.frame_difference = (
            frame_difference or FrameDifference()
        )

        self.context_builder = (
            context_builder or VisionContextBuilder()
        )

        self.analyzer = (
            analyzer or ScreenAnalyzer()
        )

        self.transition = (
            transition or ScreenTransition()
        )

        # ------------------------------------------
        # State
        # ------------------------------------------

        self.state = DesktopState()

        self.previous_summary: Optional[
            ScreenSummary
        ] = None

        self.current_summary: Optional[
            ScreenSummary
        ] = None

        self.current_context: Optional[
            VisionContext
        ] = None

        self.frame_index = 0

        self.running = False

        self.paused = False

        # ------------------------------------------
        # Threading
        # ------------------------------------------

        self._thread: Optional[
            threading.Thread
        ] = None

        self._stop_event = threading.Event()

        self._lock = threading.RLock()

        # ------------------------------------------
        # Event callbacks
        # ------------------------------------------

        self._vision_callbacks: List[
            Callable[[DesktopState], None]
        ] = []

        self._event_callbacks: List[
            Callable[[VisionEvent], None]
        ] = []
        self.pipeline = VisionPipeline(
            image_processor=ImageProcessor(),
            ocr_engine=None,
        )
    # ======================================================
    # Lifecycle
    # ======================================================

    def start(self):

        """
        Starts MYRAA live vision.
        """

        with self._lock:

            if self.running:
                return

            self.running = True

            self.paused = False

            self._stop_event.clear()

            if self.config.auto_start_capture:

                self.capture.start()

            self._thread = threading.Thread(

                target=self._vision_loop,

                daemon=True,

                name="MYRAA-Vision",

            )

            self._thread.start()

    # ------------------------------------------------------

    def stop(self):

        """
        Stops live vision.
        """

        with self._lock:

            if not self.running:
                return

            self.running = False

            self._stop_event.set()

            self.capture.stop()

            if self._thread is not None:

                self._thread.join(timeout=2)

    # ------------------------------------------------------

    def pause(self):

        self.paused = True

    # ------------------------------------------------------

    def resume(self):

        self.paused = False

    # ------------------------------------------------------

    @property
    def is_running(self):

        return self.running

    # ------------------------------------------------------

    @property
    def is_paused(self):

        return self.paused

    # ------------------------------------------------------

    def add_state_listener(

        self,

        callback: Callable[[DesktopState], None],

    ):

        self._vision_callbacks.append(callback)

    # ------------------------------------------------------

    def add_event_listener(

        self,

        callback: Callable[[VisionEvent], None],

    ):

        self._event_callbacks.append(callback)

    # ======================================================
    # Main Vision Loop
    # ======================================================

    def _vision_loop(self):
        """
        Background vision worker.
        """
        print("[Vision] Loop started")
        frame_interval = 1.0 / max(
            self.config.target_fps,
            1,
        )

        previous_frame = None

        while (
            self.running
            and not self._stop_event.is_set()
        ):

            if self.paused:

                time.sleep(0.05)

                continue

            start = time.perf_counter()

            frame = self.capture.latest_image()
            print(
                "[Vision] latest_image =",
                frame is not None
            )

            if frame is None:

                time.sleep(0.01)

                continue

            try:

                self._process_frame(

                    frame,

                    previous_frame,

                )

                previous_frame = frame

            except Exception as exc:

                if self.config.debug:

                    print(

                        "[Vision]",

                        exc,

                    )

            elapsed = (

                time.perf_counter()

                - start

            )

            remaining = (

                frame_interval

                - elapsed

            )

            if remaining > 0:

                time.sleep(remaining)

    # ======================================================
    # Frame Processing
    # ======================================================

    def _process_frame(

        self,

        frame,

        previous_frame,

    ):

        """
        Complete frame pipeline.
        """
        print("[Vision] Processing frame")
        self.frame_index += 1

        # --------------------------------------
        # First frame
        # --------------------------------------

        if previous_frame is None:

            if not self.config.process_first_frame:

                return

        else:

            difference = self.frame_difference.compare(

                previous_frame,

                frame,

            )

            if (

                difference.score

                < self.config.minimum_change

            ):

                return

            changed_regions = (

                difference.changed_regions

            )

        if previous_frame is None:

            changed_regions = []

        # --------------------------------------
        # Build semantic context
        # --------------------------------------

        context = self._build_context(

            frame,

            changed_regions,

        )

        if context is None:

            return

        summary = self.analyzer.analyze(

            context,

        )

        self.current_context = context

        self.current_summary = summary

        # --------------------------------------
        # Desktop State
        # --------------------------------------

        self.state.update(

            frame_id=self.frame_index,

            vision_context=context,

            screen_summary=summary,

            changed_regions=changed_regions,

            confidence=summary.confidence,

        )

        # --------------------------------------
        # Semantic Events
        # --------------------------------------

        events = self.transition.compare(

            self.previous_summary,

            summary,

        )

        self.previous_summary = summary

        # --------------------------------------
        # Publish
        # --------------------------------------

        self._publish_state()

        self._publish_events(

            events,

        )

    # ======================================================
    # Publishers
    # ======================================================

    def _publish_state(self):
        print("[Vision] Publishing DesktopState")
        for callback in self._vision_callbacks:

            try:

                callback(

                    self.state,

                )

            except Exception:

                pass

    # ------------------------------------------------------

    def _publish_events(

        self,

        events: List[VisionEvent],

    ):

        for event in events:

            for callback in self._event_callbacks:

                try:

                    callback(

                        event,

                    )

                except Exception:

                    pass
    def _build_context(

        self,

        frame,

        changed_regions,

    ) -> VisionContext | None:

        if not hasattr(self, "pipeline"):

            raise RuntimeError(

                "VisionPipeline has not been configured."

            )

        return self.pipeline.process(frame)

