"""
Central configuration for the ANPR MVP pipeline.
Override any of these via environment variables (see .env.example).
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STORAGE_DIR = os.path.join(BASE_DIR, "storage")
VIDEOS_DIR = os.path.join(STORAGE_DIR, "videos")
SNAPSHOTS_DIR = os.path.join(STORAGE_DIR, "snapshots")
PLATES_DIR = os.path.join(STORAGE_DIR, "plates")

for _d in (STORAGE_DIR, VIDEOS_DIR, SNAPSHOTS_DIR, PLATES_DIR):
    os.makedirs(_d, exist_ok=True)

MODELS_DIR = os.path.join(BASE_DIR, "models")

# Where the vehicle detector (standard COCO YOLOv8n) lives.
# Auto-downloaded by ultralytics on first use if not present.
VEHICLE_MODEL_PATH = os.environ.get(
    "VEHICLE_MODEL_PATH", os.path.join(MODELS_DIR, "yolov8n.pt")
)

# Where the license-plate detector lives. This is NOT the stock COCO model —
# COCO has no "license plate" class. See README for provenance / download
# instructions. Configurable so you can swap in your own trained weights.
PLATE_MODEL_PATH = os.environ.get(
    "PLATE_MODEL_PATH", os.path.join(MODELS_DIR, "license_plate_detector.pt")
)

# How many frames per second of VIDEO TIME to actually run detection on.
# Not every frame, but enough to keep moving vehicles visible.
PROCESS_FPS = float(os.environ.get("PROCESS_FPS", "5"))

# Vehicle detector confidence threshold. YOLO_CONFIDENCE is the preferred
# env var, VEHICLE_CONF_THRESHOLD is kept for backwards compatibility.
YOLO_CONFIDENCE = float(
    os.environ.get(
        "YOLO_CONFIDENCE",
        os.environ.get("VEHICLE_CONF_THRESHOLD", "0.25"),
    )
)
VEHICLE_CONF_THRESHOLD = YOLO_CONFIDENCE

# Minimum confidence to keep a plate detection.
PLATE_CONF_THRESHOLD = float(os.environ.get("PLATE_CONF_THRESHOLD", "0.30"))

# Minimum OCR confidence to keep a read.
OCR_CONF_THRESHOLD = float(os.environ.get("OCR_CONF_THRESHOLD", "0.25"))

# Minimum plate text length (after normalization) to accept as a plausible
# Indian registration number fragment. Real plates are 9-10 chars
# (e.g. CG04AB1234) but OCR often misses a character, so we're lenient.
MIN_PLATE_TEXT_LEN = int(os.environ.get("MIN_PLATE_TEXT_LEN", "4"))

# Temporal de-duplication window (seconds). Repeated sightings of the same
# plate within this window count as ONE appearance (the highest-confidence
# one is kept).
DEDUP_WINDOW_SECONDS = float(os.environ.get("DEDUP_WINDOW_SECONDS", "3.0"))

# Vehicle tracking parameters for traffic footage.
TRACK_LOST_TIMEOUT_SECONDS = float(
    os.environ.get("TRACK_LOST_TIMEOUT_SECONDS", "1.5")
)
TRACK_HIGH_THRESH = float(os.environ.get("TRACK_HIGH_THRESH", "0.25"))
TRACK_LOW_THRESH = float(os.environ.get("TRACK_LOW_THRESH", "0.10"))
NEW_TRACK_THRESH = float(os.environ.get("NEW_TRACK_THRESH", "0.30"))
TRACK_BUFFER_FRAMES = int(os.environ.get("TRACK_BUFFER_FRAMES", "30"))
MATCH_THRESH = float(os.environ.get("MATCH_THRESH", "0.80"))

# Debug mode overlays the selected representative snapshot with track info.
DEBUG_TRACKING = os.environ.get("DEBUG_TRACKING", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

TRACKER_DIR = os.path.join(BASE_DIR, "trackers")
TRACKER_CONFIG_PATH = os.path.join(TRACKER_DIR, "bytetrack_traffic.yaml")


def _write_tracker_config() -> None:
    os.makedirs(TRACKER_DIR, exist_ok=True)
    tracker_yaml = f"""tracker_type: bytetrack
track_high_thresh: {TRACK_HIGH_THRESH}
track_low_thresh: {TRACK_LOW_THRESH}
new_track_thresh: {NEW_TRACK_THRESH}
track_buffer: {TRACK_BUFFER_FRAMES}
match_thresh: {MATCH_THRESH}
fuse_score: true
"""
    with open(TRACKER_CONFIG_PATH, "w", encoding="utf-8") as handle:
        handle.write(tracker_yaml)


_write_tracker_config()

# COCO class ids for vehicles we care about.
VEHICLE_CLASS_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

OCR_ENGINE = os.environ.get("OCR_ENGINE", "easyocr")  # easyocr | paddleocr
