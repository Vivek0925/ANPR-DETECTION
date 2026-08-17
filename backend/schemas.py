"""
Pydantic schemas for API responses.
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class VideoOut(BaseModel):
    id: int
    filename: str
    duration: Optional[float] = None
    fps: Optional[float] = None
    total_frames: Optional[int] = None
    uploaded_at: datetime
    status: str
    error_message: Optional[str] = None
    frames_processed: int
    vehicles_detected: int
    vehicle_events_detected: int
    plates_recognized: int
    progress_percent: float

    class Config:
        from_attributes = True


class VideoStatusOut(BaseModel):
    id: int
    status: str
    progress_percent: float
    frames_processed: int
    vehicles_detected: int
    vehicle_events_detected: int
    plates_recognized: int
    unique_plates: int
    error_message: Optional[str] = None
    duration: Optional[float] = None

    class Config:
        from_attributes = True


class DetectionOut(BaseModel):
    id: int
    video_id: int
    video_filename: str
    plate_number: str
    raw_ocr_text: Optional[str] = None
    timestamp_seconds: float
    formatted_timestamp: str
    frame_number: int
    track_id: Optional[int] = None
    event_start_seconds: Optional[float] = None
    event_end_seconds: Optional[float] = None
    vehicle_type: Optional[str] = None
    ocr_confidence: Optional[float] = None
    detection_confidence: Optional[float] = None
    snapshot_url: Optional[str] = None
    plate_crop_url: Optional[str] = None
    video_url: Optional[str] = None

    class Config:
        from_attributes = True


class SearchResultOut(BaseModel):
    plate_number: str
    total_appearances: int
    results: List[DetectionOut]
