from __future__ import annotations

from typing import Protocol

from demo2_reasoning.config import ModelConfig
from demo2_reasoning.schemas import ModelCallSpec, ProviderResponse


class Provider(Protocol):
    config: ModelConfig

    async def complete(self, spec: ModelCallSpec) -> ProviderResponse:
        ...
