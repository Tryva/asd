# Contributing to ASD

## Local development

Create a virtual environment, install the package with `python -m pip install
-e .`, and run the complete suite with:

```bash
python -m unittest discover -s tests -v
```

Run `python examples/agent_control_demo.py` when changing the public adapter
or its documentation.

## Expectations

Keep changes small, deterministic, dependency-light, and covered by tests.
Preserve evidence provenance, the TWO_ANCHOR contract, and the safety rule that
`UNKNOWN` is never an automatic deny decision.

## Reporting detector errors

Open an issue with a minimal synthetic reproduction when possible. Clearly say
whether the report is a false positive or false negative, include the input
shape and observed decision, and remove secrets or private data.
