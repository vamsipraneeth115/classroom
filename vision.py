from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import mediapipe as mp


LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


@dataclass
class DetectionResult:
    face_index: int
    attention_state: str
    emotion: str
    sleepy_score: float
    distraction_score: float
    eye_ratio: float
    head_offset: float
    face_found: bool


@dataclass
class FrameAnalysis:
    faces: List[DetectionResult]
    primary_attention_state: str
    primary_emotion: str
    sleepy_score: float
    distraction_score: float
    eye_ratio: float
    head_offset: float
    face_found: bool
    face_count: int


class VisionAnalyzer:
    def __init__(
        self,
        sleepy_eye_threshold: float = 0.18,
        distraction_head_threshold: float = 0.16,
        enable_emotion: bool = False,
        max_faces: int = 5,
    ) -> None:
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max_faces,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.sleepy_eye_threshold = sleepy_eye_threshold
        self.distraction_head_threshold = distraction_head_threshold
        self.enable_emotion = enable_emotion
        self.max_faces = max_faces

    def analyze_frame(self, frame) -> Tuple[FrameAnalysis, object]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            annotated = frame.copy()
            analysis = FrameAnalysis(
                faces=[],
                primary_attention_state="no_face",
                primary_emotion="neutral",
                sleepy_score=0.0,
                distraction_score=0.0,
                eye_ratio=0.0,
                head_offset=0.0,
                face_found=False,
                face_count=0,
            )
            self._draw_overlay(annotated, analysis, 0.0)
            return (
                analysis,
                annotated,
            )

        h, w, _ = frame.shape
        annotated = frame.copy()
        faces: List[DetectionResult] = []
        for face_index, face_landmarks in enumerate(results.multi_face_landmarks[: self.max_faces], start=1):
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

            faces.append(
                DetectionResult(
                    face_index=face_index,
                    attention_state=attention_state,
                    emotion=emotion,
                    sleepy_score=round(sleepy_score, 3),
                    distraction_score=round(distraction_score, 3),
                    eye_ratio=round(eye_ratio, 3),
                    head_offset=round(head_offset, 3),
                    face_found=True,
                )
            )

            x1 = max(min(left_face[0], right_face[0]) - 20, 0)
            y1 = max(min(points[10][1], points[152][1]) - 20, 0)
            x2 = min(max(left_face[0], right_face[0]) + 20, w - 1)
            y2 = min(max(points[10][1], points[152][1]) + 20, h - 1)
            color = self._state_color(attention_state)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated,
                f"Face {face_index}: {attention_state}",
                (x1, max(y1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

        analysis = self._build_frame_analysis(faces)
        self._draw_overlay(annotated, analysis, 0.0)
        return analysis, annotated

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

    @classmethod
    def draw_summary_overlay(cls, frame, analysis: FrameAnalysis, fps: float) -> None:
        cls._draw_overlay(frame, analysis, fps)

    @staticmethod
    def _state_color(attention_state: str) -> Tuple[int, int, int]:
        color_map = {
            "attentive": (0, 200, 0),
            "distracted": (0, 165, 255),
            "sleepy": (0, 0, 255),
            "no_face": (150, 150, 150),
        }
        return color_map.get(attention_state, (255, 255, 255))

    def _build_frame_analysis(self, faces: List[DetectionResult]) -> FrameAnalysis:
        if not faces:
            return FrameAnalysis(
                faces=[],
                primary_attention_state="no_face",
                primary_emotion="neutral",
                sleepy_score=0.0,
                distraction_score=0.0,
                eye_ratio=0.0,
                head_offset=0.0,
                face_found=False,
                face_count=0,
            )

        state_priority = {"sleepy": 3, "distracted": 2, "attentive": 1}
        primary_face = max(faces, key=lambda face: state_priority.get(face.attention_state, 0))
        primary_emotion = Counter(face.emotion for face in faces).most_common(1)[0][0]
        face_count = len(faces)
        return FrameAnalysis(
            faces=faces,
            primary_attention_state=primary_face.attention_state,
            primary_emotion=primary_emotion,
            sleepy_score=round(sum(face.sleepy_score for face in faces) / face_count, 3),
            distraction_score=round(sum(face.distraction_score for face in faces) / face_count, 3),
            eye_ratio=round(sum(face.eye_ratio for face in faces) / face_count, 3),
            head_offset=round(sum(face.head_offset for face in faces) / face_count, 3),
            face_found=True,
            face_count=face_count,
        )

    @classmethod
    def _draw_overlay(cls, frame, analysis: FrameAnalysis, fps: float) -> None:
        color = cls._state_color(analysis.primary_attention_state)
        cv2.rectangle(frame, (8, 8), (340, 145), (18, 18, 18), -1)
        cv2.putText(frame, f"Class state: {analysis.primary_attention_state}", (18, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)
        cv2.putText(frame, f"Faces detected: {analysis.face_count}", (18, 61), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1)
        cv2.putText(frame, f"Emotion: {analysis.primary_emotion}", (18, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1)
        cv2.putText(frame, f"Avg EAR: {analysis.eye_ratio:.3f}", (18, 109), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1)
        cv2.putText(frame, f"Avg head offset: {analysis.head_offset:.3f}", (18, 132), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1)
        if fps > 0:
            cv2.putText(frame, f"FPS: {fps:.1f}", (235, 132), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1)
        if not analysis.face_found:
            cv2.putText(frame, "No faces found", (190, 61), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 1)
