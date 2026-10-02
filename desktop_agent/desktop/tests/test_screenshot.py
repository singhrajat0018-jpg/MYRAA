"""
Screenshot engine tests (Part 4-6 restoration).

Previously a module-level script that CAPTURED THE LIVE SCREEN and SAVED
timestamped PNGs at import time. Now a proper pytest module covering the
ScreenshotEngine contract using in-memory PIL images — no live capture,
no filesystem writes.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from desktop_agent.desktop.vision.screenshot_engine import (
    ScreenshotEngine,
    ScreenshotResult,
)


def _make_result(width=640, height=400):
    image = Image.new("RGB", (width, height), color=(10, 20, 30))
    return ScreenshotResult(image=image, width=width, height=height)


class TestScreenshotEngine:

    def test_engine_constructs(self):
        engine = ScreenshotEngine()
        engine.close()

    def test_monitor_count_returns_int(self):
        engine = ScreenshotEngine()
        try:
            assert isinstance(engine.monitor_count(), int)
            assert engine.monitor_count() >= 0
        finally:
            engine.close()

    def test_capture_region_validates(self):
        engine = ScreenshotEngine()
        try:
            # validate_region is pure logic — no live capture
            assert engine.validate_region(0, 0, 100, 100) is True
            assert engine.validate_region(0, 0, 0, 100) is False
            assert engine.validate_region(0, 0, 100, 0) is False
            with pytest.raises(ValueError):
                engine.safe_capture_region(0, 0, 0, 100)
        finally:
            engine.close()

    def test_crop_returns_new_result(self):
        engine = ScreenshotEngine()
        try:
            result = _make_result(width=640, height=400)
            cropped = engine.crop(result, 10, 20, 110, 120)
            assert cropped.width == 100
            assert cropped.height == 100
            assert cropped.image.size == (100, 100)
        finally:
            engine.close()

    def test_resize_changes_dimensions(self):
        engine = ScreenshotEngine()
        try:
            result = _make_result(width=640, height=400)
            resized = engine.resize(result, 320, 200)
            assert resized.width == 320
            assert resized.height == 200
            assert resized.image.size == (320, 200)
        finally:
            engine.close()

    def test_image_size_and_resolution(self):
        engine = ScreenshotEngine()
        try:
            result = _make_result(width=640, height=400)
            assert engine.image_size(result) == (640, 400)
            assert engine.resolution(result) == "640x400"
        finally:
            engine.close()

    def test_to_bytes_produces_png(self):
        engine = ScreenshotEngine()
        try:
            result = _make_result()
            data = engine.to_bytes(result, format="PNG")
            assert isinstance(data, bytes)
            assert data[:8] == b"\x89PNG\r\n\x1a\n"
        finally:
            engine.close()

    def test_to_numpy_returns_array(self):
        import numpy as np

        engine = ScreenshotEngine()
        try:
            result = _make_result()
            arr = engine.to_numpy(result)
            assert isinstance(arr, np.ndarray)
            assert arr.shape[:2] == (400, 640)
        finally:
            engine.close()

    def test_save_writes_to_path(self):
        engine = ScreenshotEngine()
        try:
            with tempfile.TemporaryDirectory() as td:
                result = _make_result()
                path = Path(td) / "shot.png"
                saved = engine.save(result, path)
                assert saved == path
                assert path.exists()
        finally:
            engine.close()
