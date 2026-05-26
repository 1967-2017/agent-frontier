from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

from .config import latest_path
from .metrics import choose_best_value
from .schemas import StrategyModelSummary


def load_latest_run() -> Path:
    data = json.loads(latest_path().read_text(encoding="utf-8"))
    return Path(data["run_dir"])


def write_reports(run_dir: Path, summaries: list[StrategyModelSummary]) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.csv"
    with metrics_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["strategy", "model", "provider", "status", "total", "completed", "correct", "accuracy", "avg_thinking_tokens", "avg_wall_time_s", "cost_per_question", "note"],
        )
        writer.writeheader()
        for item in summaries:
            writer.writerow(item.model_dump())

    winner, reason = choose_best_value(summaries)
    one_line_conclusion = (
        f"本任务最划算的是 {winner.strategy} 策略 + {winner.model} 模型，因为 {reason}"
        if winner
        else f"本任务最划算的是 N/A 策略 + N/A 模型，因为 {reason}"
    )
    conclusion = f"**{one_line_conclusion}**"
    table_lines = [
        "| 策略 | 模型 | 准确率 | 平均 thinking tokens | 平均 wall time | 单题成本 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in summaries:
        if item.status == "skipped":
            table_lines.append(f"| {item.strategy} | {item.model} | skipped | skipped | skipped | skipped |")
        else:
            table_lines.append(
                f"| {item.strategy} | {item.model} | {item.accuracy:.1%} | {item.avg_thinking_tokens:.1f} | {item.avg_wall_time_s:.2f}s | ${item.cost_per_question:.6f} estimated |"
            )
    report = "\n".join(
        [
            "# Demo2 Report",
            "",
            *table_lines,
            "",
            "Note: token usage and cost are estimated demo values based on prompt/output length, not provider billing.",
            "The final value conclusion uses accuracy and real wall time only.",
            "",
            conclusion,
            "",
        ]
    )
    (run_dir / "report.md").write_text(report, encoding="utf-8")

    completed = [item for item in summaries if item.status == "completed" and item.accuracy is not None and item.cost_per_question is not None]
    plt.figure(figsize=(8, 5))
    for item in completed:
        plt.scatter(item.cost_per_question, item.accuracy, label=f"{item.strategy} + {item.model}")
        plt.annotate(f"{item.strategy}\n{item.model}", (item.cost_per_question, item.accuracy), fontsize=7)
    plt.xlabel("Estimated cost per question (USD)")
    plt.ylabel("Accuracy")
    plt.title("Accuracy vs Estimated Cost")
    plt.grid(True, alpha=0.3)
    if completed:
        plt.legend(fontsize=6, loc="best")
    plt.tight_layout()
    scatter_path = run_dir / "scatter.png"
    plt.savefig(scatter_path)
    plt.close()

    summary_data = {
        "summaries": [item.model_dump() for item in summaries],
        "one_line_conclusion": one_line_conclusion,
        "conclusion": conclusion,
        "winner": winner.model_dump() if winner else None,
        "note": "token usage and cost are estimated demo values based on prompt/output length, not provider billing",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Demo2 report")
    parser.add_argument("--latest", action="store_true")
    args = parser.parse_args()
    if not args.latest:
        raise SystemExit("Only --latest is currently supported")
    run_dir = load_latest_run()
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    summaries = [StrategyModelSummary.model_validate(item) for item in summary["summaries"]]
    write_reports(run_dir, summaries)
    print(run_dir / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
