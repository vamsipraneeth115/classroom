# Smart Classroom Engagement Analyzer — End to End

## Project Overview

This project is a complete pipeline for classroom engagement monitoring. It combines:
- a vision analyzer (`main.py` + `vision.py`) that detects faces and attention states,
- a backend API (`cloud/server.py`) that stores events in SQLite,
- a dashboard (`dashboard/app.py` + `dashboard/templates/index.html`) that displays live data,
- an NLP query console backed by `nlp/query_handler.py`,
- optional MQTT-ready alert publishing via `mqtt_client.py`.

The workflow is:
1. `main.py` captures a webcam frame or runs simulated vision.
2. Detection results are published locally and sent to the backend.
3. `cloud/server.py` stores events in `classroom.db` and exposes API routes.
4. The dashboard fetches stats and logs from the backend.
5. The NLP query console sends a question to the backend and receives a text answer.

---

## File structure and responsibilities

### Root files

- `main.py`
  - Entry point for the vision analyzer.
  - Captures webcam frames using OpenCV.
  - Uses `VisionAnalyzer` from `vision.py` or simulation fallback.
  - Sends summary/face data to backend API `/api/events`.
  - Publishes simulated IoT LED state via `mqtt_client.py`.

- `vision.py`
  - Implements the face and attention detection logic.
  - Defines data classes `DetectionResult` and `FrameAnalysis`.
  - Draws overlays on video frames.

- `mqtt_client.py`
  - Contains `SimulatedAlertPublisher` and `MQTTAlertPublisher`.
  - `SimulatedAlertPublisher` prints LED states to terminal.
  - `MQTTAlertPublisher` connects to an MQTT broker if real mode is enabled.

- `requirements.txt`
  - Lists Python dependencies: `Flask`, `mediapipe`, `opencv-python`, `paho-mqtt`, `requests`.

### Backend

- `cloud/server.py`
  - Flask backend app and API server.
  - Stores event rows in SQLite database `classroom.db`.
  - Creates `events` table and runs schema migrations at startup.
  - Provides endpoints:
    - `/` — backend dashboard entrypoint.
    - `/health` — health check.
    - `/api/events` — ingest analyzer events.
    - `/api/current` — latest batch summary.
    - `/api/logs` — recent event log rows.
    - `/api/stats` — aggregated counts.
    - `/api/query` — NLP question endpoint.

- `nlp/query_handler.py`
  - Handles natural-language-style queries against the event database.
  - Supports questions about summary, distracted/sleepy/attentive counts, and emotion counts.
  - Returns JSON answers like "Summary: 10 total face detections...".

### Dashboard

- `dashboard/app.py`
  - Flask app for the front-end dashboard.
  - Fetches backend data server-side using requests to `http://127.0.0.1:5000`.
  - Exposes `/api/query` proxy to the backend query endpoint.
  - Serves template `dashboard/templates/index.html`.

- `dashboard/templates/index.html`
  - HTML dashboard layout.
  - Shows current attention status, stats, and recent logs.
  - Implements the NLP query console with JavaScript.
  - Sends query requests to `/api/query` on the dashboard server.

---

## End-to-end execution flow

### 1. Start the backend

The backend must be running first:

```powershell
cd "c:\Users\chand\OneDrive\Desktop\engagement\classroom-analyzer"
python cloud/server.py
```

What it does:
- creates/updates `classroom.db`
- starts Flask on `http://127.0.0.1:5000`
- exposes `/api/events`, `/api/current`, `/api/logs`, `/api/stats`, `/api/query`

### 2. Start the dashboard

Open a second terminal:

```powershell
cd "c:\Users\chand\OneDrive\Desktop\engagement\classroom-analyzer"
python dashboard/app.py
```

It serves the UI at:
- `http://127.0.0.1:5050`

The dashboard reads backend data and proxies NLP query requests.

### 3. Start the analyzer

Open a third terminal:

```powershell
cd "c:\Users\chand\OneDrive\Desktop\engagement\classroom-analyzer"
python main.py --server-url http://127.0.0.1:5000
```

Optional simulation mode if the webcam is unavailable:

```powershell
python main.py --simulate-vision --server-url http://127.0.0.1:5000
```

What happens in `main.py`:
- parses CLI args, including `--simulate-vision`, `--server-url`, `--mqtt-mode`
- opens webcam with OpenCV or falls back to simulated frames
- analyzes frames every `process_every_nth_frame`
- sends detection payload to backend `/api/events`
- publishes LED state via MQTT simulation
- displays an OpenCV window called `Smart Classroom Engagement Analyzer`

### 4. Live data flow

From `main.py`:
- creates `payload` containing `summary` and `faces`
- posts to `http://127.0.0.1:5000/api/events`
- backend inserts rows into `events`
- dashboard fetches `/api/current`, `/api/stats`, and `/api/logs`
- NLP console posts to dashboard `/api/query`
- dashboard forwards query to backend `/api/query`
- backend uses `nlp/query_handler.py` to answer

---

## Key mechanisms and code references

### Analyzer / vision pipeline

- `main.py` functions:
  - `parse_args()` — CLI configuration.
  - `build_simulated_analysis()` / `build_simulated_frame()` — demo mode.
  - `post_detection()` — sends backend payload.
  - `safe_show()` — displays webcam or simulated output.
  - `main()` — capture loop, analysis, backend post, publisher, UI.

- In `main.py`, the loop does:
  - `capture.grab()` / `capture.retrieve()`
  - `cv2.resize(...)`
  - `analyzer.analyze_frame(frame)` or simulation
  - publish state on change via `publisher.publish_state(...)`
  - `post_detection(...)` every `send_interval`
  - `safe_show(...)` to show results and quit on `q`

