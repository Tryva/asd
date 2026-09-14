from __future__ import annotations

import sys
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from stagnation_detector.detector import DetectorConfig  # noqa: E402
from stagnation_detector.integrations.agent_control import (  # noqa: E402
    AgentControlAdapter,
    StagnationEvaluator,
    recommended_control_action,
)


def event(step: int, **fields: object) -> dict[str, object]:
    value: dict[str, object] = {
        "event_type": "tool",
        "step_id": step,
        "agent_name": "agent-a",
        "session_id": "session-a",
    }
    value.update(fields)
    return value


class AgentControlIntegrationTests(unittest.TestCase):
    def make_adapter(self, **kwargs: object) -> AgentControlAdapter:
        return AgentControlAdapter(
            contract="TWO_ANCHOR",
            detector_config=DetectorConfig(window=4, retention_window=8, max_steps=None, max_tokens=None),
            **kwargs,
        )

    def test_adapter_normalizes_agent_control_shape(self):
        adapter = self.make_adapter()
        converted = adapter.normalize(
            {
                "type": "tool",
                "step": 7,
                "name": "search",
                "input": {"query_hash": "q1"},
                "result_fingerprint": "r1",
                "state_fingerprint": "s1",
                "agent_name": "agent-a",
                "run_id": "run-a",
            }
        )
        self.assertEqual(converted.step_id, 7)
        self.assertEqual(converted.tool_name, "search")
        self.assertEqual(converted.tool_result, {"fingerprint": "r1"})
        self.assertEqual(converted.state_after, {"fingerprint": "s1"})

    def test_fingerprints_are_sufficient_without_raw_content(self):
        adapter = self.make_adapter()
        result = {}
        for step in range(1, 5):
            result = adapter.evaluate(
                event(
                    step,
                    tool_name="lookup",
                    action_fingerprint="action-1",
                    result_fingerprint="result-1",
                    state_fingerprint="state-1",
                    artifacts_created=[],
                )
            )
        self.assertEqual(result["status"], "LOOPING")
        self.assertTrue(result["evidence"])

    def test_sessions_and_agents_are_isolated(self):
        adapter = self.make_adapter()
        for step in range(1, 4):
            adapter.evaluate(event(step, tool_name="lookup", tool_result={"ok": False}, state_after={"p": 1}, artifacts_created=[]))
        other = event(1, agent_name="agent-b", session_id="session-b", tool_name="write", tool_result={"ok": True}, state_before={"p": 0}, state_after={"p": 1}, artifacts_created=["a"])
        result = adapter.evaluate(other)
        self.assertEqual(result["status"], "PROGRESSING")
        self.assertEqual(adapter.session_count, 2)
        self.assertEqual(adapter.retained_event_count, 4)

    def test_progress_stagnation_loop_and_unknown(self):
        progress = self.make_adapter()
        result = {}
        for step in range(1, 5):
            result = progress.evaluate(event(step, tool_name="write", tool_result={"ok": True}, state_before={"p": step - 1}, state_after={"p": step}, artifacts_created=[f"a-{step}"]))
        self.assertEqual(result["status"], "PROGRESSING")

        stagnation = self.make_adapter()
        result = {}
        for step in range(1, 5):
            result = stagnation.evaluate(event(step, tool_name="create", tool_args={"attempt": step}, error_type="HTTPError", error_message="400 invalid", state_after={"p": 1}, artifacts_created=[]))
        self.assertEqual(result["status"], "STAGNATING")

        loop = self.make_adapter()
        result = {}
        for step in range(1, 5):
            result = loop.evaluate(event(step, tool_name="lookup", tool_args={"id": 1}, tool_result={"ok": False}, state_after={"p": 1}, artifacts_created=[]))
        self.assertEqual(result["status"], "LOOPING")

        unknown = self.make_adapter()
        result = {}
        for step in range(1, 5):
            result = unknown.evaluate(event(step, tool_name=f"query-{step}", tool_result={"value": step}))
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["evidence_contract_satisfied"])

    def test_conflict_and_missing_identity_are_unknown(self):
        adapter = self.make_adapter()
        result = {}
        for step in range(1, 5):
            result = adapter.evaluate(event(step, tool_name="lookup", tool_args={"id": 1}, tool_result={"value": step}, error_type="TimeoutError", state_after={"p": 1}, artifacts_created=[], metadata={"verified_observation": True}))
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertIn("conflict", result["reason"])
        missing = adapter.evaluate({"event_type": "tool", "step_id": 1, "tool_name": "lookup", "tool_result": {"ok": True}})
        self.assertEqual(missing["status"], "UNKNOWN")

    def test_unknown_never_maps_to_deny(self):
        self.assertEqual(recommended_control_action("UNKNOWN"), "LOG")
        evaluator = StagnationEvaluator({"contract": "TWO_ANCHOR", "trigger_statuses": ("UNKNOWN",)})
        result = evaluator.evaluate_event({"event_type": "tool", "step_id": 1, "tool_name": "lookup", "tool_result": {"ok": True}}, session_key="agent/session")
        self.assertTrue(result["matched"])
        self.assertNotEqual(recommended_control_action(result["status"]), "DENY")

    def test_bounded_state_and_ttl_cleanup(self):
        now = [0.0]
        adapter = self.make_adapter(max_sessions=2, session_ttl_seconds=10, clock=lambda: now[0])
        for index in range(3):
            adapter.evaluate(event(1, agent_name="agent", session_id=f"session-{index}", tool_name="x", tool_result={"i": index}, state_after={"i": index}))
        self.assertEqual(adapter.session_count, 2)
        self.assertLessEqual(adapter.retained_event_count, 2 * 8)
        now[0] = 11.0
        adapter.evaluate(event(1, agent_name="agent", session_id="fresh", tool_name="x", tool_result={"i": 4}, state_after={"i": 4}))
        self.assertEqual(adapter.session_count, 1)

    def test_deterministic_replay(self):
        events = [event(i, tool_name="lookup", tool_args={"id": 1}, tool_result={"ok": False}, state_after={"p": 1}, artifacts_created=[]) for i in range(1, 5)]
        def replay() -> dict[str, object]:
            adapter = self.make_adapter()
            result: dict[str, object] = {}
            for item in events:
                result = adapter.evaluate(item)
            return result
        self.assertEqual(replay(), replay())

    def test_upstream_contract_entry_point_and_context_hook(self):
        pyproject = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('agent_control.evaluators', pyproject)
        self.assertIn('stagnation_detector.integrations.agent_control:StagnationEvaluator', pyproject)
        self.assertTrue(hasattr(StagnationEvaluator, "evaluate_with_context"))


if __name__ == "__main__":
    unittest.main()
