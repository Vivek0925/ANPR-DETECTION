"""
AI-Based Intelligent Vehicle Surveillance and CCTV Video Retrieval System
MVP backend (FastAPI).
"""
import os
import shutil
import threading
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import config
from database import init_db, get_db, SessionLocal
from models import Video, Detection
from schemas import VideoOut, VideoStatusOut, DetectionOut, SearchResultOut
from services.video_processor import process_video, format_timestamp
from services.search import search_by_plate

app = FastAPI(title="AI Vehicle Surveillance & CCTV Retrieval MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP only - no auth, so this is fine for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# Serve raw files (videos, snapshots, plate crops) statically so the
# frontend video player and <img> tags can load them directly.
app.mount("/media/videos", StaticFiles(directory=config.VIDEOS_DIR), name="videos")
app.mount("/media/snapshots", StaticFiles(directory=config.SNAPSHOTS_DIR), name="snapshots")
app.mount("/media/plates", StaticFiles(directory=config.PLATES_DIR), name="plates")

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def _to_detection_out(detection: Detection, video: Video, request_base: str = "") -> DetectionOut:
    snapshot_url = None
    if detection.snapshot_path and os.path.exists(detection.snapshot_path):
        rel = os.path.relpath(detection.snapshot_path, config.SNAPSHOTS_DIR)
        snapshot_url = f"/media/snapshots/{rel}"

    plate_crop_url = None
    if detection.plate_crop_path and os.path.exists(detection.plate_crop_path):
        rel = os.path.relpath(detection.plate_crop_path, config.PLATES_DIR)
        plate_crop_url = f"/media/plates/{rel}"

    video_url = f"/media/videos/{os.path.basename(video.filepath)}"

    return DetectionOut(
        id=detection.id,
        video_id=detection.video_id,
        video_filename=video.filename,
        plate_number=detection.plate_number,
        raw_ocr_text=detection.raw_ocr_text,
        timestamp_seconds=detection.timestamp_seconds,
        formatted_timestamp=format_timestamp(detection.timestamp_seconds),
        frame_number=detection.frame_number,
        track_id=detection.track_id,
        event_start_seconds=detection.event_start_seconds,
        event_end_seconds=detection.event_end_seconds,
        vehicle_type=detection.vehicle_type,
        ocr_confidence=detection.ocr_confidence,
        detection_confidence=detection.detection_confidence,
        snapshot_url=snapshot_url,
        plate_crop_url=plate_crop_url,
        video_url=video_url,
    )


@app.get("/")
def root():
    return {"status": "ok", "service": "anpr-mvp-backend"}


@app.post("/videos/upload", response_model=VideoOut)
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_VIDEO_EXTENSIONS)}",
        )

    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(config.VIDEOS_DIR, safe_name)

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    video = Video(
        filename=file.filename,
        filepath=dest_path,
        status="pending",
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@app.post("/videos/{video_id}/process")
def start_processing(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "Video not found")
    if video.status == "processing":
        return {"message": "Already processing", "video_id": video_id}

    # Reset any prior detections if re-processing.
    db.query(Detection).filter(Detection.video_id == video_id).delete()
    video.status = "pending"
    video.frames_processed = 0
    video.vehicles_detected = 0
    video.vehicle_events_detected = 0
    video.plates_recognized = 0
    video.progress_percent = 0.0
    video.error_message = None
    db.commit()

    # Simple background task: a daemon thread. Good enough for an MVP demo
    # (no Celery/RabbitMQ needed). Each thread opens its own DB session.
    thread = threading.Thread(target=process_video, args=(video_id,), daemon=True)
    thread.start()

    return {"message": "Processing started", "video_id": video_id}


@app.get("/videos", response_model=list[VideoOut])
def list_videos(db: Session = Depends(get_db)):
    return db.query(Video).order_by(Video.uploaded_at.desc()).all()


@app.get("/videos/{video_id}", response_model=VideoOut)
def get_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "Video not found")
    return video


@app.get("/videos/{video_id}/status", response_model=VideoStatusOut)
def get_video_status(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "Video not found")

    unique_plates = (
        db.query(Detection.plate_number)
        .filter(Detection.video_id == video_id)
        .distinct()
        .count()
    )

    return VideoStatusOut(
        id=video.id,
        status=video.status,
        progress_percent=video.progress_percent,
        frames_processed=video.frames_processed,
        vehicles_detected=video.vehicles_detected,
        vehicle_events_detected=video.vehicle_events_detected,
        plates_recognized=video.plates_recognized,
        unique_plates=unique_plates,
        error_message=video.error_message,
        duration=video.duration,
    )


@app.get("/search", response_model=SearchResultOut)
def search(plate: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    normalized_query, results = search_by_plate(db, plate)

    detection_outs = [_to_detection_out(det, vid) for det, vid in results]

    return SearchResultOut(
        plate_number=normalized_query,
        total_appearances=len(detection_outs),
        results=detection_outs,
    )


@app.get("/detections/{detection_id}", response_model=DetectionOut)
def get_detection(detection_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(Detection, Video)
        .join(Video, Detection.video_id == Video.id)
        .filter(Detection.id == detection_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Detection not found")
    detection, video = row
    return _to_detection_out(detection, video)
