"""
MYRAA Vision V3

Vision Validator

Runs the complete vision pipeline and validates every stage.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .vision_pipeline import VisionPipeline
from .ocr_backends.base import BaseOCRBackend


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

        ocr_backend: BaseOCRBackend,

    ):

        self.pipeline = VisionPipeline(

            ocr_backend=ocr_backend,

        )

    # ------------------------------------------------------

    def validate(self):

        print()

        print("=" * 60)

        print(" MYRAA Vision Validation ")

        print("=" * 60)

        start = time.perf_counter()

        result = self.pipeline.analyze()

        elapsed = time.perf_counter() - start

        self._check(

            "Screenshot",

            result.screenshot is not None,

        )

        self._check(

            "OCR",

            result.ocr_result is not None,

            f"{len(result.ocr_result.words)} words",

        )

        self._check(

            "Text Regions",

            len(result.text_regions) > 0,

            str(len(result.text_regions)),

        )

        self._check(

            "Shapes",

            result.shapes is not None,

            str(len(result.shapes)),

        )

        self._check(

            "Layout",

            result.layout is not None,

        )

        self._check(

            "Vision Context",

            result.context is not None,

        )

        self._check(

            "Semantic Nodes",

            result.context.node_count > 0,

            str(result.context.node_count),

        )

        self._check(

            "Spatial Graph",

            result.context.graph is not None,

        )

        self._check(

            "Semantic Tree",

            result.context.tree is not None,

        )

        self._check(

            "Screen Summary",

            result.summary is not None,

        )

        print()

        print("-" * 60)

        print(f"Screen Type     : {result.summary.screen_type.value}")

        print(f"Confidence      : {result.summary.confidence:.2f}")

        print(f"OCR Words       : {len(result.ocr_result.words)}")

        print(f"Text Regions    : {len(result.text_regions)}")

        print(f"Shapes          : {len(result.shapes)}")

        print(f"Semantic Nodes  : {result.context.node_count}")

        print(f"Resolution      : {result.context.width} x {result.context.height}")

        print(f"Execution Time  : {elapsed:.3f} sec")

        print("-" * 60)

        print()

        print("VISION VALIDATION COMPLETED")

        print("=" * 60)

        return result

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