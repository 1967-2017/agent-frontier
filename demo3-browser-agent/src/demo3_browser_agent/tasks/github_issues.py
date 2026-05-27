from __future__ import annotations

from demo3_browser_agent.schemas import AgentDecision, TaskValidationResult
from demo3_browser_agent.tasks.base import TaskContext, missing_fields, write_rows_csv


class GitHubIssuesTask:
    id = "github-issues"
    name = "GitHub open bug issues"
    start_url = "https://github.com/modelcontextprotocol/servers/issues"
    artifact_name = "github_bug_issues.csv"
    max_retries = 1

    def instruction(self) -> str:
        return """
Use the GitHub web UI for modelcontextprotocol/servers to find open issues with the bug label.
Collect every visible matching issue you can find from the filtered issue list.
For each issue, extract number, title, url, and labels.
When complete, return action_type=finish with rows containing exactly those fields.
If the page shows no matching open bug issues, finish with an empty rows array and a summary explaining that observation.
Do not use GitHub APIs or invent issues.
""".strip()

    async def prepare(self, context: TaskContext) -> None:
        return None

    async def validate_finish(self, decision: AgentDecision, context: TaskContext) -> TaskValidationResult:
        fields = ["number", "title", "url", "labels"]
        if decision.rows:
            missing = missing_fields(decision.rows, fields)
            if missing:
                return TaskValidationResult(passed=False, message="missing fields: " + "; ".join(missing[:5]))
        elif not decision.summary:
            return TaskValidationResult(passed=False, message="empty issue rows require a summary")
        path = context.artifact_dir / self.artifact_name
        write_rows_csv(path, fields, decision.rows)
        return TaskValidationResult(passed=True, message="wrote GitHub issues CSV", artifact_paths=[str(path)])
