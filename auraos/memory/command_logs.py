"""Store and retrieve command logs."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CommandLogEntry:
    """A single command lifecycle record."""

    timestamp: str
    command: str
    intent_kind: str
    action: str
    allowed: bool
    success: bool
    feedback: str


class CommandLogger:
    """Append command records as JSON lines."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or Path(__file__).resolve().parent / "command_logs.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        command: str,
        intent_kind: str,
        action: str,
        allowed: bool,
        success: bool,
        feedback: str,
    ) -> CommandLogEntry:
        entry = CommandLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            command=command,
            intent_kind=intent_kind,
            action=action,
            allowed=allowed,
            success=success,
            feedback=feedback,
        )

        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(asdict(entry)) + "\n")

        return entry

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []

        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        recent_lines = lines[-limit:]
        return [json.loads(line) for line in recent_lines if line.strip()]
