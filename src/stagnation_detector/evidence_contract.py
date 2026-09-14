"""Deterministic evidence contracts layered over the frozen ICM 07 detector.

This module deliberately does not change the detector policy.  It answers a
narrower question: whether the signals and trusted anchors are sufficient to
authorize a hard decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .detector import DetectorConfig, Detection, detect_stagnation
from .events import TrajectoryEvent
from .normalize import action_fingerprint, error_family, fingerprint, observation_fingerprint, state_fingerprint


HARD_STOPS = frozenset({"STAGNATING", "LOOPING", "BUDGET_RISK"})
CONTRACTS = ("TWO_ANCHOR", "TWO_OF_THREE", "STRONG_SINGLE", "WEIGHTED", "CONSERVATIVE_UNKNOWN")
TELEMETRY_CLASSES = ("FULL", "REDUCED", "MINIMAL", "INSUFFICIENT")
_ANCHOR_KEYS = (
    "checkpoint_id",
    "artifact_id",
    "artifact_hash",
    "resource_id",
    "external_state_fingerprint",
    "state_version",
    "completed_step_count",
    "tool_result_fingerprint",
    "custom_user_key",
)


@dataclass(frozen=True)
class AnchorInfo:
    kind: str
    values: tuple[str, ...]
    trusted: bool

    @property
    def present(self) -> bool:
        return self.trusted and bool(self.values)

    @property
    def unchanged(self) -> bool:
        return self.present and len(set(self.values)) == 1

    @property
    def changed(self) -> bool:
        return self.present and len(set(self.values)) > 1


def _structured_state(value: Any) -> bool:
    """Accept deterministic structured state, reject free-form claims."""
    return value is not None and not isinstance(value, str) and not isinstance(value, bytes)


def _metadata(event: TrajectoryEvent) -> Mapping[str, Any]:
    return event.metadata if isinstance(event.metadata, Mapping) else {}


def _explicit_anchor(event: TrajectoryEvent) -> tuple[str, Any] | None:
    metadata = _metadata(event)
    for key in _ANCHOR_KEYS:
        value = metadata.get(key)
        if value is not None:
            return key, value
    return None


def trusted_state_anchor(events: Iterable[TrajectoryEvent]) -> AnchorInfo:
    values = list(events)
    if not values or not all(_structured_state(event.state_after) for event in values):
        return AnchorInfo("state_fingerprint", (), False)
    return AnchorInfo("state_fingerprint", tuple(fingerprint(event.state_after) for event in values), True)


def trusted_progress_anchor(events: Iterable[TrajectoryEvent]) -> AnchorInfo:
    values = list(events)
    explicit: list[tuple[str, Any]] = []
    for event in values:
        anchor = _explicit_anchor(event)
        if anchor is None:
            artifacts = event.artifacts_created
            if artifacts is not None and isinstance(artifacts, (list, tuple, set)) and artifacts:
                anchor = ("artifact_id", artifacts)
        if anchor is None:
            return AnchorInfo("progress_anchor", (), False)
        explicit.append(anchor)
    if not explicit:
        return AnchorInfo("progress_anchor", (), False)
    kinds = {kind for kind, _ in explicit}
    if len(kinds) != 1:
        return AnchorInfo("progress_anchor", (), False)
    return AnchorInfo(next(iter(kinds)), tuple(fingerprint(value) for _, value in explicit), True)


def _has_result_or_error(event: TrajectoryEvent) -> bool:
    return event.tool_result is not None or error_family(event) is not None


def _has_action(event: TrajectoryEvent) -> bool:
    return action_fingerprint(event) is not None and event.step_id is not None


def telemetry_class(events: Iterable[TrajectoryEvent]) -> str:
    values = list(events)
    if not values or not all(_has_action(event) and _has_result_or_error(event) for event in values):
        return "INSUFFICIENT"
    state = trusted_state_anchor(values).present
    progress = trusted_progress_anchor(values).present
    if state and progress:
        return "FULL"
    if state or progress:
        return "REDUCED"
    return "MINIMAL"


def _signal_groups(detection: Detection, events: list[TrajectoryEvent]) -> dict[str, bool]:
    signals = set(detection.signals)
    recent = events[-3:]
    actions = [action_fingerprint(event) for event in recent]
    results = [fingerprint(event.tool_result) if event.tool_result is not None else error_family(event) for event in recent]
    action_result_repeat = (
        len(recent) == 3
        and all(value is not None for value in actions + results)
        and len(set(zip(actions, results))) == 1
    )
    state = trusted_state_anchor(events)
    progress = trusted_progress_anchor(events)
    return {
        "action_result_repetition": action_result_repeat or "EXACT_REPEAT" in signals,
        "state_stagnation": state.unchanged or "NO_STATE_DELTA" in signals,
        "progress_anchor_stagnation": progress.unchanged,
        "primary_repeat": bool({"EXACT_REPEAT", "REPEATED_ERROR_FAMILY", "CYCLE_DETECTION"} & signals),
        "primary_error": "REPEATED_ERROR_FAMILY" in signals,
        "cycle": "CYCLE_DETECTION" in signals,
        "budget": "BUDGET_RISK" in signals,
        "context_growth": "CONTEXT_GROWTH_WITHOUT_PROGRESS" in signals,
        "no_artifact": "NO_NEW_ARTIFACT" in signals,
        "trusted_state": state.present,
        "trusted_progress": progress.present,
        "trusted_state_unchanged": state.unchanged,
        "trusted_progress_unchanged": progress.unchanged,
    }


def _base_detection(events: list[TrajectoryEvent], config: DetectorConfig | None) -> Detection:
    return detect_stagnation(events, config)


def _decision_reason(decision: str, groups: Mapping[str, bool], missing: list[str]) -> str:
    if decision == "LOOPING":
        return "Repeated normalized cycle/repetition is corroborated by a trusted unchanged state anchor."
    if decision == "STAGNATING":
        return "A primary stagnation signal is corroborated by an independent trusted anchor with no observed advance."
    if decision == "BUDGET_RISK":
        return "A configured budget threshold is reached without positive progress evidence."
    if decision == "PROGRESSING":
        return "At least one explicit deterministic progress signal is present and no contract conflict was observed."
    return "Hard decision withheld because the required evidence contract was not satisfied: " + ", ".join(missing or ["no decisive evidence"]) + "."


def _evaluate_contract(name: str, detection: Detection, groups: Mapping[str, bool], telemetry: str) -> tuple[str, list[str], list[str], bool]:
    missing: list[str] = []
    used: list[str] = []
    primary = groups["primary_repeat"] or groups["primary_error"] or groups["cycle"] or "NO_STATE_DELTA" in detection.signals
    # Presence alone is not progress evidence: the anchor must remain
    # unchanged while the primary signal repeats.
    anchor = groups["trusted_state_unchanged"] or groups["trusted_progress_unchanged"]
    hard = False
    decision = "UNKNOWN"

    if name == "TWO_ANCHOR":
        if groups["cycle"] or groups["primary_error"] or "EXACT_REPEAT" in detection.signals:
            hard = anchor
            used = ["primary repetition/error/cycle"] + (["trusted unchanged state/progress anchor"] if anchor else [])
        elif "NO_STATE_DELTA" in detection.signals:
            hard = groups["trusted_progress"] and groups["trusted_state"]
            used = ["trusted unchanged state anchor", "independent trusted progress anchor"] if hard else ["NO_STATE_DELTA"]
        if not anchor:
            missing.append("one independent trusted state/progress anchor")
        if not primary:
            missing.append("one primary stagnation signal")
    elif name == "TWO_OF_THREE":
        indicators = sum((groups["action_result_repetition"], groups["state_stagnation"], groups["progress_anchor_stagnation"]))
        hard = indicators >= 2 and anchor
        used = [label for label, value in (("action/result repetition", groups["action_result_repetition"]), ("state stagnation", groups["state_stagnation"]), ("progress-anchor stagnation", groups["progress_anchor_stagnation"])) if value]
        if indicators < 2:
            missing.append("two of action/result, state, and progress-anchor evidence")
        if not anchor:
            missing.append("one trusted anchor")
    elif name == "STRONG_SINGLE":
        hard = groups["cycle"] and groups["trusted_state"] and telemetry in {"FULL", "REDUCED"}
        used = ["exact normalized A-B cycle", "trusted normalized state series"] if hard else ["cycle candidate"]
        if not groups["cycle"]:
            missing.append("deterministic normalized cycle")
        if not groups["trusted_state"]:
            missing.append("trusted normalized state series")
        if telemetry == "MINIMAL":
            missing.append("at least REDUCED telemetry")
    elif name == "WEIGHTED":
        weights = {
            "EXACT_REPEAT": 3,
            "REPEATED_ERROR_FAMILY": 3,
            "CYCLE_DETECTION": 4,
            "NO_STATE_DELTA": 2,
            "NO_NEW_ARTIFACT": 1,
            "CONTEXT_GROWTH_WITHOUT_PROGRESS": 1,
        }
        score = sum(weights.get(signal, 0) for signal in detection.signals)
        hard = score >= 4 and primary and anchor
        used = [f"fixed evidence score={score}"]
        if score < 4:
            missing.append("fixed score >= 4")
        if not primary:
            missing.append("one primary signal")
        if not anchor:
            missing.append("one trusted anchor")
    elif name == "CONSERVATIVE_UNKNOWN":
        hard = groups["cycle"] and groups["trusted_state_unchanged"] and groups["trusted_progress_unchanged"]
        used = ["cycle", "trusted state anchor", "independent trusted progress anchor"] if hard else []
        if not groups["cycle"]:
            missing.append("deterministic cycle")
        if not groups["trusted_state"]:
            missing.append("trusted state anchor")
        if not groups["trusted_progress"]:
            missing.append("independent trusted progress anchor")

    if hard:
        decision = "LOOPING" if groups["cycle"] or "EXACT_REPEAT" in detection.signals else "STAGNATING"
    elif groups["budget"] and not detection.evidence_strength == "CONFLICTING":
        decision = "BUDGET_RISK"
        used.append("budget threshold")
    elif detection.status == "PROGRESSING":
        decision = "PROGRESSING"
        used.extend([item for item in detection.signals if item in {"STATE_TRANSITION", "NEW_ARTIFACT", "CHECKPOINT_ADVANCED", "SUBTASK_COMPLETED", "CONSTRAINT_RESOLVED", "NEW_VERIFIED_OBSERVATION"}])
    return decision, used, missing, hard


def evaluate_contract(
    events: Iterable[TrajectoryEvent | Mapping[str, Any]],
    contract: str,
    config: DetectorConfig | None = None,
) -> dict[str, Any]:
    """Return an auditable decision with no raw content requirement."""
    if contract not in CONTRACTS:
        raise ValueError(f"unknown evidence contract: {contract}")
    normalized = [event if isinstance(event, TrajectoryEvent) else TrajectoryEvent.from_mapping(event) for event in events]
    detection = _base_detection(normalized, config)
    return evaluate_detection_contract(detection, normalized, contract)


def evaluate_detection_contract(
    detection: Detection,
    events: Iterable[TrajectoryEvent | Mapping[str, Any]],
    contract: str,
) -> dict[str, Any]:
    """Evaluate a known detection against a contract.

    This additive helper is used by bounded streaming integrations.  The
    detector may have accumulated positive evidence and budget totals that are
    intentionally not present in its retained event suffix; callers provide
    the detector's current ``Detection`` and only the bounded suffix needed by
    the contract's anchor checks.
    """
    if contract not in CONTRACTS:
        raise ValueError(f"unknown evidence contract: {contract}")
    normalized = [event if isinstance(event, TrajectoryEvent) else TrajectoryEvent.from_mapping(event) for event in events]
    telemetry = telemetry_class(normalized)
    groups = _signal_groups(detection, normalized)
    decision, used, missing, satisfied = _evaluate_contract(contract, detection, groups, telemetry)
    if telemetry == "INSUFFICIENT" and decision in HARD_STOPS:
        decision = "UNKNOWN"
        satisfied = False
        missing.append("usable action/result identity and ordering")
    return {
        "decision": decision,
        "evidence_used": sorted(set(used)),
        "missing_evidence": sorted(set(missing)),
        "evidence_contract_satisfied": bool(satisfied),
        "decision_reason": _decision_reason(decision, groups, missing),
        "telemetry_class": telemetry,
        "detector_status": detection.status,
        "detector_signals": list(detection.signals),
        "detection_evidence": list(detection.evidence),
        "window": list(detection.window),
    }


def minimum_useful_telemetry() -> dict[str, Any]:
    return {
        "required_fields": ["step_id", "event_type", "tool_name or action identity", "tool_result or error family"],
        "required_anchor": "one trusted structured state/progress anchor for hard stagnation/looping decisions",
        "raw_content_required": "NO",
        "optional_fields": ["tool_args hash", "context_size", "token_delta", "cost_delta", "checkpoint/artifact IDs"],
    }
