from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from demo3_browser_agent.config import top_level_trace_path


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class TraceWriter:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.path = run_dir / "trace.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        top_level_trace_path().write_text("", encoding="utf-8")

    def append(self, event_type: str, **payload: Any) -> dict[str, Any]:
        event = {
            "ts": utc_now(),
            "demo": "demo3-browser-agent",
            "event_type": event_type,
            **payload,
        }
        line = json.dumps(redact_secrets(_jsonable(event)), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        with top_level_trace_path().open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return event

    def copy_to_latest(self) -> None:
        if self.path.exists():
            shutil.copyfile(self.path, top_level_trace_path())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(data), ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\.\-]{12,}", re.I),
]


def redact_secrets(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub(lambda match: _mask_secret(match.group(0)), redacted)
        return redacted
    if isinstance(value, dict):
        return {key: redact_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [redact_secrets(item) for item in value]
    return value


def _mask_secret(secret: str) -> str:
    if secret.lower().startswith("bearer "):
        return "Bearer ***REDACTED***"
    if len(secret) <= 10:
        return "***REDACTED***"
    return f"{secret[:6]}...{secret[-4:]}[REDACTED]"


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value
