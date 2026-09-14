from __future__ import annotations

import unittest

from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from stagnation_detector.detector import DetectorConfig, StagnationDetector, detect_stagnation
from stagnation_detector.adapters import AutoGenAdapter, GenericJSONAdapter, LangChainAdapter, LangGraphAdapter, OpenAIAgentsAdapter, PydanticAIAdapter
from anchor_benchmark import developer_progress_key
from stagnation_detector.anchor_enrichment import apply_progress_key, convert_events, mode_events
from stagnation_detector.cross_framework_dataset import cross_framework_traces
from stagnation_detector.evidence_contract import CONTRACTS, evaluate_contract, telemetry_class, trusted_progress_anchor
from stagnation_detector.events import EventValidationError, TrajectoryEvent
from stagnation_detector.fixtures import benchmark_fixtures
from stagnation_detector.heldout_dataset import heldout_traces
from stagnation_detector.public_trace_dataset import public_trace_traces


def event(step: int, **kwargs):
    value = {"event_type": "tool", "step_id": step}
    value.update(kwargs)
    return value


class DetectorTests(unittest.TestCase):
    def test_bounded_retention_and_full_history_debug_mode(self):
        config = DetectorConfig(window=4, retention_window=8, max_steps=None, max_tokens=None)
        detector = StagnationDetector(config)
        for index in range(100):
            detector.observe(event(index, tool_name=f"tool-{index}", tool_result={"index": index}))
        self.assertEqual(len(detector.events), 8)
        self.assertEqual(detector.events[0].step_id, 92)
        debug = StagnationDetector(DetectorConfig(window=4, retention_window=8, retain_raw_events=True, max_steps=None, max_tokens=None))
        for index in range(100):
            debug.observe(event(index, tool_name=f"tool-{index}", tool_result={"index": index}))
        self.assertEqual(len(debug.events), 100)

    def test_cycle_detection_survives_eviction(self):
        config = DetectorConfig(window=4, retention_window=8, max_steps=None, max_tokens=None)
        detector = StagnationDetector(config)
        for index in range(12):
            detector.observe(event(index, tool_name=f"unique-{index}", tool_result={"index": index}, state_after={"phase": "same"}))
        for index, name in enumerate(("a", "b", "a", "b"), 12):
            result = detector.observe(event(index, tool_name=name, tool_result=name, state_after={"phase": "same"}))
        self.assertEqual(result.status, "LOOPING")
        self.assertIn("CYCLE_DETECTION", result.signals)

    def test_repeated_error_and_exact_repetition_survive_eviction(self):
        error_config = DetectorConfig(window=4, retention_window=8, max_steps=None, max_tokens=None)
        error_detector = StagnationDetector(error_config)
        for index in range(12):
            error_detector.observe(event(index, tool_name=f"unique-{index}", tool_result={"index": index}, state_after={"phase": "same"}))
        for index in range(12, 16):
            result = error_detector.observe(event(index, tool_name="lookup", tool_args={"attempt": index}, error_type="TimeoutError", state_after={"phase": "same"}, artifacts_created=[]))
        self.assertEqual(result.status, "STAGNATING")
        self.assertIn("REPEATED_ERROR_FAMILY", result.signals)

        repeat_detector = StagnationDetector(error_config)
        for index in range(12):
            repeat_detector.observe(event(index, tool_name=f"unique-{index}", tool_result={"index": index}, state_after={"phase": "same"}))
        for index in range(12, 16):
            result = repeat_detector.observe(event(index, tool_name="lookup", tool_args={"id": 1}, tool_result={"ok": True}, state_after={"phase": "same"}, artifacts_created=[]))
        self.assertEqual(result.status, "LOOPING")
        self.assertIn("EXACT_REPEAT", result.signals)

    def test_unknown_and_explanation_are_preserved_after_rollover(self):
        unknown = StagnationDetector(DetectorConfig(window=4, retention_window=8, max_steps=None, max_tokens=None))
        for index in range(100):
            result = unknown.observe(event(index, tool_name="query", tool_result={"unique": index}))
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.evidence_strength, "INSUFFICIENT")

        explainable = StagnationDetector(DetectorConfig(window=4, retention_window=8, max_steps=None, max_tokens=None))
        for index in range(12):
            explainable.observe(event(index, tool_name=f"unique-{index}", tool_result={"index": index}, state_after={"phase": "same"}))
        for index in range(12, 16):
            result = explainable.observe(event(index, tool_name="lookup", tool_args={"attempt": index}, error_type="TimeoutError", state_after={"phase": "same"}, artifacts_created=[]))
        self.assertEqual(result.status, "STAGNATING")
        self.assertTrue(any("same normalized error family" in item for item in result.evidence))

    def test_no_false_progress_after_rollover(self):
        detector = StagnationDetector(DetectorConfig(window=4, retention_window=8, max_steps=None, max_tokens=None))
        for index in range(12):
            detector.observe(event(index, tool_name=f"unique-{index}", tool_result={"index": index}, state_after={"phase": "same"}, artifacts_created=[]))
        for index in range(12, 16):
            result = detector.observe(event(index, tool_name="lookup", tool_args={"id": 1}, error_type="HTTPError", state_after={"phase": "same"}, artifacts_created=[]))
        self.assertNotEqual(result.status, "PROGRESSING")

    def test_trusted_progress_evidence_persists_without_raw_history(self):
        detector = StagnationDetector(DetectorConfig(window=4, retention_window=8, max_steps=None, max_tokens=None))
        detector.observe(event(1, tool_name="write", tool_result={"ok": True}, state_before={"p": 0}, state_after={"p": 1}, artifacts_created=["a-1"]))
        for index in range(2, 102):
            result = detector.observe(event(index, tool_name=f"query-{index}", tool_result={"index": index}))
        self.assertEqual(result.status, "PROGRESSING")
        self.assertTrue(any("NEW_ARTIFACT" in item for item in result.evidence))

    def test_incremental_replay_is_deterministic(self):
        events = [event(index, tool_name="lookup", error_type="TimeoutError", state_after={"phase": "same"}, artifacts_created=[]) for index in range(100)]
        config = DetectorConfig(window=4, retention_window=16, max_steps=None, max_tokens=None)
        first_detector = StagnationDetector(config)
        first = [first_detector.observe(item).to_mapping() for item in events]
        replay = StagnationDetector(config)
        second = [replay.observe(item).to_mapping() for item in events]
        self.assertEqual(first, second)

    def test_ten_thousand_event_smoke_and_memory_bound(self):
        detector = StagnationDetector(DetectorConfig(window=4, retention_window=16, max_steps=None, max_tokens=None))
        for index in range(10_000):
            detector.observe(event(index, tool_name=f"tool-{index}", tool_result={"index": index}))
        self.assertEqual(len(detector.events), 16)
        self.assertEqual(detector.status().status, "UNKNOWN")

    def test_retention_window_must_cover_detection_window(self):
        with self.assertRaises(ValueError):
            DetectorConfig(window=8, retention_window=4)

    def test_missing_fields_remain_missing(self):
        parsed = TrajectoryEvent.from_mapping({"event_type": "model_output"})
        self.assertIsNone(parsed.state_after)
        self.assertIsNone(parsed.token_delta)

    def test_malformed_event_is_rejected(self):
        with self.assertRaises(EventValidationError):
            TrajectoryEvent.from_mapping({"event_type": ""})
        with self.assertRaises(EventValidationError):
            TrajectoryEvent.from_mapping({"event_type": "tool", "token_delta": "unknown"})

    def test_exact_repeat_is_looping_with_evidence(self):
        events = [event(i, tool_name="lookup", tool_args={"id": 1}, tool_result=None, error_type="TimeoutError", state_before={"p": 1}, state_after={"p": 1}, artifacts_created=[]) for i in range(4)]
        result = detect_stagnation(events)
        self.assertEqual(result.status, "LOOPING")
        self.assertTrue(result.evidence)
        self.assertIn("EXACT_REPEAT", result.signals)

    def test_ab_cycle_is_looping(self):
        events = [event(i, tool_name=name, tool_args={}, tool_result=name, state_before={"p": name}, state_after={"p": name}) for i, name in enumerate(["a", "b", "a", "b"], 1)]
        self.assertEqual(detect_stagnation(events).status, "LOOPING")

    def test_legitimate_repeated_tool_with_artifacts_progresses(self):
        events = [event(i, tool_name="read", tool_args={"file": i}, tool_result={"ok": True}, state_before={"p": i - 1}, state_after={"p": i}, artifacts_created=[f"a-{i}"]) for i in range(1, 5)]
        self.assertEqual(detect_stagnation(events).status, "PROGRESSING")

    def test_transient_retry_eventually_progresses(self):
        events = [event(1, tool_name="fetch", tool_args={"id": 1}, error_type="TimeoutError", error_message="timeout", state_before={"p": 1}, state_after={"p": 1}, artifacts_created=[]), event(2, tool_name="fetch", tool_args={"id": 1}, tool_result={"ok": True}, state_before={"p": 1}, state_after={"p": 2}, artifacts_created=["r-1"])]
        self.assertEqual(detect_stagnation(events).status, "PROGRESSING")

    def test_permanent_error_stagnates(self):
        events = [event(i, tool_name="create", tool_args={"i": i}, error_type="HTTPError", error_message=f"400 invalid {i}", state_before={"p": 1}, state_after={"p": 1}, artifacts_created=[]) for i in range(4)]
        self.assertEqual(detect_stagnation(events).status, "STAGNATING")

    def test_missing_state_is_unknown(self):
        events = [event(i, tool_name="query", tool_args={"i": i}, tool_result={"text": f"v{i}"}) for i in range(4)]
        self.assertEqual(detect_stagnation(events).status, "UNKNOWN")

    def test_conflicting_signals_are_unknown(self):
        events = [event(i, tool_name="lookup", tool_args={"id": 1}, tool_result={"text": i}, error_type="TimeoutError", error_message=f"timeout {i}", state_before={"p": 1}, state_after={"p": 1}, artifacts_created=[], metadata={"verified_observation": True}) for i in range(4)]
        self.assertEqual(detect_stagnation(events).status, "UNKNOWN")

    def test_context_growth_without_progress_stagnates(self):
        events = [event(i, tool_name="reason", tool_args={"i": i}, state_before={"p": 1}, state_after={"p": 1}, artifacts_created=[], token_delta=20, context_size=i * 100) for i in range(1, 5)]
        self.assertEqual(detect_stagnation(events).status, "STAGNATING")

    def test_budget_risk(self):
        events = [event(i, tool_name="reason", tool_args={"i": i}, state_before={"p": 1}, state_after={"p": 1}, artifacts_created=[], token_delta=100) for i in range(1, 5)]
        result = detect_stagnation(events, DetectorConfig(max_tokens=400, max_steps=20))
        self.assertEqual(result.status, "BUDGET_RISK")

    def test_fixture_count_and_expected_categories(self):
        fixtures = benchmark_fixtures()
        self.assertEqual(len(fixtures), 22)
        self.assertEqual(sum(f["fixture_id"].startswith("S") for f in fixtures), 10)
        self.assertEqual(sum(f["fixture_id"].startswith("L") for f in fixtures), 7)
        self.assertEqual(sum(f["fixture_id"].startswith("A") for f in fixtures), 5)

    def test_deterministic_reproducibility(self):
        fixture = benchmark_fixtures()[3]
        first = detect_stagnation(fixture["trajectory_events"]).to_mapping()
        second = detect_stagnation(fixture["trajectory_events"]).to_mapping()
        self.assertEqual(first, second)

    def test_generic_adapter_preserves_normalized_event(self):
        converted = GenericJSONAdapter().convert({"event_type": "tool", "tool_name": "search", "step_id": 1})
        self.assertEqual(converted.tool_name, "search")
        self.assertEqual(converted.step_id, 1)

    def test_langgraph_adapter_is_thin_and_dependency_free(self):
        converted = LangGraphAdapter().convert({"event": "on_tool_end", "name": "search", "data": {"output": {"ok": True}, "state_after": {"n": 1}}, "metadata": {"langgraph_step": 2}})
        self.assertEqual(converted.event_type, "on_tool_end")
        self.assertEqual(converted.tool_name, "search")
        self.assertEqual(converted.state_after, {"n": 1})
        self.assertEqual(converted.step_id, 2)

    def test_heldout_dataset_is_separate_from_icm07_fixtures(self):
        traces = heldout_traces()
        self.assertEqual(len(traces), 30)
        self.assertEqual(sum(t["human_label"] in {"STAGNATING", "LOOPING", "BUDGET_RISK"} for t in traces), 10)
        self.assertEqual(sum(t["human_label"] == "PROGRESSING" for t in traces), 10)
        self.assertEqual(sum(t["human_label"] == "UNKNOWN" for t in traces), 10)
        self.assertNotEqual(traces[0]["trace_id"], benchmark_fixtures()[0]["fixture_id"])

    def test_two_anchor_requires_trusted_anchor_for_hard_stop(self):
        events = [event(i, tool_name="lookup", tool_result=None, error_type="HTTPError", error_message="400 invalid", state_after={"phase": "request"}) for i in range(1, 5)]
        result = evaluate_contract(events, "TWO_ANCHOR")
        self.assertIn(result["decision"], {"STAGNATING", "LOOPING"})
        self.assertTrue(result["evidence_contract_satisfied"])
        self.assertIn("decision_reason", result)
        sparse = [event(i, tool_name="lookup", tool_result={"id": 1}) for i in range(1, 5)]
        self.assertEqual(evaluate_contract(sparse, "TWO_ANCHOR")["decision"], "UNKNOWN")

    def test_contract_output_is_auditable_and_deterministic(self):
        trace = next(item for item in cross_framework_traces() if item["trace_id"] == "B01")
        converted = [LangGraphAdapter().convert(raw) for raw in trace["raw_events"]]
        first = evaluate_contract(converted, "TWO_ANCHOR")
        second = evaluate_contract(converted, "TWO_ANCHOR")
        self.assertEqual(first, second)
        for field in ("decision", "evidence_used", "missing_evidence", "evidence_contract_satisfied", "decision_reason"):
            self.assertIn(field, first)

    def test_cross_framework_adapters_are_thin_and_dependency_free(self):
        self.assertEqual(OpenAIAgentsAdapter().convert({"type": "tool_output", "step_id": 1, "tool": "x", "result": {"ok": True}}).tool_name, "x")
        self.assertEqual(PydanticAIAdapter().convert({"kind": "tool_result", "step_id": 1, "tool": "x", "result": {"ok": True}}).event_type, "tool_result")
        self.assertEqual(AutoGenAdapter().convert({"kind": "message", "step_id": 1, "tool": "agent", "output": {"ok": True}}).tool_name, "agent")
        self.assertEqual(LangChainAdapter().convert({"event_type": "chain_step", "step_id": 1, "name": "retrieve", "output": {"ok": True}}).tool_name, "retrieve")

    def test_all_contracts_preserve_exact_decision_states(self):
        events = [event(i, tool_name="x", tool_result={"ok": False}, state_after={"phase": "same"}) for i in range(1, 5)]
        self.assertTrue(set(CONTRACTS))
        for contract in CONTRACTS:
            self.assertIn(evaluate_contract(events, contract)["decision"], {"PROGRESSING", "STAGNATING", "LOOPING", "BUDGET_RISK", "UNKNOWN"})

    def test_telemetry_degrades_to_unknown_when_anchors_and_results_are_removed(self):
        complete = [TrajectoryEvent.from_mapping(event(i, tool_name="x", tool_result={"ok": False}, state_after={"phase": "same"}, artifacts_created=["a"], metadata={"checkpoint_id": "cp"})) for i in range(1, 5)]
        self.assertEqual(telemetry_class(complete), "FULL")
        sparse = [TrajectoryEvent.from_mapping(event(i, tool_name="x")) for i in range(1, 5)]
        self.assertEqual(telemetry_class(sparse), "INSUFFICIENT")

    def test_adapter_enrichment_is_policy_free_and_extracts_native_anchor(self):
        trace = {"adapter": "langgraph-compat", "raw_events": [{"event": "checkpoint", "name": "node", "step": 1, "data": {"output": {"ok": False}, "state_after": {"phase": "same"}, "checkpoint_id": "cp-1"}, "metadata": {}}]}
        events = convert_events(trace, adapter_enriched=True)
        self.assertEqual(events[0].metadata["checkpoint_id"], "cp-1")
        self.assertEqual(events[0].metadata["anchor_source"], "adapter-native")

    def test_run_and_trace_ids_are_not_auto_trusted_as_progress(self):
        trace = {"adapter": "openai-agents", "raw_events": [{"type": "generation", "step_id": i, "tool": "agent", "result": {"text": "same"}, "metadata": {"trace_id": f"t{i}", "span_id": f"s{i}"}} for i in range(1, 5)]}
        events = convert_events(trace, adapter_enriched=True)
        self.assertFalse(telemetry_class(events) == "FULL")
        self.assertFalse(trusted_progress_anchor(events).present)

    def test_user_key_validation_surfaces_bad_keys(self):
        events = [TrajectoryEvent.from_mapping(event(i, tool_name="x", tool_result={"ok": False})) for i in range(1, 5)]
        _, changing = apply_progress_key(events, lambda item: item.step_id)
        self.assertIn("ALWAYS_CHANGING_PROGRESS_KEY", changing)
        _, unstable = apply_progress_key(events, lambda item: object())
        self.assertIn("UNSTABLE_PROGRESS_KEY", unstable)
        _, constant = apply_progress_key(events, lambda item: "same")
        self.assertIn("CONSTANT_PROGRESS_KEY", constant)

    def test_all_four_modes_are_available_without_external_services(self):
        trace = next(item for item in public_trace_traces() if item["trace_id"] == "C01")
        for mode in ("TWO_ANCHOR_NO_ENRICHMENT", "TWO_ANCHOR_ADAPTER_ENRICHED", "TWO_ANCHOR_USER_PROGRESS_KEY", "TWO_ANCHOR_ADAPTER_PLUS_USER_KEY"):
            needs_user_key = mode in {"TWO_ANCHOR_USER_PROGRESS_KEY", "TWO_ANCHOR_ADAPTER_PLUS_USER_KEY"}
            events, _ = mode_events(trace, mode, developer_progress_key if needs_user_key else None)
            self.assertEqual(len(events), len(trace["raw_events"]))

    def test_set_c_is_separate_and_has_twenty_public_traces(self):
        traces = public_trace_traces()
        self.assertEqual(len(traces), 20)
        self.assertEqual(len({trace["trace_id"] for trace in traces}), 20)
        self.assertEqual(sum(trace["human_label"] in {"STAGNATING", "LOOPING"} for trace in traces), 12)
        self.assertTrue(all(trace["provenance"] == "independent_public_documentation" for trace in traces))


if __name__ == "__main__":
    unittest.main()
