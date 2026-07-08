"""Execute system-level actions."""

from auraos.brain.models import ActionPlan, ExecutionResult
from auraos.conversation.conversation_brain import ConversationBrain
from auraos.memory.execution_history import ExecutionHistory
from auraos.memory.intent_patterns import IntentPatternMemory


class SystemExecutor:
    """Handle internal system actions."""

    def __init__(self, pattern_memory: IntentPatternMemory | None = None) -> None:
        self.pattern_memory = pattern_memory or IntentPatternMemory()
        self.execution_history = ExecutionHistory()
        self.conversation_brain = ConversationBrain()

    def execute(self, plan: ActionPlan) -> ExecutionResult:
        if plan.action == "noop":
            return ExecutionResult(False, "Please enter a command.")

        if plan.action == "exit":
            return ExecutionResult(True, "Shutting down AuraOS core.", should_exit=True)

        if plan.action == "help":
            return ExecutionResult(
                True,
                "Try: 'open notes', 'search Python dataclasses', 'explain this code', 'debug this error', 'plan my next steps', 'history', or 'exit'.",
            )

        if plan.action in {"confirm", "cancel"}:
            return ExecutionResult(False, f"Nothing to {plan.action}.")

        if plan.action == "execution_history":
            return self._execution_history()

        if plan.action == "conversation_response":
            response = self.conversation_brain.respond(plan.command)
            return ExecutionResult(True, response.message)

        if plan.action == "learn_intent_pattern":
            return self._learn_intent_pattern(plan)

        if plan.action == "list_learned_intents":
            return self._list_learned_intents()

        if plan.action == "unknown":
            return ExecutionResult(False, "I do not understand that command yet.")

        return ExecutionResult(False, f"System executor cannot handle '{plan.action}'.")

    def _execution_history(self) -> ExecutionResult:
        entries = self.execution_history.recent(5)
        if not entries:
            return ExecutionResult(True, "No execution history yet.")

        summary = []
        for entry in entries:
            status = "ok" if entry.get("success") else "failed"
            summary.append(f"{entry.get('action')} ({status}): {entry.get('feedback')}")

        return ExecutionResult(True, "Recent executions: " + " | ".join(summary))

    def _learn_intent_pattern(self, plan: ActionPlan) -> ExecutionResult:
        kind = plan.args.get("kind", "")
        pattern = plan.args.get("pattern", "")

        try:
            learned_pattern = self.pattern_memory.add(kind, pattern)
        except ValueError as error:
            return ExecutionResult(False, str(error))

        return ExecutionResult(
            True,
            f"Learned {learned_pattern.kind} phrase: '{learned_pattern.pattern}'.",
        )

    def _list_learned_intents(self) -> ExecutionResult:
        patterns = self.pattern_memory.load()
        if not patterns:
            return ExecutionResult(True, "No learned intent patterns yet.")

        pattern_list = ", ".join(f"{pattern.kind}: '{pattern.pattern}'" for pattern in patterns)
        return ExecutionResult(True, f"Learned intent patterns: {pattern_list}.")
