from __future__ import annotations

import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from demo3_browser_agent.config import browser_task_goal
from demo3_browser_agent.schemas import AgentDecision, AgentObservation, BrowserActionType, TaskValidationResult
from demo3_browser_agent.tasks.base import TaskContext


class EbayTask:
    id = "ebay"
    name = "Shopping product detail screenshots"
    artifact_name = "product_screenshots.json"
    max_retries = 1

    def __init__(self, site_url: str | None = None, query: str | None = None, sort_goal: str | None = None, target_count: int | None = None):
        self.start_url = site_url or browser_task_goal(self.id, "site_url")
        self.query = query or browser_task_goal(self.id, "query")
        self.sort_goal = sort_goal or browser_task_goal(self.id, "sort_goal")
        count_value = str(target_count) if target_count is not None else browser_task_goal(self.id, "target_count")
        if not self.start_url or not self.query or not self.sort_goal or not count_value:
            raise RuntimeError("ebay task requires DEMO3_EBAY_SITE_URL, DEMO3_EBAY_QUERY, DEMO3_EBAY_SORT_GOAL, and DEMO3_EBAY_TARGET_COUNT or constructor arguments")
        self.target_count = int(count_value)
        self.product_urls: list[str] = []
        self.screenshots: list[str] = []
        self.last_result_click_signature: str = ""
        self.repeated_result_clicks = 0
        self.last_results_url = ""

    def instruction(self) -> str:
        return f"""
Use the browser on the shopping site to collect product detail screenshots.
Search query: {self.query}
Sort goal: {self.sort_goal}
Target count: {self.target_count} product detail pages.

Use visual grounding only: click and type actions must use Set-of-Mark mark_id values from the current observation. Never infer or invent pixel coordinates.
After sorting, choose the visible product results in top-to-bottom order. Skip only listings whose own visible card content clearly identifies them as non-organic listings; do not infer that a product is non-organic from unrelated page regions.
For each selected product, open its detail page, wait until the detail page is visibly loaded, allow the app to save the observation screenshot, then return to the sorted results page and continue with the next unvisited top-to-bottom result.
Do not sign in, add to cart, bid, buy, make an offer, checkout, contact sellers, or enter any payment or irreversible flow.
If a click leaves you on the same results page, do not repeat the same mark; choose another marked link for the intended product or continue to the next visible result.
Finish only after the required number of distinct product detail pages has been recorded.
""".strip()

    def instruction_for_observation(self, observation: AgentObservation) -> str:
        self._record_detail_observation(observation)
        marks = _mark_summary(observation)
        repeat_warning = _repeat_warning(self.last_result_click_signature, self.repeated_result_clicks)
        screenshots = "\n".join(self.screenshots[-self.target_count:]) or "none yet"
        product_urls = "\n".join(self.product_urls[-self.target_count:]) or "none yet"
        return f"""
{self.instruction()}

Current progress: {len(self.product_urls)} distinct product detail pages recorded; need {self.target_count}.
Recorded product URLs:
{product_urls}
Latest detail screenshot paths:
{screenshots}
{repeat_warning}

Available Set-of-Mark controls and links for this observation, in screen order:
{marks}
""".strip()

    async def prepare(self, context: TaskContext) -> None:
        self.product_urls = []
        self.screenshots = []
        self.last_result_click_signature = ""
        self.repeated_result_clicks = 0
        self.last_results_url = ""
        return None

    def adjust_decision(self, decision: AgentDecision, observation: AgentObservation) -> AgentDecision:
        if not _looks_like_results_page(observation):
            self.repeated_result_clicks = 0
            return decision
        self.last_results_url = observation.url
        if decision.action_type != BrowserActionType.click or decision.mark_id is None:
            return decision
        mark = next((candidate for candidate in observation.marks if candidate.id == decision.mark_id), None)
        signature = _click_signature(observation.url, mark)
        if signature and signature == self.last_result_click_signature:
            self.repeated_result_clicks += 1
            return AgentDecision(
                thought="The same marked result-page element was selected again without leaving the results page, so I will pause and reassess the visible marks instead of repeating it.",
                action_type=BrowserActionType.wait,
                seconds=1,
            )
        self.last_result_click_signature = signature
        self.repeated_result_clicks = 0
        return decision

    async def validate_finish(self, decision: AgentDecision, context: TaskContext) -> TaskValidationResult:
        if len(self.product_urls) < self.target_count:
            return TaskValidationResult(passed=False, message=f"expected {self.target_count} distinct product detail URLs, got {len(self.product_urls)}")
        if len(set(self.screenshots)) < self.target_count:
            return TaskValidationResult(passed=False, message=f"expected {self.target_count} detail screenshot paths, got {len(set(self.screenshots))}")
        path = context.artifact_dir / self.artifact_name
        manifest = {
            "site": _host(self.start_url),
            "query": self.query,
            "sort_goal": self.sort_goal,
            "target_count": self.target_count,
            "product_urls": self.product_urls[: self.target_count],
            "screenshots": self.screenshots[: self.target_count],
            "summary": decision.summary or f"Recorded {len(self.product_urls[: self.target_count])} product detail screenshots.",
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return TaskValidationResult(passed=True, message="wrote product detail screenshot manifest", artifact_paths=[str(path), *self.screenshots[: self.target_count]])

    def _record_detail_observation(self, observation: AgentObservation) -> None:
        normalized = _normalize_detail_url(observation.url, self.start_url, self.last_results_url)
        if not normalized or normalized in self.product_urls:
            return
        self.product_urls.append(normalized)
        self.screenshots.append(observation.screenshot_path)


def _looks_like_results_page(observation: AgentObservation) -> bool:
    parts = urlsplit(observation.url)
    query_keys = {key for key, _ in parse_qsl(parts.query, keep_blank_values=True)}
    return bool(parts.netloc and (query_keys or parts.path.strip("/"))) and not _looks_like_home_page(observation.url)


def _looks_like_home_page(url: str) -> bool:
    parts = urlsplit(url)
    return parts.path in {"", "/"} and not parts.query


def _normalize_detail_url(url: str, start_url: str, last_results_url: str) -> str:
    parts = urlsplit(url)
    if not parts.netloc or _host(url) != _host(start_url):
        return ""
    if _looks_like_home_page(url):
        return ""
    if last_results_url and _same_document(url, last_results_url):
        return ""
    clean_query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if _stable_query_key(key)]
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(clean_query), ""))


