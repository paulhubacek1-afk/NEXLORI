"""Programm-Icon. Die Laufzeit- und Fenster-Icons passen sich an das aktive Theme an."""
from __future__ import annotations

STRIPES = ("#E40303", "#FF8C00", "#FFED00", "#008026", "#004DFF", "#750787")


def make_icon(size: int = 256, theme=None):
    from PIL import Image, ImageDraw

    scale = 4
    s = size * scale
    background = getattr(theme, "bg", "#15131A")
    foreground = getattr(theme, "fg", "#FFFFFF")
    accent = getattr(theme, "accent", "#FF8C00")
    stripes = tuple(getattr(theme, "stripes", ()) or ((accent,) if theme is not None else STRIPES))
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(s * 0.2)
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=background)

    # Theme palette stripe, cropped to the rounded square.
    stripe_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    stripe_draw = ImageDraw.Draw(stripe_layer)
    top, bottom = int(s * 0.70), int(s * 0.94)
    step = (bottom - top) / max(1, len(stripes))
    for i, color in enumerate(stripes):
        stripe_draw.rectangle(
            [0, int(top + i * step), s, int(top + (i + 1) * step) + 1],
            fill=color,
        )
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=255)
    img.paste(stripe_layer, (0, 0), Image.composite(stripe_layer.getchannel("A"), Image.new("L", (s, s), 0), mask))

    # The N stays high-contrast against the selected theme.
    draw = ImageDraw.Draw(img)
    width = int(s * 0.11)
    x0, x1, y0, y1 = int(s * 0.27), int(s * 0.73), int(s * 0.16), int(s * 0.62)
    for points in (((x0, y1), (x0, y0)), ((x0, y0), (x1, y1)), ((x1, y1), (x1, y0))):
        draw.line(points, fill=foreground, width=width, joint="curve")
    for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
        draw.ellipse([x - width // 2, y - width // 2, x + width // 2, y + width // 2], fill=foreground)
    return img.resize((size, size), Image.LANCZOS)


def save_ico(path: str, theme=None) -> None:
    make_icon(256, theme=theme).save(
        path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
