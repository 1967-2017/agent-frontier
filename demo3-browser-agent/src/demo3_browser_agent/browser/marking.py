from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import Page

from demo3_browser_agent.schemas import Mark

INTERACTIVE_SELECTOR = ",".join(
    [
        "a",
        "button",
        "input",
        "textarea",
        "select",
        "[role=button]",
        "[role=link]",
        "[contenteditable=true]",
        "summary",
        "[tabindex]:not([tabindex='-1'])",
        "[aria-haspopup]",
        "[aria-expanded]",
        "[aria-controls]",
        "[onclick]",
    ]
)


async def collect_marks(page: Page, limit: int = 120) -> list[Mark]:
    await page.locator("a[target='_blank']").evaluate_all("elements => elements.forEach(el => el.removeAttribute('target'))")
    candidates = await page.locator(INTERACTIVE_SELECTOR).all()
    candidates.extend(await _text_control_candidates(page))
    raw_marks: list[Mark] = []
    seen: set[tuple[int, int, int, int] | tuple[str, str]] = set()
    for element in candidates:
        try:
            if not await element.is_visible() or not await element.is_enabled():
                continue
            box = await element.bounding_box()
            if not box:
                continue
            x, y, width, height = box["x"], box["y"], box["width"], box["height"]
            if width < 4 or height < 4 or x + width < 0 or y + height < 0:
                continue
            viewport = page.viewport_size or {"width": 1366, "height": 900}
            if x > viewport["width"] or y > viewport["height"]:
                continue
            rounded = (round(x), round(y), round(width), round(height))
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            role = await element.get_attribute("role")
            text = " ".join((await _element_text(element, tag)).split())[:160]
            key = rounded if text else (tag, str(rounded))
            text_key = (tag, text.lower()) if text else key
            if key in seen or text_key in seen:
                continue
            seen.add(key)
            seen.add(text_key)
            selector = await element.evaluate(
                """
                el => {
                  if (el.id) return `#${CSS.escape(el.id)}`;
                  const name = el.getAttribute('name');
                  if (name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
                  const role = el.getAttribute('role');
                  if (role) return `${el.tagName.toLowerCase()}[role="${CSS.escape(role)}"]`;
                  return el.tagName.toLowerCase();
                }
                """
            )
            raw_marks.append(
                Mark(
                    id=0,
                    role=role,
                    text=text,
                    tag=tag,
                    bbox=(x, y, width, height),
                    center=(x + width / 2, y + height / 2),
                    selector=selector,
                )
            )
        except Exception:
            continue
    prioritized = sorted(raw_marks, key=_mark_priority)[:limit]
    return [mark.model_copy(update={"id": index}) for index, mark in enumerate(prioritized, start=1)]


async def _text_control_candidates(page: Page):
    await page.locator("[data-demo3-text-control]").evaluate_all(
        "elements => elements.forEach(el => el.removeAttribute('data-demo3-text-control'))"
    )
    await page.locator("body *").evaluate_all(
        r"""
        elements => {
          const visible = el => {
            const style = getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.visibility !== 'hidden' && style.display !== 'none' && rect.width >= 4 && rect.height >= 4;
          };
          const clickableSelector = 'button,a,[role="button"],[role="link"],[tabindex]:not([tabindex="-1"]),[aria-haspopup],[aria-expanded],[aria-controls],[onclick]';
          const nearestClickable = el => el.closest(clickableSelector) || (getComputedStyle(el).cursor === 'pointer' ? el : null);
          const seen = new Set();
          let index = 0;
          for (const el of elements) {
            if (!visible(el)) continue;
            const text = (el.innerText || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
            if (!text) continue;
            const candidate = nearestClickable(el);
            if (!candidate || !visible(candidate) || seen.has(candidate)) continue;
            seen.add(candidate);
            candidate.setAttribute('data-demo3-text-control', String(index));
            index += 1;
            if (index >= 80) break;
          }
        }
        """,
    )
    return await page.locator("[data-demo3-text-control]").all()


async def _element_text(element, tag: str) -> str:
    input_type = (await element.get_attribute("type") or "").lower()
    aria_label = await element.get_attribute("aria-label")
    placeholder = await element.get_attribute("placeholder")
    name = await element.get_attribute("name")
    value = await element.get_attribute("value")

    if tag == "input" and input_type in {"radio", "checkbox"}:
        label = await element.evaluate(
            """
            el => {
              const direct = el.closest('label');
              if (direct) return direct.innerText;
              if (el.id) {
                const explicit = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                if (explicit) return explicit.innerText;
              }
              return '';
            }
            """
        )
        checked = await element.is_checked()
        base = label or aria_label or value or name or input_type
        return f"{base} checked={str(checked).lower()}"

    if tag in {"input", "textarea", "select"}:
        current = await element.input_value(timeout=500) if tag != "select" else None
        base = aria_label or placeholder or name or value or ""
        if current:
            return f"{base} value={current}".strip()
        return base

    return (await element.inner_text(timeout=500)) or aria_label or name or ""


def _mark_priority(mark: Mark) -> tuple[int, float, float]:
    tag = mark.tag or ""
    role = (mark.role or "").lower()
    score = 50
    if tag in {"input", "textarea"}:
        score = 0
    elif tag == "select":
        score = 10
    elif tag == "button" or "button" in role:
        score = 20
    elif tag == "a" or "link" in role:
        score = 30
    elif mark.text:
        score = 40
    x, y, width, height = mark.bbox
    return (score, max(0, y), max(0, x))


def draw_marks(screenshot_path: Path, marked_path: Path, marks: list[Mark]) -> None:
    image = Image.open(screenshot_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = _font()
    colors = {
        "a": "#f59e0b",
        "button": "#22c55e",
        "input": "#3b82f6",
        "textarea": "#3b82f6",
        "select": "#8b5cf6",
    }
    for mark in marks:
        x, y, width, height = mark.bbox
        color = colors.get(mark.tag or "", "#ef4444")
        draw.rectangle((x, y, x + width, y + height), outline=color, width=3)
        label = f"[{mark.id}]"
        label_box = draw.textbbox((0, 0), label, font=font)
        label_width = label_box[2] - label_box[0] + 8
        label_height = label_box[3] - label_box[1] + 6
        label_x = max(0, x)
        label_y = max(0, y - label_height)
        draw.rectangle((label_x, label_y, label_x + label_width, label_y + label_height), fill=color)
        draw.text((label_x + 4, label_y + 2), label, fill="white", font=font)
    marked_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(marked_path)


def _font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", 18)
    except OSError:
        return ImageFont.load_default()
