# ASD trace format

The tester accepts either a JSON array of events or an object containing an
`events` array. Run one with:

```bash
python examples/test_asd.py examples/looping.json
```

## Smallest useful event

`event_type` is the only field required by the event envelope. For a useful
external test, include these fields on every event:

| Field | Requirement | Purpose |
| --- | --- | --- |
| `event_type` | REQUIRED | Event kind, for example `tool` or `model_output`. |
| `step_id` | REQUIRED for ordered trace evidence | Stable ordering/window identifier. |
| `tool_name` (or another action identity) | REQUIRED for repeat/cycle evidence | Identifies the action. Hash it if the name is sensitive. |
| `tool_result` or `error_type`/`error_message` | REQUIRED for observable outcome | Shows what happened without requiring raw content. |
| `state_after` or a trusted progress anchor | REQUIRED for a hard TWO_ANCHOR decision | A structured state/checkpoint/artifact/resource anchor. |

Optional fields include `tool_args`, `state_before`, `artifacts_created`,
`subtasks_completed`, `constraints_resolved`, `token_delta`, `cost_delta`,
`context_size`, `timestamp`, and `metadata`. Numeric budget fields must be
numeric when present. Raw prompts and tool payloads are not required.

Trusted progress signals include a changed `state_before`/`state_after`, a
state version, an advanced checkpoint, a created artifact/resource identifier,
verified subtask or constraint progress, or a stable tool-result fingerprint.
These are evidence only when they describe externally meaningful progress.

Timestamps, trace IDs, span IDs, message IDs, retry counters, and step numbers
are identifiers or ordering metadata; changing them does not prove progress.

Example with raw content omitted:

```json
{
  "events": [
    {
      "event_type": "tool",
      "step_id": 1,
      "tool_name": "lookup",
      "tool_args": {"resource_id": "synthetic-1"},
      "tool_result": {"fingerprint": "result-hash-1"},
      "state_after": {"version": 3},
      "artifacts_created": []
    }
  ]
}
```

## Redact a real trace

Do not send credentials, secrets, customer data, or confidential payloads.
Before testing, replace:

- customer text, prompts, and tool payloads with short synthetic placeholders;
- URLs and customer resources with synthetic resource IDs;
- raw tool results with a stable fingerprint;
- sensitive state with a version, hash, or checkpoint identifier.

Keep the event structure, ordering, action identity, outcome/error family, and
trusted anchors. Then run the local JSON file with `test_asd.py` and inspect
the status, signals, and evidence. `UNKNOWN` is a valid non-blocking result
when the redacted trace no longer contains enough evidence.

The repository examples are synthetic: `progressing.json`, `looping.json`,
and `ambiguous.json` (the UNKNOWN case).
