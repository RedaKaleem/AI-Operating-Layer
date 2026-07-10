"""Optional model-backed classifier wrapper for offline testing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from auraos.hand_tracking.data_collection.config import CSV_COLUMNS, LANDMARK_COUNT
from auraos.hand_tracking.model_training.features import build_features


@dataclass(frozen=True)
class ModelGesturePrediction:
    gesture: str
    confidence: float


class ModelGestureClassifier:
    """Load a trained model and predict one landmark set.

    This class is intentionally not connected to the live cursor controller yet.
    """

    def __init__(self, model_path: str | Path = "models/hand_gesture/gesture_model.joblib") -> None:
        self.model = joblib.load(Path(model_path).expanduser())

    def predict(self, landmarks: list[tuple[float, float, float]]) -> ModelGesturePrediction:
        if len(landmarks) != LANDMARK_COUNT:
            raise ValueError(f"Expected {LANDMARK_COUNT} landmarks.")
        row = {
            "timestamp": "",
            "session_id": "",
            "frame_id": 0,
            "gesture": "idle",
            "handedness": "Unknown",
            "confidence": 1.0,
        }
        for index, landmark in enumerate(landmarks):
            row[f"x{index}"], row[f"y{index}"], row[f"z{index}"] = landmark
        df = pd.DataFrame([row], columns=CSV_COLUMNS)
        features, _ = build_features(df)
        probabilities = self.model.predict_proba(features)[0]
        best_index = int(probabilities.argmax())
        return ModelGesturePrediction(
            gesture=str(self.model.classes_[best_index]),
            confidence=float(probabilities[best_index]),
        )
