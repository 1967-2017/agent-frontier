from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path

from demo3_browser_agent.browser.guardrails import GuardrailError, Guardrails
from demo3_browser_agent.browser.session import BrowserSession
from demo3_browser_agent.config import latest_path, max_steps, outputs_dir, runs_dir
from demo3_browser_agent.local_site.server import LocalSiteServer
from demo3_browser_agent.providers.base import DecisionRequest
from demo3_browser_agent.providers.registry import provider_for_env
from demo3_browser_agent.schemas import AgentDecision, BrowserActionType, RunState, TaskState, TaskStatus
from demo3_browser_agent.tasks import ArxivTask, EbayTask, GitHubIssuesTask, LocalFormTask, ModalWallTask, NetworkDropTask
from demo3_browser_agent.tasks.base import BrowserTask, TaskContext
from demo3_browser_agent.trace import TraceWriter, redact_secrets, write_json

TASKS = {
    "arxiv": ArxivTask,
    "ebay": EbayTask,
    "github-issues": GitHubIssuesTask,
    "local-form": LocalFormTask,
    "modal-wall": ModalWallTask,
    "network-drop": NetworkDropTask,
}

LOCAL_SITE_TASKS = {"local-form", "network-drop"}


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


async def run_demo3(
    task_ids: list[str] | None = None,
    check_browser: bool = False,
    check_sites: bool = False,
    step_override: int | None = None,
    mode: str = "interactive",
    current_scenario: str | None = None,
) -> Path:
    selected = task_ids or ["ebay", "github-issues", "local-form"]
    run_id = new_run_id()
    run_dir = runs_dir() / run_id
    artifact_dir = run_dir / "artifacts"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    writer = TraceWriter(run_dir)
    write_json(latest_path(), {"run_id": run_id, "run_dir": str(run_dir), "trace": str(run_dir / "trace.jsonl")})
    state = RunState(run_id=run_id, mode=mode, current_scenario=current_scenario, max_steps=step_override or max_steps())
    for task_id in selected:
        task = _task(task_id)
        state.tasks[task.id] = TaskState(id=task.id, name=task.name)
    _write_state(run_dir, state)
    writer.append("run_start", run_id=run_id, mode=mode, scenario_id=current_scenario, tasks=selected)

    browser = BrowserSession(headless=True if (check_browser or check_sites) else None)
    local_site = LocalSiteServer() if any(task_id in LOCAL_SITE_TASKS for task_id in selected) else None
    if local_site:
        local_site.start()
    try:
        await browser.start()
        if check_browser:
            await browser.goto("data:text/html,<button>Browser check</button><input placeholder='ok'>")
            observation = await browser.observe(run_dir, "check-browser", 1)
            writer.append("observation", run_id=run_id, task_id="check-browser", step=1, observation=observation)
            state.current_screenshot = observation.screenshot_path
            state.current_marked_screenshot = observation.marked_screenshot_path
            state.status = TaskStatus.passed
            _write_state(run_dir, state)
            return run_dir
        if check_sites:
            for task_id in ["ebay", "github-issues", "local-form"]:
                task = _task(task_id)
                if task_id in LOCAL_SITE_TASKS and not local_site:
                    local_site = LocalSiteServer()
                    local_site.start()
                await browser.goto(task.start_url)
                observation = await browser.observe(run_dir, task_id, 1)
                writer.append("site_check", run_id=run_id, task_id=task_id, url=observation.url, title=observation.title, marks=len(observation.marks), observation=observation)
                print(f"{task_id}: url={observation.url} title={observation.title!r} marks={len(observation.marks)}")
            state.status = TaskStatus.passed
            _write_state(run_dir, state)
            return run_dir

        provider = provider_for_env()
        guardrails = Guardrails(step_override or max_steps())
        context = TaskContext(run_dir=run_dir, artifact_dir=artifact_dir)
        for task_id in selected:
            task = _task(task_id)
            await _run_task(task, context, browser, provider, guardrails, writer, state, run_dir)
        state.status = TaskStatus.passed if all(task.status == TaskStatus.passed for task in state.tasks.values()) else TaskStatus.failed
        state.summary = _run_summary(state)
        writer.append("run_complete", run_id=run_id, mode=mode, scenario_id=current_scenario, status=state.status.value, summary=state.summary)
    except KeyboardInterrupt:
        state.status = TaskStatus.interrupted
        writer.append("interrupt", run_id=run_id)
    except Exception as exc:
        state.status = TaskStatus.failed
        writer.append("run_error", run_id=run_id, error=str(redact_secrets(str(exc))))
        raise
    finally:
        state.summary = _run_summary(state)
        _write_state(run_dir, state)
        await browser.close()
        if local_site:
            local_site.stop()
        writer.copy_to_latest()
        _write_summary(run_dir, state)
    return run_dir


