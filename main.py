from __future__ import annotations

import argparse
import uuid
import time
from typing import Any, Dict

import cv2
import numpy as np
import requests

from mqtt_client import MQTTConfig, build_publisher
from vision import DetectionResult, FrameAnalysis, VisionAnalyzer


def post_detection(server_url: str, analysis: FrameAnalysis) -> None:
    payload: Dict[str, Any] = {
        "batch_id": str(uuid.uuid4()),
        "summary": {
            "attention_state": analysis.primary_attention_state,
            "emotion": analysis.primary_emotion,
            "sleepy_score": analysis.sleepy_score,
            "distraction_score": analysis.distraction_score,
            "eye_ratio": analysis.eye_ratio,
            "head_offset": analysis.head_offset,
            "face_found": analysis.face_found,
            "face_count": analysis.face_count,
        },
        "faces": [
            {
                "face_index": face.face_index,
                "attention_state": face.attention_state,
                "emotion": face.emotion,
                "sleepy_score": face.sleepy_score,
                "distraction_score": face.distraction_score,
                "eye_ratio": face.eye_ratio,
                "head_offset": face.head_offset,
                "face_found": face.face_found,
            }
            for face in analysis.faces
        ],
    }
    try:
        requests.post(f"{server_url}/api/events", json=payload, timeout=3)
    except requests.RequestException as exc:
        print(f"Backend unavailable: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Classroom Engagement Analyzer")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--server-url", default="http://127.0.0.1:5000")
    parser.add_argument("--mqtt-mode", choices=["simulate", "real"], default="simulate")
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--send-interval", type=float, default=2.0)
    parser.add_argument("--simulate-vision", action="store_true")
    parser.add_argument("--frame-width", type=int, default=480)
    parser.add_argument("--frame-height", type=int, default=360)
    parser.add_argument("--process-every-nth-frame", type=int, default=2)
    parser.add_argument("--disable-emotion", action="store_true")
    parser.add_argument("--max-faces", type=int, default=5)
    return parser.parse_args()


def build_simulated_result(step: int, emotion_enabled: bool) -> DetectionResult:
    states = [
        ("attentive", "happy" if emotion_enabled else "neutral", 0.28, 0.03),
        ("distracted", "neutral", 0.25, 0.24),
        ("sleepy", "sad" if emotion_enabled else "neutral", 0.11, 0.05),
    ]
    attention_state, emotion, eye_ratio, head_offset = states[step % len(states)]
    sleepy_score = 0.9 if attention_state == "sleepy" else 0.1
    distraction_score = 0.9 if attention_state == "distracted" else 0.1
    return DetectionResult(
        face_index=1,
        attention_state=attention_state,
        emotion=emotion,
        sleepy_score=sleepy_score,
        distraction_score=distraction_score,
        eye_ratio=eye_ratio,
        head_offset=head_offset,
        face_found=True,
    )


def build_simulated_analysis(step: int, emotion_enabled: bool) -> FrameAnalysis:
    face_count = (step % 3) + 1
    faces = []
    for offset in range(face_count):
        face = build_simulated_result(step + offset, emotion_enabled=emotion_enabled)
        face.face_index = offset + 1
        faces.append(face)

    state_priority = {"sleepy": 3, "distracted": 2, "attentive": 1}
    primary_face = max(faces, key=lambda item: state_priority.get(item.attention_state, 0))
    return FrameAnalysis(
        faces=faces,
        primary_attention_state=primary_face.attention_state,
        primary_emotion=primary_face.emotion,
        sleepy_score=round(sum(face.sleepy_score for face in faces) / face_count, 3),
        distraction_score=round(sum(face.distraction_score for face in faces) / face_count, 3),
        eye_ratio=round(sum(face.eye_ratio for face in faces) / face_count, 3),
        head_offset=round(sum(face.head_offset for face in faces) / face_count, 3),
        face_found=True,
        face_count=face_count,
    )


