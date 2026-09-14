# ASD — Agent Stagnation Detector

ASD is a small, framework-neutral detector for repeated work, missing
verifiable progress, deterministic loops, and budget risk in agent trajectories.
It is a detector and evidence contract, not an agent runtime, quality judge, or
recovery engine.

## Why repetition is not enough

An agent may legitimately read several files, retry a transient operation, or
repeat a tool while the external state changes. ASD therefore requires
observable evidence and distinguishes legitimate progress from repeated work
without verifiable progress.

## Decisions

The detector returns one of:

- `PROGRESSING`
- `STAGNATING`
- `LOOPING`
- `BUDGET_RISK`
- `UNKNOWN`

`UNKNOWN` means that the available evidence is insufficient for a justified hard
stagnation or loop decision. It is non-blocking by default and never maps to
`DENY` in the included integration.

## TWO_ANCHOR evidence contract

Hard stagnation/loop decisions require both a primary negative signal and an
independent trusted state or progress anchor. Suitable anchors include a state
version, checkpoint, artifact/resource identifier, completed-item counter, or
trusted tool-result fingerprint. Trace IDs, span IDs, message IDs, timestamps,
and retry counters are not progress proof by themselves.

Raw prompts and raw tool results are not required. Structured fields and stable
fingerprints are sufficient. Missing, conflicting, and ambiguous evidence is
preserved as `UNKNOWN` rather than silently treated as progress or failure.

## Install

```bash
python -m pip install .
```

Optional Agent Control evaluator plugin:

```bash
python -m pip install ".[agent-control]"
```

The plugin uses the `agent_control.evaluators` entry point and
`evaluate_with_context(data, step)`. Agent Control remains the enforcement
layer; ASD returns structured evidence. The default mapping is:

| ASD status | Recommended action |
| --- | --- |
| `PROGRESSING` | `ALLOW` |
| `STAGNATING` | `WARN` |
| `LOOPING` | `WARN` |
| `BUDGET_RISK` | `WARN` |
| `UNKNOWN` | `LOG` |

A host may opt into a strict `LOOPING` → `DENY` policy. `UNKNOWN` must not be
configured as `DENY`. Configure the evaluator name as `asd.stagnation`.

## Minimal Python example

```python
from stagnation_detector import detect_stagnation

events = [
    {
        "event_type": "tool",
        "step_id": 1,
        "tool_name": "write",
        "state_before": {"version": 0},
        "state_after": {"version": 1},
        "artifacts_created": ["artifact-1"],
    },
]

decision = detect_stagnation(events)
print(decision.status)
```

Run the synthetic Agent Control adapter example with:

```bash
python examples/agent_control_demo.py
```

The JSON examples in `examples/` are synthetic and show progressing, looping,
and insufficient-evidence trajectories. They do not contain customer traces.

## Limitations

ASD does not understand business goals, prove answer quality, verify arbitrary
external side effects, choose a recovery action, or establish production
reliability. Thresholds are initial deterministic defaults. State is bounded
and process-local; a multi-worker deployment needs an explicitly shared state
design. The project contains no LLM calls or paid APIs.

## License

Apache-2.0. See `LICENSE`.
