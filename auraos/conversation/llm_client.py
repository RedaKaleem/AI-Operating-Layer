"""LLM client for AuraOS conversation mode."""

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from auraos.conversation.prompts import CONVERSATION_SYSTEM_PROMPT


OLLAMA_PROVIDER = "ollama"
OPENAI_PROVIDER = "openai"
DEFAULT_PROVIDER = OLLAMA_PROVIDER
DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MAX_INPUT_CHARS = 6000
DEFAULT_MAX_OUTPUT_TOKENS = 450
MAX_ERROR_DETAIL_CHARS = 240
PLACEHOLDER_API_KEYS = {
    "",
    "replace_with_your_api_key",
    "your_api_key_here",
    "your_new_key_here",
}

SENSITIVE_INPUT_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


class LLMClientError(RuntimeError):
    """Raised when the LLM client cannot return a response."""


class LLMInputRejected(LLMClientError):
    """Raised when user input should not be sent to a remote LLM."""


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for the conversation LLM."""

    provider: str
    model: str
    base_url: str
    api_key: str = ""
    timeout_seconds: float = 30.0
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS


class LLMClient:
    """Small OpenAI-compatible Responses API client using the standard library."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        load_local_env()
        self.config = config or self.from_environment()
        self._validate_config()

    @staticmethod
    def from_environment() -> LLMConfig:
        load_local_env()
        provider = os.getenv("AURAOS_LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
        if provider == OLLAMA_PROVIDER:
            return LLMConfig(
                provider=OLLAMA_PROVIDER,
                model=os.getenv("AURAOS_OLLAMA_MODEL", os.getenv("AURAOS_LLM_MODEL", DEFAULT_OLLAMA_MODEL)),
                base_url=os.getenv("AURAOS_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/"),
                max_input_chars=_read_int_env("AURAOS_LLM_MAX_INPUT_CHARS", DEFAULT_MAX_INPUT_CHARS),
                max_output_tokens=_read_int_env("AURAOS_LLM_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS),
            )

        if provider != OPENAI_PROVIDER:
            raise LLMClientError(f"Unsupported LLM provider '{provider}'.")

        api_key = os.getenv("AURAOS_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not _has_real_api_key(api_key):
            raise LLMClientError("No OpenAI API key configured.")

        base_url = os.getenv("AURAOS_OPENAI_BASE_URL", os.getenv("AURAOS_LLM_BASE_URL", DEFAULT_OPENAI_BASE_URL)).rstrip("/")
        return LLMConfig(
            provider=OPENAI_PROVIDER,
            model=os.getenv("AURAOS_OPENAI_MODEL", os.getenv("AURAOS_LLM_MODEL", DEFAULT_OPENAI_MODEL)),
            base_url=base_url,
            api_key=api_key,
            max_input_chars=_read_int_env("AURAOS_LLM_MAX_INPUT_CHARS", DEFAULT_MAX_INPUT_CHARS),
            max_output_tokens=_read_int_env("AURAOS_LLM_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS),
        )

    @staticmethod
    def is_configured() -> bool:
        load_local_env()
        provider = os.getenv("AURAOS_LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
        if provider == OLLAMA_PROVIDER:
            return True
        if provider == OPENAI_PROVIDER:
            return _has_real_api_key(os.getenv("AURAOS_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))
        return False

    def respond(self, user_message: str) -> str:
        safe_user_message = self._validate_user_message(user_message)
        if self.config.provider == OLLAMA_PROVIDER:
            return self._respond_with_ollama(safe_user_message)

        if self.config.provider == OPENAI_PROVIDER:
            return self._respond_with_openai(safe_user_message)

        raise LLMClientError(f"Unsupported LLM provider '{self.config.provider}'.")

    def _respond_with_ollama(self, user_message: str) -> str:
        payload = {
            "model": self.config.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": CONVERSATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "options": {
                "num_predict": self.config.max_output_tokens,
            },
        }
        response_payload = self._post_json(
            f"{self.config.base_url}/api/chat",
            payload,
            headers={"Content-Type": "application/json"},
        )

        message = response_payload.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

        response_text = response_payload.get("response")
        if isinstance(response_text, str) and response_text.strip():
            return response_text.strip()

        raise LLMClientError("Ollama response did not contain text.")

    def _respond_with_openai(self, user_message: str) -> str:
        payload = {
            "model": self.config.model,
            "instructions": CONVERSATION_SYSTEM_PROMPT,
            "input": user_message,
            "max_output_tokens": self.config.max_output_tokens,
        }
        response_payload = self._post_json(
            f"{self.config.base_url}/responses",
            payload,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            use_ssl_context=True,
        )

        output_text = response_payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        extracted_text = self._extract_output_text(response_payload)
        if extracted_text:
            return extracted_text

        raise LLMClientError("OpenAI response did not contain text.")

    def _post_json(
        self,
        url: str,
        payload: dict,
        headers: dict[str, str],
        use_ssl_context: bool = False,
    ) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            if use_ssl_context:
                response = urllib.request.urlopen(
                    request,
                    timeout=self.config.timeout_seconds,
                    context=_create_ssl_context(),
                )
            else:
                response = urllib.request.urlopen(request, timeout=self.config.timeout_seconds)

            with response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise LLMClientError(_format_http_error(error)) from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise LLMClientError(f"LLM request failed: {error}") from error

    def _extract_output_text(self, payload: dict) -> str:
        parts = []
        output = payload.get("output", [])
        if not isinstance(output, list):
            return ""

        for item in output:
            if not isinstance(item, dict):
                continue

            content = item.get("content", [])
            if not isinstance(content, list):
                continue

            for content_item in content:
                if not isinstance(content_item, dict):
                    continue

                text = content_item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())

        return "\n".join(parts).strip()

    def _validate_config(self) -> None:
        if self.config.provider == OLLAMA_PROVIDER:
            if self.config.base_url != DEFAULT_OLLAMA_BASE_URL and os.getenv("AURAOS_ALLOW_CUSTOM_LLM_BASE_URL") != "true":
                raise LLMClientError("Custom Ollama base URL is disabled.")

            if not self.config.base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
                raise LLMClientError("Ollama base URL must point to localhost.")
            return

        if self.config.provider == OPENAI_PROVIDER:
            if self.config.base_url != DEFAULT_OPENAI_BASE_URL and os.getenv("AURAOS_ALLOW_CUSTOM_LLM_BASE_URL") != "true":
                raise LLMClientError("Custom OpenAI base URL is disabled.")

            if not self.config.base_url.startswith("https://"):
                raise LLMClientError("OpenAI base URL must use HTTPS.")
            return

        raise LLMClientError(f"Unsupported LLM provider '{self.config.provider}'.")

    def _validate_user_message(self, user_message: str) -> str:
        cleaned_message = user_message.strip()
        if not cleaned_message:
            raise LLMInputRejected("Empty message.")

        if len(cleaned_message) > self.config.max_input_chars:
            raise LLMInputRejected(
                f"Message is too long for conversation mode. Limit: {self.config.max_input_chars} characters."
            )

        for pattern in SENSITIVE_INPUT_PATTERNS:
            if pattern.search(cleaned_message):
                raise LLMInputRejected("Message looks like it contains a secret or credential.")

        return cleaned_message


def load_local_env() -> None:
    """Load simple KEY=value pairs from the project .env file."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        os.environ[key] = _clean_env_value(value)


def _clean_env_value(value: str) -> str:
    cleaned_value = value.strip()
    if (
        len(cleaned_value) >= 2
        and cleaned_value[0] == cleaned_value[-1]
        and cleaned_value[0] in {"'", '"'}
    ):
        return cleaned_value[1:-1]
    return cleaned_value


def _read_int_env(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default

    try:
        parsed_value = int(value)
    except ValueError:
        return default

    return parsed_value if parsed_value > 0 else default


def _has_real_api_key(api_key: str | None) -> bool:
    if api_key is None:
        return False

    return api_key.strip() not in PLACEHOLDER_API_KEYS


def _create_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()

    return ssl.create_default_context(cafile=certifi.where())


def _format_http_error(error: urllib.error.HTTPError) -> str:
    detail = _read_http_error_detail(error)
    if detail:
        return f"LLM request failed: HTTP {error.code}: {detail}"
    return f"LLM request failed: HTTP {error.code}"


def _read_http_error_detail(error: urllib.error.HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", errors="replace")
    except Exception:
        return ""

    if not body:
        return ""

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body[:MAX_ERROR_DETAIL_CHARS]

    api_error = payload.get("error")
    if not isinstance(api_error, dict):
        return body[:MAX_ERROR_DETAIL_CHARS]

    parts = []
    for key in ("code", "type", "message"):
        value = api_error.get(key)
        if isinstance(value, str) and value:
            parts.append(value)

    return " | ".join(parts)[:MAX_ERROR_DETAIL_CHARS]
