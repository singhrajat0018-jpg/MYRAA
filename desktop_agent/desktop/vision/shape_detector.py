"""
MYRAA Desktop Control V3

Shape Detection Engine
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .ui_models import BoundingBox


@dataclass(slots=True)
class ShapeCandidate:
    bounds: BoundingBox
    contour: np.ndarray
    confidence: float
    shape: str


class ShapeDetector:

    def __init__(
        self,
        min_area: int = 500,
    ):
        self.min_area = min_area

    def detect(
        self,
        image: np.ndarray,
    ) -> list[ShapeCandidate]:

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

        blurred = cv2.GaussianBlur(
            gray,
            (5, 5),
            0,
        )

        edges = cv2.Canny(
            blurred,
            50,
            150,
        )

        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        results: list[ShapeCandidate] = []

        for contour in contours:

            area = cv2.contourArea(contour)

            if area < self.min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            polygon = cv2.approxPolyDP(
                contour,
                0.03 * cv2.arcLength(contour, True),
                True,
            )

            if len(polygon) == 4:
                shape = "rectangle"
            else:
                shape = "unknown"

            results.append(
                ShapeCandidate(
                    bounds=BoundingBox(
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                    ),
                    contour=contour,
                    confidence=min(1.0, area / 5000),
                    shape=shape,
                )
            )

        return results