from __future__ import annotations

import os
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[2]
ENV = dotenv_values(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        value = ENV.get(name)
    if value is None:
        return default
    return str(value)


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    api_key_env: str
    base_url_env: str

    @property
    def api_key(self) -> str:
        return _env(self.api_key_env, "")

    @property
    def base_url(self) -> str:
        value = _env(self.base_url_env, "")
        if value:
            return value
        if self.provider == "openai":
            return "https://api.openai.com/v1"
        return ""


MODEL_CONFIGS = {
    "openai": ModelConfig("openai", _env("DEMO3_MODEL", "gpt-5.4"), "OPENAI_API_KEY", "OPENAI_BASE_URL"),
    "deepseek": ModelConfig("deepseek", "DeepSeek-V4-Pro", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL"),
}

DEFAULT_BLACKLIST = [
    "*/login*",
    "*/signin*",
    "*/checkout*",
    "*/payment*",
    "*/billing*",
    "*/account/delete*",
    "*/settings/security*",
    "https://accounts.google.com/*",
    "https://login.microsoftonline.com/*",
]


def project_root() -> Path:
    return ROOT


def outputs_dir() -> Path:
    return ROOT / "outputs"


def runs_dir() -> Path:
    return outputs_dir() / "runs"


def latest_path() -> Path:
    return outputs_dir() / "latest.json"


def top_level_trace_path() -> Path:
    return ROOT / "trace.jsonl"


def dashboard_port() -> int:
    return int(_env("DEMO3_DASHBOARD_PORT", "8503"))


def max_steps() -> int:
    return min(int(_env("DEMO3_MAX_STEPS", "30")), 30)


def browser_headless() -> bool:
    return _env("DEMO3_BROWSER_HEADLESS", "false").lower() in {"1", "true", "yes"}


def request_timeout() -> float:
    return float(_env("DEMO3_REQUEST_TIMEOUT", "120"))


def dashboard_refresh_seconds() -> float:
    return max(float(_env("DEMO3_DASHBOARD_REFRESH_SECONDS", "1.5")), 0.2)


def token_price_per_million() -> tuple[float, float]:
    """Return configured (input, output) prices per 1M tokens in USD.

    OpenAI-compatible gateways and custom model names such as gpt-5.5 do not
    expose reliable price metadata in chat responses, so cost is estimated only
    when the user configures explicit prices.
    """
    return (
        float(_env("DEMO3_INPUT_PRICE_PER_1M", "0")),
        float(_env("DEMO3_OUTPUT_PRICE_PER_1M", "0")),
    )


def selected_provider() -> str:
    return _env("DEMO3_PROVIDER", "openai").strip().lower()


def model_config() -> ModelConfig:
    provider = selected_provider()
    if provider not in MODEL_CONFIGS:
        raise RuntimeError(f"unsupported DEMO3_PROVIDER: {provider}")
    config = MODEL_CONFIGS[provider]
    if provider == "openai":
        return ModelConfig(provider, _env("DEMO3_MODEL", config.model), config.api_key_env, config.base_url_env)
    return config


def browser_task_goal(task_id: str, field: str, default: str = "") -> str:
    key = f"DEMO3_{task_id.replace('-', '_').upper()}_{field.upper()}"
    return _env(key, default)


def browser_task_target_count(task_id: str, default: int = 3) -> int:
    key = f"DEMO3_{task_id.replace('-', '_').upper()}_TARGET_COUNT"
    return int(_env(key, str(default)))


def blacklist_patterns() -> list[str]:
    raw = _env("DEMO3_BLACKLIST_URLS", "")
    patterns = [part.strip() for part in raw.split(",") if part.strip()]
    return patterns or DEFAULT_BLACKLIST


def is_blacklisted_url(url: str) -> bool:
    return any(fnmatch(url, pattern) for pattern in blacklist_patterns())
