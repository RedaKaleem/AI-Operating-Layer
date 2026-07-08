"""Conversation brain for non-action help."""

from dataclasses import dataclass

from auraos.conversation.llm_client import LLMClient, LLMClientError, LLMInputRejected


@dataclass(frozen=True)
class ConversationResponse:
    """A conversational response from AuraOS."""

    message: str


class ConversationBrain:
    """Handle explanation, debugging, advice, planning, and natural chat."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client
        if self.llm_client is None and LLMClient.is_configured():
            try:
                self.llm_client = LLMClient()
            except LLMClientError:
                self.llm_client = None

    def respond(self, command: str) -> ConversationResponse:
        cleaned_command = command.strip()
        lowered_command = cleaned_command.lower()
        api_error_message = ""

        if not cleaned_command:
            return ConversationResponse("I am here. Ask me to explain, debug, plan, or open something.")

        if self.llm_client is not None:
            try:
                return ConversationResponse(self.llm_client.respond(cleaned_command))
            except LLMInputRejected as error:
                return ConversationResponse(
                    f"I blocked that from being sent to the conversation model: {error} "
                    "Remove secrets or shorten the message, then try again."
                )
            except LLMClientError as error:
                api_error_message = f"Conversation model unavailable: {error}. "

        if self._looks_like_code_explanation(lowered_command):
            return ConversationResponse(api_error_message + self._code_explanation_response(cleaned_command))

        if self._looks_like_debug_request(lowered_command):
            return ConversationResponse(api_error_message + self._debug_response(cleaned_command))

        if self._looks_like_plan_request(lowered_command):
            return ConversationResponse(api_error_message + self._plan_response(cleaned_command))

        if self._looks_like_advice_request(lowered_command):
            return ConversationResponse(api_error_message + self._advice_response(cleaned_command))

        if lowered_command in {"hello", "hi", "hey", "hey aura", "aura"}:
            return ConversationResponse(
                api_error_message + "I am listening. I can help with actions, code, debugging, planning, or advice."
            )

        return ConversationResponse(
            api_error_message
            + "I can help with that, but I need a little more detail. "
            "Tell me whether you want an explanation, a debug pass, a plan, or an action."
        )

    def _looks_like_code_explanation(self, command: str) -> bool:
        return any(
            phrase in command
            for phrase in (
                "explain code",
                "explain this code",
                "what does this code do",
                "walk me through",
                "how does this work",
            )
        )

    def _looks_like_debug_request(self, command: str) -> bool:
        return any(
            phrase in command
            for phrase in (
                "debug",
                "fix this error",
                "error",
                "traceback",
                "not working",
                "why is this failing",
            )
        )

    def _looks_like_plan_request(self, command: str) -> bool:
        return any(
            phrase in command
            for phrase in (
                "plan",
                "roadmap",
                "steps",
                "break this down",
                "what should i do next",
            )
        )

    def _looks_like_advice_request(self, command: str) -> bool:
        return any(
            phrase in command
            for phrase in (
                "advice",
                "should i",
                "what do you think",
                "recommend",
                "best way",
            )
        )

    def _code_explanation_response(self, command: str) -> str:
        return (
            "Send me the code or file name you want explained. "
            "I will break it down by purpose, important functions, data flow, and any risky parts."
        )

    def _debug_response(self, command: str) -> str:
        return (
            "Send me the exact error text or traceback. "
            "I will look for the failing line, likely cause, safest fix, and a quick verification step."
        )

    def _plan_response(self, command: str) -> str:
        return (
            "Here is a useful planning shape: define the goal, list constraints, split the work into small milestones, "
            "build the riskiest part first, then verify each step before expanding."
        )

    def _advice_response(self, command: str) -> str:
        return (
            "My advice: choose the smallest next step that gives you real feedback. "
            "For AuraOS, that usually means adding one capability, testing it with logs, then tightening safety."
        )
