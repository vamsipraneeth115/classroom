from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import mediapipe as mp


LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


@dataclass
class DetectionResult:
    attention_state: str
    emotion: str
    sleepy_score: float
    distraction_score: float
    eye_ratio: float
    head_offset: float
    face_found: bool


class VisionAnalyzer:
    def __init__(
        self,
        sleepy_eye_threshold: float = 0.18,
        distraction_head_threshold: float = 0.16,
        enable_emotion: bool = False,
    ) -> None:
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.sleepy_eye_threshold = sleepy_eye_threshold
        self.distraction_head_threshold = distraction_head_threshold
        self.enable_emotion = enable_emotion

    def analyze_frame(self, frame) -> Tuple[DetectionResult, object]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            annotated = frame.copy()
            self._draw_overlay(annotated, "distracted", "neutral", 0.0, 1.0, 0.0, False)
            return (
                DetectionResult(
                    attention_state="distracted",
                    emotion="neutral",
                    sleepy_score=0.0,
                    distraction_score=1.0,
                    eye_ratio=0.0,
                    head_offset=1.0,
                    face_found=False,
                ),
                annotated,
            )

        face_landmarks = results.multi_face_landmarks[0]
        h, w, _ = frame.shape
        points = [(int(lm.x * w), int(lm.y * h)) for lm in face_landmarks.landmark]

        left_ear = self._eye_aspect_ratio(points, LEFT_EYE)
        right_ear = self._eye_aspect_ratio(points, RIGHT_EYE)
        eye_ratio = (left_ear + right_ear) / 2.0

        nose = points[1]
        left_face = points[234]
        right_face = points[454]
        face_center_x = (left_face[0] + right_face[0]) / 2.0
        face_width = max(abs(right_face[0] - left_face[0]), 1)
        head_offset = abs(nose[0] - face_center_x) / face_width

        sleepy_score = max(0.0, min(1.0, (self.sleepy_eye_threshold - eye_ratio) * 10 + 0.5))
        distraction_score = max(
            0.0,
            min(1.0, (head_offset - self.distraction_head_threshold) * 8 + 0.5),
        )

        if eye_ratio < self.sleepy_eye_threshold:
            attention_state = "sleepy"
        elif head_offset > self.distraction_head_threshold:
            attention_state = "distracted"
        else:
            attention_state = "attentive"

        emotion = "neutral"
        if self.enable_emotion and attention_state == "attentive":
            emotion = "happy"
        elif self.enable_emotion and attention_state == "sleepy":
            emotion = "sad"

        annotated = frame.copy()
        x1 = max(min(left_face[0], right_face[0]) - 20, 0)
        y1 = max(min(points[10][1], points[152][1]) - 20, 0)
        x2 = min(max(left_face[0], right_face[0]) + 20, w - 1)
        y2 = min(max(points[10][1], points[152][1]) + 20, h - 1)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (90, 200, 255), 2)
        self._draw_overlay(
            annotated,
            attention_state,
            emotion,
            eye_ratio,
            head_offset,
            0.0,
            True,
        )

        result = DetectionResult(
            attention_state=attention_state,
            emotion=emotion,
            sleepy_score=round(sleepy_score, 3),
            distraction_score=round(distraction_score, 3),
            eye_ratio=round(eye_ratio, 3),
            head_offset=round(head_offset, 3),
            face_found=True,
        )
        return result, annotated

    def close(self) -> None:
        self.face_mesh.close()

    @staticmethod
    def _distance(a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return math.dist(a, b)

    def _eye_aspect_ratio(self, points: List[Tuple[int, int]], eye_indices: List[int]) -> float:
        p1, p2, p3, p4, p5, p6 = [points[idx] for idx in eye_indices]
        vertical_1 = self._distance(p2, p6)
        vertical_2 = self._distance(p3, p5)
        horizontal = self._distance(p1, p4)
        return (vertical_1 + vertical_2) / max(2.0 * horizontal, 1.0)

    @staticmethod
    def _draw_overlay(
        frame,
        attention_state: str,
        emotion: str,
        eye_ratio: float,
        head_offset: float,
        fps: float,
        face_found: bool,
    ) -> None:
        color_map = {
            "attentive": (0, 200, 0),
            "distracted": (0, 165, 255),
            "sleepy": (0, 0, 255),
        }
        color = color_map.get(attention_state, (255, 255, 255))
        cv2.rectangle(frame, (8, 8), (310, 125), (18, 18, 18), -1)
        cv2.putText(frame, f"Attention: {attention_state}", (18, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
        cv2.putText(frame, f"Emotion: {emotion}", (18, 63), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1)
        cv2.putText(frame, f"EAR: {eye_ratio:.3f}", (18, 87), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1)
        cv2.putText(frame, f"Head offset: {head_offset:.3f}", (18, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1)
        if fps > 0:
            cv2.putText(frame, f"FPS: {fps:.1f}", (220, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1)
        if not face_found:
            cv2.putText(frame, "Face not found", (18, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
