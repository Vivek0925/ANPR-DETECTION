"""
OCR service for Indian vehicle license plates.

Uses EasyOCR with:
- Multiple preprocessing variants
- Character allowlist
- Indian plate-friendly validation
- OCR result merging
- Confidence scoring
- Common OCR character correction
"""

import re
from collections import defaultdict

import cv2
import numpy as np
import easyocr

import config


_reader = None


# ============================================================
# OCR READER
# ============================================================

def get_reader():
    global _reader

    if _reader is None:
        print("[OCR] Loading EasyOCR...")

        _reader = easyocr.Reader(
            ["en"],
            gpu=False,
            verbose=False,
        )

        print("[OCR] EasyOCR loaded.")

    return _reader


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_plate_text(
    raw_text: str,
) -> str:

    if not raw_text:
        return ""

    text = str(
        raw_text
    ).upper()

    # Remove spaces, hyphens and symbols.
    text = re.sub(
        r"[^A-Z0-9]",
        "",
        text,
    )

    return text


# ============================================================
# OCR CONFUSIONS
# ============================================================

OCR_CONFUSIONS = {
    "O": "0",
    "I": "1",
    "L": "1",
    "Z": "2",
    "S": "5",
    "G": "6",
    "B": "8",
}


# ============================================================
# BASIC VALIDATION
# ============================================================

def is_plausible_plate(
    text: str,
) -> bool:

    text = normalize_plate_text(
        text
    )

    if not text:
        return False

    min_length = getattr(
        config,
        "MIN_PLATE_TEXT_LEN",
        4,
    )

    if len(text) < min_length:
        return False

    # Realistic upper limit.
    if len(text) > 12:
        return False

    # A plate should normally contain
    # both letters and numbers.
    has_letter = bool(
        re.search(
            r"[A-Z]",
            text,
        )
    )

    has_number = bool(
        re.search(
            r"[0-9]",
            text,
        )
    )

    if not has_letter or not has_number:
        return False

    # Reject excessive repetition.
    counts = defaultdict(int)

    for char in text:
        counts[char] += 1

    most_common = max(
        counts.values()
    )

    if (
        most_common / len(text)
        > 0.70
    ):
        return False

    return True


# ============================================================
# CHARACTER CORRECTION
# ============================================================

def _correct_ocr_characters(
    text: str,
) -> str:
    """
    Correct obvious OCR mistakes.

    We don't blindly convert the entire string because Indian
    plates contain both letters and numbers.

    Character correction is based on the position in the plate.
    """

    text = normalize_plate_text(
        text
    )

    if not text:
        return ""

    chars = list(text)

    # --------------------------------------------------------
    # Indian plate structure is commonly:
    #
    # STATE + DISTRICT + SERIES + NUMBER
    #
    # Example:
    #
    # CG04AB1234
    # MH12DE5678
    #
    # The first ~4 characters are normally letters/numbers
    # and the final 4 are usually numeric.
    # --------------------------------------------------------

    if len(chars) >= 8:

        # Final four characters are usually numbers.
        for i in range(
            max(
                0,
                len(chars) - 4,
            ),
            len(chars),
        ):

            replacements = {
                "O": "0",
                "I": "1",
                "L": "1",
                "Z": "2",
                "S": "5",
                "G": "6",
                "B": "8",
            }

            chars[i] = replacements.get(
                chars[i],
                chars[i],
            )

    return "".join(
        chars
    )


# ============================================================
# OCR RESULT SORTING
# ============================================================

def _left_x(
    item,
) -> float:

    try:
        return float(
            item[0][0][0]
        )
    except Exception:
        return float("inf")


# ============================================================
# RUN OCR
# ============================================================

def _run_ocr(
    image,
):
    reader = get_reader()

    try:

        results = reader.readtext(
            image,

            # Only alphanumeric characters.
            allowlist=(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "0123456789"
            ),

            detail=1,

            paragraph=False,

            # Better for small plate text.
            mag_ratio=1.5,
        )

    except Exception as error:

        print(
            "[OCR] Error:",
            error,
        )

        return []

    return results or []


