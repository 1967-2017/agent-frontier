from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from demo3_browser_agent.schemas import AgentObservation, ProviderResponse


@dataclass(frozen=True)
class DecisionRequest:
    task_id: str
    task_name: str
    task_instruction: str
    run_dir: Path
    observation: AgentObservation
    previous_error: str | None = None


class VisionProvider(Protocol):
    async def decide(self, request: DecisionRequest) -> ProviderResponse: ...
