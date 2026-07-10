"""AuraOS hand tracking entry point."""

from __future__ import annotations

import argparse
import sys
import time
import tkinter as tk
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageTk

from auraos.hand_tracking import control as gesture_control
from auraos.hand_tracking.camera import Camera
from auraos.hand_tracking.classifier import GestureClassifier, HandPose
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
    parser.add_argument("--max-hands", type=int, default=2, help="Maximum hands to detect.")
    parser.add_argument("--no-preview", action="store_true", help="Run without an OpenCV preview window.")
    parser.add_argument("--control-cursor", action="store_true", help="Allow gestures to move/click/scroll the cursor.")
    parser.add_argument("--cursor-smoothing", type=float, default=0.55, help="Cursor smoothing from 0.0 to 1.0.")
    parser.add_argument("--cursor-margin", type=float, default=0.12, help="Camera-frame margin expanded to screen edges.")
    parser.add_argument("--debounce-seconds", type=float, default=0.6, help="Minimum time between repeated static events.")
    parser.add_argument("--min-gesture-confidence", type=float, default=0.9, help="Minimum confidence needed to trigger gesture actions.")
    parser.add_argument("--pinch-hold-seconds", type=float, default=0.45, help="Seconds before pinch becomes drag.")
    parser.add_argument("--snap-stop-seconds", type=float, default=0.28, help="Thumb-middle snap/release window that stops hand tracking.")
    parser.add_argument("--no-snap-stop", action="store_true", help="Disable snap gesture stopping hand tracking.")
    parser.add_argument("--no-clap-stop", action="store_true", help="Disable two-hand clap stopping hand tracking.")
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
    clap_detector = ClapStopDetector(enabled=not args.no_clap_stop)
    bus = GestureEventBus()
    bus.subscribe(lambda event: print(event.to_json(), flush=True))
    action_engine = GestureActionEngine(
        cursor=cursor,
        bus=bus,
        mirror_cursor=args.mirror_cursor,
        pinch_hold_seconds=args.pinch_hold_seconds,
        snap_stop_seconds=args.snap_stop_seconds,
        snap_stop_enabled=not args.no_snap_stop,
        min_confidence=args.min_gesture_confidence,
    )

    last_static_gesture: str | None = None
    last_change_time = 0.0
    last_frame_at = time.time()
    fps = 0.0
    preview = None

    try:
        gesture_control.clear_stop_request()
        camera.start()
        if not args.no_preview:
            preview = AuraHandTrackingPreview()
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
            confidence = 0.0
            now = time.time()
            frame_delta = now - last_frame_at
            last_frame_at = now
            if frame_delta > 0:
                fps = (fps * 0.85) + ((1.0 / frame_delta) * 0.15)

            hands = detector.detect(frame)
            if gesture_control.should_stop():
                display_label = "voice_stop"
                if preview is not None:
                    _show_preview(preview, frame, active_landmarks, display_label, cursor_label, args.control_cursor, fps, confidence)
                    time.sleep(0.2)
                break

            if clap_detector.update(hands):
                display_label = "clap_stop"
                bus.publish(GestureEvent(name="clap_stop"))
                if preview is not None:
                    _show_preview(preview, frame, active_landmarks, display_label, cursor_label, args.control_cursor, fps, confidence)
                    time.sleep(0.25)
                break

            if hands:
                landmarks = hands[0]
                active_landmarks = landmarks
                pose = classifier.analyze(landmarks)
                static_gesture = pose.gesture
                display_label = static_gesture
                confidence = pose.confidence
                cursor_label = action_engine.handle_pose(pose, landmarks)
                if action_engine.should_stop:
                    display_label = "snap_stop"
                    if preview is not None:
                        _show_preview(preview, frame, active_landmarks, display_label, cursor_label, args.control_cursor, fps, confidence)
                        time.sleep(0.25)
                    break

                if static_gesture != last_static_gesture and now - last_change_time > args.debounce_seconds:
                    last_static_gesture = static_gesture
                    last_change_time = now
                    if static_gesture != "unknown" and confidence >= args.min_gesture_confidence:
                        bus.publish(GestureEvent(name=static_gesture))

            if preview is not None and _show_preview(preview, frame, active_landmarks, display_label, cursor_label, args.control_cursor, fps, confidence):
                break
    except RuntimeError as error:
        print(error)
        raise SystemExit(1) from error
    except KeyboardInterrupt:
        print("\nAuraOS hand tracking stopped.")
    finally:
        camera.stop()
        detector.close()
        if preview is not None:
            preview.close()


