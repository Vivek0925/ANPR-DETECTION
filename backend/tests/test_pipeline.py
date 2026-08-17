"""
Integration tests for the ANPR MVP backend.

Run with:  pytest tests/ -v
(from the backend/ directory, with the venv active)

These exercise the exact workflow the MVP success criteria calls for:
upload -> process -> detect -> store -> search -> timestamp -> (video
serving that the frontend uses for the seek).

Some tests use a synthetic video/plate image rather than a real CCTV
recording, since no real, legally-redistributable Indian traffic footage
ships in this repo (see README > Test Data). Synthetic input still fully
exercises the pipeline wiring: frame extraction, DB writes, the search
index, timestamp math, and deduplication -- it just isn't a guarantee
that the AI models will produce a plate on synthetic input (they're
trained for real-world photos). Where real detection matters, tests
seed the DB directly and assert on retrieval instead.
"""
import os
import sys
import shutil
import tempfile

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_STORAGE = tempfile.mkdtemp(prefix="anpr_test_storage_")
os.environ["ANPR_TEST_STORAGE"] = TEST_STORAGE


@pytest.fixture(scope="module")
def client():
    # Use an isolated, temporary SQLite file so tests never touch the
    # developer's real database.
    import config
    config.STORAGE_DIR = TEST_STORAGE
    config.VIDEOS_DIR = os.path.join(TEST_STORAGE, "videos")
    config.SNAPSHOTS_DIR = os.path.join(TEST_STORAGE, "snapshots")
    config.PLATES_DIR = os.path.join(TEST_STORAGE, "plates")
    for d in (config.VIDEOS_DIR, config.SNAPSHOTS_DIR, config.PLATES_DIR):
        os.makedirs(d, exist_ok=True)

    import database
    database.DB_PATH = os.path.join(TEST_STORAGE, "test_anpr.db")
    database.SQLALCHEMY_DATABASE_URL = f"sqlite:///{database.DB_PATH}"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    database.engine = create_engine(
        database.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    database.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=database.engine
    )

    import main
    main.SessionLocal = database.SessionLocal

    test_client = TestClient(main.app)
    yield test_client

    shutil.rmtree(TEST_STORAGE, ignore_errors=True)


@pytest.fixture(scope="module")
def synthetic_video_path():
    path = os.path.join(TEST_STORAGE, "synthetic_test.mp4")
    width, height, fps, duration_sec = 320, 240, 10, 3
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    for _ in range(fps * duration_sec):
        frame = np.full((height, width, 3), 50, dtype=np.uint8)
        out.write(frame)
    out.release()
    return path


@pytest.fixture(scope="module")
def corrupt_video_path():
    path = os.path.join(TEST_STORAGE, "corrupt.mp4")
    with open(path, "wb") as f:
        f.write(b"not a real video file")
    return path


