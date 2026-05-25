from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from mcp import ClientSession, StdioServerParameters
import mcp.client.stdio as stdio_module
from mcp.client.stdio import stdio_client
from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .trace import read_trace

SERVER_COMMAND = sys.executable
SERVER_ARGS = ["-m", "demo1_mcp.server"]


@dataclass
class CaseResult:
    id: int
    scenario: str
    status: str
    evidence: str
    detail: str = ""


@dataclass
class CaseState:
    id: int
    scenario: str
    status: str = "PENDING"
    evidence: str = ""
    detail: str = ""


@dataclass(frozen=True)
class AcceptanceConfig:
    service: str = "payment-api"
    metric: str = "p99"
    window: str = "15m"


@dataclass
class DemoResult:
    demo: str
    cases: list[CaseResult]

    @property
    def passed(self) -> int:
        return sum(1 for case in self.cases if case.status == "PASS")

    @property
    def failed(self) -> int:
        return sum(1 for case in self.cases if case.status == "FAIL")

    def to_json(self) -> dict[str, Any]:
        return {
            "demo": self.demo,
            "summary": {"passed": self.passed, "failed": self.failed, "total": len(self.cases)},
            "cases": [asdict(case) for case in self.cases],
        }


async def with_session(fn: Callable[[ClientSession], Awaitable[Any]]) -> Any:
    params = StdioServerParameters(command=SERVER_COMMAND, args=SERVER_ARGS)
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)


def _text_from_content_blocks(blocks: list[Any]) -> str:
    values: list[str] = []
    for block in blocks:
        text = getattr(block, "text", None)
        if text is not None:
            values.append(text)
    return "\n".join(values)


def _json_from_tool_result(result: Any) -> dict[str, Any]:
    text = _text_from_content_blocks(result.content)
    if not text:
        raise AssertionError("tool result did not contain text content")
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        return parsed
    raise AssertionError("tool result was not a JSON object")


async def case_query_metric(config: AcceptanceConfig) -> CaseResult:
    async def run(session: ClientSession) -> dict[str, Any]:
        result = await session.call_tool(
            "query_metric",
            {"service": config.service, "metric": config.metric, "window": config.window},
        )
        payload = _json_from_tool_result(result)
        assert payload["service"] == config.service
        assert payload["metric"] == config.metric
        assert payload["window"] == config.window
        assert isinstance(payload.get("points"), list)
        assert isinstance(payload.get("summary"), dict)
        return payload

    payload = await with_session(run)
    return CaseResult(1, "query_metric tool", "PASS", "tool", f"points={len(payload['points'])}")


async def case_reconnect(config: AcceptanceConfig) -> CaseResult:
    async def run(session: ClientSession) -> list[str]:
        result = await session.list_tools()
        return [tool.name for tool in result.tools]

    first = await with_session(run)
    second = await with_session(run)
    required = {"query_metric", "tail_log", "restart_service", "notify_oncall"}
    assert required.issubset(set(first))
    assert required.issubset(set(second))
    return CaseResult(2, "second client reconnect", "PASS", "stdio", "same command accepted twice")


async def case_restart_safety(config: AcceptanceConfig) -> CaseResult:
    async def run(session: ClientSession) -> tuple[dict[str, Any], dict[str, Any]]:
        dry_result = await session.call_tool("restart_service", {"service": config.service})
        dry = _json_from_tool_result(dry_result)
        assert dry["service"] == config.service
        assert dry["dry_run"] is True
        assert dry["executed"] is False

        execute_result = await session.call_tool(
            "restart_service", {"service": config.service, "dry_run": False}
        )
        executed = _json_from_tool_result(execute_result)
        assert executed["service"] == config.service
        assert executed["dry_run"] is False
        assert executed["executed"] is True
        assert isinstance(executed.get("restart_count"), int)
        return dry, executed

    dry, executed = await with_session(run)
    return CaseResult(
        3,
        "restart dry-run safety",
        "PASS",
        "tool",
        f"dry_run={dry['dry_run']} restart_count={executed['restart_count']}",
    )


async def case_incident_resource(config: AcceptanceConfig) -> CaseResult:
    async def run(session: ClientSession) -> dict[str, Any]:
        result = await session.read_resource("incident://list")
        assert result.contents, "resource returned no contents"
        text = getattr(result.contents[0], "text", "")
        payload = json.loads(text)
        assert isinstance(payload.get("incidents"), list)
        return payload

    payload = await with_session(run)
    return CaseResult(4, "incident resource channel", "PASS", "resource", f"incidents={len(payload['incidents'])}")


