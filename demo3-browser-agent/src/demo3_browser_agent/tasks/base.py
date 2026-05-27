from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from demo3_browser_agent.schemas import AgentDecision, AgentObservation, TaskValidationResult


@dataclass(frozen=True)
class TaskContext:
    run_dir: Path
    artifact_dir: Path


class BrowserTask(Protocol):
    id: str
    name: str
    start_url: str
    artifact_name: str | None
    max_retries: int

    def instruction(self) -> str: ...

    def instruction_for_observation(self, observation: AgentObservation) -> str: ...

    async def prepare(self, context: TaskContext) -> None: ...

    async def validate_finish(self, decision: AgentDecision, context: TaskContext) -> TaskValidationResult: ...


def write_rows_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def missing_fields(rows: list[dict], fields: list[str]) -> list[str]:
    missing = []
    for index, row in enumerate(rows, start=1):
        for field in fields:
            if not str(row.get(field, "")).strip():
                missing.append(f"row {index}: {field}")
    return missing
