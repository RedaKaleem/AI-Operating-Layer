"""Linux-specific executor."""

import shutil
import subprocess

from auraos.brain.models import ActionPlan, ExecutionResult
from auraos.executors.base_executor import BasePlatformExecutor


class LinuxExecutor(BasePlatformExecutor):
    """Linux executor."""

    platform_name = "Linux"

    def execute(self, plan: ActionPlan) -> ExecutionResult:
        if plan.action == "real_open_app":
            app_name = plan.args.get("app_name", "").strip()
            if not app_name:
                return ExecutionResult(False, "Tell me which Linux app to open.")

            launcher = shutil.which("gtk-launch")
            if launcher is not None:
                try:
                    subprocess.Popen([launcher, app_name])
                except OSError as error:
                    return ExecutionResult(False, f"Could not open '{app_name}' on Linux: {error}")

                return ExecutionResult(True, f"Opened Linux app '{app_name}'.")

            executable = shutil.which(app_name)
            if executable is None:
                return ExecutionResult(False, f"Could not find Linux app '{app_name}'.")

            try:
                subprocess.Popen([executable])
            except OSError as error:
                return ExecutionResult(False, f"Could not open '{app_name}' on Linux: {error}")

            return ExecutionResult(True, f"Opened Linux app '{app_name}'.")

        if plan.action == "real_open_file":
            file_query = plan.args.get("file_query", "").strip()
            file_path = self.resolve_user_file(file_query)
            if file_path is None:
                return ExecutionResult(False, f"Could not find file matching '{file_query}'.")

            opener = shutil.which("xdg-open")
            if opener is None:
                return ExecutionResult(False, "Could not find xdg-open to open the file.")

            try:
                subprocess.Popen([opener, str(file_path)])
            except OSError as error:
                return ExecutionResult(False, f"Could not open file '{file_path}': {error}")

            return ExecutionResult(True, f"Opened file '{file_path.name}'.")

        if plan.action == "real_recent_download":
            latest_download = self.latest_download()
            if latest_download is None:
                return ExecutionResult(False, "Could not find a recent download.")

            if plan.args.get("open", "false") == "true":
                opener = shutil.which("xdg-open")
                if opener is None:
                    return ExecutionResult(False, "Could not find xdg-open to open the recent download.")

                try:
                    subprocess.Popen([opener, str(latest_download)])
                except OSError as error:
                    return ExecutionResult(False, f"Could not open recent download '{latest_download}': {error}")

                return ExecutionResult(True, f"Opened recent download '{self.describe_file_time(latest_download)}'.")

            return ExecutionResult(True, f"Most recent download: {self.describe_file_time(latest_download)}.")

        if plan.action == "real_search":
            query = plan.args.get("query", "").strip()
            if not query:
                return ExecutionResult(False, "Tell me what to search for.")

            return self.open_browser_search(query)

        return self.unsupported(plan.action)
