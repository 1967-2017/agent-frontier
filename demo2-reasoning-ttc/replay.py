from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax


def latest_trace() -> Path:
    latest = json.loads(Path("outputs/latest.json").read_text(encoding="utf-8"))
    return Path(latest["run_dir"]) / "trace.jsonl"


def load_events(path: Path) -> list[dict]:
    events = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                events.append(json.loads(line))
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay Demo2 trace")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--trace")
    parser.add_argument("--no-delay", action="store_true")
    args = parser.parse_args()
    trace = latest_trace() if args.latest else Path(args.trace)
    console = Console(force_terminal=True, legacy_windows=False)
    for event in load_events(trace):
        payload = {key: event.get(key) for key in ["event_type", "strategy", "provider", "model", "question_id", "sample_index", "status", "latency_ms", "output", "cost"] if key in event}
        syntax = Syntax(json.dumps(payload, ensure_ascii=False, indent=2, default=str), "json", word_wrap=True)
        console.print(Panel(syntax, title=f"{event.get('ts')} {event.get('event_type')}", box=box.ASCII))
        if not args.no_delay:
            time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
