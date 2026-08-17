# AI-Based Intelligent Vehicle Surveillance and CCTV Video Retrieval System (MVP)

A final-year project MVP that does exactly one thing well: upload a CCTV
recording, and later **search for a vehicle's number plate and jump
straight to the moment it appeared** in the original footage.

```
CCTV VIDEO → AI DETECTION → PLATE + TIMESTAMP INDEX → SEARCH PLATE
→ TIMESTAMP RESULTS → CLICK RESULT → ORIGINAL VIDEO → AUTO-SEEK
```

---

## 1. Project overview

| | |
|---|---|
| Backend | Python, FastAPI, OpenCV, Ultralytics YOLOv8, EasyOCR, SQLite |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS v4 |
| Storage | SQLite (`backend/storage/anpr.db`) + video/snapshot files on disk |
| Background jobs | A plain Python thread per video (no Celery/Redis) |

**What it does**: detects vehicles (car/motorcycle/bus/truck) with a
standard YOLOv8 model, detects license plates with a **plate-specific**
YOLOv8 model, crops + preprocesses + OCRs each plate with EasyOCR,
normalizes the text, de-duplicates repeated sightings of the same plate
into single "appearances," and stores `plate_number → timestamp` in
SQLite with an index on `plate_number` for fast search.

**What it deliberately does NOT do**: authentication, multi-user
support, RTSP/live cameras, watchlists, alerts, analytics, face
recognition, or any cloud/production infrastructure. See the project
brief for the full exclusion list — this MVP exists to prove one
workflow works end to end.

---

## 2. Architecture

```
Video ─▶ OpenCV frame sampling (PROCESS_FPS)
      ─▶ Vehicle detection (YOLOv8n, COCO)
      ─▶ Plate detection (YOLOv8, plate-specific model)
      ─▶ Crop plate ─▶ Preprocess (upscale, CLAHE, denoise)
      ─▶ OCR (EasyOCR) ─▶ Normalize text
      ─▶ Temporal de-dup (configurable window)
      ─▶ SQLite (videos, detections; indexed on plate_number)

Frontend: Upload → poll /videos/{id}/status → Search → click a result
          → /viewer?detection=<id> → <video> element seeks to
          detection.timestamp_seconds
```

---

## 3. Prerequisites

- Python 3.10+ (developed/tested on 3.12)
- Node.js 18+ (developed/tested on Node 22)
- ~2 GB free disk (PyTorch + model weights + EasyOCR's own models)
- A CPU is enough — no GPU/CUDA required. GPU will speed up processing if
  present (edit `gpu=False` in `backend/services/ocr.py` and the YOLO
  `device` arg if you have CUDA set up).

---

## 4. AI model setup — READ THIS FIRST

This is the part most ANPR tutorials get wrong: **the standard COCO
YOLO model does not have a "license plate" class.** Using it for plate
detection silently produces nothing useful. This MVP uses two separate
models:

### 4a. Vehicle detector (`models/yolov8n.pt`)
Stock YOLOv8n pretrained on COCO. `ultralytics` will auto-download it on
first use if missing, or fetch it yourself:
```bash
curl -L -o backend/models/yolov8n.pt \
  https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
```

### 4b. License-plate detector (`models/license_plate_detector.pt`)
A YOLOv8 model **fine-tuned specifically on license plates** (single
class: `license_plate`). This repo does not vendor the weights file
itself (keep the repo small / avoid redistribution ambiguity) — fetch it
with:
```bash
mkdir -p backend/models
curl -L -o backend/models/license_plate_detector.pt \
  https://raw.githubusercontent.com/Muhammad-Zeerak-Khan/Automatic-License-Plate-Recognition-using-YOLOv8/main/license_plate_detector.pt
```
Verify it loaded correctly:
```bash
python3 -c "from ultralytics import YOLO; m = YOLO('backend/models/license_plate_detector.pt'); print(m.names)"
# should print: {0: 'license_plate'}
```

**This model was trained on general (largely Western-format) plates.**
It detects "a rectangular plate region," which transfers reasonably well
across countries — but the OCR step below is what's tuned for Indian
plates, not the detector. If you have access to Indian-plate-labeled
data and want higher accuracy, fine-tune your own YOLOv8 detector and
point `PLATE_MODEL_PATH` at it (see `.env.example`). No code changes
needed — the path is fully configurable.

### 4c. OCR: EasyOCR, not PaddleOCR
The brief asked for PaddleOCR-first. In practice, `paddlepaddle`'s pip
install is heavy, GPU/CPU-build-mismatch-prone, and has caused broken
installs across several recent versions in sandboxed/offline-ish
environments. EasyOCR installs cleanly with plain `pip install
easyocr`, runs fine on CPU, and was reliable in testing. The engine is
swappable — `backend/services/ocr.py` is a single, small module; if you
want to try PaddleOCR, `OCR_ENGINE=paddleocr` is scaffolded as a config
value, but the actual PaddleOCR call isn't implemented (this is the one
place the brief's default was intentionally overridden — see the
"Known limitations" section for why).

