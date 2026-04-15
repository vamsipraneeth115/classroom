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


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


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
                face_found INTEGER DEFAULT 1,
                batch_id TEXT,
                face_index INTEGER DEFAULT 0,
                face_count INTEGER DEFAULT 1
            )
            """
        )
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(events)").fetchall()
        }
        migrations = {
            "batch_id": "ALTER TABLE events ADD COLUMN batch_id TEXT",
            "face_index": "ALTER TABLE events ADD COLUMN face_index INTEGER DEFAULT 0",
            "face_count": "ALTER TABLE events ADD COLUMN face_count INTEGER DEFAULT 1",
        }
        for column_name, sql in migrations.items():
            if column_name not in existing_columns:
                conn.execute(sql)
        conn.commit()


def fetch_logs(limit: int = 100) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, attention_state, emotion, sleepy_score,
                   distraction_score, eye_ratio, head_offset, face_found,
                   batch_id, face_index, face_count
            FROM events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def compute_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS count FROM events WHERE face_found = 1"
        ).fetchone()["count"]
        no_face_frames = conn.execute(
            "SELECT COUNT(*) AS count FROM events WHERE face_found = 0"
        ).fetchone()["count"]
        state_rows = conn.execute(
            """
            SELECT attention_state, COUNT(*) AS count
            FROM events
            WHERE face_found = 1
            GROUP BY attention_state
            """
        ).fetchall()
        emotion_rows = conn.execute(
            """
            SELECT emotion, COUNT(*) AS count
            FROM events
            WHERE face_found = 1
            GROUP BY emotion
            """
        ).fetchall()
        latest_event = conn.execute(
            """
            SELECT id, batch_id, timestamp, attention_state, emotion, sleepy_score, distraction_score,
                   eye_ratio, head_offset, face_found, face_index, face_count
            FROM events
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    states = {row["attention_state"]: row["count"] for row in state_rows}
    emotions = {row["emotion"]: row["count"] for row in emotion_rows}
    return {
        "total_events": total,
        "no_face_frames": no_face_frames,
        "attention_counts": states,
        "emotion_counts": emotions,
        "current": compute_current_batch(latest_event["batch_id"]) if latest_event and latest_event["batch_id"] else (dict(latest_event) if latest_event else None),
    }


def compute_current_batch(batch_id: str | None) -> Dict[str, Any] | None:
    if batch_id is None:
        return None

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, attention_state, emotion, sleepy_score, distraction_score,
                   eye_ratio, head_offset, face_found, face_index, face_count
            FROM events
            WHERE batch_id = ?
            ORDER BY face_index ASC, id ASC
            """,
            (batch_id,),
        ).fetchall()

    if not rows:
        return None

    face_rows = [row for row in rows if row["face_found"]]
    if not face_rows:
        row = rows[0]
        return {
            "timestamp": row["timestamp"],
            "attention_state": "no_face",
            "emotion": "neutral",
            "sleepy_score": 0.0,
            "distraction_score": 0.0,
            "eye_ratio": 0.0,
            "head_offset": 0.0,
            "face_count": 0,
            "faces": [],
        }

    state_priority = {"sleepy": 3, "distracted": 2, "attentive": 1}
    primary_row = max(face_rows, key=lambda row: state_priority.get(row["attention_state"], 0))
    return {
        "timestamp": face_rows[0]["timestamp"],
        "attention_state": primary_row["attention_state"],
        "emotion": primary_row["emotion"],
        "sleepy_score": round(sum(row["sleepy_score"] for row in face_rows) / len(face_rows), 3),
        "distraction_score": round(sum(row["distraction_score"] for row in face_rows) / len(face_rows), 3),
        "eye_ratio": round(sum(row["eye_ratio"] for row in face_rows) / len(face_rows), 3),
        "head_offset": round(sum(row["head_offset"] for row in face_rows) / len(face_rows), 3),
        "face_count": len(face_rows),
        "faces": [
            {
                "face_index": row["face_index"],
                "attention_state": row["attention_state"],
                "emotion": row["emotion"],
            }
            for row in face_rows
        ],
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
    batch_id = payload.get("batch_id") or datetime.now(UTC).isoformat(timespec="milliseconds")
    summary = payload.get("summary", {})
    faces = payload.get("faces", [])
    timestamp = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    if faces:
        events = [
            {
                "timestamp": timestamp,
                "attention_state": face.get("attention_state", "attentive"),
                "emotion": face.get("emotion", "neutral"),
                "sleepy_score": float(face.get("sleepy_score", 0)),
                "distraction_score": float(face.get("distraction_score", 0)),
                "eye_ratio": float(face.get("eye_ratio", 0)),
                "head_offset": float(face.get("head_offset", 0)),
                "face_found": 1 if face.get("face_found", True) else 0,
                "batch_id": batch_id,
                "face_index": int(face.get("face_index", index)),
                "face_count": len(faces),
            }
            for index, face in enumerate(faces, start=1)
        ]
    else:
        events = [
            {
                "timestamp": timestamp,
                "attention_state": summary.get("attention_state", "no_face"),
                "emotion": summary.get("emotion", "neutral"),
                "sleepy_score": float(summary.get("sleepy_score", 0)),
                "distraction_score": float(summary.get("distraction_score", 0)),
                "eye_ratio": float(summary.get("eye_ratio", 0)),
                "head_offset": float(summary.get("head_offset", 0)),
                "face_found": 1 if summary.get("face_found", False) else 0,
                "batch_id": batch_id,
                "face_index": 0,
                "face_count": int(summary.get("face_count", 0)),
            }
        ]

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO events (
                timestamp, attention_state, emotion, sleepy_score,
                distraction_score, eye_ratio, head_offset, face_found,
                batch_id, face_index, face_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event["timestamp"],
                    event["attention_state"],
                    event["emotion"],
                    event["sleepy_score"],
                    event["distraction_score"],
                    event["eye_ratio"],
                    event["head_offset"],
                    event["face_found"],
                    event["batch_id"],
                    event["face_index"],
                    event["face_count"],
                )
                for event in events
            ],
        )
        conn.commit()

    current = compute_current_batch(batch_id)
    print(
        f"[backend] stored batch at {timestamp} "
        f"faces={len(faces)} class_state={(current or {}).get('attention_state', 'no_face')}",
        flush=True,
    )
    return jsonify({"message": "events stored", "event": current}), 201


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


@app.route("/api/query", methods=["OPTIONS", "POST"])
def query():
    if request.method == "OPTIONS":
        return jsonify({}), 204

    payload = request.get_json(force=True)
    query_text = payload.get("query", "")
    answer = answer_query(query_text, DB_PATH)
    return jsonify(answer)


init_db()


if __name__ == "__main__":
    print("[backend] server starting on http://127.0.0.1:5000", flush=True)
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
