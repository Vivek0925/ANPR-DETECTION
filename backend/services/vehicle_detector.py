"""
Vehicle detection using a stock (COCO-pretrained) YOLOv8 model.
Detects: car, motorcycle, bus, truck.
"""
import os
import threading
from ultralytics import YOLO

import config


class VehicleDetector:
    def __init__(self, model_path: str = None):
        model_path = model_path or config.VEHICLE_MODEL_PATH
        # ultralytics will auto-download yolov8n.pt if the path doesn't
        # exist AND it's a bare recognized name; if a real path is missing
        # we fail loudly instead of silently downloading something else.
        if not os.path.exists(model_path) and not model_path.endswith("yolov8n.pt"):
            raise FileNotFoundError(
                f"Vehicle detection model not found at {model_path}. "
                f"Set VEHICLE_MODEL_PATH or place yolov8n.pt in the models/ dir."
            )
        self.model = YOLO(model_path)
        self._lock = threading.Lock()

    def reset_tracker(self):
        # Reset the predictor between videos so a fresh tracker is created.
        # Setting predictor.trackers = None can break ultralytics callbacks
        # that index predictor.trackers[0]. Recreating predictor is safer.
        self.model.predictor = None

    def detect(self, frame):
        """
        Returns a list of dicts: {bbox: (x1,y1,x2,y2), class_name, confidence}
        """
        with self._lock:
            results = self.model.predict(
                frame,
                verbose=False,
                conf=config.VEHICLE_CONF_THRESHOLD,
                classes=list(config.VEHICLE_CLASS_IDS.keys()),
            )[0]
        return self._boxes_to_detections(results, include_track_id=False)

    def track(self, frame):
        """
        Returns vehicle detections with persistent tracker IDs.
        """
        with self._lock:
            try:
                results = self.model.track(
                    frame,
                    verbose=False,
                    conf=config.VEHICLE_CONF_THRESHOLD,
                    persist=True,
                    tracker=config.TRACKER_CONFIG_PATH,
                    classes=list(config.VEHICLE_CLASS_IDS.keys()),
                )[0]
                return self._boxes_to_detections(results, include_track_id=True)
            except Exception:
                # Keep pipeline alive even if tracker internals fail.
                # We still return vehicle detections, just without track IDs.
                results = self.model.predict(
                    frame,
                    verbose=False,
                    conf=config.VEHICLE_CONF_THRESHOLD,
                    classes=list(config.VEHICLE_CLASS_IDS.keys()),
                )[0]
                return self._boxes_to_detections(results, include_track_id=False)

    def _boxes_to_detections(self, results, include_track_id: bool):
        detections = []
        boxes = getattr(results, "boxes", None)
        if boxes is None:
            return detections

        xyxy = boxes.xyxy.tolist() if hasattr(boxes, "xyxy") else []
        confs = boxes.conf.tolist() if hasattr(boxes, "conf") else []
        classes = boxes.cls.tolist() if hasattr(boxes, "cls") else []

        ids = None
        if include_track_id and hasattr(boxes, "id"):
            raw_ids = boxes.id
            if raw_ids is not None:
                ids = raw_ids.tolist()

        for index in range(len(xyxy)):
            x1, y1, x2, y2 = xyxy[index]
            score = confs[index] if index < len(confs) else 0.0
            class_id = int(classes[index]) if index < len(classes) else -1
            if class_id not in config.VEHICLE_CLASS_IDS:
                continue
            track_id = None
            if include_track_id and ids is not None and index < len(ids):
                track_value = ids[index]
                if track_value is not None:
                    track_id = int(track_value)
            detections.append(
                {
                    "bbox": (int(x1), int(y1), int(x2), int(y2)),
                    "class_name": config.VEHICLE_CLASS_IDS[class_id],
                    "confidence": float(score),
                    "track_id": track_id,
                }
            )
        return detections
