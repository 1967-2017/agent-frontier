from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd
import streamlit as st

from demo2_reasoning.config import latest_path
from demo2_reasoning.providers.registry import model_configs
from demo2_reasoning.runner import run_evaluation
from demo2_reasoning.schemas import StrategyModelSummary
from demo2_reasoning.strategies import STRATEGIES


REFRESH_INTERVAL_SECONDS = 1
BON_STRATEGY = "BoN=5 + SC"


def start_evaluation_in_background(questions: int) -> None:
    def _run() -> None:
        asyncio.run(run_evaluation(questions))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def read_json_or_none(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def read_results_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    return rows


def fmt_percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def fmt_seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}s"


def fmt_number(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.1f}"
    return str(int(value))


def fmt_cost(value: float | None) -> str:
    return "-" if value is None else f"${value:.6f} estimated"


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "--:--:--"
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def elapsed_seconds(state: dict[str, Any] | None, is_complete: bool) -> float | None:
    if state is None:
        return None
    started_at = parse_iso_datetime(state.get("started_at"))
    if started_at is None:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    end_at = parse_iso_datetime(state.get("completed_at")) if is_complete else datetime.now(timezone.utc)
    if end_at is None:
        return None
    if end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=timezone.utc)
    return (end_at - started_at).total_seconds()


