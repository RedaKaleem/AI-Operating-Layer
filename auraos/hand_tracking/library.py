"""Focused AuraOS hand gesture library."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GestureSpec:
    """Describes a supported hand gesture."""

    category: str
    gesture: str
    action: str
    status: str = "implemented"
    notes: str = ""


GESTURE_LIBRARY: tuple[GestureSpec, ...] = (
    GestureSpec("Cursor Control", "Move Index Finger", "Move Cursor"),
    GestureSpec("Cursor Control", "Thumb + Index Pinch", "Left Click"),
    GestureSpec("Cursor Control", "Thumb + Middle Finger Hold/Release", "Right Click"),
    GestureSpec("Cursor Control", "Double Thumb + Index Pinch", "Double Click"),
    GestureSpec("Cursor Control", "Thumb + Index Pinch and Hold", "Drag"),
    GestureSpec("Cursor Control", "Release Pinch or Open Palm", "Drop / Release Drag"),
    GestureSpec("Navigation", "Two Fingers Up/Down", "Scroll"),
    GestureSpec("Session Control", "Clap Both Hands", "Stop Hand Tracking"),
    GestureSpec("Session Control", "Say Activate Gestures", "Start Hand Tracking"),
    GestureSpec("Session Control", "Say Deactivate Hand Tracking", "Stop Hand Tracking"),
)
