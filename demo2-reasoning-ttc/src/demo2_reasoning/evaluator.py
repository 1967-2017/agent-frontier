from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Iterable

NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")
FINAL_RE = re.compile(r"final answer\s*[:=]\s*([-+]?\$?\d[\d,]*(?:\.\d+)?)", re.IGNORECASE)
HASH_RE = re.compile(r"####\s*([-+]?\$?\d[\d,]*(?:\.\d+)?)")


def clean_number(value: str) -> str:
    return value.strip().replace("$", "").replace(",", "")


def extract_numeric_answer(text: str) -> str | None:
    for pattern in (FINAL_RE, HASH_RE):
        match = pattern.search(text)
        if match:
            return clean_number(match.group(1))
    matches = NUMBER_RE.findall(text)
    if matches:
        return clean_number(matches[-1])
    return None


def to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(clean_number(str(value)))
    except (InvalidOperation, ValueError):
        return None


def is_correct(prediction: str | None, target: str) -> bool:
    pred = to_decimal(prediction)
    gold = to_decimal(extract_numeric_answer(target) or target)
    if pred is None or gold is None:
        return False
    return abs(pred - gold) <= Decimal("0.000001")


def majority_vote(answers: Iterable[str | None]) -> str | None:
    counts: dict[str, int] = {}
    order: list[str] = []
    for answer in answers:
        if answer is None:
            continue
        if answer not in counts:
            order.append(answer)
            counts[answer] = 0
        counts[answer] += 1
    if not counts:
        return None
    return sorted(order, key=lambda item: (-counts[item], order.index(item)))[0]
