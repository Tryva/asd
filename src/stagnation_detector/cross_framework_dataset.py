"""SET_B: new source-anchored cross-framework contract traces.

These are normalized reconstruction fixtures, kept separate from ICM 08.  The
framework names describe the event shapes exercised by each thin adapter; the
contract remains framework-neutral.
"""

from __future__ import annotations

from typing import Any


def _event(step: int, **kwargs: Any) -> dict[str, Any]:
    value = {"event_type": "event", "step_id": step, "timestamp": float(step)}
    value.update(kwargs)
    return value


def _langgraph(step: int, node: str, **kwargs: Any) -> dict[str, Any]:
    data = {"output": {"node": node}, **kwargs}
    return {"event": "on_tool_end", "name": node, "step": step, "timestamp": float(step), "data": data, "metadata": {"langgraph_step": step}}


def _record(trace_id: str, framework: str, adapter: str, source: str, label: str, rationale: str, events: list[dict[str, Any]], completeness: str = "complete") -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "framework": framework,
        "adapter": adapter,
        "source": source,
        "raw_trace_reference": source,
        "workflow_type": "CROSS_FRAMEWORK",
        "human_label": label,
        "label_rationale": rationale,
        "raw_events": events,
        "trace_completeness": completeness,
    }


def cross_framework_traces() -> list[dict[str, Any]]:
    langgraph = "https://docs.langchain.com/oss/python/langgraph/graph-api"
    langchain = "https://python.langchain.com/docs/concepts/callbacks/"
    openai = "https://openai.github.io/openai-agents-python/running_agents/"
    pydantic = "https://ai.pydantic.dev/agents/"
    autogen = "https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/termination.html"
    traces: list[dict[str, Any]] = []

    traces.append(_record("B01", "LangGraph", "langgraph-compat", langgraph, "LOOPING", "A-B graph cycle repeats with a stable structured state and no committed progress anchor.", [_langgraph(i, "node_a" if i % 2 else "node_b", state_before={"phase": "A" if i % 2 else "B"}, state_after={"phase": "A" if i % 2 else "B"}, error={"type": "GraphRecursion", "message": "recursion limit"}) for i in range(1, 7)]))
    traces.append(_record("B02", "LangChain", "langchain-compat", langchain, "STAGNATING", "The same permanent protocol failure repeats while the structured state remains at request.", [_event(i, event="on_tool_end", name="invoke", output={"ok": False}, error_type="HTTPError", error_message="400 invalid request", state_before={"phase": "request"}, state_after={"phase": "request"}) for i in range(1, 5)]))
    traces.append(_record("B03", "OpenAI Agents", "openai-agents", openai, "STAGNATING", "Repeated tool failure and unchanged verified state provide two independent evidence types.", [_event(i, type="tool_error", tool="lookup", input={"id": 7}, result=None, error_type="TimeoutError", error_message="upstream timeout", state_after={"phase": "lookup"}, metadata={"checkpoint_id": "cp-0"}) for i in range(1, 5)]))
    traces.append(_record("B04", "PydanticAI", "pydantic-ai", pydantic, "LOOPING", "The normalized tool/result pair repeats exactly with an unchanged state fingerprint.", [_event(i, kind="tool_call", tool="validate", input={"field": "email"}, result={"valid": False}, state_after={"phase": "validate"}) for i in range(1, 5)]))
    traces.append(_record("B05", "AutoGen", "autogen", autogen, "STAGNATING", "A repeated agent error is paired with an unchanged externally identified checkpoint.", [_event(i, kind="message", tool="reviewer", output=None, error_type="PolicyError", error_message="approval unavailable", state_after={"phase": "review"}, metadata={"state_version": "review-0"}) for i in range(1, 5)]))

    traces.append(_record("B06", "LangGraph", "langgraph-compat", langgraph, "PROGRESSING", "Each graph step commits a new artifact and advances state.", [_langgraph(i, "write", output={"ok": True}, state_before={"files": i - 1}, state_after={"files": i}, artifacts_created=[f"patch-{i}"]) for i in range(1, 5)]))
    traces.append(_record("B07", "LangChain", "langchain-compat", langchain, "PROGRESSING", "Retrieval results and a monotonic document count advance on every event.", [_event(i, event="chain_step", name="retrieve", output={"document_id": i}, state_before={"documents": i - 1}, state_after={"documents": i}, artifacts_created=[f"doc-{i}"]) for i in range(1, 5)]))
    traces.append(_record("B08", "OpenAI Agents", "openai-agents", openai, "PROGRESSING", "A failed call is followed by a verified state change and an artifact.", [_event(1, type="tool_error", tool="compile", input={"file": "a.py"}, result=None, error_type="TimeoutError", error_message="transient", state_after={"phase": "compile"}), _event(2, type="tool_output", tool="compile", input={"file": "a.py"}, result={"tests": "pass"}, state_before={"phase": "compile"}, state_after={"phase": "tested"}, artifacts_created=["test-report"], metadata={"verified_observation": True})]))
    traces.append(_record("B09", "PydanticAI", "pydantic-ai", pydantic, "PROGRESSING", "Validation retry changes the state and produces a verified output artifact.", [_event(1, kind="retry", tool="parse", result=None, error_type="ValidationError", error_message="missing field", state_after={"phase": "parse"}), _event(2, kind="tool_result", tool="parse", result={"ok": True}, state_before={"phase": "parse"}, state_after={"phase": "complete"}, artifacts_created=["validated-record"], metadata={"verified_observation": True})]))
    traces.append(_record("B10", "AutoGen", "autogen", autogen, "PROGRESSING", "Agent handoff, draft artifact, and approval create a visible terminating path.", [_event(1, kind="message", tool="researcher", output={"handoff": True}, state_before={"phase": "research"}, state_after={"phase": "handoff"}), _event(2, kind="message", tool="writer", output={"draft": True}, state_before={"phase": "handoff"}, state_after={"phase": "draft"}, artifacts_created=["draft"]), _event(3, kind="termination", tool="reviewer", output={"approved": True}, state_before={"phase": "draft"}, state_after={"phase": "done"})]))

    traces.append(_record("B11", "LangGraph", "langgraph-compat", langgraph, "UNKNOWN", "Repeated external timeouts have no receipt or state-after anchor, so remote completion is unknowable.", [_langgraph(i, "external", output={"status": "timeout"}) for i in range(1, 5)], "partial"))
    traces.append(_record("B12", "LangChain", "langchain-compat", langchain, "UNKNOWN", "Novel retrieved text without a trusted state or artifact anchor does not establish useful progress.", [_event(i, event="chain_step", name="retrieve", output={"text": f"variant-{i}"}, context_size=100 * i, token_delta=20) for i in range(1, 5)], "partial"))
    traces.append(_record("B13", "OpenAI Agents", "openai-agents", openai, "UNKNOWN", "Repeated tool output lacks a postback/state anchor, so causal completion is unavailable.", [_event(i, type="tool_output", tool="lookup", result={"id": 9}, metadata={"postback": None}) for i in range(1, 5)], "sparse"))
    traces.append(_record("B14", "PydanticAI", "pydantic-ai", pydantic, "UNKNOWN", "Schema failures repeat but intended recovery semantics and external state are absent.", [_event(i, kind="tool_schema_error", tool="dynamic", error_type="SchemaError", error_message=f"field variant {i}") for i in range(1, 5)], "sparse"))
    traces.append(_record("B15", "AutoGen", "autogen", autogen, "UNKNOWN", "Messages vary in wording but no deterministic task or checkpoint outcome is visible.", [_event(i, kind="message", tool="agent_turn", output={"text": f"new wording {i}"}) for i in range(1, 5)], "sparse"))
    return traces
