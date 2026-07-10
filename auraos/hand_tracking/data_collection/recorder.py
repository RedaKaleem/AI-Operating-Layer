"""Keyboard-controlled webcam recorder for labeled hand landmark datasets."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from auraos.hand_tracking.camera import Camera
from auraos.hand_tracking.data_collection.config import (
    DEFAULT_DATASET_PATH,
    DEFAULT_DUPLICATE_DISTANCE,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_RECORDINGS_DIR,
    DEFAULT_SAMPLE_INTERVAL_SECONDS,
    GESTURES,
)
from auraos.hand_tracking.data_collection.dataset_manager import DatasetManager, GestureSample
from auraos.hand_tracking.data_collection.landmark_utils import landmark_distance, validate_landmarks
from auraos.hand_tracking.detector import DetectedHand, HandDetector

LOGGER = logging.getLogger(__name__)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    cv2 = _require_cv2()
    manager = DatasetManager(args.dataset_path, args.recordings_dir)
    session_id = manager.create_session()
    gesture_counts, total_count = manager.counts()

    camera = Camera(device_index=args.camera, width=args.width, height=args.height)
    detector = HandDetector(model_path=args.model_path, max_hands=args.max_hands)

    selected_index = 0
    recording = False
    paused = False
    frame_id = 0
    saved_this_session = 0
    last_sample_at = 0.0
    last_saved: dict[tuple[str, str], list[tuple[float, float, float]]] = {}
    fps = 0.0
    last_frame_at = time.time()

    try:
        camera.start()
        LOGGER.info("Dataset recorder running. Press Q in the camera window to quit.")
        while True:
            frame = camera.read_frame()
            if frame is None:
                LOGGER.warning("Camera returned no frame; stopping recorder.")
                break

            frame_id += 1
            now = time.time()
            delta = now - last_frame_at
            last_frame_at = now
            if delta > 0:
                fps = (fps * 0.85) + ((1.0 / delta) * 0.15)

            hands = detector.detect_hands(frame)
            selected_gesture = GESTURES[selected_index]

            if recording and not paused and now - last_sample_at >= args.sample_interval:
                saved = save_due_samples(
                    manager=manager,
                    session_id=session_id,
                    frame_id=frame_id,
                    gesture=selected_gesture,
                    hands=hands,
                    min_confidence=args.min_confidence,
                    duplicate_distance=args.duplicate_distance,
                    last_saved=last_saved,
                )
                if saved:
                    last_sample_at = now
                    saved_this_session += saved
                    gesture_counts, total_count = manager.counts()

            draw_overlay(
                cv2=cv2,
                frame=frame,
                hands=hands,
                selected_index=selected_index,
                recording=recording,
                paused=paused,
                gesture_count=gesture_counts.get(selected_gesture, 0),
                total_count=total_count,
                fps=fps,
                session_id=session_id,
                saved_this_session=saved_this_session,
            )
            cv2.imshow("AuraOS Gesture Dataset Recorder", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 255:
                continue
            if ord("1") <= key <= ord(str(len(GESTURES))):
                selected_index = key - ord("1")
                LOGGER.info("Selected gesture: %s", GESTURES[selected_index])
            elif key in {ord("r"), ord("R")}:
                recording = True
                paused = False
                LOGGER.info("Recording started for session %s", session_id)
            elif key in {ord("s"), ord("S")}:
                recording = False
                paused = False
                LOGGER.info("Recording stopped.")
            elif key in {ord("p"), ord("P")}:
                if recording:
                    paused = not paused
                    LOGGER.info("Recording %s.", "paused" if paused else "resumed")
            elif key in {ord("d"), ord("D")}:
                recording = False
                paused = False
                deleted = manager.delete_session(session_id)
                session_id = manager.create_session()
                saved_this_session = 0
                last_saved.clear()
                gesture_counts, total_count = manager.counts()
                LOGGER.info("Deleted %s rows and started new session %s", deleted, session_id)
            elif key in {ord("q"), ord("Q"), 27}:
                break
    finally:
        manager.finish_session(session_id)
        detector.close()
        camera.stop()
        cv2.destroyAllWindows()


def save_due_samples(
    manager: DatasetManager,
    session_id: str,
    frame_id: int,
    gesture: str,
    hands: list[DetectedHand],
    min_confidence: float,
    duplicate_distance: float,
    last_saved: dict[tuple[str, str], list[tuple[float, float, float]]],
) -> int:
    saved = 0
    for hand in hands:
        if hand.confidence < min_confidence:
            continue
        if not validate_landmarks(hand.landmarks):
            LOGGER.warning("Skipping malformed landmark set on frame %s", frame_id)
            continue

        duplicate_key = (gesture, hand.handedness)
        previous = last_saved.get(duplicate_key)
        if previous is not None and landmark_distance(previous, hand.landmarks) < duplicate_distance:
            continue

        sample = GestureSample(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            frame_id=frame_id,
            gesture=gesture,
            handedness=hand.handedness,
            confidence=hand.confidence,
            landmarks=hand.landmarks,
        )
        manager.append_sample(sample)
        last_saved[duplicate_key] = list(hand.landmarks)
        saved += 1
    return saved


def draw_overlay(
    cv2,
    frame,
    hands: list[DetectedHand],
    selected_index: int,
    recording: bool,
    paused: bool,
    gesture_count: int,
    total_count: int,
    fps: float,
    session_id: str,
    saved_this_session: int,
) -> None:
    status = "PAUSED" if paused else "RECORDING" if recording else "IDLE"
    status_color = (0, 200, 255) if paused else (40, 220, 80) if recording else (210, 210, 210)
    primary = hands[0] if hands else None
    handedness = primary.handedness if primary else "none"
    confidence = primary.confidence if primary else 0.0

    cv2.rectangle(frame, (0, 0), (frame.shape[1], 178), (8, 14, 28), -1)
    lines = [
        f"Gesture [{selected_index + 1}]: {GESTURES[selected_index]}",
        f"Status: {status}",
        f"Hand: {handedness}  Confidence: {confidence:.0%}",
        f"Samples for gesture: {gesture_count}  Total: {total_count}  Session: {saved_this_session}",
        f"FPS: {fps:.1f}  Session ID: {session_id}",
        "1-8 select | R record | S stop | P pause | D delete session | Q quit",
    ]
    for index, text in enumerate(lines):
        color = status_color if index == 1 else (225, 240, 255)
        cv2.putText(frame, text, (16, 28 + index * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2, cv2.LINE_AA)

    for hand in hands:
        draw_landmarks(cv2, frame, hand)


def draw_landmarks(cv2, frame, hand: DetectedHand) -> None:
    height, width = frame.shape[:2]
    points = [(int(x * width), int(y * height)) for x, y, _ in hand.landmarks]
    connections = (
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (5, 9), (9, 10), (10, 11), (11, 12),
        (9, 13), (13, 14), (14, 15), (15, 16),
        (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
    )
    for start, end in connections:
        cv2.line(frame, points[start], points[end], (50, 220, 255), 2, cv2.LINE_AA)
    for point in points:
        cv2.circle(frame, point, 4, (255, 120, 80), -1, cv2.LINE_AA)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect labeled AuraOS hand gesture landmark samples.")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index.")
    parser.add_argument("--width", type=int, default=640, help="Camera capture width.")
    parser.add_argument("--height", type=int, default=480, help="Camera capture height.")
    parser.add_argument("--max-hands", type=int, default=2, help="Maximum hands to record per frame.")
    parser.add_argument("--model-path", help="Optional MediaPipe hand_landmarker.task path.")
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH, help="CSV path for raw samples.")
    parser.add_argument("--recordings-dir", type=Path, default=DEFAULT_RECORDINGS_DIR, help="Directory for session metadata.")
    parser.add_argument("--sample-interval", type=float, default=DEFAULT_SAMPLE_INTERVAL_SECONDS, help="Seconds between saved samples.")
    parser.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE, help="Minimum MediaPipe confidence to save.")
    parser.add_argument("--duplicate-distance", type=float, default=DEFAULT_DUPLICATE_DISTANCE, help="Minimum average landmark movement to save.")
    return parser.parse_args()


def _require_cv2():
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "Gesture dataset recording requires OpenCV. Install dependencies with "
            "`python3 -m pip install -r requirements.txt`."
        ) from error
    return cv2


if __name__ == "__main__":
    main()
