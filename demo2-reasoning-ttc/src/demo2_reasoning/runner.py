from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .config import DEFAULT_QUESTIONS, SUPPORTED_QUESTION_COUNTS, latest_path, runs_dir
from .dataset import load_problems
from .evaluator import extract_numeric_answer, is_correct, majority_vote
from .metrics import summarize_results
from .providers.registry import model_configs, provider_for
from .report import write_reports
from .schemas import ModelCallResult, StrategyModelSummary
from .strategies import STRATEGIES
from .trace import append_event
from .virtual_usage import estimate_cost, estimate_tokens


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def prompt_from_spec(spec) -> str:
    return "\n".join(str(message.get("content", "")) for message in spec.messages)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, data) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")


async def run_evaluation(questions: int = DEFAULT_QUESTIONS) -> Path:
    if questions not in SUPPORTED_QUESTION_COUNTS:
        raise ValueError(f"questions must be one of {sorted(SUPPORTED_QUESTION_COUNTS)}")
    problems = load_problems(questions)
    run_id = new_run_id()
    run_dir = runs_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.jsonl"
    results_path = run_dir / "results.jsonl"
    state_path = run_dir / "state.json"
    latest_path().parent.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    write_json(
        state_path,
        {
            "run_id": run_id,
            "started_at": started_at,
            "updated_at": started_at,
            "question_total": questions,
            "estimated_cost_so_far": 0.0,
            "initializing": True,
        },
    )
    write_json(latest_path(), {"run_id": run_id, "run_dir": str(run_dir), "questions": questions})

    append_event(trace_path, "run_start", run_id=run_id, questions=questions)
    append_event(trace_path, "dataset_loaded", dataset="gsmhardv2", questions=len(problems))

    results: list[ModelCallResult] = []
    skipped: list[StrategyModelSummary] = []
    total_strategy_model_pairs = len(STRATEGIES) * len(model_configs())
    pair_index = 0

    for strategy in STRATEGIES:
        append_event(trace_path, "strategy_start", strategy=strategy.name)
        for model_config in model_configs():
            pair_index += 1
            supported, reason = strategy.supports_model(model_config)
            if not supported:
                skipped_summary = StrategyModelSummary(
                    strategy=strategy.name,
                    model=model_config.model,
                    provider=model_config.provider,
                    status="skipped",
                    total=questions,
                    completed=0,
                    correct=0,
                    accuracy=None,
                    avg_thinking_tokens=None,
                    avg_wall_time_s=None,
                    cost_per_question=None,
                    note=reason,
                )
                skipped.append(skipped_summary)
                append_event(trace_path, "strategy_skipped", strategy=strategy.name, provider=model_config.provider, model=model_config.model, reason=reason)
                continue

            provider = provider_for(model_config)
            for question_index, problem in enumerate(problems, start=1):
                specs = strategy.build_specs(problem, model_config)
                sample_results: list[ModelCallResult] = []
                for spec in specs:
                    state = {
                        "run_id": run_id,
                        "started_at": started_at,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "strategy": strategy.name,
                        "strategy_index": pair_index,
                        "strategy_total": total_strategy_model_pairs,
                        "model": model_config.model,
                        "question_index": question_index,
                        "question_total": questions,
                        "sample_index": spec.sample_index,
                        "sample_total": len(specs),
                        "estimated_cost_so_far": round(sum(item.estimated_cost_usd for item in results), 6),
                    }
                    write_json(state_path, state)
                    append_event(trace_path, "model_call_start", run_id=run_id, strategy=strategy.name, provider=model_config.provider, model=model_config.model, question_id=problem.id, sample_index=spec.sample_index)
                    prompt = prompt_from_spec(spec)
                    try:
                        response = await provider.complete(spec)
                        extracted = extract_numeric_answer(response.text)
                        correct = is_correct(extracted, problem.answer)
                        input_tokens, output_tokens, thinking_tokens = estimate_tokens(prompt, response.text, strategy.name)
                        cost = estimate_cost(model_config.model, input_tokens, output_tokens, thinking_tokens)
                        result = ModelCallResult(
                            provider=model_config.provider,
                            model=model_config.model,
                            strategy=strategy.name,
                            question_id=problem.id,
                            sample_index=spec.sample_index,
                            prompt=prompt,
                            output_text=response.text,
                            extracted_answer=extracted,
                            target_answer=problem.answer,
                            correct=correct,
                            latency_ms=response.latency_ms,
                            estimated_input_tokens=input_tokens,
                            estimated_output_tokens=output_tokens,
                            estimated_thinking_tokens=thinking_tokens,
                            estimated_cost_usd=cost,
                            status="ok",
                        )
                    except Exception as exc:
                        result = ModelCallResult(
                            provider=model_config.provider,
                            model=model_config.model,
                            strategy=strategy.name,
                            question_id=problem.id,
                            sample_index=spec.sample_index,
                            prompt=prompt,
                            output_text="",
                            extracted_answer=None,
                            target_answer=problem.answer,
                            correct=False,
                            latency_ms=0,
                            estimated_input_tokens=0,
                            estimated_output_tokens=0,
                            estimated_thinking_tokens=0,
                            estimated_cost_usd=0.0,
                            status="error",
                            error=str(exc),
                        )
                    sample_results.append(result)
                    append_jsonl(results_path, result.model_dump())
                    append_event(
                        trace_path,
                        "model_call_end" if result.status == "ok" else "model_call_error",
                        run_id=run_id,
                        strategy=strategy.name,
                        provider=model_config.provider,
                        model=model_config.model,
                        question_id=problem.id,
                        sample_index=spec.sample_index,
                        output={"extracted_answer": result.extracted_answer, "target_answer": result.target_answer, "correct": result.correct},
                        tokens={"estimated_input": result.estimated_input_tokens, "estimated_output": result.estimated_output_tokens, "estimated_thinking": result.estimated_thinking_tokens, "virtual": True},
                        cost={"estimated_usd": result.estimated_cost_usd, "virtual": True},
                        latency_ms=result.latency_ms,
                        status=result.status,
                        error=result.error,
                    )

                if strategy.name == "BoN=5 + SC":
                    vote = majority_vote(item.extracted_answer for item in sample_results)
                    voted_correct = is_correct(vote, problem.answer)
                    total_latency = sum(item.latency_ms for item in sample_results)
                    total_input = sum(item.estimated_input_tokens for item in sample_results)
                    total_output = sum(item.estimated_output_tokens for item in sample_results)
                    total_thinking = sum(item.estimated_thinking_tokens for item in sample_results)
                    total_cost = sum(item.estimated_cost_usd for item in sample_results)
                    aggregate = ModelCallResult(
                        provider=model_config.provider,
                        model=model_config.model,
                        strategy=strategy.name,
                        question_id=problem.id,
                        sample_index=0,
                        prompt=sample_results[0].prompt if sample_results else "",
                        output_text="\n---\n".join(item.output_text for item in sample_results),
                        extracted_answer=vote,
                        target_answer=problem.answer,
                        correct=voted_correct,
                        latency_ms=total_latency,
                        estimated_input_tokens=total_input,
                        estimated_output_tokens=total_output,
                        estimated_thinking_tokens=total_thinking,
                        estimated_cost_usd=total_cost,
                        status="ok" if any(item.status == "ok" for item in sample_results) else "error",
                    )
                    results.append(aggregate)
                    append_jsonl(results_path, aggregate.model_dump())
                    append_event(trace_path, "self_consistency_vote", run_id=run_id, strategy=strategy.name, provider=model_config.provider, model=model_config.model, question_id=problem.id, answers=[item.extracted_answer for item in sample_results], selected=vote, correct=voted_correct)
                else:
                    results.extend(sample_results)

                summaries = summarize_results(results, skipped)
                append_event(trace_path, "metrics_update", run_id=run_id, summaries=[item.model_dump() for item in summaries])

    summaries = summarize_results(results, skipped)
    summary = write_reports(run_dir, summaries)
    completed_at = datetime.now(timezone.utc).isoformat()
    write_json(
        state_path,
        {
            "run_id": run_id,
            "complete": True,
            "started_at": started_at,
            "updated_at": completed_at,
            "completed_at": completed_at,
            "estimated_cost_so_far": round(sum(item.estimated_cost_usd for item in results), 6),
            "questions": questions,
        },
    )
    append_event(trace_path, "run_complete", run_id=run_id, summary=summary)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Demo2 reasoning evaluation")
    parser.add_argument("--questions", type=int, default=DEFAULT_QUESTIONS)
    args = parser.parse_args()
    run_dir = asyncio.run(run_evaluation(args.questions))
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