EasyOCR downloads its own recognition weights (~100 MB) on first run
and caches them in `~/.EasyOCR/model/`. This requires internet access
the first time only.

---

## 5. Installation

### Backend
```bash
cd backend
python3 -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Get the models (see section 4 above)
mkdir -p models
curl -L -o models/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
curl -L -o models/license_plate_detector.pt https://raw.githubusercontent.com/Muhammad-Zeerak-Khan/Automatic-License-Plate-Recognition-using-YOLOv8/main/license_plate_detector.pt

cp .env.example .env   # optional — defaults already match this file
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local   # optional — defaults to http://localhost:8000
```

---

## 6. Running

**Backend** (from `backend/`):
```bash
uvicorn main:app --reload
```
First startup takes 30–60 seconds while PyTorch/Ultralytics/EasyOCR
import — this is normal, not a hang. Once you see `Application startup
complete`, visit `http://localhost:8000/docs` for interactive API docs.

**Frontend** (from `frontend/`, in a second terminal):
```bash
npm run dev
```
Visit `http://localhost:3000`.

---

## 7. Using it

### Upload a video
Go to **Upload**, drop in an `.mp4`/`.avi`/`.mov`/`.mkv`/`.webm` file.
Processing starts automatically and the page polls
`/videos/{id}/status` every 1.5s, showing an ASCII progress bar, frames
processed, vehicles detected, and unique plates found.

### Search a plate
Go to **Search**, type a registration number (e.g. `CG04AB1234` — case
and spacing don't matter, it's normalized). Every appearance is listed
with its timestamp, a plate-crop thumbnail, and confidence.

### Video timestamp retrieval
Click any result → the original video opens in an HTML5 `<video>`
player and **automatically seeks** to that timestamp
(`video.currentTime = detection.timestamp_seconds`, fired on
`loadedmetadata`/`canplay`). Play/pause/seek works normally from there.

---

## 8. Test data

No copyrighted CCTV footage is included in this repo. To test with real
footage:
- Use your own dashcam/CCTV/phone recording of traffic — that's
  actually the best test, since it's the real target use case.
