"""
MYRAA Vision V3 — Vision Manager

Coordinates vision analysis by consuming the canonical
ScreenShareEngine (single capture authority).

Phase 3.3: VisionManager no longer owns a capture engine.
It reads frames from ScreenShareEngine and performs analysis.
"""

from __future__ import annotations
from .vision_pipeline import VisionPipeline
import logging
import threading
import time

from dataclasses import dataclass
from typing import Callable, List, Optional
from .image_processor import ImageProcessor
from .ocr_engine import OCREngine

# appropriate backend import bhi yahan hoga
from .desktop_state import DesktopState
from .frame_difference import FrameDifference
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


log = logging.getLogger(__name__)


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
    Vision analysis layer. Consumes ScreenShareEngine as the single
    capture source. No longer owns a capture engine or capture thread.
    """

    # ------------------------------------------------------

    def __init__(

        self,

        frame_difference: Optional[FrameDifference] = None,

        analyzer: Optional[ScreenAnalyzer] = None,

        context_builder: Optional[VisionContextBuilder] = None,

        transition: Optional[ScreenTransition] = None,

        config: Optional[VisionManagerConfig] = None,

    ):

        self.config = config or VisionManagerConfig()

        # ------------------------------------------
        # Analysis engines (NO capture engine)
        # ------------------------------------------

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
    def start(self, screen_share=None):

        """
        Start vision analysis. Consumes ScreenShareEngine for frames.
        Does NOT start a capture engine — ScreenShareEngine is the source.
        """

        with self._lock:

            if self.running:

                return

            self.running = True

            self.paused = False

            self._stop_event.clear()

            self._screen_share = screen_share

            self._thread = threading.Thread(

                target=self._vision_loop,

                daemon=True,

                name="MYRAA-Vision",

            )

            self._thread.start()

    # ------------------------------------------------------
    def stop(self):

        """
        Stop vision analysis. Does NOT stop ScreenShareEngine.
        """

        with self._lock:

            if not self.running:

                return

            self.running = False

            self._stop_event.set()

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
        Background vision worker — reads from ScreenShareEngine.
        """
        log.debug("Vision loop started (consuming ScreenShareEngine)")
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

            # Read frame from ScreenShareEngine (single capture authority)
            if self._screen_share is None:
                time.sleep(0.1)
                continue

            frame = self._screen_share.latest_image()
            log.debug("latest_image = %s", frame is not None)

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

                    log.debug("Vision error: %s", exc)

            time.sleep(frame_interval)

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
        log.debug("Processing frame")
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
        log.debug("Publishing DesktopState")
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

