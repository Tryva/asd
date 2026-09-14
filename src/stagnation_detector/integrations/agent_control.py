"""Agent Control integration for the ASD detector.

The module is dependency-free until the optional Agent Control evaluator
runtime is installed.  The public ``AgentControlAdapter`` is useful in local
or client-side integrations; when ``agent-control-evaluators`` is installed,
``StagnationEvaluator`` is also discoverable through the upstream
``agent_control.evaluators`` entry-point group.
"""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from numbers import Real
from typing import Any, Callable, Mapping

from ..detector import DetectorConfig, StagnationDetector
from ..evidence_contract import CONTRACTS, evaluate_detection_contract
from ..events import EventValidationError, TrajectoryEvent

try:  # Optional: local adapter use must not require the Agent Control SDK.
    from agent_control_evaluators import Evaluator, EvaluatorConfig, EvaluatorMetadata, register_evaluator
    from agent_control_models import EvaluatorResult

    _AGENT_CONTROL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised by environments without the extra.
    _AGENT_CONTROL_AVAILABLE = False

    class EvaluatorConfig:  # type: ignore[no-redef]
        """Fallback config marker used only for local dependency-free imports."""

    class Evaluator:  # type: ignore[no-redef]
        """Fallback base marker used only for local dependency-free imports."""

    class EvaluatorMetadata:  # type: ignore[no-redef]
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)


_DEFAULT_TRIGGER_STATUSES = ("STAGNATING", "LOOPING", "BUDGET_RISK")
_RECOMMENDED_ACTIONS = {
    "PROGRESSING": "ALLOW",
    "UNKNOWN": "LOG",
    "BUDGET_RISK": "WARN",
    "STAGNATING": "WARN",
    "LOOPING": "WARN",
}
_ANCHOR_FIELDS = {
    "checkpoint_id",
    "artifact_id",
    "artifact_hash",
    "resource_id",
    "external_state_fingerprint",
    "state_version",
    "completed_step_count",
    "tool_result_fingerprint",
    "custom_user_key",
}


def recommended_control_action(status: str) -> str:
    """Map a detector status to an advisory action.

    This function never enforces a policy.  In particular, ``UNKNOWN`` maps
    only to ``LOG`` and can never become ``DENY`` here.
    """

    return _RECOMMENDED_ACTIONS.get(status, "LOG")


def _read(value: Any, *names: str) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return None
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _numeric_or_none(value: Any) -> Real | None:
    return value if isinstance(value, Real) and not isinstance(value, bool) else None


