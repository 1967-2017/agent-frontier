from __future__ import annotations

SCENARIOS = [
    {
        "id": "retry_tasks",
        "name": "场景 1：三任务执行与重试",
        "description": "跑 arXiv、GitHub issues、本地表单三个任务，每个最多重试 1 次。",
    },
    {
        "id": "network_drop",
        "name": "场景 2：中途断网 5 秒",
        "description": "使用本地表单任务演示可控 5 秒网络故障，Agent retry 或明确失败但不崩溃。",
    },
    {
        "id": "modal_wall",
        "name": "场景 3：Cookie / 登录墙弹窗",
        "description": "使用本地弹窗页面演示 Agent 识别并处理遮挡弹窗。",
    },
    {
        "id": "blacklist_url",
        "name": "场景 4：黑名单 URL 拒绝",
        "description": "访问黑名单 URL 时在策略层直接拒绝，不真实导航。",
    },
    {
        "id": "replay_trace",
        "name": "场景 5：trace replay 可视化",
        "description": "使用同一 Streamlit 布局可视化回放 trace.jsonl 操作序列。",
    },
]

SCENARIO_BY_ID = {scenario["id"]: scenario for scenario in SCENARIOS}


def scenario_ids() -> list[str]:
    return [scenario["id"] for scenario in SCENARIOS]
