"""Shared data models for the AuraOS brain pipeline."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Intent:
    """A normalized understanding of a user command."""

    command: str
    kind: str
    confidence: float
    entities: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionPlan:
    """A safe, explicit action request for the router."""

    command: str
    intent_kind: str
    executor: str
    action: str
    args: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SafetyResult:
    """Decision from the safety layer."""

    allowed: bool
    reason: str
    requires_confirmation: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    """Result returned by an executor."""

    success: bool
    message: str
    should_exit: bool = False
