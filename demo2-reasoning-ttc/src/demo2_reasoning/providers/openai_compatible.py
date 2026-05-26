from __future__ import annotations

import time
from urllib.parse import urljoin

import httpx

from demo2_reasoning.config import ModelConfig, request_timeout
from demo2_reasoning.schemas import ModelCallSpec, ProviderResponse


class OpenAICompatibleProvider:
    def __init__(self, config: ModelConfig):
        self.config = config

    def _endpoint(self) -> str:
        base = self.config.base_url.rstrip("/") + "/"
        return urljoin(base, "chat/completions")

    async def complete(self, spec: ModelCallSpec) -> ProviderResponse:
        if not self.config.api_key:
            raise RuntimeError(f"missing API key env: {self.config.api_key_env}")
        if not self.config.base_url:
            raise RuntimeError(f"missing base URL env: {self.config.base_url_env}")
        body = {
            "model": spec.model,
            "messages": spec.messages,
            "temperature": spec.temperature,
            "max_tokens": spec.max_tokens,
        }
        if self.config.provider == "deepseek":
            body["thinking"] = {"type": "enabled" if spec.native_thinking else "disabled"}
            if spec.native_thinking and spec.reasoning_effort:
                body["reasoning_effort"] = spec.reasoning_effort
        headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=request_timeout()) as client:
            response = await client.post(self._endpoint(), headers=headers, json=body)
            response.raise_for_status()
            raw = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        choices = raw.get("choices", [])
        if not choices:
            raise RuntimeError("provider response contained no choices")
        message = choices[0].get("message", {})
        text = message.get("content") or message.get("reasoning_content") or ""
        return ProviderResponse(text=text, latency_ms=latency_ms, raw={"provider": self.config.provider, "model": spec.model})
