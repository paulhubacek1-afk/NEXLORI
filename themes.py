"""Themes (inkl. Pride-Farbwelten) mit eingebauter Barrierefreiheitsprüfung (WCAG-Kontrast).

Themes sind reine Gestaltung: Es werden keine Angaben zur Person erhoben oder gespeichert.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    if not _HEX_RE.match(value):
        raise ValueError(f"ungültige Farbe (erwartet #RRGGBB): {value!r}")
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def relative_luminance(value: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in hex_to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    bg: str
    surface: str
    fg: str
    accent: str
    stripes: tuple[str, ...] = ()  # optionale Farbstreifen (z. B. Tab-Leiste)

    def __post_init__(self) -> None:
        for value in (self.bg, self.surface, self.fg, self.accent, *self.stripes):
            hex_to_rgb(value)
        if not re.fullmatch(r"[a-z0-9-]{1,40}", self.name):
            raise ValueError("Theme-Name: nur a-z, 0-9 und '-' (max. 40 Zeichen)")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stripes"] = list(self.stripes)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Theme":
        return cls(
            name=str(data["name"]), label=str(data.get("label", data["name"])), bg=data["bg"],
            surface=data["surface"], fg=data["fg"], accent=data["accent"],
            stripes=tuple(data.get("stripes", ())),
        )


def accessibility_issues(theme: Theme) -> list[str]:
    """Leere Liste = WCAG AA für Text (4,5:1) und Bedienelemente (3:1) erfüllt."""
    issues = []
    for label, a, b, minimum in (
        ("Text auf Hintergrund", theme.fg, theme.bg, 4.5),
        ("Text auf Fläche", theme.fg, theme.surface, 4.5),
        ("Akzent auf Hintergrund", theme.accent, theme.bg, 3.0),
        ("Akzent auf Fläche", theme.accent, theme.surface, 3.0),
    ):
        ratio = contrast_ratio(a, b)
        if ratio < minimum:
            issues.append(f"{label}: Kontrast {ratio:.2f}:1 (benötigt {minimum}:1)")
    return issues


def _pride(name: str, label: str, accent: str, stripes: tuple[str, ...]) -> Theme:
    return Theme(name, label, "#15131A", "#221F2B", "#F3F1F7", accent, stripes)


_THEMES = [
    Theme("hell", "Hell", "#FFFFFF", "#F0F0F4", "#1A1A1F", "#4533D6"),
    Theme("dunkel", "Dunkel", "#121214", "#1E1E23", "#ECECF1", "#8AB4FF"),
    Theme("ruhig", "Ruhig (wenig Kontrastspitzen)", "#F4F1EA", "#E9E5DA", "#2B2A27", "#2F5E4E"),
    Theme("hochkontrast", "Hoher Kontrast", "#000000", "#000000", "#FFFFFF", "#FFFF00"),
    _pride("pride-regenbogen", "Pride – Regenbogen", "#FF8C00",
           ("#E40303", "#FF8C00", "#FFED00", "#008026", "#004DFF", "#750787")),
    _pride("pride-trans", "Pride – Trans", "#5BCEFA", ("#5BCEFA", "#F5A9B8", "#FFFFFF", "#F5A9B8", "#5BCEFA")),
    _pride("pride-bi", "Pride – Bi", "#E0488F", ("#D60270", "#9B4F96", "#0038A8")),
    _pride("pride-pan", "Pride – Pan", "#FF218C", ("#FF218C", "#FFD800", "#21B1FF")),
    _pride("pride-lesbisch", "Pride – Lesbisch", "#FF9A56",
           ("#D52D00", "#EF7627", "#FF9A56", "#FFFFFF", "#D162A4", "#B55690", "#A30262")),
    _pride("pride-nonbinaer", "Pride – Nichtbinär", "#B07FE0", ("#FCF434", "#FFFFFF", "#9C59D1", "#2C2C2C")),
    _pride("pride-asexuell", "Pride – Asexuell", "#B57BD8", ("#000000", "#A3A3A3", "#FFFFFF", "#800080")),
]
BUILTIN_THEMES: dict[str, Theme] = {t.name: t for t in _THEMES}


def custom_theme(name: str, bg: str, surface: str, fg: str, accent: str, label: str | None = None) -> Theme:
    """Erstellt ein eigenes Theme und lehnt es ab, wenn es die Kontrast-Mindestwerte verfehlt."""
    theme = Theme(name, label or name, bg, surface, fg, accent)
    issues = accessibility_issues(theme)
    if issues:
        raise ValueError("Theme nicht barrierearm genug: " + "; ".join(issues))
    return theme
