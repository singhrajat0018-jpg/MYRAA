"""
Image processor tests (Part 4-6 restoration).

Previously a module-level script that CAPTURED THE LIVE SCREEN and WROTE
11 PNG files (gray.png, blur.png, ...) into the repo at import time — this
is exactly why `adaptive.png`, `binary.png`, `crop.png`, `denoise.png`, ...
appeared as untracked modifications in git status.

Now a proper pytest module over deterministic in-memory frames. No live
capture, no filesystem writes, no global state.
"""

from __future__ import annotations

import numpy as np
import pytest

from desktop_agent.desktop.vision.image_processor import ImageProcessor


def _frame(width=320, height=200):
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[20:60, 30:150] = (255, 255, 255)  # white block
    img[60:140, 40:200] = (0, 0, 255)     # red block
    return img


class TestImageProcessor:

    def test_grayscale(self):
        proc = ImageProcessor()
        gray = proc.grayscale(_frame())
        assert len(gray.shape) == 2
        assert gray.dtype == np.uint8

    def test_resize(self):
        proc = ImageProcessor()
        out = proc.resize(_frame(), 160, 100)
        assert out.shape == (100, 160, 3)

    def test_scale(self):
        proc = ImageProcessor()
        out = proc.scale(_frame(), 0.5)
        assert out.shape[:2] == (100, 160)

    def test_crop(self):
        proc = ImageProcessor()
        out = proc.crop(_frame(), 30, 30, 100, 80)
        assert out.shape[:2] == (80, 100)

    def test_rotate(self):
        proc = ImageProcessor()
        out = proc.rotate(_frame(), 15)
        assert out.shape == (200, 320, 3)

    def test_flip_horizontal(self):
        proc = ImageProcessor()
        src = _frame()
        out = proc.flip_horizontal(src)
        assert out.shape == src.shape

    def test_flip_vertical(self):
        proc = ImageProcessor()
        src = _frame()
        out = proc.flip_vertical(src)
        assert out.shape == src.shape

    def test_gaussian_blur(self):
        proc = ImageProcessor()
        out = proc.gaussian_blur(_frame())
        assert out.shape == (200, 320, 3)

    def test_median_blur(self):
        proc = ImageProcessor()
        out = proc.median_blur(_frame())
        assert out.shape == (200, 320, 3)

    def test_sharpen(self):
        proc = ImageProcessor()
        out = proc.sharpen(_frame())
        assert out.shape == (200, 320, 3)

    def test_denoise(self):
        proc = ImageProcessor()
        out = proc.denoise(_frame())
        assert out.shape == (200, 320, 3)

    def test_threshold(self):
        proc = ImageProcessor()
        out = proc.threshold(_frame())
        assert len(out.shape) == 2  # binary result

    def test_adaptive_threshold(self):
        proc = ImageProcessor()
        out = proc.adaptive_threshold(_frame())
        assert len(out.shape) == 2

    def test_otsu_threshold(self):
        proc = ImageProcessor()
        out = proc.otsu_threshold(_frame())
        assert len(out.shape) == 2

    def test_all_ops_preserve_dtype(self):
        proc = ImageProcessor()
        src = _frame()
        for op in (
            proc.grayscale,
            proc.threshold,
            proc.adaptive_threshold,
            proc.otsu_threshold,
        ):
            assert op(src).dtype == np.uint8
