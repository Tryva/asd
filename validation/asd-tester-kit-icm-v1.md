# ASD tester kit ICM v1

## OBSERVATIONS

- Fresh clone from `https://github.com/Tryva/asd.git` succeeded.
- Existing README explained the Agent Control demo, but did not give a JSON
  trace command, event contract, or redaction path.
- Existing synthetic traces already covered progressing, looping, and
  insufficient evidence (`UNKNOWN`), but `python examples/progressing.json`
  merely evaluated as a no-op; it did not run ASD.
- The existing demo returned useful structured evidence, but its nested JSON
  output was more work to interpret than a compact status/signals/evidence
  view.

For each observation, evidence was recorded by replaying the clean clone and
reading `README.md`, `examples/*.json`, `examples/agent_control_demo.py`, and
the detector/event interfaces.

## HYPOTHESES

| Hypothesis | Result | Evidence |
| --- | --- | --- |
| H1: minimum event format is unclear | VALIDATED | No trace contract or field guidance existed in the README/examples. |
| H2: no one-command meaningful example | VALIDATED | No command accepted a JSON trace and printed one decision; the JSON file itself did nothing. |
| H3: redacting a real trace is unclear | VALIDATED | No redaction instructions or safe fingerprint/substitute examples existed. |
| H4: output is difficult to interpret | VALIDATED | The demo emitted nested integration JSON rather than a direct status/signals/evidence report. |
| H5: setup is unnecessary | INCONCLUSIVE | `python -m pip install .` completed in the audit, but the existing demo was already dependency-light; no setup change was justified. |

## DECISIONS

- Fix only the validated tester-experience friction.
- Reuse the existing synthetic JSON files; do not duplicate them under a new
  directory.
- Keep detector semantics, TWO_ANCHOR, integration policy, and dependencies
  unchanged.

## CHANGES

- Added `examples/test_asd.py`, a standard-library runner that calls the
  existing `detect_stagnation` core, accepts an object or event array, prints
  status/signals/evidence, and reports malformed input clearly.
- Added `examples/TRACE_FORMAT.md` with the smallest useful event contract,
  trusted versus non-trusted progress fields, concrete JSON, and a redaction
  guide.
- Added a short README “Try ASD in 5 minutes” section.
- Reused `examples/progressing.json`, `examples/looping.json`, and
  `examples/ambiguous.json` for PROGRESSING, LOOPING, and UNKNOWN.

## VALIDATION

- Baseline suite: 44 tests passed after source-path setup; no kit existed in
  the baseline.
- Post-change suite: 44 tests passed.
- Runner replay: progressing → `PROGRESSING`; looping → `LOOPING` with
  `EXACT_REPEAT`, `NO_NEW_ARTIFACT`, and `NO_STATE_DELTA`; ambiguous →
  `UNKNOWN`.
- Runner usage error: no path returns a clear usage message and exit code 2.
- Fresh clone after push: clone → install → first `LOOPING` result completed in
  under one minute on this host (install took approximately 35–45 seconds).
- Custom redacted trace replay succeeded with `LOOPING` and the same evidence.
- Fresh-clone suite: all 44 tests passed.
- No core files, thresholds, contracts, or integration behavior changed.

## REMAINING_FRICTIONS

- A real external tester still needs Python and the normal package install.
- The runner reports detector output, not the optional Agent Control contract
  wrapper; that is intentional for a five-minute core test.
- `ambiguous.json` is the pre-existing name for the UNKNOWN example.

## NEXT_DECISION

The kit reaches the first meaningful result in under five minutes on a clean
clone and is `READY_FOR_EXTERNAL_TESTERS`. Reassess after actual external
tester feedback.
