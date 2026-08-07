"""
MYRAA Production UI Detector Test
"""

from pathlib import Path

import cv2

from desktop_agent.desktop.vision.ocr_backends.tesseract_backend import (
    TesseractBackend,
)
from desktop_agent.desktop.vision.ocr_engine import OCREngine
from desktop_agent.desktop.vision.screenshot_engine import ScreenshotEngine
from desktop_agent.desktop.vision.ui_detector import UIDetector


def main():

    print("=" * 70)
    print("MYRAA UI DETECTOR TEST")
    print("=" * 70)

    # --------------------------------------------------
    # Screenshot
    # --------------------------------------------------

    screenshot = ScreenshotEngine()

    image = screenshot.capture_for_opencv()

    # --------------------------------------------------
    # OCR + Detector
    # --------------------------------------------------

    backend = TesseractBackend()

    ocr = OCREngine(backend)

    detector = UIDetector(ocr)

    elements = detector.detect(image)

    print(f"\nDetected Elements : {len(elements)}")

    print("\n" + "=" * 70)
    print("UI ELEMENTS")
    print("=" * 70)

    for element in elements:

        print(

            f"{element.type.value:<10}",

            f"{element.text:<30}",

            f"{element.confidence:.2f}",

        )

    # --------------------------------------------------
    # Draw UI Elements
    # --------------------------------------------------

    output = image.copy()

    for element in elements:

        cv2.rectangle(

            output,

            (

                element.bounds.x,

                element.bounds.y,

            ),

            (

                element.bounds.right,

                element.bounds.bottom,

            ),

            (0, 255, 0),

            2,

        )

    # --------------------------------------------------
    # Shape Detector
    # --------------------------------------------------

    print("\n" + "=" * 70)
    print("SHAPE DETECTOR")
    print("=" * 70)

    shapes = detector.detect_shapes(image)

    print(f"Shapes Found : {len(shapes)}")

    for shape in shapes:

        print(

            shape.shape,

            f"{shape.confidence:.2f}",

        )

        cv2.rectangle(

            output,

            (

                shape.bounds.x,

                shape.bounds.y,

            ),

            (

                shape.bounds.right,

                shape.bounds.bottom,

            ),

            (255, 0, 0),

            2,

        )

    # --------------------------------------------------
    # Save
    # --------------------------------------------------

    path = Path("ui_detector_result.png")

    cv2.imwrite(

        str(path),

        output,

    )

    print("\nSaved:", path.resolve())

    screenshot.close()


if __name__ == "__main__":

    main()