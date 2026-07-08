"""Store learned intent patterns."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LearnedIntentPattern:
    """A user-taught command phrase."""

    kind: str
    pattern: str


class IntentPatternMemory:
    """Persist and match learned command patterns."""

    SUPPORTED_KINDS = {"app", "browser", "file"}

    def __init__(self, pattern_path: Path | None = None) -> None:
        self.pattern_path = pattern_path or Path(__file__).resolve().parent / "intent_patterns.json"
        self.pattern_path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, kind: str, pattern: str) -> LearnedIntentPattern:
        normalized_kind = kind.strip().lower()
        normalized_pattern = self._normalize_pattern(pattern)

        if normalized_kind not in self.SUPPORTED_KINDS:
            raise ValueError(f"Unsupported intent kind: {kind}")

        if "{target}" not in normalized_pattern:
            raise ValueError("Learned patterns must include {target}.")

        learned_pattern = LearnedIntentPattern(normalized_kind, normalized_pattern)
        patterns = self.load()

        if learned_pattern not in patterns:
            patterns.append(learned_pattern)
            self._save(patterns)

        return learned_pattern

    def load(self) -> list[LearnedIntentPattern]:
        if not self.pattern_path.exists():
            return []

        try:
            raw_patterns = json.loads(self.pattern_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        if not isinstance(raw_patterns, list):
            return []

        patterns = []
        for raw_pattern in raw_patterns:
            if not isinstance(raw_pattern, dict):
                continue

            kind = raw_pattern.get("kind")
            pattern = raw_pattern.get("pattern")
            if isinstance(kind, str) and isinstance(pattern, str):
                patterns.append(LearnedIntentPattern(kind, pattern))

        return patterns

    def match(self, command: str) -> tuple[LearnedIntentPattern, str] | None:
        normalized_command = command.strip().lower()

        for learned_pattern in self.load():
            match = self._compile_pattern(learned_pattern.pattern).fullmatch(normalized_command)
            if match is None:
                continue

            target = match.group("target").strip()
            if target:
                return learned_pattern, target

        return None

    def _save(self, patterns: list[LearnedIntentPattern]) -> None:
        raw_patterns = [asdict(pattern) for pattern in patterns]
        self.pattern_path.write_text(json.dumps(raw_patterns, indent=2) + "\n", encoding="utf-8")

    def _compile_pattern(self, pattern: str) -> re.Pattern[str]:
        escaped_pattern = re.escape(pattern)
        regex_pattern = escaped_pattern.replace(r"\{target\}", r"(?P<target>.+)")
        return re.compile(regex_pattern, re.IGNORECASE)

    def _normalize_pattern(self, pattern: str) -> str:
        cleaned_pattern = pattern.strip().lower()
        cleaned_pattern = cleaned_pattern.strip("\"'")
        return " ".join(cleaned_pattern.split())
