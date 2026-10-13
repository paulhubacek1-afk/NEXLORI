"""Eigener CSS-Parser, Selektor-Matching, Kaskade und berechnete Stile (Teilmenge).

Unterstützt: Typ-/Klassen-/ID-/Universalselektoren, Selektorlisten, Nachfahren- und
Kind-Kombinatoren, !important, style-Attribut. Nicht unterstützt (Regel wird verworfen):
Pseudoklassen, Attributselektoren, Geschwister-Kombinatoren, @-Regeln.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .dom import Node

Color = tuple[int, int, int]

NAMED_COLORS: dict[str, Color | None] = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
    "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
    "orange": (255, 165, 0), "purple": (128, 0, 128), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "silver": (192, 192, 192), "navy": (0, 0, 128),
    "teal": (0, 128, 128), "maroon": (128, 0, 0), "lime": (0, 255, 0),
    "aqua": (0, 255, 255), "fuchsia": (255, 0, 255), "olive": (128, 128, 0),
    "pink": (255, 192, 203), "transparent": None,
}
FONT_SIZE_KEYWORDS = {
    "xx-small": 9.0, "x-small": 10.0, "small": 13.0, "medium": 16.0,
    "large": 18.0, "x-large": 24.0, "xx-large": 32.0,
}
BORDER_STYLES = {"none", "solid", "dashed", "dotted", "double"}


# --------------------------------------------------------------------------- Werte
def parse_color(value: str) -> Color | None:
    """Gibt (r, g, b) zurück, None für 'transparent'. ValueError bei ungültigem Wert."""
    v = value.strip().lower()
    if v in NAMED_COLORS:
        return NAMED_COLORS[v]
    if re.fullmatch(r"#[0-9a-f]{3}", v):
        return tuple(int(c * 2, 16) for c in v[1:])  # type: ignore[return-value]
    if re.fullmatch(r"#[0-9a-f]{6}", v):
        return int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16)
    m = re.fullmatch(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", v)
    if m:
        r, g, b = (int(x) for x in m.groups())
        if max(r, g, b) <= 255:
            return r, g, b
    raise ValueError(f"ungültige Farbe: {value!r}")


_LEN_RE = re.compile(r"^(-?(?:\d+\.?\d*|\.\d+))(px|em|rem|pt|%)?$")


def parse_length(value: str, font_size: float) -> float | str:
    """Px-Wert (float), 'auto' oder Prozentwert als String ('50%'). Sonst ValueError."""
    v = value.strip().lower()
    if v == "auto":
        return "auto"
    m = _LEN_RE.match(v)
    if not m:
        raise ValueError(f"ungültige Länge: {value!r}")
    num, unit = float(m.group(1)), m.group(2)
    if unit is None:
        if num != 0:
            raise ValueError("Einheit fehlt")
        return 0.0
    if unit == "px":
        return num
    if unit == "em":
        return num * font_size
    if unit == "rem":
        return num * 16.0
    if unit == "pt":
        return num * 4.0 / 3.0
    return f"{num:g}%"


def _abs_length(value: str, font_size: float, *, allow_auto: bool, allow_negative: bool) -> float | str:
    result = parse_length(value, font_size)
    if isinstance(result, str) and result != "auto":
        raise ValueError("Prozentwerte werden hier noch nicht unterstützt")
    if result == "auto" and not allow_auto:
        raise ValueError("auto nicht erlaubt")
    if isinstance(result, float) and result < 0 and not allow_negative:
        raise ValueError("negativer Wert nicht erlaubt")
    return result


def _expand_box(value: str) -> list[str]:
    parts = value.split()
    if not 1 <= len(parts) <= 4:
        raise ValueError("1 bis 4 Werte erwartet")
    if len(parts) == 1:
        return parts * 4
    if len(parts) == 2:
        return [parts[0], parts[1], parts[0], parts[1]]
    if len(parts) == 3:
        return [parts[0], parts[1], parts[2], parts[1]]
    return parts


# --------------------------------------------------------------------------- Stil
@dataclass
class Style:
    display: str = "inline"
    color: Color = (0, 0, 0)
    background: Color | None = None
    font_size: float = 16.0
    bold: bool = False
    text_align: str = "left"
    underline: bool = False
    line_height: float = 1.2  # Vielfaches der Schriftgröße
    margin: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])  # t r b l (float | 'auto')
    padding: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    border_width: float = 0.0
    border_style: str = "none"
    border_color: Color | None = None  # None = currentcolor
    width: float | str | None = None  # px, '50%' oder None (auto)
    height: float | None = None

    @property
    def effective_border(self) -> float:
        return self.border_width if self.border_style != "none" else 0.0


def inherit(parent: Style) -> Style:
    return Style(
        color=parent.color, font_size=parent.font_size, bold=parent.bold,
        text_align=parent.text_align, underline=parent.underline, line_height=parent.line_height,
    )


def _tokens(value: str) -> list[str]:
    return re.findall(r"rgb\([^)]*\)|\S+", value)


def apply_declaration(style: Style, prop: str, value: str, parent: Style) -> None:
    """Wendet eine Deklaration an. Ungültige Werte werfen ValueError und werden ignoriert."""
    v = value.strip().lower()
    if prop == "display":
        style.display = v
    elif prop == "color":
        c = parse_color(v)
        if c is not None:
            style.color = c
    elif prop in ("background", "background-color"):
        for tok in _tokens(v):
            try:
                style.background = parse_color(tok)
                return
            except ValueError:
                continue
        raise ValueError("keine Farbe gefunden")
    elif prop == "font-size":
        if v in FONT_SIZE_KEYWORDS:
            style.font_size = FONT_SIZE_KEYWORDS[v]
        else:
            size = parse_length(v, parent.font_size)
            if isinstance(size, str):
                if size == "auto":
                    raise ValueError("auto ungültig")
                size = float(size[:-1]) / 100.0 * parent.font_size
            if size <= 0:
                raise ValueError("Schriftgröße muss positiv sein")
            style.font_size = size
    elif prop == "font-weight":
        if v in ("bold", "bolder"):
            style.bold = True
        elif v in ("normal", "lighter"):
            style.bold = False
        elif v.isdigit():
            style.bold = int(v) >= 600
        else:
            raise ValueError("ungültiges font-weight")
    elif prop == "text-align":
        if v not in ("left", "center", "right"):
            raise ValueError("nicht unterstützt")
        style.text_align = v
    elif prop in ("text-decoration", "text-decoration-line"):
        style.underline = "underline" in v
    elif prop == "line-height":
        if v == "normal":
            style.line_height = 1.2
        elif re.fullmatch(r"\d*\.?\d+", v):
            style.line_height = float(v)
        else:
            px = parse_length(v, style.font_size)
            if isinstance(px, str):
                raise ValueError("Prozent/auto nicht unterstützt")
            style.line_height = px / style.font_size
    elif prop == "margin":
        style.margin = [_abs_length(p, style.font_size, allow_auto=True, allow_negative=True) for p in _expand_box(v)]
    elif prop == "padding":
        style.padding = [_abs_length(p, style.font_size, allow_auto=False, allow_negative=False) for p in _expand_box(v)]
    elif prop.startswith(("margin-", "padding-")):
        kind, side = prop.split("-", 1)
        idx = {"top": 0, "right": 1, "bottom": 2, "left": 3}.get(side)
        if idx is None:
            raise ValueError("unbekannte Seite")
        target = style.margin if kind == "margin" else style.padding
        target[idx] = _abs_length(
            v, style.font_size, allow_auto=(kind == "margin"), allow_negative=(kind == "margin")
        )
    elif prop in ("width", "height"):
        parsed = None if v == "auto" else parse_length(v, style.font_size)
        if isinstance(parsed, float) and parsed < 0:
            raise ValueError("negativ")
        if prop == "height" and isinstance(parsed, str):
            raise ValueError("Prozenthöhen nicht unterstützt")
        setattr(style, prop, parsed)
    elif prop == "border":
        width, bstyle, color = style.border_width, style.border_style, style.border_color
        if v == "none":
            style.border_style = "none"
            style.border_width = 0.0
            return
        width = 3.0 if width == 0 else width  # CSS-Standard 'medium', wenn keine Breite genannt wird
        for tok in _tokens(v):
            if tok in BORDER_STYLES:
                bstyle = tok
                continue
            try:
                parsed_len = _abs_length(tok, style.font_size, allow_auto=False, allow_negative=False)
                width = float(parsed_len)  # type: ignore[arg-type]
            except ValueError:
                color = None if tok == "currentcolor" else parse_color(tok)
        style.border_width, style.border_style, style.border_color = width, bstyle, color
    elif prop == "border-width":
        style.border_width = float(_abs_length(v, style.font_size, allow_auto=False, allow_negative=False))
    elif prop == "border-style":
        if v not in BORDER_STYLES:
            raise ValueError("unbekannter Stil")
        style.border_style = v
    elif prop == "border-color":
        style.border_color = None if v == "currentcolor" else parse_color(v)
    # Alle anderen Eigenschaften werden bewusst ignoriert (siehe docs/COMPATIBILITY.md).


# ----------------------------------------------------------------- Selektoren / Regeln
_COMPOUND_RE = re.compile(r"^(\*|[a-zA-Z][\w-]*)?((?:[#.][\w-]+)*)$")


@dataclass(frozen=True)
class Compound:
    tag: str | None
    id: str | None
    classes: tuple[str, ...]

    def matches(self, node: Node) -> bool:
        if node.is_text:
            return False
        if self.tag and self.tag != node.tag:
            return False
        if self.id and node.attrs.get("id") != self.id:
            return False
        have = node.classes
        return all(c in have for c in self.classes)


@dataclass(frozen=True)
class Selector:
    parts: tuple[tuple[str, Compound], ...]  # (Kombinator vor dem Teil, Teil)

    @property
    def specificity(self) -> tuple[int, int, int]:
        ids = sum(1 for _, c in self.parts if c.id)
        cls = sum(len(c.classes) for _, c in self.parts)
        tags = sum(1 for _, c in self.parts if c.tag)
        return ids, cls, tags

    def matches(self, node: Node) -> bool:
        return self._match(len(self.parts) - 1, node)

    def _match(self, idx: int, node: Node) -> bool:
        comb, comp = self.parts[idx]
        if not comp.matches(node):
            return False
        if idx == 0:
            return True
        anc = node.parent
        if comb == ">":
            return anc is not None and self._match(idx - 1, anc)
        while anc is not None:
            if self._match(idx - 1, anc):
                return True
            anc = anc.parent
        return False


def parse_selector(text: str) -> Selector | None:
    """None, wenn der Selektor (noch) nicht unterstützt wird."""
    text = text.strip()
    if not text or any(ch in text for ch in "+~[:"):
        return None
    parts: list[tuple[str, Compound]] = []
    for comb, comp_text in re.findall(r"\s*(>?)\s*([^\s>]+)", text):
        m = _COMPOUND_RE.match(comp_text)
        if not m:
            return None
        tag = m.group(1)
        tag = None if tag in (None, "", "*") else tag.lower()
        ids = re.findall(r"#([\w-]+)", m.group(2))
        classes = tuple(re.findall(r"\.([\w-]+)", m.group(2)))
        if len(ids) > 1:
            return None
        parts.append((comb or " ", Compound(tag, ids[0] if ids else None, classes)))
    return Selector(tuple(parts)) if parts else None


@dataclass(frozen=True)
class Rule:
    selector: Selector
    declarations: tuple[tuple[str, str, bool], ...]  # (Eigenschaft, Wert, !important)


_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def parse_declarations(text: str) -> list[tuple[str, str, bool]]:
    out = []
    for chunk in text.split(";"):
        if ":" not in chunk:
            continue
        prop, value = chunk.split(":", 1)
        prop, value = prop.strip().lower(), value.strip()
        important = False
        if value.lower().endswith("!important"):
            important, value = True, value[: -len("!important")].strip()
        if prop and value:
            out.append((prop, value, important))
    return out


def parse_stylesheet(text: str) -> list[Rule]:
    text = _COMMENT_RE.sub("", text)
    rules: list[Rule] = []
    i, n = 0, len(text)
    while i < n:
        j = text.find("{", i)
        if j == -1:
            break
        prelude = text[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            depth += (text[k] == "{") - (text[k] == "}")
            k += 1
        body = text[j + 1 : k - 1]
        i = k
        if ";" in prelude:  # z. B. "@import url(x); a" -> "a"
            prelude = prelude.rsplit(";", 1)[1].strip()
        if prelude.startswith("@"):
            continue  # @media, @font-face, ... werden noch nicht unterstützt
        decls = tuple(parse_declarations(body))
        for sel_text in prelude.split(","):
            sel = parse_selector(sel_text)
            if sel is not None:
                rules.append(Rule(sel, decls))
    return rules


UA_STYLESHEET = parse_stylesheet(
    """
    html, body, div, p, section, article, header, footer, nav, main, aside, form,
    h1, h2, h3, h4, h5, h6, ul, ol, blockquote, pre, address, center, figure, figcaption,
    details, summary, fieldset, legend, dl, dt, dd, hgroup, menu,
    table, thead, tbody, tfoot, caption, tr, td, th { display: block }
    li { display: list-item }
    head, script, style, title, meta, link, template, noembed, svg, canvas, video, audio,
    iframe, object, embed, select, textarea, datalist, option { display: none }
    body { margin: 8px }
    p { margin: 1em 0 }
    h1 { font-size: 2em; font-weight: bold; margin: 0.67em 0 }
    h2 { font-size: 1.5em; font-weight: bold; margin: 0.83em 0 }
    h3 { font-size: 1.17em; font-weight: bold; margin: 1em 0 }
    h4 { font-size: 1em; font-weight: bold; margin: 1.33em 0 }
    h5 { font-size: 0.83em; font-weight: bold; margin: 1.67em 0 }
    h6 { font-size: 0.67em; font-weight: bold; margin: 2.33em 0 }
    b, strong, th { font-weight: bold }
    small { font-size: 0.83em }
    big { font-size: 1.17em }
    center { text-align: center }
    a { color: #0000ee; text-decoration: underline }
    ul, ol { margin: 1em 0; padding-left: 40px }
    dd { margin-left: 40px }
    blockquote { margin: 1em 40px }
    hr { display: block; height: 1px; background: #888888; margin: 8px 0 }
    """
)


class _RuleIndex:
    """Sortiert Regeln nach ihrem rechtesten Selektorteil, damit nicht jede Regel für jedes Element geprüft wird."""

    def __init__(self, rules: list[tuple[int, int, "Rule"]]):
        self.by_id: dict[str, list] = {}
        self.by_class: dict[str, list] = {}
        self.by_tag: dict[str, list] = {}
        self.universal: list = []
        for item in rules:
            comp = item[2].selector.parts[-1][1]
            if comp.id:
                self.by_id.setdefault(comp.id, []).append(item)
            elif comp.classes:
                self.by_class.setdefault(comp.classes[0], []).append(item)
            elif comp.tag:
                self.by_tag.setdefault(comp.tag, []).append(item)
            else:
                self.universal.append(item)

    def candidates(self, node: Node) -> list:
        out = list(self.universal)
        out += self.by_tag.get(node.tag or "", [])
        ident = node.attrs.get("id")
        if ident:
            out += self.by_id.get(ident, [])
        for cls in set(node.classes):
            out += self.by_class.get(cls, [])
        return out


def scale_styles(root: Node, zoom: float) -> None:
    """Skaliert alle absoluten Längen (Zoom / Bildschirmskalierung). Einmal nach compute_styles aufrufen."""
    if zoom == 1.0:
        return
    for node in root.iter():
        s = node.style
        if s is None:
            continue
        s.font_size *= zoom
        s.margin = [v * zoom if isinstance(v, (int, float)) else v for v in s.margin]
        s.padding = [v * zoom for v in s.padding]
        s.border_width *= zoom
        if isinstance(s.width, (int, float)):
            s.width *= zoom
        if s.height is not None:
            s.height *= zoom


def compute_styles(root: Node, author_sheets: list[list[Rule]] | None = None, zoom: float = 1.0) -> None:
    """Berechnet node.style für alle Knoten unterhalb von root (Kaskade + Vererbung + Zoom)."""
    root.style = Style(display="block")
    rules: list[tuple[int, int, Rule]] = [(0, i, r) for i, r in enumerate(UA_STYLESHEET)]
    order = 0
    for sheet in author_sheets or []:
        for r in sheet:
            rules.append((1, order, r))
            order += 1
    index = _RuleIndex(rules)
    for child in root.children:
        _compute(child, root.style, index)  # type: ignore[arg-type]
    scale_styles(root, zoom)


def _compute(node: Node, parent: Style, index: _RuleIndex) -> None:
    style = inherit(parent)
    if node.is_text:
        node.style = style
        return
    candidates = []  # (important, origin, spec, order, prop, value)
    for origin, order, rule in index.candidates(node):
        if rule.selector.matches(node):
            for prop, value, imp in rule.declarations:
                candidates.append((imp, origin, rule.selector.specificity, order, prop, value))
    for prop, value, imp in parse_declarations(node.attrs.get("style", "")):
        candidates.append((imp, 2, (0, 0, 0), 0, prop, value))
    candidates.sort(key=lambda c: c[:4])
    for font_size_pass in (True, False):  # font-size zuerst, damit em-Werte stimmen
        for _imp, _origin, _spec, _order, prop, value in candidates:
            if (prop == "font-size") != font_size_pass:
                continue
            try:
                apply_declaration(style, prop, value, parent)
            except ValueError:
                pass  # ungültige Deklarationen werden wie in CSS ignoriert
    if "hidden" in node.attrs:
        style.display = "none"
    node.style = style
    for child in node.children:
        _compute(child, style, index)