def build_simulated_frame(analysis: FrameAnalysis):
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    frame[:] = (32, 36, 44)
    cv2.rectangle(frame, (70, 55), (890, 485), (55, 62, 74), -1)
    positions = [(260, 240), (480, 220), (700, 245)]
    color = VisionAnalyzer._state_color(analysis.primary_attention_state)
    for face, center in zip(analysis.faces, positions):
        cx, cy = center
        face_color = VisionAnalyzer._state_color(face.attention_state)
        cv2.circle(frame, (cx, cy), 75, (220, 220, 220), 3)
        cv2.circle(frame, (cx - 28, cy - 18), 10, (220, 220, 220), -1)
        cv2.circle(frame, (cx + 28, cy - 18), 10, (220, 220, 220), -1)
        cv2.ellipse(frame, (cx, cy + 28), (32, 14), 0, 0, 180, (220, 220, 220), 3)
        cv2.putText(frame, f"Face {face.face_index}: {face.attention_state}", (cx - 72, cy + 110), cv2.FONT_HERSHEY_SIMPLEX, 0.55, face_color, 2)

    cv2.putText(frame, "SIMULATION MODE", (90, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
    cv2.putText(
        frame,
        f"Class state: {analysis.primary_attention_state}",
        (90, 400),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        color,
        3,
    )
    cv2.putText(
        frame,
        f"Faces detected: {analysis.face_count} | Emotion: {analysis.primary_emotion}",
        (90, 445),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (240, 240, 240),
        2,
    )
    cv2.putText(
        frame,
        "Webcam unavailable: cycling demo states locally",
        (90, 160),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (190, 190, 190),
        2,
    )
    return frame


def safe_show(window_name: str, frame) -> bool:
    try:
        cv2.imshow(window_name, frame)
        return cv2.waitKey(15) & 0xFF == ord("q")
    except cv2.error:
        return False


def main() -> None:
    args = parse_args()
    publisher = build_publisher(
        args.mqtt_mode,
        MQTTConfig(broker_host=args.mqtt_host, broker_port=args.mqtt_port),
    )
    capture = cv2.VideoCapture(args.camera_index)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.frame_width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.frame_height)
    use_simulated_vision = args.simulate_vision or not capture.isOpened()
    analyzer = None if use_simulated_vision else VisionAnalyzer(
        enable_emotion=not args.disable_emotion,
        max_faces=args.max_faces,
    )

    if use_simulated_vision:
        print("Webcam unavailable. Falling back to simulation-only vision mode.")
    else:
        print(f"Webcam opened successfully at {args.frame_width}x{args.frame_height}.")

    print("Press 'q' to quit the analyzer window.")
    print(f"Processing every {args.process_every_nth_frame} frame(s). Emotion enabled: {not args.disable_emotion}")

    last_sent_at = 0.0
    last_published_state = None
    simulation_step = 0
    frame_counter = 0
    fps = 0.0
    fps_started_at = time.time()
    fps_frame_counter = 0
    last_analysis = build_simulated_analysis(0, emotion_enabled=not args.disable_emotion)
    last_frame = build_simulated_frame(last_analysis)

    try:
        while True:
            if use_simulated_vision:
                analysis = build_simulated_analysis(simulation_step, emotion_enabled=not args.disable_emotion)
                annotated = build_simulated_frame(analysis)
                simulation_step += 1
                last_analysis = analysis
                last_frame = annotated
                time.sleep(1)
            else:
                ok = capture.grab()
                if not ok:
                    print("Failed to read frame from webcam. Switching to simulation mode.")
                    use_simulated_vision = True
                    analyzer = None
                    continue
                ok, frame = capture.retrieve()
                if not ok:
                    continue

                frame = cv2.resize(frame, (args.frame_width, args.frame_height))
                frame_counter += 1
                fps_frame_counter += 1
                elapsed = time.time() - fps_started_at
                if elapsed >= 1.0:
                    fps = fps_frame_counter / elapsed
                    fps_frame_counter = 0
                    fps_started_at = time.time()

                if frame_counter % max(args.process_every_nth_frame, 1) == 0:
                    last_analysis, last_frame = analyzer.analyze_frame(frame)
                else:
                    last_frame = frame.copy()
                    VisionAnalyzer.draw_summary_overlay(last_frame, last_analysis, fps)

                analysis = last_analysis
                annotated = last_frame

            if analysis.primary_attention_state != last_published_state:
                publisher.publish_state(analysis.primary_attention_state)
                last_published_state = analysis.primary_attention_state

            now = time.time()
            if now - last_sent_at >= args.send_interval:
                post_detection(args.server_url, analysis)
                last_sent_at = now

            if safe_show("Smart Classroom Engagement Analyzer", annotated):
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()
        if analyzer is not None:
            analyzer.close()
        publisher.close()


if __name__ == "__main__":
    main()
