"""
Vehicle event tracking and temporal license-plate consensus.

The tracker groups multiple frames of the same vehicle into
one continuous vehicle event.

Instead of trusting one OCR frame, plate readings are accumulated
and the most consistent reading is selected.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import cv2
import numpy as np


BBox = Tuple[int, int, int, int]


# ============================================================
# TRACKED VEHICLE
# ============================================================

@dataclass
class TrackedVehicle:
    track_id: Optional[int]
    bbox: BBox
    class_name: str
    confidence: float


# ============================================================
# PLATE OBSERVATION
# ============================================================

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


# ============================================================
# PLATE READING
# ============================================================

@dataclass
class PlateReading:
    text: str
    raw_text: str

    total_score: float = 0.0
    confidence_sum: float = 0.0

    observations: int = 0

    best_confidence: float = 0.0
    best_plate_confidence: float = 0.0

    best_bbox: Optional[BBox] = None
    best_crop: Optional[np.ndarray] = None
    best_frame: Optional[np.ndarray] = None

    best_timestamp: float = 0.0
    best_frame_number: int = 0

    def add(
        self,
        observation: PlateObservation,
    ):

        confidence = float(
            observation.ocr_confidence or 0.0
        )

        plate_confidence = float(
            observation.confidence or 0.0
        )

        # ----------------------------------------------------
        # Weighted observation score
        # ----------------------------------------------------

        score = (
            confidence * 0.75
            +
            plate_confidence * 0.25
        )

        self.total_score += score

        self.confidence_sum += confidence

        self.observations += 1

        # ----------------------------------------------------
        # Keep strongest observation
        # ----------------------------------------------------

        if (
            confidence > self.best_confidence
            or (
                abs(
                    confidence
                    - self.best_confidence
                ) < 0.03
                and plate_confidence
                > self.best_plate_confidence
            )
        ):

            self.best_confidence = confidence

            self.best_plate_confidence = (
                plate_confidence
            )

            self.best_bbox = (
                observation.bbox
            )

            self.best_crop = (
                observation.crop.copy()
            )

            self.best_frame = (
                observation.frame.copy()
            )

            self.best_timestamp = (
                observation.timestamp_seconds
            )

            self.best_frame_number = (
                observation.frame_number
            )

            self.raw_text = (
                observation.raw_text
            )


# ============================================================
# VEHICLE EVENT
# ============================================================

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

    # --------------------------------------------------------
    # Temporal OCR readings
    # --------------------------------------------------------

    plate_readings: Dict[str, PlateReading] = field(
        default_factory=dict
    )

    # Number of OCR observations.
    plate_observation_count: int = 0


    # ========================================================
    # UPDATE VEHICLE
    # ========================================================

    def update_vehicle(
        self,
        timestamp_seconds: float,
        frame_number: int,
        vehicle: TrackedVehicle,
    ):

        self.last_seen_seconds = (
            timestamp_seconds
        )

        self.last_seen_frame = (
            frame_number
        )

        self.representative_vehicle_bbox = (
            vehicle.bbox
        )

        self.representative_vehicle_confidence = (
            vehicle.confidence
        )


    # ========================================================
    # CONSIDER PLATE
    # ========================================================

    def consider_plate(
        self,
        observation: PlateObservation,
    ):

        text = (
            observation.normalized_text
            or ""
        ).strip().upper()

        if not text:
            return

        # ----------------------------------------------------
        # Create reading bucket
        # ----------------------------------------------------

        reading = self.plate_readings.get(
            text
        )

        if reading is None:

            reading = PlateReading(
                text=text,
                raw_text=(
                    observation.raw_text
                    or text
                ),
            )

            self.plate_readings[text] = (
                reading
            )

        # ----------------------------------------------------
        # Add observation
        # ----------------------------------------------------

        reading.add(
            observation
        )

        self.plate_observation_count += 1

        # ----------------------------------------------------
        # Recalculate best plate
        # ----------------------------------------------------

        self._select_best_plate()


    # ========================================================
    # SELECT BEST PLATE
    # ========================================================

    def _select_best_plate(self):

        if not self.plate_readings:
            return

        candidates = []

        for text, reading in (
            self.plate_readings.items()
        ):

            if reading.observations <= 0:
                continue

            average_confidence = (
                reading.confidence_sum
                / reading.observations
            )

            # ------------------------------------------------
            # Consensus is more important than one lucky OCR.
            # ------------------------------------------------

            consensus_score = (
                min(
                    reading.observations,
                    5,
                )
                * 0.55
            )

            confidence_score = (
                average_confidence
                * 0.35
            )

            best_score = (
                reading.best_confidence
                * 0.10
            )

            final_score = (
                consensus_score
                + confidence_score
                + best_score
            )

            candidates.append(
                (
                    final_score,
                    reading.observations,
                    average_confidence,
                    reading.best_confidence,
                    text,
                    reading,
                )
            )

        if not candidates:
            return

        # Highest consensus first.
        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
                item[3],
            ),
            reverse=True,
        )

        (
            _score,
            _observations,
            average_confidence,
            _best_confidence,
            text,
            reading,
        ) = candidates[0]

        # ----------------------------------------------------
        # Do not accept a single weak OCR reading.
        # ----------------------------------------------------

        if (
            reading.observations < 2
            and reading.best_confidence < 0.70
        ):
            return

        self.plate_number = text

        self.raw_ocr_text = (
            reading.raw_text
        )

        self.ocr_confidence = max(
            average_confidence,
            reading.best_confidence,
        )

        self.plate_confidence = (
            reading.best_plate_confidence
        )

        self.plate_bbox = (
            reading.best_bbox
        )

        if reading.best_crop is not None:

            self.plate_crop = (
                reading.best_crop.copy()
            )

        if reading.best_frame is not None:

            self.snapshot_frame = (
                reading.best_frame.copy()
            )

        self.representative_timestamp_seconds = (
            reading.best_timestamp
        )

        self.representative_frame_number = (
            reading.best_frame_number
        )


# ============================================================
# BBOX CENTER
# ============================================================

def bbox_center(
    bbox: BBox,
) -> Tuple[float, float]:

    x1, y1, x2, y2 = bbox

    return (
        (x1 + x2) / 2.0,
        (y1 + y2) / 2.0,
    )


# ============================================================
# BBOX IOU
# ============================================================

def bbox_iou(
    a: BBox,
    b: BBox,
) -> float:

    ax1, ay1, ax2, ay2 = a

    bx1, by1, bx2, by2 = b

    inter_x1 = max(
        ax1,
        bx1,
    )

    inter_y1 = max(
        ay1,
        by1,
    )

    inter_x2 = min(
        ax2,
        bx2,
    )

    inter_y2 = min(
        ay2,
        by2,
    )

    if (
        inter_x2 <= inter_x1
        or inter_y2 <= inter_y1
    ):
        return 0.0

    inter_area = float(
        (
            inter_x2 - inter_x1
        )
        *
        (
            inter_y2 - inter_y1
        )
    )

    area_a = float(
        max(
            1,
            ax2 - ax1,
        )
        *
        max(
            1,
            ay2 - ay1,
        )
    )

    area_b = float(
        max(
            1,
            bx2 - bx1,
        )
        *
        max(
            1,
            by2 - by1,
        )
    )

    return (
        inter_area
        /
        (
            area_a
            + area_b
            - inter_area
        )
    )


# ============================================================
# MATCH PLATE TO VEHICLE
# ============================================================

def match_plate_to_vehicle(
    plate_bbox: BBox,
    vehicles: List[TrackedVehicle],
) -> Optional[TrackedVehicle]:

    if not vehicles:
        return None

    px, py = bbox_center(
        plate_bbox
    )

    containing = []

    for vehicle in vehicles:

        vx1, vy1, vx2, vy2 = (
            vehicle.bbox
        )

        if (
            vx1 <= px <= vx2
            and vy1 <= py <= vy2
        ):

            containing.append(
                vehicle
            )

    if containing:

        return max(
            containing,
            key=lambda vehicle:
                vehicle.confidence,
        )

    # --------------------------------------------------------
    # Fallback: IoU
    # --------------------------------------------------------

    best_vehicle = max(
        vehicles,
        key=lambda vehicle:
            bbox_iou(
                plate_bbox,
                vehicle.bbox,
            ),
    )

    if (
        bbox_iou(
            plate_bbox,
            best_vehicle.bbox,
        )
        <= 0.0
    ):

        return None

    return best_vehicle


# ============================================================
# SNAPSHOT
# ============================================================

def build_snapshot_frame(
    event: VehicleEventState,
    debug_tracking: bool,
) -> Optional[np.ndarray]:

    if event.snapshot_frame is None:
        return None

    frame = event.snapshot_frame.copy()

    x1, y1, x2, y2 = (
        event.representative_vehicle_bbox
    )

    # ========================================================
    # DEBUG MODE
    # ========================================================

    if debug_tracking:

        vehicle_color = (
            0,
            255,
            0,
        )

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            vehicle_color,
            2,
        )

        lines = [
            (
                event.vehicle_type.title()
                if event.vehicle_type
                else "Vehicle"
            ),
            (
                f"ID: "
                f"{event.track_id if event.track_id is not None else 'NA'}"
            ),
            (
                f"Confidence: "
                f"{event.representative_vehicle_confidence:.2f}"
            ),
        ]

        if event.plate_number:

            lines.append(
                f"Plate: "
                f"{event.plate_number}"
            )

        text_x = max(
            0,
            x1,
        )

        text_y = max(
            20,
            y1 - 10,
        )

        for index, line in enumerate(
            lines
        ):

            cv2.putText(
                frame,
                line,
                (
                    text_x,
                    text_y
                    + (
                        index
                        * 22
                    ),
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                vehicle_color,
                2,
                cv2.LINE_AA,
            )

        # Plate bounding box

        if event.plate_bbox is not None:

            px1, py1, px2, py2 = (
                event.plate_bbox
            )

            cv2.rectangle(
                frame,
                (px1, py1),
                (px2, py2),
                (
                    255,
                    191,
                    0,
                ),
                2,
            )

    # ========================================================
    # NORMAL MODE
    # ========================================================

    elif (
        event.plate_bbox is not None
        and event.plate_number
    ):

        px1, py1, px2, py2 = (
            event.plate_bbox
        )

        cv2.rectangle(
            frame,
            (px1, py1),
            (px2, py2),
            (
                0,
                255,
                0,
            ),
            2,
        )

        cv2.putText(
            frame,
            event.plate_number,
            (
                px1,
                max(
                    0,
                    py1 - 10,
                ),
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (
                0,
                255,
                0,
            ),
            2,
            cv2.LINE_AA,
        )

    return frame


# ============================================================
# VEHICLE EVENT TRACKER
# ============================================================

class VehicleEventTracker:

    def __init__(
        self,
        lost_timeout_seconds: float,
    ):

        self.lost_timeout_seconds = (
            lost_timeout_seconds
        )

        self._events: Dict[
            str,
            VehicleEventState,
        ] = {}


    # ========================================================
    # VEHICLE KEY
    # ========================================================

    @staticmethod
    def vehicle_key(
        vehicle: TrackedVehicle,
    ) -> str:

        if vehicle.track_id is not None:

            return str(
                vehicle.track_id
            )

        return (
            f"{vehicle.class_name}:"
            f"{vehicle.bbox}"
        )


    # ========================================================
    # OBSERVE FRAME
    # ========================================================

    def observe_frame(
        self,
        timestamp_seconds: float,
        frame_number: int,
        frame: np.ndarray,
        vehicles: List[TrackedVehicle],
        plate_observations: List[PlateObservation],
    ) -> List[VehicleEventState]:

        finalized = (
            self.finalize_expired(
                timestamp_seconds
            )
        )

        # ----------------------------------------------------
        # Best plate observation per vehicle
        # ----------------------------------------------------

        plate_by_vehicle: Dict[
            str,
            PlateObservation,
        ] = {}

        for observation in (
            plate_observations
        ):

            current = (
                plate_by_vehicle.get(
                    observation.vehicle_key
                )
            )

            if current is None:

                plate_by_vehicle[
                    observation.vehicle_key
                ] = observation

                continue

            candidate_score = (
                observation.ocr_confidence
                * 0.75
                +
                observation.confidence
                * 0.25
            )

            current_score = (
                current.ocr_confidence
                * 0.75
                +
                current.confidence
                * 0.25
            )

            if candidate_score > current_score:

                plate_by_vehicle[
                    observation.vehicle_key
                ] = observation

        # ----------------------------------------------------
        # Update vehicles
        # ----------------------------------------------------

        for vehicle in vehicles:

            key = self.vehicle_key(
                vehicle
            )

            event = (
                self._events.get(
                    key
                )
            )

            observation = (
                plate_by_vehicle.get(
                    key
                )
            )

            if (
                event is not None
                and event.plate_number is not None
                and observation is not None
                and observation.normalized_text
                and observation.normalized_text.upper() != event.plate_number
            ):
                finalized.append(event)
                del self._events[key]
                event = None

            # ------------------------------------------------
            # New vehicle
            # ------------------------------------------------

            if event is None:

                event = VehicleEventState(
                    key=key,

                    track_id=(
                        vehicle.track_id
                    ),

                    vehicle_type=(
                        vehicle.class_name
                    ),

                    first_seen_seconds=(
                        timestamp_seconds
                    ),

                    last_seen_seconds=(
                        timestamp_seconds
                    ),

                    first_seen_frame=(
                        frame_number
                    ),

                    last_seen_frame=(
                        frame_number
                    ),

                    representative_timestamp_seconds=(
                        timestamp_seconds
                    ),

                    representative_frame_number=(
                        frame_number
                    ),

                    representative_vehicle_bbox=(
                        vehicle.bbox
                    ),

                    representative_vehicle_confidence=(
                        vehicle.confidence
                    ),
                )

                self._events[key] = (
                    event
                )

            # ------------------------------------------------
            # Update vehicle
            # ------------------------------------------------

            event.update_vehicle(
                timestamp_seconds,
                frame_number,
                vehicle,
            )

            # ------------------------------------------------
            # Plate
            # ------------------------------------------------

            if observation is not None:

                event.consider_plate(
                    observation
                )

        return finalized


    # ========================================================
    # FINALIZE EXPIRED
    # ========================================================

    def finalize_expired(
        self,
        timestamp_seconds: float,
    ) -> List[VehicleEventState]:

        finalized = []

        for key, event in list(
            self._events.items()
        ):

            if (
                timestamp_seconds
                - event.last_seen_seconds
                > self.lost_timeout_seconds
            ):

                finalized.append(
                    event
                )

                del self._events[key]

        return finalized


    # ========================================================
    # FINALIZE ALL
    # ========================================================

    def finalize_all(
        self,
    ) -> List[VehicleEventState]:

        finalized = list(
            self._events.values()
        )

        self._events.clear()

        return finalized