"""Thin adapters from common trace shapes to the neutral event envelope."""

from __future__ import annotations

from typing import Any, Mapping

from .events import TrajectoryEvent


class GenericJSONAdapter:
    """Adapter for already-normalized JSON event mappings."""

    name = "generic-json"

    def convert(self, raw: Mapping[str, Any]) -> TrajectoryEvent:
        return TrajectoryEvent.from_mapping(raw)


class LangGraphAdapter:
    """Dependency-free adapter for common LangGraph/LangChain stream event shapes.

    It maps event structure only. It contains no stagnation policy.
    """

    name = "langgraph-compat"

    def convert(self, raw: Mapping[str, Any]) -> TrajectoryEvent:
        if not isinstance(raw, Mapping):
            raise ValueError("LangGraph event must be a mapping")
        data = raw.get("data") if isinstance(raw.get("data"), Mapping) else {}
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {}
        event_name = raw.get("event") or raw.get("type") or "unknown"
        event_type = str(event_name)
        tool_name = raw.get("name") or data.get("tool_name") or data.get("name")
        tool_args = data.get("input", data.get("tool_input"))
        tool_result = data.get("output", data.get("tool_output", data.get("result")))
        error = data.get("error")
        error_type = data.get("error_type")
        error_message = data.get("error_message")
        if isinstance(error, Mapping):
            error_type = error_type or error.get("type")
            error_message = error_message or error.get("message")
        elif error is not None:
            error_message = error_message or str(error)
        state_after = data.get("state_after", metadata.get("state_after"))
        state_before = data.get("state_before", metadata.get("state_before"))
        artifacts = data.get("artifacts_created", metadata.get("artifacts_created"))
        subtasks = data.get("subtasks_completed", metadata.get("subtasks_completed"))
        constraints = data.get("constraints_resolved", metadata.get("constraints_resolved"))
        step_id = metadata.get("langgraph_step", raw.get("step", raw.get("step_id")))
        timestamp = raw.get("timestamp", metadata.get("timestamp"))
        passthrough_metadata = dict(metadata)
        passthrough_metadata["adapter"] = self.name
        return TrajectoryEvent.from_mapping(
            {
                "timestamp": timestamp,
                "step_id": step_id,
                "event_type": event_type,
                "tool_name": tool_name,
                "tool_args": tool_args,
                "tool_result": tool_result,
                "error_type": error_type,
                "error_message": error_message,
                "state_before": state_before,
                "state_after": state_after,
                "artifacts_created": artifacts,
                "subtasks_completed": subtasks,
                "constraints_resolved": constraints,
                "token_delta": raw.get("token_delta", metadata.get("token_delta")),
                "cost_delta": raw.get("cost_delta", metadata.get("cost_delta")),
                "context_size": raw.get("context_size", metadata.get("context_size")),
                "metadata": passthrough_metadata,
            }
        )


class _EventShapeAdapter:
    """Small dependency-free adapter for framework event dictionaries."""

    name = "event-shape"

    def convert(self, raw: Mapping[str, Any]) -> TrajectoryEvent:
        if not isinstance(raw, Mapping):
            raise ValueError("framework event must be a mapping")
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {}
        data = raw.get("data") if isinstance(raw.get("data"), Mapping) else {}
        event_type = raw.get("event_type") or raw.get("type") or raw.get("event") or raw.get("kind") or "unknown"
        tool_name = raw.get("tool_name") or raw.get("tool") or raw.get("name") or data.get("tool_name") or data.get("name")
        result = raw.get("tool_result", raw.get("result", raw.get("output")))
        if result is None:
            result = data.get("tool_result", data.get("result", data.get("output")))
        error = raw.get("error") or data.get("error")
        error_type = raw.get("error_type") or data.get("error_type")
        error_message = raw.get("error_message") or data.get("error_message")
        if isinstance(error, Mapping):
            error_type = error_type or error.get("type")
            error_message = error_message or error.get("message")
        elif error is not None:
            error_message = error_message or str(error)
        merged_metadata = dict(metadata)
        merged_metadata["adapter"] = self.name
        return TrajectoryEvent.from_mapping(
            {
                "timestamp": raw.get("timestamp", metadata.get("timestamp")),
                "step_id": raw.get("step_id", raw.get("step", metadata.get("step_id"))),
                "event_type": str(event_type),
                "tool_name": tool_name,
                "tool_args": raw.get("tool_args", raw.get("input", data.get("input"))),
                "tool_result": result,
                "error_type": error_type,
                "error_message": error_message,
                "state_before": raw.get("state_before", data.get("state_before")),
                "state_after": raw.get("state_after", data.get("state_after")),
                "artifacts_created": raw.get("artifacts_created", data.get("artifacts_created")),
                "subtasks_completed": raw.get("subtasks_completed", data.get("subtasks_completed")),
                "constraints_resolved": raw.get("constraints_resolved", data.get("constraints_resolved")),
                "token_delta": raw.get("token_delta", metadata.get("token_delta")),
                "cost_delta": raw.get("cost_delta", metadata.get("cost_delta")),
                "context_size": raw.get("context_size", metadata.get("context_size")),
                "metadata": merged_metadata,
            }
        )


class OpenAIAgentsAdapter(_EventShapeAdapter):
    name = "openai-agents"


class PydanticAIAdapter(_EventShapeAdapter):
    name = "pydantic-ai"


class AutoGenAdapter(_EventShapeAdapter):
    name = "autogen"


class LangChainAdapter(_EventShapeAdapter):
    name = "langchain-compat"


def adapter_for(name: str):
    if name == "generic-json":
        return GenericJSONAdapter()
    if name == "langgraph-compat":
        return LangGraphAdapter()
    if name == "langchain-compat":
        return LangChainAdapter()
    if name == "openai-agents":
        return OpenAIAgentsAdapter()
    if name == "pydantic-ai":
        return PydanticAIAdapter()
    if name == "autogen":
        return AutoGenAdapter()
    raise ValueError(f"unknown adapter: {name}")
