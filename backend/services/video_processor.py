"""
Core AI pipeline:

Video -> OpenCV frame extraction -> vehicle detection -> plate detection
      -> plate crop -> preprocessing -> OCR -> normalization
      -> timestamp calc -> temporal dedup -> SQLite storage
"""
import os
import time
import traceback

import cv2

import config
from database import SessionLocal
from models import Video, Detection
from services.vehicle_detector import VehicleDetector
from services.plate_detector import PlateDetector
from services.preprocessing import preprocess_plate_crop
from services.ocr import read_plate_text_best
from services.vehicle_events import (
    TrackedVehicle,
    PlateObservation,
    VehicleEventTracker,
    build_snapshot_frame,
    match_plate_to_vehicle,
)

# Lazily-created singletons so we don't reload the (heavy) models per video.
_vehicle_detector = None
_plate_detector = None


def _get_detectors():
    global _vehicle_detector, _plate_detector
    if _vehicle_detector is None:
        _vehicle_detector = VehicleDetector()
    if _plate_detector is None:
        _plate_detector = PlateDetector()
    return _vehicle_detector, _plate_detector


def format_timestamp(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _vehicle_type_for_bbox(plate_bbox, vehicles):
    """Assign the plate to the vehicle whose box contains/overlaps it most,
    for a friendlier vehicle_type label. Falls back to 'vehicle' if unknown.
    """
    px1, py1, px2, py2 = plate_bbox
    pcx, pcy = (px1 + px2) / 2, (py1 + py2) / 2
    for v in vehicles:
        vx1, vy1, vx2, vy2 = v["bbox"]
        if vx1 <= pcx <= vx2 and vy1 <= pcy <= vy2:
            return v["class_name"]
    return "vehicle"


def _sanitize_plate_for_filename(plate_number: str) -> str:
    return "".join(ch for ch in plate_number if ch.isalnum()).upper() or "plate"


def _make_tracked_vehicle(vehicle: dict) -> TrackedVehicle:
    return TrackedVehicle(
        track_id=vehicle.get("track_id"),
        bbox=vehicle["bbox"],
        class_name=vehicle["class_name"],
        confidence=vehicle["confidence"],
    )


def process_video(video_id: int):
    """
    Runs the full pipeline for a video already saved on disk, updating
    progress fields on the Video row as it goes and writing Detection rows.
    This is designed to be called as a background task (thread).
    """
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return

        video.status = "processing"
        video.error_message = None
        db.commit()

        try:
            vehicle_detector, plate_detector = _get_detectors()
        except FileNotFoundError as e:
            video.status = "failed"
            video.error_message = str(e)
            db.commit()
            return

        vehicle_detector.reset_tracker()

        cap = cv2.VideoCapture(video.filepath)
        if not cap.isOpened():
            video.status = "failed"
            video.error_message = "Could not open uploaded video file (unsupported or corrupt)."
            db.commit()
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        duration = total_frames / fps if fps > 0 else 0.0

        video.fps = fps
        video.total_frames = total_frames
        video.duration = duration
        db.commit()

        # Only sample PROCESS_FPS frames per second of video, not every frame.
        frame_interval = max(1, int(round(fps / config.PROCESS_FPS)))

        event_tracker = VehicleEventTracker(config.TRACK_LOST_TIMEOUT_SECONDS)

        frame_idx = 0
        frames_processed = 0
        vehicles_detected = 0
        vehicle_events_detected = 0
        plates_recognized = 0

        video_snapshot_dir = os.path.join(config.SNAPSHOTS_DIR, str(video.id))
        video_plate_dir = os.path.join(config.PLATES_DIR, str(video.id))
        os.makedirs(video_snapshot_dir, exist_ok=True)
        os.makedirs(video_plate_dir, exist_ok=True)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp_seconds = frame_idx / fps

                vehicles = vehicle_detector.track(frame)
                vehicles_detected += len(vehicles)

                plates = plate_detector.detect(frame)
                tracked_vehicles = [_make_tracked_vehicle(vehicle) for vehicle in vehicles]
                plate_observations = []

                for plate in plates:
                    x1, y1, x2, y2 = plate["bbox"]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
                    if x2 <= x1 or y2 <= y1:
                        continue
                    plate_crop = frame[y1:y2, x1:x2]

                    processed_crop = preprocess_plate_crop(plate_crop)
                    raw_text, normalized, ocr_conf = read_plate_text_best(
                        [processed_crop, plate_crop]
                    )

                    if not normalized or ocr_conf < config.OCR_CONF_THRESHOLD:
                        continue

                    vehicle = match_plate_to_vehicle(plate["bbox"], tracked_vehicles)
                    if vehicle is None:
                        continue

                    plate_observations.append(
                        PlateObservation(
                            bbox=plate["bbox"],
                            confidence=plate["confidence"],
                            raw_text=raw_text,
                            normalized_text=normalized,
                            ocr_confidence=ocr_conf,
                            crop=processed_crop,
                            frame=frame,
                            timestamp_seconds=timestamp_seconds,
                            frame_number=frame_idx,
                            vehicle_key=VehicleEventTracker.vehicle_key(vehicle),
                        )
                    )

                finalized_events = event_tracker.observe_frame(
                    timestamp_seconds,
                    frame_idx,
                    frame,
                    tracked_vehicles,
                    plate_observations,
                )

                for event in finalized_events:
                    vehicle_events_detected += 1
                    if not event.plate_number:
                        continue

                    plate_slug = _sanitize_plate_for_filename(event.plate_number)
                    plate_crop_path = None
                    snapshot_path = None

                    if event.plate_crop is not None:
                        plate_crop_filename = (
                            f"{plate_slug}_track{event.track_id or 'na'}_{event.representative_frame_number}.jpg"
                        )
                        plate_crop_path = os.path.join(video_plate_dir, plate_crop_filename)
                        cv2.imwrite(plate_crop_path, event.plate_crop)

                    snapshot_frame = build_snapshot_frame(event, config.DEBUG_TRACKING)
                    if snapshot_frame is not None:
                        snapshot_filename = (
                            f"{plate_slug}_track{event.track_id or 'na'}_{event.representative_frame_number}.jpg"
                        )
                        snapshot_path = os.path.join(video_snapshot_dir, snapshot_filename)
                        cv2.imwrite(snapshot_path, snapshot_frame)

                    detection = Detection(
                        video_id=video.id,
                        plate_number=event.plate_number,
                        raw_ocr_text=event.raw_ocr_text,
                        timestamp_seconds=event.representative_timestamp_seconds,
                        frame_number=event.representative_frame_number,
                        track_id=event.track_id,
                        event_start_seconds=event.first_seen_seconds,
                        event_end_seconds=event.last_seen_seconds,
                        vehicle_type=event.vehicle_type,
                        ocr_confidence=event.ocr_confidence,
                        detection_confidence=event.plate_confidence,
                        snapshot_path=snapshot_path,
                        plate_crop_path=plate_crop_path,
                    )
                    db.add(detection)
                    db.commit()
                    db.refresh(detection)
                    plates_recognized += 1

                frames_processed += 1

                # progress update
                video.frames_processed = frames_processed
                video.vehicles_detected = vehicles_detected
                video.vehicle_events_detected = vehicle_events_detected
                video.plates_recognized = plates_recognized
                if total_frames > 0:
                    video.progress_percent = min(99.0, (frame_idx / total_frames) * 100)
                db.commit()

            frame_idx += 1

        cap.release()

        for event in event_tracker.finalize_all():
            vehicle_events_detected += 1
            if not event.plate_number:
                continue

            plate_slug = _sanitize_plate_for_filename(event.plate_number)
            plate_crop_path = None
            snapshot_path = None

            if event.plate_crop is not None:
                plate_crop_filename = (
                    f"{plate_slug}_track{event.track_id or 'na'}_{event.representative_frame_number}.jpg"
                )
                plate_crop_path = os.path.join(video_plate_dir, plate_crop_filename)
                cv2.imwrite(plate_crop_path, event.plate_crop)

            snapshot_frame = build_snapshot_frame(event, config.DEBUG_TRACKING)
            if snapshot_frame is not None:
                snapshot_filename = (
                    f"{plate_slug}_track{event.track_id or 'na'}_{event.representative_frame_number}.jpg"
                )
                snapshot_path = os.path.join(video_snapshot_dir, snapshot_filename)
                cv2.imwrite(snapshot_path, snapshot_frame)

            detection = Detection(
                video_id=video.id,
                plate_number=event.plate_number,
                raw_ocr_text=event.raw_ocr_text,
                timestamp_seconds=event.representative_timestamp_seconds,
                frame_number=event.representative_frame_number,
                track_id=event.track_id,
                event_start_seconds=event.first_seen_seconds,
                event_end_seconds=event.last_seen_seconds,
                vehicle_type=event.vehicle_type,
                ocr_confidence=event.ocr_confidence,
                detection_confidence=event.plate_confidence,
                snapshot_path=snapshot_path,
                plate_crop_path=plate_crop_path,
            )
            db.add(detection)
            db.commit()
            db.refresh(detection)
            plates_recognized += 1

        video.status = "complete"
        video.error_message = None
        video.progress_percent = 100.0
        video.frames_processed = frames_processed
        video.vehicles_detected = vehicles_detected
        video.vehicle_events_detected = vehicle_events_detected
        video.plates_recognized = plates_recognized
        db.commit()

    except Exception as e:
        traceback.print_exc()
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = "failed"
                video.error_message = f"{type(e).__name__}: {e}"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
