"""
MYRAA Desktop Vision V3

OCR -> TextRegion Converter
"""

from __future__ import annotations

from typing import List

from .ocr_backends.base import OCRResult
from .text_region import TextRegion
from .ui_models import BoundingBox


class OCRTextRegionConverter:
    """
    Converts OCRResult into TextRegion models.
    """

    def convert(
        self,
        result: OCRResult,
    ) -> List[TextRegion]:

        regions: List[TextRegion] = []

        line_index = 0

        # Convert every OCR line
        for line in result.lines:

            for word in line.words:

                region = TextRegion(

                    text=word.text,

                    confidence=word.confidence,

                    bounds=BoundingBox(
                        x=word.x,
                        y=word.y,
                        width=word.width,
                        height=word.height,
                    ),

                    words=[word.text],

                    line=line_index,

                    paragraph=0,

                    metadata={
                        "source": "ocr",
                    },

                )

                regions.append(region)

            line_index += 1

        return regions

    # -------------------------------------------------

    def convert_words(
        self,
        result: OCRResult,
    ) -> List[TextRegion]:
        """
        Converts OCR words only (ignores line grouping).
        """

        regions: List[TextRegion] = []

        for word in result.words:

            regions.append(

                TextRegion(

                    text=word.text,

                    confidence=word.confidence,

                    bounds=BoundingBox(
                        x=word.x,
                        y=word.y,
                        width=word.width,
                        height=word.height,
                    ),

                    words=[word.text],

                    metadata={
                        "source": "ocr",
                    },

                )

            )

        return regions