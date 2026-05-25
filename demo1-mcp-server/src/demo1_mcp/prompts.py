from __future__ import annotations

from .trace import record_event


def oncall_triage(service: str) -> str:
    def build() -> str:
        return f"""You are the on-call triage assistant for service: {service}.

Use the available MCP tools and resources to investigate:
1. Read incident://list to identify active incidents for {service}.
2. Read runbook://{service} for service-specific mitigation steps.
3. Call query_metric({service}, relevant metrics, relevant windows) to inspect symptoms.
4. Call tail_log({service}, relevant line count, relevant severity) to inspect recent errors.
5. If mitigation is needed, call restart_service({service}) first with dry_run=true.
6. Only call restart_service({service}, dry_run=false) after explicit operator confirmation.
7. If human escalation is needed, call notify_oncall({service}, summary, severity).

Return a concise triage summary with evidence, suspected cause, and recommended next action."""

    return record_event(
        "prompt",
        "oncall-triage",
        {"service": service},
        build,
    )
