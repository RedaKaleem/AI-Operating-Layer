"""AuraOS hand tracking entry point."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from auraos.hand_tracking.camera import Camera
from auraos.hand_tracking.classifier import GestureClassifier, HandPose, MotionGestureDetector
from auraos.hand_tracking.controller import CursorController
from auraos.hand_tracking.detector import HandDetector
from auraos.hand_tracking.events import GestureEvent, GestureEventBus
from auraos.hand_tracking.library import GESTURE_LIBRARY

WRIST = 0
INDEX_TIP = 8
MIDDLE_TIP = 12
THUMB_TIP = 4

HAND_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AuraOS camera hand tracking.")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index.")
    parser.add_argument("--list-gestures", action="store_true", help="Print the AuraOS gesture library, then exit.")
    parser.add_argument("--width", type=int, default=640, help="Camera capture width.")
    parser.add_argument("--height", type=int, default=480, help="Camera capture height.")
    parser.add_argument(
        "--model-path",
        help="Optional MediaPipe hand_landmarker.task path. Omit this to use mp.solutions.hands.",
    )
    parser.add_argument("--max-hands", type=int, default=1, help="Maximum hands to detect.")
    parser.add_argument("--no-preview", action="store_true", help="Run without an OpenCV preview window.")
    parser.add_argument("--control-cursor", action="store_true", help="Allow gestures to move/click/scroll the cursor.")
    parser.add_argument(
        "--action-profile",
        choices=("desktop", "media"),
        default="desktop",
        help="Resolve overlapping gestures for desktop/navigation or media controls.",
    )
    parser.add_argument("--cursor-smoothing", type=float, default=0.35, help="Cursor smoothing from 0.0 to 1.0.")
    parser.add_argument("--cursor-margin", type=float, default=0.12, help="Camera-frame margin expanded to screen edges.")
    parser.add_argument("--debounce-seconds", type=float, default=0.6, help="Minimum time between repeated static events.")
    parser.add_argument("--pinch-hold-seconds", type=float, default=0.45, help="Seconds before pinch becomes drag.")
    parser.add_argument("--mirror-cursor", action="store_true", default=True, help="Mirror X movement for natural webcam control.")
    parser.add_argument("--no-mirror-cursor", action="store_false", dest="mirror_cursor", help="Disable mirrored cursor X movement.")
    args = parser.parse_args()

    if args.list_gestures:
        _print_gesture_library()
        return

    try:
        camera = Camera(device_index=args.camera, width=args.width, height=args.height)
        detector = HandDetector(model_path=args.model_path, max_hands=args.max_hands)
        cursor = (
            CursorController(smoothing=args.cursor_smoothing, edge_margin=args.cursor_margin)
            if args.control_cursor
            else None
        )
    except RuntimeError as error:
        print(error)
        raise SystemExit(1) from error

    classifier = GestureClassifier()
    motion_detector = MotionGestureDetector()
    bus = GestureEventBus()
    bus.subscribe(lambda event: print(event.to_json(), flush=True))
    action_engine = GestureActionEngine(
        cursor=cursor,
        bus=bus,
        mirror_cursor=args.mirror_cursor,
        profile=args.action_profile,
        pinch_hold_seconds=args.pinch_hold_seconds,
    )

    last_static_gesture: str | None = None
    last_change_time = 0.0

    try:
        camera.start()
        print("AuraOS hand tracking is running. Press q in the preview window or Ctrl+C to quit.")
        if args.control_cursor:
            print("Cursor control is enabled. Move the pointer to the top-left corner for pyautogui failsafe.")
            if sys.platform == "darwin":
                print("On macOS, cursor control also needs Accessibility permission for your terminal app.")

        while True:
            frame = camera.read_frame()
            if frame is None:
                print("Failed to read a frame from the camera.")
                break

            display_label = "no_hand"
            cursor_label = ""
            active_landmarks = None
            hands = detector.detect(frame)
            if hands:
                landmarks = hands[0]
                active_landmarks = landmarks
                pose = classifier.analyze(landmarks)
                swipe = motion_detector.update(landmarks, pose.raised_count)
                if swipe:
                    display_label = swipe
                    last_static_gesture = None
                    bus.publish(GestureEvent(name=swipe))
                    action_engine.handle_swipe(swipe)
                else:
                    static_gesture = pose.gesture
                    display_label = static_gesture
                    cursor_label = action_engine.handle_pose(pose, landmarks)

                    now = time.time()
                    if static_gesture != last_static_gesture and now - last_change_time > args.debounce_seconds:
                        last_static_gesture = static_gesture
                        last_change_time = now
                        if static_gesture != "unknown":
                            bus.publish(GestureEvent(name=static_gesture))

            if not args.no_preview and _show_preview(frame, active_landmarks, display_label, cursor_label):
                break
    except RuntimeError as error:
        print(error)
        raise SystemExit(1) from error
    except KeyboardInterrupt:
        print("\nAuraOS hand tracking stopped.")
    finally:
        camera.stop()
        detector.close()
        if not args.no_preview:
            _destroy_preview()


class GestureActionEngine:
    """Turns recognized gestures into cursor/system actions."""

    def __init__(
        self,
        cursor: CursorController | None,
        bus: GestureEventBus,
        mirror_cursor: bool,
        profile: str,
        pinch_hold_seconds: float,
    ) -> None:
        self.cursor = cursor
        self.bus = bus
        self.mirror_cursor = mirror_cursor
        self.profile = profile
        self.pinch_hold_seconds = pinch_hold_seconds
        self.double_pinch_seconds = 0.45
        self.action_cooldown_seconds = 0.7
        self._index_pinch_started_at: float | None = None
        self._index_pinch_dragging = False
        self._last_index_pinch_release = 0.0
        self._last_middle_pinching = False
        self._last_scroll_y: float | None = None
        self._last_action_at: dict[str, float] = {}

    def handle_pose(self, pose: HandPose, landmarks: list[tuple[float, float, float]]) -> str:
        self._move_cursor(landmarks)
        self._handle_index_pinch(pose)
        self._handle_middle_pinch(pose)
        self._handle_two_finger_scroll(pose, landmarks)
        self._handle_static_actions(pose)

        x_norm, y_norm, _ = landmarks[INDEX_TIP]
        return f"{pose.gesture} | index x={x_norm:.2f} y={y_norm:.2f}"

    def handle_swipe(self, swipe: str) -> None:
        if self.cursor is None:
            return

        if self.profile == "media":
            if swipe == "swipe_right":
                self._cool_action("next_track", self.cursor.next_track)
            elif swipe == "swipe_left":
                self._cool_action("previous_track", self.cursor.previous_track)
            return

        actions = {
            "swipe_left": self.cursor.browser_back,
            "swipe_right": self.cursor.browser_forward,
            "three_finger_swipe_left": self.cursor.previous_desktop,
            "three_finger_swipe_right": self.cursor.next_desktop,
            "swipe_up": self.cursor.mission_control,
            "swipe_down": self.cursor.show_desktop,
        }
        action = actions.get(swipe)
        if action is not None:
            self._cool_action(swipe, action)

    def _move_cursor(self, landmarks: list[tuple[float, float, float]]) -> None:
        if self.cursor is None:
            return

        x_norm, y_norm, _ = landmarks[INDEX_TIP]
        self.cursor.move_to_normalized(x_norm, y_norm, mirror=self.mirror_cursor)

    def _handle_index_pinch(self, pose: HandPose) -> None:
        if self.cursor is None:
            return

        now = time.time()
        if pose.is_thumb_index_pinch:
            if self._index_pinch_started_at is None:
                self._index_pinch_started_at = now
                self.bus.publish(GestureEvent(name="thumb_index_pinch_start"))
            elif not self._index_pinch_dragging and now - self._index_pinch_started_at >= self.pinch_hold_seconds:
                self.cursor.drag_down()
                self._index_pinch_dragging = True
                self.bus.publish(GestureEvent(name="pinch_hold_drag_start"))
            return

        if self._index_pinch_started_at is None:
            return

        was_dragging = self._index_pinch_dragging
        self._index_pinch_started_at = None
        self._index_pinch_dragging = False

        if was_dragging:
            self.cursor.drag_up()
            self.bus.publish(GestureEvent(name="drag_drop"))
            return

        if now - self._last_index_pinch_release <= self.double_pinch_seconds:
            self.cursor.double_click()
            self.bus.publish(GestureEvent(name="double_pinch"))
            self._last_index_pinch_release = 0.0
        else:
            self.cursor.click()
            self.bus.publish(GestureEvent(name="left_click"))
            self._last_index_pinch_release = now

    def _handle_middle_pinch(self, pose: HandPose) -> None:
        if self.cursor is None:
            return

        if pose.is_thumb_middle_pinch and not self._last_middle_pinching:
            self.cursor.right_click()
            self.bus.publish(GestureEvent(name="right_click"))

        self._last_middle_pinching = pose.is_thumb_middle_pinch

    def _handle_two_finger_scroll(self, pose: HandPose, landmarks: list[tuple[float, float, float]]) -> None:
        if self.cursor is None:
            return

        if pose.gesture != "two_fingers":
            self._last_scroll_y = None
            return

        y_norm = landmarks[INDEX_TIP][1]
        if self._last_scroll_y is None:
            self._last_scroll_y = y_norm
            return

        dy = y_norm - self._last_scroll_y
        self._last_scroll_y = y_norm
        if abs(dy) < 0.025:
            return

        self.cursor.scroll("down" if dy > 0 else "up", amount=max(1, int(abs(dy) * 1800)))
        self.bus.publish(GestureEvent(name="two_finger_scroll", metadata={"direction": "down" if dy > 0 else "up"}))

    def _handle_static_actions(self, pose: HandPose) -> None:
        if self.cursor is None:
            return

        if pose.gesture == "open_palm" and self._index_pinch_dragging:
            self.cursor.drag_up()
            self._index_pinch_dragging = False
            self._index_pinch_started_at = None
            self.bus.publish(GestureEvent(name="open_palm_release_drag"))

        if self.profile == "media":
            if pose.gesture == "open_palm":
                self._cool_action("play_pause", self.cursor.play_pause)
            elif pose.gesture == "thumbs_up":
                self.bus.publish(GestureEvent(name="like_current_song"))
            return

        if pose.gesture == "spread_fingers":
            self.bus.publish(GestureEvent(name="maximize_window"))
        elif pose.gesture == "fingers_together":
            self.bus.publish(GestureEvent(name="minimize_window"))
        elif pose.gesture == "closed_fist":
            self.bus.publish(GestureEvent(name="sleep_auraos"))

    def _cool_action(self, name: str, action) -> None:
        now = time.time()
        if now - self._last_action_at.get(name, 0.0) < self.action_cooldown_seconds:
            return

        self._last_action_at[name] = now
        action()
        self.bus.publish(GestureEvent(name=name))


def _show_preview(
    frame,
    landmarks: list[tuple[float, float, float]] | None,
    label: str,
    cursor_label: str,
) -> bool:
    import cv2

    if landmarks:
        _draw_landmarks(frame, landmarks)

    cv2.putText(frame, f"Gesture: {label}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    if cursor_label:
        cv2.putText(frame, cursor_label, (10, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
    cv2.imshow("AuraOS Hand Tracking (press q to quit)", frame)
    return cv2.waitKey(1) & 0xFF == ord("q")


def _draw_landmarks(frame, landmarks: list[tuple[float, float, float]]) -> None:
    import cv2

    height, width = frame.shape[:2]
    points = [(int(x * width), int(y * height)) for x, y, _ in landmarks]

    for start, end in HAND_CONNECTIONS:
        cv2.line(frame, points[start], points[end], (0, 180, 255), 2)

    for index, point in enumerate(points):
        radius = 7 if index in {INDEX_TIP, THUMB_TIP, MIDDLE_TIP} else 4
        color = (
            (0, 255, 0)
            if index == INDEX_TIP
            else (255, 80, 80)
            if index == THUMB_TIP
            else (255, 0, 255)
            if index == MIDDLE_TIP
            else (255, 255, 255)
        )
        cv2.circle(frame, point, radius, color, -1)

    cv2.putText(frame, "index", points[INDEX_TIP], cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(frame, "middle", points[MIDDLE_TIP], cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)


def _print_gesture_library() -> None:
    current_category = ""
    for spec in GESTURE_LIBRARY:
        if spec.category != current_category:
            current_category = spec.category
            print(f"\n{current_category}")
        suffix = f" - {spec.notes}" if spec.notes else ""
        print(f"  [{spec.status}] {spec.gesture} -> {spec.action}{suffix}")


def _destroy_preview() -> None:
    import cv2

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