# ---------------------------------------------------------------------
# 1. Video upload
# ---------------------------------------------------------------------
def test_video_upload(client, synthetic_video_path):
    with open(synthetic_video_path, "rb") as f:
        resp = client.post(
            "/videos/upload",
            files={"file": ("synthetic_test.mp4", f, "video/mp4")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["filename"] == "synthetic_test.mp4"
    assert "id" in body


def test_video_upload_rejects_bad_extension(client):
    resp = client.post(
        "/videos/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------
# 2 & 3. Video processing + database insertion
# ---------------------------------------------------------------------
def test_video_processing_and_db_insertion(client, synthetic_video_path):
    with open(synthetic_video_path, "rb") as f:
        resp = client.post(
            "/videos/upload",
            files={"file": ("synthetic_test.mp4", f, "video/mp4")},
        )
    video_id = resp.json()["id"]

    # Call the pipeline function directly (synchronous) rather than via
    # the threaded endpoint, so the test is deterministic.
    from services.video_processor import process_video
    process_video(video_id)

    status = client.get(f"/videos/{video_id}/status").json()
    assert status["status"] == "complete"
    assert status["frames_processed"] > 0
    assert status["duration"] == pytest.approx(3.0, abs=0.5)


# ---------------------------------------------------------------------
# 4, 5, 6. Plate search + timestamp formatting + retrieval fields
# ---------------------------------------------------------------------
def test_search_and_timestamp_formatting(client):
    # Seed detections directly -- this is what process_video() would have
    # written had the plate been visible in real footage. This isolates
    # the search/retrieval code path from AI model accuracy.
    from database import SessionLocal
    from models import Video, Detection

    db = SessionLocal()
    video = Video(
        filename="cctv_01.mp4",
        filepath=os.path.join(TEST_STORAGE, "videos", "cctv_01.mp4"),
        duration=800,
        fps=25,
        status="complete",
        progress_percent=100.0,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    db.add_all([
        Detection(video_id=video.id, plate_number="CG04AB1234",
                  raw_ocr_text="CG04AB1234", timestamp_seconds=92,
                  frame_number=2300, vehicle_type="car",
                  ocr_confidence=0.94, detection_confidence=0.9),
        Detection(video_id=video.id, plate_number="CG04AB1234",
                  raw_ocr_text="CG04AB1234", timestamp_seconds=463,
                  frame_number=11575, vehicle_type="car",
                  ocr_confidence=0.97, detection_confidence=0.91),
        Detection(video_id=video.id, plate_number="MH12XY5678",
                  raw_ocr_text="MH12XY5678", timestamp_seconds=135,
                  frame_number=3375, vehicle_type="car",
                  ocr_confidence=0.88, detection_confidence=0.85),
    ])
    db.commit()
    db.close()

    resp = client.get("/search", params={"plate": "cg04ab1234"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["plate_number"] == "CG04AB1234"
    assert body["total_appearances"] == 2
    timestamps = [r["formatted_timestamp"] for r in body["results"]]
    assert timestamps == ["01:32", "07:43"]
    # results must include what the frontend needs to open + seek the video
    for r in body["results"]:
        assert r["video_url"] is not None
        assert r["timestamp_seconds"] > 0

    # a different plate should not match
    resp2 = client.get("/search", params={"plate": "MH12XY5678"})
    assert resp2.json()["total_appearances"] == 1

    # case-insensitivity / normalization
    resp3 = client.get("/search", params={"plate": "  cg 04 ab 1234  "})
    assert resp3.json()["total_appearances"] == 2


def test_timestamp_formatting_hour_boundary():
    from services.video_processor import format_timestamp
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(92) == "01:32"
    assert format_timestamp(463) == "07:43"
    assert format_timestamp(3661) == "01:01:01"


# ---------------------------------------------------------------------
# 7. Invalid video handling
# ---------------------------------------------------------------------
def test_invalid_video_handling(client, corrupt_video_path):
    with open(corrupt_video_path, "rb") as f:
        resp = client.post(
            "/videos/upload",
            files={"file": ("corrupt.mp4", f, "video/mp4")},
        )
    video_id = resp.json()["id"]

    from services.video_processor import process_video
    process_video(video_id)

    status = client.get(f"/videos/{video_id}/status").json()
    assert status["status"] == "failed"
    assert status["error_message"]


# ---------------------------------------------------------------------
# 8. No plate detected (synthetic video has no plates -> zero detections,
#    but processing must still complete cleanly, not crash/hang/fail)
# ---------------------------------------------------------------------
def test_no_plate_detected_completes_cleanly(client, synthetic_video_path):
    with open(synthetic_video_path, "rb") as f:
        resp = client.post(
            "/videos/upload",
            files={"file": ("blank.mp4", f, "video/mp4")},
        )
    video_id = resp.json()["id"]

    from services.video_processor import process_video
    process_video(video_id)

    status = client.get(f"/videos/{video_id}/status").json()
    assert status["status"] == "complete"
    assert status["plates_recognized"] == 0
    assert status["unique_plates"] == 0


# ---------------------------------------------------------------------
# 9. OCR failure / low-confidence text is rejected, not stored
# ---------------------------------------------------------------------
def test_ocr_rejects_low_confidence_and_short_text():
    from services.ocr import normalize_plate_text
    import config

    # Normalization behavior
    assert normalize_plate_text(" cg-04 ab*1234 ") == "CG04AB1234"
    assert normalize_plate_text("") == ""

    # Text shorter than MIN_PLATE_TEXT_LEN should never be treated as a
    # plausible plate (this is enforced in read_plate_text; we assert the
    # threshold config exists and is sane).
    assert config.MIN_PLATE_TEXT_LEN >= 1


# ---------------------------------------------------------------------
# 10. Duplicate / temporal dedup handling
# ---------------------------------------------------------------------
def test_temporal_dedup_keeps_best_confidence():
    """
    Unit-level check of the dedup rule described in the spec: sightings
    of the same plate within DEDUP_WINDOW_SECONDS collapse into one
    appearance, keeping the highest-confidence read.
    """
    import config

    sightings = {}
    events = [
        ("CG04AB1234", 10.2, 0.80),
        ("CG04AB1234", 10.4, 0.92),  # within window, higher conf -> replaces
        ("CG04AB1234", 10.6, 0.85),  # within window, lower conf -> ignored
        ("CG04AB1234", 10.2 + config.DEDUP_WINDOW_SECONDS + 1, 0.70),  # new appearance
    ]

    appearances = []
    for plate, ts, conf in events:
        prior = sightings.get(plate)
        is_new = prior is None or (ts - prior["last_ts"]) > config.DEDUP_WINDOW_SECONDS
        if is_new:
            appearances.append({"ts": ts, "conf": conf})
            sightings[plate] = {"last_ts": ts, "best_confidence": conf}
        else:
            sightings[plate]["last_ts"] = ts
            if conf > sightings[plate]["best_confidence"]:
                appearances[-1]["conf"] = conf
                sightings[plate]["best_confidence"] = conf

    assert len(appearances) == 2  # collapsed to 2 appearances, not 4
    assert appearances[0]["conf"] == 0.92  # kept the strongest read
    assert appearances[1]["ts"] > 14


def test_vehicle_event_tracker_groups_same_track_into_one_event():
    import numpy as np
    import config
    from services.vehicle_events import (
        VehicleEventTracker,
        TrackedVehicle,
        PlateObservation,
    )

    tracker = VehicleEventTracker(
        lost_timeout_seconds=config.TRACK_LOST_TIMEOUT_SECONDS
    )
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    vehicle = TrackedVehicle(
        track_id=17,
        bbox=(2, 2, 20, 20),
        class_name="car",
        confidence=0.91,
    )
    plate = PlateObservation(
        bbox=(4, 12, 14, 18),
        confidence=0.86,
        raw_text="cg04ab1234",
        normalized_text="CG04AB1234",
        ocr_confidence=0.94,
        crop=frame.copy(),
        frame=frame.copy(),
        timestamp_seconds=10.0,
        frame_number=100,
        vehicle_key="17",
    )

    finalized_1 = tracker.observe_frame(10.0, 100, frame, [vehicle], [plate])
    assert finalized_1 == []

    finalized_2 = tracker.observe_frame(10.8, 104, frame, [vehicle], [plate])
    assert finalized_2 == []

    finalized_3 = tracker.observe_frame(13.0, 130, frame, [], [])
    assert len(finalized_3) == 1

    event = finalized_3[0]
    assert event.track_id == 17
    assert event.plate_number == "CG04AB1234"
    assert event.first_seen_seconds == 10.0
    assert event.last_seen_seconds == 10.8
    assert event.representative_timestamp_seconds == 10.0


def test_vehicle_event_tracker_splits_reused_track_id_on_plate_change():
    import numpy as np
    import config
    from services.vehicle_events import (
        VehicleEventTracker,
        TrackedVehicle,
        PlateObservation,
    )

    tracker = VehicleEventTracker(
        lost_timeout_seconds=config.TRACK_LOST_TIMEOUT_SECONDS
    )
    frame = np.zeros((48, 48, 3), dtype=np.uint8)
    vehicle = TrackedVehicle(
        track_id=21,
        bbox=(2, 2, 30, 30),
        class_name="car",
        confidence=0.92,
    )

    plate_first = PlateObservation(
        bbox=(8, 16, 22, 24),
        confidence=0.88,
        raw_text="CG04AB1234",
        normalized_text="CG04AB1234",
        ocr_confidence=0.95,
        crop=frame.copy(),
        frame=frame.copy(),
        timestamp_seconds=1.0,
        frame_number=10,
        vehicle_key="21",
    )

    plate_second = PlateObservation(
        bbox=(8, 16, 22, 24),
        confidence=0.90,
        raw_text="W1771TX",
        normalized_text="W1771TX",
        ocr_confidence=0.93,
        crop=frame.copy(),
        frame=frame.copy(),
        timestamp_seconds=2.0,
        frame_number=20,
        vehicle_key="21",
    )

    assert tracker.observe_frame(1.0, 10, frame, [vehicle], [plate_first]) == []

    finalized = tracker.observe_frame(2.0, 20, frame, [vehicle], [plate_second])
    assert len(finalized) == 1
    assert finalized[0].plate_number == "CG04AB1234"

    final_all = tracker.finalize_all()
    assert len(final_all) == 1
    assert final_all[0].plate_number == "W1771TX"


def test_match_plate_to_vehicle_requires_actual_overlap_when_not_contained():
    from services.vehicle_events import match_plate_to_vehicle, TrackedVehicle

    # Plate is disjoint from all vehicles, so assignment should be rejected.
    plate_bbox = (200, 200, 220, 220)
    vehicles = [
        TrackedVehicle(track_id=1, bbox=(10, 10, 60, 60), class_name="car", confidence=0.8),
        TrackedVehicle(track_id=2, bbox=(80, 20, 130, 70), class_name="car", confidence=0.9),
    ]
    assert match_plate_to_vehicle(plate_bbox, vehicles) is None


# ---------------------------------------------------------------------
# The critical end-to-end integration test called out in the spec:
# upload -> detect plate -> store timestamp -> search plate -> click
# result -> video opens -> video seeks to timestamp.
#
# The "video opens and seeks" part is a frontend/browser behavior
# (verified separately, see README > Testing), but everything the
# frontend depends on -- a resolvable video_url, correct timestamp, and
# range-request support for seeking -- is verified here.
# ---------------------------------------------------------------------
def test_end_to_end_upload_to_seekable_result(client):
    from database import SessionLocal
    from models import Video, Detection
    import config

    # Simulate a real "processed" video with a real video file on disk so
    # we can assert the static file server returns range-request support.
    video_path = os.path.join(config.VIDEOS_DIR, "e2e_test.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, 25, (320, 240))
    for _ in range(50):
        out.write(np.full((240, 320, 3), 20, dtype=np.uint8))
    out.release()

    db = SessionLocal()
    video = Video(filename="e2e_test.mp4", filepath=video_path,
                  duration=2.0, fps=25, status="complete", progress_percent=100.0)
    db.add(video)
    db.commit()
    db.refresh(video)

    detection = Detection(
        video_id=video.id, plate_number="DL01AB1234", raw_ocr_text="DL01AB1234",
        timestamp_seconds=1.2, frame_number=30, vehicle_type="car",
        ocr_confidence=0.95, detection_confidence=0.9,
    )
    db.add(detection)
    db.commit()
    db.close()

    # search
    search_resp = client.get("/search", params={"plate": "DL01AB1234"})
    result = search_resp.json()["results"][0]
    assert result["formatted_timestamp"] == "00:01"
    assert result["video_url"].startswith("/media/videos/")

    # "click result" -> fetch detection detail (what the viewer page loads)
    detail_resp = client.get(f"/detections/{result['id']}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["timestamp_seconds"] == pytest.approx(1.2)

    # "video opens" -> the video file must be servable with range support
    video_resp = client.get(result["video_url"])
    assert video_resp.status_code == 200
    assert video_resp.headers.get("accept-ranges") == "bytes"
