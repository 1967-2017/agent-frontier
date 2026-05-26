from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .schemas import ModelCallResult, StrategyModelSummary


def summarize_results(results: list[ModelCallResult], skipped: list[StrategyModelSummary]) -> list[StrategyModelSummary]:
    grouped: dict[tuple[str, str, str], list[ModelCallResult]] = defaultdict(list)
    for result in results:
        if result.sample_index == 0 or result.status == "ok":
            grouped[(result.strategy, result.provider, result.model)].append(result)
    summaries: list[StrategyModelSummary] = list(skipped)
    for (strategy, provider, model), rows in grouped.items():
        if not rows:
            continue
        total = len(rows)
        correct = sum(1 for row in rows if row.correct)
        summaries.append(
            StrategyModelSummary(
                strategy=strategy,
                provider=provider,
                model=model,
                status="completed",
                total=total,
                completed=total,
                correct=correct,
                accuracy=correct / total if total else None,
                avg_thinking_tokens=mean(row.estimated_thinking_tokens for row in rows) if rows else None,
                avg_wall_time_s=mean(row.latency_ms for row in rows) / 1000 if rows else None,
                cost_per_question=mean(row.estimated_cost_usd for row in rows) if rows else None,
            )
        )
    return sorted(summaries, key=lambda item: (item.strategy, item.model))


def choose_best_value(summaries: list[StrategyModelSummary]) -> tuple[StrategyModelSummary | None, str]:
    candidates = [item for item in summaries if item.status == "completed" and item.accuracy is not None and item.avg_wall_time_s is not None]
    if not candidates:
        return None, "没有完成的策略+模型组合可用于判断。"
    best_accuracy = max(item.accuracy or 0 for item in candidates)
    near_best = [item for item in candidates if (item.accuracy or 0) >= best_accuracy - 0.02]
    winner = min(near_best, key=lambda item: item.avg_wall_time_s or 999999)
    reason = (
        f"它的准确率为 {winner.accuracy:.1%}，处于最高准确率 2 个百分点以内，"
        f"且候选组合中平均 wall time 最低（{winner.avg_wall_time_s:.2f}s）。"
    )
    return winner, reason
