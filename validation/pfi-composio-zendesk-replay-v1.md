# ASD PFI / Composio / Zendesk Replay Validation

## 1. Question

Can ASD identify lack of verifiable progress in real PFI agent trajectories
without falsely flagging legitimate repeated work?

This study evaluates ASD as it exists. It does not modify detection policy,
thresholds, `TWO_ANCHOR`, `UNKNOWN`, event semantics, or classifier behavior.

## 2. Source corpus

Source repository: `Tryva/pfi-validation-lab`  
Branch: `feat/pfi-backend-v0`  
Source commit: `123cf394dcc6d191a48af56a277fa270ee6437a5`

The branch contains the following relevant source types:

- Composio/Zendesk read-only POC and preflight scripts;
- a four-tool read-only Zendesk contract;
- an offline qualification contract and deterministic unit tests;
- no exported trajectories, replay fixtures, trace JSON, snapshots, structured
  logs, ticket before/after states, or historical tool-invocation records.

PFI was inspected read-only and was not changed, committed, or pushed.

## 3. Evidence quality

The PFI repository provides evidence that a read-only integration surface was
designed and tested. It does not provide observations from an agent trajectory.
The declared tools explain what a verifier could read, but do not show what an
agent attempted or what changed in Zendesk.

No Composio response, retry sequence, error record, external resource state,
side effect, artifact, checkpoint, or cost/budget signal was available for
replay. No sensitive PFI data was copied into ASD.

Assessment: integration-contract evidence is present; replay evidence is
absent.

## 4. Ground-truth method

No hard ground-truth label was assigned. There is no observed Zendesk state
before/after, historical assertion about a trajectory outcome, external
artifact, verified tool result, or structured execution log from which to label
progress, stagnation, looping, budget risk, or unknown.

The PFI tests validate contract safety and preflight behavior, not agent task
success or no-progress behavior. They cannot substitute for trajectory ground
truth.

## 5. Trace selection

`TRAJECTORIES_FOUND: 0`  
`TRAJECTORIES_USABLE: 0`  
`TRAJECTORIES_REJECTED: 0`

There was nothing eligible to convert to ASD events. No synthetic trace was
created to satisfy the evidence target.

## 6. ASD replay results

No replay was executed because there were no source trajectories. Therefore:

- `PROGRESSING: 0`
- `STAGNATING: 0`
- `LOOPING: 0`
- `BUDGET_RISK: 0`
- `UNKNOWN: 0`
- `ASD_TRUE_POSITIVES: 0`
- `ASD_FALSE_POSITIVES: 0`
- `ASD_FALSE_NEGATIVES: 0`
- `ASD_UNKNOWN: 0`

All replay metrics are `N/A (denominator 0)`, not zero-performance claims.

## 7. Baseline comparison

The exact-duplicate detector and simple repeated-action-window baseline were
not run. Without labeled real trajectories, precision, recall, and false-stop
rate would be undefined and potentially misleading.

`EXACT_DUPLICATE_BASELINE: N/A (no trajectories)`  
`REPEAT_WINDOW_BASELINE: N/A (no trajectories)`

## 8. False positives

No false-positive assessment is possible. The source branch contains no
legitimate repeated-work trajectory with verified progress evidence.

## 9. False negatives

No false-negative assessment is possible. The source branch contains no
verified no-progress trajectory against which ASD could be tested.

## 10. UNKNOWN analysis

The correct outcome for the study-level question is uncertainty about transfer
to PFI trajectories, not an ASD classification. The missing external state and
ordered execution data prevent a per-trace `UNKNOWN` replay label.

## 11. Telemetry gaps

The decisive gaps are:

- no ordered Composio tool-call history or replay export;
- no sanitized tool results, error families, or retry sequence;
- no Zendesk ticket state before and after an action;
- no audit history tying an action to a resource or side effect;
- no checkpoint, artifact, state version, or trusted progress anchor;
- no agent outcome assertion connected to an execution trace.

These are `INSUFFICIENT_TELEMETRY`, `MISSING_PROGRESS_ANCHOR`, and
`STATE_MUTATION_NOT_VISIBLE` risks at study level, not demonstrated ASD bugs.

## 12. Scientific interpretation

The evidence supports that PFI has a narrowly scoped, side-effect-free
verification contract and deterministic contract tests. It does not support a
claim that ASD works, fails, or transfers to real Composio/Zendesk trajectories.

The strongest current conclusion is that the proposed replay study is not yet
identifiable from the checked-out PFI branch. The absence of trajectories is a
corpus limitation, not evidence for or against ASD.

## 13. Decision

`INCONCLUSIVE`

The minimum evidence target was not available. No provider call, Zendesk action,
automation, or external side effect was triggered.

## 14. Next decision

Obtain a sanitized, offline export of real historical trajectories or explicit
fixtures containing ordered events plus external-state evidence. Re-run this
study only when the corpus includes enough high/medium-confidence cases to
evaluate progressing work, no-progress work, and ambiguous evidence. Do not
modify ASD core to fit the missing fields.

## Verification record

- ASD repository changed: `NO` for core files.
- PFI repository changed: `NO`.
- ASD tests: `44 PASS`.
- PFI read-only repository tests: `13 PASS`.
- Secrets copied: `NO`.
- PII copied: `NO`.
- Live Composio/Zendesk calls: `NO`.
- Zendesk writes or side effects: `NO`.