- `vision.py` is the actual detection module.
  - if using MediaPipe, it extracts face landmarks.
  - computes attention state, emotion, sleepy score, distraction score.
  - returns `DetectionResult` and `FrameAnalysis`.

### Backend storage and API

- `cloud/server.py` uses SQLite and Flask.
- schema includes fields:
  - `id`, `timestamp`, `attention_state`, `emotion`, `sleepy_score`, `distraction_score`, `eye_ratio`, `head_offset`, `face_found`, `batch_id`, `face_index`, `face_count`
- `compute_summary()` aggregates totals and latest batch.
- `/api/events` stores one row for each detected face.
- `/api/current` returns current batch summary.
- `/api/query` calls `answer_query()`.

### NLP query logic

- `nlp/query_handler.py` checks the text and answers:
  - `summary` keys
  - `distracted`, `sleepy`, `attentive`
  - `happy`, `neutral`, `sad`
- if text is not understood, it returns a help message.

### NLP part implementation

The NLP part is a lightweight rule-based query responder:
- The dashboard sends a POST request to `/api/query` with `{"query": "..."}`.
- The backend route in `cloud/server.py` forwards this request to `nlp/query_handler.py`.
- `answer_query()` normalizes the text to lowercase and matches keywords.
- It runs SQL queries on `classroom.db` to compute counts and summaries.
- Results are returned as JSON with `query` and `answer` fields.

This is not a neural language model; it is a simple text classifier that uses keyword matching and database lookups.

### Cloud / CC part implementation

The “CC part” refers to the cloud/backend component of this project.
- `cloud/server.py` is the central backend API service.
- It uses Flask to expose HTTP endpoints for ingestion, status, logs, stats, and NLP queries.
- The backend stores data in local SQLite (`classroom.db`).
- It creates the `events` table automatically and migrates new columns if needed.
- It computes aggregated dashboards and current batch summaries from stored events.
- It also adds CORS headers so the dashboard and browser can access API endpoints safely.

### SE part implementation

The “SE part” refers to the software engineering architecture and integration:
- Clear separation of concerns:
  - `main.py` handles capture and orchestration,
  - `vision.py` handles detection logic,
  - `cloud/server.py` handles persistence and APIs,
  - `dashboard/app.py` handles UI rendering and proxying,
  - `nlp/query_handler.py` handles query interpretation.
- Modular design makes each layer replaceable.
- The project uses simple REST APIs for communication between the analyzer, backend, and dashboard.
- The dashboard proxies NLP requests through its own `/api/query` endpoint to avoid browser CORS issues.
- Error handling is present in `main.py` to continue running if the backend is temporarily unavailable.
- The software is designed for local end-to-end testing, with all services running on `localhost`.

### ML part implementation

The ML part is the vision and attention detection logic.
- `vision.py` likely uses MediaPipe face landmarks to detect faces and facial geometry.
- It computes per-face metrics such as eye aspect ratio, head offset, and emotion heuristics.
- `DetectionResult` and `FrameAnalysis` capture each face’s state and the classroom summary.
- `main.py` uses `VisionAnalyzer.analyze_frame(frame)` to process video frames.
- The ML logic is combined with simple rules:
  - `sleepy` when eye ratio is low,
  - `distracted` when head offset is large,
  - `attentive` otherwise.
- Emotion output is derived from rules rather than a full neural classifier.

### Implementation summary by layer

- ML layer: `vision.py` + `main.py` capture/analysis loop
- SE layer: `main.py`, `dashboard/app.py`, API routing, and modular file structure
- CC layer: `cloud/server.py`, `classroom.db`, API endpoints, data storage
- NLP layer: `nlp/query_handler.py`, backend query route, dashboard proxy

### Dashboard and query console

- `dashboard/app.py` fetches backend JSON and renders HTML.
- the HTML page includes a query form.
- the query console posts to `/api/query` on the dashboard server.
- the dashboard proxies that request to the backend.

---

## Recommended run order

1. Start backend: `python cloud/server.py`
2. Start dashboard: `python dashboard/app.py`
3. Start analyzer: `python main.py --server-url http://127.0.0.1:5000`
4. Open browser: `http://127.0.0.1:5050`

---

## Troubleshooting

- If the dashboard shows no data:
  - make sure backend is running on `127.0.0.1:5000`
  - make sure analyzer is posting to `--server-url`
- If `main.py` cannot open webcam:
  - use `--simulate-vision`
- If the NLP query console fails:
  - restart the dashboard server after changes
  - verify backend is reachable from `dashboard/app.py`

---

## Where everything lives

- `main.py` — analyzer and overall orchestrator
- `vision.py` — face detection and analysis
- `mqtt_client.py` — alert publisher (simulated or real)
- `cloud/server.py` — backend API and SQLite storage
- `nlp/query_handler.py` — conversational query answers
- `dashboard/app.py` — dashboard frontend server
- `dashboard/templates/index.html` — dashboard UI
- `dashboard/static/style.css` — UI styles
- `requirements.txt` — Python dependencies
- `classroom.db` — runtime SQLite database file

---

## Summary

This project is a local end-to-end classroom engagement demo. It is designed to run on your machine with:
- a backend API for event ingestion and storage,
- a dashboard to visualize live status,
- an analyzer that detects attention state from webcam frames or simulation,
- an NLP query console for simple natural language status questions.

The file `end to end.md` now documents the full flow, responsibilities, key files, and runtime process for the entire project.
