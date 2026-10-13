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


def page_theme_css(theme: Theme) -> str:
    """Locally recolour a webpage without filtering images, video or the site's layout."""
    light = theme.name in {"hell", "ruhig"}
    scheme = "light" if light else "dark"
    return f"""
:root {{
  color-scheme: {scheme} !important;
  --nexlori-page-bg: {theme.bg};
  --nexlori-page-surface: {theme.surface};
  --nexlori-page-text: {theme.fg};
  --nexlori-page-accent: {theme.accent};
}}
html, body {{
  background-color: var(--nexlori-page-bg) !important;
  color: var(--nexlori-page-text) !important;
}}
/* Apply the active text and border palette broadly while preserving media and vector icons. */
*:not(img):not(video):not(audio):not(canvas):not(svg):not(path):not(iframe):not(picture):not(source) {{
  color: var(--nexlori-page-text) !important;
  border-color: var(--nexlori-page-accent) !important;
}}
/* Recolour common solid page surfaces without replacing background images or gradients. */
main, article, section, aside, nav, header, footer, table, thead, tbody, tfoot, tr, td, th,
form, fieldset, dialog, details, [role="main"], [role="navigation"], [role="banner"],
[role="contentinfo"], [role="dialog"], [role="region"], [class*="card" i], [class*="panel" i],
[class*="modal" i], [class*="surface" i] {{
  background-color: var(--nexlori-page-surface) !important;
}}
a, a:visited, [role="link"] {{
  color: var(--nexlori-page-accent) !important;
}}
input:not([type="checkbox"]):not([type="radio"]):not([type="range"]),
textarea, select, option {{
  background-color: var(--nexlori-page-surface) !important;
  color: var(--nexlori-page-text) !important;
  border-color: var(--nexlori-page-accent) !important;
}}
button, [role="button"], input[type="button"], input[type="submit"] {{
  color: var(--nexlori-page-text) !important;
  border-color: var(--nexlori-page-accent) !important;
}}
::selection {{
  background: var(--nexlori-page-accent) !important;
  color: var(--nexlori-page-bg) !important;
}}
::-webkit-scrollbar-thumb {{
  background: var(--nexlori-page-accent) !important;
}}
/* Images, video, canvas and site layout are left untouched. */
"""


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
    _pride("pride-gay", "Pride – Gay", "#7DD3FC",
           ("#078D70", "#26CEAA", "#98E8C1", "#FFFFFF", "#7BADE2", "#5049CC", "#3D1A78")),
    _pride("pride-genderfluid", "Pride – Genderfluid", "#D9A9EF",
           ("#B57EDC", "#FFFFFF", "#000000", "#F5A9B8", "#5BCEFA")),
    _pride("pride-aromantisch", "Pride – Aromantisch", "#8DD6B2",
           ("#3DA542", "#A7D379", "#FFFFFF", "#A9A9A9", "#000000")),
    _pride("pride-queer", "Pride – Queer", "#F39BD2",
           ("#E40303", "#FF8C00", "#FFED00", "#008026", "#004DFF", "#750787")),
    _pride("pride-progress", "Pride – Progress", "#68DDB2",
           ("#000000", "#784F17", "#5BCEFA", "#F5A9B8", "#FFFFFF", "#E40303", "#FF8C00", "#FFED00", "#008026", "#004DFF", "#750787")),
    _pride("pride-intersex-progress", "Pride – Intersex Progress", "#F6D75D",
           ("#000000", "#784F17", "#5BCEFA", "#F5A9B8", "#FFFFFF", "#F6D75D", "#7B2CBF")),
    _pride("pride-genderqueer", "Pride – Genderqueer", "#BBA1F8",
           ("#B57EDC", "#FFFFFF", "#4A8123")),
    _pride("pride-agender", "Pride – Agender", "#68DDB2",
           ("#000000", "#B9B9B9", "#FFFFFF", "#B8F483", "#FFFFFF", "#B9B9B9", "#000000")),
    _pride("pride-demiboy", "Pride – Demiboy", "#71C8F3",
           ("#7F7F7F", "#C4C4C4", "#FFFFFF", "#9DD7EA", "#7F7F7F")),
    _pride("pride-demigirl", "Pride – Demigirl", "#EAA4F5",
           ("#7F7F7F", "#C4C4C4", "#FFFFFF", "#FFAECD", "#EAA4F5")),
    _pride("pride-demigender", "Pride – Demigender", "#9CCBFF",
           ("#7F7F7F", "#C4C4C4", "#FFFFFF", "#B4E0B4", "#7F7F7F")),
    _pride("pride-bigender", "Pride – Bigender", "#EAB4D5",
           ("#C479A2", "#D6C7E8", "#FFFFFF", "#D6C7E8", "#6D82D5")),
    _pride("pride-polysexual", "Pride – Polysexual", "#F7A8D8",
           ("#F714BA", "#01D66A", "#1594F6")),
    _pride("pride-omnisexual", "Pride – Omnisexual", "#9CCBFF",
           ("#FF9CCD", "#FF53BF", "#200044", "#6760FE", "#8EA6FF")),
    _pride("pride-abrosexual", "Pride – Abrosexual", "#9CE6CF",
           ("#75E7C3", "#B5E48C", "#FFFFFF", "#E8A2B8", "#E87DAB")),
    _pride("pride-aroace", "Pride – Aromantisch-Asexuell", "#F59E0B",
           ("#E28C00", "#ECCD00", "#FFFFFF", "#62AEDC", "#203856")),
    _pride("pride-intersex", "Pride – Intersex", "#F6D75D",
           ("#FFD800", "#7B2CBF", "#FFD800")),
    _pride("pride-bear", "Pride – Bear", "#E5B77C",
           ("#623804", "#D56300", "#FEDD63", "#FFFFFF", "#D3D3D3", "#555555", "#000000")),
    _pride("pride-leather", "Pride – Leather", "#71C8F3",
           ("#000000", "#252525", "#71C8F3", "#FFFFFF", "#71C8F3", "#D71920", "#000000")),
    _pride("pride-polyamorie", "Pride – Polyamorie", "#71C8F3",
           ("#0000FF", "#E91E63", "#000000", "#FFD700")),
    _pride("pride-ally", "Pride – Ally", "#D8E7FF",
           ("#000000", "#FFFFFF", "#E40303", "#FF8C00", "#FFED00", "#008026", "#004DFF", "#750787")),
    _pride("pride-questioning", "Pride – Questioning", "#BBA1F8",
           ("#E6E6FA", "#FFFFFF", "#BBA1F8", "#FFFFFF", "#E6E6FA")),
    _pride("pride-sapphic", "Pride – Sapphic", "#F1B0D0",
           ("#FFFFFF", "#F7A8D8", "#E34A77", "#E87535", "#F4A55B")),
    _pride("pride-achillean", "Pride – Achillean", "#9CCBFF",
           ("#078D70", "#26CEAA", "#98E8C1", "#FFFFFF", "#7BADE2", "#5049CC", "#3D1A78")),
    _pride("pride-mlm", "Pride – Men Loving Men", "#7DD3FC",
           ("#078D70", "#26CEAA", "#98E8C1", "#FFFFFF", "#7BADE2", "#5049CC", "#3D1A78")),
    _pride("pride-neutrois", "Pride – Neutrois", "#9CE6CF",
           ("#FFFFFF", "#1F1F1F", "#9CE6CF")),
    _pride("pride-pangender", "Pride – Pangender", "#F1B0D0",
           ("#F7A8D8", "#FFD3E8", "#FFFFFF", "#FFF798", "#FFFFFF", "#B5AAFF", "#9CCBFF")),
    _pride("pride-lgbtqia", "Pride – LGBTQIA+", "#68DDB2",
           ("#E40303", "#FF8C00", "#FFED00", "#008026", "#004DFF", "#750787", "#000000", "#FFFFFF")),
    _pride("pride-transmasc", "Pride – Transmasculin", "#71C8F3",
           ("#FF8ABD", "#CDF5FE", "#9AEBFF", "#74DFFF", "#FFFFFF", "#74DFFF", "#9AEBFF")),
    _pride("pride-transfem", "Pride – Transfeminin", "#EAA4F5",
           ("#7F7F7F", "#F7A8D8", "#FFFFFF", "#EAA4F5", "#7F7F7F")),
    _pride("pride-xenogender", "Pride – Xenogender", "#BBA1F8",
           ("#BBA1F8", "#E7B8FF", "#FFFFFF", "#E7B8FF", "#BBA1F8")),
    _pride("pride-demifluid", "Pride – Demifluid", "#F0B1FF",
           ("#7F7F7F", "#BBA1F8", "#FFFFFF", "#F7A8D8", "#7F7F7F")),
    _pride("pride-queerplatonic", "Pride – Queerplatonisch", "#F6D75D",
           ("#FF8C00", "#F6D75D", "#FFFFFF", "#68DDB2", "#1594F6")),
    _pride("pride-demisexual", "Pride – Demisexuell", "#BBA1F8",
           ("#000000", "#696969", "#FFFFFF", "#BBA1F8", "#FFFFFF")),
    _pride("pride-demiromantic", "Pride – Demiromantisch", "#68DDB2",
           ("#3DA542", "#A7D379", "#FFFFFF", "#696969", "#000000")),
    _pride("pride-graysexual", "Pride – Graysexuell", "#BBA1F8",
           ("#740194", "#AEB2D5", "#FFFFFF", "#AEB2D5", "#740194")),
    _pride("pride-grayromantic", "Pride – Grayromantisch", "#68DDB2",
           ("#7B3F99", "#A8A8A8", "#FFFFFF", "#A8A8A8", "#7B3F99")),
    _pride("pride-aceflux", "Pride – Aceflux", "#BBA1F8",
           ("#FFEA70", "#F4A9B8", "#FFFFFF", "#BBA1F8", "#333333")),
    _pride("pride-aroflux", "Pride – Aroflux", "#68DDB2",
           ("#EF6A7A", "#F6B1D0", "#FFFFFF", "#B9A2E8", "#4A6E65")),
    _pride("pride-biromantic", "Pride – Biromantisch", "#EAA4F5",
           ("#D60270", "#9B4F96", "#0038A8", "#8C4799", "#D60270")),
    _pride("pride-panromantic", "Pride – Panromantisch", "#FF9CCD",
           ("#FF218C", "#FFD800", "#21B1FF", "#FF218C")),
    _pride("pride-polyromantic", "Pride – Polyromantisch", "#F7A8D8",
           ("#F714BA", "#01D66A", "#1594F6", "#F714BA")),
    _pride("pride-homoromantic", "Pride – Homoromantisch", "#71C8F3",
           ("#078D70", "#26CEAA", "#98E8C1", "#FFFFFF", "#7BADE2", "#5049CC", "#3D1A78")),
    _pride("pride-omniromantic", "Pride – Omniromantisch", "#9CCBFF",
           ("#FF9CCD", "#FF53BF", "#200044", "#6760FE", "#8EA6FF")),
    _pride("pride-maverique", "Pride – Maverique", "#F6D75D",
           ("#F6D75D", "#FFFFFF", "#F6D75D", "#000000")),
    _pride("pride-genderflux", "Pride – Genderflux", "#F7A8D8",
           ("#F7A8D8", "#F6D75D", "#FFFFFF", "#BBA1F8", "#7F7F7F")),
    _pride("pride-polygender", "Pride – Polygender", "#BBA1F8",
           ("#F7A8D8", "#BBA1F8", "#68DDB2", "#FFFFFF", "#7F7F7F")),
    _pride("pride-intergender", "Pride – Intergender", "#EAA4F5",
           ("#F7A8D8", "#FFFFFF", "#EAA4F5", "#FFFFFF", "#F7A8D8")),
    _pride("pride-heteroflexible", "Pride – Heteroflexibel", "#71C8F3",
           ("#000000", "#FFFFFF", "#71C8F3", "#FFFFFF", "#000000")),
    _pride("pride-homoflexible", "Pride – Homoflexibel", "#68DDB2",
           ("#000000", "#FFFFFF", "#68DDB2", "#FFFFFF", "#000000")),
    _pride("pride-skoliosexual", "Pride – Skoliosexuell", "#BBA1F8",
           ("#FFFFFF", "#BBA1F8", "#68DDB2", "#BBA1F8", "#FFFFFF")),
    _pride("pride-neuroqueer", "Pride – Neuroqueer", "#BBA1F8",
           ("#F7A8D8", "#BBA1F8", "#68DDB2", "#F6D75D", "#9CCBFF")),
    _pride("pride-quoiromantic", "Pride – Quoiromantisch", "#F6D75D",
           ("#ECA95A", "#F6D75D", "#FFFFFF", "#7A7A7A", "#000000")),
    Theme("gothic", "Gothic", "#100C14", "#211927", "#F4EAF6", "#E29BCE",
          ("#151018", "#4D2D58", "#A55A97", "#D8A8CE")),
    Theme("cyberpunk", "Cyberpunk", "#100A24", "#211743", "#F8F0FF", "#F72585",
          ("#F72585", "#7209B7", "#3A0CA3", "#4CC9F0")),
    Theme("forest", "Wald", "#0D1B15", "#193126", "#EAF7EF", "#78D6A3",
          ("#173B2B", "#397A51", "#78D6A3")),
    Theme("ocean", "Ozean", "#0C1724", "#162A3D", "#ECF7FF", "#77D4FF",
          ("#0C1724", "#176B87", "#77D4FF")),
    Theme("sakura", "Sakura", "#261722", "#3B2134", "#FFF1F8", "#FF9ACF",
          ("#FF9ACF", "#E9B7D1", "#B77D9C")),
    Theme("mitternacht", "Mitternacht", "#090D18", "#141A2B", "#F0F4FF", "#93AFFF",
          ("#090D18", "#263B75", "#93AFFF")),
    Theme("kaffee", "Kaffee", "#211812", "#34251B", "#FFF3E3", "#E5B77C",
          ("#38251B", "#885B37", "#E5B77C")),
]
BUILTIN_THEMES: dict[str, Theme] = {t.name: t for t in _THEMES}


def custom_theme(name: str, bg: str, surface: str, fg: str, accent: str, label: str | None = None) -> Theme:
    """Erstellt ein eigenes Theme und lehnt es ab, wenn es die Kontrast-Mindestwerte verfehlt."""
    theme = Theme(name, label or name, bg, surface, fg, accent)
    issues = accessibility_issues(theme)
    if issues:
        raise ValueError("Theme nicht barrierearm genug: " + "; ".join(issues))
    return theme
