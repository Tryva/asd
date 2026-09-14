# ASD — Canonical R&D Sources

Purpose: keep a small, high-signal corpus of external technical/scientific sources that can materially change ASD decisions.

This is **not** a generic reading list. A source belongs here only if it can help validate, refute, stress-test, or operationalize ASD's core questions around agent progress, stagnation, loops, long-horizon execution, retries, trajectory evaluation, external state, or runtime control.

## Evidence tiers

- **TIER A — Decision-changing evidence**: benchmarks, datasets, or papers that can directly challenge ASD assumptions or provide replayable trajectories.
- **TIER B — Transfer / environment evidence**: realistic agent environments and runtimes useful for testing generalization and progress anchors.
- **TIER C — Instrumentation / discovery evidence**: observability and telemetry systems useful for understanding real production traces, but insufficient alone to justify scientific conclusions.

Rule: **Tier C evidence must not, by itself, validate a scientific claim about ASD.**

---

## TIER A — Priority sources

### 1. τ³-bench / τ-bench family
- TYPE: benchmark + code + task data
- REPO: https://github.com/sierra-research/tau2-bench
- LEGACY_REPO: https://github.com/sierra-research/tau-bench
- WHY_RELEVANT: realistic tool-agent-user interactions with external task state and multi-step execution.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether ASD can distinguish repeated-but-progressing work from no-progress loops on real tool trajectories.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes
- PRIORITY: A
- NOTE: prefer the latest τ-bench family repository; the original tau-bench repo marks its tasks as outdated.

### 2. Toolathlon
- TYPE: benchmark + code + long-horizon tool trajectories
- REPO: https://github.com/HYZ17/Toolathlon-Official
- WHY_RELEVANT: long-horizon tasks with many tools and multi-call workflows.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: stagnation detection, cycle detection, long-run bounded-state behavior, and steps potentially saved.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes / benchmark artifacts
- PRIORITY: A

### 3. AgentDebug / AgentErrorBench
- TYPE: paper + benchmark + annotated agent failures
- REPO: https://github.com/ulab-uiuc/AgentDebug
- WHY_RELEVANT: focuses on diagnosing agent failures and trajectory-level error classes rather than only final success.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether ASD is over-collapsing distinct failure modes into stagnation/looping.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes
- PRIORITY: A

### 4. AgentDiagnose
- TYPE: peer-reviewed paper / agent trajectory diagnosis
- PAPER: https://aclanthology.org/2025.emnlp-demos.15/
- WHY_RELEVANT: analyzes multi-step trajectories, state transitions, verification, exploration, and failure diagnosis.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether ASD's evidence model is too shallow relative to richer process-level diagnosis.
- CODE_AVAILABLE: verify per paper/repo
- DATA_AVAILABLE: verify per paper/repo
- PEER_REVIEWED: yes
- PRIORITY: A

### 5. BFCL — Berkeley Function Calling Leaderboard
- TYPE: benchmark + code + multi-turn tool use
- REPO: https://github.com/ShishirPatil/gorilla
- WHY_RELEVANT: function/tool calling evaluation including multi-turn and recovery-oriented behavior in newer benchmark versions.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: repeated calls, recovery attempts, tool-call correctness, and trajectory-level failure patterns.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes
- PRIORITY: A

### 6. AgentLens
- TYPE: paper / trajectory-level agent evaluation
- PAPER: https://arxiv.org/abs/2607.06624
- WHY_RELEVANT: evaluates full coding-agent trajectories including tools, verification, recovery, and path quality.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether ASD's trajectory evidence is sufficient to say something useful before final task completion.
- CODE_AVAILABLE: verify
- DATA_AVAILABLE: verify
- PRIORITY: A

### 7. ATBench
- TYPE: benchmark + code + trajectory safety / diagnosis
- REPO: https://github.com/LiYu0524/ATbench
- WHY_RELEVANT: trajectory-level agent analysis and audited cases.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether ASD's signals remain meaningful across different failure causes and safety-relevant trajectories.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes
- PRIORITY: A

---

## TIER B — Transfer and environment sources

### 8. AgentBench
- TYPE: benchmark + multi-environment agent evaluation
- REPO: https://github.com/THUDM/AgentBench
- WHY_RELEVANT: broad agent benchmark across heterogeneous environments.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: framework/environment transferability of ASD behavior.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes
- PRIORITY: B

### 9. AgentBoard
- TYPE: benchmark + analytical agent evaluation
- REPO: https://github.com/hkust-nlp/AgentBoard
- WHY_RELEVANT: emphasizes analytical and fine-grained evaluation instead of only final pass/fail.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: usefulness of intermediate progress metrics and trajectory-level analysis.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes
- PEER_REVIEWED: yes
- PRIORITY: B

