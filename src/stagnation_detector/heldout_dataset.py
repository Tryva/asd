"""Manually labelled held-out traces derived from public reproductions/examples.

These are not the ICM 07 fixtures. They preserve source references and label
uncertainty so the benchmark can distinguish public evidence from raw logs.
"""

from __future__ import annotations

from typing import Any


def _generic(step: int, **kwargs: Any) -> dict[str, Any]:
    value = {"event_type": "tool", "step_id": step, "timestamp": float(step)}
    value.update(kwargs)
    return value


def _langgraph(step: int, name: str, **kwargs: Any) -> dict[str, Any]:
    metadata = dict(kwargs.pop("metadata", {}))
    metadata.setdefault("langgraph_step", step)
    return {"event": "on_tool_end", "name": name, "timestamp": float(step), "data": kwargs, "metadata": metadata}


def _trace(
    trace_id: str,
    source: str,
    framework: str,
    workflow_type: str,
    adapter: str,
    events: list[dict[str, Any]],
    label: str,
    rationale: str,
    progress: list[str],
    stagnation: list[str],
    missing: list[str],
    confidence: str,
    completeness: str,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "source": source,
        "framework": framework,
        "workflow_type": workflow_type,
        "adapter": adapter,
        "raw_trace_reference": source,
        "raw_events": events,
        "human_label": label,
        "label_rationale": rationale,
        "observable_progress": progress,
        "observable_stagnation": stagnation,
        "missing_evidence": missing,
        "confidence": confidence,
        "trace_completeness": completeness,
    }


