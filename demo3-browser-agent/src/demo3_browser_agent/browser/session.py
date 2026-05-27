from __future__ import annotations

from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from demo3_browser_agent.browser.actions import execute_action
from demo3_browser_agent.browser.marking import collect_marks, draw_marks
from demo3_browser_agent.config import browser_headless
from demo3_browser_agent.schemas import AgentDecision, AgentObservation


class BrowserSession:
    def __init__(self, headless: bool | None = None):
        self.headless = browser_headless() if headless is None else headless
        self._playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        try:
            self.browser = await self._playwright.chromium.launch(headless=self.headless, args=["--disable-gpu", "--disable-software-rasterizer"])
        except Exception:
            if self.headless:
                raise
            self.headless = True
            self.browser = await self._playwright.chromium.launch(headless=True, args=["--disable-gpu", "--disable-software-rasterizer"])
        self.context = await self.browser.new_context(viewport={"width": 1366, "height": 900}, ignore_https_errors=True)
        self.page = await self.context.new_page()

    async def goto(self, url: str) -> None:
        page = self._require_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(800)

    async def observe(self, run_dir: Path, task_id: str, step: int, suffix: str = "") -> AgentObservation:
        page = self._require_page()
        screenshot_dir = run_dir / "screenshots" / task_id
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / f"step_{step:03d}{suffix}.png"
        marked_path = screenshot_dir / f"marked_step_{step:03d}{suffix}.png"
        await page.screenshot(path=screenshot_path, full_page=False)
        marks = await collect_marks(page)
        visible_text = await _visible_text(page)
        draw_marks(screenshot_path, marked_path, marks)
        return AgentObservation(
            step=step,
            url=page.url,
            title=await page.title(),
            screenshot_path=str(screenshot_path.relative_to(run_dir)),
            marked_screenshot_path=str(marked_path.relative_to(run_dir)),
            marks=marks,
            visible_text=visible_text,
        )

    async def execute(self, decision: AgentDecision, observation: AgentObservation) -> dict:
        return await execute_action(self._require_page(), decision, observation.marks)

    async def close(self) -> None:
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _require_page(self) -> Page:
        if not self.page:
            raise RuntimeError("browser session is not started")
        return self.page


async def _visible_text(page: Page) -> str:
    text = await page.locator("body").inner_text(timeout=1000)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())[:8000]
