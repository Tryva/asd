"""Minimal, deterministic agent trajectory stagnation detector."""

from .detector import Detection, DetectorConfig, StagnationDetector, detect_stagnation
from .events import EventValidationError, TrajectoryEvent

__all__ = [
    "Detection",
    "DetectorConfig",
    "EventValidationError",
    "StagnationDetector",
    "TrajectoryEvent",
    "detect_stagnation",
]
