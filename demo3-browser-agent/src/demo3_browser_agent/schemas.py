from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    interrupted = "interrupted"


class BrowserActionType(str, Enum):
    click = "click"
    type = "type"
    press = "press"
    scroll = "scroll"
    wait = "wait"
    navigate = "navigate"
    finish = "finish"
    fail = "fail"


class Mark(BaseModel):
    id: int
    role: str | None = None
    text: str | None = None
    tag: str | None = None
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    selector: str | None = None


class AgentObservation(BaseModel):
    step: int
    url: str
    title: str
    screenshot_path: str
    marked_screenshot_path: str
    marks: list[Mark] = Field(default_factory=list)
    visible_text: str = ""


class AgentDecision(BaseModel):
    thought: str
    action_type: BrowserActionType
    mark_id: int | None = None
    text: str | None = None
    key: str | None = None
    url: str | None = None
    direction: str | None = None
    seconds: float | None = None
    danger: bool = False
    done: bool = False
    confidence: float | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None

    @field_validator("rows", mode="before")
    @classmethod
    def none_rows_to_empty(cls, value):
        return [] if value is None else value


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0
    estimated: bool = True


class ProviderResponse(BaseModel):
    decision: AgentDecision
    latency_ms: int
    raw: dict[str, Any] = Field(default_factory=dict)
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = 0.0


class TaskValidationResult(BaseModel):
    passed: bool
    message: str
    artifact_paths: list[str] = Field(default_factory=list)


class TaskState(BaseModel):
    id: str
    name: str
    status: TaskStatus = TaskStatus.pending
    attempt: int = 0
    step: int = 0
    message: str = ""


class RunState(BaseModel):
    run_id: str
    mode: str = "interactive"
    status: TaskStatus = TaskStatus.running
    current_scenario: str | None = None
    current_task: str | None = None
    current_url: str = ""
    current_screenshot: str = ""
    current_marked_screenshot: str = ""
    current_thought: str = ""
    current_action: str = ""
    step: int = 0
    max_steps: int = 30
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    tasks: dict[str, TaskState] = Field(default_factory=dict)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
