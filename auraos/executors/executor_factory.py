"""Factory for selecting platform-specific executors."""

import platform

from auraos.executors.base_executor import BasePlatformExecutor
from auraos.executors.linux_executor import LinuxExecutor
from auraos.executors.macos_executor import MacOSExecutor
from auraos.executors.windows_executor import WindowsExecutor


class ExecutorFactory:
    """Create the executor that matches the current operating system."""

    @staticmethod
    def current_platform_name() -> str:
        return platform.system().lower()

    @classmethod
    def create_platform_executor(cls) -> BasePlatformExecutor:
        platform_name = cls.current_platform_name()

        if platform_name == "darwin":
            return MacOSExecutor()

        if platform_name == "windows":
            return WindowsExecutor()

        if platform_name == "linux":
            return LinuxExecutor()

        return LinuxExecutor()
