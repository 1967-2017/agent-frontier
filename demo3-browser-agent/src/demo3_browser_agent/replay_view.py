from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from demo3_browser_agent.config import latest_path, project_root
from demo3_browser_agent.trace import read_jsonl


def resolve_trace(latest: bool, trace: str | None) -> Path:
    if trace:
        return Path(trace)
    if latest:
        data = json.loads(latest_path().read_text(encoding="utf-8"))
        return Path(data["trace"])
    return project_root() / "trace.jsonl"


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
