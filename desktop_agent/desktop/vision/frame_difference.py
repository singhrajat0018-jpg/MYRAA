
"""
MYRAA Desktop Control V3

Frame Difference Engine
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

@dataclass
class ChangedRegion:
    x: int
    y: int
    width: int
    height: int
    area: float

@dataclass
class DifferenceResult:
    changed: bool
    score: float
    threshold: float
    regions: list[ChangedRegion]


class FrameDifference:

    def __init__(
        self,
        threshold: float = 0.5,
        min_area: int = 1500,
        pixel_threshold: int = 35,
        debug: bool = False,
    ):
        self.threshold = threshold
        self.min_area = min_area
        self.pixel_threshold = pixel_threshold
        self.debug = debug 
    # -------------------------------------------------
    # INTERNAL
    # -------------------------------------------------

    def _prepare(
        self,
        image: np.ndarray,
    ) -> np.ndarray:

        if len(image.shape) == 3:

            image = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2GRAY,
            )

        return image

    # -------------------------------------------------
    # INTERNAL ANALYSIS
    # -------------------------------------------------

    def _analyze(
        self,
        previous: np.ndarray,
        current: np.ndarray,
        
    ) -> tuple[float, np.ndarray, list[ChangedRegion]]:

        previous = self._prepare(previous)
        current = self._prepare(current)

        if previous.shape != current.shape:
            raise ValueError("Frame sizes do not match.")

        diff = cv2.absdiff(previous, current)

        changed_pixels = np.count_nonzero(diff)
        total_pixels = diff.size

        score = round(
            float((changed_pixels / total_pixels) * 100),
            3,
        )

        _, mask = cv2.threshold(
            diff,
            self.pixel_threshold,
            255,
            cv2.THRESH_BINARY,
        )       

        mask = self.clean_mask(mask)

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        
        regions = []

        for contour in contours:

            area = cv2.contourArea(contour)

            if area < self.min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            regions.append(
                ChangedRegion(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    area=area,
                )
            )
        if self.debug:
                    print(f"Contours: {len(contours)}")
                    cv2.imwrite("debug_mask.png", mask)
        return score, mask, regions  
          

    # -------------------------------------------------
    # COMPARISON
    # -------------------------------------------------

    def compare(
        self,
        previous: np.ndarray,
        current: np.ndarray,
    ) -> DifferenceResult:

        score, _, regions = self._analyze(
            previous,
            current,
            
        )

        return DifferenceResult(
            changed=(
                score >= self.threshold
                or len(regions) > 0
            ),
            score=score,
            threshold=self.threshold,
            regions=regions,
        )     

      

    # -------------------------------------------------
    # CLEAN MASK
    # -------------------------------------------------

    def clean_mask(
        self,
        mask: np.ndarray,
    ) -> np.ndarray:

        kernel = np.ones(
            (3, 3),
            np.uint8,
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            kernel,
        )

        mask = cv2.dilate(
            mask,
            kernel,
            iterations=2,
        )

        return mask

    # -------------------------------------------------
    # CHANGED REGIONS
    # -------------------------------------------------

    def changed_regions(
        self,
        previous: np.ndarray,
        current: np.ndarray,
    ) -> list[ChangedRegion]:

        _, _, regions = self._analyze(
            previous,
            current,
           
        )

        return regions

    # -------------------------------------------------
    # DEBUG
    # -------------------------------------------------

    def draw_regions(
        self,
        image: np.ndarray,
        regions: list[ChangedRegion],
    ) -> np.ndarray:

        debug = image.copy()

        for region in regions:

            cv2.rectangle(
                debug,
                (region.x, region.y),
                (
                    region.x + region.width,
                    region.y + region.height,
                ),
                (0, 255, 0),
                2,
            )

        return debug

    def difference_mask(
        self,
        previous: np.ndarray,
        current: np.ndarray,
    ) -> np.ndarray:

        _, mask, _ = self._analyze(
            previous,
            current,
        )

        return mask   