"""AuraOS entry point."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from auraos.brain.command_router import CommandRouter
from auraos.brain.intent_detector import IntentDetector
from auraos.brain.models import ActionPlan, ExecutionResult
from auraos.brain.planner import Planner
from auraos.brain.safety import SafetyChecker
from auraos.memory.command_logs import CommandLogger
from auraos.memory.execution_history import ExecutionHistory
from auraos.memory.intent_patterns import IntentPatternMemory


class AuraOSCore:
    """Core command processing pipeline."""

    def __init__(self) -> None:
        self.pattern_memory = IntentPatternMemory()
        self.intent_detector = IntentDetector(self.pattern_memory)
        self.planner = Planner()
        self.safety_checker = SafetyChecker()
        self.router = CommandRouter(self.pattern_memory)
        self.logger = CommandLogger()
        self.execution_history = ExecutionHistory()
        self.pending_plan: ActionPlan | None = None

    def process_command(self, command: str) -> ExecutionResult:
        intent = self.intent_detector.detect(command)
        plan = self.planner.create_plan(intent)

        if plan.action == "confirm":
            result = self._confirm_pending_action()
            self._log_command(command, intent.kind, plan.action, True, result)
            return result

        if plan.action == "cancel":
            result = self._cancel_pending_action()
            self._log_command(command, intent.kind, plan.action, True, result)
            return result

        safety_result = self.safety_checker.check(plan)

        if safety_result.requires_confirmation:
            self.pending_plan = plan
            result = ExecutionResult(False, self._confirmation_message(plan, safety_result.reason))
        elif safety_result.allowed:
            result = self.router.route(plan)
            self._record_execution(plan, confirmed=False, result=result)
        else:
            result = ExecutionResult(False, safety_result.reason)

        self._log_command(command, intent.kind, plan.action, safety_result.allowed, result)
        return result

    def _confirm_pending_action(self) -> ExecutionResult:
        if self.pending_plan is None:
            return ExecutionResult(False, "No pending action to confirm.")

        plan = self.pending_plan
        self.pending_plan = None
        result = self.router.route(plan)
        self._record_execution(plan, confirmed=True, result=result)
        return result

    def _cancel_pending_action(self) -> ExecutionResult:
        if self.pending_plan is None:
            return ExecutionResult(False, "No pending action to cancel.")

        action = self.pending_plan.action
        self.pending_plan = None
        return ExecutionResult(True, f"Cancelled pending action '{action}'.")

    def _confirmation_message(self, plan: ActionPlan, reason: str) -> str:
        target = plan.args.get("app_name") or plan.args.get("query") or plan.command
        return f"{reason} Pending target: '{target}'."

    def _record_execution(self, plan: ActionPlan, confirmed: bool, result: ExecutionResult) -> None:
        if not plan.action.startswith("real_"):
            return

        self.execution_history.record(
            command=plan.command,
            action=plan.action,
            executor=plan.executor,
            confirmed=confirmed,
            success=result.success,
            feedback=result.message,
        )

    def _log_command(
        self,
        command: str,
        intent_kind: str,
        action: str,
        allowed: bool,
        result: ExecutionResult,
    ) -> None:
        self.logger.log(
            command=command,
            intent_kind=intent_kind,
            action=action,
            allowed=allowed,
            success=result.success,
            feedback=result.message,
        )


def main() -> None:
    """Start the AuraOS text command loop."""
    core = AuraOSCore()
    print("AuraOS core is running. Type 'help' or 'exit'.")

    while True:
        try:
            command = input("AuraOS> ")
        except EOFError:
            print("Shutting down AuraOS core.")
            break

        result = core.process_command(command)
        print(result.message)

        if result.should_exit:
            break


if __name__ == "__main__":
    main()
