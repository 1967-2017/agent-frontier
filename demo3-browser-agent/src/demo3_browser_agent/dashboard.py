from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from demo3_browser_agent.config import dashboard_refresh_seconds, latest_path, project_root
from demo3_browser_agent.replay_view import ReplayFrame, build_replay_frames, get_latest_trace, load_trace
from demo3_browser_agent.scenarios import SCENARIOS
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

FRONTEND_SCENARIOS = [
    {"label": "1. arxiv", "command": "task", "value": "arxiv"},
    {"label": "2. github", "command": "task", "value": "github-issues"},
    {"label": "3. local", "command": "task", "value": "local-form"},
    {"label": "4. 中途断网5秒", "command": "scenario", "value": "network_drop"},
    {"label": "5. cookie弹窗", "command": "scenario", "value": "modal_wall"},
    {"label": "6. 黑名单url拒绝", "command": "scenario", "value": "blacklist_url"},
    {"label": "7. trace replay可视化", "command": "scenario", "value": "replay_trace"},
]

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


def _demo_mode() -> str:
    mode = os.environ.get("DEMO3_MODE", "interactive").strip().lower()
    return mode if mode in {"interactive", "all", "replay"} else "interactive"

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


def _timer_running(state: dict | None) -> bool:
    return bool(state and state.get("status") == "running")


