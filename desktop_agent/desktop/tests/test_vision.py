"""
Vision pipeline / validator contract tests (Part 4-6 restoration).

Tests the REAL production contract:
    VisionPipeline(image_processor, ocr_engine, ...).process(frame)
        -> VisionContext

Previously this file was a module-level smoke script that built
``VisionValidator(backend)`` (which passed ``ocr_backend=`` to
VisionPipeline — a TypeError). Now it is a proper pytest module that
exercises the pipeline + validator with a synthetic frame. No desktop
interaction, no Tesseract requirement.
"""

from __future__ import annotations

import numpy as np
import pytest

from desktop_agent.desktop.vision.image_processor import ImageProcessor
from desktop_agent.desktop.vision.ocr_engine import OCREngine
from desktop_agent.desktop.vision.ocr_backends.base import (
    OCRResult,
    BaseOCRBackend,
)
from desktop_agent.desktop.vision.vision_pipeline import VisionPipeline
from desktop_agent.desktop.vision.vision_validator import VisionValidator
from desktop_agent.desktop.vision.vision_context import VisionContext


class StubOCRBackend(BaseOCRBackend):
    """Deterministic OCR backend so the pipeline runs without Tesseract."""

    def recognize(self, image: np.ndarray) -> OCRResult:
        return OCRResult(
            text="MYRAA",
            confidence=0.95,
            words=[],
            lines=[],
        )


def _synthetic_frame(width=320, height=200):
    """Deterministic BGR frame with a few solid blocks."""

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # White block in the header region
    frame[20:60, 30:150] = (255, 255, 255)
    # Red block (content region)
    frame[80:140, 40:200] = (0, 0, 255)
    return frame


class TestVisionPipeline:

    def test_process_returns_vision_context(self):
        pipeline = VisionPipeline(
            image_processor=ImageProcessor(),
            ocr_engine=OCREngine(StubOCRBackend()),
        )
        context = pipeline.process(_synthetic_frame())
        assert isinstance(context, VisionContext)
        assert context is not None
        assert context.screen is not None
        assert context.graph is not None
        assert context.tree is not None

    def test_process_without_ocr_is_safe(self):
        """OCR is optional in the current contract (VisionManager passes None)."""
        pipeline = VisionPipeline(
            image_processor=ImageProcessor(),
            ocr_engine=None,
        )
        context = pipeline.process(_synthetic_frame())
        assert context is not None
        assert context.node_count >= 0

    def test_process_reports_frame_dimensions(self):
        pipeline = VisionPipeline(
            image_processor=ImageProcessor(),
            ocr_engine=None,
        )
        context = pipeline.process(_synthetic_frame(width=640, height=480))
        assert context.width == 640
        assert context.height == 480


class TestVisionValidator:

    def test_validator_accepts_backend_and_builds_pipeline(self):
        """Legacy entry point: VisionValidator(ocr_backend) must construct
        the real VisionPipeline instead of raising TypeError."""
        validator = VisionValidator(ocr_backend=StubOCRBackend())
        assert validator.pipeline is not None
        # OCREngine wraps the backend
        assert validator.pipeline.ocr is not None

    def test_validator_validate_returns_context(self):
        validator = VisionValidator(ocr_backend=StubOCRBackend())
        context = validator.validate(_synthetic_frame())
        assert isinstance(context, VisionContext)

    def test_validator_without_ocr(self):
        validator = VisionValidator()
        context = validator.validate(_synthetic_frame())
        assert isinstance(context, VisionContext)