class GestureActionEngine:
    """Turns recognized gestures into cursor/system actions."""

    def __init__(
        self,
        cursor: CursorController | None,
        bus: GestureEventBus,
        mirror_cursor: bool,
        pinch_hold_seconds: float,
        snap_stop_seconds: float,
        snap_stop_enabled: bool,
        min_confidence: float,
    ) -> None:
        self.cursor = cursor
        self.bus = bus
        self.mirror_cursor = mirror_cursor
        self.pinch_hold_seconds = pinch_hold_seconds
        self.snap_stop_seconds = snap_stop_seconds
        self.snap_stop_enabled = snap_stop_enabled
        self.min_confidence = min_confidence
        self.double_pinch_seconds = 0.45
        self.snap_stop_min_seconds = 0.08
        self.snap_stop_min_frames = 3
        self._index_pinch_started_at: float | None = None
        self._index_pinch_dragging = False
        self._last_index_pinch_release = 0.0
        self._last_middle_pinching = False
        self._middle_pinch_started_at: float | None = None
        self._middle_pinch_frames = 0
        self.should_stop = False
        self._last_scroll_y: float | None = None

    def handle_pose(self, pose: HandPose, landmarks: list[tuple[float, float, float]]) -> str:
        self._move_cursor(landmarks)
        if pose.confidence < self.min_confidence:
            x_norm, y_norm, _ = landmarks[INDEX_TIP]
            return f"{pose.gesture} {pose.confidence:.0%} | index x={x_norm:.2f} y={y_norm:.2f}"

        self._handle_index_pinch(pose)
        self._handle_middle_pinch(pose)
        self._handle_two_finger_scroll(pose, landmarks)
        self._handle_static_actions(pose)

        x_norm, y_norm, _ = landmarks[INDEX_TIP]
        return f"{pose.gesture} {pose.confidence:.0%} | index x={x_norm:.2f} y={y_norm:.2f}"

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
        now = time.time()

        if pose.is_thumb_middle_pinch:
            if not self._last_middle_pinching:
                self._middle_pinch_started_at = now
                self._middle_pinch_frames = 0
                self.bus.publish(GestureEvent(name="thumb_middle_pinch_start"))
            self._middle_pinch_frames += 1
            self._last_middle_pinching = True
            return

        if not self._last_middle_pinching:
            return

        pinch_duration = now - self._middle_pinch_started_at if self._middle_pinch_started_at is not None else 999.0
        pinch_frames = self._middle_pinch_frames
        self._last_middle_pinching = False
        self._middle_pinch_started_at = None
        self._middle_pinch_frames = 0

        if (
            self.snap_stop_enabled
            and self.snap_stop_min_seconds <= pinch_duration <= self.snap_stop_seconds
            and pinch_frames >= self.snap_stop_min_frames
            and pose.thumb_middle_distance > 0.12
        ):
            self.should_stop = True
            self.bus.publish(GestureEvent(name="snap_stop", metadata={"duration": round(pinch_duration, 3)}))
            return

        if self.cursor is not None:
            self.cursor.right_click()
            self.bus.publish(GestureEvent(name="right_click"))

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


class ClapStopDetector:
    """Detect a two-hand clap as a stop gesture."""

    def __init__(
        self,
        enabled: bool = True,
        apart_threshold: float = 0.34,
        close_threshold: float = 0.16,
        close_frames_required: int = 2,
        cooldown_seconds: float = 1.0,
    ) -> None:
        self.enabled = enabled
        self.apart_threshold = apart_threshold
        self.close_threshold = close_threshold
        self.close_frames_required = close_frames_required
        self.cooldown_seconds = cooldown_seconds
        self._saw_apart = False
        self._close_frames = 0
        self._last_clap_at = 0.0

    def update(self, hands: list[list[tuple[float, float, float]]]) -> bool:
        if not self.enabled or len(hands) < 2:
            self._close_frames = 0
            return False

        now = time.time()
        if now - self._last_clap_at < self.cooldown_seconds:
            return False

        center_a = _hand_center(hands[0])
        center_b = _hand_center(hands[1])
        distance = _point_distance(center_a, center_b)

        if distance >= self.apart_threshold:
            self._saw_apart = True
            self._close_frames = 0
            return False

        if self._saw_apart and distance <= self.close_threshold:
            self._close_frames += 1
            if self._close_frames >= self.close_frames_required:
                self._last_clap_at = now
                self._saw_apart = False
                self._close_frames = 0
                return True
        else:
            self._close_frames = 0

        return False


