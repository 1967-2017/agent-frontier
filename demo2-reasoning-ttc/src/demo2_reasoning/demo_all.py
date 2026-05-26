from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import DEFAULT_QUESTIONS
from .runner import run_evaluation
from .schemas import StrategyModelSummary


def render_panel(run_dir: Path) -> None:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    summaries = [StrategyModelSummary.model_validate(item) for item in summary["summaries"]]
    table = Table(title="Demo2 Summary Panel", box=box.ASCII, show_lines=True)
    table.add_column("策略")
    table.add_column("模型")
    table.add_column("状态")
    table.add_column("准确率", justify="right")
    table.add_column("平均 thinking tokens", justify="right")
    table.add_column("平均 wall time", justify="right")
    table.add_column("单题成本", justify="right")
    for item in summaries:
        if item.status == "skipped":
            table.add_row(item.strategy, item.model, "skipped", "skipped", "skipped", "skipped", "skipped")
        else:
            table.add_row(
                item.strategy,
                item.model,
                item.status,
                f"{item.accuracy:.1%}",
                f"{item.avg_thinking_tokens:.1f}",
                f"{item.avg_wall_time_s:.2f}s",
                f"${item.cost_per_question:.6f} estimated",
            )
    artifacts = Table.grid(padding=(0, 2))
    artifacts.add_column(style="bold")
    artifacts.add_column()
    for name in ["trace.jsonl", "results.jsonl", "summary.json", "metrics.csv", "report.md", "scatter.png"]:
        artifacts.add_row(name, "PASS" if (run_dir / name).exists() else "FAIL")
    group = Table.grid(expand=True)
    group.add_column()
    group.add_row(table)
    group.add_row(Panel(artifacts, title="Artifacts", box=box.ASCII))
    group.add_row(Panel(summary["conclusion"], title="Conclusion", box=box.ASCII))
    group.add_row(Panel("Token usage and cost are estimated demo values based on prompt/output length, not provider billing.", title="Cost note", box=box.ASCII))
    Console(force_terminal=True, legacy_windows=False).print(Panel(group, title=f"Demo2 run: {run_dir.name}", border_style="green", box=box.ASCII))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Demo2 all use cases and render summary panel")
    parser.add_argument("--questions", type=int, default=DEFAULT_QUESTIONS)
    args = parser.parse_args()
    run_dir = asyncio.run(run_evaluation(args.questions))
    render_panel(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
