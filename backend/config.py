"""
Central configuration for the ANPR pipeline.

All important settings can be overridden through environment variables
from backend/.env.
"""

import os


# ============================================================
# BASE DIRECTORIES
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

STORAGE_DIR = os.path.join(
    BASE_DIR,
    "storage"
)

VIDEOS_DIR = os.path.join(
    STORAGE_DIR,
    "videos"
)

SNAPSHOTS_DIR = os.path.join(
    STORAGE_DIR,
    "snapshots"
)

PLATES_DIR = os.path.join(
    STORAGE_DIR,
    "plates"
)


# Create required directories automatically
for directory in (
    STORAGE_DIR,
    VIDEOS_DIR,
    SNAPSHOTS_DIR,
    PLATES_DIR,
):
    os.makedirs(
        directory,
        exist_ok=True
    )


# ============================================================
# AI MODEL DIRECTORY
# ============================================================

MODELS_DIR = os.path.join(
    BASE_DIR,
    "models"
)


# ============================================================
# VEHICLE DETECTION MODEL
# ============================================================

# Standard YOLOv8 COCO model.
#
# COCO vehicle classes:
#   2 = car
#   3 = motorcycle
#   5 = bus
#   7 = truck

VEHICLE_MODEL_PATH = os.environ.get(
    "VEHICLE_MODEL_PATH",
    os.path.join(
        MODELS_DIR,
        "yolov8n.pt"
    )
)


# ============================================================
# LICENSE PLATE DETECTION MODEL
# ============================================================

# Custom license plate YOLO model.

PLATE_MODEL_PATH = os.environ.get(
    "PLATE_MODEL_PATH",
    os.path.join(
        MODELS_DIR,
        "license_plate_detector.pt"
    )
)


# ============================================================
# VIDEO PROCESSING SPEED
# ============================================================

# Number of video frames processed per second.
#
# Lower value:
#   Faster processing
#
# Higher value:
#   Better detection coverage
#
# 3 FPS is a good starting point for CPU-based processing.

PROCESS_FPS = float(
    os.environ.get(
        "PROCESS_FPS",
        "3"
    )
)


# ============================================================
# VEHICLE DETECTION CONFIDENCE
# ============================================================

# Minimum YOLO confidence required for a vehicle.

YOLO_CONFIDENCE = float(
    os.environ.get(
        "YOLO_CONFIDENCE",
        os.environ.get(
            "VEHICLE_CONF_THRESHOLD",
            "0.30"
        )
    )
)

# Backwards compatibility
VEHICLE_CONF_THRESHOLD = YOLO_CONFIDENCE


# ============================================================
# LICENSE PLATE CONFIDENCE
# ============================================================

# Minimum confidence required for a license plate.

PLATE_CONF_THRESHOLD = float(
    os.environ.get(
        "PLATE_CONF_THRESHOLD",
        "0.35"
    )
)


# ============================================================
# OCR CONFIDENCE
# ============================================================

# Minimum OCR confidence required to save a plate.

OCR_CONF_THRESHOLD = float(
    os.environ.get(
        "OCR_CONF_THRESHOLD",
        "0.35"
    )
)


# ============================================================
# LICENSE PLATE TEXT VALIDATION
# ============================================================

# Minimum number of characters required after OCR
# normalization.
#
# Example:
#   CG04AB1234 -> valid
#   AB123      -> valid
#   A          -> rejected

MIN_PLATE_TEXT_LEN = int(
    os.environ.get(
        "MIN_PLATE_TEXT_LEN",
        "4"
    )
)


# ============================================================
# PLATE DE-DUPLICATION
# ============================================================

# Repeated detections of the same plate within this
# time window are treated as the same appearance.

DEDUP_WINDOW_SECONDS = float(
    os.environ.get(
        "DEDUP_WINDOW_SECONDS",
        "3.0"
    )
)


# ============================================================
# VEHICLE TRACKING
# ============================================================

# How long a vehicle can disappear before its track
# is considered lost.

TRACK_LOST_TIMEOUT_SECONDS = float(
    os.environ.get(
        "TRACK_LOST_TIMEOUT_SECONDS",
        "1.5"
    )
)


