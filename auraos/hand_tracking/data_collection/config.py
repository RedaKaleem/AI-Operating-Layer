"""Configuration for the AuraOS hand gesture dataset recorder."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_PATH = PROJECT_ROOT / "dataset" / "raw" / "hand_gestures.csv"
DEFAULT_RECORDINGS_DIR = PROJECT_ROOT / "recordings"

LANDMARK_COUNT = 21
GESTURES = [
    "pointing",
    "open_palm",
    "two_fingers",
    "thumb_index_pinch",
    "thumb_middle_pinch",
    "closed_fist",
    "spread_fingers",
    "idle",
]

DEFAULT_SAMPLE_INTERVAL_SECONDS = 0.15
DEFAULT_MIN_CONFIDENCE = 0.70
DEFAULT_DUPLICATE_DISTANCE = 0.015

CSV_COLUMNS = [
    "timestamp",
    "session_id",
    "frame_id",
    "gesture",
    "handedness",
    "confidence",
]
for index in range(LANDMARK_COUNT):
    CSV_COLUMNS.extend([f"x{index}", f"y{index}", f"z{index}"])
