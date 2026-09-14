# ASD — Agent Stagnation Detector

Detect when an AI agent stops making verifiable progress.

ASD is a framework-neutral deterministic detector for:

- stagnation
- loops
- budget risk
- insufficient evidence

An agent may legitimately repeat a tool while external state changes. ASD
therefore looks for observable progress evidence instead of treating repetition
alone as failure.

## Why ASD

ASD separates detection from enforcement. It produces a deterministic status and
structured evidence that a host system can review or use in an explicitly chosen
control policy. It is not an agent runtime, quality judge, or recovery engine.

## Quick start

```bash
git clone https://github.com/Tryva/asd.git
cd asd
python -m venv .venv
```

On macOS/Linux, activate with `source .venv/bin/activate`. On Windows
PowerShell, activate with `.venv\\Scripts\\Activate.ps1`. Then run:

```bash
python -m pip install .
python examples/agent_control_demo.py
python -m unittest discover -s tests -v
```

The demo and tests are local and do not call an LLM, provider, or paid API.

## Example output

A synthetic trajectory that repeats the same lookup without a state change can
produce `LOOPING`:

```text
{
  "status": "LOOPING",
  "signals": ["EXACT_REPEAT", "NO_STATE_DELTA", "NO_NEW_ARTIFACT"],
  "evidence": [
    "same normalized observation repeated 3 times",
    "trusted state anchor unchanged across 4 steps",
    "no verified artifact created"
  ]
}
```

This is synthetic evidence only; the repository contains no customer traces.

## Decisions

The detector returns one of `PROGRESSING`, `STAGNATING`, `LOOPING`,
`BUDGET_RISK`, or `UNKNOWN`. `UNKNOWN` means that the evidence is insufficient
for a justified hard decision. It is non-blocking by default and maps to `LOG`
in the included integration.

## TWO_ANCHOR

Hard stagnation/loop decisions require a primary negative signal and an
independent trusted state or progress anchor. Examples include a state version,
checkpoint, artifact/resource identifier, completed-item counter, or trusted
tool-result fingerprint. Trace IDs, timestamps, and retry counters are not
progress proof by themselves.

| Simple duplicate detector | ASD |
| --- | --- |
| Exact repetition | Exact repetition plus evidence checks |
| No trusted progress evidence | Trusted progress anchors are explicit |
| Legitimate repetition is indistinguishable | Legitimate repetition can remain progressing |
| No cycle model | Repeated cycles can be detected |
| Ambiguous evidence is usually a binary result | Ambiguous evidence is preserved as `UNKNOWN` |
| Little or no explanation | Structured evidence and missing-evidence fields |

## Agent Control integration

Install the optional evaluator plugin with:

```bash
python -m pip install ".[agent-control]"
```

The evaluator is discoverable through `agent_control.evaluators` as
`asd_stagnation` and exposes `evaluate_with_context(data, step)`. Agent Control
remains the enforcement layer; its evaluator metadata name is
`asd.stagnation`. A host may opt into a strict `LOOPING` → `DENY` policy, but
`UNKNOWN` must not be configured as `DENY`.

## Safety / UNKNOWN

Missing, conflicting, and ambiguous evidence is preserved as `UNKNOWN` rather
than silently treated as progress or failure. ASD never turns `UNKNOWN` into
`DENY`; hosts remain responsible for policy and safety decisions.

## Examples

The JSON files in `examples/` show synthetic progressing, looping, and
insufficient-evidence trajectories. Run the adapter demo with:

```bash
python examples/agent_control_demo.py
```

## Limitations

ASD does not understand business goals, prove answer quality, verify arbitrary
external side effects, choose a recovery action, or establish production
reliability. Thresholds are initial deterministic defaults. State is bounded
and process-local; multi-worker use needs an explicitly shared state design.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local development, tests, and how to
report false positives or false negatives.

## License

Apache-2.0. See [LICENSE](LICENSE).