# ByteTrack parameters

TRACK_HIGH_THRESH = float(
    os.environ.get(
        "TRACK_HIGH_THRESH",
        "0.25"
    )
)

TRACK_LOW_THRESH = float(
    os.environ.get(
        "TRACK_LOW_THRESH",
        "0.10"
    )
)

NEW_TRACK_THRESH = float(
    os.environ.get(
        "NEW_TRACK_THRESH",
        "0.30"
    )
)

TRACK_BUFFER_FRAMES = int(
    os.environ.get(
        "TRACK_BUFFER_FRAMES",
        "30"
    )
)

MATCH_THRESH = float(
    os.environ.get(
        "MATCH_THRESH",
        "0.80"
    )
)


# ============================================================
# DEBUG TRACKING
# ============================================================

# Set DEBUG_TRACKING=1 in .env to show tracking
# information on generated snapshots.

DEBUG_TRACKING = (
    os.environ
    .get(
        "DEBUG_TRACKING",
        "0"
    )
    .strip()
    .lower()
    in {
        "1",
        "true",
        "yes",
        "on",
    }
)


# ============================================================
# TRACKER CONFIGURATION
# ============================================================

TRACKER_DIR = os.path.join(
    BASE_DIR,
    "trackers"
)

TRACKER_CONFIG_PATH = os.path.join(
    TRACKER_DIR,
    "bytetrack_traffic.yaml"
)


def _write_tracker_config():
    """
    Create the ByteTrack configuration file
    automatically.
    """

    os.makedirs(
        TRACKER_DIR,
        exist_ok=True
    )

    tracker_yaml = f"""tracker_type: bytetrack
track_high_thresh: {TRACK_HIGH_THRESH}
track_low_thresh: {TRACK_LOW_THRESH}
new_track_thresh: {NEW_TRACK_THRESH}
track_buffer: {TRACK_BUFFER_FRAMES}
match_thresh: {MATCH_THRESH}
fuse_score: true
"""

    with open(
        TRACKER_CONFIG_PATH,
        "w",
        encoding="utf-8"
    ) as handle:

        handle.write(
            tracker_yaml
        )


_write_tracker_config()


# ============================================================
# VEHICLE CLASSES
# ============================================================

# COCO class IDs used by YOLOv8.

VEHICLE_CLASS_IDS = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


# ============================================================
# OCR ENGINE
# ============================================================

# Supported:
#   easyocr
#   paddleocr

OCR_ENGINE = os.environ.get(
    "OCR_ENGINE",
    "easyocr"
)


# ============================================================
# OPTIONAL PERFORMANCE SETTINGS
# ============================================================

# OCR is expensive.
#
# The video processor uses this value to avoid repeatedly
# running OCR on the same tracked vehicle.

OCR_INTERVAL_SECONDS = float(
    os.environ.get(
        "OCR_INTERVAL_SECONDS",
        "1.0"
    )
)


# Maximum number of frames that can be processed
# simultaneously by future optimized pipelines.

MAX_PROCESSING_WORKERS = int(
    os.environ.get(
        "MAX_PROCESSING_WORKERS",
        "1"
    )
)


# ============================================================
# FINAL CONFIG SUMMARY
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("ANPR CONFIGURATION")
    print("=" * 60)

    print(f"Vehicle model : {VEHICLE_MODEL_PATH}")
    print(f"Plate model   : {PLATE_MODEL_PATH}")

    print(
        f"Process FPS   : {PROCESS_FPS}"
    )

    print(
        f"Vehicle conf  : {YOLO_CONFIDENCE}"
    )

    print(
        f"Plate conf    : {PLATE_CONF_THRESHOLD}"
    )

    print(
        f"OCR conf      : {OCR_CONF_THRESHOLD}"
    )

    print(
        f"OCR interval  : {OCR_INTERVAL_SECONDS}s"
    )

    print(
        f"Tracker buffer: {TRACK_BUFFER_FRAMES}"
    )

    print(
        f"OCR engine    : {OCR_ENGINE}"
    )

    print("=" * 60)