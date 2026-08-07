"""
MYRAA Desktop Control V3

Image Processing Engine
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class ImageProcessor:

    # -------------------------------------------------
    # BASIC
    # -------------------------------------------------

    def grayscale(
        self,
        image: np.ndarray,
    ) -> np.ndarray:

        if len(image.shape) == 2:
            return image

        return cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY,
        )

    def resize(
        self,
        image: np.ndarray,
        width: int,
        height: int,
    ) -> np.ndarray:

        return cv2.resize(
            image,
            (width, height),
            interpolation=cv2.INTER_AREA,
        )

    def scale(
        self,
        image: np.ndarray,
        factor: float,
    ) -> np.ndarray:

        return cv2.resize(
            image,
            None,
            fx=factor,
            fy=factor,
            interpolation=cv2.INTER_AREA,
        )

    # -------------------------------------------------
    # CROP
    # -------------------------------------------------

    def crop(
        self,
        image: np.ndarray,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> np.ndarray:

        return image[
            y:y + height,
            x:x + width,
        ]

    # -------------------------------------------------
    # ROTATION
    # -------------------------------------------------

    def rotate(
        self,
        image: np.ndarray,
        angle: float,
    ) -> np.ndarray:

        h, w = image.shape[:2]

        center = (w // 2, h // 2)

        matrix = cv2.getRotationMatrix2D(
            center,
            angle,
            1.0,
        )

        return cv2.warpAffine(
            image,
            matrix,
            (w, h),
        )

    # -------------------------------------------------
    # FLIP
    # -------------------------------------------------

    def flip_horizontal(
        self,
        image: np.ndarray,
    ) -> np.ndarray:

        return cv2.flip(image, 1)

    def flip_vertical(
        self,
        image: np.ndarray,
    ) -> np.ndarray:

        return cv2.flip(image, 0)

        # -------------------------------------------------
    # BLUR
    # -------------------------------------------------

    def gaussian_blur(
        self,
        image: np.ndarray,
        kernel_size: int = 5,
    ) -> np.ndarray:

        return cv2.GaussianBlur(
            image,
            (kernel_size, kernel_size),
            0,
        )

    def median_blur(
        self,
        image: np.ndarray,
        kernel_size: int = 5,
    ) -> np.ndarray:

        return cv2.medianBlur(
            image,
            kernel_size,
        )

    # -------------------------------------------------
    # SHARPEN
    # -------------------------------------------------

    def sharpen(
        self,
        image: np.ndarray,
    ) -> np.ndarray:

        kernel = np.array(
            [
                [0, -1, 0],
                [-1, 5, -1],
                [0, -1, 0],
            ],
            dtype=np.float32,
        )

        return cv2.filter2D(
            image,
            -1,
            kernel,
        )

    # -------------------------------------------------
    # DENOISE
    # -------------------------------------------------

    def denoise(
        self,
        image: np.ndarray,
    ) -> np.ndarray:

        if len(image.shape) == 2:

            return cv2.fastNlMeansDenoising(
                image,
                None,
                10,
                7,
                21,
            )

        return cv2.fastNlMeansDenoisingColored(
            image,
            None,
            10,
            10,
            7,
            21,
        )

    # -------------------------------------------------
    # THRESHOLD
    # -------------------------------------------------

    def threshold(
        self,
        image: np.ndarray,
        value: int = 127,
    ) -> np.ndarray:

        gray = self.grayscale(image)

        _, result = cv2.threshold(
            gray,
            value,
            255,
            cv2.THRESH_BINARY,
        )

        return result

    def adaptive_threshold(
        self,
        image: np.ndarray,
    ) -> np.ndarray:

        gray = self.grayscale(image)

        return cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2,
        )

    def otsu_threshold(
        self,
        image: np.ndarray,
    ) -> np.ndarray:

        gray = self.grayscale(image)

        _, result = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )

        return result