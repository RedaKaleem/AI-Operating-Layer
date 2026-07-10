"""Append-safe CSV and session metadata management for gesture datasets."""

from __future__ import annotations

import csv
import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from auraos.hand_tracking.data_collection.config import CSV_COLUMNS, GESTURES, LANDMARK_COUNT
from auraos.hand_tracking.data_collection.landmark_utils import flatten_landmarks, validate_landmarks

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class GestureSample:
    timestamp: str
    session_id: str
    frame_id: int
    gesture: str
    handedness: str
    confidence: float
    landmarks: list[tuple[float, float, float]]


class DatasetManager:
    """Owns CSV writes, row validation, counts, and session metadata."""

    def __init__(self, dataset_path: str | Path, recordings_dir: str | Path) -> None:
        self.dataset_path = Path(dataset_path).expanduser()
        self.recordings_dir = Path(recordings_dir).expanduser()
        self.metadata_path = self.recordings_dir / "session_metadata.json"
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_csv_header()

    def create_session(self) -> str:
        session_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        metadata = self._load_metadata()
        metadata.append(
            {
                "session_id": session_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "dataset_path": str(self.dataset_path),
                "gestures": GESTURES,
                "status": "active",
            }
        )
        self._save_metadata(metadata)
        LOGGER.info("Started dataset recording session %s", session_id)
        return session_id

    def finish_session(self, session_id: str) -> None:
        metadata = self._load_metadata()
        for entry in metadata:
            if entry.get("session_id") == session_id and entry.get("status") == "active":
                entry["status"] = "completed"
                entry["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._save_metadata(metadata)

    def append_sample(self, sample: GestureSample) -> None:
        row = self.sample_to_row(sample)
        if not self.validate_row(row):
            raise ValueError("Refusing to save malformed gesture sample row.")
        with self.dataset_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writerow(row)

    def sample_to_row(self, sample: GestureSample) -> dict[str, str | int | float]:
        values = flatten_landmarks(sample.landmarks)
        row: dict[str, str | int | float] = {
            "timestamp": sample.timestamp,
            "session_id": sample.session_id,
            "frame_id": sample.frame_id,
            "gesture": sample.gesture,
            "handedness": sample.handedness,
            "confidence": f"{sample.confidence:.6f}",
        }
        for index in range(LANDMARK_COUNT):
            row[f"x{index}"] = f"{values[index * 3]:.8f}"
            row[f"y{index}"] = f"{values[index * 3 + 1]:.8f}"
            row[f"z{index}"] = f"{values[index * 3 + 2]:.8f}"
        return row

    def validate_row(self, row: dict[str, object]) -> bool:
        if set(row.keys()) != set(CSV_COLUMNS):
            return False
        if str(row["gesture"]) not in GESTURES:
            return False
        if str(row["handedness"]) not in {"Left", "Right", "Unknown"}:
            return False
        try:
            confidence = float(row["confidence"])
            int(row["frame_id"])
            landmarks = [
                (
                    float(row[f"x{index}"]),
                    float(row[f"y{index}"]),
                    float(row[f"z{index}"]),
                )
                for index in range(LANDMARK_COUNT)
            ]
        except (TypeError, ValueError, KeyError):
            return False
        return 0.0 <= confidence <= 1.0 and validate_landmarks(landmarks)

    def counts(self) -> tuple[dict[str, int], int]:
        gesture_counts = {gesture: 0 for gesture in GESTURES}
        total = 0
        if not self.dataset_path.exists():
            return gesture_counts, total
        with self.dataset_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                gesture = row.get("gesture")
                if gesture in gesture_counts:
                    gesture_counts[gesture] += 1
                    total += 1
        return gesture_counts, total

    def delete_session(self, session_id: str) -> int:
        """Remove rows for a collection session and mark it deleted in metadata."""
        if not self.dataset_path.exists():
            return 0

        kept_rows = []
        deleted = 0
        with self.dataset_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("session_id") == session_id:
                    deleted += 1
                else:
                    kept_rows.append(row)

        fd, temp_name = tempfile.mkstemp(prefix="hand_gestures_", suffix=".csv", dir=str(self.dataset_path.parent))
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            with temp_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                writer.writerows(kept_rows)
            temp_path.replace(self.dataset_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        metadata = self._load_metadata()
        for entry in metadata:
            if entry.get("session_id") == session_id:
                entry["status"] = "deleted"
                entry["deleted_at"] = datetime.now(timezone.utc).isoformat()
                entry["deleted_rows"] = deleted
        self._save_metadata(metadata)
        LOGGER.info("Deleted %s rows from session %s", deleted, session_id)
        return deleted

    def _ensure_csv_header(self) -> None:
        if self.dataset_path.exists() and self.dataset_path.stat().st_size > 0:
            return
        with self.dataset_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()

    def _load_metadata(self) -> list[dict[str, object]]:
        if not self.metadata_path.exists():
            return []
        try:
            with self.metadata_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError:
            LOGGER.warning("Session metadata was malformed; starting a fresh metadata list.")
            return []
        return data if isinstance(data, list) else []

    def _save_metadata(self, metadata: list[dict[str, object]]) -> None:
        with self.metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)
            handle.write("\n")
