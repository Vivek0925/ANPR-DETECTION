"""
Video processing pipeline for ANPR.

Pipeline:

Video
  ↓
Sample frames
  ↓
Vehicle detection + ByteTrack
  ↓
License plate detection
  ↓
Plate → vehicle matching
  ↓
Expanded plate crop
  ↓
Multi-variant OCR
  ↓
Temporal OCR voting
  ↓
Vehicle event tracker
  ↓
Database
"""

import os
import re
import traceback
from collections import defaultdict, Counter

import cv2

import config

from database import SessionLocal
from models import Video, Detection

from services.vehicle_detector import VehicleDetector
from services.plate_detector import PlateDetector

from services.preprocessing import preprocess_plate_crop

from services.ocr import (
    read_plate_text_best,
    normalize_plate_text,
)

from services.vehicle_events import (
    TrackedVehicle,
    PlateObservation,
    VehicleEventTracker,
    build_snapshot_frame,
    match_plate_to_vehicle,
)


# ============================================================
# LAZY LOADED MODELS
# ============================================================

_vehicle_detector = None
_plate_detector = None


def _get_detectors():
    global _vehicle_detector
    global _plate_detector

    if _vehicle_detector is None:
        print("[AI] Loading vehicle detector...")
        _vehicle_detector = VehicleDetector()

    if _plate_detector is None:
        print("[AI] Loading license plate detector...")
        _plate_detector = PlateDetector()

    return _vehicle_detector, _plate_detector


# ============================================================
# TIMESTAMP
# ============================================================

def format_timestamp(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


# ============================================================
# VEHICLE IDENTITY
# ============================================================

def _vehicle_identity(vehicle):
    """
    Stable vehicle identity.

    Prefer ByteTrack ID.

    Spatial fallback is only used when tracker does not provide an ID.
    """

    track_id = vehicle.get("track_id")

    if track_id is not None:
        return f"track:{track_id}"

    x1, y1, x2, y2 = vehicle["bbox"]

    center_x = int(((x1 + x2) / 2) / 60)
    center_y = int(((y1 + y2) / 2) / 60)

    return (
        f"fallback:"
        f"{vehicle.get('class_name', 'vehicle')}:"
        f"{center_x}:"
        f"{center_y}"
    )


# ============================================================
# TRACKED VEHICLE
# ============================================================

def _make_tracked_vehicle(vehicle):
    return TrackedVehicle(
        track_id=vehicle.get("track_id"),
        bbox=vehicle["bbox"],
        class_name=vehicle["class_name"],
        confidence=vehicle["confidence"],
    )


# ============================================================
# PLATE → VEHICLE FALLBACK MATCH
# ============================================================

def _fallback_match_plate_to_vehicle(
    plate_bbox,
    vehicles,
):
    if not vehicles:
        return None

    px1, py1, px2, py2 = plate_bbox

    plate_cx = (px1 + px2) / 2
    plate_cy = (py1 + py2) / 2

    best_vehicle = None
    best_distance = float("inf")

    for vehicle in vehicles:

        vx1, vy1, vx2, vy2 = vehicle.bbox

        # Plate center inside vehicle
        if (
            vx1 <= plate_cx <= vx2
            and vy1 <= plate_cy <= vy2
        ):
            return vehicle

        vehicle_cx = (vx1 + vx2) / 2
        vehicle_cy = (vy1 + vy2) / 2

        distance = (
            (plate_cx - vehicle_cx) ** 2
            +
            (plate_cy - vehicle_cy) ** 2
        )

        if distance < best_distance:
            best_distance = distance
            best_vehicle = vehicle

    return best_vehicle


# ============================================================
# EXPAND PLATE CROP
# ============================================================

def _expand_plate_bbox(
    bbox,
    frame_shape,
    padding_ratio=0.15,
):
    """
    Expands plate bounding box slightly.

    This is important because YOLO plate boxes can be very tight
    and OCR benefits from a small amount of surrounding context.
    """

    x1, y1, x2, y2 = bbox

    height, width = frame_shape[:2]

    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)

    pad_x = int(bw * padding_ratio)
    pad_y = int(bh * padding_ratio)

    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)

    x2 = min(width, x2 + pad_x)
    y2 = min(height, y2 + pad_y)

    return x1, y1, x2, y2


# ============================================================
# OCR VARIANTS
# ============================================================

