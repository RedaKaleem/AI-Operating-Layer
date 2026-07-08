"""Safety checks for commands and planned actions."""

import json
import re
from pathlib import Path
from typing import Any

from auraos.brain.models import ActionPlan, SafetyResult


DEFAULT_ALLOWED_ACTIONS = {
    "noop",
    "exit",
    "help",
    "confirm",
    "cancel",
    "conversation_response",
    "execution_history",
    "unknown",
    "real_open_app",
    "real_open_file",
    "real_recent_download",
    "real_search",
}

DEFAULT_ALLOWED_EXECUTORS = {
    "app",
    "browser",
    "system",
}

DEFAULT_BLOCKED_ACTIONS = {
    "delete_file",
    "delete_folder",
    "format_disk",
    "install_package",
    "modify_permissions",
    "move_file",
    "restart_system",
    "run_shell_command",
    "shutdown_system",
    "uninstall_app",
    "write_file",
}

DEFAULT_CONFIRMATION_REQUIRED_ACTIONS = {
    "delete_file",
    "delete_folder",
    "install_package",
    "modify_permissions",
    "move_file",
    "restart_system",
    "run_shell_command",
    "shutdown_system",
    "uninstall_app",
    "write_file",
}

DEFAULT_BLOCKED_COMMAND_PATTERNS = {
    r"\brm\s+-[^\n]*r[^\n]*f\b",
    r"\brm\s+-[^\n]*f[^\n]*r\b",
    r"\brm\b",
    r"\bsudo\b",
    r"\bsu\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bformat\b",
    r"\berase\b",
    r"\bwipe\b",
    r"\bdelete\b",
    r"\bremove\b",
    r"\btrash\b",
    r"\buninstall\b",
    r"\bshutdown\b",
    r"\brestart\b",
    r"\breboot\b",
    r"\bkill\b",
    r"\bkillall\b",
    r"\bpkill\b",
    r"\blaunchctl\b",
    r"\bcrontab\b",
    r"\bcurl\b",
    r"\bwget\b",
    r"\bpip\s+install\b",
    r"\bbrew\s+install\b",
    r"\bnpm\s+install\b",
    r"\bmv\b",
    r"\bcp\b",
    r">",
    r">>",
}


class SafetyChecker:
    """Gate plans before they reach executors."""

    def __init__(self, permissions_path: Path | None = None) -> None:
        self.permissions_path = permissions_path or Path(__file__).resolve().parents[1] / "config" / "permissions.json"
        self.permissions = self._load_permissions()
        self.allowed_actions = self._load_string_set("allowed_actions", DEFAULT_ALLOWED_ACTIONS)
        self.allowed_executors = self._load_string_set("allowed_executors", DEFAULT_ALLOWED_EXECUTORS)
        self.blocked_actions = self._load_string_set("blocked_actions", DEFAULT_BLOCKED_ACTIONS)
        self.confirmation_required_actions = self._load_string_set(
            "confirmation_required_actions",
            DEFAULT_CONFIRMATION_REQUIRED_ACTIONS,
        )
        self.blocked_command_patterns = self._load_string_set(
            "blocked_command_patterns",
            DEFAULT_BLOCKED_COMMAND_PATTERNS,
        )

    def check(self, plan: ActionPlan) -> SafetyResult:
        command_block = self._check_command_text(plan.command)
        if command_block is not None:
            return command_block

        if plan.executor not in self.allowed_executors:
            return SafetyResult(False, f"Executor '{plan.executor}' is not allowed.")

        if plan.action in self.blocked_actions:
            return SafetyResult(False, f"Action '{plan.action}' is strictly blocked.")

        if plan.action in self.confirmation_required_actions:
            return SafetyResult(
                False,
                f"Action '{plan.action}' requires confirmation. Type 'confirm' to run it or 'cancel' to discard it.",
                requires_confirmation=True,
            )

        if plan.action in self.allowed_actions:
            return SafetyResult(True, "Action is allowed.")

        return SafetyResult(False, f"Action '{plan.action}' is not allowed by permissions.")

    def _check_command_text(self, command: str) -> SafetyResult | None:
        normalized_command = command.strip().lower()
        if not normalized_command:
            return None

        for pattern in self.blocked_command_patterns:
            if re.search(pattern, normalized_command):
                return SafetyResult(False, "Blocked for safety: destructive or system-level commands require explicit confirmation.")

        return None

    def _load_permissions(self) -> dict[str, Any]:
        if not self.permissions_path.exists():
            return {}

        try:
            permissions = json.loads(self.permissions_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

        if not isinstance(permissions, dict):
            return {}

        return permissions

    def _load_string_set(self, key: str, default: set[str]) -> set[str]:
        configured_values = self.permissions.get(key)
        if not isinstance(configured_values, list):
            return set(default)

        values = {value for value in configured_values if isinstance(value, str)}
        return values or set(default)
