from __future__ import annotations

import base64
import json
import re
import time

from openai import AsyncOpenAI

from demo3_browser_agent.config import ModelConfig, request_timeout, token_price_per_million
from demo3_browser_agent.providers.base import DecisionRequest
from demo3_browser_agent.schemas import AgentDecision, ProviderResponse, TokenUsage


class OpenAICompatibleVisionProvider:
    def __init__(self, config: ModelConfig):
        self.config = config
        self._client: AsyncOpenAI | None = None

    def _client_for_request(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        return self._client

    async def decide(self, request: DecisionRequest) -> ProviderResponse:
        if not self.config.api_key:
            raise RuntimeError(f"missing API key env: {self.config.api_key_env}")
        if not self.config.base_url:
            raise RuntimeError(f"missing base URL env: {self.config.base_url_env}")

        image_path = request.run_dir / request.observation.marked_screenshot_path
        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        content = [
            {"type": "text", "text": _prompt(request)},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
        ]
        body = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "max_tokens": 1200,
        }
        started = time.perf_counter()
        client = self._client_for_request()
        response = await client.chat.completions.create(
            model=body["model"],
            messages=body["messages"],
            temperature=body["temperature"],
            max_tokens=body["max_tokens"],
            timeout=request_timeout(),
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        text, usage, raw_response = _normalize_response(response)
        decision = AgentDecision.model_validate_json(_extract_json(text))
        tokens = TokenUsage(
            input=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            output=int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            estimated=not bool(usage),
        )
        input_price, output_price = token_price_per_million()
        cost_usd = (tokens.input * input_price + tokens.output * output_price) / 1_000_000
        return ProviderResponse(
            decision=decision,
            latency_ms=latency_ms,
            raw={"provider": self.config.provider, "model": self.config.model, "response_type": type(response).__name__, "usage": usage, "response": raw_response},
            tokens=tokens,
            cost_usd=cost_usd,
        )


SYSTEM_PROMPT = """You are a browser computer-use agent. Decide one safe next action from the marked screenshot and mark list. Use mark IDs, never raw coordinates. Return JSON only. Every nullable field must be null when unused, except rows which must always be an array; use rows: [] for non-finish actions."""


def _prompt(request: DecisionRequest) -> str:
    marks = [mark.model_dump(mode="json") for mark in request.observation.marks]
    schema = {
        "thought": "one sentence explaining the next action",
        "action_type": "click | type | press | scroll | wait | navigate | finish | fail",
        "mark_id": "integer mark id for click/type, or null",
        "text": "text for type, or null",
        "key": "keyboard key for press, or null",
        "url": "url for navigate, or null",
        "direction": "up or down for scroll, or null",
        "seconds": "seconds for wait, or null",
        "danger": "true before submit/save/delete/confirm/close actions",
        "done": "true only when finishing the task",
        "confidence": "0.0 to 1.0",
        "rows": "always an array; [] for non-finish actions; structured rows only for finish actions",
        "summary": "brief result or failure reason",
    }
    previous_error = f"\nPrevious error to correct: {request.previous_error}" if request.previous_error else ""
    return f"""
Task: {request.task_name}
Instruction: {request.task_instruction}
Current URL: {request.observation.url}
Current title: {request.observation.title}
Step: {request.observation.step}
Visible text from current viewport:
{request.observation.visible_text[:4000]}
Available marks JSON:
{json.dumps(marks, ensure_ascii=False, indent=2)}
{previous_error}

Return exactly one JSON object matching this schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}
""".strip()


def _normalize_response(response) -> tuple[str, dict, object]:
    """Return (message_text, usage_dict, JSON-safe raw excerpt).

    Some OpenAI-compatible gateways return the official SDK object, some return a
    plain dict, and a few wrappers return a JSON string or even the assistant text
    directly. Demo 3 accepts all of those shapes so provider differences do not
    crash the agent before the model decision can be parsed.
    """
    if isinstance(response, str):
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            return response, {}, response[:1000]
        text, usage, raw = _normalize_response(parsed)
        return text, usage, raw

    if isinstance(response, dict):
        usage = response.get("usage") or {}
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content") or message.get("reasoning_content") or choices[0].get("text") or ""
            return _content_to_text(content), usage, _raw_excerpt(response)
        if "content" in response:
            return _content_to_text(response.get("content")), usage, _raw_excerpt(response)
        if "text" in response:
            return str(response.get("text") or ""), usage, _raw_excerpt(response)
        return json.dumps(response, ensure_ascii=False), usage, _raw_excerpt(response)

    usage_obj = getattr(response, "usage", None)
    usage = _usage_to_dict(usage_obj)
    choices = getattr(response, "choices", None) or []
    if choices:
        choice = choices[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None) if message else getattr(choice, "text", "")
        return _content_to_text(content), usage, _raw_excerpt(response)
    content = getattr(response, "content", None)
    if content is not None:
        return _content_to_text(content), usage, _raw_excerpt(response)
    text = getattr(response, "text", None)
    if text is not None:
        return str(text), usage, _raw_excerpt(response)
    return str(response), usage, _raw_excerpt(response)


def _usage_to_dict(usage) -> dict:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
        "completion_tokens": getattr(usage, "completion_tokens", 0),
    }


def _content_to_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(getattr(item, "text", item)))
        return "".join(parts)
    return str(content)


def _raw_excerpt(response) -> object:
    try:
        if hasattr(response, "model_dump"):
            data = response.model_dump()
        else:
            data = response
        text = json.dumps(data, ensure_ascii=False, default=str)
        return json.loads(text[:2000]) if text.startswith("{") and len(text) <= 2000 else text[:2000]
    except Exception:
        return str(response)[:2000]


def _extract_json(text: str) -> str:
    stripped = text.strip()
    lower = stripped.lower()
    if lower.startswith("<!doctype html") or lower.startswith("<html"):
        raise RuntimeError(
            "模型接口返回了 HTML 页面，而不是模型 JSON。请检查 DEMO3_PROVIDER 对应的 *_BASE_URL 是否为 OpenAI-compatible API 地址，"
            "例如 https://api.openai.com/v1 或你的中转服务 /v1 地址；不要填写网页控制台、聊天页面或普通站点首页。"
        )
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.S)
    if match:
        return match.group(1)
    match = re.search(r"\{.*\}", stripped, flags=re.S)
    if match:
        return match.group(0)
    raise RuntimeError(f"model did not return JSON: {text[:200]}")
