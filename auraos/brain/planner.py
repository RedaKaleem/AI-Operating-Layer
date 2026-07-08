"""Plan execution steps for user requests."""

from auraos.brain.models import ActionPlan, Intent


class Planner:
    """Convert detected intent into an execution plan."""

    def create_plan(self, intent: Intent) -> ActionPlan:
        if intent.kind == "empty":
            return ActionPlan(intent.command, intent.kind, "system", "noop")

        if intent.kind == "exit":
            return ActionPlan(intent.command, intent.kind, "system", "exit")

        if intent.kind == "help":
            return ActionPlan(intent.command, intent.kind, "system", "help")

        if intent.kind == "confirm":
            return ActionPlan(intent.command, intent.kind, "system", "confirm")

        if intent.kind == "cancel":
            return ActionPlan(intent.command, intent.kind, "system", "cancel")

        if intent.kind == "execution_history":
            return ActionPlan(intent.command, intent.kind, "system", "execution_history")

        if intent.kind == "learn_intent_pattern":
            return ActionPlan(
                intent.command,
                intent.kind,
                "system",
                "learn_intent_pattern",
                {
                    "kind": intent.entities.get("kind", ""),
                    "pattern": intent.entities.get("pattern", ""),
                },
            )

        if intent.kind == "list_learned_intents":
            return ActionPlan(intent.command, intent.kind, "system", "list_learned_intents")

        if intent.kind == "app":
            return ActionPlan(
                intent.command,
                intent.kind,
                "app",
                "real_open_app",
                {"app_name": intent.entities.get("app_name", "")},
            )

        if intent.kind == "browser":
            return ActionPlan(
                intent.command,
                intent.kind,
                "browser",
                "real_search",
                {"query": intent.entities.get("query", "")},
            )

        if intent.kind == "file":
            return ActionPlan(
                intent.command,
                intent.kind,
                "app",
                "real_open_file",
                {"file_query": intent.entities.get("file_query", "")},
            )

        if intent.kind == "recent_download":
            return ActionPlan(
                intent.command,
                intent.kind,
                "app",
                "real_recent_download",
                {"open": intent.entities.get("open", "false")},
            )

        if intent.kind == "conversation":
            return ActionPlan(
                intent.command,
                intent.kind,
                "system",
                "conversation_response",
                {"topic": intent.entities.get("topic", "")},
            )

        return ActionPlan(intent.command, intent.kind, "system", "unknown")
