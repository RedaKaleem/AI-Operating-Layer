"""Gesture events emitted by hand tracking."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GestureEvent:
    """Serializable gesture event."""

    name: str
    confidence: float = 1.0
    metadata: dict[str, object] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, object]:
        return {
            "gesture": self.name,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            **self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


class GestureEventBus:
    """Tiny publish/subscribe bus for gesture events."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[GestureEvent], None]] = []

    def subscribe(self, callback: Callable[[GestureEvent], None]) -> None:
        self._subscribers.append(callback)

    def publish(self, event: GestureEvent) -> None:
        for callback in self._subscribers:
            callback(event)

