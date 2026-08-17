"""
OCR service. Uses EasyOCR (chosen over PaddleOCR for this MVP -- see README
'Troubleshooting' for why: PaddleOCR's paddlepaddle dependency is heavy and
version-fragile; EasyOCR installs cleanly with pip and is reliable enough for
an MVP demonstration). The engine is swappable via config.OCR_ENGINE.
"""
import re
import easyocr

import config

_reader = None


def _safe_left_x(result_item) -> float:
    """
    Return left-most x coordinate for an OCR item; malformed items are pushed
    to the end of sorting rather than crashing processing.
    """
    try:
        return float(result_item[0][0][0])
    except Exception:
        return float("inf")


def get_reader():
    global _reader
    if _reader is None:
        # gpu=False -> CPU inference, works everywhere without CUDA setup.
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


def normalize_plate_text(raw_text: str) -> str:
    """
    Simple, non-aggressive normalization for Indian plates:
    - uppercase
    - strip whitespace
    - remove characters that aren't A-Z or 0-9
    """
    if not raw_text:
        return ""
    text = raw_text.upper()
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text


def read_plate_text(plate_image_bgr):
    """
    Runs OCR on a preprocessed plate crop.
    Returns (raw_text, normalized_text, confidence) or (None, None, 0.0)
    if nothing usable was read.
    """
    reader = get_reader()
    results = reader.readtext(plate_image_bgr)
    if not results:
        return None, None, 0.0

    # Concatenate all detected text fragments left-to-right (a plate may be
    # read as multiple text pieces), weighting confidence by fragment length.
    results_sorted = sorted(results, key=_safe_left_x)  # sort by x when present
    raw_parts = []
    confidences = []
    for item in results_sorted:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        text = item[1]
        conf = item[2]
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            conf_value = float(conf)
        except Exception:
            conf_value = 0.0
        raw_parts.append(text)
        confidences.append(conf_value)

    if not raw_parts:
        return None, None, 0.0

    raw_text = "".join(raw_parts)
    normalized = normalize_plate_text(raw_text)

    if len(normalized) < config.MIN_PLATE_TEXT_LEN:
        return raw_text, None, 0.0

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return raw_text, normalized, float(avg_confidence)


def read_plate_text_best(crops):
    """
    Runs OCR over multiple candidate crops and returns the best reading.
    Selection priority:
    1) longer normalized text
    2) higher OCR confidence
    """
    best = (None, None, 0.0)
    best_score = (0, 0.0)

    for crop in crops:
        if crop is None:
            continue
        raw_text, normalized, conf = read_plate_text(crop)
        if not normalized:
            continue
        score = (len(normalized), float(conf))
        if score > best_score:
            best_score = score
            best = (raw_text, normalized, float(conf))

    return best
