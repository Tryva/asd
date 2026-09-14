"""Reproducible local demo of the ASD / Agent Control contract.

Run from ``stagnation-detector/``:

    python examples/agent_control_demo.py

This demo does not need a running Agent Control server.  The returned action
is the action a configured Agent Control control would apply when its
evaluator result matches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stagnation_detector.detector import DetectorConfig  # noqa: E402
from stagnation_detector.integrations.agent_control import (  # noqa: E402
    AgentControlAdapter,
    StagnationEvaluator,
)


def _event(step: int, **fields: object) -> dict[str, object]:
    value: dict[str, object] = {
        "event_type": "tool",
        "step_id": step,
        "agent_name": "demo-agent",
        "session_id": "demo-session",
    }
    value.update(fields)
    return value


def _policy_action(status: str, policy: str) -> str:
    policies = {
        "observe-only": {
            "PROGRESSING": "allow",
            "UNKNOWN": "log",
            "STAGNATING": "log",
            "LOOPING": "log",
            "BUDGET_RISK": "log",
        },
        "safe-warning": {
            "PROGRESSING": "allow",
            "UNKNOWN": "log",
            "STAGNATING": "warn",
            "LOOPING": "warn",
            "BUDGET_RISK": "warn",
        },
        "strict-loop-guard": {
            "PROGRESSING": "allow",
            "UNKNOWN": "log",
            "STAGNATING": "warn",
            "LOOPING": "deny",
            "BUDGET_RISK": "warn",
        },
    }
    return policies[policy][status]


def main() -> None:
    config = DetectorConfig(window=4, retention_window=8, max_steps=None, max_tokens=None)
    evaluator = StagnationEvaluator({"contract": "TWO_ANCHOR"})
    # The injected adapter keeps this demo deterministic and independent of
    # the optional Agent Control package/server.
    evaluator._adapter = lambda: AgentControlAdapter(  # type: ignore[attr-defined]
        contract="TWO_ANCHOR", detector_config=config
    )

    cases = {
        "progress": [
            _event(i, tool_name="write", tool_result={"ok": True}, state_before={"p": i - 1}, state_after={"p": i}, artifacts_created=[f"artifact-{i}"])
            for i in range(1, 5)
        ],
        "loop": [
            _event(i, tool_name="lookup", tool_args={"id": 1}, tool_result={"ok": False}, state_before={"p": 1}, state_after={"p": 1}, artifacts_created=[])
            for i in range(1, 5)
        ],
        "ambiguous": [
            _event(i, tool_name=f"query-{i}", tool_result={"value": i}) for i in range(1, 5)
        ],
    }
    # Each case gets a fresh evaluator state, as a real run would have a
    # distinct session key.
    output = {}
    for name, events in cases.items():
        adapter = AgentControlAdapter(contract="TWO_ANCHOR", detector_config=config)
        case_evaluator = StagnationEvaluator({"contract": "TWO_ANCHOR"})
        case_evaluator._adapter = lambda adapter=adapter: adapter  # type: ignore[attr-defined]
        result = {}
        for item in events:
            result = case_evaluator.evaluate_event(item)
        result["agent_control_action"] = _policy_action(result["status"], "strict-loop-guard")
        output[name] = result
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
