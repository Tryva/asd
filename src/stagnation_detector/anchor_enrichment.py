"""Optional, policy-free anchor enrichment for ICM 10.

The functions here only acquire or validate evidence.  They never decide
whether a trajectory is stagnating.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from .adapters import adapter_for
from .events import TrajectoryEvent
from .normalize import fingerprint


NATIVE_ANCHOR_KEYS = (
    "state_version",
    "checkpoint_id",
    "artifact_id",
    "artifact_hash",
    "resource_id",
    "external_state_fingerprint",
    "completed_step_count",
    "tool_result_fingerprint",
)
REJECTED_ID_KEYS = {"run_id", "trace_id", "span_id", "message_id", "timestamp", "attempt_id"}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _native_anchor(raw: Mapping[str, Any]) -> tuple[str, Any] | None:
    sources = (_mapping(raw), _mapping(raw.get("metadata")), _mapping(raw.get("data")))
    for source in sources:
        for key in NATIVE_ANCHOR_KEYS:
            if source.get(key) is not None:
                return key, source[key]
    return None


def convert_events(trace: Mapping[str, Any], adapter_enriched: bool = False) -> list[TrajectoryEvent]:
    """Convert raw events; optionally copy only recognized native anchors."""
    adapter = adapter_for(str(trace["adapter"]))
    converted: list[TrajectoryEvent] = []
    for raw in trace["raw_events"]:
        event = adapter.convert(raw)
        if adapter_enriched:
            anchor = _native_anchor(raw)
            if anchor is not None:
                metadata = dict(event.metadata) if isinstance(event.metadata, Mapping) else {}
                metadata[anchor[0]] = anchor[1]
                metadata["anchor_source"] = "adapter-native"
                event = TrajectoryEvent.from_mapping({**event.to_mapping(), "metadata": metadata})
        converted.append(event)
    return converted


def apply_progress_key(
    events: Iterable[TrajectoryEvent],
    progress_key: Callable[[TrajectoryEvent], Any],
) -> tuple[list[TrajectoryEvent], list[str]]:
    """Apply a developer key as a fingerprint and return deterministic warnings."""
    values: list[str | None] = []
    warnings: list[str] = []
    enriched: list[TrajectoryEvent] = []
    for event in events:
        try:
            first = progress_key(event)
            second = progress_key(event)
        except Exception as exc:  # validation must degrade, never silently trust
            warnings.append(f"PROGRESS_KEY_ERROR:{type(exc).__name__}")
            values.append(None)
            enriched.append(event)
            continue
        first_fp = fingerprint(first)
        second_fp = fingerprint(second)
        if first_fp != second_fp:
            warnings.append("UNSTABLE_PROGRESS_KEY")
            values.append(None)
            enriched.append(event)
            continue
        values.append(first_fp)
        metadata = dict(event.metadata) if isinstance(event.metadata, Mapping) else {}
        if first_fp is not None:
            metadata["custom_user_key"] = first_fp
        enriched.append(TrajectoryEvent.from_mapping({**event.to_mapping(), "metadata": metadata}))
    if any(value is None for value in values):
        warnings.append("MISSING_PROGRESS_KEY")
    present = [value for value in values if value is not None]
    if present and len(set(present)) == 1:
        warnings.append("CONSTANT_PROGRESS_KEY")
    if len(present) >= 4 and len(set(present)) == len(present):
        warnings.append("ALWAYS_CHANGING_PROGRESS_KEY")
    return enriched, sorted(set(warnings))


def mode_events(
    trace: Mapping[str, Any],
    mode: str,
    progress_key: Callable[[TrajectoryEvent], Any] | None = None,
) -> tuple[list[TrajectoryEvent], list[str]]:
    """Build one of the four predeclared ICM 10 modes."""
    if mode not in {"TWO_ANCHOR_NO_ENRICHMENT", "TWO_ANCHOR_ADAPTER_ENRICHED", "TWO_ANCHOR_USER_PROGRESS_KEY", "TWO_ANCHOR_ADAPTER_PLUS_USER_KEY"}:
        raise ValueError(f"unknown mode: {mode}")
    enriched = mode in {"TWO_ANCHOR_ADAPTER_ENRICHED", "TWO_ANCHOR_ADAPTER_PLUS_USER_KEY"}
    events = convert_events(trace, adapter_enriched=enriched)
    if mode in {"TWO_ANCHOR_USER_PROGRESS_KEY", "TWO_ANCHOR_ADAPTER_PLUS_USER_KEY"}:
        if progress_key is None:
            raise ValueError("user progress mode requires progress_key")
        return apply_progress_key(events, progress_key)
    return events, []
