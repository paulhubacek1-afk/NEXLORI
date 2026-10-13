"""Schriftladen und Textmessung. Pillow wird nur hier (und im Painter) benötigt."""
from __future__ import annotations

import threading
from functools import lru_cache

from .layout import MonospaceMetrics

_REGULAR = [
    "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "LiberationSans-Regular.ttf", "arial.ttf", "Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
]
_BOLD = [
    "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
]


# FreeType-Schriftobjekte werden von Layout-Threads (Messen) und der Oberfläche (Zeichnen) gemeinsam genutzt.
FONT_LOCK = threading.RLock()


@lru_cache(maxsize=256)
def load_font(size: int, bold: bool):
    from PIL import ImageFont

    for name in _BOLD if bold else _REGULAR:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)  # Pillow >= 10.1


class PillowMetrics:
    """Misst Text mit denselben Schriften, die der Painter später verwendet."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, bool], float] = {}

    def text_width(self, text: str, size: float, bold: bool) -> float:
        key = (text, max(1, round(size)), bold)
        width = self._cache.get(key)
        if width is None:
            if len(self._cache) > 50_000:
                self._cache.clear()
            with FONT_LOCK:
                width = self._cache[key] = float(load_font(key[1], bold).getlength(text))
        return width


def default_metrics():
    try:
        import PIL  # noqa: F401
    except ImportError:
        return MonospaceMetrics()
    return PillowMetrics()
