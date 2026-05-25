from __future__ import annotations

import time
from collections import Counter
from typing import Any

from rich import box
from rich.align import Align
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .trace import diff_params, read_trace

STYLE_BY_TYPE = {
    "tool": "cyan",
    "resource": "green",
    "prompt": "magenta",
    "server": "yellow",
    "error": "red",
}


def _event_line(event: dict[str, Any]) -> Text:
    event_type = event.get("event_type", "unknown")
    style = STYLE_BY_TYPE.get(event_type, "white")
    status = event.get("status", "unknown")
    name = event.get("name", "unknown")
    ts = event.get("ts", "")
    params = event.get("input", {})
    text = Text()
    text.append(f"{ts} ", style="dim")
    text.append(f"[{event_type}]", style=style)
    text.append(f" {name}", style="bold")
    text.append(f" status={status}", style="green" if status == "ok" else "red")
    if params:
        text.append(f" input={params}", style="white")
    if event.get("error"):
        text.append(f" error={event['error']}", style="red")
    return text


def _trace_panel(events: list[dict[str, Any]]) -> Panel:
    lines = [_event_line(event) for event in events[-24:]]
    content = Group(*lines) if lines else Align.center("Waiting for MCP events...", vertical="middle")
    return Panel(content, title="Real-time trace", border_style="blue", box=box.ASCII)


def _recent_diff(events: list[dict[str, Any]]) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    last_by_name: dict[str, dict[str, Any]] = {}
    recent: list[tuple[str, dict[str, dict[str, Any]]]] = []
    for event in events:
        name = event.get("name", "unknown")
        current = event.get("input", {}) or {}
        delta = diff_params(last_by_name.get(name), current)
        if delta:
            recent.append((name, delta))
        last_by_name[name] = current
    for name, delta in recent[-5:]:
        rendered = ", ".join(
            f"{key}: {change['before']} -> {change['after']}" for key, change in delta.items()
        )
        table.add_row(name, rendered)
    if not recent:
        table.add_row("none", "No parameter changes yet")
    return table


def _stats_panel(events: list[dict[str, Any]]) -> Panel:
    event_counts = Counter(event.get("event_type", "unknown") for event in events)
    tool_counts = Counter(
        event.get("name", "unknown") for event in events if event.get("event_type") == "tool"
    )
    resource_counts = Counter(
        event.get("name", "unknown") for event in events if event.get("event_type") == "resource"
    )
    prompt_counts = Counter(
        event.get("name", "unknown") for event in events if event.get("event_type") == "prompt"
    )

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Total calls", str(len([e for e in events if e.get("event_type") in {"tool", "resource", "prompt"}])))
    table.add_row("Tool events", str(event_counts.get("tool", 0)))
    for name, count in sorted(tool_counts.items()):
        table.add_row(f"  - {name}", str(count))
    table.add_row("Resource events", str(event_counts.get("resource", 0)))
    for name, count in sorted(resource_counts.items()):
        table.add_row(f"  - {name}", str(count))
    table.add_row("Prompt events", str(event_counts.get("prompt", 0)))
    for name, count in sorted(prompt_counts.items()):
        table.add_row(f"  - {name}", str(count))
    table.add_row("Server events", str(event_counts.get("server", 0)))

    group = Group(table, Panel(_recent_diff(events), title="Recent parameter diff", border_style="cyan", box=box.ASCII))
    return Panel(group, title="Stats", border_style="green", box=box.ASCII)


def _layout() -> Table:
    events = read_trace()
    table = Table.grid(expand=True)
    table.add_column(ratio=3)
    table.add_column(ratio=2)
    table.add_row(_trace_panel(events), _stats_panel(events))
    return table


def main() -> None:
    with Live(_layout(), refresh_per_second=4, screen=True) as live:
        while True:
            live.update(_layout())
            time.sleep(0.25)


if __name__ == "__main__":
    main()