def heldout_traces() -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    langchain_400 = "https://github.com/langchain-ai/langchainjs/issues/11339"
    anthropic_tool = "https://github.com/anthropics/anthropic-sdk-python/issues/1536"
    openai_tool = "https://github.com/openai/openai-agents-python/issues/1061"
    pydantic_retry = "https://github.com/pydantic/pydantic-ai/issues/4557"
    openai_empty = "https://github.com/openai/openai-python/issues/2870"
    langfuse_context = "https://github.com/langfuse/langfuse/issues/12873"
    agno_governance = "https://github.com/agno-agi/agno/issues/9151"
    llama_fields = "https://github.com/run-llama/llama_index/issues/20386"
    langgraph_recursion = "https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT"
    autogen_termination = "https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/termination.html"

    # 10 stagnation/loop traces: public issue reproductions or explicit public mechanisms.
    traces.append(_trace("H01", langchain_400, "LangChain JS", "TOOL_BUSINESS", "generic-json", [_generic(i, tool_name="chat", tool_args={"prompt": "large"}, error_type="HTTPError", error_message=f"400 context too large attempt {i}", state_before={"phase": "request"}, state_after={"phase": "request"}, artifacts_created=[]) for i in range(1, 5)], "STAGNATING", "deterministic client error is retried without a state change", [], ["permanent 400 retry"], [], "HIGH", "complete"))
    traces.append(_trace("H02", anthropic_tool, "Anthropic SDK", "TOOL_BUSINESS", "generic-json", [_generic(i, tool_name="get_weather", tool_args={"city": "Paris"}, tool_result={"temperature": 18}, metadata={"tool_result_recorded": False}) for i in range(1, 5)], "LOOPING", "the public reproduction repeats a tool request because the result message is missing", [], ["missing tool result"], ["state_after", "artifacts_created"], "HIGH", "sparse"))
    traces.append(_trace("H03", openai_tool, "OpenAI Agents", "TOOL_BUSINESS", "generic-json", [_generic(i, event_type="tool_call", tool_name="lookup", tool_args={"id": 9}, tool_result={"id": 9}, metadata={"tool_output_posted": False}) for i in range(1, 5)], "LOOPING", "production issue reports a tool completion without the required output post", [], ["tool output propagation"], ["state_after"], "HIGH", "sparse"))
    traces.append(_trace("H04", pydantic_retry, "PydanticAI", "CODING_DEBUGGING", "generic-json", [_generic(i, event_type="model_retry", tool_name="validate_output", tool_args={"attempt": i}, tool_result={"thinking_only": True}, error_type="ModelRetry", error_message="output text unavailable") for i in range(1, 5)], "STAGNATING", "retry consumes turns while the usable output remains absent", [], ["thinking-only retry"], ["state_after", "artifacts_created"], "MEDIUM", "sparse"))
    traces.append(_trace("H05", openai_empty, "OpenAI SDK", "CODING_DEBUGGING", "generic-json", [_generic(i, event_type="model_result", tool_result={"status": "completed", "output": None}, metadata={"response_status": "completed"}) for i in range(1, 5)], "STAGNATING", "completed status repeats without a usable output", [], ["empty output"], ["state_after", "tool_name"], "MEDIUM", "sparse"))
    traces.append(_trace("H06", langfuse_context, "Langfuse", "RESEARCH_SEARCH", "generic-json", [_generic(i, event_type="context_update", tool_name="compress", tool_result={"summary": f"variant-{i}"}, context_size=100 * i, token_delta=40, metadata={"session_boundary_uncertain": True}) for i in range(1, 5)], "STAGNATING", "context grows across a questionable session boundary without verified task progress", [], ["context/session drift"], ["state_after", "artifacts_created"], "MEDIUM", "partial"))
    traces.append(_trace("H07", agno_governance, "Agno", "TOOL_BUSINESS", "generic-json", [_generic(i, event_type="governance_check", tool_name="authorize", tool_args={"action": "same"}, tool_result={"allowed": False}, error_type="PolicyError", error_message=f"authorization unresolved {i}", state_before={"phase": "authorize"}, state_after={"phase": "authorize"}, artifacts_created=[]) for i in range(1, 5)], "STAGNATING", "authorization loop has no state or policy resolution", [], ["governance loop"], [], "MEDIUM", "complete"))
    traces.append(_trace("H08", llama_fields, "LlamaIndex", "RESEARCH_SEARCH", "generic-json", [_generic(i, event_type="tool_call", tool_name="retrieve", tool_args={"query": f"q{i}"}, tool_result={"trusted": False}, state_before={"phase": "retrieve"}, state_after={"phase": "retrieve"}, artifacts_created=[]) for i in range(1, 5)], "STAGNATING", "arguments vary but trusted/deterministic usable state never advances", [], ["untrusted result"], [], "MEDIUM", "complete"))
    traces.append(_trace("H09", langgraph_recursion, "LangGraph", "MULTI_AGENT", "langgraph-compat", [_langgraph(i, "node_a" if i % 2 else "node_b", output={"phase": "A" if i % 2 else "B"}, state_before={"phase": "A" if i % 2 else "B"}, state_after={"phase": "A" if i % 2 else "B"}) for i in range(1, 7)], "LOOPING", "documented recursion-limit failure is a repeating graph cycle", ["local state alternates"], ["cycle"], [], "HIGH", "complete"))
    traces.append(_trace("H10", autogen_termination, "AutoGen", "MULTI_AGENT", "generic-json", [_generic(i, event_type="message", tool_name="agent_turn", tool_result={"text": f"same plan {i}"}, state_before={"phase": "plan"}, state_after={"phase": "plan"}, artifacts_created=[]) for i in range(1, 5)], "STAGNATING", "a reproducible team with only a generic message limit can repeat a plan without a state transition", [], ["no termination predicate for progress"], [], "LOW", "complete"))

    # 10 legitimate long-run traces from documented framework/runtime mechanisms.
    traces.append(_trace("L11", "https://docs.langchain.com/oss/python/langgraph/persistence", "LangGraph", "CODING_DEBUGGING", "langgraph-compat", [_langgraph(i, "write_file", output={"file": f"file-{i}", "ok": True}, state_before={"files": i - 1}, state_after={"files": i}, artifacts_created=[f"patch-{i}"]) for i in range(1, 6)], "PROGRESSING", "checkpointed file work creates a new artifact per step", ["artifact", "state transition", "checkpoint"], [], [], "HIGH", "complete"))
    traces.append(_trace("L12", "https://docs.langchain.com/oss/python/langgraph/graph-api", "LangGraph", "RESEARCH_SEARCH", "langgraph-compat", [_langgraph(i, "search", output={"evidence": i}, state_before={"count": i - 1}, state_after={"count": i}, artifacts_created=[f"source-{i}"], metadata={"checkpoint_advanced": True}) for i in range(1, 5)], "PROGRESSING", "new verified evidence and checkpoints advance", ["artifact", "checkpoint"], [], [], "HIGH", "complete"))
    traces.append(_trace("L13", "https://openai.github.io/openai-agents-python/running_agents/", "OpenAI Agents", "TOOL_BUSINESS", "generic-json", [_generic(1, event_type="tool_call", tool_name="lookup", tool_args={"id": 1}, tool_result={"id": 1}, state_before={"phase": "lookup"}, state_after={"phase": "lookup"}), _generic(2, event_type="tool_call", tool_name="save", tool_args={"id": 1}, tool_result={"ok": True}, state_before={"phase": "lookup"}, state_after={"phase": "saved"}, artifacts_created=["record-1"]), _generic(3, event_type="final", tool_result={"answer": "done"}, state_before={"phase": "saved"}, state_after={"phase": "done"})], "PROGRESSING", "tool result, state advancement, artifact, and final output are visible", ["state transition", "artifact"], [], [], "HIGH", "complete"))
    traces.append(_trace("L14", "https://openai.github.io/openai-agents-python/guardrails/", "OpenAI Agents", "TOOL_BUSINESS", "generic-json", [_generic(i, event_type="guardrail_pass", tool_name="check", tool_result={"ok": True}, state_before={"phase": i - 1}, state_after={"phase": i}, metadata={"verified_observation": True}) for i in range(1, 5)], "PROGRESSING", "guardrail checks advance a monotonic phase", ["verified observation", "state transition"], [], [], "HIGH", "complete"))
    traces.append(_trace("L15", "https://github.com/pydantic/pydantic-ai/blob/main/docs/tools-advanced.md", "PydanticAI", "CODING_DEBUGGING", "generic-json", [_generic(1, event_type="tool_retry", tool_name="compile", tool_args={"file": "a.py"}, error_type="ValidationError", error_message="fix needed", state_before={"phase": "compile"}, state_after={"phase": "compile"}), _generic(2, event_type="tool_result", tool_name="compile", tool_args={"file": "a.py"}, tool_result={"tests": "pass"}, state_before={"phase": "compile"}, state_after={"phase": "tested"}, artifacts_created=["test-report"])], "PROGRESSING", "a validation retry is followed by a successful tested artifact", ["error class changed", "state transition", "artifact"], [], [], "HIGH", "complete"))
    traces.append(_trace("L16", autogen_termination, "AutoGen", "MULTI_AGENT", "generic-json", [_generic(1, event_type="message", tool_name="researcher", tool_result={"handoff": True}, state_before={"phase": "research"}, state_after={"phase": "handoff"}), _generic(2, event_type="message", tool_name="writer", tool_result={"draft": True}, state_before={"phase": "handoff"}, state_after={"phase": "draft"}, artifacts_created=["draft"]), _generic(3, event_type="termination", tool_name="reviewer", tool_result={"approved": True}, state_before={"phase": "draft"}, state_after={"phase": "done"})], "PROGRESSING", "handoff, artifact, and approval form a terminating path", ["state transition", "artifact"], [], [], "HIGH", "complete"))
    traces.append(_trace("L17", "https://docs.temporal.io/encyclopedia/retry-policies", "Temporal", "TOOL_BUSINESS", "generic-json", [_generic(1, event_type="activity_failed", tool_name="charge", error_type="TimeoutError", error_message="transient", state_before={"phase": "charge"}, state_after={"phase": "charge"}), _generic(2, event_type="activity_succeeded", tool_name="charge", tool_result={"receipt": "r1"}, state_before={"phase": "charge"}, state_after={"phase": "charged"}, artifacts_created=["receipt"])], "PROGRESSING", "activity retry succeeds and records a receipt", ["error class changed", "state transition", "artifact"], [], [], "HIGH", "complete"))
    traces.append(_trace("L18", "https://docs.restate.dev/tour/workflows", "Restate", "TOOL_BUSINESS", "generic-json", [_generic(i, event_type="journal_step", tool_name="step", tool_result={"committed": i}, state_before={"journal": i - 1}, state_after={"journal": i}, metadata={"checkpoint_advanced": True}) for i in range(1, 5)], "PROGRESSING", "journaled steps commit and advance", ["checkpoint"], [], [], "HIGH", "complete"))
    traces.append(_trace("L19", "https://docs.dbos.dev/ai/ai-quickstart", "DBOS", "CODING_DEBUGGING", "generic-json", [_generic(i, event_type="workflow_step", tool_name="agent_step", tool_result={"checkpoint": i}, state_before={"checkpoint": i - 1}, state_after={"checkpoint": i}, metadata={"checkpoint_advanced": True}) for i in range(1, 5)], "PROGRESSING", "database-backed checkpoint advances through recovery", ["checkpoint", "state transition"], [], [], "HIGH", "complete"))
    traces.append(_trace("L20", "https://python.langchain.com/", "LangChain", "RESEARCH_SEARCH", "generic-json", [_generic(i, event_type="chain_step", tool_name="retrieve", tool_result={"document": i}, state_before={"documents": i - 1}, state_after={"documents": i}, artifacts_created=[f"doc-{i}"]) for i in range(1, 5)], "PROGRESSING", "each retrieval produces a new document and state count", ["artifact", "state transition"], [], [], "MEDIUM", "complete"))

    # 10 ambiguous/incomplete traces. The expected label is UNKNOWN by manual review.
    traces.append(_trace("A21", anthropic_tool, "Anthropic SDK", "TOOL_BUSINESS", "generic-json", [_generic(i, tool_name="get_weather", tool_args={"city": "Paris"}, tool_result={"temperature": 18}) for i in range(1, 5)], "UNKNOWN", "the public failure indicates missing tool propagation, but this trace has no authoritative state", [], ["possible repeated call"], ["state", "tool-result linkage"], "LOW", "sparse"))
    traces.append(_trace("A22", openai_tool, "OpenAI Agents", "TOOL_BUSINESS", "generic-json", [_generic(i, event_type="tool_call", tool_name="lookup", tool_result={"id": 9}, metadata={"postback": None}) for i in range(1, 5)], "UNKNOWN", "a missing postback is plausible but the trace cannot establish whether the tool was reissued", [], ["missing postback evidence"], ["state", "causal linkage"], "LOW", "sparse"))
    traces.append(_trace("A23", langfuse_context, "Langfuse", "RESEARCH_SEARCH", "generic-json", [_generic(i, event_type="context_update", tool_name="compress", tool_result={"summary": f"v{i}"}, context_size=i * 100, token_delta=20) for i in range(1, 5)], "UNKNOWN", "text/context novelty does not establish useful progress", [], [], ["state", "verified observation"], "LOW", "partial"))
    traces.append(_trace("A24", agno_governance, "Agno", "TOOL_BUSINESS", "generic-json", [_generic(i, event_type="policy_check", tool_name="authorize", tool_result={"allowed": i % 2 == 0}, metadata={"policy_source": "unknown"}) for i in range(1, 5)], "UNKNOWN", "policy changes are visible but their business effect is not", [], [], ["state", "domain outcome"], "LOW", "sparse"))
    traces.append(_trace("A25", llama_fields, "LlamaIndex", "RESEARCH_SEARCH", "generic-json", [_generic(i, event_type="tool_result", tool_name="retrieve", tool_result={"text": f"variant-{i}"}) for i in range(1, 5)], "UNKNOWN", "slightly different results have no verified usefulness", [], [], ["state", "artifact", "oracle"], "LOW", "sparse"))
    traces.append(_trace("A26", "https://docs.langchain.com/oss/python/langgraph/persistence", "LangGraph", "TOOL_BUSINESS", "langgraph-compat", [_langgraph(i, "external_call", output={"status": "timeout"}, metadata={"langgraph_step": i}) for i in range(1, 5)], "UNKNOWN", "checkpoint-visible timeout does not reveal whether the external effect committed", [], ["possible repeated external call"], ["external receipt", "state_before", "state_after"], "MEDIUM", "partial"))
    traces.append(_trace("A27", "https://github.com/pydantic/pydantic-ai/issues/6979", "PydanticAI", "CODING_DEBUGGING", "generic-json", [_generic(i, event_type="tool_schema_error", tool_name="dynamic_tool", error_type="SchemaError", error_message=f"field variant {i}") for i in range(1, 5)], "UNKNOWN", "schema errors repeat, but the trace lacks the caller’s intended recovery semantics", [], ["repeated schema failure"], ["state", "goal"], "LOW", "sparse"))
    traces.append(_trace("A28", "https://openai.github.io/openai-agents-python/running_agents/", "OpenAI Agents", "CODING_DEBUGGING", "generic-json", [_generic(i, event_type="model_output", tool_result=f"new wording {i}") for i in range(1, 5)], "UNKNOWN", "novel text without a tool/state oracle is ambiguous", [], [], ["state", "task oracle"], "LOW", "sparse"))
    traces.append(_trace("A29", "https://docs.temporal.io/encyclopedia/retry-policies", "Temporal", "TOOL_BUSINESS", "generic-json", [_generic(i, event_type="activity_timeout", tool_name="send", error_type="TimeoutError", error_message=f"attempt {i}") for i in range(1, 5)], "UNKNOWN", "timeout does not establish whether the remote side effect happened", [], ["possible side effect"], ["receipt", "state", "idempotency"], "LOW", "sparse"))
    traces.append(_trace("A30", "https://docs.restate.dev/foundations/key-concepts", "Restate", "TOOL_BUSINESS", "generic-json", [_generic(i, event_type="handler_result", tool_name="external_api", tool_result={"status": "unknown"}, metadata={"journaled": True}) for i in range(1, 5)], "UNKNOWN", "journal state exists but remote truth and semantic outcome are absent", [], ["unknown external state"], ["remote receipt", "domain outcome"], "LOW", "partial"))
    return traces
