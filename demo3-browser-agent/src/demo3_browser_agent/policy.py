from __future__ import annotations

import re

BLACKLISTED_PATTERNS = [
    re.compile(r".*malware.*", re.I),
    re.compile(r".*/blocked$", re.I),
]


class PolicyDenied(RuntimeError):
    pass


def is_blacklisted_url(url: str) -> bool:
    return any(pattern.fullmatch(url) for pattern in BLACKLISTED_PATTERNS)


def check_url_policy(url: str) -> None:
    if is_blacklisted_url(url):
        raise PolicyDenied("URL is blacklisted")
