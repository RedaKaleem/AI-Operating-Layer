"""Landmark validation and duplicate-filter helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence

from auraos.hand_tracking.data_collection.config import LANDMARK_COUNT

Landmark = tuple[float, float, float]


def validate_landmarks(landmarks: Sequence[Sequence[float]]) -> bool:
    """Return True when landmarks have the expected 21 finite x/y/z values."""
    if len(landmarks) != LANDMARK_COUNT:
        return False
    for landmark in landmarks:
        if len(landmark) != 3:
            return False
        if not all(math.isfinite(float(value)) for value in landmark):
            return False
    return True


def flatten_landmarks(landmarks: Sequence[Sequence[float]]) -> list[float]:
    """Flatten 21 (x, y, z) landmarks into x0, y0, z0 ... x20, y20, z20."""
    if not validate_landmarks(landmarks):
        raise ValueError("Expected 21 landmarks with finite x, y, z coordinates.")
    return [float(value) for landmark in landmarks for value in landmark]


def landmark_distance(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> float:
    """Average Euclidean distance between two normalized landmark sets."""
    if not validate_landmarks(first) or not validate_landmarks(second):
        return math.inf

    total = 0.0
    for a, b in zip(first, second, strict=True):
        total += math.sqrt(
            (float(a[0]) - float(b[0])) ** 2
            + (float(a[1]) - float(b[1])) ** 2
            + (float(a[2]) - float(b[2])) ** 2
        )
    return total / LANDMARK_COUNT