def _build_ocr_variants(plate_crop):
    """
    Build a small number of high-value OCR variants.

    We intentionally keep this smaller than the previous pipeline
    because EasyOCR is CPU-heavy.
    """

    variants = []

    if plate_crop is None:
        return variants

    if plate_crop.size == 0:
        return variants

    original = plate_crop.copy()

    # --------------------------------------------------------
    # 1. Original
    # --------------------------------------------------------

    variants.append(original)

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

        variants.append(upscaled)

    except Exception:
        upscaled = original

    # --------------------------------------------------------
    # 3. CLAHE
    # --------------------------------------------------------

    try:

        gray = cv2.cvtColor(
            upscaled,
            cv2.COLOR_BGR2GRAY,
        )

        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8),
        )

        enhanced = clahe.apply(gray)

        enhanced = cv2.cvtColor(
            enhanced,
            cv2.COLOR_GRAY2BGR,
        )

        variants.append(enhanced)

    except Exception:
        pass

    return variants


# ============================================================
# OCR
# ============================================================

def _read_plate_with_multiple_variants(plate_crop):
    """
    Run OCR over multiple variants.

    Returns:

        raw_text
        normalized_text
        confidence
    """

    variants = _build_ocr_variants(plate_crop)

    if not variants:
        return "", "", 0.0

    best_raw = ""
    best_normalized = ""
    best_confidence = 0.0

    # --------------------------------------------------------
    # Existing preprocessing
    # --------------------------------------------------------

    try:

        processed = preprocess_plate_crop(
            plate_crop
        )

        if (
            processed is not None
            and processed.size > 0
        ):
            variants.insert(
                0,
                processed,
            )

    except Exception:
        pass

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    for image in variants:

        try:

            raw_text, normalized, confidence = (
                read_plate_text_best(
                    [image]
                )
            )

        except Exception:
            continue

        if not normalized:
            continue

        normalized = normalize_plate_text(
            normalized
        )

        if not normalized:
            continue

        try:
            confidence = float(
                confidence or 0
            )
        except Exception:
            confidence = 0.0

        # Prefer confidence first.
        # If confidence is similar, prefer longer plate.
        if (
            confidence > best_confidence
            or (
                abs(confidence - best_confidence) < 0.05
                and len(normalized) > len(best_normalized)
            )
        ):
            best_raw = raw_text or normalized
            best_normalized = normalized
            best_confidence = confidence

    return (
        best_raw,
        best_normalized,
        best_confidence,
    )


# ============================================================
# PLATE VALIDATION
# ============================================================

def _looks_like_plate(text):
    """
    Reject obvious OCR garbage.

    This is intentionally not a strict Indian registration validator,
    because CCTV footage can produce partial plates.
    """

    if not text:
        return False

    text = normalize_plate_text(text)

    if len(text) < config.MIN_PLATE_TEXT_LEN:
        return False

    if len(text) > 12:
        return False

    if not re.search(r"[A-Z]", text):
        return False

    if not re.search(r"[0-9]", text):
        return False

    # Reject strings dominated by one repeated character.
    counts = Counter(text)

    most_common_count = counts.most_common(1)[0][1]

    if most_common_count / len(text) > 0.70:
        return False

    return True


# ============================================================
# OCR TEMPORAL VOTING
# ============================================================

class OCRVoteBuffer:
    """
    Keeps OCR observations for each tracked vehicle.

    This prevents:

        3436837
        B436837
        D436837
        04368S37
        ...

    from immediately becoming separate database events.

    Instead, repeated observations compete and the most stable
    candidate is selected.
    """

    def __init__(self):
        self.data = defaultdict(list)

    def add(
        self,
        track_id,
        text,
        confidence,
        timestamp,
    ):
        if track_id is None:
            return

        text = normalize_plate_text(text)

        if not _looks_like_plate(text):
            return

        self.data[track_id].append(
            (
                text,
                float(confidence),
                float(timestamp),
            )
        )

        # Keep only recent observations.
        cutoff = timestamp - 5.0

        self.data[track_id] = [
            item
            for item in self.data[track_id]
            if item[2] >= cutoff
        ]

    def best(self, track_id):
        observations = self.data.get(
            track_id,
            [],
        )

        if not observations:
            return None

        grouped = defaultdict(list)

        for text, confidence, timestamp in observations:
            grouped[text].append(
                confidence
            )

        candidates = []

        for text, confidences in grouped.items():

            avg_conf = (
                sum(confidences)
                / len(confidences)
            )

            count = len(confidences)

            score = (
                count * 0.60
                +
                avg_conf * 0.40
            )

            candidates.append(
                (
                    score,
                    avg_conf,
                    count,
                    text,
                )
            )

        candidates.sort(
            reverse=True
        )

        return candidates[0][3]

    def clear(self, track_id):
        self.data.pop(
            track_id,
            None,
        )


