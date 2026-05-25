from __future__ import annotations

from typing import Any

from .data_store import list_incidents_data, read_runbook_data
from .trace import record_event


def incident_list() -> dict[str, Any]:
    return record_event("resource", "incident://list", {}, list_incidents_data)


def runbook(service: str) -> str:
    return record_event(
        "resource",
        "runbook://{service}",
        {"service": service},
        lambda: read_runbook_data(service),
    )
