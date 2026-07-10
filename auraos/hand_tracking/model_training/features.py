"""Dataset loading and feature extraction for gesture model training."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from auraos.hand_tracking.data_collection.config import CSV_COLUMNS, GESTURES, LANDMARK_COUNT

LANDMARK_COLUMNS = [f"{axis}{index}" for index in range(LANDMARK_COUNT) for axis in ("x", "y", "z")]


def load_dataset(path: str | Path) -> pd.DataFrame:
    dataset_path = Path(path).expanduser()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    return pd.read_csv(dataset_path)


def validate_dataframe(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    missing = [column for column in CSV_COLUMNS if column not in df.columns]
    if missing:
        errors.append(f"Missing columns: {', '.join(missing)}")
        return errors

    unknown_gestures = sorted(set(df["gesture"].dropna()) - set(GESTURES))
    if unknown_gestures:
        errors.append(f"Unknown gestures: {', '.join(unknown_gestures)}")

    numeric = df[["confidence", *LANDMARK_COLUMNS]].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        errors.append("Some confidence or landmark values are not numeric.")
    if len(df) == 0:
        errors.append("Dataset is empty.")
    return errors


def filter_dataset(df: pd.DataFrame, min_confidence: float) -> pd.DataFrame:
    filtered = df.copy()
    filtered["confidence"] = pd.to_numeric(filtered["confidence"], errors="coerce")
    filtered = filtered.dropna(subset=["gesture", "confidence", *LANDMARK_COLUMNS])
    filtered = filtered[filtered["gesture"].isin(GESTURES)]
    filtered = filtered[filtered["confidence"] >= min_confidence]
    return filtered.reset_index(drop=True)


def build_features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return engineered landmark features and gesture labels."""
    raw = df[LANDMARK_COLUMNS].astype("float32").to_numpy()
    landmarks = raw.reshape((-1, LANDMARK_COUNT, 3))

    wrist = landmarks[:, [0], :]
    centered = landmarks - wrist
    scale = np.linalg.norm(landmarks[:, 9, :] - landmarks[:, 0, :], axis=1)
    scale = np.maximum(scale, 1e-6).reshape((-1, 1, 1))
    normalized = centered / scale

    fingertip_indices = [4, 8, 12, 16, 20]
    fingertip_distances = []
    for start_index, start in enumerate(fingertip_indices):
        for end in fingertip_indices[start_index + 1 :]:
            distance = np.linalg.norm(normalized[:, start, :] - normalized[:, end, :], axis=1)
            fingertip_distances.append(distance)
    pairwise = np.stack(fingertip_distances, axis=1).astype("float32")

    features = np.concatenate(
        [
            raw.astype("float32"),
            normalized.reshape((len(df), -1)).astype("float32"),
            pairwise,
        ],
        axis=1,
    )
    labels = df["gesture"].astype(str).to_numpy()
    return features, labels
