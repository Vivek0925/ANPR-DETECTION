"""
License plate detector.

Optimized for CCTV / traffic footage:
- Uses the dedicated license-plate YOLO model
- Tries multiple image scales
- Filters tiny / unrealistic detections
- Removes duplicate overlapping detections
- Keeps the strongest plate boxes
"""

import os
from typing import List, Dict

import cv2
import numpy as np
from ultralytics import YOLO

import config


class PlateDetector:

    def __init__(self, model_path: str = None):

        model_path = (
            model_path
            or config.PLATE_MODEL_PATH
        )

        if not os.path.exists(model_path):

            raise FileNotFoundError(
                f"""
License-plate model not found:

{model_path}

Make sure:

models/license_plate_detector.pt

exists inside your backend directory.
"""
            )

        print(
            f"[PLATE] Loading model: {model_path}"
        )

        self.model = YOLO(
            model_path
        )

        print(
            "[PLATE] Model loaded successfully."
        )

    # =========================================================
    # IOU
    # =========================================================

    @staticmethod
    def _iou(
        box_a,
        box_b,
    ):

        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b

        ix1 = max(
            ax1,
            bx1,
        )

        iy1 = max(
            ay1,
            by1,
        )

        ix2 = min(
            ax2,
            bx2,
        )

        iy2 = min(
            ay2,
            by2,
        )

        if (
            ix2 <= ix1
            or iy2 <= iy1
        ):
            return 0.0

        intersection = (
            (ix2 - ix1)
            *
            (iy2 - iy1)
        )

        area_a = (
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

        area_b = (
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
            intersection
            /
            (
                area_a
                + area_b
                - intersection
            )
        )

    # =========================================================
    # VALIDATE BOX
    # =========================================================

    @staticmethod
    def _valid_plate_box(
        bbox,
        frame_shape,
    ):

        x1, y1, x2, y2 = bbox

        height, width = (
            frame_shape[:2]
        )

        # Clamp coordinates.
        x1 = max(
            0,
            min(
                x1,
                width - 1,
            ),
        )

        y1 = max(
            0,
            min(
                y1,
                height - 1,
            ),
        )

        x2 = max(
            0,
            min(
                x2,
                width,
            ),
        )

        y2 = max(
            0,
            min(
                y2,
                height,
            ),
        )

        if x2 <= x1:
            return False

        if y2 <= y1:
            return False

        box_width = x2 - x1
        box_height = y2 - y1

        area = (
            box_width
            *
            box_height
        )

        frame_area = (
            width
            *
            height
        )

        if frame_area <= 0:
            return False

        # Reject extremely tiny boxes.
        min_area = (
            frame_area
            * 0.00003
        )

        if area < min_area:
            return False

        # Reject huge boxes.
        if area > frame_area * 0.15:
            return False

        # License plates are generally wider than tall.
        aspect_ratio = (
            box_width
            /
            max(
                box_height,
                1,
            )
        )

        # Allow fairly wide variation because CCTV plates
        # can be angled.
        if aspect_ratio < 1.25:
            return False

        if aspect_ratio > 12.0:
            return False

        return True

    # =========================================================
    # EXTRACT DETECTIONS
    # =========================================================

    def _extract(
        self,
        results,
        frame_shape,
        confidence_threshold,
        scale_name,
    ):

        detections = []

        if not results:
            return detections

        result = results[0]

        if result.boxes is None:
            return detections

        for box in result.boxes:

            try:

                coordinates = (
                    box.xyxy[0]
                    .cpu()
                    .numpy()
                    .tolist()
                )

                confidence = float(
                    box.conf[0]
                    .cpu()
                    .item()
                )

            except Exception:
                continue

            if (
                confidence
                < confidence_threshold
            ):
                continue

            x1, y1, x2, y2 = (
                map(
                    int,
                    coordinates,
                )
            )

            bbox = (
                x1,
                y1,
                x2,
                y2,
            )

            if not self._valid_plate_box(
                bbox,
                frame_shape,
            ):
                continue

            detections.append(
                {
                    "bbox": bbox,
                    "confidence": confidence,
                    "scale": scale_name,
                }
            )

        return detections

    # =========================================================
    # REMOVE DUPLICATES
    # =========================================================

    def _remove_duplicates(
        self,
        detections,
    ):

        if not detections:
            return []

        # Highest confidence first.
        detections = sorted(
            detections,
            key=lambda item: item[
                "confidence"
            ],
            reverse=True,
        )

        selected = []

        for candidate in detections:

            duplicate = False

            for existing in selected:

                if (
                    self._iou(
                        candidate["bbox"],
                        existing["bbox"],
                    )
                    >= 0.45
                ):

                    duplicate = True
                    break

            if not duplicate:

                selected.append(
                    candidate
                )

        return selected

    # =========================================================
    # MAIN DETECTION
    # =========================================================

    def detect(
        self,
        frame,
    ) -> List[Dict]:

        if frame is None:
            return []

        if frame.size == 0:
            return []

        confidence = float(
            getattr(
                config,
                "PLATE_CONF_THRESHOLD",
                0.30,
            )
        )

        detections = []

        # =====================================================
        # PASS 1 — NORMAL FRAME
        # =====================================================

        try:

            results = self.model.predict(
                frame,
                verbose=False,
                conf=confidence,
                imgsz=960,
                max_det=50,
            )

            detections.extend(
                self._extract(
                    results,
                    frame.shape,
                    confidence,
                    "normal",
                )
            )

        except Exception as error:

            print(
                "[PLATE] Normal detection error:",
                error,
            )

        # =====================================================
        # PASS 2 — UPSCALED FRAME
        # =====================================================
        #
        # Useful when the license plate is small in a
        # 720p/1080p traffic video.
        #
        # Only run this when normal detection found few/no
        # plates, keeping processing reasonably fast.
        # =====================================================

        if len(detections) == 0:

            try:

                height, width = (
                    frame.shape[:2]
                )

                scale = 1.5

                upscaled = cv2.resize(
                    frame,
                    (
                        int(width * scale),
                        int(height * scale),
                    ),
                    interpolation=cv2.INTER_CUBIC,
                )

                results = self.model.predict(
                    upscaled,
                    verbose=False,
                    conf=max(
                        0.20,
                        confidence - 0.05,
                    ),
                    imgsz=1280,
                    max_det=50,
                )

                scaled_detections = (
                    self._extract(
                        results,
                        upscaled.shape,
                        max(
                            0.20,
                            confidence - 0.05,
                        ),
                        "upscaled",
                    )
                )

                # Convert coordinates back to original frame.
                for detection in scaled_detections:

                    x1, y1, x2, y2 = (
                        detection["bbox"]
                    )

                    detection["bbox"] = (
                        int(x1 / scale),
                        int(y1 / scale),
                        int(x2 / scale),
                        int(y2 / scale),
                    )

                    # Revalidate after scaling.
                    if self._valid_plate_box(
                        detection["bbox"],
                        frame.shape,
                    ):

                        detections.append(
                            detection
                        )

            except Exception as error:

                print(
                    "[PLATE] Upscaled detection error:",
                    error,
                )

        # =====================================================
        # REMOVE DUPLICATES
        # =====================================================

        detections = (
            self._remove_duplicates(
                detections
            )
        )

        # =====================================================
        # SORT
        # =====================================================

        detections.sort(
            key=lambda item:
                item["confidence"],
            reverse=True,
        )

        # =====================================================
        # LIMIT
        # =====================================================

        return detections[:20]