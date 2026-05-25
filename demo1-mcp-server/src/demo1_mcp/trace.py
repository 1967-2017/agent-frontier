from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from .config import trace_path

T = TypeVar("T")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class TraceEvent:
    event_type: str
    name: str
    input: dict[str, Any]
    output: Any
    status: str
    duration_ms: int
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "ts": utc_now(),
            "demo": "demo1-mcp-server",
            "event_type": self.event_type,
            "name": self.name,
            "input": self.input,
            "output": self.output,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "tokens": None,
            "cost": None,
        }
        if self.error:
            data["error"] = self.error
        return data


def append_trace(event: TraceEvent, path: Path | None = None) -> None:
    target = path or trace_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event.to_json(), ensure_ascii=False, default=str) + "\n")


def record_event(event_type: str, name: str, input_data: dict[str, Any], fn: Callable[[], T]) -> T:
    started = time.perf_counter()
    try:
        output = fn()
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        append_trace(
            TraceEvent(
                event_type=event_type,
                name=name,
                input=input_data,
                output=None,
                status="error",
                duration_ms=duration_ms,
                error=str(exc),
            )
        )
        raise
    duration_ms = int((time.perf_counter() - started) * 1000)
    append_trace(
        TraceEvent(
            event_type=event_type,
            name=name,
            input=input_data,
            output=output,
            status="ok",
            duration_ms=duration_ms,
        )
    )
    return output


def read_trace(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or trace_path()
    if not target.exists():
        return []
    events: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                events.append(json.loads(line))
    return events


def diff_params(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if previous is None:
        return {key: {"before": None, "after": value} for key, value in current.items()}
    keys = set(previous) | set(current)
    return {
        key: {"before": previous.get(key), "after": current.get(key)}
        for key in sorted(keys)
        if previous.get(key) != current.get(key)
    }