def _same_document(left: str, right: str) -> bool:
    left_parts = urlsplit(left)
    right_parts = urlsplit(right)
    return (left_parts.netloc.lower(), left_parts.path.rstrip("/"), left_parts.query) == (right_parts.netloc.lower(), right_parts.path.rstrip("/"), right_parts.query)


def _stable_query_key(key: str) -> bool:
    lowered = key.lower()
    return not (lowered.startswith("_") or lowered in {"hash", "campid", "mkcid", "mkevt", "toolid", "customid"})


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower()


def _click_signature(url: str, mark) -> str:
    if not mark:
        return ""
    text = " ".join((mark.text or "").split()).lower()
    x, y, width, height = mark.bbox
    return f"{url}|{mark.id}|{round(y)}|{text[:80]}"


def _repeat_warning(signature: str, count: int) -> str:
    if not signature or count <= 0:
        return ""
    return "Previous click selected the same marked element and stayed on the results page. Choose a different visible mark rather than repeating it."


def _mark_summary(observation: AgentObservation) -> str:
    if not observation.marks:
        return "No marks available. Use wait or scroll; do not guess coordinates."
    sorted_marks = sorted(observation.marks, key=lambda mark: (mark.bbox[1], mark.bbox[0], mark.id))
    lines = []
    for mark in sorted_marks:
        text = " ".join((mark.text or "").split())[:90]
        role = mark.role or ""
        tag = mark.tag or ""
        lines.append(f"{mark.id}: tag={tag} role={role} text={text}")
    return "\n".join(lines[:120])
