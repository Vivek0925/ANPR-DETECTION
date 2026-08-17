"""
Utilities for grouping vehicle detections into continuous appearance events.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


BBox = Tuple[int, int, int, int]


@dataclass
class TrackedVehicle:
    track_id: Optional[int]
    bbox: BBox
    class_name: str
    confidence: float


@dataclass
class PlateObservation:
    bbox: BBox
    confidence: float
    raw_text: str
    normalized_text: str
    ocr_confidence: float
    crop: np.ndarray
    frame: np.ndarray
    timestamp_seconds: float
    frame_number: int
    vehicle_key: str


@dataclass
class VehicleEventState:
    key: str
    track_id: Optional[int]
    vehicle_type: str
    first_seen_seconds: float
    last_seen_seconds: float
    first_seen_frame: int
    last_seen_frame: int
    representative_timestamp_seconds: float
    representative_frame_number: int
    representative_vehicle_bbox: BBox
    representative_vehicle_confidence: float
    plate_number: Optional[str] = None
    raw_ocr_text: Optional[str] = None
    ocr_confidence: float = 0.0
    plate_confidence: float = 0.0
    plate_bbox: Optional[BBox] = None
    plate_crop: Optional[np.ndarray] = None
    snapshot_frame: Optional[np.ndarray] = None

    def update_vehicle(self, timestamp_seconds: float, frame_number: int, vehicle: TrackedVehicle):
        self.last_seen_seconds = timestamp_seconds
        self.last_seen_frame = frame_number
        self.representative_vehicle_bbox = vehicle.bbox
        self.representative_vehicle_confidence = vehicle.confidence

    def consider_plate(self, observation: PlateObservation):
        score = (observation.ocr_confidence, observation.confidence)
        current_score = (self.ocr_confidence, self.plate_confidence)
        if self.plate_number is not None and score <= current_score:
            return

        self.plate_number = observation.normalized_text
        self.raw_ocr_text = observation.raw_text
        self.ocr_confidence = observation.ocr_confidence
        self.plate_confidence = observation.confidence
        self.plate_bbox = observation.bbox
        self.plate_crop = observation.crop.copy()
        self.snapshot_frame = observation.frame.copy()
        self.representative_timestamp_seconds = observation.timestamp_seconds
        self.representative_frame_number = observation.frame_number


def bbox_center(bbox: BBox) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def bbox_iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0

    inter_area = float((inter_x2 - inter_x1) * (inter_y2 - inter_y1))
    area_a = float(max(1, ax2 - ax1) * max(1, ay2 - ay1))
    area_b = float(max(1, bx2 - bx1) * max(1, by2 - by1))
    return inter_area / (area_a + area_b - inter_area)


def match_plate_to_vehicle(plate_bbox: BBox, vehicles: List[TrackedVehicle]) -> Optional[TrackedVehicle]:
    if not vehicles:
        return None

    px, py = bbox_center(plate_bbox)
    containing = []
    for vehicle in vehicles:
        vx1, vy1, vx2, vy2 = vehicle.bbox
        if vx1 <= px <= vx2 and vy1 <= py <= vy2:
            containing.append(vehicle)

    if containing:
        return max(containing, key=lambda vehicle: vehicle.confidence)

    # When center-point containment fails, only accept a vehicle if there is
    # at least some real overlap. This avoids mis-assigning a plate to an
    # unrelated car when boxes are disjoint.
    best_vehicle = max(vehicles, key=lambda vehicle: bbox_iou(plate_bbox, vehicle.bbox))
    if bbox_iou(plate_bbox, best_vehicle.bbox) <= 0.0:
        return None
    return best_vehicle


def build_snapshot_frame(event: VehicleEventState, debug_tracking: bool) -> Optional[np.ndarray]:
    if event.snapshot_frame is None:
        return None

    frame = event.snapshot_frame.copy()
    x1, y1, x2, y2 = event.representative_vehicle_bbox

    if debug_tracking:
        vehicle_color = (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), vehicle_color, 2)

        lines = [
            event.vehicle_type.title() if event.vehicle_type else "Vehicle",
            f"ID: {event.track_id if event.track_id is not None else 'NA'}",
            f"Confidence: {event.representative_vehicle_confidence:.2f}",
        ]
        if event.plate_number:
            lines.append(f"Plate: {event.plate_number}")

        text_x = max(0, x1)
        text_y = max(20, y1 - 10)
        for index, line in enumerate(lines):
            cv2.putText(
                frame,
                line,
                (text_x, text_y + (index * 22)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                vehicle_color,
                2,
                cv2.LINE_AA,
            )

        if event.plate_bbox is not None:
            px1, py1, px2, py2 = event.plate_bbox
            cv2.rectangle(frame, (px1, py1), (px2, py2), (255, 191, 0), 2)
    elif event.plate_bbox is not None and event.plate_number:
        px1, py1, px2, py2 = event.plate_bbox
        cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 255, 0), 2)
        cv2.putText(
            frame,
            event.plate_number,
            (px1, max(0, py1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

    return frame


class VehicleEventTracker:
    def __init__(self, lost_timeout_seconds: float):
        self.lost_timeout_seconds = lost_timeout_seconds
        self._events: Dict[str, VehicleEventState] = {}

    @staticmethod
    def vehicle_key(vehicle: TrackedVehicle) -> str:
        if vehicle.track_id is not None:
            return str(vehicle.track_id)
        return f"{vehicle.class_name}:{vehicle.bbox}"

    def observe_frame(
        self,
        timestamp_seconds: float,
        frame_number: int,
        frame: np.ndarray,
        vehicles: List[TrackedVehicle],
        plate_observations: List[PlateObservation],
    ) -> List[VehicleEventState]:
        finalized = self.finalize_expired(timestamp_seconds)

        plate_by_vehicle: Dict[str, PlateObservation] = {}
        for observation in plate_observations:
            current = plate_by_vehicle.get(observation.vehicle_key)
            candidate_score = (observation.ocr_confidence, observation.confidence)
            current_score = (
                current.ocr_confidence,
                current.confidence,
            ) if current is not None else (-1.0, -1.0)
            if current is None or candidate_score > current_score:
                plate_by_vehicle[observation.vehicle_key] = observation

        for vehicle in vehicles:
            key = self.vehicle_key(vehicle)
            event = self._events.get(key)
            if event is None:
                event = VehicleEventState(
                    key=key,
                    track_id=vehicle.track_id,
                    vehicle_type=vehicle.class_name,
                    first_seen_seconds=timestamp_seconds,
                    last_seen_seconds=timestamp_seconds,
                    first_seen_frame=frame_number,
                    last_seen_frame=frame_number,
                    representative_timestamp_seconds=timestamp_seconds,
                    representative_frame_number=frame_number,
                    representative_vehicle_bbox=vehicle.bbox,
                    representative_vehicle_confidence=vehicle.confidence,
                )
                self._events[key] = event
            event.update_vehicle(timestamp_seconds, frame_number, vehicle)

            observation = plate_by_vehicle.get(key)
            if observation is not None:
                if self._should_split_event_for_plate_change(event, observation):
                    finalized.append(event)
                    event = VehicleEventState(
                        key=key,
                        track_id=vehicle.track_id,
                        vehicle_type=vehicle.class_name,
                        first_seen_seconds=timestamp_seconds,
                        last_seen_seconds=timestamp_seconds,
                        first_seen_frame=frame_number,
                        last_seen_frame=frame_number,
                        representative_timestamp_seconds=timestamp_seconds,
                        representative_frame_number=frame_number,
                        representative_vehicle_bbox=vehicle.bbox,
                        representative_vehicle_confidence=vehicle.confidence,
                    )
                    self._events[key] = event
                event.consider_plate(observation)

        return finalized

    @staticmethod
    def _should_split_event_for_plate_change(
        event: VehicleEventState,
        observation: PlateObservation,
    ) -> bool:
        if not event.plate_number:
            return False
        if not observation.normalized_text:
            return False
        if observation.normalized_text == event.plate_number:
            return False

        # Split only on high-confidence conflicting reads to reduce churn from
        # transient OCR noise. This protects true second vehicles when a track
        # ID is reused by the tracker.
        return event.ocr_confidence >= 0.80 and observation.ocr_confidence >= 0.80

    def finalize_expired(self, timestamp_seconds: float) -> List[VehicleEventState]:
        finalized: List[VehicleEventState] = []
        for key, event in list(self._events.items()):
            if (timestamp_seconds - event.last_seen_seconds) > self.lost_timeout_seconds:
                finalized.append(event)
                del self._events[key]
        return finalized

    def finalize_all(self) -> List[VehicleEventState]:
        finalized = list(self._events.values())
        self._events.clear()
        return finalized