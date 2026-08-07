"""
MYRAA Desktop Control V3

OCR Engine Smoke Test
"""

from __future__ import annotations

from pathlib import Path

import cv2
import pytesseract

from desktop_agent.desktop.vision.screenshot_engine import ScreenshotEngine
from desktop_agent.desktop.vision.ocr_engine import OCREngine
from desktop_agent.desktop.vision.ocr_backends.tesseract_backend import (
    TesseractBackend,
)


TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def main():

    print("=" * 70)
    print("MYRAA OCR ENGINE TEST")
    print("=" * 70)

    # ----------------------------------------------------------
    # Verify executable
    # ----------------------------------------------------------

    if not Path(TESSERACT_PATH).exists():
        raise FileNotFoundError(
            f"Tesseract executable not found:\n{TESSERACT_PATH}"
        )

    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

    print("Tesseract Path")
    print(pytesseract.pytesseract.tesseract_cmd)

    print()

    print("Version")
    print(pytesseract.get_tesseract_version())

    # ----------------------------------------------------------
    # Initialize OCR
    # ----------------------------------------------------------

    backend = TesseractBackend(
        executable=TESSERACT_PATH
    )

    ocr = OCREngine(backend)

    capture = ScreenshotEngine()

    # ----------------------------------------------------------
    # Capture Screen
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print("Capturing Screen")
    print("=" * 70)

    screenshot = capture.capture_screen()

    image = capture.to_opencv(screenshot)

    cv2.imwrite("ocr_test_screen.png", image)

    print("Resolution :", image.shape)

    # ----------------------------------------------------------
    # OCR
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print("Running OCR")
    print("=" * 70)

    result = ocr.recognize(image)

    print()

    print("Confidence :", round(result.confidence, 2))
    print("Words      :", len(result.words))
    print("Lines      :", len(result.lines))

    print()

    print("=" * 70)
    print("TEXT")
    print("=" * 70)

    print(result.text)

    print()

    print("=" * 70)
    print("FIRST 20 WORDS")
    print("=" * 70)

    for word in result.words[:20]:

        print(
            f"{word.text:<20}"
            f"{word.confidence:>8.2f}"
        )

    print()

    print("=" * 70)
    print("OCR TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()