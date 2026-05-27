from __future__ import annotations

from demo3_browser_agent.config import is_blacklisted_url
from demo3_browser_agent.schemas import AgentDecision, AgentObservation, BrowserActionType, Mark

DANGEROUS_TERMS = {
    "submit",
    "send",
    "save",
    "create",
    "delete",
    "confirm",
    "close",
    "checkout",
    "purchase",
}


class GuardrailError(RuntimeError):
    pass


class Guardrails:
    def __init__(self, max_steps: int):
        self.max_steps = min(max_steps, 30)

    def validate_step(self, step: int) -> None:
        if step > self.max_steps:
            raise GuardrailError(f"step limit exceeded: {step} > {self.max_steps}")

    def validate_url(self, url: str) -> None:
        if is_blacklisted_url(url):
            raise GuardrailError(f"blacklisted URL blocked: {url}")

    def validate_decision(self, decision: AgentDecision, observation: AgentObservation) -> None:
        if decision.action_type == BrowserActionType.navigate and decision.url:
            self.validate_url(decision.url)
        if decision.mark_id is not None and not _mark_by_id(observation.marks, decision.mark_id):
            raise GuardrailError(f"unknown mark_id: {decision.mark_id}")
        if decision.action_type in {BrowserActionType.click, BrowserActionType.type} and decision.mark_id is None:
            raise GuardrailError(f"{decision.action_type.value} requires mark_id")
        if decision.action_type == BrowserActionType.type and decision.text is None:
            raise GuardrailError("type requires text")
        if decision.action_type == BrowserActionType.press and not decision.key:
            raise GuardrailError("press requires key")

    def is_dangerous(self, decision: AgentDecision, observation: AgentObservation) -> bool:
        if decision.danger:
            return True
        if decision.action_type == BrowserActionType.finish:
            return False
        mark = _mark_by_id(observation.marks, decision.mark_id) if decision.mark_id else None
        parts = [decision.text, mark.text if mark else None, mark.role if mark else None, mark.tag if mark else None]
        text = " ".join(str(part) for part in parts if part).lower()
        return any(term in text for term in DANGEROUS_TERMS)


def _mark_by_id(marks: list[Mark], mark_id: int) -> Mark | None:
    return next((mark for mark in marks if mark.id == mark_id), None)