def _render_status_bar(run_dir: Path | None, state: dict) -> None:
    elapsed = _format_elapsed(_elapsed_seconds(run_dir, state))
    total_tokens = int(state.get("total_input_tokens", 0) or 0) + int(state.get("total_output_tokens", 0) or 0)
    cost_usd = float(state.get("total_cost_usd", 0.0) or 0.0)
    icon_class = "running" if _timer_running(state) else ""
    st.markdown(
        f"""
        <div class="demo3-status-bar">
            <span class="demo3-status-icon {icon_class}">✳</span>
            <span class="demo3-status-text">{elapsed} · {total_tokens:,} tokens · ${cost_usd:.4f}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_replay_status_bar(frame: ReplayFrame, playing: bool) -> None:
    total_tokens = frame.total_input_tokens + frame.total_output_tokens
    icon_class = "running" if playing else ""
    st.markdown(
        f"""
        <div class="demo3-status-bar">
            <span class="demo3-status-icon {icon_class}">✳</span>
            <span class="demo3-status-text">Frame {frame.index + 1} · {total_tokens:,} tokens · ${frame.total_cost_usd:.4f}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _is_process_idle() -> bool:
    process = st.session_state.run_process
    return process is None or process.poll() is not None


def _start_scenario(scenario_id: str, all_mode: bool = False) -> None:
    if not _is_process_idle():
        return
    args = [sys.executable, "-m", "demo3_browser_agent.scenario_runner"]
    args.append("--all" if all_mode else "--scenario")
    if not all_mode:
        args.append(scenario_id)
    st.session_state.run_process = subprocess.Popen(args, cwd=project_root())


def _start_task(task_id: str) -> None:
    if not _is_process_idle():
        return
    args = [sys.executable, "-m", "demo3_browser_agent.runner", "--tasks", task_id]
    st.session_state.run_process = subprocess.Popen(args, cwd=project_root())


def _render_live_left(run_dir: Path | None, state: dict | None) -> None:
    st.subheader("浏览器 / 页面视图")
    if state and state.get("current_scenario") == "blacklist_url" and not state.get("current_marked_screenshot"):
        st.error("访问被阻止")
        st.write("**URL:** https://malware.test/")
        st.write("**原因:** 命中黑名单策略，未执行真实导航。")
    elif run_dir and state and state.get("current_marked_screenshot"):
        image_path = run_dir / state["current_marked_screenshot"]
        if image_path.exists():
            st.image(str(image_path), use_container_width=True)
        else:
            st.info(f"等待截图生成：{image_path}")
    else:
        st.info("暂无运行记录。请选择场景并点击运行。")
    if state and state.get("current_url"):
        st.caption(f"当前 URL：{state.get('current_url', '')}")


def _render_status_panel(run_dir: Path | None, state: dict | None) -> None:
    st.subheader("Agent 决策过程")
    if not state:
        st.info("运行开始后，这里会显示实时状态。")
        return
    _render_status_bar(run_dir, state)
    st.metric("步骤", f"Step {state.get('step', 0)} / Max {state.get('max_steps', 30)}")
    st.caption(f"模式：{state.get('mode', '-')} · 场景：{state.get('current_scenario') or '-'} · 状态：{_status(state.get('status', '-'))}")
    st.write("**模型一句话推理**")
    st.info(_one_sentence(state.get("current_thought") or "等待模型决策"))
    st.write("**即将执行动作**")
    st.warning(_action(state.get("current_action") or "-"))
    st.write("**任务状态**")
    for task in state.get("tasks", {}).values():
        status = task["status"]
        st.write(f"{_badge(status)} `{_status(status)}` {task['name']}")
    if state.get("summary", {}).get("demo_all"):
        _render_demo_all_summary(state["summary"]["demo_all"])
    elif state.get("status") != "running" and state.get("summary"):
        st.write("**本轮总结**")
        st.json(state["summary"])
    st.write("**最近事件**")
    for event in reversed(state.get("recent_events", [])[-5:]):
        st.json(event)


def _render_demo_all_summary(summary: dict) -> None:
    st.write("**本轮 Demo 总览**")
    rows = []
    for index, scenario in enumerate(summary.get("scenarios", []), 1):
        rows.append({
            "#": index,
            "场景": scenario.get("name"),
            "状态": _badge(scenario.get("status", "failed")),
            "重试": scenario.get("retries", 0),
            "耗时": f"{scenario.get('duration_seconds', 0)}s",
        })
    if rows:
        st.table(rows)
    st.success(f"结论：{summary.get('passed', 0)} / {summary.get('total', 0)} 通过")


def _one_sentence(value: str) -> str:
    text = str(value).strip()
    for marker in ["。", ".", "！", "!"]:
        if marker in text:
            return text.split(marker, 1)[0] + marker
    return text


def _render_replay(left, right) -> bool:
    trace_path = get_latest_trace()
    if not trace_path:
        with left:
            st.info("暂无 trace，可先运行 demo 或 demo-all。")
        with right:
            st.info("Replay 等待 trace.jsonl。")
        return False
    frames = build_replay_frames(load_trace(trace_path), trace_path)
    if not frames:
        with left:
            st.info(f"Trace 为空：{trace_path}")
        return False
    if "replay_index" not in st.session_state:
        st.session_state.replay_index = 0
    if "replay_playing" not in st.session_state:
        st.session_state.replay_playing = False
    st.session_state.replay_index = min(st.session_state.replay_index, len(frames) - 1)
    frame = frames[st.session_state.replay_index]
    with left:
        st.subheader("Replay 画面")
        if frame.screenshot_path and frame.screenshot_path.exists():
            st.image(str(frame.screenshot_path), use_container_width=True)
        else:
            st.info(frame.summary or frame.event_type)
        st.caption(f"trace: {trace_path}")
    with right:
        st.subheader("Agent 决策过程")
        _render_replay_status_bar(frame, st.session_state.replay_playing)
        st.metric("步骤", f"Step {frame.index + 1} / Max {len(frames)}")
        st.write("**模型一句话推理**")
        st.info(_one_sentence(frame.reasoning_summary or frame.summary or "等待模型决策"))
        st.write("**即将执行动作**")
        st.warning(_action(frame.action or "-"))
        st.write("**任务状态**")
        for task_id, status in frame.task_statuses.items():
            st.write(f"{_badge(status)} `{_status(status)}` {task_id}")
        cols = st.columns(3)
        if cols[0].button("上一帧", use_container_width=True):
            st.session_state.replay_index = max(st.session_state.replay_index - 1, 0)
            st.rerun()
        if cols[1].button("暂停" if st.session_state.replay_playing else "播放", use_container_width=True):
            st.session_state.replay_playing = not st.session_state.replay_playing
            st.rerun()
        if cols[2].button("下一帧", use_container_width=True):
            st.session_state.replay_index = min(st.session_state.replay_index + 1, len(frames) - 1)
            st.rerun()
        st.session_state.replay_index = st.slider("Frame", 0, len(frames) - 1, st.session_state.replay_index)
    if st.session_state.replay_playing:
        time.sleep(0.8)
        st.session_state.replay_index = min(st.session_state.replay_index + 1, len(frames) - 1)
        if st.session_state.replay_index >= len(frames) - 1:
            st.session_state.replay_playing = False
        st.rerun()
    return False


st.set_page_config(page_title="Demo 3 浏览器 Agent", layout="wide")
st.markdown(
    """
    <style>
    .demo3-status-bar {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        background: #1f1f1f;
        color: #bdbdbd;
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 15px;
        font-weight: 600;
        line-height: 1;
        margin-bottom: 10px;
        width: fit-content;
        max-width: 100%;
    }
    .demo3-status-icon {
        color: #ff7a1a;
        font-size: 18px;
        line-height: 1;
        display: inline-block;
        transform-origin: 50% 50%;
    }
    .demo3-status-icon.running {
        animation: demo3-spin 1.2s linear infinite;
    }
    @keyframes demo3-spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    .demo3-status-text {
        white-space: nowrap;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
mode = _demo_mode()
st.title("Demo 3：浏览器 Agent / Computer Use")
st.caption("左侧展示真实浏览器截图与 Set-of-Mark 标注，右侧展示 Agent 的决策过程、动作、成本与任务状态。")
st.caption(f"当前模式：`{mode}`")

refresh_seconds = dashboard_refresh_seconds()

if "run_process" not in st.session_state:
    st.session_state.run_process = None
if "demo_all_started" not in st.session_state:
    st.session_state.demo_all_started = False

scenario_options = {scenario["label"]: scenario for scenario in FRONTEND_SCENARIOS}
controls = st.columns([2, 1, 1, 3])
with controls[0]:
    selected_name = st.selectbox("选择场景", list(scenario_options.keys()), disabled=mode != "interactive")
with controls[1]:
    if mode == "all":
        if st.button("运行全部场景", use_container_width=True):
            _start_scenario("retry_tasks", all_mode=True)
            st.session_state.demo_all_started = True
    elif mode == "replay":
        st.button("Replay 模式", disabled=True, use_container_width=True)
    elif st.button("运行场景", use_container_width=True):
        selected = scenario_options[selected_name]
        if selected["command"] == "task":
            _start_task(selected["value"])
        else:
            _start_scenario(selected["value"])
with controls[2]:
    auto_refresh = st.toggle("实时刷新", value=mode != "replay")
with controls[3]:
    if st.button("手动刷新", use_container_width=True):
        st.rerun()

if mode == "all" and not st.session_state.demo_all_started:
    _start_scenario("retry_tasks", all_mode=True)
    st.session_state.demo_all_started = True

run_dir = _latest_run_dir() if latest_path().exists() else None
state = _load_state(run_dir) if run_dir else None
left, right = st.columns([7, 3])

if mode == "replay":
    auto_refresh = _render_replay(left, right)
else:
    with left:
        _render_live_left(run_dir, state)
    with right:
        _render_status_panel(run_dir, state)

if run_dir:
    st.subheader("Trace 事件")
    events = read_jsonl(run_dir / "trace.jsonl")[-12:]
    for event in events:
        label = event.get("message") or event.get("event_type")
        st.text(f"{event.get('ts')} · {label}")

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
