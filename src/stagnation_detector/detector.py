"""Small deterministic stagnation policy with an explicit UNKNOWN outcome."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from numbers import Real
from typing import Any, Iterable, Mapping

from .events import TrajectoryEvent
from .normalize import (
    action_fingerprint,
    error_family,
    fingerprint,
    metadata_flag,
    nonempty,
    numeric_progress,
    observation_fingerprint,
    state_fingerprint,
)


STATUSES = ("PROGRESSING", "STAGNATING", "LOOPING", "BUDGET_RISK", "UNKNOWN")
ALL_SIGNALS = frozenset(
    {
        "EXACT_REPEAT",
        "REPEATED_ERROR_FAMILY",
        "NO_STATE_DELTA",
        "NO_NEW_ARTIFACT",
        "NO_SUBTASK_PROGRESS",
        "NO_CONSTRAINT_REDUCTION",
        "CONTEXT_GROWTH_WITHOUT_PROGRESS",
        "BUDGET_RISK",
        "CYCLE_DETECTION",
    }
)


@dataclass(frozen=True)
class DetectorConfig:
    window: int = 4
    exact_repeat_threshold: int = 3
    error_repeat_threshold: int = 3
    cycle_repetitions: int = 2
    budget_risk_ratio: float = 0.8
    max_steps: int | None = 10
    max_tokens: float | None = 500.0
    max_cost: float | None = None
    max_seconds: float | None = None
    enabled_signals: frozenset[str] = field(default_factory=lambda: ALL_SIGNALS)
    retention_window: int = 64
    retain_raw_events: bool = False

    def __post_init__(self) -> None:
        if self.window < 2 or self.exact_repeat_threshold < 2 or self.error_repeat_threshold < 2:
            raise ValueError("window and repeat thresholds must be at least 2")
        if self.retention_window < self.window:
            raise ValueError("retention_window must be at least as large as window")
        if not 0 < self.budget_risk_ratio <= 1:
            raise ValueError("budget_risk_ratio must be in (0, 1]")


@dataclass(frozen=True)
class Detection:
    status: str
    evidence_strength: str
    evidence: tuple[str, ...]
    signals: tuple[str, ...]
    window: tuple[Any, ...]

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"invalid status: {self.status}")
        if self.status != "PROGRESSING" and not self.evidence:
            raise ValueError("non-PROGRESSING decisions require evidence")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "evidence_strength": self.evidence_strength,
            "evidence": list(self.evidence),
            "signals": list(self.signals),
            "window": list(self.window),
        }


class _IncrementalState:
    """Bounded runtime state for online detection.

    The state deliberately stores only the configured recent window plus
    scalar summaries needed by the existing detector rules.  Positive signal
    names are monotonic because the original detector also retained positive
    evidence once observed anywhere in the trace.
    """

    def __init__(self, retention_window: int, detection_window: int) -> None:
        self.recent: deque[TrajectoryEvent] = deque(maxlen=retention_window)
        self.recent_step_ids: deque[Any] = deque(maxlen=detection_window)
        self.recent_observations: deque[str | None] = deque(maxlen=detection_window)
        self.recent_families: deque[str | None] = deque(maxlen=detection_window)
        self.recent_states: deque[str | None] = deque(maxlen=detection_window)
        self.recent_state_after: deque[Any] = deque(maxlen=detection_window)
        self.recent_artifacts: deque[Any] = deque(maxlen=detection_window)
        self.recent_subtasks: deque[Any] = deque(maxlen=detection_window)
        self.recent_constraints: deque[Any] = deque(maxlen=detection_window)
        self.recent_pairs: deque[tuple[str | None, str | None]] = deque(maxlen=detection_window)
        self.recent_contexts: deque[Any] = deque(maxlen=detection_window)
        self.recent_tokens: deque[Any] = deque(maxlen=detection_window)
        self.event_count = 0
        self.positive_signals: set[str] = set()
        self.previous_state: str | None = None
        self.previous_error: str | None = None
        self.previous_subtasks: Any = None
        self.previous_constraints: Any = None
        self.all_tokens_present = True
        self.token_sum = 0.0
        self.all_costs_present = True
        self.cost_sum = 0.0
        self.all_timestamps_present = True
        self.first_timestamp: Real | None = None
        self.last_timestamp: Real | None = None

    def observe(self, event: TrajectoryEvent) -> None:
        self.event_count += 1
        self.recent.append(event)
        self.recent_step_ids.append(event.step_id)
        action = action_fingerprint(event)
        family = error_family(event)
        current_state = state_fingerprint(event)
        observation = (
            None
            if action is None
            else fingerprint(
                {
                    "action": action,
                    "result": event.tool_result,
                    "error_type": event.error_type,
                    "error_message": event.error_message,
                    "state": current_state,
                    "artifacts": event.artifacts_created,
                }
            )
        )
        self.recent_observations.append(observation)
        self.recent_families.append(family)
        self.recent_states.append(current_state)
        self.recent_state_after.append(event.state_after)
        self.recent_artifacts.append(event.artifacts_created)
        self.recent_subtasks.append(event.subtasks_completed)
        self.recent_constraints.append(event.constraints_resolved)
        self.recent_pairs.append((action, current_state))
        self.recent_contexts.append(event.context_size)
        self.recent_tokens.append(event.token_delta)

        before = fingerprint(event.state_before)
        after = fingerprint(event.state_after)
        if before is not None and after is not None and before != after:
            self.positive_signals.add("STATE_TRANSITION")
        if nonempty(event.artifacts_created):
            self.positive_signals.add("NEW_ARTIFACT")
        if nonempty(event.subtasks_completed) or numeric_progress(self.previous_subtasks, event.subtasks_completed):
            self.positive_signals.add("SUBTASK_COMPLETED")
        if nonempty(event.constraints_resolved) or numeric_progress(self.previous_constraints, event.constraints_resolved):
            self.positive_signals.add("CONSTRAINT_RESOLVED")
        if metadata_flag(event, "verified_observation"):
            self.positive_signals.add("NEW_VERIFIED_OBSERVATION")
        if metadata_flag(event, "checkpoint_advanced"):
            self.positive_signals.add("CHECKPOINT_ADVANCED")

        current_error = family
        if self.previous_state is not None and current_state is not None and self.previous_state != current_state:
            self.positive_signals.add("STATE_TRANSITION")
        if self.previous_error is not None and current_error is not None and self.previous_error != current_error:
            self.positive_signals.add("ERROR_CLASS_CHANGED")
        self.previous_state = current_state
        self.previous_error = current_error
        self.previous_subtasks = event.subtasks_completed
        self.previous_constraints = event.constraints_resolved

        if event.token_delta is None:
            self.all_tokens_present = False
        else:
            self.token_sum += event.token_delta
        if event.cost_delta is None:
            self.all_costs_present = False
        else:
            self.cost_sum += event.cost_delta
        if event.timestamp is None:
            self.all_timestamps_present = False
        elif self.event_count == 1:
            self.first_timestamp = event.timestamp
        self.last_timestamp = event.timestamp


class StagnationDetector:
    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()
        self._state = _IncrementalState(self.config.retention_window, self.config.window)
        self._raw_events: list[TrajectoryEvent] | None = [] if self.config.retain_raw_events else None

    def observe(self, event: TrajectoryEvent | Mapping[str, Any]) -> Detection:
        normalized = event if isinstance(event, TrajectoryEvent) else TrajectoryEvent.from_mapping(event)
        self._state.observe(normalized)
        if self._raw_events is not None:
            self._raw_events.append(normalized)
        return self.status()

    def status(self) -> Detection:
        return _detect_incremental(self._state, self.config)

    @property
    def events(self) -> tuple[TrajectoryEvent, ...]:
        if self._raw_events is not None:
            return tuple(self._raw_events)
        return tuple(self._state.recent)


def detect_stagnation(
    events: Iterable[TrajectoryEvent | Mapping[str, Any]], config: DetectorConfig | None = None
) -> Detection:
    detector = StagnationDetector(config)
    for event in events:
        detector.observe(event)
    return detector.status()


def _detect(events: list[TrajectoryEvent], config: DetectorConfig) -> Detection:
    if not events:
        return Detection("UNKNOWN", "INSUFFICIENT", ("no trajectory events observed",), (), ())
    recent = events[-config.window :]
    window_ready = len(recent) >= config.window
    evidence: list[str] = []
    signals: list[str] = []

    def enabled(name: str) -> bool:
        return name in config.enabled_signals

    # Positive evidence is explicit and never inferred from mere activity.
    progress = _positive_signals(events)
    strong_progress = {
        "STATE_TRANSITION",
        "NEW_ARTIFACT",
        "SUBTASK_COMPLETED",
        "CONSTRAINT_RESOLVED",
        "CHECKPOINT_ADVANCED",
    }
    positive_names = sorted(progress)
    if positive_names:
        evidence.extend(f"positive evidence: {name}" for name in positive_names)

    obs = [observation_fingerprint(event) for event in recent]
    if enabled("EXACT_REPEAT") and _repeated_known(obs, config.exact_repeat_threshold):
        signals.append("EXACT_REPEAT")
        evidence.append(f"same normalized observation repeated {config.exact_repeat_threshold} times")

    families = [error_family(event) for event in recent]
    if enabled("REPEATED_ERROR_FAMILY") and _repeated_known(families, config.error_repeat_threshold):
        signals.append("REPEATED_ERROR_FAMILY")
        evidence.append(f"same normalized error family repeated {config.error_repeat_threshold} times")

    states = [state_fingerprint(event) for event in recent]
    state_after_values = [event.state_after for event in recent]
    if enabled("NO_STATE_DELTA") and window_ready and _all_present(state_after_values) and _all_equal_known(states):
        signals.append("NO_STATE_DELTA")
        evidence.append(f"state fingerprint unchanged across {len(recent)} observed steps")

    artifacts = [event.artifacts_created for event in recent]
    if enabled("NO_NEW_ARTIFACT") and window_ready and _all_present(artifacts) and not any(nonempty(item) for item in artifacts):
        signals.append("NO_NEW_ARTIFACT")
        evidence.append(f"no verified artifact/resource created across {len(recent)} observed steps")

    subtasks = [event.subtasks_completed for event in recent]
    if enabled("NO_SUBTASK_PROGRESS") and window_ready and _all_present(subtasks) and not _increasing_or_nonempty(subtasks):
        signals.append("NO_SUBTASK_PROGRESS")
        evidence.append(f"no verified subtask completion across {len(recent)} observed steps")

    constraints = [event.constraints_resolved for event in recent]
    if enabled("NO_CONSTRAINT_REDUCTION") and window_ready and _all_present(constraints) and not _increasing_or_nonempty(constraints):
        signals.append("NO_CONSTRAINT_REDUCTION")
        evidence.append(f"no constraint reduction across {len(recent)} observed steps")

    if enabled("CONTEXT_GROWTH_WITHOUT_PROGRESS") and window_ready and _context_growth(recent) and not progress:
        signals.append("CONTEXT_GROWTH_WITHOUT_PROGRESS")
        evidence.append("context or token usage increased while no positive progress signal was observed")

    if enabled("CYCLE_DETECTION"):
        cycle_length = _repeated_cycle(recent, config.cycle_repetitions)
        if cycle_length is not None:
            signals.append("CYCLE_DETECTION")
            evidence.append(f"normalized action/state cycle repeated with period {cycle_length}")

    if enabled("BUDGET_RISK"):
        budget_evidence = _budget_risk(events, config)
        if budget_evidence:
            signals.append("BUDGET_RISK")
            evidence.extend(budget_evidence)

    negative = set(signals)
    hard_loop = bool({"EXACT_REPEAT", "CYCLE_DETECTION"} & negative)
    stagnation = bool(
        {
            "REPEATED_ERROR_FAMILY",
            "NO_STATE_DELTA",
            "NO_NEW_ARTIFACT",
            "NO_SUBTASK_PROGRESS",
            "NO_CONSTRAINT_REDUCTION",
            "CONTEXT_GROWTH_WITHOUT_PROGRESS",
        }
        & negative
    )
    cyclic_state_changes = hard_loop and set(progress) <= {"STATE_TRANSITION"}
    substantive_stagnation = bool(
        {
            "REPEATED_ERROR_FAMILY",
            "NO_STATE_DELTA",
            "NO_SUBTASK_PROGRESS",
            "NO_CONSTRAINT_REDUCTION",
            "CONTEXT_GROWTH_WITHOUT_PROGRESS",
        }
        & negative
    )
    conflict = bool(negative) and bool(progress) and (hard_loop or substantive_stagnation) and not cyclic_state_changes

    if conflict:
        evidence.append("positive progress evidence conflicts with stagnation/loop signals")
        return Detection("UNKNOWN", "CONFLICTING", tuple(evidence), tuple(sorted(signals)), _window_ids(recent))
    if "BUDGET_RISK" in negative and not progress:
        return Detection("BUDGET_RISK", "DETERMINISTIC", tuple(evidence), tuple(sorted(signals)), _window_ids(recent))
    meaningful_progress = strong_progress - {"STATE_TRANSITION"}
    if hard_loop and not (set(progress) & meaningful_progress):
        return Detection("LOOPING", "DETERMINISTIC", tuple(evidence), tuple(sorted(signals)), _window_ids(recent))
    if stagnation and not progress:
        return Detection("STAGNATING", "DETERMINISTIC", tuple(evidence), tuple(sorted(signals)), _window_ids(recent))
    if progress:
        return Detection("PROGRESSING", "DETERMINISTIC", tuple(evidence), tuple(sorted(signals)), _window_ids(recent))
    if len(events) < config.window:
        evidence.append(f"only {len(events)} events observed; window requires {config.window}")
    else:
        evidence.append("no sufficient positive or negative signal was observable")
    return Detection("UNKNOWN", "INSUFFICIENT", tuple(evidence), tuple(sorted(signals)), _window_ids(recent))


def _detect_incremental(state: _IncrementalState, config: DetectorConfig) -> Detection:
    """Evaluate the frozen rules from bounded recent data and summaries."""
    if state.event_count == 0:
        return Detection("UNKNOWN", "INSUFFICIENT", ("no trajectory events observed",), (), ())
    recent_ids = tuple(state.recent_step_ids)
    observations = list(state.recent_observations)
    families = list(state.recent_families)
    states = list(state.recent_states)
    state_after_values = list(state.recent_state_after)
    artifacts = list(state.recent_artifacts)
    subtasks = list(state.recent_subtasks)
    constraints = list(state.recent_constraints)
    pairs = list(state.recent_pairs)
    contexts = list(state.recent_contexts)
    tokens = list(state.recent_tokens)
    recent_length = len(observations)
    window_ready = recent_length >= config.window
    evidence: list[str] = []
    signals: list[str] = []

    def enabled(name: str) -> bool:
        return name in config.enabled_signals

    progress = state.positive_signals
    strong_progress = {
        "STATE_TRANSITION",
        "NEW_ARTIFACT",
        "SUBTASK_COMPLETED",
        "CONSTRAINT_RESOLVED",
        "CHECKPOINT_ADVANCED",
    }
    positive_names = sorted(progress)
    if positive_names:
        evidence.extend(f"positive evidence: {name}" for name in positive_names)

    if enabled("EXACT_REPEAT") and _repeated_known(observations, config.exact_repeat_threshold):
        signals.append("EXACT_REPEAT")
        evidence.append(f"same normalized observation repeated {config.exact_repeat_threshold} times")

    if enabled("REPEATED_ERROR_FAMILY") and _repeated_known(families, config.error_repeat_threshold):
        signals.append("REPEATED_ERROR_FAMILY")
        evidence.append(f"same normalized error family repeated {config.error_repeat_threshold} times")

    if enabled("NO_STATE_DELTA") and window_ready and _all_present(state_after_values) and _all_equal_known(states):
        signals.append("NO_STATE_DELTA")
        evidence.append(f"state fingerprint unchanged across {recent_length} observed steps")

    if enabled("NO_NEW_ARTIFACT") and window_ready and _all_present(artifacts) and not any(nonempty(item) for item in artifacts):
        signals.append("NO_NEW_ARTIFACT")
        evidence.append(f"no verified artifact/resource created across {recent_length} observed steps")

    if enabled("NO_SUBTASK_PROGRESS") and window_ready and _all_present(subtasks) and not _increasing_or_nonempty(subtasks):
        signals.append("NO_SUBTASK_PROGRESS")
        evidence.append(f"no verified subtask completion across {recent_length} observed steps")

    if enabled("NO_CONSTRAINT_REDUCTION") and window_ready and _all_present(constraints) and not _increasing_or_nonempty(constraints):
        signals.append("NO_CONSTRAINT_REDUCTION")
        evidence.append(f"no constraint reduction across {recent_length} observed steps")

    if enabled("CONTEXT_GROWTH_WITHOUT_PROGRESS") and window_ready and _context_growth_values(contexts, tokens) and not progress:
        signals.append("CONTEXT_GROWTH_WITHOUT_PROGRESS")
        evidence.append("context or token usage increased while no positive progress signal was observed")

    if enabled("CYCLE_DETECTION"):
        cycle_length = _repeated_cycle_pairs(pairs, config.cycle_repetitions)
        if cycle_length is not None:
            signals.append("CYCLE_DETECTION")
            evidence.append(f"normalized action/state cycle repeated with period {cycle_length}")

    if enabled("BUDGET_RISK"):
        budget_evidence = _incremental_budget_risk(state, config)
        if budget_evidence:
            signals.append("BUDGET_RISK")
            evidence.extend(budget_evidence)

    negative = set(signals)
    hard_loop = bool({"EXACT_REPEAT", "CYCLE_DETECTION"} & negative)
    stagnation = bool(
        {
            "REPEATED_ERROR_FAMILY",
            "NO_STATE_DELTA",
            "NO_NEW_ARTIFACT",
            "NO_SUBTASK_PROGRESS",
            "NO_CONSTRAINT_REDUCTION",
            "CONTEXT_GROWTH_WITHOUT_PROGRESS",
        }
        & negative
    )
    cyclic_state_changes = hard_loop and set(progress) <= {"STATE_TRANSITION"}
    substantive_stagnation = bool(
        {
            "REPEATED_ERROR_FAMILY",
            "NO_STATE_DELTA",
            "NO_SUBTASK_PROGRESS",
            "NO_CONSTRAINT_REDUCTION",
            "CONTEXT_GROWTH_WITHOUT_PROGRESS",
        }
        & negative
    )
    conflict = bool(negative) and bool(progress) and (hard_loop or substantive_stagnation) and not cyclic_state_changes

    if conflict:
        evidence.append("positive progress evidence conflicts with stagnation/loop signals")
        return Detection("UNKNOWN", "CONFLICTING", tuple(evidence), tuple(sorted(signals)), recent_ids)
    if "BUDGET_RISK" in negative and not progress:
        return Detection("BUDGET_RISK", "DETERMINISTIC", tuple(evidence), tuple(sorted(signals)), recent_ids)
    meaningful_progress = strong_progress - {"STATE_TRANSITION"}
    if hard_loop and not (set(progress) & meaningful_progress):
        return Detection("LOOPING", "DETERMINISTIC", tuple(evidence), tuple(sorted(signals)), recent_ids)
    if stagnation and not progress:
        return Detection("STAGNATING", "DETERMINISTIC", tuple(evidence), tuple(sorted(signals)), recent_ids)
    if progress:
        return Detection("PROGRESSING", "DETERMINISTIC", tuple(evidence), tuple(sorted(signals)), recent_ids)
    if state.event_count < config.window:
        evidence.append(f"only {state.event_count} events observed; window requires {config.window}")
    else:
        evidence.append("no sufficient positive or negative signal was observable")
    return Detection("UNKNOWN", "INSUFFICIENT", tuple(evidence), tuple(sorted(signals)), recent_ids)


def _incremental_budget_risk(state: _IncrementalState, config: DetectorConfig) -> list[str]:
    ratios: list[tuple[str, float]] = []
    if config.max_steps is not None:
        ratios.append(("steps", state.event_count / config.max_steps))
    if config.max_tokens is not None and state.all_tokens_present:
        ratios.append(("tokens", state.token_sum / config.max_tokens))
    if config.max_cost is not None and state.all_costs_present:
        ratios.append(("cost", state.cost_sum / config.max_cost))
    if (
        config.max_seconds is not None
        and state.all_timestamps_present
        and state.first_timestamp is not None
        and state.last_timestamp is not None
        and state.last_timestamp >= state.first_timestamp
    ):
        ratios.append(("time", (state.last_timestamp - state.first_timestamp) / config.max_seconds))
    return [f"{name} budget at {ratio:.0%} of configured limit" for name, ratio in ratios if ratio >= config.budget_risk_ratio]


def _positive_signals(events: list[TrajectoryEvent]) -> set[str]:
    signals: set[str] = set()
    previous_state: str | None = None
    previous_error: str | None = None
    previous_subtasks: Any = None
    previous_constraints: Any = None
    for event in events:
        before = fingerprint(event.state_before)
        after = fingerprint(event.state_after)
        if before is not None and after is not None and before != after:
            signals.add("STATE_TRANSITION")
        if nonempty(event.artifacts_created):
            signals.add("NEW_ARTIFACT")
        if nonempty(event.subtasks_completed) or numeric_progress(previous_subtasks, event.subtasks_completed):
            signals.add("SUBTASK_COMPLETED")
        if nonempty(event.constraints_resolved) or numeric_progress(previous_constraints, event.constraints_resolved):
            signals.add("CONSTRAINT_RESOLVED")
        if metadata_flag(event, "verified_observation"):
            signals.add("NEW_VERIFIED_OBSERVATION")
        if metadata_flag(event, "checkpoint_advanced"):
            signals.add("CHECKPOINT_ADVANCED")
        current_state = state_fingerprint(event)
        current_error = error_family(event)
        if previous_state is not None and current_state is not None and previous_state != current_state:
            signals.add("STATE_TRANSITION")
        if previous_error is not None and current_error is not None and previous_error != current_error:
            signals.add("ERROR_CLASS_CHANGED")
        previous_state = current_state
        previous_error = current_error
        previous_subtasks = event.subtasks_completed
        previous_constraints = event.constraints_resolved
    return signals


def _repeated_known(values: list[Any], threshold: int) -> bool:
    return len(values) >= threshold and values[-threshold:] == [values[-1]] * threshold and values[-1] is not None


def _all_present(values: list[Any]) -> bool:
    return bool(values) and all(value is not None for value in values)


def _all_equal_known(values: list[Any]) -> bool:
    return _all_present(values) and len(set(values)) == 1


def _increasing_or_nonempty(values: list[Any]) -> bool:
    for index, value in enumerate(values):
        if nonempty(value):
            return True
        if index and numeric_progress(values[index - 1], value):
            return True
    return False


def _context_growth(events: list[TrajectoryEvent]) -> bool:
    contexts = [event.context_size for event in events]
    tokens = [event.token_delta for event in events]
    return _context_growth_values(contexts, tokens)


def _context_growth_values(contexts: list[Any], tokens: list[Any]) -> bool:
    context_grows = _all_present(contexts) and contexts[-1] > contexts[0]
    token_grows = _all_present(tokens) and sum(tokens) > 0
    return bool(context_grows or token_grows)


def _repeated_cycle(events: list[TrajectoryEvent], repetitions: int) -> int | None:
    pairs = [(action_fingerprint(event), state_fingerprint(event)) for event in events]
    return _repeated_cycle_pairs(pairs, repetitions)


def _repeated_cycle_pairs(pairs: list[tuple[str | None, str | None]], repetitions: int) -> int | None:
    if any(action is None or state is None for action, state in pairs):
        return None
    for period in range(1, min(3, len(pairs) // repetitions) + 1):
        sample = pairs[-period:]
        if pairs[-period * repetitions :] == sample * repetitions and period > 1 and len(set(sample)) > 1:
            return period
    return None


def _budget_risk(events: list[TrajectoryEvent], config: DetectorConfig) -> list[str]:
    ratios: list[tuple[str, float]] = []
    if config.max_steps is not None:
        ratios.append(("steps", len(events) / config.max_steps))
    tokens = [event.token_delta for event in events]
    if config.max_tokens is not None and _all_present(tokens):
        ratios.append(("tokens", sum(tokens) / config.max_tokens))
    costs = [event.cost_delta for event in events]
    if config.max_cost is not None and _all_present(costs):
        ratios.append(("cost", sum(costs) / config.max_cost))
    timestamps = [event.timestamp for event in events]
    if config.max_seconds is not None and _all_present(timestamps) and timestamps[-1] >= timestamps[0]:
        ratios.append(("time", (timestamps[-1] - timestamps[0]) / config.max_seconds))
    return [f"{name} budget at {ratio:.0%} of configured limit" for name, ratio in ratios if ratio >= config.budget_risk_ratio]


def _window_ids(events: list[TrajectoryEvent]) -> tuple[Any, ...]:
    return tuple(event.step_id if event.step_id is not None else index for index, event in enumerate(events))
