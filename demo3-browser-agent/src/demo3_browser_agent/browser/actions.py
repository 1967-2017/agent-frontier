from __future__ import annotations

import asyncio

from playwright.async_api import Page

from demo3_browser_agent.schemas import AgentDecision, BrowserActionType, Mark


async def execute_action(page: Page, decision: AgentDecision, marks: list[Mark]) -> dict:
    action = decision.action_type
    if action == BrowserActionType.click:
        mark = _require_mark(marks, decision.mark_id)
        page_before = page.url
        pages_before = set(page.context.pages)
        await page.mouse.click(mark.center[0], mark.center[1])
        await _settle(page)
        new_pages = [candidate for candidate in page.context.pages if candidate not in pages_before]
        if new_pages:
            target = new_pages[-1]
            try:
                await target.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            await page.goto(target.url, wait_until="domcontentloaded", timeout=45000)
            await target.close()
            await _settle(page)
        return {"ok": True, "action": "click", "mark_id": mark.id, "url_before": page_before, "url_after": page.url}
    if action == BrowserActionType.type:
        mark = _require_mark(marks, decision.mark_id)
        await page.mouse.click(mark.center[0], mark.center[1])
        await page.keyboard.press("Control+A")
        await page.keyboard.type(decision.text or "")
        await _settle(page)
        return {"ok": True, "action": "type", "mark_id": mark.id, "text_length": len(decision.text or "")}
    if action == BrowserActionType.press:
        key = decision.key or ""
        if _is_history_back_key(key):
            return await _go_back(page, key)
        await page.keyboard.press(key)
        await _settle(page)
        return {"ok": True, "action": "press", "key": key}
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


async def _go_back(page: Page, key: str) -> dict:
    url_before = page.url
    history_before = await _history_length(page)
    try:
        response = await page.go_back(wait_until="domcontentloaded", timeout=45000)
    except Exception as exc:
        await _settle(page)
        return {
            "ok": False,
            "action": "press",
            "key": key,
            "interpreted_as": "history_back",
            "url_before": url_before,
            "url_after": page.url,
            "history_length_before": history_before,
            "error": f"history back failed: {exc}",
        }
    await _settle(page)
    url_after = page.url
    history_after = await _history_length(page)
    if url_after == url_before:
        return {
            "ok": False,
            "action": "press",
            "key": key,
            "interpreted_as": "history_back",
            "url_before": url_before,
            "url_after": url_after,
            "history_length_before": history_before,
            "history_length_after": history_after,
            "navigation_response": bool(response),
            "error": "history back did not change the current URL",
        }
    return {
        "ok": True,
        "action": "press",
        "key": key,
        "interpreted_as": "history_back",
        "url_before": url_before,
        "url_after": url_after,
        "history_length_before": history_before,
        "history_length_after": history_after,
        "navigation_response": bool(response),
    }


async def _history_length(page: Page) -> int | None:
    try:
        return await page.evaluate("() => window.history.length")
    except Exception:
        return None


def _is_history_back_key(key: str) -> bool:
    normalized = key.replace(" ", "").replace("-", "+").lower()
    return normalized in {"alt+left", "alt+arrowleft", "meta+arrowleft", "meta+left", "browserback"}


async def _settle(page: Page) -> None:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    await page.wait_for_timeout(700)
