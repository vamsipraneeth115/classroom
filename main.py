from __future__ import annotations

import argparse
import time
from typing import Any, Dict

import cv2
import numpy as np
import requests

from mqtt_client import MQTTConfig, build_publisher
from vision import DetectionResult, VisionAnalyzer


def post_detection(server_url: str, result: DetectionResult) -> None:
    payload: Dict[str, Any] = {
        "attention_state": result.attention_state,
        "emotion": result.emotion,
        "sleepy_score": result.sleepy_score,
        "distraction_score": result.distraction_score,
        "eye_ratio": result.eye_ratio,
        "head_offset": result.head_offset,
        "face_found": result.face_found,
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
        attention_state=attention_state,
        emotion=emotion,
        sleepy_score=sleepy_score,
        distraction_score=distraction_score,
        eye_ratio=eye_ratio,
        head_offset=head_offset,
        face_found=True,
    )


def build_simulated_frame(result: DetectionResult):
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    frame[:] = (32, 36, 44)
    cv2.rectangle(frame, (70, 55), (890, 485), (55, 62, 74), -1)
    cv2.circle(frame, (480, 230), 95, (220, 220, 220), 3)
    cv2.circle(frame, (445, 210), 12, (220, 220, 220), -1)
    cv2.circle(frame, (515, 210), 12, (220, 220, 220), -1)
    cv2.ellipse(frame, (480, 270), (40, 18), 0, 0, 180, (220, 220, 220), 3)

    color_map = {
        "attentive": (0, 200, 0),
        "distracted": (0, 165, 255),
        "sleepy": (0, 0, 255),
    }
    color = color_map[result.attention_state]
    cv2.putText(frame, "SIMULATION MODE", (90, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
    cv2.putText(
        frame,
        f"Attention: {result.attention_state}",
        (90, 400),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        color,
        3,
    )
    cv2.putText(
        frame,
        f"Emotion: {result.emotion}",
        (90, 445),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.95,
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
    analyzer = None if use_simulated_vision else VisionAnalyzer(enable_emotion=not args.disable_emotion)

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
    last_result = build_simulated_result(0, emotion_enabled=not args.disable_emotion)
    last_frame = build_simulated_frame(last_result)

    try:
        while True:
            if use_simulated_vision:
                result = build_simulated_result(simulation_step, emotion_enabled=not args.disable_emotion)
                annotated = build_simulated_frame(result)
                simulation_step += 1
                last_result = result
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
                    last_result, last_frame = analyzer.analyze_frame(frame)
                else:
                    last_frame = frame.copy()
                    VisionAnalyzer._draw_overlay(
                        last_frame,
                        last_result.attention_state,
                        last_result.emotion,
                        last_result.eye_ratio,
                        last_result.head_offset,
                        fps,
                        last_result.face_found,
                    )

                result = last_result
                annotated = last_frame

            if result.attention_state != last_published_state:
                publisher.publish_state(result.attention_state)
                last_published_state = result.attention_state

            now = time.time()
            if now - last_sent_at >= args.send_interval:
                post_detection(args.server_url, result)
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
