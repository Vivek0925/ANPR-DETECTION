Model weights are NOT included in this repository (kept out per project
scope — see the top-level README section 4, "AI Model Setup").

Download them before running the backend:

```bash
cd backend
mkdir -p models
curl -L -o models/yolov8n.pt \
  https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
curl -L -o models/license_plate_detector.pt \
  https://raw.githubusercontent.com/Muhammad-Zeerak-Khan/Automatic-License-Plate-Recognition-using-YOLOv8/main/license_plate_detector.pt
```

Paths are configurable via `VEHICLE_MODEL_PATH` / `PLATE_MODEL_PATH` in
`.env` if you want to point at your own trained weights instead.
