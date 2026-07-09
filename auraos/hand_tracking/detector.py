"""MediaPipe hand landmark detection."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class HandDetector:
    """Detect normalized 21-point hand landmarks using MediaPipe."""

    def __init__(self, model_path: str | Path | None = None, max_hands: int = 1) -> None:
        mp = _require_mediapipe()
        self._mp = mp
        self._mode = "solutions"
        self._hands = None
        self._landmarker = None

        if model_path is None:
            if not hasattr(mp, "solutions"):
                raise RuntimeError(
                    "This MediaPipe install does not include mp.solutions. "
                    "Install the pinned dependency with `python3 -m pip install -r requirements.txt`."
                )
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=max_hands,
                min_detection_confidence=0.55,
                min_tracking_confidence=0.55,
            )
            return

        model = Path(model_path).expanduser()
        if not model.exists():
            raise RuntimeError(f"Hand landmark model not found at {model}.")

        self._mode = "tasks"
        base_options = mp.tasks.BaseOptions(
            model_asset_path=str(model),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        )
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_hands=max_hands,
        )
        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)

    def detect(self, frame_bgr):
        cv2 = _require_cv2()
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        if self._mode == "solutions":
            result = self._hands.process(frame_rgb)
            if not result.multi_hand_landmarks:
                return []
            return [[(lm.x, lm.y, lm.z) for lm in hand.landmark] for hand in result.multi_hand_landmarks]

        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._landmarker.detect(mp_image)
        return [[(lm.x, lm.y, lm.z) for lm in hand] for hand in result.hand_landmarks]

    def close(self) -> None:
        if self._hands is not None:
            self._hands.close()
        if self._landmarker is not None:
            self._landmarker.close()


def _require_cv2():
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "Hand tracking requires OpenCV. Install dependencies with "
            "`python3 -m pip install -r requirements.txt`."
        ) from error
    return cv2


def _require_mediapipe():
    cache_root = Path(tempfile.gettempdir()) / "auraos-hand-tracking-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))

    try:
        import mediapipe as mp
    except ImportError as error:
        raise RuntimeError(
            "Hand tracking requires MediaPipe. Install dependencies with "
            "`python3 -m pip install -r requirements.txt`."
        ) from error
    return mp
