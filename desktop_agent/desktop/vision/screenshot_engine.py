"""
MYRAA Desktop Control V3

Screenshot Engine

Responsibilities
----------------
- Full screen capture
- Region capture
- Return PIL Image
- Save screenshots
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

import mss
from PIL import Image


@dataclass
class ScreenshotResult:
    image: Image.Image
    width: int
    height: int


class ScreenshotEngine:

    def __init__(self):

        self.sct = mss.mss()

    # -------------------------------------------------
    # INTERNAL
    # -------------------------------------------------

    def _grab(self, monitor):

        shot = self.sct.grab(monitor)

        image = Image.frombytes(
            "RGB",
            shot.size,
            shot.rgb,
        )

        return ScreenshotResult(
            image=image,
            width=image.width,
            height=image.height,
        )

    # -------------------------------------------------
    # FULL SCREEN
    # -------------------------------------------------

    def capture_screen(self):

        return self._grab(
            self.sct.monitors[0]
        )

    # -------------------------------------------------
    # REGION
    # -------------------------------------------------

    def capture_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
    ):

        monitor = {
            "left": left,
            "top": top,
            "width": width,
            "height": height,
        }

        return self._grab(monitor)

    # -------------------------------------------------
    # SAVE
    # -------------------------------------------------

    def save(
        self,
        result: ScreenshotResult,
        path: str | Path,
    ):

        path = Path(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result.image.save(path)

        return path

    # -------------------------------------------------
    # TIMESTAMP
    # -------------------------------------------------

    def save_timestamped(
        self,
        result: ScreenshotResult,
        folder: str | Path = "screenshots",
    ):

        folder = Path(folder)

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = datetime.now().strftime(
            "%Y%m%d_%H%M%S.png"
        )

        path = folder / filename

        result.image.save(path)

        return path

        # -------------------------------------------------
    # MONITORS
    # -------------------------------------------------

    def monitor_count(self) -> int:
        """
        Returns the number of physical monitors.
        """
        return len(self.sct.monitors) - 1

    def monitor_info(self):

        monitors = []

        for index, monitor in enumerate(self.sct.monitors[1:], start=1):

            monitors.append(
                {
                    "index": index,
                    "left": monitor["left"],
                    "top": monitor["top"],
                    "width": monitor["width"],
                    "height": monitor["height"],
                }
            )

        return monitors

    def capture_monitor(
        self,
        index: int,
    ):

        if index < 1 or index >= len(self.sct.monitors):
            raise ValueError(f"Invalid monitor index: {index}")

        return self._grab(
            self.sct.monitors[index]
        )

    # -------------------------------------------------
    # ACTIVE WINDOW
    # -------------------------------------------------

    def capture_active_window(self):

        import pygetwindow as gw

        window = gw.getActiveWindow()

        if window is None:
            raise RuntimeError("No active window found.")

        if window.width <= 0 or window.height <= 0:
            raise RuntimeError("Active window is minimized.")

        monitor = {
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height,
        }

        return self._grab(monitor)

    # -------------------------------------------------
    # IMAGE CONVERSION
    # -------------------------------------------------

    def to_numpy(
        self,
        result: ScreenshotResult,
    ):

        import numpy as np

        return np.array(result.image)

    def to_opencv(
        self,
        result: ScreenshotResult,
    ):

        import cv2

        image = self.to_numpy(result)

        return cv2.cvtColor(
            image,
            cv2.COLOR_RGB2BGR,
        )

    # -------------------------------------------------
    # RAW BYTES
    # -------------------------------------------------

    def to_bytes(
        self,
        result: ScreenshotResult,
        format: str = "PNG",
    ):

        from io import BytesIO

        buffer = BytesIO()

        result.image.save(
            buffer,
            format=format,
        )

        return buffer.getvalue()

        # -------------------------------------------------
    # VALIDATION
    # -------------------------------------------------

    def validate_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
    ) -> bool:

        if width <= 0 or height <= 0:
            return False

        return True

    def safe_capture_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
    ):

        if not self.validate_region(left, top, width, height):
            raise ValueError("Invalid capture region.")

        return self.capture_region(
            left,
            top,
            width,
            height,
        )

    # -------------------------------------------------
    # IMAGE INFORMATION
    # -------------------------------------------------

    def image_size(
        self,
        result: ScreenshotResult,
    ):

        return (
            result.width,
            result.height,
        )

    def resolution(
        self,
        result: ScreenshotResult,
    ):

        return f"{result.width}x{result.height}"

    # -------------------------------------------------
    # IMAGE UTILITIES
    # -------------------------------------------------

    def crop(
        self,
        result: ScreenshotResult,
        left: int,
        top: int,
        right: int,
        bottom: int,
    ):

        image = result.image.crop(
            (
                left,
                top,
                right,
                bottom,
            )
        )

        return ScreenshotResult(
            image=image,
            width=image.width,
            height=image.height,
        )

    def resize(
        self,
        result: ScreenshotResult,
        width: int,
        height: int,
    ):

        image = result.image.resize(
            (
                width,
                height,
            )
        )

        return ScreenshotResult(
            image=image,
            width=image.width,
            height=image.height,
        )

    # -------------------------------------------------
    # PLANNER SUPPORT
    # -------------------------------------------------

    def capture_for_ocr(self):

        """
        Returns a NumPy image ready for OCR.
        """

        result = self.capture_screen()

        return self.to_numpy(result)

    def capture_for_opencv(self):

        """
        Returns OpenCV BGR image.
        """

        result = self.capture_screen()

        return self.to_opencv(result)

    # -------------------------------------------------
    # CLEANUP
    # -------------------------------------------------

    def close(self):

        self.sct.close()

    def __enter__(self):

        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):

        self.close()