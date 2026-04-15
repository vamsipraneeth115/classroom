from __future__ import annotations

import os

import requests
from flask import Flask, jsonify, make_response, render_template, request


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
            "no_face_frames": 0,
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


@app.route("/api/query", methods=["POST"])
def proxy_query():
    payload = request.get_json(force=True)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/query",
            json=payload,
            timeout=5,
        )
        response = make_response(resp.content, resp.status_code)
        response.headers["Content-Type"] = "application/json"
        return response
    except requests.RequestException as exc:
        return jsonify({"query": payload.get("query", ""), "answer": f"Backend request failed: {exc}"}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