async def case_prompt_fill(config: AcceptanceConfig) -> CaseResult:
    async def run(session: ClientSession) -> str:
        result = await session.get_prompt("oncall-triage", {"service": config.service})
        assert result.messages, "prompt returned no messages"
        content = result.messages[0].content
        text = getattr(content, "text", "")
        assert config.service in text
        assert f"restart_service({config.service})" in text
        return text

    text = await with_session(run)
    return CaseResult(5, "oncall prompt fill", "PASS", "prompt", f"chars={len(text)}")


async def case_shutdown_error(config: AcceptanceConfig) -> CaseResult:
    params = StdioServerParameters(command=SERVER_COMMAND, args=SERVER_ARGS)
    original_create_process = stdio_module._create_platform_compatible_process
    server_process: Any | None = None
    client_error_detail: str | None = None
    shutdown_started = False
    unexpected_success = False

    async def capture_process(*args: Any, **kwargs: Any) -> Any:
        nonlocal server_process
        server_process = await original_create_process(*args, **kwargs)
        return server_process

    stdio_module._create_platform_compatible_process = capture_process
    try:
        try:
            with open(os.devnull, "w", encoding="utf-8") as errlog:
                async with stdio_client(params, errlog=errlog) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        if server_process is None:
                            raise AssertionError("could not capture stdio server process for shutdown test")
                        shutdown_started = True
                        server_process.terminate()
                        try:
                            await asyncio.wait_for(server_process.wait(), timeout=5)
                        except asyncio.TimeoutError:
                            server_process.kill()
                            await server_process.wait()
                            raise AssertionError("server process did not terminate cleanly")
                        try:
                            await asyncio.wait_for(session.list_tools(), timeout=3)
                        except Exception as exc:
                            message = str(exc) or exc.__class__.__name__
                            client_error_detail = f"{exc.__class__.__name__}: {message[:120]}"
                        else:
                            unexpected_success = True
        except Exception as exc:
            if unexpected_success:
                raise AssertionError("client call unexpectedly succeeded after server shutdown") from exc
            if not shutdown_started:
                raise
            if client_error_detail is None:
                message = str(exc) or exc.__class__.__name__
                client_error_detail = f"{exc.__class__.__name__}: {message[:120]}"
    finally:
        stdio_module._create_platform_compatible_process = original_create_process

    if unexpected_success:
        raise AssertionError("client call unexpectedly succeeded after server shutdown")
    if client_error_detail is None:
        raise AssertionError("client did not report an error after server shutdown")
    return CaseResult(6, "server shutdown error", "PASS", "client error", client_error_detail)


CaseFn = Callable[[AcceptanceConfig], Awaitable[CaseResult]]


CASE_DEFS: list[tuple[int, str, CaseFn]] = [
    (1, "query_metric tool", case_query_metric),
    (2, "second client reconnect", case_reconnect),
    (3, "restart dry-run safety", case_restart_safety),
    (4, "incident resource channel", case_incident_resource),
    (5, "oncall prompt fill", case_prompt_fill),
    (6, "server shutdown error", case_shutdown_error),
]


def select_cases(case_filter: str | None) -> list[tuple[int, str, CaseFn]]:
    if not case_filter:
        return CASE_DEFS
    aliases = {
        "query_metric": 1,
        "query": 1,
        "reconnect": 2,
        "restart": 3,
        "restart_service": 3,
        "resource": 4,
        "incident": 4,
        "prompt": 5,
        "oncall": 5,
        "shutdown": 6,
        "error": 6,
    }
    requested: set[int] = set()
    for raw in case_filter.split(","):
        token = raw.strip().lower().replace("-", "_")
        if not token:
            continue
        if token.isdigit():
            requested.add(int(token))
        elif token in aliases:
            requested.add(aliases[token])
        else:
            raise ValueError(f"Unknown case selector: {raw}")
    selected = [case for case in CASE_DEFS if case[0] in requested]
    if not selected:
        raise ValueError(f"No cases selected by: {case_filter}")
    return selected


async def run_case(fn: CaseFn, fallback_id: int, scenario: str, config: AcceptanceConfig) -> CaseResult:
    try:
        return await fn(config)
    except Exception as exc:
        return CaseResult(fallback_id, scenario, "FAIL", "error", str(exc))


async def run_acceptance(config: AcceptanceConfig, case_filter: str | None = None) -> DemoResult:
    cases: list[CaseResult] = []
    for case_id, scenario, fn in select_cases(case_filter):
        cases.append(await run_case(fn, case_id, scenario, config))
    return DemoResult("demo1-mcp-server", cases)