class AuraHandTrackingPreview:
    """AuraOS-styled Tk window for the hand-tracking camera preview."""

    def __init__(self, width: int = 980, height: int = 780) -> None:
        self.width = width
        self.height = height
        self.closed = False
        self.photo = None
        self.root = tk.Tk()
        self.root.title("AuraOS")
        self.root.configure(bg="#050912")
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.minsize(820, 640)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("q", lambda _event: self.close())
        self.root.bind("<Escape>", lambda _event: self.close())

        self._build()

    def show(self, frame) -> bool:
        if self.closed:
            return True

        frame_rgb = _bgr_to_rgb(frame)
        image = Image.fromarray(frame_rgb)
        image.thumbnail((900, 560), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image=image)
        self.video_label.configure(image=self.photo)
        self.root.update_idletasks()
        self.root.update()
        return self.closed

    def close(self) -> None:
        self.closed = True
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _build(self) -> None:
        titlebar = tk.Frame(self.root, bg="#303030", height=34)
        titlebar.pack(fill=tk.X)
        titlebar.pack_propagate(False)

        traffic = tk.Frame(titlebar, bg="#303030")
        traffic.pack(side=tk.LEFT, padx=12)
        for color in ("#ff5f57", "#ffbd2e", "#5f6062"):
            dot = tk.Canvas(traffic, width=18, height=18, bg="#303030", highlightthickness=0)
            dot.create_oval(3, 3, 15, 15, fill=color, outline="")
            dot.pack(side=tk.LEFT, padx=4, pady=8)

        tk.Label(titlebar, text="AuraOS", fg="#c8c8c8", bg="#303030", font=("Helvetica", 15, "bold")).pack(pady=5)

        shell = tk.Frame(self.root, bg="#050912", padx=24, pady=24)
        shell.pack(fill=tk.BOTH, expand=True)

        frame = tk.Frame(shell, bg="#07101f", highlightbackground="#2bd7ff", highlightthickness=1, padx=18, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(frame, bg="#07101f")
        header.pack(fill=tk.X)
        tk.Label(header, text="AURAOS", fg="#a84cff", bg="#07101f", font=("Helvetica", 24, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="  Hand Tracking", fg="#d8e7ff", bg="#07101f", font=("Helvetica", 23, "bold")).pack(side=tk.LEFT)
        tk.Button(
            header,
            text="x",
            command=self.close,
            bg="#0b1424",
            fg="#d9e8ff",
            activebackground="#14223a",
            activeforeground="#ffffff",
            bd=0,
            width=3,
        ).pack(side=tk.RIGHT)

        body = tk.Frame(frame, bg="#07101f")
        body.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        video_shell = tk.Frame(body, bg="#0a1426", highlightbackground="#21466d", highlightthickness=1, padx=10, pady=10)
        video_shell.pack(fill=tk.BOTH, expand=True)
        self.video_label = tk.Label(video_shell, bg="#020611")
        self.video_label.pack(expand=True)

        footer = tk.Frame(frame, bg="#0a1426", highlightbackground="#1c355a", highlightthickness=1)
        footer.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            footer,
            text="Controls: index moves cursor  |  thumb+index click/drag  |  thumb+middle right click  |  quick thumb+middle snap stops tracking  |  q closes",
            fg="#cfe4ff",
            bg="#0a1426",
            font=("Helvetica", 11),
            padx=12,
            pady=10,
            anchor="w",
        ).pack(fill=tk.X)


def _show_preview(
    preview: AuraHandTrackingPreview,
    frame,
    landmarks: list[tuple[float, float, float]] | None,
    label: str,
    cursor_label: str,
    cursor_enabled: bool,
    fps: float,
    confidence: float,
) -> bool:
    import cv2

    _draw_hud(frame, label, cursor_label, cursor_enabled, fps, confidence)
    if landmarks:
        _draw_landmarks(frame, landmarks)

    return preview.show(frame)


def _draw_hud(frame, label: str, cursor_label: str, cursor_enabled: bool, fps: float, confidence: float) -> None:
    import cv2

    height, width = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (width, 88), (4, 9, 18), -1)
    cv2.addWeighted(overlay, 0.62, frame, 0.38, 0, frame)

    cv2.putText(frame, "AURAOS HAND TRACKING", (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (230, 246, 255), 2)
    _draw_status_chip(frame, 18, 48, f"Gesture: {label}", (43, 215, 255))
    _draw_status_chip(frame, 210, 48, "Cursor: on" if cursor_enabled else "Cursor: preview", (65, 255, 155))
    _draw_status_chip(frame, 370, 48, f"{fps:04.1f} FPS", (180, 130, 255))
    _draw_status_chip(frame, 500, 48, f"Accuracy: {confidence:.0%}", _accuracy_color(confidence))

    if cursor_label:
        cv2.putText(frame, cursor_label, (18, height - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (230, 246, 255), 2)


def _draw_status_chip(frame, x: int, y: int, text: str, color: tuple[int, int, int]) -> None:
    import cv2

    (text_width, text_height), _baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
    padding_x = 12
    padding_y = 8
    left = x
    top = y - text_height - padding_y
    right = x + text_width + (padding_x * 2)
    bottom = y + padding_y
    cv2.rectangle(frame, (left, top), (right, bottom), (16, 26, 42), -1)
    cv2.rectangle(frame, (left, top), (right, bottom), color, 1)
    cv2.putText(frame, text, (x + padding_x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 1)


def _accuracy_color(confidence: float) -> tuple[int, int, int]:
    if confidence >= 0.9:
        return (65, 255, 155)
    if confidence >= 0.75:
        return (0, 200, 255)
    return (80, 80, 255)


def _hand_center(hand: list[tuple[float, float, float]]) -> tuple[float, float]:
    anchor_indices = (0, 5, 9, 13, 17)
    x = sum(hand[index][0] for index in anchor_indices) / len(anchor_indices)
    y = sum(hand[index][1] for index in anchor_indices) / len(anchor_indices)
    return x, y


def _point_distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5


def _bgr_to_rgb(frame):
    import cv2

    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def _draw_landmarks(frame, landmarks: list[tuple[float, float, float]]) -> None:
    import cv2

    height, width = frame.shape[:2]
    points = [(int(x * width), int(y * height)) for x, y, _ in landmarks]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    left, right = max(0, min(xs) - 18), min(width - 1, max(xs) + 18)
    top, bottom = max(0, min(ys) - 18), min(height - 1, max(ys) + 18)

    overlay = frame.copy()
    cv2.rectangle(overlay, (left, top), (right, bottom), (7, 18, 32), -1)
    cv2.addWeighted(overlay, 0.22, frame, 0.78, 0, frame)
    cv2.rectangle(frame, (left, top), (right, bottom), (43, 215, 255), 1)

    for start, end in HAND_CONNECTIONS:
        cv2.line(frame, points[start], points[end], (18, 78, 112), 5)
        cv2.line(frame, points[start], points[end], (43, 215, 255), 2)

    for index, point in enumerate(points):
        radius = 8 if index in {INDEX_TIP, THUMB_TIP, MIDDLE_TIP} else 4
        color = (
            (0, 255, 0)
            if index == INDEX_TIP
            else (255, 80, 80)
            if index == THUMB_TIP
            else (255, 0, 255)
            if index == MIDDLE_TIP
            else (255, 255, 255)
        )
        if index in {INDEX_TIP, THUMB_TIP, MIDDLE_TIP}:
            cv2.circle(frame, point, radius + 6, color, 1)
        cv2.circle(frame, point, radius, color, -1)

    index_point = points[INDEX_TIP]
    cv2.drawMarker(frame, index_point, (0, 255, 0), cv2.MARKER_CROSS, 26, 2)
    cv2.putText(frame, "index cursor", (index_point[0] + 10, index_point[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.putText(frame, "thumb", (points[THUMB_TIP][0] + 8, points[THUMB_TIP][1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 80, 80), 1)
    cv2.putText(frame, "middle", (points[MIDDLE_TIP][0] + 8, points[MIDDLE_TIP][1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 255), 1)


def _print_gesture_library() -> None:
    current_category = ""
    for spec in GESTURE_LIBRARY:
        if spec.category != current_category:
            current_category = spec.category
            print(f"\n{current_category}")
        suffix = f" - {spec.notes}" if spec.notes else ""
        print(f"  [{spec.status}] {spec.gesture} -> {spec.action}{suffix}")


if __name__ == "__main__":
    main()
