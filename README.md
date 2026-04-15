# Smart Classroom Engagement Analyzer

Complete hackathon-ready project for analyzing classroom engagement with a simulated IoT pipeline today and ESP32 MQTT hardware integration tomorrow.

## Features

- Webcam-based classroom monitoring using OpenCV + MediaPipe
- Attention state detection: `attentive`, `distracted`, `sleepy`
- Simulated IoT LED feedback in terminal
- MQTT-ready publishing for ESP32 on topic `classroom/alert`
- Cloud/API backend using Flask + SQLite
- NLP-style query endpoint
- Browser dashboard for live stats and logs

## Project Structure

```text
classroom-analyzer/
├── main.py
├── vision.py
├── mqtt_client.py
├── cloud/
│   └── server.py
├── nlp/
│   └── query_handler.py
├── dashboard/
│   ├── app.py
│   ├── static/
│   │   └── style.css
│   └── templates/
│       └── index.html
├── esp32/
│   └── esp32_code.ino
├── requirements.txt
└── README.md
```

## How It Works

### AI + Vision Layer

- `main.py` opens the webcam.
- `vision.py` uses MediaPipe Face Mesh landmarks.
- Detection logic:
  - `sleepy`: low eye aspect ratio indicates eye closure
  - `distracted`: head offset suggests looking away
  - `attentive`: default when eyes are open and head is centered
- Emotion detection is a lightweight heuristic that outputs `happy`, `neutral`, or `sad`.

### IoT Layer Today

- `mqtt_client.py` runs in simulation mode by default.
- No hardware is required.
- The program prints:
  - `LED ON (sleepy)`
  - `LED ON (distracted)`
  - `LED OFF (attentive)`

### IoT Layer Tomorrow

- Switch to `--mqtt-mode real`.
- The Python app publishes attention state to topic `classroom/alert`.
- The ESP32 subscribes and controls LED on GPIO `2`.

### Cloud Layer

- `cloud/server.py` stores events in `classroom.db`.
- Every event contains timestamp, attention state, emotion, and diagnostic scores.

### NLP Layer

- `nlp/query_handler.py` handles simple natural-language style queries.
- Supported examples:
  - `Show summary`
  - `How many times distracted?`
  - `How many happy detections?`

### Dashboard

- `dashboard/app.py` serves a browser dashboard.
- Shows current status, stats, recent logs, and a query console.

## Run Instructions

### 1. Install dependencies

```powershell
cd classroom-analyzer
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run backend server

```powershell
cd classroom-analyzer
python cloud/server.py
```

Backend URL: `http://127.0.0.1:5000`

### 3. Run dashboard

Open a second terminal:

```powershell
cd classroom-analyzer
python dashboard/app.py
```

Dashboard URL: `http://127.0.0.1:5050`

### 4. Run AI program

Open a third terminal:

```powershell
cd classroom-analyzer
python main.py
```

This will:

- Open webcam feed
- Show attention state and emotion on screen
- Print simulated LED ON/OFF messages in terminal
- Store events in the Flask backend
- Feed the dashboard

### 5. Test NLP queries

Use the dashboard query box and try:

- `Show summary`
- `How many times distracted?`
- `How many times sleepy?`
- `How many happy detections?`

You can also test directly:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/query -ContentType "application/json" -Body '{"query":"Show summary"}'
```

## Demo Today Without Hardware

1. Start backend.
2. Start dashboard.
3. Start `main.py`.
4. Face the camera normally to see `attentive`.
5. Turn your head to one side to trigger `distracted`.
6. Close your eyes briefly to trigger `sleepy`.
7. Watch the terminal for simulated LED output.
8. Confirm logs and stats appear in the dashboard.

## Demo Tomorrow With ESP32

### Hardware needed

- ESP32 board
- Wi-Fi
- MQTT broker such as Mosquitto

### Steps

1. Start an MQTT broker on your machine or network.
2. Update `esp32/esp32_code.ino` with your Wi-Fi and broker IP.
3. Upload the code using Arduino IDE.
4. Run the Python analyzer in MQTT mode:

```powershell
python main.py --mqtt-mode real --mqtt-host 127.0.0.1 --mqtt-port 1883
```

5. Python publishes `attentive`, `distracted`, or `sleepy` to `classroom/alert`.
6. ESP32 receives the message.
7. GPIO 2 LED behavior:
  - `sleepy` -> ON
  - `distracted` -> ON
  - `attentive` -> OFF

## Notes

- This project works without hardware today.
- It is ready for hardware integration tomorrow.
- If your webcam does not open, try:

```powershell
python main.py --camera-index 1
```
