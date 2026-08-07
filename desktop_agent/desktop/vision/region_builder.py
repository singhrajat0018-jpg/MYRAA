"""
MYRAA Desktop Control V3

OCR Region Builder
"""

from __future__ import annotations

from collections.abc import Sequence

from .ocr_backends.base import OCRWord
from .text_region import TextRegion
from .ui_models import BoundingBox


class RegionBuilder:

    """
    Converts OCR words into merged text regions.
    """

    def __init__(

        self,

        horizontal_gap: int = 24,

        vertical_gap: int = 14,

    ):

        self.horizontal_gap = horizontal_gap

        self.vertical_gap = vertical_gap

    def build(

        self,

        words: Sequence[OCRWord],

    ) -> list[TextRegion]:

        if not words:

            return []

        words = sorted(

            words,

            key=lambda w: (

                w.y,

                w.x,

            ),

        )

        groups: list[list[OCRWord]] = []

        current = [words[0]]

        for word in words[1:]:

            previous = current[-1]

            if self._mergeable(previous, word):

                current.append(word)

            else:

                groups.append(current)

                current = [word]

        groups.append(current)

        regions = [

            self._create_region(group)

            for group in groups

        ]

        return self.merge_regions(regions)      

    def _mergeable(

       self,

       left: OCRWord,
     
       right: OCRWord,

    ) -> bool:

       if abs(

          left.y -

          right.y

        ) > self.vertical_gap:

        return False

       gap = right.x - (

            left.x +

          left.width

      )

       return 0 <= gap <= self.horizontal_gap

    def _create_region(

        self,

        words: list[OCRWord],

    ) -> TextRegion:

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

        confidence = (

            sum(

                word.confidence

                for word in words

            )

            /

            len(words)

        )

        return TextRegion(

            text=" ".join(

                word.text

                for word in words

            ),

            confidence=confidence,

            bounds=BoundingBox(

                x=left,

                y=top,

                width=right-left,

                height=bottom-top,

            ),

            words=[

                word.text

                for word in words

            ],

        )

    # ---------------------------------------------------------
    # REGION MERGING
    # ---------------------------------------------------------

    def merge_regions(
        self,
        regions: list[TextRegion],
    ) -> list[TextRegion]:

        if not regions:
            return []

        merged: list[TextRegion] = []

        current = regions[0]

        for region in regions[1:]:

            if self._regions_can_merge(current, region):

                current = self._merge_two_regions(
                    current,
                    region,
                )

            else:

                merged.append(current)

                current = region

        merged.append(current)

        return merged

    def _regions_can_merge(
        self,
        first: TextRegion,
        second: TextRegion,
    ) -> bool:

        vertical_gap = abs(
            first.bounds.y -
            second.bounds.y
        )

        if vertical_gap > self.vertical_gap:
            return False

        horizontal_gap = (
            second.bounds.x -
            first.bounds.right
        )

        return 0 <= horizontal_gap <= self.horizontal_gap

    def _merge_two_regions(
        self,
        first: TextRegion,
        second: TextRegion,
    ) -> TextRegion:

        left = min(
            first.bounds.x,
            second.bounds.x,
        )

        top = min(
            first.bounds.y,
            second.bounds.y,
        )

        right = max(
            first.bounds.right,
            second.bounds.right,
        )

        bottom = max(
            first.bounds.bottom,
            second.bounds.bottom,
        )

        text = (
            first.text +
            " " +
            second.text
        )

        confidence = (
            first.confidence +
            second.confidence
        ) / 2

        return TextRegion(

            text=text.strip(),

            confidence=confidence,

            bounds=BoundingBox(

                x=left,

                y=top,

                width=right - left,

                height=bottom - top,

            ),

            words=first.words + second.words,

        )