from __future__ import annotations

from demo3_browser_agent.schemas import AgentDecision, TaskValidationResult
from demo3_browser_agent.tasks.base import TaskContext, missing_fields, write_rows_csv


class NetworkDropTask:
    id = "network-drop"
    name = "Network drop local form recovery"
    start_url = "http://127.0.0.1:8765/network-drop"
    artifact_name = "network_drop_submission.csv"
    max_retries = 1

    def instruction(self) -> str:
        return """
Complete the local support intake form shown in the browser.
This page intentionally simulates a five second network outage on the first submit attempt.
If the submit fails or the page reports that the network is unavailable, wait briefly and retry the submit without crashing.
Use the visible facts to choose the route: priority escalation only when Enterprise account and High severity are visible; otherwise choose standard queue.
After the page shows a confirmation number, return action_type=finish with one row containing requester, service, route, confirmation, and summary.
""".strip()

    def instruction_for_observation(self, observation):
        return self.instruction()

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
        return TaskValidationResult(passed=True, message="wrote network drop submission CSV", artifact_paths=[str(path)])
