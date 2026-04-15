from __future__ import annotations

import os

import requests
from flask import Flask, render_template


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:5000")
app = Flask(__name__)


def fetch_json(path: str, fallback):
    try:
        response = requests.get(f"{BACKEND_URL}{path}", timeout=3)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return fallback


@app.route("/")
def index():
    current = fetch_json("/api/current", None)
    stats = fetch_json(
        "/api/stats",
        {
            "total_events": 0,
            "attention_counts": {},
            "emotion_counts": {},
            "current": None,
        },
    )
    logs = fetch_json("/api/logs?limit=20", [])
    return render_template(
        "index.html",
        backend_url=BACKEND_URL,
        current=current,
        stats=stats,
        logs=logs,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
