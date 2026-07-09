"""Camera capture helpers for hand tracking."""

from __future__ import annotations

import sys


class Camera:
    """Thin wrapper around OpenCV camera capture."""

    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480) -> None:
        self.device_index = device_index
        self.width = width
        self.height = height
        self._capture = None

    def start(self) -> None:
        cv2 = _require_cv2()
        backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else 0
        self._capture = cv2.VideoCapture(self.device_index, backend)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        if not self._capture.isOpened():
            permission_hint = ""
            if sys.platform == "darwin":
                permission_hint = (
                    " On macOS, open System Settings > Privacy & Security > Camera "
                    "and allow your terminal app or Python."
                )
            raise RuntimeError(
                f"Could not open camera at index {self.device_index}. "
                "Check camera permissions and make sure no other app is using it."
                f"{permission_hint}"
            )

    def read_frame(self):
        if self._capture is None:
            raise RuntimeError("Camera is not started.")

        ok, frame = self._capture.read()
        return frame if ok else None

    def stop(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


def _require_cv2():
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "Hand tracking requires OpenCV. Install dependencies with "
            "`python3 -m pip install -r requirements.txt`."
        ) from error
    return cv2
