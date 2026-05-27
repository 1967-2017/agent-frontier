from __future__ import annotations

from demo3_browser_agent.schemas import AgentDecision, AgentObservation, TaskValidationResult
from demo3_browser_agent.tasks.base import TaskContext, missing_fields, write_rows_csv


class ArxivTask:
    id = "arxiv"
    name = "arXiv MCP protocol search"
    start_url = "https://arxiv.org"
    artifact_name = "arxiv_mcp_protocol.csv"
    max_retries = 1

    def __init__(self):
        self.seen_text: list[str] = []

    def instruction(self) -> str:
        return """
Use the browser to search arXiv for MCP protocol. Collect the first five search results from the results page.
The arXiv results page shows title, authors, and abstract snippets directly. If an abstract first sentence is truncated, click that result's More link before recording it.
If fewer than five complete results are visible in the current viewport, scroll down and continue collecting; do not finish until five rows are available.
For each result, extract title, authors, abstract_first_sentence, and url.
When complete, return action_type=finish with rows containing exactly those fields.
Do not invent missing data; use visible page text and accumulated seen result text only.
""".strip()

    def instruction_for_observation(self, observation: AgentObservation) -> str:
        if "arxiv" in observation.url.lower() and observation.visible_text:
            self._remember_visible_text(observation.visible_text)
        seen = "\n---\n".join(self.seen_text[-4:])
        if not seen:
            return self.instruction()
        return f"""
{self.instruction()}

Accumulated arXiv result text seen so far across scrolls:
{seen[:6000]}
""".strip()

    async def prepare(self, context: TaskContext) -> None:
        self.seen_text = []
        return None

    def _remember_visible_text(self, text: str) -> None:
        excerpt = _result_text_excerpt(text)
        if excerpt and excerpt not in self.seen_text:
            self.seen_text.append(excerpt)

    async def validate_finish(self, decision: AgentDecision, context: TaskContext) -> TaskValidationResult:
        fields = ["title", "authors", "abstract_first_sentence", "url"]
        if len(decision.rows) < 5:
            return TaskValidationResult(passed=False, message=f"expected 5 rows, got {len(decision.rows)}")
        rows = decision.rows[:5]
        missing = missing_fields(rows, fields)
        if missing:
            return TaskValidationResult(passed=False, message="missing fields: " + "; ".join(missing[:5]))
        path = context.artifact_dir / self.artifact_name
        write_rows_csv(path, fields, rows)
        return TaskValidationResult(passed=True, message="wrote arXiv results CSV", artifact_paths=[str(path)])


def _result_text_excerpt(text: str) -> str:
    marker = "Showing "
    start = text.find(marker)
    if start == -1:
        start = text.find("arXiv:")
    if start == -1:
        return ""
    return text[start:][:3000]
