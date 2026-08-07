"""
MYRAA Desktop Control V3

OCR Engine
"""

from __future__ import annotations

import numpy as np

from .image_processor import ImageProcessor
from .ocr_backends.base import (
    BaseOCRBackend,
    OCRResult,
)


class OCREngine:

    def __init__(
        self,
        backend: BaseOCRBackend,
    ):

        self.backend = backend

        self.processor = ImageProcessor()

    # -------------------------------------------------
    # INTERNAL
    # -------------------------------------------------

    def preprocess(
        self,
        image: np.ndarray,
    ) -> np.ndarray:

        image = self.processor.grayscale(image)

        image = self.processor.denoise(image)

        image = self.processor.otsu_threshold(image)

        return image

    # -------------------------------------------------
    # OCR
    # -------------------------------------------------

    def recognize(
        self,
        image: np.ndarray,
        preprocess: bool = True,
    ) -> OCRResult:

        if preprocess:

            image = self.preprocess(image)

        return self.backend.recognize(image)


    # -------------------------------------------------
    # REGION OCR
    # -------------------------------------------------

    def recognize_region(
        self,
        image: np.ndarray,
        x: int,
        y: int,
        width: int,
        height: int,
        preprocess: bool = True,
    ) -> OCRResult:

        region = image[
            y:y + height,
            x:x + width,
        ]

        return self.recognize(
            region,
            preprocess=preprocess,
        )


    # -------------------------------------------------
    # MULTI REGION OCR
    # -------------------------------------------------

    def recognize_regions(
        self,
        image: np.ndarray,
        regions: list[tuple[int, int, int, int]],
        preprocess: bool = True,
    ) -> list[OCRResult]:

        results = []

        for x, y, w, h in regions:

            results.append(

                self.recognize_region(
                    image,
                    x,
                    y,
                    w,
                    h,
                    preprocess,
                )

            )

        return results

    # -------------------------------------------------
    # VALIDATION
    # -------------------------------------------------

    @staticmethod
    def is_empty(
        image: np.ndarray,
    ) -> bool:

        return image.size == 0

    # -------------------------------------------------
    # SAFE OCR
    # -------------------------------------------------

    def safe_recognize(
        self,
        image: np.ndarray,
        preprocess: bool = True,
    ) -> OCRResult:

        if self.is_empty(image):

            return OCRResult(
                text="",
                confidence=0.0,
                words=[],
                lines=[],
            )

        return self.recognize(
            image,
            preprocess,
        )

    # -------------------------------------------------
    # FILTER
    # -------------------------------------------------

    def filter_confidence(
        self,
        result: OCRResult,
        minimum: float = 50.0,
    ) -> OCRResult:

        words = [

            word

            for word in result.words

            if word.confidence >= minimum

        ]

        return OCRResult(

            text=" ".join(
                word.text
                for word in words
            ),

            confidence=(
                sum(
                    word.confidence
                    for word in words
                )
                / len(words)
                if words
                else 0.0
            ),

            words=words,

            lines=[],
        )

    # -------------------------------------------------
    # TEXT
    # -------------------------------------------------

    def extract_text(
        self,
        image: np.ndarray,
    ) -> str:

        return self.recognize(image).text