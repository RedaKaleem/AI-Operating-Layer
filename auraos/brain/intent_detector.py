"""Detect user intent from commands."""

from auraos.brain.models import Intent
from auraos.memory.intent_patterns import IntentPatternMemory


class IntentDetector:
    """Simple rule-based intent detector for the foundation layer."""

    def __init__(self, pattern_memory: IntentPatternMemory | None = None) -> None:
        self.pattern_memory = pattern_memory or IntentPatternMemory()

    def detect(self, command: str) -> Intent:
        cleaned_command = command.strip()
        lowered_command = cleaned_command.lower()

        if not cleaned_command:
            return Intent(cleaned_command, "empty", 1.0)

        if lowered_command in {"exit", "quit", "stop"}:
            return Intent(cleaned_command, "exit", 1.0)

        if lowered_command in {"confirm", "yes", "approve"}:
            return Intent(cleaned_command, "confirm", 1.0)

        if lowered_command in {"cancel", "no", "deny"}:
            return Intent(cleaned_command, "cancel", 1.0)

        if lowered_command in {"history", "execution history", "show history", "recent actions"}:
            return Intent(cleaned_command, "execution_history", 1.0)

        if lowered_command in {
            "recent download",
            "latest download",
            "last download",
            "what was the recent file downloaded",
            "what was the latest file downloaded",
            "what did i download recently",
        }:
            return Intent(cleaned_command, "recent_download", 0.95, {"open": "false"})

        if lowered_command in {
            "open recent download",
            "open latest download",
            "open last download",
            "open the recent file downloaded",
            "open the latest file downloaded",
        }:
            return Intent(cleaned_command, "recent_download", 0.95, {"open": "true"})

        if lowered_command in {"learned intents", "show learned intents", "list learned intents"}:
            return Intent(cleaned_command, "list_learned_intents", 1.0)

        learned_intent = self._detect_learning_command(cleaned_command)
        if learned_intent is not None:
            return learned_intent

        learned_match = self.pattern_memory.match(cleaned_command)
        if learned_match is not None:
            learned_pattern, target = learned_match
            entity_names = {
                "app": "app_name",
                "browser": "query",
                "file": "file_query",
            }
            entity_name = entity_names.get(learned_pattern.kind, "query")
            return Intent(
                cleaned_command,
                learned_pattern.kind,
                0.95,
                {entity_name: target, "learned_pattern": learned_pattern.pattern},
            )

        if lowered_command.startswith(("open file ", "open my file ", "find file ", "show file ")):
            file_query = self._strip_prefix(cleaned_command, ("open file ", "open my file ", "find file ", "show file "))
            return Intent(cleaned_command, "file", 0.85, {"file_query": file_query})

        if lowered_command.startswith(("open ", "launch ", "start ")):
            app_name = self._strip_prefix(cleaned_command, ("open ", "launch ", "start "))
            return Intent(cleaned_command, "app", 0.9, {"app_name": app_name})

        if lowered_command.startswith(("search ", "google ", "look up ")):
            query = self._strip_prefix(cleaned_command, ("search ", "google ", "look up "))
            return Intent(cleaned_command, "browser", 0.85, {"query": query})

        if lowered_command in {"help", "what can you do"}:
            return Intent(cleaned_command, "help", 1.0)

        if self._looks_like_conversation(lowered_command):
            return Intent(cleaned_command, "conversation", 0.75, {"topic": cleaned_command})

        return Intent(cleaned_command, "unknown", 0.2)

    def _detect_learning_command(self, command: str) -> Intent | None:
        lowered_command = command.lower()
        prefixes = ("teach app ", "teach browser ", "teach file ")

        for prefix in prefixes:
            if not lowered_command.startswith(prefix):
                continue

            kind = prefix.removeprefix("teach ").strip()
            pattern = command[len(prefix) :].strip()
            return Intent(command, "learn_intent_pattern", 1.0, {"kind": kind, "pattern": pattern})

        return None

    def _strip_prefix(self, command: str, prefixes: tuple[str, ...]) -> str:
        lowered_command = command.lower()

        for prefix in prefixes:
            if lowered_command.startswith(prefix):
                return command[len(prefix) :].strip()

        return command.strip()

    def _looks_like_conversation(self, command: str) -> bool:
        conversational_starters = (
            "can you explain",
            "can you debug",
            "can you fix",
            "can you help",
            "can you plan",
            "could you explain",
            "could you debug",
            "could you help",
            "could you plan",
            "explain",
            "debug",
            "fix this error",
            "why",
            "how",
            "what is",
            "what are",
            "what do you think",
            "should i",
            "give me advice",
            "plan",
            "help me",
            "talk",
            "hello",
            "hi",
            "hey",
        )
        conversational_phrases = (
            "explain this",
            "explain code",
            "debug this",
            "fix this error",
            "help me debug",
            "help me plan",
            "plan my",
            "give me a plan",
            "what should i do",
            "what do you recommend",
        )
        return command.startswith(conversational_starters) or any(
            phrase in command for phrase in conversational_phrases
        )
