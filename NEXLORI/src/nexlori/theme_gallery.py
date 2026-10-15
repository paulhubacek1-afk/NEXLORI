"""Safe URL parsing for theme-gallery activation links.

This module intentionally has no Qt dependency so the URL validation is testable
in headless CI environments.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from .core.themes import BUILTIN_THEMES


def gallery_theme_slug(raw_url: str) -> str | None:
    """Accept only gallery links for a known built-in theme; never execute remote code."""
    try:
        parsed = urlsplit(str(raw_url))
    except ValueError:
        return None
    if parsed.scheme.lower() != "nexlori-theme" or parsed.netloc.lower() != "apply":
        return None
    slug = parsed.path.strip("/")
    if not re.fullmatch(r"[a-z0-9-]{1,40}", slug):
        return None
    return slug if slug in BUILTIN_THEMES else None
