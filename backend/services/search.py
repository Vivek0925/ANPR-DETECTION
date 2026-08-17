"""
Plate search — the core retrieval feature of this MVP.
"""
from sqlalchemy.orm import Session
from sqlalchemy import asc

from models import Detection, Video
from services.ocr import normalize_plate_text


CONFUSABLE_MAP = {
    "0": "O",
    "O": "O",
    "1": "I",
    "I": "I",
    "L": "I",
    "2": "Z",
    "Z": "Z",
    "5": "S",
    "S": "S",
    "6": "G",
    "G": "G",
    "8": "B",
    "B": "B",
    "7": "T",
    "T": "T",
}


def _fold_confusables(text: str) -> str:
    return "".join(CONFUSABLE_MAP.get(ch, ch) for ch in text)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(
                prev[j] + 1,      # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost,
            ))
        prev = curr
    return prev[-1]


def _fuzzy_candidates(db: Session, normalized_query: str):
    if not normalized_query:
        return []

    folded_query = _fold_confusables(normalized_query)
    max_distance = 2 if len(normalized_query) <= 7 else 3

    rows = (
        db.query(Detection, Video)
        .join(Video, Detection.video_id == Video.id)
        .order_by(asc(Detection.video_id), asc(Detection.timestamp_seconds))
        .all()
    )

    matches = []
    for detection, video in rows:
        plate = normalize_plate_text(detection.plate_number or "")
        if not plate:
            continue
        folded_plate = _fold_confusables(plate)
        if abs(len(folded_plate) - len(folded_query)) > max_distance:
            continue
        distance = _levenshtein(folded_query, folded_plate)
        if distance <= max_distance:
            matches.append((distance, detection, video))

    matches.sort(key=lambda item: (item[0], item[1].video_id, item[1].timestamp_seconds))
    return [(detection, video) for _, detection, video in matches]


def search_by_plate(db: Session, plate_query: str):
    """
    Returns (normalized_query, list[Detection]) ordered by timestamp,
    joined with their video. Uses a normalized substring/exact match
    against the indexed plate_number column.
    """
    normalized_query = normalize_plate_text(plate_query)
    if not normalized_query:
        return normalized_query, []

    results = (
        db.query(Detection, Video)
        .join(Video, Detection.video_id == Video.id)
        .filter(Detection.plate_number.like(f"%{normalized_query}%"))
        .order_by(asc(Detection.video_id), asc(Detection.timestamp_seconds))
        .all()
    )

    if not results:
        results = _fuzzy_candidates(db, normalized_query)

    return normalized_query, results
