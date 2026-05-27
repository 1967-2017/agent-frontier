from __future__ import annotations

from demo3_browser_agent.schemas import AgentDecision, TaskValidationResult
from demo3_browser_agent.tasks.base import TaskContext, missing_fields, write_rows_csv


class LocalFormTask:
    id = "local-form"
    name = "Local form branch decision"
    start_url = "http://127.0.0.1:8765"
    artifact_name = "local_form_submission.csv"
    max_retries = 1

    def instruction(self) -> str:
        return """
Complete the local support intake form shown in the browser.
Read the visible account tier and incident severity from the page.
Fill requester name, service, summary, and choose the escalation route based on the visible facts:
priority escalation is appropriate only when the page indicates an Enterprise account and High severity; otherwise choose standard queue.
When requester, service, summary, and the correct route are filled or selected, submit the form. Before submit, mark the action as danger=true.
Do not click a route again when its mark text already shows checked=true.
After the page shows a confirmation number, return action_type=finish with one row containing requester, service, route, confirmation, and summary.
Do not choose the branch from hidden assumptions; use the visible page content.
""".strip()

    async def prepare(self, context: TaskContext) -> None:
        return None

    async def validate_finish(self, decision: AgentDecision, context: TaskContext) -> TaskValidationResult:
        fields = ["requester", "service", "route", "confirmation", "summary"]
        if len(decision.rows) != 1:
            return TaskValidationResult(passed=False, message=f"expected one submission row, got {len(decision.rows)}")
        missing = missing_fields(decision.rows, fields)
        if missing:
            return TaskValidationResult(passed=False, message="missing fields: " + "; ".join(missing))
        path = context.artifact_dir / self.artifact_name
        write_rows_csv(path, fields, decision.rows)
        return TaskValidationResult(passed=True, message="wrote local form submission CSV", artifact_paths=[str(path)])