async def _run_task(task: BrowserTask, context: TaskContext, browser: BrowserSession, provider, guardrails: Guardrails, writer: TraceWriter, state: RunState, run_dir: Path) -> None:
    task_state = state.tasks[task.id]
    await task.prepare(context)
    for attempt in range(task.max_retries + 1):
        task_state.status = TaskStatus.running
        task_state.attempt = attempt
        state.current_task = task.id
        _write_state(run_dir, state)
        writer.append("task_start", run_id=state.run_id, mode=state.mode, scenario_id=state.current_scenario, task_id=task.id, attempt=attempt, start_url=task.start_url)
        previous_error = None
        try:
            guardrails.validate_url(task.start_url)
            await browser.goto(task.start_url)
            guardrails.validate_url(browser.page.url if browser.page else task.start_url)
            for step in range(1, guardrails.max_steps + 1):
                guardrails.validate_step(step)
                task_state.step = step
                state.step = step
                observation = await browser.observe(run_dir, task.id, step)
                state.current_url = observation.url
                state.current_screenshot = observation.screenshot_path
                state.current_marked_screenshot = observation.marked_screenshot_path
                state.current_thought = "正在基于当前页面生成下一步决策。"
                state.current_action = ""
                _write_state(run_dir, state)
                writer.append("observation", run_id=state.run_id, mode=state.mode, scenario_id=state.current_scenario, task_id=task.id, attempt=attempt, step=step, observation=observation)
                instruction = task.instruction_for_observation(observation) if hasattr(task, "instruction_for_observation") else task.instruction()
                request = DecisionRequest(task.id, task.name, instruction, run_dir, observation, previous_error)
                response = await provider.decide(request)
                decision = response.decision
                state.current_thought = decision.thought
                state.current_action = decision.action_type.value
                state.total_input_tokens += response.tokens.input
                state.total_output_tokens += response.tokens.output
                state.total_cost_usd += response.cost_usd
                _write_state(run_dir, state)
                if hasattr(task, "adjust_decision"):
                    decision = task.adjust_decision(decision, observation)
                    state.current_thought = decision.thought
                    state.current_action = decision.action_type.value
                    _write_state(run_dir, state)
                writer.append("model_decision_end", run_id=state.run_id, mode=state.mode, scenario_id=state.current_scenario, task_id=task.id, attempt=attempt, step=step, decision=decision, tokens=response.tokens, cost_usd=response.cost_usd, latency_ms=response.latency_ms)
                guardrails.validate_decision(decision, observation)
                if guardrails.is_dangerous(decision, observation):
                    writer.append("action_planned", run_id=state.run_id, task_id=task.id, attempt=attempt, step=step, message="[ACTION] dangerous browser action planned", decision=decision)
                result = await browser.execute(decision, observation)
                writer.append("action_executed", run_id=state.run_id, task_id=task.id, attempt=attempt, step=step, result=result)
                if decision.action_type not in {BrowserActionType.finish, BrowserActionType.fail}:
                    updated_observation = await browser.observe(run_dir, task.id, step, suffix="_after")
                    state.current_url = updated_observation.url
                    state.current_screenshot = updated_observation.screenshot_path
                    state.current_marked_screenshot = updated_observation.marked_screenshot_path
                    state.current_thought = "页面已更新，等待下一步模型决策。"
                    state.current_action = ""
                _remember_event(state, {"task": task.id, "step": step, "thought": decision.thought, "action": decision.action_type.value})
                _write_state(run_dir, state)
                if decision.action_type == BrowserActionType.finish or decision.done:
                    validation = await task.validate_finish(decision, context)
                    task_state.message = validation.message
                    task_state.status = TaskStatus.passed if validation.passed else TaskStatus.failed
                    writer.append("task_passed" if validation.passed else "task_failed", run_id=state.run_id, mode=state.mode, scenario_id=state.current_scenario, task_id=task.id, attempt=attempt, validation=validation)
                    _write_state(run_dir, state)
                    if validation.passed:
                        return
                    previous_error = validation.message
                    break
                if decision.action_type == BrowserActionType.fail:
                    previous_error = decision.summary or "model failed task"
                    break
        except (GuardrailError, Exception) as exc:
            previous_error = str(redact_secrets(str(exc)))
            task_state.message = previous_error
            writer.append("task_attempt_error", run_id=state.run_id, task_id=task.id, attempt=attempt, error=previous_error)
        if attempt >= task.max_retries:
            task_state.status = TaskStatus.failed
            writer.append("task_failed", run_id=state.run_id, mode=state.mode, scenario_id=state.current_scenario, task_id=task.id, attempt=attempt, message=previous_error or "retry limit reached")
            _write_state(run_dir, state)
            return


def _task(task_id: str) -> BrowserTask:
    if task_id not in TASKS:
        raise RuntimeError(f"unknown task: {task_id}")
    return TASKS[task_id]()


def _run_summary(state: RunState) -> dict:
    tasks = list(state.tasks.values())
    passed = sum(1 for task in tasks if task.status == TaskStatus.passed)
    failed = sum(1 for task in tasks if task.status == TaskStatus.failed)
    interrupted = sum(1 for task in tasks if task.status == TaskStatus.interrupted)
    first_attempt_passed = sum(1 for task in tasks if task.status == TaskStatus.passed and task.attempt == 0)
    return {
        "status": state.status.value,
        "total": len(tasks),
        "passed": passed,
        "failed": failed,
        "interrupted": interrupted,
        "first_attempt_passed": first_attempt_passed,
        "total_input_tokens": state.total_input_tokens,
        "total_output_tokens": state.total_output_tokens,
        "total_cost_usd": state.total_cost_usd,
    }

def _write_state(run_dir: Path, state: RunState) -> None:
    write_json(run_dir / "state.json", state)


def _write_summary(run_dir: Path, state: RunState) -> None:
    write_json(run_dir / "summary.json", state)


def _remember_event(state: RunState, event: dict) -> None:
    state.recent_events = (state.recent_events + [event])[-8:]


def parse_tasks(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default=None)
    parser.add_argument("--check-browser", action="store_true")
    parser.add_argument("--check-sites", action="store_true")
    parser.add_argument("--max-steps", type=int, default=None)
    args = parser.parse_args()
    run_dir = asyncio.run(run_demo3(parse_tasks(args.tasks), check_browser=args.check_browser, check_sites=args.check_sites, step_override=args.max_steps))
    print(run_dir)


if __name__ == "__main__":
    main()
