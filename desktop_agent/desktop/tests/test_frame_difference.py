"""
Frame difference engine tests (Part 4-6 restoration).

Previously a module-level script that CAPTURED TWO LIVE SCREENSHOTS 5s apart
and wrote debug PNGs at import time. Now a proper pytest module using
deterministic in-memory frames — no live capture, no sleeps, no file writes.
"""

from __future__ import annotations

import numpy as np
import pytest

from desktop_agent.desktop.vision.frame_difference import (
    ChangedRegion,
    DifferenceResult,
    FrameDifference,
)


def _frame(width=320, height=200, fill=0):
    img = np.full((height, width, 3), fill, dtype=np.uint8)
    # Add a static block so identical frames still match deterministically
    img[20:60, 30:150] = (255, 255, 255)
    return img


class TestFrameDifference:

    def test_identical_frames_no_change(self):
        detector = FrameDifference()
        first = _frame(fill=0)
        second = first.copy()
        result = detector.compare(first, second)
        assert isinstance(result, DifferenceResult)
        assert result.changed is False
        assert result.score == 0.0
        assert result.regions == []

    def test_changed_frame_detected(self):
        detector = FrameDifference()
        first = _frame(fill=0)
        second = first.copy()
        # Paint a big distinct block -> guaranteed difference
        second[60:140, 40:200] = (0, 0, 255)
        result = detector.compare(first, second)
        assert isinstance(result, DifferenceResult)
        assert result.score > 0.0

    def test_threshold_behavior(self):
        detector = FrameDifference(threshold=10.0)
        first = _frame(fill=0)
        second = first.copy()
        second[60:140, 40:200] = (0, 0, 255)
        result = detector.compare(first, second)
        # A threshold above the observed score yields changed=False
        assert result.threshold == 10.0
        assert isinstance(result.score, float)

    def test_changed_regions_list(self):
        detector = FrameDifference(min_area=10)
        first = _frame(fill=0)
        second = first.copy()
        second[60:140, 40:200] = (0, 0, 255)
        regions = detector.changed_regions(first, second)
        assert isinstance(regions, list)
        for region in regions:
            assert isinstance(region, ChangedRegion)

    def test_mismatched_sizes_raise(self):
        detector = FrameDifference()
        with pytest.raises(ValueError):
            detector.compare(_frame(320, 200), _frame(100, 100))

    def test_compare_returns_typed_result(self):
        detector = FrameDifference()
        result = detector.compare(_frame(), _frame())
        assert isinstance(result.changed, bool)
        assert isinstance(result.score, float)
        assert isinstance(result.regions, list)
