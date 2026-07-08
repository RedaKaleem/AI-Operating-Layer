"""macOS-specific executor."""

from pathlib import Path
import subprocess

from auraos.brain.models import ActionPlan, ExecutionResult
from auraos.executors.base_executor import BasePlatformExecutor


class MacOSExecutor(BasePlatformExecutor):
    """macOS executor."""

    platform_name = "macOS"

    def execute(self, plan: ActionPlan) -> ExecutionResult:
        if plan.action == "real_open_app":
            app_name = plan.args.get("app_name", "").strip()
            if not app_name:
                return ExecutionResult(False, "Tell me which macOS app to open.")

            app_path = self._resolve_app(app_name)
            opened_name = app_path.stem if app_path is not None else app_name
            result = self._run_open_command(["open", "-a", opened_name])
            if result is not None and app_path is not None:
                result = self._run_open_command(["open", str(app_path)])

            if result is not None:
                return ExecutionResult(False, f"Could not open '{app_name}' on macOS: {result}")

            return ExecutionResult(True, f"Opened macOS app '{opened_name}'.")

        if plan.action == "real_open_file":
            file_query = plan.args.get("file_query", "").strip()
            file_path = self.resolve_user_file(file_query)
            if file_path is None:
                return ExecutionResult(False, f"Could not find file matching '{file_query}'.")

            result = self._run_open_command(["open", str(file_path)])
            if result is not None:
                return ExecutionResult(False, f"Could not open file '{file_path}': {result}")

            return ExecutionResult(True, f"Opened file '{file_path.name}'.")

        if plan.action == "real_recent_download":
            latest_download = self.latest_download()
            if latest_download is None:
                return ExecutionResult(False, "Could not find a recent download.")

            if plan.args.get("open", "false") == "true":
                result = self._run_open_command(["open", str(latest_download)])
                if result is not None:
                    return ExecutionResult(False, f"Could not open recent download '{latest_download}': {result}")

                return ExecutionResult(True, f"Opened recent download '{self.describe_file_time(latest_download)}'.")

            return ExecutionResult(True, f"Most recent download: {self.describe_file_time(latest_download)}.")

        if plan.action == "real_search":
            query = plan.args.get("query", "").strip()
            if not query:
                return ExecutionResult(False, "Tell me what to search for.")

            return self.open_browser_search(query)

        return self.unsupported(plan.action)

    def _run_open_command(self, command: list[str]) -> str | None:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as error:
            return str(error)

        if completed.returncode == 0:
            return None

        error_text = completed.stderr.strip() or completed.stdout.strip()
        return error_text or f"open exited with code {completed.returncode}"

    def _resolve_app(self, app_name: str) -> Path | None:
        normalized_name = app_name.lower().replace(" ", "")
        app_roots = [
            Path("/Applications"),
            Path.home() / "Applications",
            Path("/System/Applications"),
            Path("/System/Applications/Utilities"),
        ]

        for root in app_roots:
            if not root.exists():
                continue

            matches = []
            try:
                for app_path in root.rglob("*.app"):
                    candidate = app_path.stem.lower().replace(" ", "")
                    if candidate == normalized_name:
                        return app_path

                    if normalized_name in candidate:
                        matches.append(app_path)
            except (OSError, PermissionError):
                continue

            if matches:
                return sorted(matches, key=lambda path: len(path.stem))[0]

        return None
