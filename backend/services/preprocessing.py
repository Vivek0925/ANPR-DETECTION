"""
Preprocessing for cropped plate images prior to OCR:
resize -> grayscale -> contrast enhancement.
"""
import cv2
import numpy as np


def preprocess_plate_crop(plate_bgr: np.ndarray) -> np.ndarray:
    """
    Takes a BGR crop of a license plate and returns a preprocessed image
    (still 3-channel BGR, since EasyOCR expects that) ready for OCR.
    """
    if plate_bgr is None or plate_bgr.size == 0:
        return plate_bgr

    h, w = plate_bgr.shape[:2]
    if h == 0 or w == 0:
        return plate_bgr

    # Upscale small crops so OCR has more pixels to work with.
    target_width = 300
    if w < target_width:
        scale = target_width / w
        plate_bgr = cv2.resize(
            plate_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC
        )

    gray = cv2.cvtColor(plate_bgr, cv2.COLOR_BGR2GRAY)

    # CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Mild denoise
    enhanced = cv2.bilateralFilter(enhanced, 5, 50, 50)

    # Back to 3-channel for OCR engines that expect color input
    result = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    return result
