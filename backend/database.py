"""
SQLite database setup using SQLAlchemy.
"""
import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "storage", "anpr.db")

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    os.makedirs(os.path.join(BASE_DIR, "storage"), exist_ok=True)
    import models  # noqa: F401  (ensures models are registered on Base)
    Base.metadata.create_all(bind=engine)
    _migrate_additional_columns()


def _migrate_additional_columns():
    with engine.begin() as connection:
        inspector = inspect(connection)

        video_columns = {column["name"] for column in inspector.get_columns("videos")}
        if "vehicle_events_detected" not in video_columns:
            connection.execute(
                text(
                    "ALTER TABLE videos ADD COLUMN vehicle_events_detected INTEGER DEFAULT 0"
                )
            )

        detection_columns = {
            column["name"] for column in inspector.get_columns("detections")
        }
        if "track_id" not in detection_columns:
            connection.execute(text("ALTER TABLE detections ADD COLUMN track_id INTEGER"))
        if "event_start_seconds" not in detection_columns:
            connection.execute(
                text("ALTER TABLE detections ADD COLUMN event_start_seconds FLOAT")
            )
        if "event_end_seconds" not in detection_columns:
            connection.execute(
                text("ALTER TABLE detections ADD COLUMN event_end_seconds FLOAT")
            )
