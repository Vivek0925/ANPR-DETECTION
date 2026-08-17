"""
License-plate detection using a YOLOv8 model FINE-TUNED specifically for
license plates. The stock COCO YOLO model has no "license plate" class, so
using it here would silently produce nothing (or garbage) -- see README for
where PLATE_MODEL_PATH weights come from.
"""
import os
from ultralytics import YOLO

import config


class PlateDetector:
    def __init__(self, model_path: str = None):
        model_path = model_path or config.PLATE_MODEL_PATH
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"License-plate detection model not found at {model_path}.\n"
                f"This MVP requires a model trained specifically to detect "
                f"license plates (the standard COCO YOLO model cannot do this).\n"
                f"See README.md -> 'AI Model Setup' for download instructions.\n"
                f"Configure a different path via the PLATE_MODEL_PATH env var."
            )
        self.model = YOLO(model_path)

    def detect(self, frame):
        """
        Returns a list of dicts: {bbox: (x1,y1,x2,y2), confidence}
        """
        results = self.model.predict(
            frame, verbose=False, conf=config.PLATE_CONF_THRESHOLD
        )[0]
        detections = []
        for box in results.boxes.data.tolist():
            x1, y1, x2, y2, score = box[:5]
            detections.append(
                {
                    "bbox": (int(x1), int(y1), int(x2), int(y2)),
                    "confidence": float(score),
                }
            )
        return detections
