"""Run ASD against a JSON trajectory and print a compact human-readable result."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Make the example runnable from a source checkout as well as after install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stagnation_detector.detector import detect_stagnation  # noqa: E402
from stagnation_detector.events import EventValidationError  # noqa: E402


def _load_events(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"trace file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"trace is not valid JSON: line {exc.lineno}, column {exc.colno}") from exc
    except OSError as exc:
        raise ValueError(f"could not read trace: {exc}") from exc

    if isinstance(payload, dict):
        payload = payload.get("events")
    if not isinstance(payload, list):
        raise ValueError("trace must be a JSON array or an object with an 'events' array")
    if not payload:
        raise ValueError("trace must contain at least one event")
    if not all(isinstance(event, dict) for event in payload):
        raise ValueError("each trace event must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("Usage: python examples/test_asd.py PATH_TO_TRACE.json", file=sys.stderr)
        return 2

    try:
        events = _load_events(Path(arguments[0]))
        detection = detect_stagnation(events)
    except (EventValidationError, TypeError, ValueError) as exc:
        print(f"ERROR: malformed trace: {exc}", file=sys.stderr)
        return 2

    print(f"STATUS: {detection.status}")
    print("SIGNALS:")
    for signal in detection.signals:
        print(f"- {signal}")
    if not detection.signals:
        print("- NONE")
    print("EVIDENCE:")
    for item in detection.evidence:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
