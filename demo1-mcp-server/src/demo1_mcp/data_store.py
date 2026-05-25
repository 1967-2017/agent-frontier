from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from .config import data_dir


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _window_to_minutes(window: str) -> int | None:
    normalized = window.strip().lower()
    if not normalized:
        return None
    unit = normalized[-1]
    value = normalized[:-1]
    if not value.isdigit():
        return None
    amount = int(value)
    if unit == "m":
        return amount
    if unit == "h":
        return amount * 60
    return None


def query_metric_data(service: str, metric: str, window: str) -> dict[str, Any]:
    data = _read_json(data_dir() / "metrics.json")
    services = data.get("services", {})
    if service not in services:
        raise ValueError(f"Unknown service: {service}")
    metrics = services[service].get("metrics", {})
    if metric not in metrics:
        raise ValueError(f"Unknown metric for service {service}: {metric}")

    metric_data = metrics[metric]
    points = list(metric_data.get("points", []))
    window_minutes = _window_to_minutes(window)
    if window_minutes is not None and points:
        points = points[-max(1, min(len(points), window_minutes // 5 or 1)) :]
    values = [point["value"] for point in points]
    summary = {
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "avg": round(mean(values), 3) if values else None,
    }
    return {
        "service": service,
        "metric": metric,
        "window": window,
        "unit": metric_data.get("unit"),
        "points": points,
        "summary": summary,
    }


def tail_log_data(service: str, lines: int, level: str) -> dict[str, Any]:
    if lines < 1:
        raise ValueError("lines must be >= 1")
    log_path = data_dir() / "logs" / f"{service}.log"
    if not log_path.exists():
        raise ValueError(f"Unknown service log: {service}")
    normalized_level = level.strip().upper()
    entries: list[dict[str, str]] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            parts = raw_line.strip().split(" ", 3)
            if len(parts) < 4:
                continue
            timestamp, entry_level, trace_part, message = parts
            if normalized_level and entry_level.upper() != normalized_level:
                continue
            trace_id = trace_part.split("=", 1)[1] if "=" in trace_part else trace_part
            entries.append(
                {
                    "timestamp": timestamp,
                    "level": entry_level,
                    "trace_id": trace_id,
                    "message": message,
                }
            )
    return {
        "service": service,
        "lines": lines,
        "level": normalized_level,
        "entries": entries[-lines:],
    }


def restart_service_data(service: str, dry_run: bool = True) -> dict[str, Any]:
    state_path = data_dir() / "service_state.json"
    state = _read_json(state_path)
    services = state.get("services", {})
    if service not in services:
        raise ValueError(f"Unknown service: {service}")
    service_state = services[service]
    if dry_run:
        return {
            "service": service,
            "dry_run": True,
            "action": "restart_service",
            "would_restart": True,
            "executed": False,
            "message": "Dry run only. Pass dry_run=false to execute restart.",
        }

    previous_status = service_state.get("status", "unknown")
    restarted_at = _utc_now()
    service_state["status"] = "running"
    service_state["restart_count"] = int(service_state.get("restart_count", 0)) + 1
    service_state["last_restarted_at"] = restarted_at
    _write_json(state_path, state)
    return {
        "service": service,
        "dry_run": False,
        "action": "restart_service",
        "executed": True,
        "previous_status": previous_status,
        "current_status": service_state["status"],
        "restart_count": service_state["restart_count"],
        "restarted_at": restarted_at,
    }


def notify_oncall_data(service: str, summary: str, severity: str) -> dict[str, Any]:
    services = _read_json(data_dir() / "service_state.json").get("services", {})
    if service not in services:
        raise ValueError(f"Unknown service: {service}")
    record = {
        "id": str(uuid.uuid4()),
        "timestamp": _utc_now(),
        "service": service,
        "summary": summary,
        "severity": severity,
    }
    sink = data_dir() / "notifications.jsonl"
    with sink.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {
        "service": service,
        "severity": severity,
        "notified": True,
        "sink": str(sink.relative_to(data_dir().parent)),
        "record_id": record["id"],
    }


def list_incidents_data() -> dict[str, Any]:
    return _read_json(data_dir() / "incidents.json")


def read_runbook_data(service: str) -> str:
    path = data_dir() / "runbooks" / f"{service}.md"
    if not path.exists():
        raise ValueError(f"Unknown service runbook: {service}")
    return path.read_text(encoding="utf-8")