# ============================================================
# SAVE DETECTION
# ============================================================

def _sanitize_plate_for_filename(
    plate_number,
):
    cleaned = "".join(
        char
        for char in plate_number
        if char.isalnum()
    )

    return (
        cleaned.upper()
        or "plate"
    )


def _save_detection(
    db,
    video,
    event,
    video_snapshot_dir,
    video_plate_dir,
):
    """
    Save every tracked vehicle event.

    recognized:
        Plate successfully detected and read.

    ocr_failed:
        Plate was detected but OCR could not produce
        a valid plate number.

    no_plate:
        No license plate was detected for this vehicle.
    """

    if event.plate_number:
        plate_status = "recognized"
        plate_slug = _sanitize_plate_for_filename(
            event.plate_number
        )

    elif event.plate_observation_count > 0:
        plate_status = "ocr_failed"
        plate_slug = "ocr_failed"

    else:
        plate_status = "no_plate"
        plate_slug = "no_plate"

    plate_crop_path = None
    snapshot_path = None

    # --------------------------------------------------------
    # Plate crop
    # --------------------------------------------------------

    if event.plate_crop is not None:

        filename = (
            f"{plate_slug}_"
            f"track{event.track_id or 'na'}_"
            f"{event.representative_frame_number}.jpg"
        )

        plate_crop_path = os.path.join(
            video_plate_dir,
            filename,
        )

        cv2.imwrite(
            plate_crop_path,
            event.plate_crop,
        )

    # --------------------------------------------------------
    # Snapshot
    # --------------------------------------------------------

    snapshot_frame = build_snapshot_frame(
        event,
        config.DEBUG_TRACKING,
    )

    if snapshot_frame is not None:

        filename = (
            f"{plate_slug}_"
            f"track{event.track_id or 'na'}_"
            f"{event.representative_frame_number}.jpg"
        )

        snapshot_path = os.path.join(
            video_snapshot_dir,
            filename,
        )

        cv2.imwrite(
            snapshot_path,
            snapshot_frame,
        )

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    detection = Detection(
        video_id=video.id,

        plate_number=event.plate_number,

        plate_status=plate_status,

        raw_ocr_text=event.raw_ocr_text,

        timestamp_seconds=(
            event.representative_timestamp_seconds
        ),

        frame_number=(
            event.representative_frame_number
        ),

        track_id=event.track_id,

        event_start_seconds=(
            event.first_seen_seconds
        ),

        event_end_seconds=(
            event.last_seen_seconds
        ),

        vehicle_type=event.vehicle_type,

        ocr_confidence=(
            event.ocr_confidence
        ),

        detection_confidence=(
            event.plate_confidence
        ),

        snapshot_path=snapshot_path,

        plate_crop_path=plate_crop_path,
    )

    db.add(detection)

    return True


# ============================================================
# MAIN PROCESSOR
# ============================================================