def question_level_results(strategy_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if strategy_name == BON_STRATEGY:
        return [row for row in rows if int(row.get("sample_index", -1)) == 0]
    return [row for row in rows if int(row.get("sample_index", 0)) != 0]


def aggregate_result_rows(rows: list[dict[str, Any]], total_questions: int) -> dict[str, Any]:
    completed = len({row.get("question_id") for row in rows if row.get("question_id")})
    correct = sum(1 for row in rows if row.get("correct"))
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    cost_total = sum(float(row.get("estimated_cost_usd") or 0.0) for row in rows)
    error_count = sum(1 for row in rows if row.get("status") == "error")

    return {
        "completed": min(completed, total_questions),
        "correct": correct,
        "accuracy": correct / completed if completed else None,
        "avg_wall_time_s": mean(float(row.get("latency_ms") or 0) for row in rows) / 1000 if rows else None,
        "avg_thinking_tokens": mean(float(row.get("estimated_thinking_tokens") or 0) for row in rows) if rows else None,
        "cost_per_question": cost_total / completed if completed else None,
        "total_cost": cost_total,
        "error_count": error_count,
        "has_ok": bool(ok_rows),
    }


def build_realtime_matrix_rows(
    results_path: Path,
    state: dict[str, Any] | None,
    total_questions: int,
    is_complete: bool,
) -> tuple[list[dict[str, Any]], bool]:
    raw_results = read_results_jsonl(results_path)
    grouped_raw: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in raw_results:
        key = (str(row.get("strategy", "")), str(row.get("model", "")))
        grouped_raw.setdefault(key, []).append(row)

    rows: list[dict[str, Any]] = []
    current_strategy = None if state is None else state.get("strategy")
    current_model = None if state is None else state.get("model")

    for strategy in STRATEGIES:
        for model_config in model_configs():
            supported, reason = strategy.supports_model(model_config)
            key = (strategy.name, model_config.model)
            raw_group = grouped_raw.get(key, [])
            question_rows = question_level_results(strategy.name, raw_group)
            metrics = aggregate_result_rows(question_rows, total_questions)
            completed = metrics["completed"]

            if not supported:
                status = "skipped"
            elif current_strategy == strategy.name and current_model == model_config.model and not is_complete:
                status = "running"
            elif completed >= total_questions:
                status = "completed"
            elif metrics["error_count"] > 0:
                status = "error"
            elif completed > 0:
                status = "partial"
            else:
                status = "pending"

            completion_text = f"{completed}/{total_questions}"
            if strategy.name == BON_STRATEGY:
                sample_index = state.get("sample_index") if state else None
                sample_total = state.get("sample_total") if state else None
                if current_strategy == strategy.name and current_model == model_config.model and sample_index and sample_total:
                    completion_text = f"{completion_text}  sample {sample_index}/{sample_total}"

            rows.append(
                {
                    "策略": strategy.name,
                    "模型": model_config.model,
                    "状态": status,
                    "完成": completion_text,
                    "正确": metrics["correct"],
                    "准确率": fmt_percent(metrics["accuracy"]),
                    "平均 wall time": fmt_seconds(metrics["avg_wall_time_s"]),
                    "平均 thinking tokens": fmt_number(metrics["avg_thinking_tokens"]),
                    "单题成本": fmt_cost(metrics["cost_per_question"]),
                    "总成本": fmt_cost(metrics["total_cost"]),
                    "note": reason if not supported else "",
                }
            )

    return rows, bool(raw_results)


def build_summary_fallback_rows(summary_path: Path) -> list[dict[str, Any]]:
    summary = read_json_or_none(summary_path)
    if summary is None:
        return []
    summaries = [StrategyModelSummary.model_validate(item) for item in summary.get("summaries", [])]
    rows = []
    for item in summaries:
        total_cost = None if item.cost_per_question is None else item.cost_per_question * item.completed
        rows.append(
            {
                "策略": item.strategy,
                "模型": item.model,
                "状态": item.status,
                "完成": f"{item.completed}/{item.total}",
                "正确": item.correct,
                "准确率": fmt_percent(item.accuracy),
                "平均 wall time": fmt_seconds(item.avg_wall_time_s),
                "平均 thinking tokens": fmt_number(item.avg_thinking_tokens),
                "单题成本": fmt_cost(item.cost_per_question),
                "总成本": fmt_cost(total_cost),
                "note": item.note,
            }
        )
    return rows


def style_matrix(df: pd.DataFrame):
    status_colors = {
        "pending": "background-color: #f3f4f6; color: #374151",
        "running": "background-color: #dbeafe; color: #1d4ed8; font-weight: 600",
        "partial": "background-color: #fef3c7; color: #92400e",
        "completed": "background-color: #dcfce7; color: #166534",
        "skipped": "background-color: #e5e7eb; color: #6b7280",
        "error": "background-color: #fee2e2; color: #b91c1c; font-weight: 600",
    }

    def status_style(value: str) -> str:
        return status_colors.get(value, "")

    def accuracy_style(value: str) -> str:
        if value == "-":
            return ""
        number = float(value.rstrip("%"))
        if number >= 80:
            return "background-color: #dcfce7; color: #166534"
        if number >= 50:
            return "background-color: #fef3c7; color: #92400e"
        return "background-color: #fee2e2; color: #b91c1c"

    return df.style.map(status_style, subset=["状态"]).map(accuracy_style, subset=["准确率"])


def first_conclusion_paragraph(summary: dict[str, Any]) -> str:
    conclusion = str(summary.get("conclusion", "")).strip()
    if not conclusion:
        return ""
    return conclusion.split("\n\n", 1)[0]


def show_completion_report_sections(run_dir: Path, summary_path: Path) -> None:
    summary = read_json_or_none(summary_path)
    if summary is None:
        return

    one_line_conclusion = summary.get("one_line_conclusion") or first_conclusion_paragraph(summary)
    st.subheader("结论")
    st.markdown(one_line_conclusion)

    st.subheader("Accuracy vs Estimated Cost")
    scatter_path = run_dir / "scatter.png"
    if scatter_path.exists():
        st.image(str(scatter_path))


def is_question_level_result(item: dict[str, Any]) -> bool:
    sample_index = int(item.get("sample_index", 0))
    if item.get("strategy") == BON_STRATEGY:
        return sample_index == 0
    return sample_index != 0


def show_mistake_summary(results_path: Path) -> None:
    mistakes = []
    for item in read_results_jsonl(results_path):
        if item.get("status") == "ok" and not item.get("correct") and is_question_level_result(item):
            mistakes.append(item)

    with st.expander("最近错题的 thinking 摘要", expanded=False):
        if not mistakes:
            st.info("暂无错题。")
            return

        for item in reversed(mistakes):
            title = f"{item['question_id']} · {item['strategy']} · {item['model']}"
            st.markdown(f"**{title}**")
            with st.expander("回答内容", expanded=False):
                st.write({"target": item.get("target_answer"), "prediction": item.get("extracted_answer")})
                st.text(item.get("output_text") or "")



st.set_page_config(page_title="Demo2 Reasoning TTC", layout="wide")
st.title("Demo2 ｜ 推理模型 + Test-Time Compute")
st.caption("Token usage and cost are estimated demo values based on prompt/output length, not provider billing. Final value conclusion uses accuracy and wall time only.")

question_count = st.selectbox("Question count", [2, 10, 100], index=1)
run_clicked = st.button("Run Evaluation", type="primary", disabled=st.session_state.get("evaluation_running", False))

if run_clicked:
    existing_latest = read_json_or_none(latest_path())
    st.session_state["evaluation_running"] = True
    st.session_state["waiting_for_new_run"] = True
    st.session_state["previous_run_id"] = None if existing_latest is None else existing_latest.get("run_id")
    st.session_state.pop("active_run_id", None)
    start_evaluation_in_background(int(question_count))
    st.success(f"Started Demo2 evaluation with {question_count} questions.")
    time.sleep(0.5)
    st.rerun()

latest = latest_path()
if not latest.exists():
    st.info("No run yet. Click Run Evaluation to start.")
    st.stop()

latest_data = read_json_or_none(latest)
if latest_data is None:
    st.info("Latest run metadata is being written. Waiting for the next refresh...")
    time.sleep(REFRESH_INTERVAL_SECONDS)
    st.rerun()

current_run_id = latest_data.get("run_id")
if st.session_state.get("waiting_for_new_run"):
    previous_run_id = st.session_state.get("previous_run_id")
    if current_run_id == previous_run_id:
        st.info("正在创建新运行，请稍候...")
        time.sleep(REFRESH_INTERVAL_SECONDS)
        st.rerun()
    st.session_state["waiting_for_new_run"] = False
    st.session_state["active_run_id"] = current_run_id
elif st.session_state.get("evaluation_running") and st.session_state.get("active_run_id") is None:
    st.session_state["active_run_id"] = current_run_id

active_run_id = st.session_state.get("active_run_id")
is_active_run = active_run_id is None or current_run_id == active_run_id

if not is_active_run:
    st.info("正在切换到当前运行，请稍候...")
    time.sleep(REFRESH_INTERVAL_SECONDS)
    st.rerun()

run_dir = Path(latest_data["run_dir"])
state_path = run_dir / "state.json"
summary_path = run_dir / "summary.json"
results_path = run_dir / "results.jsonl"

st.subheader("Latest Run")
st.write(str(run_dir))

state = read_json_or_none(state_path) if state_path.exists() else None
if state is not None and state.get("run_id") != current_run_id:
    st.info("当前运行状态正在写入，请稍候...")
    time.sleep(REFRESH_INTERVAL_SECONDS)
    st.rerun()

if st.session_state.get("evaluation_running") and active_run_id is not None and current_run_id != active_run_id:
    st.info("正在等待当前运行数据，请稍候...")
    time.sleep(REFRESH_INTERVAL_SECONDS)
    st.rerun()

is_complete = bool(state and state.get("complete"))
if is_complete and is_active_run:
    st.session_state["evaluation_running"] = False

if state is not None:
    cost_so_far = state.get("estimated_cost_so_far", 0)
    elapsed = fmt_duration(elapsed_seconds(state, is_complete))
    if is_complete:
        total_questions = int(state.get("questions", latest_data.get("questions", question_count)))
        st.progress(1.0, text=f"完成 · 总耗时 {elapsed} · 已花 ${cost_so_far:.4f}")
    else:
        strategy_index = state.get("strategy_index", 0)
        strategy_total = state.get("strategy_total", 4)
        question_index = state.get("question_index", 0)
        total_questions = int(state.get("question_total", latest_data.get("questions", question_count)))
        current_unit = max(0, strategy_index - 1) * total_questions + question_index
        total_units = max(1, strategy_total * total_questions)
        st.progress(min(1.0, current_unit / total_units), text=f"策略 {strategy_index}/{strategy_total} · 题目 {question_index}/{total_questions} · 耗时 {elapsed} · 已花 ${cost_so_far:.4f}")
else:
    total_questions = int(latest_data.get("questions", question_count))

matrix_rows, has_results = build_realtime_matrix_rows(results_path, state, total_questions, is_complete)
used_summary_fallback = False
if is_complete and not has_results:
    fallback_rows = build_summary_fallback_rows(summary_path)
    if fallback_rows:
        matrix_rows = fallback_rows
        used_summary_fallback = True

st.subheader("策略 × 模型最终结果矩阵" if is_complete else "策略 × 模型实时指标矩阵")
if used_summary_fallback:
    st.caption("results.jsonl unavailable; showing completed summary.json fallback.")
else:
    st.caption(f"Auto refresh interval: {REFRESH_INTERVAL_SECONDS}s" if not is_complete else "Run complete.")

matrix_df = pd.DataFrame(matrix_rows)
visible_columns = ["策略", "模型", "状态", "完成", "正确", "准确率", "平均 wall time", "平均 thinking tokens", "单题成本", "总成本"]
st.dataframe(style_matrix(matrix_df[visible_columns]), use_container_width=True, hide_index=True)

if is_active_run:
    show_mistake_summary(results_path)

if is_active_run and is_complete and summary_path.exists():
    show_completion_report_sections(run_dir, summary_path)

if not is_complete:
    time.sleep(REFRESH_INTERVAL_SECONDS)
    st.rerun()
