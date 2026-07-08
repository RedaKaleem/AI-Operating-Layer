"""Base classes for platform-specific AuraOS executors."""

from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote_plus
from datetime import datetime
import webbrowser

from auraos.brain.models import ActionPlan, ExecutionResult


class BasePlatformExecutor(ABC):
    """Common contract for operating-system executors."""

    platform_name = "generic"

    @abstractmethod
    def execute(self, plan: ActionPlan) -> ExecutionResult:
        """Execute or preview a platform-specific action."""

    def open_browser_search(self, query: str) -> ExecutionResult:
        search_url = f"https://www.google.com/search?q={quote_plus(query)}"
        opened = webbrowser.open(search_url)
        if opened:
            return ExecutionResult(True, f"Opened browser search for '{query}'.")

        return ExecutionResult(False, "Could not open the browser.")

    def resolve_user_file(self, file_query: str) -> Path | None:
        cleaned_query = file_query.strip().strip("\"'")
        if not cleaned_query:
            return None

        expanded_path = Path(cleaned_query).expanduser()
        if expanded_path.exists():
            return expanded_path

        home = Path.home()
        search_roots = [
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
            home,
        ]
        normalized_query = cleaned_query.lower()

        for root in search_roots:
            if not root.exists():
                continue

            match = self._find_file(root, normalized_query)
            if match is not None:
                return match

        return None

    def latest_download(self) -> Path | None:
        downloads = Path.home() / "Downloads"
        if not downloads.exists():
            return None

        candidates = []
        try:
            for path in downloads.iterdir():
                if path.name.startswith("."):
                    continue

                try:
                    candidates.append((path.stat().st_mtime, path))
                except OSError:
                    continue
        except OSError:
            return None

        if not candidates:
            return None

        return max(candidates, key=lambda item: item[0])[1]

    def describe_file_time(self, path: Path) -> str:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        return f"{path.name} ({modified_at})"

    def _find_file(self, root: Path, normalized_query: str) -> Path | None:
        max_depth = 4
        root_depth = len(root.parts)

        try:
            for path in root.rglob("*"):
                if path.name.startswith("."):
                    continue

                depth = len(path.parts) - root_depth
                if depth > max_depth:
                    continue

                if normalized_query in path.name.lower():
                    return path
        except (OSError, PermissionError):
            return None

        return None

    def unsupported(self, action: str) -> ExecutionResult:
        return ExecutionResult(False, f"{self.platform_name} executor cannot handle '{action}'.")
