from __future__ import annotations

from pydantic import BaseModel, Field


class Problem(BaseModel):
    id: str
    question: str
    answer: str
    source: str = "gsmhardv2"
    metadata: dict = Field(default_factory=dict)


class ModelCallSpec(BaseModel):
    strategy: str
    provider: str
    model: str
    question_id: str
    sample_index: int
    messages: list[dict]
    temperature: float
    max_tokens: int
    native_thinking: bool = False
    reasoning_effort: str | None = None


class ProviderResponse(BaseModel):
    text: str
    latency_ms: int
    raw: dict = Field(default_factory=dict)


class ModelCallResult(BaseModel):
    provider: str
    model: str
    strategy: str
    question_id: str
    sample_index: int
    prompt: str
    output_text: str
    extracted_answer: str | None
    target_answer: str
    correct: bool
    latency_ms: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_thinking_tokens: int
    estimated_cost_usd: float
    status: str
    error: str | None = None


class StrategyModelSummary(BaseModel):
    strategy: str
    model: str
    provider: str
    status: str
    total: int
    completed: int
    correct: int
    accuracy: float | None
    avg_thinking_tokens: float | None
    avg_wall_time_s: float | None
    cost_per_question: float | None
    note: str = ""
