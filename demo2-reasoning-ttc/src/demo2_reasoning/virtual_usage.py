from __future__ import annotations

import math

from .config import VIRTUAL_PRICING


def estimate_tokens(prompt: str, output: str, strategy: str) -> tuple[int, int, int]:
    input_tokens = max(1, math.ceil(len(prompt) / 4))
    output_tokens = max(1, math.ceil(len(output) / 4))
    if strategy == "CoT":
        output_tokens = math.ceil(output_tokens * 1.15)
    elif strategy == "BoN=5 + SC":
        output_tokens = math.ceil(output_tokens * 1.10)
    if strategy == "Native Thinking":
        output_tokens = math.ceil(output_tokens * 0.90)
        thinking_tokens = math.ceil((input_tokens + output_tokens) * 0.65)
    else:
        thinking_tokens = output_tokens
    return input_tokens, output_tokens, thinking_tokens


def estimate_cost(model: str, input_tokens: int, output_tokens: int, thinking_tokens: int) -> float:
    pricing = VIRTUAL_PRICING[model]
    return round(
        input_tokens / 1_000_000 * pricing["input_per_1m"]
        + output_tokens / 1_000_000 * pricing["output_per_1m"]
        + thinking_tokens / 1_000_000 * pricing["thinking_per_1m"],
        8,
    )
