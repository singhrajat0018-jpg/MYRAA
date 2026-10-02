"""
MYRAA Vision V3

Vision Validator

Runs the complete vision pipeline and validates every stage against the
real production contract:

    VisionPipeline(image_processor, ocr_engine, ...).process(frame)
        -> VisionContext | None

VisionContext exposes:
    - screen  (SemanticScreen: width / height / nodes)
    - graph   (SpatialGraph)
    - tree    (SemanticTree)
    - node_count / width / height

The old validator drove a phantom ``analyze()`` API with a rich result
object that the current pipeline no longer produces. It was rewritten to
exercise the actual VisionPipeline contract so a broken validator can never
mask a broken pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .vision_pipeline import VisionPipeline
from .image_processor import ImageProcessor
from .ocr_engine import OCREngine


# ==========================================================
# Validation Result
# ==========================================================

@dataclass(slots=True)
class ValidationResult:

    passed: bool

    stage: str

    message: str


# ==========================================================
# Vision Validator
# ==========================================================

class VisionValidator:

    def __init__(
        self,
        ocr_backend=None,
        image_processor=None,
        ocr_engine=None,
        shape_detector=None,
        layout_analyzer=None,
        builder=None,
    ):
        """
        Build the same VisionPipeline the runtime uses. OCR is optional:
        pass an ``ocr_engine`` (OCREngine) directly, or pass a legacy
        ``ocr_backend`` (BaseOCRBackend) which is wrapped into an OCREngine.
        """

        if image_processor is None:
            image_processor = ImageProcessor()

        if ocr_engine is None and ocr_backend is not None:
            ocr_engine = OCREngine(ocr_backend)

        self.pipeline = VisionPipeline(
            image_processor=image_processor,
            ocr_engine=ocr_engine,
            shape_detector=shape_detector,
            layout_analyzer=layout_analyzer,
            builder=builder,
        )

    # ------------------------------------------------------

    def validate(self, frame=None):
        """
        Run the pipeline over ``frame`` (a numpy BGR image) and report each
        stage. If ``frame`` is None a live screenshot is captured first.
        Returns the resulting VisionContext (or None on failure).
        """

        print()
        print("=" * 60)
        print(" MYRAA Vision Validation ")
        print("=" * 60)

        if frame is None:
            from .screenshot_engine import ScreenshotEngine
            with ScreenshotEngine() as capture:
                frame = capture.to_numpy(capture.capture_screen())

        start = time.perf_counter()

        context = self.pipeline.process(frame)

        elapsed = time.perf_counter() - start

        self._check(
            "Frame",
            frame is not None,
        )

        self._check(
            "Vision Context",
            context is not None,
        )

        if context is not None:
            self._check(
                "Semantic Screen",
                context.screen is not None,
            )
            self._check(
                "Spatial Graph",
                context.graph is not None,
            )
            self._check(
                "Semantic Tree",
                context.tree is not None,
            )
            self._check(
                "Semantic Nodes",
                context.node_count > 0,
                str(context.node_count),
            )
            self._check(
                "Resolution",
                context.width > 0 and context.height > 0,
                f"{context.width}x{context.height}",
            )

        print()
        print("-" * 60)

        if context is not None:
            print(f"Semantic Nodes  : {context.node_count}")
            print(f"Resolution      : {context.width} x {context.height}")

        print(f"Execution Time  : {elapsed:.3f} sec")
        print("-" * 60)
        print()
        print("VISION VALIDATION COMPLETED")
        print("=" * 60)

        return context

    # ------------------------------------------------------

    @staticmethod
    def _check(
        stage,
        success,
        details="",
    ):
        status = "PASS" if success else "FAIL"
        line = f"{stage:<22} {status}"
        if details:
            line += f" ({details})"
        print(line)
