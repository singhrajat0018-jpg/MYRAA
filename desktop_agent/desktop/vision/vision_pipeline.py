"""
MYRAA Cognitive Vision

Vision Pipeline

Responsible ONLY for converting a raw screenshot into a VisionContext.

Pipeline

Frame
    ↓
Image Processing
    ↓
OCR
    ↓
Shape Detection
    ↓
Layout Analysis
    ↓
Vision Context
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .vision_context import VisionContext
from .vision_context import VisionContextBuilder

from .shape_detector import ShapeDetector
from .layout_analyzer import LayoutAnalyzer


# ==========================================================
# Result
# ==========================================================


@dataclass(slots=True)
class VisionResult:

    image: Any

    processed_image: Any

    text_regions: list

    shapes: list

    layout: Any

    context: VisionContext


# ==========================================================
# Vision Pipeline
# ==========================================================


class VisionPipeline:
    """
    Converts one screenshot into a VisionContext.

    VisionManager owns runtime.

    VisionPipeline owns computer vision.
    """

    def __init__(

        self,

        image_processor,

        ocr_engine,

        shape_detector: ShapeDetector | None = None,

        layout_analyzer: LayoutAnalyzer | None = None,

        builder: VisionContextBuilder | None = None,

    ):

        self.processor = image_processor

        self.ocr = ocr_engine

        self.shapes = (

            shape_detector

            if shape_detector

            else ShapeDetector()

        )

        self.layout = (

            layout_analyzer

            if layout_analyzer

            else LayoutAnalyzer()

        )

        self.builder = (

            builder

            if builder

            else VisionContextBuilder()

        )

    # ------------------------------------------------------

    def process(
        self,
        frame,
    ) -> VisionContext | None:
        """
        Execute complete vision pipeline.
        """

        import numpy as np

        #
        # Convert PIL -> numpy
        #

        if not isinstance(frame, np.ndarray):
            image = np.array(frame)
        else:
            image = frame

        #
        # -----------------------------------------
        # Image Processing
        # -----------------------------------------
        #

        processed = self.processor.denoise(image)
        processed = self.processor.sharpen(processed)

        #
        # -----------------------------------------
        # OCR
        # -----------------------------------------
        #

        text_regions = []

        if self.ocr is not None:

            try:

                ocr_result = self.ocr.recognize(processed)

                if hasattr(ocr_result, "regions"):

                    text_regions = ocr_result.regions

            except Exception:

                text_regions = []

        #
        # -----------------------------------------
        # Shape Detection
        # -----------------------------------------
        #

        try:

            shapes = self.shapes.detect(processed)

        except Exception:

            shapes = []

        #
        # -----------------------------------------
        # Layout
        # -----------------------------------------
        #

        layout = self.layout.analyze(
            processed,
            text_regions,
            shapes,
        )
        #
        # -----------------------------------------
        # Vision Context
        # -----------------------------------------
        #

        return self.builder.build(
            layout,
            text_regions,
            shapes,
        )