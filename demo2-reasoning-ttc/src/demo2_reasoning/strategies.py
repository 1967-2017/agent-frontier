from __future__ import annotations

from dataclasses import dataclass

from .config import DEEPSEEK_REASONING_EFFORT, ModelConfig
from .schemas import ModelCallSpec, Problem


@dataclass(frozen=True)
class Strategy:
    name: str
    temperature: float
    max_tokens: int
    samples: int
    native_thinking: bool = False

    def supports_model(self, model_config: ModelConfig) -> tuple[bool, str]:
        if self.native_thinking and not model_config.native_thinking:
            return False, "model does not advertise native thinking capability"
        return True, ""

    def prompt(self, problem: Problem) -> str:
        if self.name == "Baseline":
            return (
                "You are solving a math word problem.\n\n"
                "Return only the final numeric answer.\n"
                "Do not include reasoning steps.\n\n"
                f"Problem:\n{problem.question}"
            )
        if self.name == "CoT":
            return (
                "You are solving a math word problem.\n\n"
                "Think step by step, then give the final answer in the format:\n"
                "Final answer: <number>\n\n"
                f"Problem:\n{problem.question}"
            )
        if self.name == "Native Thinking":
            return (
                "You are solving a math word problem.\n\n"
                "Use your native reasoning mode if available.\n"
                "Return the final answer in the format:\n"
                "Final answer: <number>\n\n"
                f"Problem:\n{problem.question}"
            )
        if self.name == "BoN=5 + SC":
            return (
                "You are solving a math word problem.\n\n"
                "Think step by step, then give the final answer in the format:\n"
                "Final answer: <number>\n\n"
                f"Problem:\n{problem.question}"
            )
        raise ValueError(f"unknown strategy: {self.name}")

    def build_specs(self, problem: Problem, model_config: ModelConfig) -> list[ModelCallSpec]:
        prompt = self.prompt(problem)
        reasoning_effort = DEEPSEEK_REASONING_EFFORT if self.native_thinking else None
        return [
            ModelCallSpec(
                strategy=self.name,
                provider=model_config.provider,
                model=model_config.model,
                question_id=problem.id,
                sample_index=index + 1,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                native_thinking=self.native_thinking,
                reasoning_effort=reasoning_effort,
            )
            for index in range(self.samples)
        ]


STRATEGIES = [
    Strategy("Baseline", temperature=0.0, max_tokens=256, samples=1),
    Strategy("CoT", temperature=0.0, max_tokens=1024, samples=1),
    Strategy("Native Thinking", temperature=0.0, max_tokens=1024, samples=1, native_thinking=True),
    Strategy("BoN=5 + SC", temperature=0.7, max_tokens=1024, samples=5),
]
