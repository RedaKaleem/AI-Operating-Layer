"""Safe live preview for comparing trained and rule-based gesture classifiers."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from auraos.hand_tracking.camera import Camera
from auraos.hand_tracking.classifier import GestureClassifier
from auraos.hand_tracking.detector import DetectedHand, HandDetector
from auraos.hand_tracking.model_training.model_classifier import ModelGestureClassifier

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)


def main() -> None:
    args = parse_args()
    cv2 = _require_cv2()

    camera = Camera(device_index=args.camera, width=args.width, height=args.height)
    detector = HandDetector(model_path=args.mediapipe_model_path, max_hands=args.max_hands)
    rule_classifier = GestureClassifier()
    model_classifier = ModelGestureClassifier(args.gesture_model_path)

    fps = 0.0
    last_frame_at = time.time()

    try:
        camera.start()
        print("AuraOS model preview is running. Press q in the preview window to quit.", flush=True)
        print("Safe mode: no cursor, click, scroll, or system actions are triggered.", flush=True)

        while True:
            frame = camera.read_frame()
            if frame is None:
                print("Failed to read a frame from the camera.")
                break

            now = time.time()
            delta = now - last_frame_at
            last_frame_at = now
            if delta > 0:
                fps = (fps * 0.85) + ((1.0 / delta) * 0.15)

            hands = detector.detect_hands(frame)
            comparison = "no hand detected"
            if hands:
                hand = hands[0]
                rule_pose = rule_classifier.analyze(hand.landmarks)
                model_prediction = model_classifier.predict(hand.landmarks)
                agreement = rule_pose.gesture == model_prediction.gesture
                comparison = (
                    f"Model: {model_prediction.gesture} {model_prediction.confidence:.0%} | "
                    f"Rule: {rule_pose.gesture} {rule_pose.confidence:.0%} | "
                    f"{'AGREE' if agreement else 'DIFFER'}"
                )
                draw_landmarks(cv2, frame, hand)

            draw_overlay(cv2, frame, comparison, hands, fps, args.min_model_confidence)
            cv2.imshow("AuraOS Trained Gesture Model Preview", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in {ord("q"), ord("Q"), 27}:
                break
    finally:
        detector.close()
        camera.stop()
        cv2.destroyAllWindows()


def draw_overlay(cv2, frame, comparison: str, hands: list[DetectedHand], fps: float, min_model_confidence: float) -> None:
    height, width = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (width, 130), (8, 14, 28), -1)
    primary = hands[0] if hands else None
    handedness = primary.handedness if primary else "none"
    mediapipe_confidence = primary.confidence if primary else 0.0
    lines = [
        "AuraOS trained gesture model preview",
        comparison,
        f"MediaPipe hand: {handedness} {mediapipe_confidence:.0%} | FPS: {fps:.1f}",
        f"Model confidence guide: prefer >= {min_model_confidence:.0%} before live control",
        "Q quit | preview only, no cursor control",
    ]
    for index, text in enumerate(lines):
        color = (45, 225, 255) if index == 0 else (226, 239, 255)
        cv2.putText(frame, text, (16, 28 + index * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2, cv2.LINE_AA)


def draw_landmarks(cv2, frame, hand: DetectedHand) -> None:
    height, width = frame.shape[:2]
    points = [(int(x * width), int(y * height)) for x, y, _ in hand.landmarks]
    for start, end in HAND_CONNECTIONS:
        cv2.line(frame, points[start], points[end], (50, 220, 255), 2, cv2.LINE_AA)
    for index, point in enumerate(points):
        radius = 6 if index in {4, 8, 12, 16, 20} else 4
        cv2.circle(frame, point, radius, (255, 120, 80), -1, cv2.LINE_AA)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview trained gesture model predictions without cursor control.")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index.")
    parser.add_argument("--width", type=int, default=640, help="Camera capture width.")
    parser.add_argument("--height", type=int, default=480, help="Camera capture height.")
    parser.add_argument("--max-hands", type=int, default=1, help="Maximum hands to preview.")
    parser.add_argument("--mediapipe-model-path", help="Optional MediaPipe hand_landmarker.task path.")
    parser.add_argument(
        "--gesture-model-path",
        type=Path,
        default=Path("models") / "hand_gesture" / "gesture_model.joblib",
        help="Path to trained gesture_model.joblib.",
    )
    parser.add_argument(
        "--min-model-confidence",
        type=float,
        default=0.80,
        help="Displayed confidence guide for deciding whether live control is ready.",
    )
    return parser.parse_args()


def _require_cv2():
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "Model preview requires OpenCV. Install dependencies with "
            "`python3 -m pip install -r requirements.txt`."
        ) from error
    return cv2


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(error, flush=True)
        raise SystemExit(1) from error