# ============================================================
# EXTRACT TEXT
# ============================================================

def _extract_text(
    results,
):

    if not results:
        return (
            "",
            "",
            0.0,
        )

    results = sorted(
        results,
        key=_left_x,
    )

    parts = []
    confidences = []

    for item in results:

        if not isinstance(
            item,
            (
                list,
                tuple,
            ),
        ):
            continue

        if len(item) < 3:
            continue

        text = item[1]

        try:
            confidence = float(
                item[2]
            )
        except Exception:
            confidence = 0.0

        if not isinstance(
            text,
            str,
        ):
            continue

        text = normalize_plate_text(
            text
        )

        if not text:
            continue

        parts.append(text)

        confidences.append(
            confidence
        )

    if not parts:
        return (
            "",
            "",
            0.0,
        )

    raw_text = "".join(
        parts
    )

    normalized = normalize_plate_text(
        raw_text
    )

    if not normalized:
        return (
            raw_text,
            "",
            0.0,
        )

    average_confidence = (
        sum(confidences)
        /
        len(confidences)
        if confidences
        else 0.0
    )

    return (
        raw_text,
        normalized,
        float(
            average_confidence
        ),
    )


# ============================================================
# PREPROCESSING VARIANTS
# ============================================================

def _create_variants(
    plate_image,
):
    """
    Generate a small number of useful OCR images.

    We intentionally keep this limited because EasyOCR on CPU
    is expensive.
    """

    if (
        plate_image is None
        or plate_image.size == 0
    ):
        return []

    variants = []

    original = plate_image.copy()

    # --------------------------------------------------------
    # 1. Original
    # --------------------------------------------------------

    variants.append(
        original
    )

    # --------------------------------------------------------
    # 2. Upscaled
    # --------------------------------------------------------

    try:

        upscaled = cv2.resize(
            original,
            None,
            fx=3.0,
            fy=3.0,
            interpolation=cv2.INTER_CUBIC,
        )

        variants.append(
            upscaled
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # 3. Grayscale + CLAHE
    # --------------------------------------------------------

    try:

        gray = cv2.cvtColor(
            original,
            cv2.COLOR_BGR2GRAY,
        )

        clahe = cv2.createCLAHE(
            clipLimit=2.5,
            tileGridSize=(
                8,
                8,
            ),
        )

        enhanced = clahe.apply(
            gray
        )

        enhanced = cv2.resize(
            enhanced,
            None,
            fx=3.0,
            fy=3.0,
            interpolation=cv2.INTER_CUBIC,
        )

        variants.append(
            enhanced
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # 4. Adaptive threshold
    # --------------------------------------------------------

    try:

        gray = cv2.cvtColor(
            original,
            cv2.COLOR_BGR2GRAY,
        )

        gray = cv2.resize(
            gray,
            None,
            fx=3.0,
            fy=3.0,
            interpolation=cv2.INTER_CUBIC,
        )

        threshold = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            9,
        )

        variants.append(
            threshold
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # 5. OTSU
    # --------------------------------------------------------

    try:

        gray = cv2.cvtColor(
            original,
            cv2.COLOR_BGR2GRAY,
        )

        gray = cv2.resize(
            gray,
            None,
            fx=3.0,
            fy=3.0,
            interpolation=cv2.INTER_CUBIC,
        )

        _, otsu = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY
            + cv2.THRESH_OTSU,
        )

        variants.append(
            otsu
        )

    except Exception:
        pass

    return variants


# ============================================================
# BEST OCR RESULT
# ============================================================

def read_plate_text(
    plate_image_bgr,
):
    """
    Run OCR over multiple variants.

    Returns:

        raw_text,
        normalized_text,
        confidence
    """

    variants = _create_variants(
        plate_image_bgr
    )

    if not variants:
        return (
            None,
            None,
            0.0,
        )

    candidates = []

    for variant in variants:

        results = _run_ocr(
            variant
        )

        if not results:
            continue

        (
            raw_text,
            normalized,
            confidence,
        ) = _extract_text(
            results
        )

        if not normalized:
            continue

        corrected = (
            _correct_ocr_characters(
                normalized
            )
        )

        # Use corrected value only if plausible.
        if is_plausible_plate(
            corrected
        ):
            normalized = corrected

        if not is_plausible_plate(
            normalized
        ):
            continue

        # Slight preference for longer readings.
        length_bonus = min(
            len(normalized) * 0.015,
            0.12,
        )

        score = (
            confidence * 0.85
            +
            length_bonus
        )

        candidates.append(
            {
                "raw": raw_text,
                "text": normalized,
                "confidence": confidence,
                "score": score,
            }
        )

    if not candidates:
        return (
            None,
            None,
            0.0,
        )

    # ========================================================
    # TEMPORAL-LIKE CONSENSUS WITHIN ONE CROP
    # ========================================================

    grouped = defaultdict(
        list
    )

    for candidate in candidates:

        grouped[
            candidate["text"]
        ].append(
            candidate
        )

    best_candidate = None
    best_score = -1

    for text, items in (
        grouped.items()
    ):

        average_confidence = (
            sum(
                item["confidence"]
                for item in items
            )
            /
            len(items)
        )

        repeat_bonus = min(
            len(items) * 0.05,
            0.15,
        )

        score = (
            average_confidence
            + repeat_bonus
        )

        if score > best_score:

            best_score = score

            best_candidate = max(
                items,
                key=lambda item:
                    item["confidence"],
            )

    if best_candidate is None:
        return (
            None,
            None,
            0.0,
        )

    return (
        best_candidate["raw"],
        best_candidate["text"],
        float(
            best_candidate["confidence"]
        ),
    )


# ============================================================
# BEST OF MULTIPLE CROPS
# ============================================================

def read_plate_text_best(
    crops,
):
    """
    Run OCR over multiple candidate crops.

    Selection priority:

    1. Same text appearing in multiple variants
    2. OCR confidence
    3. Longer valid plate
    """

    if not crops:
        return (
            None,
            None,
            0.0,
        )

    candidates = []

    for crop in crops:

        if (
            crop is None
            or crop.size == 0
        ):
            continue

        try:

            (
                raw,
                normalized,
                confidence,
            ) = read_plate_text(
                crop
            )

        except Exception as error:

            print(
                "[OCR] Crop error:",
                error,
            )

            continue

        if not normalized:
            continue

        if not is_plausible_plate(
            normalized
        ):
            continue

        candidates.append(
            (
                raw,
                normalized,
                float(confidence),
            )
        )

    if not candidates:
        return (
            None,
            None,
            0.0,
        )

    # ========================================================
    # GROUP SAME READINGS
    # ========================================================

    grouped = defaultdict(
        list
    )

    for candidate in candidates:

        grouped[
            candidate[1]
        ].append(
            candidate
        )

    ranked = []

    for text, items in (
        grouped.items()
    ):

        average_confidence = (
            sum(
                item[2]
                for item in items
            )
            /
            len(items)
        )

        best_confidence = max(
            item[2]
            for item in items
        )

        repeat_bonus = min(
            len(items) * 0.08,
            0.20,
        )

        length_bonus = min(
            len(text) * 0.015,
            0.12,
        )

        final_score = (
            average_confidence * 0.65
            +
            best_confidence * 0.20
            +
            repeat_bonus
            +
            length_bonus
        )

        best_item = max(
            items,
            key=lambda item:
                item[2],
        )

        ranked.append(
            (
                final_score,
                best_item,
            )
        )

    ranked.sort(
        key=lambda item:
            item[0],
        reverse=True,
    )

    best = ranked[0][1]

    return (
        best[0],
        best[1],
        best[2],
    )