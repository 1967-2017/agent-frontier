from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from . import prompts, resources, tools
from .trace import TraceEvent, append_trace

mcp = FastMCP("demo1-ops-server")


@mcp.tool()
def query_metric(service: str, metric: str, window: str) -> dict:
    """Return structured time-series metric data for a service."""
    return tools.query_metric(service, metric, window)


@mcp.tool()
def tail_log(service: str, lines: int, level: str) -> dict:
    """Return recent log entries for a service filtered by level."""
    return tools.tail_log(service, lines, level)


@mcp.tool()
def restart_service(service: str, dry_run: bool = True) -> dict:
    """Preview or execute a service restart. Defaults to dry_run=true."""
    return tools.restart_service(service, dry_run)


@mcp.tool()
def notify_oncall(service: str, summary: str, severity: str) -> dict:
    """Append an on-call notification to notifications.jsonl."""
    return tools.notify_oncall(service, summary, severity)


@mcp.resource("incident://list")
def incident_list() -> str:
    return json.dumps(resources.incident_list(), ensure_ascii=False, indent=2)


@mcp.resource("runbook://{service}")
def runbook(service: str) -> str:
    return resources.runbook(service)


@mcp.prompt("oncall-triage")
def oncall_triage(service: str) -> str:
    return prompts.oncall_triage(service)


def main() -> None:
    append_trace(
        TraceEvent(
            event_type="server",
            name="start",
            input={"transport": "stdio"},
            output={"server": "demo1-ops-server"},
            status="ok",
            duration_ms=0,
        )
    )
    try:
        mcp.run(transport="stdio")
    finally:
        append_trace(
            TraceEvent(
                event_type="server",
                name="stop",
                input={"transport": "stdio"},
                output={"server": "demo1-ops-server"},
                status="ok",
                duration_ms=0,
            )
        )


if __name__ == "__main__":
    main()
