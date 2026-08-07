"""
MYRAA Desktop Control V3

Base OCR Backend
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class OCRWord:
    text: str
    confidence: float
    x: int
    y: int
    width: int
    height: int


@dataclass(slots=True)
class OCRLine:
    text: str
    confidence: float
    words: list[OCRWord]


@dataclass(slots=True)
class OCRResult:
    text: str
    confidence: float
    words: list[OCRWord]
    lines: list[OCRLine]


class BaseOCRBackend(ABC):

    @abstractmethod
    def recognize(
        self,
        image: np.ndarray,
    ) -> OCRResult:
        """
        Perform OCR on image.
        """
        raise NotImplementedError