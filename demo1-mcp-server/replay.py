from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

STYLE_BY_TYPE = {
    "tool": "cyan",
    "resource": "green",
    "prompt": "magenta",
    "server": "yellow",
    "error": "red",
}


def parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                events.append(json.loads(line))
    return events


def render_event(event: dict[str, Any]) -> Panel:
    event_type = event.get("event_type", "unknown")
    style = STYLE_BY_TYPE.get(event_type, "white")
    title = f"{event.get('ts', '')} [{event_type}] {event.get('name', 'unknown')}"
    payload = {
        "input": event.get("input"),
        "output": event.get("output"),
        "status": event.get("status"),
        "duration_ms": event.get("duration_ms"),
    }
    if event.get("error"):
        payload["error"] = event["error"]
    syntax = Syntax(json.dumps(payload, ensure_ascii=False, indent=2, default=str), "json", word_wrap=True)
    return Panel(syntax, title=title, border_style=style, box=box.ASCII)


def replay(events: list[dict[str, Any]], speed: float, no_delay: bool) -> None:
    console = Console(force_terminal=True, legacy_windows=False)
    if not events:
        console.print("No trace events found.", style="yellow")
        return
    previous_ts: datetime | None = None
    for event in events:
        current_ts = parse_ts(event.get("ts", ""))
        if not no_delay and previous_ts and current_ts:
            delay = max(0.0, (current_ts - previous_ts).total_seconds() / speed)
            time.sleep(min(delay, 5.0))
        console.print(render_event(event))
        previous_ts = current_ts
    console.print(Text(f"Replayed {len(events)} events.", style="bold green"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay Demo1 MCP trace.jsonl")
    parser.add_argument("--trace", default="trace.jsonl", help="Path to trace.jsonl")
    parser.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier")
    parser.add_argument("--no-delay", action="store_true", help="Replay without waiting between events")
    args = parser.parse_args()
    replay(load_events(Path(args.trace)), max(args.speed, 0.1), args.no_delay)


if __name__ == "__main__":
    main()
