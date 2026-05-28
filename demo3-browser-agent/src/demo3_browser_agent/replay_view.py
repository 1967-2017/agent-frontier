from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from demo3_browser_agent.config import latest_path, project_root
from demo3_browser_agent.trace import read_jsonl


@dataclass
class ReplayFrame:
    index: int
    timestamp: str
    event_type: str
    scenario_id: str | None = None
    task_id: str | None = None
    step: int = 0
    screenshot_path: Path | None = None
    reasoning_summary: str = ""
    action: str = ""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    task_statuses: dict[str, str] = field(default_factory=dict)
    summary: str = ""


def resolve_trace(latest: bool, trace: str | None) -> Path:
    if trace:
        return Path(trace)
    if latest:
        latest_trace = get_latest_trace()
        if latest_trace:
            return latest_trace
    return project_root() / "trace.jsonl"


def get_latest_trace() -> Path | None:
    if not latest_path().exists():
        return None
    data = json.loads(latest_path().read_text(encoding="utf-8"))
    run_dir = Path(data.get("run_dir", ""))
    state_path = run_dir / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        replay_trace = state.get("summary", {}).get("trace")
        if state.get("current_scenario") == "replay_trace" and replay_trace:
            trace = Path(replay_trace)
            return trace if trace.exists() else None
    trace = Path(data["trace"])
    return trace if trace.exists() else None


def load_trace(path: Path) -> list[dict]:
    return read_jsonl(path)


def build_replay_frames(events: list[dict], trace_path: Path) -> list[ReplayFrame]:
    frames: list[ReplayFrame] = []
    task_statuses: dict[str, str] = {}
    input_tokens = 0
    output_tokens = 0
    cost_usd = 0.0
    last_screenshot: Path | None = None
    last_reasoning = ""
    last_action = ""

    for event in events:
        event_type = event.get("event_type", "event")
        task_id = event.get("task_id")
        if task_id and event_type == "task_start":
            task_statuses[task_id] = "running"
        elif task_id and event_type == "task_passed":
            task_statuses[task_id] = "passed"
        elif task_id and event_type in {"task_failed", "task_attempt_error"}:
            task_statuses[task_id] = "failed"

        observation = event.get("observation") or {}
        screenshot = observation.get("marked_screenshot_path") or observation.get("screenshot_path")
        if screenshot:
            last_screenshot = _resolve_artifact(trace_path.parent, screenshot)

        decision = event.get("decision") or {}
        if event_type == "model_decision_end":
            last_reasoning = str(decision.get("thought") or "")
            last_action = str(decision.get("action_type") or "")
            tokens = event.get("tokens") or {}
            input_tokens += int(tokens.get("input", 0) or 0)
            output_tokens += int(tokens.get("output", 0) or 0)
            cost_usd += float(event.get("cost_usd", 0.0) or 0.0)
        elif event_type in {"action_planned", "action_executed", "navigation_denied"}:
            last_action = _event_action(event)
        elif event_type in {"scenario_passed", "scenario_failed", "run_complete"}:
            last_reasoning = str(event.get("message") or event.get("reason") or event_type)

        frame = ReplayFrame(
            index=len(frames),
            timestamp=str(event.get("ts") or ""),
            event_type=event_type,
            scenario_id=event.get("scenario_id"),
            task_id=task_id,
            step=int(event.get("step") or len(frames) + 1),
            screenshot_path=last_screenshot,
            reasoning_summary=last_reasoning,
            action=last_action,
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_cost_usd=cost_usd,
            task_statuses=dict(task_statuses),
            summary=_event_summary(event),
        )
        frames.append(frame)
    return frames


def replay(trace_path: Path, no_delay: bool = False) -> None:
    events = read_jsonl(trace_path)
    print(f"Demo 3 Replay | trace={trace_path} | events={len(events)}")
    last_ts = None
    for event in events:
        if not no_delay and last_ts:
            time.sleep(0.25)
        last_ts = event.get("ts")
        event_type = event.get("event_type")
        task = event.get("task_id", "-")
        step = event.get("step", "-")
        if event_type == "observation":
            observation = event.get("observation", {})
            print(f"{event_type} task={task} step={step} url={observation.get('url')} screenshot={observation.get('marked_screenshot_path')}")
        elif event_type == "model_decision_end":
            decision = event.get("decision", {})
            print(f"{event_type} task={task} step={step} thought={_safe(decision.get('thought'))} action={decision.get('action_type')} mark={decision.get('mark_id')}")
        elif event_type == "action_planned":
            print(f"{_safe(event.get('message', '[ACTION]'))} task={task} step={step}")
        elif event_type in {"task_failed", "run_error", "task_attempt_error"}:
            print(f"{event_type} task={task} step={step} message={_safe(event.get('message') or event.get('error'))}")
        else:
            print(f"{event_type} task={task} step={step}")


def _resolve_artifact(run_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return run_dir / path


def _event_action(event: dict) -> str:
    if event.get("event_type") == "navigation_denied":
        return f"DENY_NAVIGATION {event.get('url', '')}"
    result = event.get("result") or {}
    if isinstance(result, dict) and result.get("action"):
        return str(result["action"])
    return str(event.get("message") or event.get("event_type") or "")


def _event_summary(event: dict) -> str:
    event_type = event.get("event_type", "event")
    if event_type == "observation":
        observation = event.get("observation", {})
        return f"observation · {observation.get('url', '')}"
    if event_type == "model_decision_end":
        decision = event.get("decision", {})
        return f"model · {decision.get('action_type', '')}"
    return str(event.get("message") or event.get("reason") or event_type)


def _safe(value: object) -> str:
    return str(value or "").encode("ascii", "replace").decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--trace")
    parser.add_argument("--no-delay", action="store_true")
    args = parser.parse_args()
    replay(resolve_trace(args.latest, args.trace), no_delay=args.no_delay)


if __name__ == "__main__":
    main()
