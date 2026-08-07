"""
MYRAA Desktop Control V3

Tesseract OCR Backend
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import pytesseract

from .base import (
    BaseOCRBackend,
    OCRLine,
    OCRResult,
    OCRWord,
)


from pathlib import Path
import shutil
import pytesseract


class TesseractBackend(BaseOCRBackend):

    def __init__(
        self,
        language: str = "eng",
        config: str = "--oem 3 --psm 6",
        executable: str | None = None,
    ):

        self.language = language
        self.config = config

        if executable is not None:

            executable = Path(executable)

            if not executable.exists():
                raise FileNotFoundError(executable)

            pytesseract.pytesseract.tesseract_cmd = str(executable)

        else:

            default_locations = [

                shutil.which("tesseract"),

                r"C:\Program Files\Tesseract-OCR\tesseract.exe",

                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",

            ]

            for path in default_locations:

                if path and Path(path).exists():

                    pytesseract.pytesseract.tesseract_cmd = str(path)

                    break

            else:

                raise RuntimeError(
                    "Tesseract executable not found."
                )
    # -------------------------------------------------
    # INTERNAL
    # -------------------------------------------------

    @staticmethod
    def _safe_confidence(value: str) -> float:

        try:

            confidence = float(value)

            if confidence < 0:
                return 0.0

            return confidence

        except Exception:

            return 0.0

    # -------------------------------------------------
    # OCR
    # -------------------------------------------------

    def recognize(
        self,
        image: np.ndarray,
    ) -> OCRResult:

        data = pytesseract.image_to_data(
            image,
            lang=self.language,
            config=self.config,
            output_type=pytesseract.Output.DICT,
        )

        words: list[OCRWord] = []

        grouped_lines: dict[tuple[int, int, int], list[OCRWord]] = defaultdict(list)

        total_conf = 0.0

        for i in range(len(data["text"])):

            text = data["text"][i].strip()

            if not text:
                continue

            confidence = self._safe_confidence(
                data["conf"][i]
            )

            word = OCRWord(
                text=text,
                confidence=confidence,
                x=int(data["left"][i]),
                y=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
            )

            words.append(word)

            total_conf += confidence

            key = (
                int(data["block_num"][i]),
                int(data["par_num"][i]),
                int(data["line_num"][i]),
            )

            grouped_lines[key].append(word)

        lines: list[OCRLine] = []

        for line_words in grouped_lines.values():

            line_text = " ".join(
                w.text
                for w in line_words
            )

            line_conf = (
                sum(w.confidence for w in line_words)
                / len(line_words)
            )

            lines.append(
                OCRLine(
                    text=line_text,
                    confidence=line_conf,
                    words=line_words,
                )
            )

        full_text = "\n".join(
            line.text
            for line in lines
        )

        average_conf = (
            total_conf / len(words)
            if words
            else 0.0
        )

        return OCRResult(
            text=full_text,
            confidence=average_conf,
            words=words,
            lines=lines,
        )