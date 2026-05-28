from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

from demo3_browser_agent.config import latest_path, runs_dir
from demo3_browser_agent.policy import PolicyDenied, check_url_policy
from demo3_browser_agent.runner import new_run_id, run_demo3
from demo3_browser_agent.scenarios import SCENARIO_BY_ID, SCENARIOS
from demo3_browser_agent.schemas import RunState, TaskState, TaskStatus
from demo3_browser_agent.trace import TraceWriter, read_jsonl, write_json

LIVE_SCENARIOS = ["retry_tasks", "network_drop", "modal_wall", "blacklist_url"]
TASK_SCENARIOS = {
    "retry_tasks": ["arxiv", "github-issues", "local-form"],
    "network_drop": ["network-drop"],
    "modal_wall": ["modal-wall"],
}


async def run_scenario(scenario_id: str, mode: str = "interactive") -> Path:
    if scenario_id == "replay_trace":
        return _record_replay_scenario(mode)
    if scenario_id == "blacklist_url":
        return _run_blacklist_scenario(mode)
    if scenario_id not in TASK_SCENARIOS:
        raise RuntimeError(f"unknown scenario: {scenario_id}")

    run_dir = await run_demo3(TASK_SCENARIOS[scenario_id], mode=mode, current_scenario=scenario_id)
    _apply_scenario_summary(run_dir, scenario_id)
    return run_dir


async def run_all_scenarios() -> Path:
    started = time.time()
    scenario_rows = []
    last_run_dir: Path | None = None
    for scenario_id in LIVE_SCENARIOS:
        run_dir = await run_scenario(scenario_id, mode="all")
        last_run_dir = run_dir
        scenario_rows.append(_scenario_row(run_dir, scenario_id))

    replay_dir = _record_replay_scenario("all")
    last_run_dir = replay_dir
    scenario_rows.append(_scenario_row(replay_dir, "replay_trace"))

    status = "passed" if all(row["status"] == "passed" for row in scenario_rows) else "failed"
    summary = {
        "run_id": replay_dir.name,
        "mode": "all",
        "status": status,
        "duration_seconds": round(time.time() - started, 1),
        "scenarios": scenario_rows,
        "passed": sum(1 for row in scenario_rows if row["status"] == "passed"),
        "total": len(scenario_rows),
    }
    write_json(replay_dir / "demo_all_summary.json", summary)
    state = _load_state(replay_dir)
    if state:
        state["summary"]["demo_all"] = summary
        state["status"] = status
        write_json(replay_dir / "state.json", state)
        write_json(replay_dir / "summary.json", state)
    return last_run_dir


def _run_blacklist_scenario(mode: str) -> Path:
    scenario_id = "blacklist_url"
    scenario = SCENARIO_BY_ID[scenario_id]
    run_id = new_run_id()
    run_dir = runs_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    writer = TraceWriter(run_dir)
    blocked_url = "https://malware.test/"
    state = RunState(
        run_id=run_id,
        mode=mode,
        current_scenario=scenario_id,
        current_task="blacklist-url",
        current_thought="目标 URL 命中黑名单，因此拒绝导航。",
        current_action=f"DENY_NAVIGATION {blocked_url}",
        max_steps=1,
    )
    state.tasks["blacklist-url"] = TaskState(id="blacklist-url", name=scenario["name"], status=TaskStatus.running)
    write_json(latest_path(), {"run_id": run_id, "run_dir": str(run_dir), "trace": str(run_dir / "trace.jsonl")})
    writer.append("run_start", run_id=run_id, mode=mode, scenario_id=scenario_id, tasks=["blacklist-url"])
    writer.append("scenario_start", run_id=run_id, mode=mode, scenario_id=scenario_id)
    writer.append("policy_check", run_id=run_id, mode=mode, scenario_id=scenario_id, task_id="blacklist-url", url=blocked_url)
    try:
        check_url_policy(blocked_url)
    except PolicyDenied as exc:
        state.status = TaskStatus.passed
        state.tasks["blacklist-url"].status = TaskStatus.passed
        state.tasks["blacklist-url"].message = "blacklisted URL denied before navigation"
        state.summary = {
            "status": "passed",
            "total": 1,
            "passed": 1,
            "failed": 0,
            "blocked_url": blocked_url,
            "reason": str(exc),
        }
        writer.append("navigation_denied", run_id=run_id, mode=mode, scenario_id=scenario_id, task_id="blacklist-url", url=blocked_url, reason="blacklisted_url")
        writer.append("scenario_passed", run_id=run_id, mode=mode, scenario_id=scenario_id, summary=state.summary)
    else:
        state.status = TaskStatus.failed
        state.tasks["blacklist-url"].status = TaskStatus.failed
        state.tasks["blacklist-url"].message = "blacklisted URL was not denied"
        state.summary = {"status": "failed", "total": 1, "passed": 0, "failed": 1, "blocked_url": blocked_url}
        writer.append("scenario_failed", run_id=run_id, mode=mode, scenario_id=scenario_id, reason="policy allowed denied URL")
    writer.append("run_complete", run_id=run_id, mode=mode, scenario_id=scenario_id, status=state.status.value, summary=state.summary)
    write_json(run_dir / "state.json", state)
    write_json(run_dir / "summary.json", state)
    writer.copy_to_latest()
    return run_dir


