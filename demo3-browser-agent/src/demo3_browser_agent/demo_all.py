from __future__ import annotations

import asyncio
import json
from pathlib import Path

from demo3_browser_agent.runner import run_demo3


def main() -> None:
    run_dir = asyncio.run(run_demo3())
    summary_path = Path(run_dir) / "summary.json"
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    print("Demo 3 Summary")
    print("Task | Status | Attempt | Step | Message")
    print("-" * 72)
    for task in data.get("tasks", {}).values():
        print(f"{_safe(task['name'])} | {task['status']} | {task['attempt']} | {task['step']} | {_safe(task.get('message', ''))}")
    print(f"Run directory: {run_dir}")


def _safe(value: object) -> str:
    return str(value or "").encode("ascii", "replace").decode("ascii")


if __name__ == "__main__":
    main()
