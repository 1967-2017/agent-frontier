from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def append_event(trace_path: Path, event_type: str, **payload: Any) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": utc_now(), "demo": "demo2-reasoning-ttc", "event_type": event_type, **payload}
    with trace_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")


def read_trace(trace_path: Path) -> list[dict[str, Any]]:
    if not trace_path.exists():
        return []
    events = []
    with trace_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                events.append(json.loads(line))
    return events
