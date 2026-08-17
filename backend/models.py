"""
SQLAlchemy ORM models: videos, detections.
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    duration = Column(Float, nullable=True)          # seconds
    fps = Column(Float, nullable=True)
    total_frames = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # processing status: pending | processing | complete | failed
    status = Column(String, default="pending")
    error_message = Column(String, nullable=True)

    frames_processed = Column(Integer, default=0)
    vehicles_detected = Column(Integer, default=0)  # raw frame-level detections
    vehicle_events_detected = Column(Integer, default=0)  # tracked appearances
    plates_recognized = Column(Integer, default=0)
    progress_percent = Column(Float, default=0.0)

    detections = relationship(
        "Detection", back_populates="video", cascade="all, delete-orphan"
    )


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)

    plate_number = Column(String, nullable=False)       # normalized
    raw_ocr_text = Column(String, nullable=True)

    timestamp_seconds = Column(Float, nullable=False)
    frame_number = Column(Integer, nullable=False)

    track_id = Column(Integer, nullable=True)
    event_start_seconds = Column(Float, nullable=True)
    event_end_seconds = Column(Float, nullable=True)

    vehicle_type = Column(String, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    detection_confidence = Column(Float, nullable=True)

    snapshot_path = Column(String, nullable=True)
    plate_crop_path = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="detections")


# Index to make plate search fast
Index("ix_detections_plate_number", Detection.plate_number)
