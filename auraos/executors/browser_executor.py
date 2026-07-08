"""Execute browser actions."""

from auraos.brain.models import ActionPlan, ExecutionResult
from auraos.executors.executor_factory import ExecutorFactory


class BrowserExecutor:
    """Browser executor that delegates to the current OS."""

    def __init__(self) -> None:
        self.platform_executor = ExecutorFactory.create_platform_executor()

    def execute(self, plan: ActionPlan) -> ExecutionResult:
        return self.platform_executor.execute(plan)
