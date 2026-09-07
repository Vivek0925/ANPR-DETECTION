"""
Smart license-plate search for the ANPR system.

Features:
- Exact plate matching
- Normalized matching
- OCR-confusion tolerant matching
- Fuzzy Levenshtein matching
- Partial matching
- Similarity scoring
- Duplicate removal
"""

from sqlalchemy.orm import Session
from sqlalchemy import asc

from models import Detection, Video
from services.ocr import normalize_plate_text


# Common OCR character confusions.
OCR_CONFUSIONS = {
    "0": {"O"},
    "O": {"0"},

    "1": {"I", "L"},
    "I": {"1", "L"},
    "L": {"1", "I"},

    "2": {"Z"},
    "Z": {"2"},

    "5": {"S"},
    "S": {"5"},

    "6": {"G"},
    "G": {"6"},

    "8": {"B"},
    "B": {"8"},

    "7": {"T"},
    "T": {"7"},
}


def clean_plate(text: str) -> str:
    """Normalize a license plate."""

    if not text:
        return ""

    return normalize_plate_text(text)


def _levenshtein(a: str, b: str) -> float:
    """Calculate OCR-aware Levenshtein distance."""

    if a == b:
        return 0

    if not a:
        return len(b)

    if not b:
        return len(a)

    previous = list(range(len(b) + 1))

    for i, char_a in enumerate(a, start=1):
        current = [i]

        for j, char_b in enumerate(b, start=1):

            if char_a == char_b:
                cost = 0

            elif char_b in OCR_CONFUSIONS.get(char_a, set()):
                # Common OCR error gets a very small penalty.
                cost = 0.25

            else:
                cost = 1

            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + cost,
                )
            )

        previous = current

    return previous[-1]


def _similarity(a: str, b: str) -> float:
    """Return similarity from 0.0 to 1.0."""

    if not a or not b:
        return 0.0

    distance = _levenshtein(a, b)

    max_length = max(len(a), len(b))

    if max_length == 0:
        return 1.0

    return max(
        0.0,
        min(
            1.0,
            1.0 - (distance / max_length),
        ),
    )


def _position_aware_match(query: str, plate: str) -> float:
    """
    Compare characters at the same positions.

    Example:

        34A23126
        34A2312G

    The final G is treated as a likely OCR error.
    """

    if not query or not plate:
        return 0.0

    max_length = max(
        len(query),
        len(plate),
    )

    score = 0.0

    for i in range(
        min(
            len(query),
            len(plate),
        )
    ):

        query_char = query[i]
        plate_char = plate[i]

        if query_char == plate_char:
            score += 1.0

        elif plate_char in OCR_CONFUSIONS.get(
            query_char,
            set(),
        ):
            score += 0.85

    return score / max_length


def _match_score(query: str, plate: str) -> float:
    """Combine fuzzy and position-based matching."""

    if query == plate:
        return 1.0

    # Partial match.
    if query in plate or plate in query:

        shorter = min(
            len(query),
            len(plate),
        )

        longer = max(
            len(query),
            len(plate),
        )

        if longer == 0:
            return 0.0

        return 0.92 * (
            shorter / longer
        )

    fuzzy_score = _similarity(
        query,
        plate,
    )

    position_score = _position_aware_match(
        query,
        plate,
    )

    return max(
        0.0,
        min(
            1.0,
            fuzzy_score * 0.55
            + position_score * 0.45,
        ),
    )


def _max_allowed_distance(length: int) -> float:
    """Maximum OCR error allowed."""

    if length <= 5:
        return 1.0

    if length <= 8:
        return 2.0

    return 3.0


