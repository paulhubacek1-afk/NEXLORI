"""Programm-Icon, zur Laufzeit gezeichnet (eine Quelle für Fenster-Icon und .ico-Datei)."""
from __future__ import annotations

STRIPES = ("#E40303", "#FF8C00", "#FFED00", "#008026", "#004DFF", "#750787")


def make_icon(size: int = 256):
    from PIL import Image, ImageDraw

    scale = 4  # Supersampling für glatte Kanten
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = int(s * 0.2)
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill="#15131A")

    # Regenbogen-Streifen im unteren Drittel, auf die abgerundete Form zugeschnitten
    stripes = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stripes)
    top, bottom = int(s * 0.70), int(s * 0.94)
    step = (bottom - top) / len(STRIPES)
    for i, color in enumerate(STRIPES):
        sd.rectangle([0, int(top + i * step), s, int(top + (i + 1) * step) + 1], fill=color)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=255)
    img.paste(stripes, (0, 0), Image.composite(stripes.split()[3], Image.new("L", (s, s), 0), mask))

    # Weißes „N“
    w = int(s * 0.11)
    x0, x1, y0, y1 = int(s * 0.27), int(s * 0.73), int(s * 0.16), int(s * 0.62)
    for pts in (((x0, y1), (x0, y0)), ((x0, y0), (x1, y1)), ((x1, y1), (x1, y0))):
        draw.line(pts, fill="#FFFFFF", width=w, joint="curve")
    for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
        draw.ellipse([x - w // 2, y - w // 2, x + w // 2, y + w // 2], fill="#FFFFFF")
    return img.resize((size, size), Image.LANCZOS)


def save_ico(path: str) -> None:
    make_icon(256).save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
