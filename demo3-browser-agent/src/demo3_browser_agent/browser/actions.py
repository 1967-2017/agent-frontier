from __future__ import annotations

import asyncio

from playwright.async_api import Page

from demo3_browser_agent.schemas import AgentDecision, BrowserActionType, Mark


async def execute_action(page: Page, decision: AgentDecision, marks: list[Mark]) -> dict:
    action = decision.action_type
    if action == BrowserActionType.click:
        mark = _require_mark(marks, decision.mark_id)
        await page.mouse.click(mark.center[0], mark.center[1])
        await _settle(page)
        return {"ok": True, "action": "click", "mark_id": mark.id}
    if action == BrowserActionType.type:
        mark = _require_mark(marks, decision.mark_id)
        await page.mouse.click(mark.center[0], mark.center[1])
        await page.keyboard.press("Control+A")
        await page.keyboard.type(decision.text or "")
        await _settle(page)
        return {"ok": True, "action": "type", "mark_id": mark.id, "text_length": len(decision.text or "")}
    if action == BrowserActionType.press:
        await page.keyboard.press(decision.key or "")
        await _settle(page)
        return {"ok": True, "action": "press", "key": decision.key}
    if action == BrowserActionType.scroll:
        direction = (decision.direction or "down").lower()
        amount = -650 if direction == "up" else 650
        await page.mouse.wheel(0, amount)
        await _settle(page)
        return {"ok": True, "action": "scroll", "direction": direction}
    if action == BrowserActionType.wait:
        seconds = min(float(decision.seconds or 1), 10)
        await asyncio.sleep(seconds)
        return {"ok": True, "action": "wait", "seconds": seconds}
    if action == BrowserActionType.navigate:
        await page.goto(decision.url or "", wait_until="domcontentloaded", timeout=45000)
        await _settle(page)
        return {"ok": True, "action": "navigate", "url": decision.url}
    if action in {BrowserActionType.finish, BrowserActionType.fail}:
        return {"ok": True, "action": action.value, "summary": decision.summary}
    return {"ok": False, "action": action.value, "error": "unsupported action"}


def _require_mark(marks: list[Mark], mark_id: int | None) -> Mark:
    for mark in marks:
        if mark.id == mark_id:
            return mark
    raise RuntimeError(f"unknown mark_id: {mark_id}")


async def _settle(page: Page) -> None:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    await page.wait_for_timeout(700)
