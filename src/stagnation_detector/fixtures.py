"""Deterministic fault-injected benchmark fixtures."""

from __future__ import annotations

from typing import Any


def _event(step: int, **kwargs: Any) -> dict[str, Any]:
    value = {"event_type": "tool", "step_id": step, "timestamp": float(step)}
    value.update(kwargs)
    return value


def _fixture(
    fixture_id: str,
    description: str,
    events: list[dict[str, Any]],
    expected_class: str,
    reason: str,
    progress: list[str] | None = None,
    stagnation: list[str] | None = None,
    ambiguity: str = "",
) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "description": description,
        "trajectory_events": events,
        "expected_class": expected_class,
        "reason": reason,
        "known_progress_signals": progress or [],
        "known_stagnation_signals": stagnation or [],
        "ambiguity_notes": ambiguity,
    }


def benchmark_fixtures() -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []

    fixtures.append(
        _fixture(
            "S01",
            "Exact identical tool retry loop",
            [
                _event(i, tool_name="lookup", tool_args={"id": 7}, tool_result=None, error_type="TimeoutError", error_message="timeout", state_before={"phase": "lookup"}, state_after={"phase": "lookup"}, artifacts_created=[])
                for i in range(1, 6)
            ],
            "LOOPING",
            "same action, result, error, and state repeat",
            stagnation=["EXACT_REPEAT", "NO_STATE_DELTA"],
        )
    )
    fixtures.append(
        _fixture(
            "S02",
            "Same error family and same state repeated",
            [
                _event(i, tool_name="parse", tool_args={"doc": "a"}, tool_result=None, error_type="ValueError", error_message=f"invalid field {i}", state_before={"phase": "parse"}, state_after={"phase": "parse"}, artifacts_created=[])
                for i in range(1, 6)
            ],
            "STAGNATING",
            "permanent validation family repeats while state is unchanged",
            stagnation=["REPEATED_ERROR_FAMILY", "NO_STATE_DELTA"],
        )
    )
    cycle_events: list[dict[str, Any]] = []
    for i in range(1, 7):
        phase = "A" if i % 2 else "B"
        cycle_events.append(_event(i, tool_name=f"step_{phase}", tool_args={}, tool_result={"phase": phase}, state_before={"phase": phase}, state_after={"phase": phase}))
    fixtures.append(_fixture("S03", "Alternating A-B-A-B action cycle", cycle_events, "LOOPING", "normalized action/state cycle repeats", stagnation=["CYCLE_DETECTION"]))
    fixtures.append(
        _fixture(
            "S04",
            "Different arguments but identical normalized result",
            [_event(i, tool_name="search", tool_args={"query": f"q{i}"}, tool_result={"items": []}, state_before={"phase": "search"}, state_after={"phase": "search"}, artifacts_created=[]) for i in range(1, 6)],
            "STAGNATING",
            "novel arguments do not change state or produce evidence",
            stagnation=["NO_STATE_DELTA", "NO_NEW_ARTIFACT"],
        )
    )
    fixtures.append(
        _fixture(
            "S05",
            "Context growth while state remains unchanged",
            [_event(i, tool_name="reason", tool_args={"round": i}, tool_result={"text": f"different-{i}"}, state_before={"phase": "reason"}, state_after={"phase": "reason"}, artifacts_created=[], token_delta=20, context_size=100 * i) for i in range(1, 6)],
            "STAGNATING",
            "tokens/context grow without a state or evidence change",
            stagnation=["CONTEXT_GROWTH_WITHOUT_PROGRESS", "NO_STATE_DELTA"],
        )
    )
    fixtures.append(
        _fixture(
            "S06",
            "Retry after a permanent 4xx",
            [_event(i, tool_name="create", tool_args={"field": f"bad-{i}"}, tool_result=None, error_type="HTTPError", error_message=f"400 invalid request {i}", state_before={"phase": "create"}, state_after={"phase": "create"}, artifacts_created=[]) for i in range(1, 5)],
            "STAGNATING",
            "permanent client error is retried with no changed state",
            stagnation=["REPEATED_ERROR_FAMILY", "NO_STATE_DELTA"],
        )
    )
    fixtures.append(
        _fixture(
            "S07",
            "Repeated parser repair failure",
            [_event(i, tool_name="parse_json", tool_args={"repair": i}, tool_result=None, error_type="ParserError", error_message=f"unexpected token {i}", state_before={"phase": "parse"}, state_after={"phase": "parse"}, artifacts_created=[]) for i in range(1, 5)],
            "STAGNATING",
            "parser repair changes syntax but not the execution state",
            stagnation=["REPEATED_ERROR_FAMILY", "NO_STATE_DELTA"],
        )
    )
    fixtures.append(
        _fixture(
            "S08",
            "Tool result is ignored and the same tool is called again",
            [_event(i, tool_name="lookup", tool_args={"id": 7}, tool_result={"id": 7}, state_before={"phase": "lookup"}, state_after={"phase": "lookup"}, artifacts_created=[], metadata={"tool_result_ignored": True}) for i in range(1, 5)],
            "LOOPING",
            "same completed observation is re-issued without state advancement",
            stagnation=["EXACT_REPEAT", "NO_STATE_DELTA"],
        )
    )
    fixtures.append(
        _fixture(
            "S09",
            "Unresolved constraints remain unchanged",
            [_event(i, tool_name="plan", tool_args={"attempt": i}, tool_result={"plan": "same"}, state_before={"phase": "plan"}, state_after={"phase": "plan"}, artifacts_created=[], constraints_resolved=[], metadata={"unresolved_constraints": ["auth", "schema"]}) for i in range(1, 5)],
            "STAGNATING",
            "no constraint is resolved despite repeated planning",
            stagnation=["NO_CONSTRAINT_REDUCTION", "NO_STATE_DELTA"],
        )
    )
    fixtures.append(
        _fixture(
            "S10",
            "Budget burn with no verified progress",
            [_event(i, tool_name="reason", tool_args={"round": i}, tool_result={"text": f"new-{i}"}, state_before={"phase": "reason"}, state_after={"phase": "reason"}, artifacts_created=[], token_delta=100, context_size=i * 100) for i in range(1, 6)],
            "BUDGET_RISK",
            "configured token budget reaches the risk threshold without progress",
            stagnation=["BUDGET_RISK", "NO_STATE_DELTA"],
        )
    )

    fixtures.append(_fixture("L11", "Same tool over multiple files with a new artifact each time", [_event(i, tool_name="read", tool_args={"file": f"file-{i}"}, tool_result={"ok": True}, state_before={"phase": "files"}, state_after={"phase": f"file-{i}"}, artifacts_created=[f"artifact-{i}"]) for i in range(1, 6)], "PROGRESSING", "each iteration creates a new verified artifact", progress=["NEW_ARTIFACT", "STATE_TRANSITION"]))
    fixtures.append(_fixture("L12", "Batch processing independent records", [_event(i, tool_name="process", tool_args={"record": i}, tool_result={"ok": True}, state_before={"processed": i - 1}, state_after={"processed": i}, artifacts_created=[], subtasks_completed=[i]) for i in range(1, 6)], "PROGRESSING", "each record is a completed subtask", progress=["SUBTASK_COMPLETED", "STATE_TRANSITION"]))
    fixtures.append(_fixture("L13", "Search iterations produce new verified evidence", [_event(i, tool_name="search", tool_args={"query": f"q{i}"}, tool_result={"evidence": [i]}, state_before={"phase": "search", "count": i - 1}, state_after={"phase": "search", "count": i}, artifacts_created=[], metadata={"verified_observation": True}) for i in range(1, 5)], "PROGRESSING", "verified observations and state change accumulate", progress=["NEW_VERIFIED_OBSERVATION", "STATE_TRANSITION"]))
    fixtures.append(_fixture("L14", "Debugging reduces the set of possible causes", [_event(i, tool_name="test", tool_args={"case": i}, tool_result={"remaining_causes": 5 - i}, state_before={"causes": 6 - i}, state_after={"causes": 5 - i}, artifacts_created=[], constraints_resolved=[f"cause-{i}"]) for i in range(1, 5)], "PROGRESSING", "each iteration removes a possible cause", progress=["CONSTRAINT_RESOLVED", "STATE_TRANSITION"]))
    transient = [_event(1, tool_name="fetch", tool_args={"id": 1}, tool_result=None, error_type="TimeoutError", error_message="timeout", state_before={"phase": "fetch"}, state_after={"phase": "fetch"}, artifacts_created=[]), _event(2, tool_name="fetch", tool_args={"id": 1}, tool_result={"id": 1}, error_type=None, error_message=None, state_before={"phase": "fetch"}, state_after={"phase": "done"}, artifacts_created=["record-1"])]
    fixtures.append(_fixture("L15", "Transient retry eventually succeeds", transient, "PROGRESSING", "error class changes and the state advances", progress=["ERROR_CLASS_CHANGED", "STATE_TRANSITION", "NEW_ARTIFACT"]))
    fixtures.append(_fixture("L16", "One subtask completes per iteration", [_event(i, tool_name="work", tool_args={"subtask": i}, tool_result={"ok": True}, state_before={"done": i - 1}, state_after={"done": i}, artifacts_created=[], subtasks_completed=[i]) for i in range(1, 6)], "PROGRESSING", "verified subtask count increases", progress=["SUBTASK_COMPLETED", "STATE_TRANSITION"]))
    fixtures.append(_fixture("L17", "Long path with slowly advancing checkpoints", [_event(i, tool_name="checkpoint", tool_args={"phase": i}, tool_result={"phase": i}, state_before={"checkpoint": i - 1}, state_after={"checkpoint": i}, artifacts_created=[], metadata={"checkpoint_advanced": True}) for i in range(1, 8)], "PROGRESSING", "checkpoint advances at every step", progress=["CHECKPOINT_ADVANCED", "STATE_TRANSITION"]))

    fixtures.append(_fixture("A18", "Similar calls with incomplete state visibility", [_event(i, tool_name="query", tool_args={"q": i}, tool_result={"text": "similar"}) for i in range(1, 5)], "UNKNOWN", "no state or verified progress is visible", ambiguity="The tool may progress externally, but the trace cannot establish it."))
    fixtures.append(_fixture("A19", "New text output with unknown semantic value", [_event(i, event_type="model_output", tool_name=None, tool_result=f"new wording {i}") for i in range(1, 5)], "UNKNOWN", "text novelty is not a progress oracle", ambiguity="Novel text may or may not solve the task."))
    fixtures.append(_fixture("A20", "Tool results differ slightly but usefulness is unknown", [_event(i, tool_name="search", tool_args={"query": i}, tool_result={"text": f"variant {i}"}) for i in range(1, 5)], "UNKNOWN", "result difference is observed but not verified", ambiguity="No state, artifact, or domain oracle is present."))
    fixtures.append(_fixture("A21", "Partial state information", [_event(i, tool_name="update", tool_args={"field": i}, tool_result={"ok": True}, state_before={"phase": "update"}) for i in range(1, 5)], "UNKNOWN", "state_after is absent, so state transition cannot be established", ambiguity="The external state may have advanced."))
    fixtures.append(_fixture("A22", "Conflicting progress and stagnation signals", [_event(i, tool_name="lookup", tool_args={"id": 7}, tool_result={"text": f"observation-{i}"}, error_type="TimeoutError", error_message=f"timeout {i}", state_before={"phase": "lookup"}, state_after={"phase": "lookup"}, artifacts_created=[], metadata={"verified_observation": True}) for i in range(1, 5)], "UNKNOWN", "verified-observation flag conflicts with repeated error and unchanged state", progress=["NEW_VERIFIED_OBSERVATION"], stagnation=["REPEATED_ERROR_FAMILY", "NO_STATE_DELTA"], ambiguity="The observation may be real, but the state transition is not established."))
    return fixtures
