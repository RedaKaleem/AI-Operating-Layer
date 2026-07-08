"""Route detected commands to the right executor."""

from auraos.brain.models import ActionPlan, ExecutionResult
from auraos.executors.app_executor import AppExecutor
from auraos.executors.browser_executor import BrowserExecutor
from auraos.executors.system_executor import SystemExecutor
from auraos.memory.intent_patterns import IntentPatternMemory


class CommandRouter:
    """Send an approved plan to the matching executor."""

    def __init__(self, pattern_memory: IntentPatternMemory | None = None) -> None:
        self.pattern_memory = pattern_memory or IntentPatternMemory()
        self.executors = {
            "app": AppExecutor(),
            "browser": BrowserExecutor(),
            "system": SystemExecutor(self.pattern_memory),
        }

    def route(self, plan: ActionPlan) -> ExecutionResult:
        executor = self.executors.get(plan.executor)

        if executor is None:
            return ExecutionResult(False, f"No executor found for '{plan.executor}'.")

        return executor.execute(plan)