def _as_key_part(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def _config_dict(config: Any) -> dict[str, Any]:
    if config is None:
        return {}
    if isinstance(config, Mapping):
        return dict(config)
    if hasattr(config, "model_dump"):
        return dict(config.model_dump())
    return {
        name: getattr(config, name)
        for name in ("contract", "trigger_statuses", "max_sessions", "session_ttl_seconds")
        if hasattr(config, name)
    }


def _make_config(config: Any) -> Any:
    values = _config_dict(config)
    if _AGENT_CONTROL_AVAILABLE:
        return _StagnationEvaluatorConfig(**values)
    return _FallbackStagnationConfig(**values)


class _FallbackStagnationConfig:
    def __init__(
        self,
        contract: str = "TWO_ANCHOR",
        trigger_statuses: tuple[str, ...] = _DEFAULT_TRIGGER_STATUSES,
        max_sessions: int = 1024,
        session_ttl_seconds: float = 3600.0,
    ) -> None:
        if contract not in CONTRACTS:
            raise ValueError(f"unknown evidence contract: {contract}")
        statuses = tuple(trigger_statuses)
        if not statuses or any(status not in {"PROGRESSING", "STAGNATING", "LOOPING", "BUDGET_RISK", "UNKNOWN"} for status in statuses):
            raise ValueError("trigger_statuses contains an unknown status")
        if max_sessions < 1 or session_ttl_seconds <= 0:
            raise ValueError("max_sessions must be positive and session_ttl_seconds must be > 0")
        self.contract = contract
        self.trigger_statuses = statuses
        self.max_sessions = max_sessions
        self.session_ttl_seconds = float(session_ttl_seconds)


if _AGENT_CONTROL_AVAILABLE:

    class _StagnationEvaluatorConfig(EvaluatorConfig):
        contract: str = "TWO_ANCHOR"
        trigger_statuses: tuple[str, ...] = _DEFAULT_TRIGGER_STATUSES
        max_sessions: int = 1024
        session_ttl_seconds: float = 3600.0


@dataclass
class _SessionState:
    detector: StagnationDetector
    last_seen: float


class AgentControlAdapter:
    """Normalize Agent Control runtime steps and maintain isolated bounded state."""

    def __init__(
        self,
        *,
        contract: str = "TWO_ANCHOR",
        detector_config: DetectorConfig | None = None,
        max_sessions: int = 1024,
        session_ttl_seconds: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if contract not in CONTRACTS:
            raise ValueError(f"unknown evidence contract: {contract}")
        if max_sessions < 1 or session_ttl_seconds <= 0:
            raise ValueError("max_sessions must be positive and session_ttl_seconds must be > 0")
        self.contract = contract
        self.detector_config = detector_config or DetectorConfig()
        self.max_sessions = max_sessions
        self.session_ttl_seconds = float(session_ttl_seconds)
        self._clock = clock
        self._sessions: OrderedDict[str, _SessionState] = OrderedDict()
        self._lock = threading.RLock()

    def stable_session_key(self, runtime: Any, step: Any = None) -> str | None:
        """Return an explicit or composite ``agent/run/session`` namespace.

        A caller-provided ``session_key`` is treated as the complete namespace.
        Otherwise the key includes the Agent Control agent identity and all
        available session/run identity fields.  No state is created without a
        stable identity, preventing unrelated trajectories from being mixed.
        """

        context = _mapping(_read(step, "context", "metadata"))
        raw = _mapping(runtime)
        runtime_metadata = _mapping(_read(runtime, "metadata"))
        metadata = dict(runtime_metadata)
        metadata.update(_mapping(_first(raw.get("metadata"), context)))
        explicit = _first(raw.get("session_key"), _read(runtime, "session_key"), metadata.get("session_key"), _read(step, "session_key"))
        if explicit is not None:
            return _as_key_part(explicit)
        agent = _first(
            raw.get("agent_name"), raw.get("agent_id"), _read(runtime, "agent_name", "agent_id"), metadata.get("agent_name"),
            metadata.get("agent_id"), _read(step, "agent_name", "agent_id"),
        )
        session = _first(raw.get("session_id"), _read(runtime, "session_id"), metadata.get("session_id"), _read(step, "session_id"))
        run = _first(raw.get("run_id"), _read(runtime, "run_id"), metadata.get("run_id"), _read(step, "run_id"))
        trace = _first(raw.get("trace_id"), _read(runtime, "trace_id"), metadata.get("trace_id"), _read(step, "trace_id"))
        agent_part = _as_key_part(agent)
        identity = [_as_key_part(value) for value in (session, run, trace)]
        identity = [value for value in identity if value is not None]
        if agent_part is None or not identity:
            return None
        return json.dumps([agent_part, *identity], separators=(",", ":"), ensure_ascii=True)

    def normalize(self, runtime: Any, step: Any = None) -> TrajectoryEvent:
        """Convert a mapping or Agent Control ``Step`` to ``TrajectoryEvent``.

        The adapter accepts fingerprints in place of raw results and only
        trusts explicitly named structured state/progress anchors.
        """

        raw = _mapping(runtime)
        step_context = _mapping(_read(step, "context", "metadata"))
        raw_metadata = _mapping(raw.get("metadata"))
        metadata = dict(step_context)
        metadata.update(raw_metadata)
        event_type = _first(raw.get("event_type"), raw.get("type"), raw.get("step_type"), _read(step, "event_type", "step_type", "type"), "agent_control.step")
        step_id = _first(raw.get("step_id"), raw.get("step"), raw.get("order"), _read(step, "step_id", "step", "order"))
        tool_name = _first(raw.get("tool_name"), raw.get("tool"), raw.get("name"), raw.get("step_name"), _read(step, "tool_name", "tool", "name", "step_name"))
        tool_args = _first(raw.get("tool_args"), raw.get("input"), raw.get("arguments"), _read(step, "tool_args", "input", "arguments"))
        result = _first(raw.get("tool_result"), raw.get("result"), raw.get("output"), _read(step, "tool_result", "result", "output"))
        error = _first(raw.get("error"), _read(step, "error"))
        error_type = _first(raw.get("error_type"), _read(step, "error_type"))
        error_message = _first(raw.get("error_message"), _read(step, "error_message"))
        if isinstance(error, Mapping):
            error_type = _first(error_type, error.get("type"))
            error_message = _first(error_message, error.get("message"))
        elif error is not None:
            error_message = _first(error_message, str(error))

        state_before = _first(raw.get("state_before"), metadata.get("state_before"))
        state_after = _first(raw.get("state_after"), metadata.get("state_after"))
        state_fingerprint = _first(raw.get("state_fingerprint"), metadata.get("state_fingerprint"), metadata.get("trusted_state_fingerprint"))
        if state_after is None and state_fingerprint is not None:
            state_after = {"fingerprint": str(state_fingerprint)}
        result_fingerprint = _first(raw.get("result_fingerprint"), raw.get("tool_result_fingerprint"), metadata.get("tool_result_fingerprint"))
        if result is None and result_fingerprint is not None:
            result = {"fingerprint": str(result_fingerprint)}
        action_fingerprint = _first(raw.get("action_fingerprint"), metadata.get("action_fingerprint"))
        if tool_name is None and action_fingerprint is not None:
            tool_name = "fingerprinted_action"
            tool_args = {"fingerprint": str(action_fingerprint)}

        anchor = _first(raw.get("progress_anchor"), metadata.get("progress_anchor"), raw.get("progress_anchor_id"), metadata.get("progress_anchor_id"))
        if anchor is not None and not any(key in metadata for key in _ANCHOR_FIELDS):
            metadata["custom_user_key"] = anchor
        metadata["agent_control_adapter"] = "asd"
        return TrajectoryEvent.from_mapping(
            {
                "event_type": str(event_type),
                "timestamp": _numeric_or_none(_first(raw.get("timestamp"), _read(step, "timestamp"))),
                "step_id": step_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
                "tool_result": result,
                "error_type": error_type,
                "error_message": error_message,
                "state_before": state_before,
                "state_after": state_after,
                "artifacts_created": _first(raw.get("artifacts_created"), metadata.get("artifacts_created")),
                "subtasks_completed": _first(raw.get("subtasks_completed"), metadata.get("subtasks_completed")),
                "constraints_resolved": _first(raw.get("constraints_resolved"), metadata.get("constraints_resolved")),
                "token_delta": _numeric_or_none(_first(raw.get("token_delta"), metadata.get("token_delta"))),
                "cost_delta": _numeric_or_none(_first(raw.get("cost_delta"), metadata.get("cost_delta"))),
                "context_size": _numeric_or_none(_first(raw.get("context_size"), metadata.get("context_size"))),
                "metadata": metadata,
            }
        )

    def evaluate(self, runtime: Any, *, session_key: str | None = None, step: Any = None) -> dict[str, Any]:
        """Record one event and return the structured ASD decision."""

        try:
            event = runtime if isinstance(runtime, TrajectoryEvent) else self.normalize(runtime, step)
        except (EventValidationError, ValueError, TypeError) as exc:
            return self._unknown("event could not be normalized", [str(exc)])
        key = session_key or self.stable_session_key(runtime, step)
        if key is None:
            return self._unknown(
                "stable agent/session/run identity is required before state can be retained",
                ["agent identity", "session_id or run_id or trace_id"],
            )
        now = self._clock()
        with self._lock:
            self._prune(now)
            state = self._sessions.get(key)
            if state is None:
                state = _SessionState(StagnationDetector(self.detector_config), now)
                self._sessions[key] = state
            else:
                state.last_seen = now
                self._sessions.move_to_end(key)
            detection = state.detector.observe(event)
            # Detection already carries cumulative progress/budget summaries;
            # contract anchor checks only need the same current decision window.
            # This keeps the integration O(window) per event even when the
            # detector retains a larger bounded audit suffix.
            contract_events = state.detector.events[-self.detector_config.window :]
            contract = evaluate_detection_contract(detection, contract_events, self.contract)
            if detection.evidence_strength == "CONFLICTING":
                # The evidence contract may find two anchors while the core
                # detector has explicitly withheld the decision because
                # positive and negative evidence conflict.  Preserve that
                # safer core outcome at the runtime boundary.
                contract = dict(contract)
                contract["decision"] = "UNKNOWN"
                contract["evidence_contract_satisfied"] = False
                contract["missing_evidence"] = sorted(
                    set(contract["missing_evidence"]) | {"non-conflicting evidence"}
                )
                contract["decision_reason"] = (
                    "Decision withheld because positive progress evidence "
                    "conflicts with stagnation/loop evidence."
                )
            return self._structured(contract)

    def _prune(self, now: float) -> None:
        expired = [key for key, state in self._sessions.items() if now - state.last_seen >= self.session_ttl_seconds]
        for key in expired:
            self._sessions.pop(key, None)
        while len(self._sessions) >= self.max_sessions:
            self._sessions.popitem(last=False)

    @staticmethod
    def _unknown(reason: str, missing: list[str]) -> dict[str, Any]:
        return {
            "status": "UNKNOWN",
            "evidence": [],
            "missing_evidence": missing,
            "evidence_contract_satisfied": False,
            "reason": reason,
            "confidence_basis": "no safe deterministic decision; identity or event evidence is missing",
            "recommended_control_action": "LOG",
        }

    @staticmethod
    def _structured(contract: Mapping[str, Any]) -> dict[str, Any]:
        status = str(contract["decision"])
        return {
            "status": status,
            "evidence": list(contract["detection_evidence"]),
            "missing_evidence": list(contract["missing_evidence"]),
            "evidence_contract_satisfied": bool(contract["evidence_contract_satisfied"]),
            "reason": contract["decision_reason"],
            "confidence_basis": (
                f"deterministic detector status={contract['detector_status']}; "
                f"contract={contract['telemetry_class']}; signals={','.join(contract['detector_signals']) or 'none'}"
            ),
            "recommended_control_action": recommended_control_action(status),
            "signals": list(contract["detector_signals"]),
            "window": list(contract["window"]),
            "telemetry_class": contract["telemetry_class"],
        }

    @property
    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    @property
    def retained_event_count(self) -> int:
        with self._lock:
            return sum(len(state.detector.events) for state in self._sessions.values())


class StagnationEvaluator(Evaluator):
    """Agent Control custom evaluator backed by the ASD adapter."""

    metadata = EvaluatorMetadata(
        name="asd.stagnation",
        version="0.1.0",
        description="Longitudinal ASD stagnation and loop evidence",
    )
    config_model = _StagnationEvaluatorConfig if _AGENT_CONTROL_AVAILABLE else _FallbackStagnationConfig

    def __init__(self, config: Any = None) -> None:
        self._config = _make_config(config)
        if _AGENT_CONTROL_AVAILABLE:
            super().__init__(self._config)

    def _adapter(self) -> AgentControlAdapter:
        return _adapter_for_config(self._config)

    def evaluate_event(self, runtime: Any, *, session_key: str | None = None, step: Any = None) -> dict[str, Any]:
        result = self._adapter().evaluate(runtime, session_key=session_key, step=step)
        result["matched"] = result["status"] in tuple(self._config.trigger_statuses)
        return result

    async def evaluate(self, data: Any) -> Any:
        """Evaluate selected data; full structural context is preferred."""

        result = self.evaluate_event(data)
        return _to_agent_control_result(result) if _AGENT_CONTROL_AVAILABLE else result

    async def evaluate_with_context(self, data: Any, step: Any) -> Any:
        """Use Agent Control's current full-Step extension point."""

        result = self.evaluate_event(data, step=step)
        return _to_agent_control_result(result) if _AGENT_CONTROL_AVAILABLE else result


_ADAPTERS: OrderedDict[str, AgentControlAdapter] = OrderedDict()
_ADAPTERS_LOCK = threading.Lock()
_MAX_CONFIGURED_ADAPTERS = 16


def _adapter_for_config(config: Any) -> AgentControlAdapter:
    key = json.dumps(_config_dict(config), sort_keys=True, default=str, separators=(",", ":"))
    with _ADAPTERS_LOCK:
        adapter = _ADAPTERS.get(key)
        if adapter is None:
            adapter = AgentControlAdapter(
                contract=config.contract,
                max_sessions=int(config.max_sessions),
                session_ttl_seconds=float(config.session_ttl_seconds),
            )
            _ADAPTERS[key] = adapter
        _ADAPTERS.move_to_end(key)
        while len(_ADAPTERS) > _MAX_CONFIGURED_ADAPTERS:
            _ADAPTERS.popitem(last=False)
        return adapter


def _to_agent_control_result(result: Mapping[str, Any]) -> Any:
    return EvaluatorResult(
        matched=bool(result.get("matched", False)),
        confidence=1.0 if result.get("status") != "UNKNOWN" else 0.0,
        message=str(result["reason"]),
        metadata={key: value for key, value in result.items() if key != "matched"},
    )


if _AGENT_CONTROL_AVAILABLE:
    StagnationEvaluator = register_evaluator(StagnationEvaluator)


__all__ = ["AgentControlAdapter", "StagnationEvaluator", "recommended_control_action"]
