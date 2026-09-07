"""
License plate image preprocessing.

The goal is to make small / blurry CCTV plates easier for OCR.

Pipeline:

crop
 ↓
resize
 ↓
CLAHE
 ↓
denoise
 ↓
sharpen
 ↓
OCR
"""

import cv2
import numpy as np


def preprocess_plate_crop(
    plate_bgr: np.ndarray
) -> np.ndarray:

    if (
        plate_bgr is None
        or plate_bgr.size == 0
    ):
        return plate_bgr


    h, w = (
        plate_bgr.shape[:2]
    )


    if h <= 0 or w <= 0:
        return plate_bgr


    # ========================================================
    # UPSCALE
    # ========================================================

    # Small plates are difficult for OCR.

    target_width = 320


    if w < target_width:

        scale = (
            target_width / float(w)
        )

        new_width = int(
            w * scale
        )

        new_height = int(
            h * scale
        )

        plate_bgr = cv2.resize(
            plate_bgr,

            (
                new_width,
                new_height,
            ),

            interpolation=cv2.INTER_CUBIC,
        )


    # ========================================================
    # GRAYSCALE
    # ========================================================

    gray = cv2.cvtColor(
        plate_bgr,
        cv2.COLOR_BGR2GRAY,
    )


    # ========================================================
    # CONTRAST
    # ========================================================

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    enhanced = clahe.apply(
        gray
    )


    # ========================================================
    # DENOISE
    # ========================================================

    enhanced = cv2.bilateralFilter(
        enhanced,
        5,
        50,
        50,
    )


    # ========================================================
    # SHARPEN
    # ========================================================

    kernel = np.array(
        [
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0],
        ],
        dtype=np.float32,
    )


    sharpened = cv2.filter2D(
        enhanced,
        -1,
        kernel,
    )


    # ========================================================
    # BACK TO BGR
    # ========================================================

    result = cv2.cvtColor(
        sharpened,
        cv2.COLOR_GRAY2BGR,
    )


    return result