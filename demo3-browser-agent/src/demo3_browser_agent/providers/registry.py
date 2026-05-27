from __future__ import annotations

from demo3_browser_agent.config import model_config
from demo3_browser_agent.providers.openai_compatible_vision import OpenAICompatibleVisionProvider


def provider_for_env() -> OpenAICompatibleVisionProvider:
    return OpenAICompatibleVisionProvider(model_config())