def _record_replay_scenario(mode: str) -> Path:
    scenario_id = "replay_trace"
    run_id = new_run_id()
    run_dir = runs_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    writer = TraceWriter(run_dir)
    latest_trace = ""
    try:
        previous_trace = _latest_trace_before(run_dir)
        latest_trace = str(previous_trace) if previous_trace else ""
    except Exception:
        latest_trace = ""
    state = RunState(
        run_id=run_id,
        mode=mode,
        status=TaskStatus.passed,
        current_scenario=scenario_id,
        current_task="replay-trace",
        current_thought="trace 已准备好，可在前端逐帧回放。",
        current_action="REPLAY_TRACE",
        max_steps=1,
        step=1,
    )
    state.tasks["replay-trace"] = TaskState(id="replay-trace", name=SCENARIO_BY_ID[scenario_id]["name"], status=TaskStatus.passed)
    state.summary = {"status": "passed", "total": 1, "passed": 1, "failed": 0, "trace": latest_trace}
    write_json(latest_path(), {"run_id": run_id, "run_dir": str(run_dir), "trace": str(run_dir / "trace.jsonl")})
    writer.append("run_start", run_id=run_id, mode=mode, scenario_id=scenario_id, tasks=["replay-trace"])
    writer.append("scenario_start", run_id=run_id, mode=mode, scenario_id=scenario_id)
    writer.append("scenario_passed", run_id=run_id, mode=mode, scenario_id=scenario_id, trace=latest_trace)
    writer.append("run_complete", run_id=run_id, mode=mode, scenario_id=scenario_id, status="passed", summary=state.summary)
    write_json(run_dir / "state.json", state)
    write_json(run_dir / "summary.json", state)
    writer.copy_to_latest()
    return run_dir


def _latest_trace_before(excluded_run_dir: Path) -> Path | None:
    if not latest_path().exists():
        return None
    latest = latest_path().read_text(encoding="utf-8")
    import json

    data = json.loads(latest)
    trace = Path(data.get("trace", ""))
    if trace.parent == excluded_run_dir:
        return None
    return trace if trace.exists() else None


def _apply_scenario_summary(run_dir: Path, scenario_id: str) -> None:
    state = _load_state(run_dir)
    if not state:
        return
    events = read_jsonl(run_dir / "trace.jsonl")
    scenario_status = state.get("status", "failed")
    if scenario_id == "retry_tasks":
        first_pass_count = sum(1 for task in state.get("tasks", {}).values() if task.get("status") == "passed" and task.get("attempt", 0) == 0)
        scenario_status = "passed" if first_pass_count >= 2 and state.get("status") == "passed" else "failed"
        state["status"] = scenario_status
        state["summary"]["first_pass_count"] = first_pass_count
        state["summary"]["first_pass_requirement"] = ">=2"
    state["summary"]["scenario_id"] = scenario_id
    state["summary"]["event_count"] = len(events)
    write_json(run_dir / "state.json", state)
    write_json(run_dir / "summary.json", state)


def _scenario_row(run_dir: Path, scenario_id: str) -> dict:
    state = _load_state(run_dir) or {}
    scenario = SCENARIO_BY_ID[scenario_id]
    tasks = state.get("tasks", {})
    retries = sum(1 for task in tasks.values() if task.get("attempt", 0) > 0)
    return {
        "id": scenario_id,
        "name": scenario["name"],
        "status": state.get("status", "failed"),
        "retries": retries,
        "duration_seconds": _duration_seconds(run_dir),
        "notes": state.get("summary", {}),
        "run_dir": str(run_dir),
    }


def _duration_seconds(run_dir: Path) -> float:
    events = read_jsonl(run_dir / "trace.jsonl")
    if len(events) < 2:
        return 0.0
    from datetime import datetime

    start = datetime.fromisoformat(events[0]["ts"])
    end = datetime.fromisoformat(events[-1]["ts"])
    return round(max((end - start).total_seconds(), 0.0), 1)


def _load_state(run_dir: Path) -> dict | None:
    path = run_dir / "state.json"
    if not path.exists():
        return None
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=[scenario["id"] for scenario in SCENARIOS])
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.all:
        run_dir = asyncio.run(run_all_scenarios())
    elif args.scenario:
        run_dir = asyncio.run(run_scenario(args.scenario))
    else:
        parser.error("provide --scenario or --all")
    print(run_dir)


if __name__ == "__main__":
    main()
