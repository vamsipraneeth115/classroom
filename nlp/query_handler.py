from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict


def _fetch_value(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def answer_query(query: str, db_path: Path) -> Dict[str, str]:
    normalized = query.strip().lower()

    if not normalized:
        return {
            "query": query,
            "answer": "Please ask something like 'Show summary' or 'How many times distracted?'",
        }

    if "summary" in normalized:
        total = _fetch_value(
            db_path,
            "SELECT COUNT(*) AS count FROM events WHERE face_found = 1",
        )["count"]
        no_face = _fetch_value(
            db_path,
            "SELECT COUNT(*) AS count FROM events WHERE face_found = 0",
        )["count"]
        distracted = _fetch_value(
            db_path,
            "SELECT COUNT(*) AS count FROM events WHERE attention_state = ? AND face_found = 1",
            ("distracted",),
        )["count"]
        sleepy = _fetch_value(
            db_path,
            "SELECT COUNT(*) AS count FROM events WHERE attention_state = ? AND face_found = 1",
            ("sleepy",),
        )["count"]
        attentive = _fetch_value(
            db_path,
            "SELECT COUNT(*) AS count FROM events WHERE attention_state = ? AND face_found = 1",
            ("attentive",),
        )["count"]
        return {
            "query": query,
            "answer": (
                f"Summary: {total} total face detections. "
                f"Attentive: {attentive}, Distracted: {distracted}, Sleepy: {sleepy}, No-face frames: {no_face}."
            ),
        }

    for state in ("distracted", "sleepy", "attentive"):
        if state in normalized:
            count = _fetch_value(
                db_path,
                "SELECT COUNT(*) AS count FROM events WHERE attention_state = ? AND face_found = 1",
                (state,),
            )["count"]
            return {
                "query": query,
                "answer": f"{count} face detections were classified as {state}.",
            }

    for emotion in ("happy", "neutral", "sad"):
        if emotion in normalized:
            count = _fetch_value(
                db_path,
                "SELECT COUNT(*) AS count FROM events WHERE emotion = ? AND face_found = 1",
                (emotion,),
            )["count"]
            return {
                "query": query,
                "answer": f"Emotion '{emotion}' appeared {count} times.",
            }

    return {
        "query": query,
        "answer": (
            "I can answer queries like 'Show summary', "
            "'How many times distracted?', or 'How many happy detections?'"
        ),
    }
