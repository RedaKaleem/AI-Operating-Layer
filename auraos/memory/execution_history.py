"""Execution history storage."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutionHistoryEntry:
    """Record of an attempted action execution."""

    timestamp: str
    command: str
    action: str
    executor: str
    confirmed: bool
    success: bool
    feedback: str


class ExecutionHistory:
    """Append execution records as JSON lines."""

    def __init__(self, history_path: Path | None = None) -> None:
        self.history_path = history_path or Path(__file__).resolve().parent / "execution_history.jsonl"
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        command: str,
        action: str,
        executor: str,
        confirmed: bool,
        success: bool,
        feedback: str,
    ) -> ExecutionHistoryEntry:
        entry = ExecutionHistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            command=command,
            action=action,
            executor=executor,
            confirmed=confirmed,
            success=success,
            feedback=feedback,
        )

        with self.history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(json.dumps(asdict(entry)) + "\n")

        return entry

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []

        lines = self.history_path.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in lines:
            if not line.strip():
                continue

            entry = json.loads(line)
            if str(entry.get("action", "")).startswith("real_"):
                entries.append(entry)

        return entries[-limit:]
