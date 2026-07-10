"""Classify MediaPipe hand landmarks into AuraOS gestures."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from math import hypot

Landmark = tuple[float, float, float]

WRIST = 0
THUMB_IP = 3
THUMB_TIP = 4
INDEX_PIP = 6
INDEX_TIP = 8
MIDDLE_PIP = 10
MIDDLE_TIP = 12
RING_PIP = 14
RING_TIP = 16
PINKY_PIP = 18
PINKY_TIP = 20

PINCH_DISTANCE_THRESHOLD = 0.06
SPREAD_DISTANCE_THRESHOLD = 0.34
PINCH_TOGETHER_DISTANCE_THRESHOLD = 0.18


@dataclass(frozen=True)
class HandPose:
    """Single-frame hand pose details used by the gesture engine."""

    gesture: str
    fingers_up: dict[str, bool]
    raised_count: int
    thumb_index_distance: float
    thumb_middle_distance: float
    index_pinky_distance: float
    confidence: float

    @property
    def is_thumb_index_pinch(self) -> bool:
        return self.thumb_index_distance < PINCH_DISTANCE_THRESHOLD

    @property
    def is_thumb_middle_pinch(self) -> bool:
        return self.thumb_middle_distance < PINCH_DISTANCE_THRESHOLD


class GestureClassifier:
    """Classify a single frame of 21 hand landmarks."""

    def classify(self, landmarks: Sequence[Landmark]) -> str:
        return self.analyze(landmarks).gesture

    def analyze(self, landmarks: Sequence[Landmark]) -> HandPose:
        if len(landmarks) < 21:
            return HandPose("unknown", {}, 0, 1.0, 1.0, 0.0, 0.0)

        thumb_index_distance = _distance(landmarks[THUMB_TIP], landmarks[INDEX_TIP])
        thumb_middle_distance = _distance(landmarks[THUMB_TIP], landmarks[MIDDLE_TIP])
        index_pinky_distance = _distance(landmarks[INDEX_TIP], landmarks[PINKY_TIP])

        fingers_up = {
            "index": landmarks[INDEX_TIP][1] < landmarks[INDEX_PIP][1],
            "middle": landmarks[MIDDLE_TIP][1] < landmarks[MIDDLE_PIP][1],
            "ring": landmarks[RING_TIP][1] < landmarks[RING_PIP][1],
            "pinky": landmarks[PINKY_TIP][1] < landmarks[PINKY_PIP][1],
        }
        raised_count = sum(fingers_up.values())
        thumb_extended = abs(landmarks[THUMB_TIP][0] - landmarks[WRIST][0]) > abs(
            landmarks[THUMB_IP][0] - landmarks[WRIST][0]
        )

        if thumb_index_distance < PINCH_DISTANCE_THRESHOLD:
            gesture = "thumb_index_pinch"
            confidence = _pinch_confidence(thumb_index_distance)
        elif thumb_middle_distance < PINCH_DISTANCE_THRESHOLD:
            gesture = "thumb_middle_pinch"
            confidence = _pinch_confidence(thumb_middle_distance)
        elif raised_count == 0 and not thumb_extended:
            gesture = "closed_fist"
            confidence = 0.92
        elif raised_count == 0 and thumb_extended and landmarks[THUMB_TIP][1] < landmarks[WRIST][1]:
            gesture = "thumbs_up"
            confidence = 0.9
        elif raised_count >= 3 and index_pinky_distance < PINCH_TOGETHER_DISTANCE_THRESHOLD:
            gesture = "fingers_together"
            confidence = 0.88
        elif raised_count == 4 and thumb_extended and index_pinky_distance > SPREAD_DISTANCE_THRESHOLD:
            gesture = "spread_fingers"
            confidence = 0.92
        elif raised_count == 4 and thumb_extended:
            gesture = "open_palm"
            confidence = 0.94
        elif fingers_up["index"] and fingers_up["middle"] and fingers_up["ring"] and not fingers_up["pinky"]:
            gesture = "three_fingers"
            confidence = 0.9
        elif fingers_up["index"] and fingers_up["middle"] and not fingers_up["ring"] and not fingers_up["pinky"]:
            gesture = "two_fingers"
            confidence = 0.92
        elif fingers_up["index"] and not fingers_up["middle"] and not fingers_up["ring"] and not fingers_up["pinky"]:
            gesture = "pointing"
            confidence = 0.93
        else:
            gesture = "unknown"
            confidence = 0.3

        return HandPose(
            gesture=gesture,
            fingers_up=fingers_up,
            raised_count=raised_count,
            thumb_index_distance=thumb_index_distance,
            thumb_middle_distance=thumb_middle_distance,
            index_pinky_distance=index_pinky_distance,
            confidence=confidence,
        )


class MotionGestureDetector:
    """Detect horizontal and vertical swipe gestures across a short window."""

    def __init__(
        self,
        window_seconds: float = 0.4,
        min_distance: float = 0.25,
        cooldown_seconds: float = 0.8,
    ) -> None:
        self.window_seconds = window_seconds
        self.min_distance = min_distance
        self.cooldown_seconds = cooldown_seconds
        self._history: deque[tuple[float, float, float, int]] = deque()
        self._last_swipe_time = 0.0

    def update(self, landmarks: Sequence[Landmark], raised_count: int = 0) -> str | None:
        if len(landmarks) < 21:
            return None

        now = time.time()
        wrist_x = landmarks[WRIST][0]
        wrist_y = landmarks[WRIST][1]
        self._history.append((now, wrist_x, wrist_y, raised_count))

        while self._history and now - self._history[0][0] > self.window_seconds:
            self._history.popleft()

        if now - self._last_swipe_time < self.cooldown_seconds or len(self._history) < 2:
            return None

        oldest_x = self._history[0][1]
        oldest_y = self._history[0][2]
        dx = wrist_x - oldest_x
        dy = wrist_y - oldest_y

        if max(abs(dx), abs(dy)) < self.min_distance:
            return None

        self._last_swipe_time = now
        self._history.clear()
        prefix = "three_finger_" if raised_count == 3 else ""
        if abs(dx) > abs(dy):
            return f"{prefix}swipe_right" if dx > 0 else f"{prefix}swipe_left"
        return f"{prefix}swipe_down" if dy > 0 else f"{prefix}swipe_up"


def _distance(first: Landmark, second: Landmark) -> float:
    return hypot(first[0] - second[0], first[1] - second[1])


def _pinch_confidence(distance: float) -> float:
    closeness = max(0.0, min(1.0, 1.0 - (distance / PINCH_DISTANCE_THRESHOLD)))
    return 0.9 + (closeness * 0.1)
