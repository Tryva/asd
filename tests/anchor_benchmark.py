"""Small test helper for trusted progress-key examples."""

from typing import Any

from stagnation_detector.events import TrajectoryEvent
from stagnation_detector.normalize import fingerprint


def developer_progress_key(event: TrajectoryEvent) -> Any:
    """Prefer explicit verified anchors and never trust volatile IDs."""
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    for key in (
        "checkpoint_id",
        "state_version",
        "artifact_id",
        "artifact_hash",
        "resource_id",
        "developer_checkpoint",
        "progress_key",
    ):
        if metadata.get(key) is not None:
            return metadata[key]
    if event.state_after is not None and not isinstance(event.state_after, str):
        return event.state_after
    if metadata.get("tool_result_verified") is True and event.tool_result is not None:
        return fingerprint(event.tool_result)
    return None
