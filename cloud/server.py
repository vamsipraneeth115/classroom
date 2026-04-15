from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from nlp.query_handler import answer_query


DB_PATH = BASE_DIR / "classroom.db"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "dashboard" / "templates"),
    static_folder=str(BASE_DIR / "dashboard" / "static"),
    static_url_path="/static",
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                attention_state TEXT NOT NULL,
                emotion TEXT NOT NULL,
                sleepy_score REAL DEFAULT 0,
                distraction_score REAL DEFAULT 0,
                eye_ratio REAL DEFAULT 0,
                head_offset REAL DEFAULT 0,
                face_found INTEGER DEFAULT 1
            )
            """
        )
        conn.commit()


def fetch_logs(limit: int = 100) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, attention_state, emotion, sleepy_score,
                   distraction_score, eye_ratio, head_offset, face_found
            FROM events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def compute_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]
        state_rows = conn.execute(
            """
            SELECT attention_state, COUNT(*) AS count
            FROM events
            GROUP BY attention_state
            """
        ).fetchall()
        emotion_rows = conn.execute(
            """
            SELECT emotion, COUNT(*) AS count
            FROM events
            GROUP BY emotion
            """
        ).fetchall()
        current = conn.execute(
            """
            SELECT timestamp, attention_state, emotion, sleepy_score, distraction_score
            FROM events
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    states = {row["attention_state"]: row["count"] for row in state_rows}
    emotions = {row["emotion"]: row["count"] for row in emotion_rows}
    return {
        "total_events": total,
        "attention_counts": states,
        "emotion_counts": emotions,
        "current": dict(current) if current else None,
    }


@app.route("/", methods=["GET"])
def dashboard():
    stats = compute_summary()
    logs = fetch_logs(20)
    return render_template(
        "index.html",
        backend_url="http://127.0.0.1:5000",
        current=stats.get("current"),
        stats=stats,
        logs=logs,
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/events", methods=["POST"])
def create_event():
    payload = request.get_json(force=True)
    event = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "attention_state": payload.get("attention_state", "attentive"),
        "emotion": payload.get("emotion", "neutral"),
        "sleepy_score": float(payload.get("sleepy_score", 0)),
        "distraction_score": float(payload.get("distraction_score", 0)),
        "eye_ratio": float(payload.get("eye_ratio", 0)),
        "head_offset": float(payload.get("head_offset", 0)),
        "face_found": 1 if payload.get("face_found", True) else 0,
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO events (
                timestamp, attention_state, emotion, sleepy_score,
                distraction_score, eye_ratio, head_offset, face_found
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["timestamp"],
                event["attention_state"],
                event["emotion"],
                event["sleepy_score"],
                event["distraction_score"],
                event["eye_ratio"],
                event["head_offset"],
                event["face_found"],
            ),
        )
        conn.commit()

    print(
        f"[backend] stored event at {event['timestamp']} "
        f"state={event['attention_state']} emotion={event['emotion']}",
        flush=True,
    )
    return jsonify({"message": "event stored", "event": event}), 201


@app.route("/api/current", methods=["GET"])
def get_current():
    summary = compute_summary()
    return jsonify(summary.get("current"))


@app.route("/api/logs", methods=["GET"])
def get_logs():
    limit = int(request.args.get("limit", 50))
    return jsonify(fetch_logs(limit))


@app.route("/api/stats", methods=["GET"])
def get_stats():
    return jsonify(compute_summary())


@app.route("/api/query", methods=["POST"])
def query():
    payload = request.get_json(force=True)
    query_text = payload.get("query", "")
    answer = answer_query(query_text, DB_PATH)
    return jsonify(answer)


init_db()


if __name__ == "__main__":
    print("[backend] server starting on http://127.0.0.1:5000", flush=True)
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
