"""Shared control signals for AuraOS hand tracking."""

from __future__ import annotations

import json
import time
from pathlib import Path

CONTROL_FILE = Path(__file__).resolve().parents[1] / "ui" / "gesture_control.json"


def clear_stop_request() -> None:
    _write({"stop_requested": False, "updated_at": time.time()})


def request_stop(reason: str = "voice") -> None:
    _write({"stop_requested": True, "reason": reason, "updated_at": time.time()})


def should_stop() -> bool:
    try:
        payload = json.loads(CONTROL_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False

    return bool(payload.get("stop_requested"))


def _write(payload: dict[str, object]) -> None:
    CONTROL_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = CONTROL_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(payload), encoding="utf-8")
    temp_file.replace(CONTROL_FILE)