- Or search for Creative-Commons-licensed traffic footage (e.g. Pexels,
  Pixabay, or Kaggle's various public ANPR datasets, several of which
  include Indian traffic clips with permissive licenses — check each
  dataset's license before use).
- Any `.mp4` with visible plates and a **standard video codec (H.264)**
  will work — see the codec note in Troubleshooting below.

---

## 9. Testing

```bash
cd backend
pip install pytest
pytest tests/ -v
```

`tests/test_pipeline.py` covers: video upload, rejecting bad file
types, video processing + DB insertion, plate search + timestamp
formatting, invalid/corrupt video handling, a video with no plates
completing cleanly, OCR text normalization/rejection, temporal
deduplication, and a full "upload → search → click → seekable video"
integration test (asserting the API returns everything the frontend
needs — a resolvable `video_url`, correct timestamp, and
range-request-capable file serving; the actual browser `<video>` seek
was verified manually with Playwright during development, since that's
a browser behavior rather than an API contract).

All 10 tests pass as of this writing.

---

## 10. Troubleshooting

**"Vehicle/plate detection model not found"** — you skipped section 4.
Run the `curl` commands there, or set `VEHICLE_MODEL_PATH` /
`PLATE_MODEL_PATH` in `.env` to wherever you put your own weights.

**Backend takes 30–60s to start** — expected. PyTorch + Ultralytics +
EasyOCR are large imports. Subsequent restarts are the same speed
(nothing to cache here); this is a one-time cost per process start, not
per video.

**Video won't play / won't seek in the browser** — 90% of the time
this is a **codec** issue, not a bug in the app. Browsers need **H.264**
video (`.mp4` container, `libx264` or hardware H.264 codec). If your
CCTV export uses an older codec like MPEG-4 Part 2 (`mp4v` — notably,
this is OpenCV's own default `VideoWriter` codec if you ever generate
test clips with it), most browsers refuse to decode it and the
`<video>` element will silently sit at `readyState: 0`. Re-encode with:
```bash
ffmpeg -i input.mp4 -c:v libx264 -pix_fmt yuv420p -movflags +faststart output.mp4
```
This does not affect the AI pipeline (OpenCV/ffmpeg can read almost any
codec for *processing*) — it only affects what the *browser* can play
back afterward.

**No plates detected on a real video** — check `/videos/{id}/status`
for `vehicles_detected` and `plates_recognized` counts. If vehicles are
detected but 0 plates: plates may be too small/blurry/angled for the
detector, or `PLATE_CONF_THRESHOLD` may be too strict — try lowering it
in `.env`. If 0 vehicles too: check the video actually has visible
traffic in frame, and that `PROCESS_FPS` isn't skipping past the only
moment a vehicle is visible (raise it for short clips).

**OCR reads garbage / 0 confusable with O, etc.** — this is normal OCR
behavior on small, low-res plate crops, not a bug. The MVP intentionally
does *not* aggressively "fix" characters (per the brief) since that risks
turning a correct read into a wrong one. Real-world accuracy improves a
lot with higher-resolution source video and well-lit, front-on plates.

**"OSError: No space left on device" during `pip install`** — PyTorch +
Ultralytics + EasyOCR need real disk space (~2–3 GB). Clear pip/uv
caches (`pip cache purge`) and retry.

**CORS errors in the browser console** — make sure the backend really
is running on `http://localhost:8000` and `NEXT_PUBLIC_API_BASE_URL` in
`frontend/.env.local` matches. The backend allows all origins by
default (`allow_origins=["*"]`) since there's no auth in this MVP — fine
for local dev, **not** something to ship as-is to production.

---

## 11. Known limitations (MVP scope)

- **Plate detector is a general-purpose model**, not one specifically
  trained on Indian plates. It reliably finds "a plate-shaped rectangle"
  but wasn't fine-tuned on Indian plate fonts/proportions/mounting
  styles. OCR + normalization *is* tuned for the Indian format
  (`SS00XX0000`), but detector accuracy on Indian plates specifically is
  unverified against real footage — see the honesty note below.
- **PaddleOCR was swapped for EasyOCR** (see section 4c) — the code is
  structured so this is a one-file change if you need to switch back.
- **No frame-level video preview/scrubber overlay** showing bounding
  boxes live during playback — only the static plate-crop snapshot is
  shown next to the player.
- **Background processing is a single Python thread**, not a real task
  queue — fine for one MVP demo, but multiple simultaneous uploads will
  contend for CPU (there's no queueing/throttling).
- **This MVP was validated using a synthetic test video** for pipeline
  wiring (upload → process → progress → DB → search → timestamp
  formatting → range-request video serving — all covered by the
  automated tests in section 9), plus a **manually seeded, realistic
  detection record** to verify the full click-through-to-auto-seek
  behavior in an actual browser (Playwright), which confirmed
  `video.currentTime` is set correctly to the stored timestamp. What
  was **not** independently verified is plate-detection *accuracy* on
  real CCTV footage, since no legally redistributable Indian traffic
  video was available in the development environment. Test with your
  own footage per section 8, and tune the confidence thresholds in
  `.env` if needed.
