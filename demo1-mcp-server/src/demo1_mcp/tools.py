from __future__ import annotations

from typing import Any

from .data_store import (
    notify_oncall_data,
    query_metric_data,
    restart_service_data,
    tail_log_data,
)
from .trace import record_event


def query_metric(service: str, metric: str, window: str) -> dict[str, Any]:
    return record_event(
        "tool",
        "query_metric",
        {"service": service, "metric": metric, "window": window},
        lambda: query_metric_data(service, metric, window),
    )


def tail_log(service: str, lines: int, level: str) -> dict[str, Any]:
    return record_event(
        "tool",
        "tail_log",
        {"service": service, "lines": lines, "level": level},
        lambda: tail_log_data(service, lines, level),
    )


def restart_service(service: str, dry_run: bool = True) -> dict[str, Any]:
    return record_event(
        "tool",
        "restart_service",
        {"service": service, "dry_run": dry_run},
        lambda: restart_service_data(service, dry_run),
    )


def notify_oncall(service: str, summary: str, severity: str) -> dict[str, Any]:
    return record_event(
        "tool",
        "notify_oncall",
        {"service": service, "summary": summary, "severity": severity},
        lambda: notify_oncall_data(service, summary, severity),
    )