def _fuzzy_candidates(
    db: Session,
    normalized_query: str,
):
    """
    Find plates that are probably the searched plate
    despite OCR errors.
    """

    if not normalized_query:
        return []

    rows = (
        db.query(Detection, Video)
        .join(
            Video,
            Detection.video_id == Video.id,
        )
        .order_by(
            asc(Detection.video_id),
            asc(Detection.timestamp_seconds),
        )
        .all()
    )

    candidates = []

    max_distance = _max_allowed_distance(
        len(normalized_query)
    )

    for detection, video in rows:

        detected_plate = clean_plate(
            detection.plate_number or ""
        )

        if not detected_plate:
            continue

        # Ignore plates whose lengths are wildly different.
        if abs(
            len(normalized_query)
            - len(detected_plate)
        ) > max_distance:
            continue

        distance = _levenshtein(
            normalized_query,
            detected_plate,
        )

        similarity = _match_score(
            normalized_query,
            detected_plate,
        )

        # Exact match.
        if detected_plate == normalized_query:

            candidates.append(
                {
                    "detection": detection,
                    "video": video,
                    "distance": 0,
                    "similarity": 1.0,
                }
            )

            continue

        # Partial match.
        if (
            normalized_query in detected_plate
            or detected_plate in normalized_query
        ):

            if similarity >= 0.75:

                candidates.append(
                    {
                        "detection": detection,
                        "video": video,
                        "distance": distance,
                        "similarity": similarity,
                    }
                )

            continue

        # Fuzzy match.
        if (
            distance <= max_distance
            and similarity >= 0.70
        ):

            candidates.append(
                {
                    "detection": detection,
                    "video": video,
                    "distance": distance,
                    "similarity": similarity,
                }
            )

    # Best matches first.
    candidates.sort(
        key=lambda item: (
            -item["similarity"],
            item["distance"],
            item["detection"].video_id,
            item["detection"].timestamp_seconds,
        )
    )

    return [
        (
            item["detection"],
            item["video"],
        )
        for item in candidates
    ]


def _remove_duplicate_detections(results):
    """
    Remove repeated detections of the same plate
    at essentially the same timestamp.
    """

    unique = {}

    for detection, video in results:

        plate = clean_plate(
            detection.plate_number or ""
        )

        key = (
            detection.video_id,
            round(
                float(
                    detection.timestamp_seconds or 0
                ),
                1,
            ),
            plate,
        )

        current = unique.get(key)

        if current is None:

            unique[key] = (
                detection,
                video,
            )

            continue

        current_detection = current[0]

        current_confidence = float(
            current_detection.ocr_confidence or 0
        )

        new_confidence = float(
            detection.ocr_confidence or 0
        )

        if new_confidence > current_confidence:

            unique[key] = (
                detection,
                video,
            )

    return list(unique.values())


def search_by_plate(
    db: Session,
    plate_query: str,
):
    """
    Search for a license plate.

    Search order:

    1. Exact database match
    2. Normalized match
    3. Fuzzy OCR match

    Returns:

        normalized_query,
        [(Detection, Video), ...]
    """

    normalized_query = clean_plate(
        plate_query
    )

    if not normalized_query:
        return normalized_query, []

    # ---------------------------------------------------------
    # 1. EXACT MATCH
    # ---------------------------------------------------------

    exact_results = (
        db.query(Detection, Video)
        .join(
            Video,
            Detection.video_id == Video.id,
        )
        .filter(
            Detection.plate_number
            == normalized_query
        )
        .order_by(
            asc(Detection.video_id),
            asc(Detection.timestamp_seconds),
        )
        .all()
    )

    if exact_results:

        return (
            normalized_query,
            _remove_duplicate_detections(
                exact_results
            ),
        )

    # ---------------------------------------------------------
    # 2. NORMALIZED MATCH
    # ---------------------------------------------------------

    rows = (
        db.query(Detection, Video)
        .join(
            Video,
            Detection.video_id == Video.id,
        )
        .order_by(
            asc(Detection.video_id),
            asc(Detection.timestamp_seconds),
        )
        .all()
    )

    normalized_matches = []

    for detection, video in rows:

        detected_plate = clean_plate(
            detection.plate_number or ""
        )

        if (
            detected_plate
            and detected_plate == normalized_query
        ):

            normalized_matches.append(
                (
                    detection,
                    video,
                )
            )

    if normalized_matches:

        return (
            normalized_query,
            _remove_duplicate_detections(
                normalized_matches
            ),
        )

    # ---------------------------------------------------------
    # 3. FUZZY OCR MATCH
    # ---------------------------------------------------------

    fuzzy_results = _fuzzy_candidates(
        db,
        normalized_query,
    )

    fuzzy_results = _remove_duplicate_detections(
        fuzzy_results
    )

    return (
        normalized_query,
        fuzzy_results,
    )