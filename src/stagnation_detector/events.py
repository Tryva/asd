"""Framework-neutral trajectory event model."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, Mapping


class EventValidationError(ValueError):
    """Raised when an event cannot be safely normalized."""


@dataclass(frozen=True)
class TrajectoryEvent:
    """A deliberately permissive event envelope.

    Only ``event_type`` is required. Missing evidence is represented as ``None``
    and is never silently converted to zero or an empty progress signal.
    """

    event_type: str
    timestamp: Any = None
    step_id: Any = None
    tool_name: Any = None
    tool_args: Any = None
    tool_result: Any = None
    error_type: Any = None
    error_message: Any = None
    state_before: Any = None
    state_after: Any = None
    artifacts_created: Any = None
    subtasks_completed: Any = None
    constraints_resolved: Any = None
    token_delta: Any = None
    cost_delta: Any = None
    context_size: Any = None
    metadata: Any = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TrajectoryEvent":
        if not isinstance(value, Mapping):
            raise EventValidationError("event must be a mapping")
        event_type = value.get("event_type")
        if not isinstance(event_type, str) or not event_type.strip():
            raise EventValidationError("event_type must be a non-empty string")
        numeric_fields = ("timestamp", "token_delta", "cost_delta", "context_size")
        for field_name in numeric_fields:
            field_value = value.get(field_name)
            if field_value is not None and not isinstance(field_value, Real):
                raise EventValidationError(f"{field_name} must be numeric when present")
        metadata = value.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise EventValidationError("metadata must be a mapping when present")
        fields = {
            field_name: value.get(field_name)
            for field_name in (
                "event_type",
                "timestamp",
                "step_id",
                "tool_name",
                "tool_args",
                "tool_result",
                "error_type",
                "error_message",
                "state_before",
                "state_after",
                "artifacts_created",
                "subtasks_completed",
                "constraints_resolved",
                "token_delta",
                "cost_delta",
                "context_size",
                "metadata",
            )
        }
        return cls(**fields)

    def to_mapping(self) -> dict[str, Any]:
        return {
            field_name: getattr(self, field_name)
            for field_name in self.__dataclass_fields__
            if getattr(self, field_name) is not None
        }