def process_video(video_id: int):

    db = SessionLocal()

    cap = None

    try:

        # ====================================================
        # GET VIDEO
        # ====================================================

        video = (
            db.query(Video)
            .filter(
                Video.id == video_id
            )
            .first()
        )

        if not video:
            print(
                f"[VIDEO {video_id}] Not found."
            )
            return

        video.status = "processing"
        video.error_message = None
        video.progress_percent = 0

        db.commit()

        print(
            f"[VIDEO {video_id}] Starting processing..."
        )

        # ====================================================
        # LOAD AI MODELS
        # ====================================================

        try:

            (
                vehicle_detector,
                plate_detector,
            ) = _get_detectors()

        except FileNotFoundError as error:

            video.status = "failed"
            video.error_message = str(error)

            db.commit()

            return

        # Reset ByteTrack
        vehicle_detector.reset_tracker()

        # ====================================================
        # OPEN VIDEO
        # ====================================================

        cap = cv2.VideoCapture(
            video.filepath
        )

        if not cap.isOpened():

            video.status = "failed"
            video.error_message = (
                "Could not open uploaded video."
            )

            db.commit()

            return

        fps = (
            cap.get(
                cv2.CAP_PROP_FPS
            )
            or 25.0
        )

        total_frames = int(
            cap.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        ) or 0

        duration = (
            total_frames / fps
            if fps > 0
            else 0
        )

        video.fps = fps
        video.total_frames = total_frames
        video.duration = duration

        db.commit()

        # ====================================================
        # PROCESSING FPS
        # ====================================================

        configured_fps = getattr(
            config,
            "PROCESS_FPS",
            3.0,
        )

        try:
            process_fps = float(
                configured_fps
            )
        except Exception:
            process_fps = 3.0

        process_fps = min(
            max(
                process_fps,
                1.0,
            ),
            6.0,
        )

        frame_interval = max(
            1,
            int(
                round(
                    fps / process_fps
                )
            ),
        )

        print(
            f"[VIDEO {video_id}]"
            f" FPS={fps:.2f}"
            f" PROCESS_FPS={process_fps:.2f}"
            f" FRAME_INTERVAL={frame_interval}"
        )

        # ====================================================
        # OCR COOLDOWN
        # ====================================================

        ocr_interval = getattr(
            config,
            "OCR_INTERVAL_SECONDS",
            1.0,
        )

        try:
            ocr_interval = float(
                ocr_interval
            )
        except Exception:
            ocr_interval = 1.0

        ocr_interval = max(
            0.5,
            ocr_interval,
        )

        # ====================================================
        # EVENT TRACKER
        # ====================================================

        event_tracker = VehicleEventTracker(
            config.TRACK_LOST_TIMEOUT_SECONDS
        )

        # ====================================================
        # OCR VOTING
        # ====================================================

        ocr_votes = OCRVoteBuffer()

        # Last OCR time per vehicle.
        last_ocr_time_by_track = {}

        # Number of license plates detected for each tracked vehicle.
        # This is intentionally separate from successful OCR observations:
        # a detected plate with failed OCR must become `ocr_failed`,
        # while a vehicle with no detected plate becomes `no_plate`.
        plate_detected_by_track = defaultdict(int)

        # ====================================================
        # COUNTERS
        # ====================================================

        frame_idx = 0
        frames_processed = 0

        unique_vehicle_ids = set()

        vehicle_events_detected = 0
        plates_recognized = 0

        # ====================================================
        # OUTPUT DIRECTORIES
        # ====================================================

        video_snapshot_dir = os.path.join(
            config.SNAPSHOTS_DIR,
            str(video.id),
        )

        video_plate_dir = os.path.join(
            config.PLATES_DIR,
            str(video.id),
        )

        os.makedirs(
            video_snapshot_dir,
            exist_ok=True,
        )

        os.makedirs(
            video_plate_dir,
            exist_ok=True,
        )

        # ====================================================
        # PROCESS VIDEO
        # ====================================================

        while True:

            ret, frame = cap.read()

            if not ret:
                break

            # ------------------------------------------------
            # FRAME SAMPLING
            # ------------------------------------------------

            if frame_idx % frame_interval != 0:

                frame_idx += 1
                continue

            timestamp_seconds = (
                frame_idx / fps
            )

            # =================================================
            # VEHICLE DETECTION + TRACKING
            # =================================================

            try:

                vehicles = (
                    vehicle_detector.track(
                        frame
                    )
                )

            except Exception as error:

                print(
                    "[VEHICLE DETECTOR ERROR]",
                    error,
                )

                vehicles = []

            # ------------------------------------------------
            # UNIQUE VEHICLES
            # ------------------------------------------------

            for vehicle in vehicles:

                identity = _vehicle_identity(
                    vehicle
                )

                unique_vehicle_ids.add(
                    identity
                )

            # =================================================
            # TRACKED VEHICLES
            # =================================================

            tracked_vehicles = [
                _make_tracked_vehicle(
                    vehicle
                )
                for vehicle in vehicles
            ]

            # =================================================
            # PLATE DETECTION
            # =================================================

            try:

                plates = (
                    plate_detector.detect(
                        frame
                    )
                )

            except Exception as error:

                print(
                    "[PLATE DETECTOR ERROR]",
                    error,
                )

                plates = []

            # =================================================
            # PLATE OBSERVATIONS
            # =================================================

            plate_observations = []

            # =================================================
            # PROCESS PLATES
            # =================================================

            for plate in plates:

                try:

                    x1, y1, x2, y2 = (
                        plate["bbox"]
                    )

                except Exception:
                    continue

                # ------------------------------------------------
                # EXPAND PLATE BOX
                # ------------------------------------------------

                x1, y1, x2, y2 = (
                    _expand_plate_bbox(
                        (
                            int(x1),
                            int(y1),
                            int(x2),
                            int(y2),
                        ),
                        frame.shape,
                        padding_ratio=0.15,
                    )
                )

                if x2 <= x1 or y2 <= y1:
                    continue

                # ------------------------------------------------
                # CROP
                # ------------------------------------------------

                plate_crop = frame[
                    y1:y2,
                    x1:x2,
                ]

                if (
                    plate_crop is None
                    or plate_crop.size == 0
                ):
                    continue

                expanded_bbox = (
                    x1,
                    y1,
                    x2,
                    y2,
                )

                # =================================================
                # MATCH PLATE → VEHICLE
                # =================================================

                vehicle = (
                    match_plate_to_vehicle(
                        expanded_bbox,
                        tracked_vehicles,
                    )
                )

                if vehicle is None:

                    vehicle = (
                        _fallback_match_plate_to_vehicle(
                            expanded_bbox,
                            tracked_vehicles,
                        )
                    )

                if vehicle is None:
                    continue

                track_id = vehicle.track_id

                # The plate detector found a plate belonging to this vehicle.
                # Count it even if OCR is skipped/fails.
                if track_id is not None:
                    plate_detected_by_track[track_id] += 1

                # =================================================
                # OCR COOLDOWN
                # =================================================

                if track_id is not None:

                    last_ocr = (
                        last_ocr_time_by_track.get(
                            track_id,
                            -999.0,
                        )
                    )

                    if (
                        timestamp_seconds
                        - last_ocr
                        < ocr_interval
                    ):
                        continue

                    last_ocr_time_by_track[
                        track_id
                    ] = timestamp_seconds

                # =================================================
                # OCR
                # =================================================

                (
                    raw_text,
                    normalized,
                    ocr_conf,
                ) = _read_plate_with_multiple_variants(
                    plate_crop
                )

                if not normalized:
                    continue

                # ------------------------------------------------
                # VALIDATE
                # ------------------------------------------------

                if not _looks_like_plate(
                    normalized
                ):
                    continue

                try:
                    ocr_conf = float(
                        ocr_conf or 0
                    )
                except Exception:
                    ocr_conf = 0.0

                # ------------------------------------------------
                # Confidence
                # ------------------------------------------------

                if (
                    ocr_conf
                    < config.OCR_CONF_THRESHOLD
                ):
                    continue

                # =================================================
                # VEHICLE KEY
                # =================================================

                vehicle_key = (
                    VehicleEventTracker.vehicle_key(
                        vehicle
                    )
                )

                # =================================================
                # OCR TEMPORAL VOTING
                # =================================================

                ocr_votes.add(
                    track_id,
                    normalized,
                    ocr_conf,
                    timestamp_seconds,
                )

                stable_plate = (
                    ocr_votes.best(
                        track_id
                    )
                )

                if stable_plate:
                    normalized = stable_plate

                # =================================================
                # OBSERVATION
                # =================================================

                observation = PlateObservation(
                    bbox=expanded_bbox,

                    confidence=float(
                        plate.get(
                            "confidence",
                            0.0,
                        )
                    ),

                    raw_text=(
                        raw_text
                    ),

                    normalized_text=(
                        normalized
                    ),

                    ocr_confidence=(
                        ocr_conf
                    ),

                    crop=(
                        plate_crop.copy()
                    ),

                    frame=(
                        frame.copy()
                    ),

                    timestamp_seconds=(
                        timestamp_seconds
                    ),

                    frame_number=(
                        frame_idx
                    ),

                    vehicle_key=(
                        vehicle_key
                    ),
                )

                plate_observations.append(
                    observation
                )

            # =================================================
            # TEMPORAL EVENT TRACKING
            # =================================================

            try:

                finalized_events = (
                    event_tracker.observe_frame(
                        timestamp_seconds,
                        frame_idx,
                        frame,
                        tracked_vehicles,
                        plate_observations,
                    )
                )

            except Exception as error:

                print(
                    "[EVENT TRACKER ERROR]",
                    error,
                )

                finalized_events = []

            # =================================================
            # SAVE EVENTS
            # =================================================

            for event in finalized_events:
                if event.plate_number and not _looks_like_plate(
                    event.plate_number
                ):
                    event.plate_number = None
                    event.raw_ocr_text = None

                # If a plate was detected for this tracked vehicle but no
                # valid OCR result survived, classify the event as OCR failed.
                # Existing successful OCR observations are preserved.
                if event.track_id is not None:
                    event.plate_observation_count = max(
                        event.plate_observation_count,
                        plate_detected_by_track.get(event.track_id, 0),
                    )

                vehicle_events_detected += 1

                saved = _save_detection(
                    db,
                    video,
                    event,
                    video_snapshot_dir,
                    video_plate_dir,
                )

                if saved and event.plate_number:
                    plates_recognized += 1

                db.commit()

                event_time = format_timestamp(
                    event.representative_timestamp_seconds
                )

                print(
                    f"[VEHICLE EVENT]"
                    f" ID={event.track_id}"
                    f" Plate={event.plate_number or 'N/A'}"
                    f" Status="
                    f"{'recognized' if event.plate_number else ('ocr_failed' if event.plate_observation_count > 0 else 'no_plate')}"
                    f" Time={event_time}"
                )

            # =================================================
            # PROGRESS
            # =================================================

            frames_processed += 1

            video.frames_processed = (
                frames_processed
            )

            video.vehicles_detected = (
                len(unique_vehicle_ids)
            )

            video.vehicle_events_detected = (
                vehicle_events_detected
            )

            video.plates_recognized = (
                plates_recognized
            )

            if total_frames > 0:

                progress = (
                    frame_idx
                    / total_frames
                ) * 100.0

                video.progress_percent = min(
                    99.0,
                    max(
                        0.0,
                        progress,
                    ),
                )

            db.commit()

            frame_idx += 1

        # ====================================================
        # RELEASE VIDEO
        # ====================================================

        cap.release()
        cap = None

        # ====================================================
        # FINALIZE REMAINING EVENTS
        # ====================================================

        try:

            final_events = (
                event_tracker.finalize_all()
            )

        except Exception as error:

            print(
                "[FINAL EVENT ERROR]",
                error,
            )

            final_events = []

        # ====================================================
        # SAVE FINAL EVENTS
        # ====================================================

        for event in final_events:

            if event.plate_number and not _looks_like_plate(
                event.plate_number
            ):
                event.plate_number = None
                event.raw_ocr_text = None

            # Preserve the distinction between:
            #   no_plate   -> plate detector found nothing
            #   ocr_failed -> plate detector found a plate, OCR failed
            if event.track_id is not None:
                event.plate_observation_count = max(
                    event.plate_observation_count,
                    plate_detected_by_track.get(event.track_id, 0),
                )

            vehicle_events_detected += 1

            saved = _save_detection(
                db,
                video,
                event,
                video_snapshot_dir,
                video_plate_dir,
            )

            if saved and event.plate_number:
                plates_recognized += 1

            db.commit()

            final_status = (
                "recognized"
                if event.plate_number
                else (
                    "ocr_failed"
                    if event.plate_observation_count > 0
                    else "no_plate"
                )
            )

            print(
                f"[FINAL VEHICLE EVENT]"
                f" ID={event.track_id}"
                f" Plate={event.plate_number or 'N/A'}"
                f" Status={final_status}"
            )

        # ====================================================
        # FINAL DATABASE UPDATE
        # ====================================================

        video.status = "complete"
        video.error_message = None
        video.progress_percent = 100.0

        video.frames_processed = (
            frames_processed
        )

        video.vehicles_detected = (
            len(unique_vehicle_ids)
        )

        video.vehicle_events_detected = (
            vehicle_events_detected
        )

        video.plates_recognized = (
            plates_recognized
        )

        db.commit()

        # ====================================================
        # LOG
        # ====================================================

        print()
        print("=" * 60)
        print(
            f"[VIDEO {video_id}] PROCESSING COMPLETE"
        )
        print("=" * 60)

        print(
            f"Frames processed : "
            f"{frames_processed}"
        )

        print(
            f"Unique vehicles  : "
            f"{len(unique_vehicle_ids)}"
        )

        print(
            f"Plate events     : "
            f"{vehicle_events_detected}"
        )

        print(
            f"Plates recognized: "
            f"{plates_recognized}"
        )

        print(
            f"Processing FPS   : "
            f"{process_fps}"
        )

        print("=" * 60)
        print()

    except Exception as error:

        traceback.print_exc()

        try:

            video = (
                db.query(Video)
                .filter(
                    Video.id == video_id
                )
                .first()
            )

            if video:

                video.status = "failed"

                video.error_message = (
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                db.commit()

        except Exception:
            pass

    finally:

        if cap is not None:

            try:
                cap.release()
            except Exception:
                pass

        db.close()