### 10. AgentDojo
- TYPE: benchmark + dynamic tool environment
- REPO: https://github.com/ethz-spylab/agentdojo
- WHY_RELEVANT: realistic tool interactions with externally observable consequences.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: distinction between tool execution, task progress, and unsafe/incorrect side effects.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes
- PRIORITY: B

### 11. SWE-bench
- TYPE: benchmark + executable ground truth
- REPO: https://github.com/SWE-bench/SWE-bench
- WHY_RELEVANT: externally verifiable outcomes via code changes and tests.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether ASD can use strong artifacts/checkpoints as trusted progress anchors.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes
- PRIORITY: B

### 12. WebArena
- TYPE: realistic web-agent benchmark
- REPO: https://github.com/web-arena-x/webarena
- WHY_RELEVANT: web tasks with persistent external state and multi-step actions.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: legitimate repeated actions versus repeated actions with no external progress.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: yes
- PRIORITY: B

### 13. AgentOccam
- TYPE: peer-reviewed paper + code
- REPO: https://github.com/amazon-science/AgentOccam
- WHY_RELEVANT: strong simple-agent baseline; useful counterweight against unnecessary architectural complexity.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether ASD improvements genuinely require additional machinery or whether simpler process rules are sufficient.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: benchmark-compatible
- PEER_REVIEWED: ICLR 2025
- PRIORITY: B

### 14. LangGraph
- TYPE: production agent runtime / graph execution framework
- REPO: https://github.com/langchain-ai/langgraph
- WHY_RELEVANT: checkpoints, retries, durability, graph state, long-running execution, and observable state transitions.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: practicality of trusted progress anchors and zero/low-code instrumentation.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: runtime traces depend on user execution
- PRIORITY: B

### 15. Letta
- TYPE: persistent-agent runtime
- REPO: https://github.com/letta-ai/letta
- WHY_RELEVANT: persistent memory, long context, stateful agents, compaction, retries, and traceable runtime failures.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether ASD mistakes legitimate state evolution / memory maintenance for stagnation.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: runtime-dependent
- PRIORITY: B

---

## TIER C — Instrumentation and discovery sources

### 16. Langfuse
- TYPE: open-source LLM / agent observability
- REPO: https://github.com/langfuse/langfuse
- WHY_RELEVANT: real-world traces, spans, tool calls, costs, observations, and production telemetry structures.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether ASD can consume existing telemetry instead of requiring custom instrumentation.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: user-generated traces
- PRIORITY: C

### 17. AgentOps
- TYPE: agent observability / session replay
- REPO: https://github.com/AgentOps-AI/agentops
- WHY_RELEVANT: tool usage, costs, failures, sessions, agent lifecycle, and multiple framework integrations.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: whether existing observability surfaces already expose enough evidence for ASD.
- CODE_AVAILABLE: yes
- DATA_AVAILABLE: user-generated traces
- PRIORITY: C

### 18. Awesome Agent Trajectory
- TYPE: curated research index
- REPO: https://github.com/YintongHuo/awesome-agent-trajectory
- WHY_RELEVANT: discovery surface for work on trajectory analysis, failure localization, intervention, recovery, and process evaluation.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: nothing directly; use only to discover primary papers/datasets.
- CODE_AVAILABLE: n/a
- DATA_AVAILABLE: n/a
- PRIORITY: C

### 19. Long-horizon agent research index / Horizon Gap
- TYPE: survey / research map
- REPO: https://github.com/deepgrounding/long-horizon-task
- WHY_RELEVANT: maps long-horizon agent research, including execution control and recovery.
- WHAT_IT_CAN_REFUTE_OR_SUPPORT: nothing directly; use to locate primary evidence.
- CODE_AVAILABLE: n/a
- DATA_AVAILABLE: n/a
- PRIORITY: C

---

## Source-use rules for future ICMs

1. Read this file first before broad web/GitHub/Hugging Face searches.
2. Prefer primary papers, benchmark repos, datasets, and executable code over summaries.
3. Prefer peer-reviewed evidence when scientific claims are at stake.
4. Preserve null / ambiguous / non-stagnation cases; do not search only for loops.
5. A benchmark success label is not automatically a stagnation label.
6. Tool-call repetition is not, by itself, evidence of stagnation.
7. External state, checkpoint movement, artifacts, verified observations, or other trusted anchors should be used whenever available.
8. If a source's labels do not map cleanly to ASD semantics, mark the mapping as unresolved instead of forcing it.
9. Discovery/index repos are not evidence substitutes; follow through to primary sources.
10. Add new entries only when they can materially alter an ASD decision or provide a uniquely useful evaluation surface.

## Current R&D question this corpus should support

> Can ASD detect lack of verifiable progress early enough to be useful, while avoiding false stops on legitimate repeated or long-horizon work?
