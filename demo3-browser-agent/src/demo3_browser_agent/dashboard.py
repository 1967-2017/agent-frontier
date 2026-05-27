from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from demo3_browser_agent.config import dashboard_refresh_seconds, latest_path, project_root
from demo3_browser_agent.trace import read_jsonl


STATUS_LABELS = {
    "pending": "等待中",
    "running": "运行中",
    "passed": "已通过",
    "failed": "失败",
    "interrupted": "已中断",
}

STATUS_BADGES = {
    "pending": "⏳",
    "running": "⏳",
    "passed": "✅",
    "failed": "❌",
    "interrupted": "❌",
}

ACTION_LABELS = {
    "click": "点击",
    "type": "输入",
    "press": "按键",
    "scroll": "滚动",
    "wait": "等待",
    "navigate": "跳转",
    "finish": "完成",
    "fail": "失败",
}


def _latest_run_dir() -> Path | None:
    try:
        data = json.loads(latest_path().read_text(encoding="utf-8"))
        return Path(data["run_dir"])
    except Exception:
        return None


def _load_state(run_dir: Path | None) -> dict | None:
    if not run_dir:
        return None
    path = run_dir / "state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _status(value: str) -> str:
    return STATUS_LABELS.get(value, value)


def _badge(value: str) -> str:
    return STATUS_BADGES.get(value, "⏳")


def _action(value: str) -> str:
    return ACTION_LABELS.get(value, value)


def _elapsed_seconds(run_dir: Path | None, state: dict | None) -> float:
    if not run_dir or not state:
        return 0.0
    events = read_jsonl(run_dir / "trace.jsonl")
    if not events:
        return 0.0
    start = _parse_ts(events[0].get("ts"))
    end = _parse_ts(events[-1].get("ts"))
    if state.get("status") == "running":
        end = datetime.now(UTC)
    if not start or not end:
        return 0.0
    return max((end - start).total_seconds(), 0.0)


def _parse_ts(value: object) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))


def _format_elapsed(seconds: float) -> str:
    minutes, remaining = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {remaining}s"
    if minutes:
        return f"{minutes}m {remaining}s"
    return f"{remaining}s"


st.set_page_config(page_title="Demo 3 浏览器 Agent", layout="wide")
st.title("Demo 3：浏览器 Agent / Computer Use")
st.caption("左侧展示真实浏览器截图与 Set-of-Mark 标注，右侧展示 Agent 的决策过程、动作、成本与任务状态。")

refresh_seconds = dashboard_refresh_seconds()

if "run_process" not in st.session_state:
    st.session_state.run_process = None

controls = st.columns([1, 1, 1, 3])
with controls[0]:
    if st.button("运行全部任务", use_container_width=True):
        if st.session_state.run_process is None or st.session_state.run_process.poll() is not None:
            st.session_state.run_process = subprocess.Popen([sys.executable, "-m", "demo3_browser_agent.runner"], cwd=project_root())
with controls[1]:
    auto_refresh = st.toggle("实时刷新", value=True)
with controls[2]:
    if st.button("手动刷新", use_container_width=True):
        st.rerun()

run_dir = _latest_run_dir() if latest_path().exists() else None
state = _load_state(run_dir) if run_dir else None
left, right = st.columns([7, 3])

with left:
    st.subheader("浏览器 / 页面视图")
    if run_dir and state and state.get("current_marked_screenshot"):
        image_path = run_dir / state["current_marked_screenshot"]
        if image_path.exists():
            st.image(str(image_path), use_container_width=True)
        else:
            st.info(f"等待截图生成：{image_path}")
    else:
        st.info("暂无运行记录。点击“运行全部任务”，或在终端执行 make run-all。")
    if state:
        st.caption(f"当前 URL：{state.get('current_url', '')}")

with right:
    st.subheader("Agent 决策过程")
    if state:
        st.caption(
            f"耗时 {_format_elapsed(_elapsed_seconds(run_dir, state))} · "
            f"输入 {state.get('total_input_tokens', 0)} tokens · "
            f"输出 {state.get('total_output_tokens', 0)} tokens · "
            f"预估成本 ${state.get('total_cost_usd', 0.0):.4f}"
        )
        st.metric("步骤", f"{state.get('step', 0)} / {state.get('max_steps', 30)}")
        st.write("**模型一句话推理**")
        st.info(state.get("current_thought") or "等待模型决策")
        st.write("**即将执行 / 最近执行动作**")
        st.warning(_action(state.get("current_action") or "-"))
        st.write("**任务状态**")
        for task in state.get("tasks", {}).values():
            status = task["status"]
            st.write(f"{_badge(status)} `{_status(status)}` {task['name']}")
        st.write("**最近事件**")
        for event in reversed(state.get("recent_events", [])[-5:]):
            st.json(event)
    else:
        st.info("运行开始后，这里会显示实时状态。")

if run_dir:
    st.subheader("Trace 事件")
    events = read_jsonl(run_dir / "trace.jsonl")[-12:]
    for event in events:
        label = event.get("message") or event.get("event_type")
        st.text(f"{event.get('ts')} · {label}")

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
