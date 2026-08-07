"""
MYRAA Desktop Control V3

Production UI Detector
Part 1A
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence
from .region_builder import RegionBuilder
from .text_region import TextRegion
from .shape_detector import ShapeDetector
import math

import cv2
import numpy as np

from .ocr_engine import OCREngine
from .ocr_backends.base import OCRResult, OCRWord
from .ui_models import (
    BoundingBox,
    UIElement,
    UIElementType,
)


# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------


@dataclass(slots=True)
class DetectorConfig:
    """
    Configuration for UI detection.
    """

    minimum_confidence: float = 25.0

    minimum_word_length: int = 2

    merge_x_gap: int = 24

    merge_y_gap: int = 12

    line_height_tolerance: int = 14

    duplicate_iou: float = 0.60

    sort_left_margin: int = 20


# ---------------------------------------------------------
# UI DETECTOR
# ---------------------------------------------------------


class UIDetector:
    """
    Production UI Detector.

    Converts OCR output into semantic UI elements.
    """

    BUTTON_KEYWORDS = {
        "ok",
        "cancel",
        "close",
        "save",
        "submit",
        "send",
        "login",
        "continue",
        "next",
        "finish",
        "apply",
        "install",
        "open",
        "search",
        "browse",
        "download",
    }

    MENU_KEYWORDS = {
        "file",
        "edit",
        "view",
        "help",
        "tools",
        "window",
        "settings",
    }

    def __init__(
        self,
        ocr: OCREngine,
        config: DetectorConfig | None = None,
    ):

        self.ocr = ocr

        self.config = config or DetectorConfig()

        self.region_builder = RegionBuilder()

        self.shape_detector = ShapeDetector()

    # ---------------------------------------------------------
    # PUBLIC
    # ---------------------------------------------------------

    def detect(
        self,
        image: np.ndarray,
    ) -> list[UIElement]:

        result = self.ocr.recognize(image)

        return self.from_ocr(result)

    # ---------------------------------------------------------
    # OCR
    # ---------------------------------------------------------

    def from_ocr(
        self,
        result: OCRResult,
    ) -> list[UIElement]:

        words = self._filtered_words(result)

        words = self._reading_order(words)

        regions = self.region_builder.build(words)

        elements: list[UIElement] = []

        for region in regions:

            ui_type = self._classify(
                region.text
            )

            elements.append(

                UIElement(

                    type=ui_type,

                    text=region.text,

                    confidence=region.confidence,

                    bounds=region.bounds,

                    clickable=self._clickable(
                        ui_type
                    ),

                )

            )

        return self._remove_duplicates(
            elements
        )

    # ---------------------------------------------------------
    # GEOMETRY
    # ---------------------------------------------------------

    @staticmethod
    def _area(
        box: BoundingBox,
    ) -> int:

        return box.width * box.height

    @staticmethod
    def _center(
        box: BoundingBox,
    ) -> tuple[int, int]:

        return (

            box.x + box.width // 2,

            box.y + box.height // 2,

        )

    @staticmethod
    def _distance(
        first: BoundingBox,
        second: BoundingBox,
    ) -> float:

        ax, ay = UIDetector._center(first)

        bx, by = UIDetector._center(second)

        return math.hypot(

            bx - ax,

            by - ay,

        )

    @staticmethod
    def _union(
        first: BoundingBox,
        second: BoundingBox,
    ) -> BoundingBox:

        left = min(

            first.x,

            second.x,

        )

        top = min(

            first.y,

            second.y,

        )

        right = max(

            first.right,

            second.right,

        )

        bottom = max(

            first.bottom,

            second.bottom,

        )

        return BoundingBox(

            x=left,

            y=top,

            width=right - left,

            height=bottom - top,

        )

    @staticmethod
    def _iou(
        first: BoundingBox,
        second: BoundingBox,
    ) -> float:

        x1 = max(

            first.x,

            second.x,

        )

        y1 = max(

            first.y,

            second.y,

        )

        x2 = min(

            first.right,

            second.right,

        )

        y2 = min(

            first.bottom,

            second.bottom,

        )

        if x2 <= x1:

            return 0.0

        if y2 <= y1:

            return 0.0

        intersection = (

            x2 - x1

        ) * (

            y2 - y1

        )

        union = (

            UIDetector._area(first)

            +

            UIDetector._area(second)

            -

            intersection

        )

        if union <= 0:

            return 0.0

        return intersection / union

    @staticmethod
    def _horizontal_gap(
        first: BoundingBox,
        second: BoundingBox,
    ) -> int:

        return second.x - first.right

    @staticmethod
    def _vertical_gap(
        first: BoundingBox,
        second: BoundingBox,
    ) -> int:

        return abs(

            first.y -

            second.y

        )

    @staticmethod
    def _same_line(
        first: BoundingBox,
        second: BoundingBox,
        tolerance: int,
    ) -> bool:

        return (

            abs(

                first.y -

                second.y

            )

            <= tolerance

        )

    @staticmethod
    def _contains(
        outer: BoundingBox,
        inner: BoundingBox,
    ) -> bool:

        return (

            inner.x >= outer.x

            and

            inner.y >= outer.y

            and

            inner.right <= outer.right

            and

            inner.bottom <= outer.bottom

        )

    # ---------------------------------------------------------
    # WORD FILTERING
    # ---------------------------------------------------------

    def _valid_word(
        self,
        word: OCRWord,
    ) -> bool:

        text = word.text.strip()

        if not text:
            return False

        if len(text) < self.config.minimum_word_length:
            return False

        if word.confidence < self.config.minimum_confidence:
            return False

        return True

    def _filtered_words(
        self,
        result: OCRResult,
    ) -> list[OCRWord]:

        words = [

            word

            for word in result.words

            if self._valid_word(word)

        ]

        return words

    # ---------------------------------------------------------
    # SORTING
    # ---------------------------------------------------------

    def _reading_order(
        self,
        words: Sequence[OCRWord],
    ) -> list[OCRWord]:

        if not words:

            return []

        return sorted(

            words,

            key=lambda word: (

                round(

                    word.y /

                    self.config.line_height_tolerance

                ),

                word.x,

            ),

        )

    def _sort_left_to_right(
        self,
        words: Sequence[OCRWord],
    ) -> list[OCRWord]:

        return sorted(

            words,

            key=lambda word: word.x,

        )

    def _sort_top_to_bottom(
        self,
        words: Sequence[OCRWord],
    ) -> list[OCRWord]:

        return sorted(

            words,

            key=lambda word: word.y,

        )

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def _average_confidence(
        words: Sequence[OCRWord],
    ) -> float:

        if not words:

            return 0.0

        return (

            sum(

                word.confidence

                for word in words

            )

            /

            len(words)

        )

    @staticmethod
    def _merge_text(
        words: Sequence[OCRWord],
    ) -> str:

        return " ".join(

            word.text.strip()

            for word in words

            if word.text.strip()

        )

    @staticmethod
    def _merge_bounds(
        words: Sequence[OCRWord],
    ) -> BoundingBox:

        left = min(

            word.x

            for word in words

        )

        top = min(

            word.y

            for word in words

        )

        right = max(

            word.x +

            word.width

            for word in words

        )

        bottom = max(

            word.y +

            word.height

            for word in words

        )

        return BoundingBox(

            x=left,

            y=top,

            width=right - left,

            height=bottom - top,

        )

    def _line_height(
        self,
        words: Sequence[OCRWord],
    ) -> float:

        if not words:

            return 0

        return (

            sum(

                word.height

                for word in words

            )

            /

            len(words)

        )

    # ---------------------------------------------------------
    # WORD MERGING
    # ---------------------------------------------------------

    def _can_merge(
        self,
        left: OCRWord,
        right: OCRWord,
    ) -> bool:

        if not self._same_line(
            BoundingBox(
                left.x,
                left.y,
                left.width,
                left.height,
            ),
            BoundingBox(
                right.x,
                right.y,
                right.width,
                right.height,
            ),
            self.config.line_height_tolerance,
        ):
            return False

        gap = right.x - (left.x + left.width)

        return 0 <= gap <= self.config.merge_x_gap

    def _merge_words(
        self,
        words: Sequence[OCRWord],
    ) -> list[list[OCRWord]]:

        if not words:
            return []

        groups: list[list[OCRWord]] = []

        current: list[OCRWord] = [words[0]]

        for word in words[1:]:

            previous = current[-1]

            if self._can_merge(previous, word):

                current.append(word)

            else:

                groups.append(current)

                current = [word]

        groups.append(current)

        return groups


    # ---------------------------------------------------------
    # CLASSIFICATION
    # ---------------------------------------------------------

    def _classify(
        self,
        text: str,
    ) -> UIElementType:

        value = text.lower().strip()

        if any(
            value.startswith(prefix)
            for prefix in ("http://", "https://", "www.")
        ):
            return UIElementType.LINK

        if value in self.MENU_KEYWORDS:
            return UIElementType.MENU

        if value in self.BUTTON_KEYWORDS:
            return UIElementType.BUTTON

        if value.endswith(":"):
            return UIElementType.LABEL

        return UIElementType.TEXT

    def _clickable(
        self,
        ui_type: UIElementType,
    ) -> bool:

        return ui_type in {
            UIElementType.BUTTON,
            UIElementType.MENU,
            UIElementType.LINK,
        }

    def _group_to_element(
        self,
        words: Sequence[OCRWord],
    ) -> UIElement:

        text = self._merge_text(words)

        bounds = self._merge_bounds(words)

        confidence = self._average_confidence(words)

        ui_type = self._classify(text)

        return UIElement(

            type=ui_type,

            text=text,

            confidence=confidence,

            bounds=bounds,

            clickable=self._clickable(ui_type),

        )

    def _remove_duplicates(
        self,
        elements: Sequence[UIElement],
    ) -> list[UIElement]:

        results: list[UIElement] = []

        for element in sorted(
            elements,
            key=lambda e: e.confidence,
            reverse=True,
        ):

            keep = True

            for existing in results:

                if (
                    self._iou(
                        element.bounds,
                        existing.bounds,
                    )
                    >= self.config.duplicate_iou
                ):

                    keep = False
                    break

            if keep:
                results.append(element)

        return results


    def detect_shapes(
       self,
       image: np.ndarray,
    ):
       return self.shape_detector.detect(image)


    