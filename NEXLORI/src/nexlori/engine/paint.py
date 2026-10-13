"""Painter: Display-Liste -> Pillow-Bitmap (komplett oder nur ein vertikaler Ausschnitt)."""
from __future__ import annotations

import math

from .fonts import FONT_LOCK, load_font
from .layout import Border, Layout, Rect, Text


def paint(
    layout: Layout,
    background: tuple[int, int, int] = (255, 255, 255),
    min_height: int = 1,
    *,
    top: float = 0.0,
    height: int | None = None,
):
    """Zeichnet die Seite. Mit `height` wird nur der Ausschnitt [top, top+height) gezeichnet –
    so bleibt das Scrollen auch bei sehr langen Seiten schnell und speicherschonend."""
    from PIL import Image, ImageDraw

    width = max(1, math.ceil(layout.width))
    if height is None:
        top = 0.0
        out_h = max(min_height, math.ceil(layout.height))
    else:
        out_h = max(1, int(height))
    bottom = top + out_h
    img = Image.new("RGB", (width, out_h), background)
    draw = ImageDraw.Draw(img)

    def fill(x: float, y: float, w: float, h: float, color) -> None:
        y -= top
        x0, y0 = round(x), round(y)
        x1, y1 = max(x0, round(x + w) - 1), max(y0, round(y + h) - 1)
        draw.rectangle([x0, y0, x1, y1], fill=color)

    for cmd in layout.commands:
        if isinstance(cmd, Text):
            if cmd.y + cmd.size * 1.4 < top or cmd.y > bottom:
                continue
            with FONT_LOCK:
                font = load_font(max(1, round(cmd.size)), cmd.bold)
                draw.text((cmd.x, cmd.y - top), cmd.text, font=font, fill=cmd.color)
            continue
        if cmd.y + cmd.h < top or cmd.y > bottom:
            continue
        if isinstance(cmd, Rect):
            fill(cmd.x, cmd.y, cmd.w, cmd.h, cmd.color)
        elif isinstance(cmd, Border):
            bw = max(1.0, cmd.width)
            fill(cmd.x, cmd.y, cmd.w, bw, cmd.color)
            fill(cmd.x, cmd.y + cmd.h - bw, cmd.w, bw, cmd.color)
            fill(cmd.x, cmd.y, bw, cmd.h, cmd.color)
            fill(cmd.x + cmd.w - bw, cmd.y, bw, cmd.h, cmd.color)
    return img
