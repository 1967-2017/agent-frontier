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
    ]
)


async def collect_marks(page: Page, limit: int = 60) -> list[Mark]:
    elements = await page.locator(INTERACTIVE_SELECTOR).all()
    marks: list[Mark] = []
    seen: set[tuple[int, int, int, int]] = set()
    for element in elements:
        if len(marks) >= limit:
            break
        try:
            if not await element.is_visible() or not await element.is_enabled():
                continue
            box = await element.bounding_box()
            if not box:
                continue
            x, y, width, height = box["x"], box["y"], box["width"], box["height"]
            if width < 4 or height < 4 or x + width < 0 or y + height < 0:
                continue
            rounded = (round(x), round(y), round(width), round(height))
            if rounded in seen:
                continue
            seen.add(rounded)
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            role = await element.get_attribute("role")
            text = await _element_text(element, tag)
            selector = await element.evaluate(
                """
                el => {
                  if (el.id) return `#${CSS.escape(el.id)}`;
                  const name = el.getAttribute('name');
                  if (name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
                  return el.tagName.toLowerCase();
                }
                """
            )
            marks.append(
                Mark(
                    id=len(marks) + 1,
                    role=role,
                    text=" ".join(text.split())[:160],
                    tag=tag,
                    bbox=(x, y, width, height),
                    center=(x + width / 2, y + height / 2),
                    selector=selector,
                )
            )
        except Exception:
            continue
    return marks


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
