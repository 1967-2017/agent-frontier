from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DATASET_URL = "https://raw.githubusercontent.com/usail-hkust/benchmark_inference_time_computation_LLM/011e76db/data/gsm8k/gsmhardv2.jsonl"
DEFAULT_QUESTIONS = 10
SUPPORTED_QUESTION_COUNTS = {2, 10, 100}
DEEPSEEK_REASONING_EFFORT = "high"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


load_dotenv(project_root() / ".env")


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    api_key_env: str
    base_url_env: str
    native_thinking: bool
    thinking_format: str | None = None

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "")

    @property
    def base_url(self) -> str:
        return os.getenv(self.base_url_env, "")


MODELS = [
    ModelConfig(
        provider="openai",
        model="gpt-5.5",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        native_thinking=False,
    ),
    ModelConfig(
        provider="deepseek",
        model="deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url_env="DEEPSEEK_BASE_URL",
        native_thinking=True,
        thinking_format="openai",
    ),
]

VIRTUAL_PRICING = {
    "gpt-5.5": {"input_per_1m": 4.00, "output_per_1m": 12.00, "thinking_per_1m": 12.00},
    "deepseek-v4-pro": {"input_per_1m": 0.60, "output_per_1m": 2.20, "thinking_per_1m": 2.20},
}


def data_dir() -> Path:
    return project_root() / "data"


def outputs_dir() -> Path:
    return project_root() / "outputs"


def runs_dir() -> Path:
    return outputs_dir() / "runs"


def latest_path() -> Path:
    return outputs_dir() / "latest.json"


def request_timeout() -> float:
    return float(os.getenv("DEMO2_REQUEST_TIMEOUT", "120"))