def _status_style(status: str) -> str:
    return {
        "PASS": "bold green",
        "FAIL": "bold red",
        "RUNNING": "bold yellow",
        "PENDING": "dim",
    }.get(status, "white")


def _event_line(event: dict[str, Any]) -> Text:
    event_type = event.get("event_type", "unknown")
    style = {"tool": "cyan", "resource": "green", "prompt": "magenta", "server": "yellow"}.get(event_type, "white")
    text = Text()
    text.append(str(event.get("ts", ""))[-13:] + " ", style="dim")
    text.append(f"[{event_type}] ", style=style)
    text.append(str(event.get("name", "unknown")), style="bold")
    if event.get("input"):
        text.append(f" {event['input']}")
    return text


def _trace_panel() -> Panel:
    events = read_trace()
    rows = [_event_line(event) for event in events[-18:]]
    content = Group(*rows) if rows else Text("Waiting for MCP trace events...", style="dim")
    return Panel(content, title="real-time trace", border_style="blue", box=box.ASCII)


def _status_panel(states: list[CaseState]) -> Panel:
    table = Table(box=box.ASCII, expand=True, show_lines=True)
    table.add_column("#", justify="right", width=3, no_wrap=True)
    table.add_column("scenario", ratio=4, overflow="fold")
    table.add_column("status", justify="center", width=9, no_wrap=True)
    table.add_column("result", ratio=5, overflow="fold")
    for state in states:
        style = _status_style(state.status)
        result = " | ".join(part for part in (state.evidence, state.detail) if part)
        table.add_row(
            str(state.id),
            state.scenario,
            f"[{style}]{state.status}[/{style}]",
            result,
        )
    passed = sum(1 for state in states if state.status == "PASS")
    failed = sum(1 for state in states if state.status == "FAIL")
    running = sum(1 for state in states if state.status == "RUNNING")
    title = f"status | pass={passed} fail={failed} running={running} total={len(states)}"
    return Panel(table, title=title, border_style="green" if failed == 0 else "red", box=box.ASCII)


def _summary_panel(states: list[CaseState]) -> Table:
    width = shutil.get_terminal_size(fallback=(120, 30)).columns
    layout = Table.grid(expand=True)
    if width >= 110:
        layout.add_column(ratio=1)
        layout.add_column(ratio=1)
        layout.add_row(_trace_panel(), _status_panel(states))
    else:
        layout.add_column()
        layout.add_row(_trace_panel())
        layout.add_row(_status_panel(states))
    return layout


async def run_acceptance_live(config: AcceptanceConfig, case_filter: str | None = None) -> DemoResult:
    selected_cases = select_cases(case_filter)
    states = [CaseState(case_id, scenario) for case_id, scenario, _ in selected_cases]
    results: list[CaseResult] = []
    console = Console()
    with Live(_summary_panel(states), console=console, refresh_per_second=6, screen=False) as live:
        for index, (case_id, scenario, fn) in enumerate(selected_cases):
            states[index].status = "RUNNING"
            live.update(_summary_panel(states))
            result = await run_case(fn, case_id, scenario, config)
            results.append(result)
            states[index].status = result.status
            states[index].evidence = result.evidence
            states[index].detail = result.detail
            live.update(_summary_panel(states))
        await asyncio.sleep(0.2)
        live.update(_summary_panel(states))
    return DemoResult("demo1-mcp-server", results)


def render_summary(result: DemoResult) -> None:
    states = [CaseState(case.id, case.scenario, case.status, case.evidence, case.detail) for case in result.cases]
    console = Console()
    console.print(_summary_panel(states))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Demo1 MCP Server acceptance checks")
    parser.add_argument("--case", dest="case_filter", help="Run selected cases by id/name, e.g. 1,3 or query_metric")
    parser.add_argument("--service", default="payment-api", help="Service name used by configurable cases")
    parser.add_argument("--metric", default="p99", help="Metric name used by query_metric")
    parser.add_argument("--window", default="15m", help="Metric window used by query_metric")
    parser.add_argument("--json", action="store_true", help="Print JSON result instead of Rich summary")
    parser.add_argument("--no-live", action="store_true", help="Disable live trace/status panel")
    args = parser.parse_args()
    config = AcceptanceConfig(service=args.service, metric=args.metric, window=args.window)
    try:
        result = asyncio.run(
            run_acceptance(config, args.case_filter)
            if args.no_live or args.json
            else run_acceptance_live(config, args.case_filter)
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result.to_json(), ensure_ascii=False, indent=2))
    elif args.no_live:
        render_summary(result)
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
