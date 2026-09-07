"""
AI-Based Intelligent Vehicle Surveillance and CCTV Video Retrieval System
FastAPI Backend
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
from database import init_db, get_db
from models import Video, Detection
from schemas import (
    VideoOut,
    VideoStatusOut,
    DetectionOut,
    SearchResultOut,
)
from services.video_processor import process_video, format_timestamp
from services.search import search_by_plate


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AI Vehicle Surveillance & CCTV Retrieval",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE
# ============================================================

init_db()


# ============================================================
# STATIC MEDIA
# ============================================================

app.mount(
    "/media/videos",
    StaticFiles(directory=config.VIDEOS_DIR),
    name="videos",
)

app.mount(
    "/media/snapshots",
    StaticFiles(directory=config.SNAPSHOTS_DIR),
    name="snapshots",
)

app.mount(
    "/media/plates",
    StaticFiles(directory=config.PLATES_DIR),
    name="plates",
)


# ============================================================
# CONSTANTS
# ============================================================

ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
}


# ============================================================
# HELPERS
# ============================================================

def _to_detection_out(
    detection: Detection,
    video: Video,
) -> DetectionOut:

    snapshot_url = None

    if (
        detection.snapshot_path
        and os.path.exists(detection.snapshot_path)
    ):
        rel = os.path.relpath(
            detection.snapshot_path,
            config.SNAPSHOTS_DIR,
        )

        snapshot_url = f"/media/snapshots/{rel}"


    plate_crop_url = None

    if (
        detection.plate_crop_path
        and os.path.exists(detection.plate_crop_path)
    ):
        rel = os.path.relpath(
            detection.plate_crop_path,
            config.PLATES_DIR,
        )

        plate_crop_url = f"/media/plates/{rel}"


    video_url = (
        f"/media/videos/"
        f"{os.path.basename(video.filepath)}"
    )


    return DetectionOut(
        id=detection.id,
        video_id=detection.video_id,

        video_filename=video.filename,

        plate_number=detection.plate_number,

        raw_ocr_text=detection.raw_ocr_text,

        timestamp_seconds=detection.timestamp_seconds,

        formatted_timestamp=format_timestamp(
            detection.timestamp_seconds
        ),

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


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "ok",
        "service": "anpr-backend",
        "message": "AI Vehicle Surveillance API is running",
    }


# ============================================================
# UPLOAD VIDEO
# ============================================================

@app.post(
    "/videos/upload",
    response_model=VideoOut,
)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided",
        )


    ext = os.path.splitext(
        file.filename
    )[1].lower()


    if ext not in ALLOWED_VIDEO_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed: "
                f"{sorted(ALLOWED_VIDEO_EXTENSIONS)}"
            ),
        )


    safe_name = (
        f"{uuid.uuid4().hex}{ext}"
    )


    dest_path = os.path.join(
        config.VIDEOS_DIR,
        safe_name,
    )


    try:

        with open(dest_path, "wb") as f:

            shutil.copyfileobj(
                file.file,
                f,
            )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Could not save video: {exc}",
        )


    video = Video(
        filename=file.filename,
        filepath=dest_path,
        status="pending",
    )


    db.add(video)

    db.commit()

    db.refresh(video)


    return video


# ============================================================
# START PROCESSING
# ============================================================

@app.post(
    "/videos/{video_id}/process"
)
def start_processing(
    video_id: int,
    db: Session = Depends(get_db),
):

    video = (
        db.query(Video)
        .filter(Video.id == video_id)
        .first()
    )


    if not video:

        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )


    if video.status == "processing":

        return {
            "message": "Already processing",
            "video_id": video_id,
        }


    # Reset old detections

    db.query(Detection).filter(
        Detection.video_id == video_id
    ).delete()


    video.status = "pending"

    video.frames_processed = 0

    video.vehicles_detected = 0

    video.vehicle_events_detected = 0

    video.plates_recognized = 0

    video.progress_percent = 0.0

    video.error_message = None


    db.commit()


    thread = threading.Thread(
        target=process_video,
        args=(video_id,),
        daemon=True,
    )

    thread.start()


    return {
        "message": "Processing started",
        "video_id": video_id,
    }


# ============================================================
# LIST VIDEOS
# ============================================================

@app.get(
    "/videos",
    response_model=list[VideoOut],
)
def list_videos(
    db: Session = Depends(get_db),
):

    return (
        db.query(Video)
        .order_by(Video.uploaded_at.desc())
        .all()
    )


# ============================================================
# GET VIDEO
# ============================================================

@app.get(
    "/videos/{video_id}",
    response_model=VideoOut,
)
def get_video(
    video_id: int,
    db: Session = Depends(get_db),
):

    video = (
        db.query(Video)
        .filter(Video.id == video_id)
        .first()
    )


    if not video:

        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )


    return video


# ============================================================
# VIDEO STATUS
# ============================================================

@app.get(
    "/videos/{video_id}/status",
    response_model=VideoStatusOut,
)
def get_video_status(
    video_id: int,
    db: Session = Depends(get_db),
):

    video = (
        db.query(Video)
        .filter(Video.id == video_id)
        .first()
    )


    if not video:

        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )


    unique_plates = (
        db.query(
            Detection.plate_number
        )
        .filter(
            Detection.video_id == video_id
        )
        .filter(
            Detection.plate_number.isnot(None)
        )
        .filter(
            Detection.plate_number != ""
        )
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


# ============================================================
# SEARCH PLATE
# ============================================================

@app.get(
    "/search",
    response_model=SearchResultOut,
)
def search(
    plate: str = Query(
        ...,
        min_length=1,
    ),
    db: Session = Depends(get_db),
):

    normalized_query, results = (
        search_by_plate(
            db,
            plate,
        )
    )


    detection_outs = [
        _to_detection_out(
            detection,
            video,
        )
        for detection, video in results
    ]


    return SearchResultOut(
        plate_number=normalized_query,

        total_appearances=len(
            detection_outs
        ),

        results=detection_outs,
    )


# ============================================================
# RECENT DETECTIONS
# ============================================================

@app.get(
    "/detections/recent",
    response_model=list[DetectionOut],
)
def recent_detections(
    limit: int = Query(
        6,
        ge=1,
        le=50,
    ),
    db: Session = Depends(get_db),
):

    rows = (
        db.query(
            Detection,
            Video,
        )
        .join(
            Video,
            Detection.video_id == Video.id,
        )
        .order_by(
            Detection.id.desc()
        )
        .limit(limit)
        .all()
    )

    return [
        _to_detection_out(
            detection,
            video,
        )
        for detection, video in rows
    ]


# ============================================================
# GET DETECTION BY ID
# ============================================================

@app.get(
    "/detections/{detection_id}",
    response_model=DetectionOut,
)
def get_detection(
    detection_id: int,
    db: Session = Depends(get_db),
):

    row = (
        db.query(
            Detection,
            Video,
        )
        .join(
            Video,
            Detection.video_id == Video.id,
        )
        .filter(
            Detection.id == detection_id
        )
        .first()
    )

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Detection not found",
        )

    detection, video = row

    return _to_detection_out(
        detection,
        video,
    )

    row = (
        db.query(
            Detection,
            Video,
        )
        .join(
            Video,
            Detection.video_id == Video.id,
        )
        .filter(
            Detection.id == detection_id
        )
        .first()
    )


    if not row:

        raise HTTPException(
            status_code=404,
            detail="Detection not found",
        )


    detection, video = row


    return _to_detection_out(
        detection,
        video,
    )


# ============================================================
# DASHBOARD STATISTICS
# ============================================================

@app.get("/dashboard/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
):

    videos = db.query(Video).all()


    total_videos = len(videos)


    total_vehicles = sum(
        (video.vehicles_detected or 0)
        for video in videos
    )


    total_plates = sum(
        (video.plates_recognized or 0)
        for video in videos
    )


    unique_plates = (
        db.query(
            Detection.plate_number
        )
        .filter(
            Detection.plate_number.isnot(None)
        )
        .filter(
            Detection.plate_number != ""
        )
        .distinct()
        .count()
    )


    processing = sum(
        1
        for video in videos
        if video.status == "processing"
    )


    completed = sum(
        1
        for video in videos
        if video.status == "completed"
    )


    failed = sum(
        1
        for video in videos
        if video.status == "failed"
    )


    return {

        "total_videos": total_videos,

        "total_vehicles": total_vehicles,

        "total_plates": total_plates,

        "unique_plates": unique_plates,

        "processing": processing,

        "completed": completed,

        "failed": failed,
    }


# ============================================================
# RECENT DETECTIONS
# ============================================================

@app.get(
    "/detections/recent",
    response_model=list[DetectionOut],
)
def recent_detections(
    limit: int = Query(
        6,
        ge=1,
        le=50,
    ),
    db: Session = Depends(get_db),
):

    rows = (
        db.query(
            Detection,
            Video,
        )
        .join(
            Video,
            Detection.video_id == Video.id,
        )
        .order_by(
            Detection.id.desc()
        )
        .limit(limit)
        .all()
    )


    return [
        _to_detection_out(
            detection,
            video,
        )
        for detection, video in rows
    ]