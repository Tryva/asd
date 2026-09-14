"""Deterministic canonicalization and signal extraction helpers."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from .events import TrajectoryEvent


_VOLATILE_KEYS = {"timestamp", "trace_id", "request_id", "attempt_id", "run_id"}


def canonicalize(value: Any) -> Any:
    """Return a JSON-safe, sorted representation without erasing missing data."""

    if value is None:
        return None
    if isinstance(value, dict):
        return {
            str(key): canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in _VOLATILE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def canonical_json(value: Any) -> str:
    return json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:16]


def state_fingerprint(event: TrajectoryEvent) -> str | None:
    if event.state_after is not None:
        return fingerprint(event.state_after)
    if event.state_before is not None:
        return fingerprint(event.state_before)
    return None


def action_fingerprint(event: TrajectoryEvent) -> str | None:
    if event.tool_name is None and event.event_type is None:
        return None
    return fingerprint({"event_type": event.event_type, "tool_name": event.tool_name, "tool_args": event.tool_args})


def observation_fingerprint(event: TrajectoryEvent) -> str | None:
    if action_fingerprint(event) is None:
        return None
    return fingerprint(
        {
            "action": action_fingerprint(event),
            "result": event.tool_result,
            "error_type": event.error_type,
            "error_message": event.error_message,
            "state": state_fingerprint(event),
            "artifacts": event.artifacts_created,
        }
    )


def error_family(event: TrajectoryEvent) -> str | None:
    if event.error_type is None and event.error_message is None:
        return None
    raw = f"{event.error_type or ''} {event.error_message or ''}".lower()
    if re.search(r"\b(400|401|403|404)\b|invalid|bad request|unauthor", raw):
        return "permanent_client_error"
    if re.search(r"\b(408|429|5\d\d)\b|timeout|temporar|rate.?limit|unavailable|connection", raw):
        return "transient_transport_error"
    if re.search(r"parse|parser|json|schema|validation|decode", raw):
        return "protocol_or_validation_error"
    return str(event.error_type or "unknown_error").lower()


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, bytes, list, tuple, set, dict)):
        return len(value) > 0
    return bool(value)


def numeric_progress(previous: Any, current: Any) -> bool:
    return isinstance(previous, (int, float)) and isinstance(current, (int, float)) and current > previous


def metadata_flag(event: TrajectoryEvent, key: str) -> bool:
    return isinstance(event.metadata, dict) and event.metadata.get(key) is True


def last_consecutive(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    for value in reversed(list(values)):
        if value is None:
            break
        result.append(value)
    return list(reversed(result))
