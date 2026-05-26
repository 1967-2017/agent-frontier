from __future__ import annotations

from demo2_reasoning.config import MODELS, ModelConfig
from demo2_reasoning.providers.openai_compatible import OpenAICompatibleProvider


def model_configs() -> list[ModelConfig]:
    return list(MODELS)


def provider_for(config: ModelConfig) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(config)
