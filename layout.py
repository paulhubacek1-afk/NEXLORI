"""Layout: Block- und Inline-Fluss (Teilmenge) und Erzeugung einer Display-Liste.

Bekannte Einschränkungen (siehe docs/COMPATIBILITY.md): kein Float/Flex/Grid/Tabellenlayout,
keine Positionierung, Margin-Kollaps nur zwischen benachbarten Geschwistern, Inline-Elemente
ignorieren eigenes Padding/Margin/Background.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from .css import Color, Style
from .dom import Node


class Metrics(Protocol):
    def text_width(self, text: str, size: float, bold: bool) -> float: ...


class MonospaceMetrics:
    """Deterministische Ersatz-Metrik (0,6 em je Zeichen) für Tests und Umgebungen ohne Pillow."""

    def text_width(self, text: str, size: float, bold: bool) -> float:
        return 0.6 * size * len(text)


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float
    color: Color


@dataclass(frozen=True)
class Border:
    x: float
    y: float
    w: float
    h: float
    width: float
    color: Color


@dataclass(frozen=True)
class Text:
    x: float
    y: float
    text: str
    size: float
    bold: bool
    color: Color
    width: float = 0.0  # gemessene Breite (für Trefferflächen von Links)
    href: str | None = None  # Ziel, wenn der Text Teil eines Links ist


@dataclass
class Layout:
    commands: list = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0


@dataclass
class _Item:
    kind: str  # "text" | "br"
    text: str
    style: Style
    href: str | None = None


@dataclass
class _Seg:
    text: str
    style: Style
    width: float
    gap: float  # Abstand vor dem Segment (Leerraum zwischen unterschiedlich formatierten Segmenten)
    href: str | None = None

    @property
    def key(self):
        return _style_key(self.style, self.href)


@dataclass
class _Line:
    segs: list
    width: float
    height: float


def _num(value) -> float:
    return value if isinstance(value, (int, float)) else 0.0


def _style_key(s: Style, href: str | None = None):
    return (s.color, s.font_size, s.bold, s.underline, href)


def _link_href(node: Node) -> str | None:
    """href des nächsten umgebenden <a href> (auch wenn der Link per CSS ein Block ist)."""
    cur: Node | None = node
    while cur is not None:
        if cur.tag == "a" and "href" in cur.attrs:
            return cur.attrs["href"]
        cur = cur.parent
    return None


class LayoutEngine:
    def __init__(self, metrics: Metrics, viewport_width: float = 800.0):
        self.m = metrics
        self.viewport_width = float(viewport_width)
        self.cmds: list = []

    # ------------------------------------------------------------------ öffentlich
    def layout(self, root: Node) -> Layout:
        self.cmds = []
        height = self._children(root, 0.0, 0.0, self.viewport_width)
        return Layout(self.cmds, self.viewport_width, height)

    # ------------------------------------------------------------------ Blöcke
    def _children(self, node: Node, x: float, y: float, avail: float) -> float:
        cy = y
        pending: float | None = None  # unteres Margin des vorherigen Block-Geschwisters
        items: list = []
        align = node.style.text_align  # type: ignore[union-attr]

        def flush() -> None:
            nonlocal cy, pending
            if not any(it.kind == "br" or it.text.strip() for it in items):
                items.clear()
                return
            if pending:
                cy += pending
            pending = None
            cy += self._lines(items, x, cy, avail, align)
            items.clear()

        for child in node.children:
            if child.is_text:
                items.append(_Item("text", child.text, child.style, _link_href(child)))
                continue
            display = child.style.display  # type: ignore[union-attr]
            if display == "none":
                continue
            if display in ("block", "list-item"):
                flush()
                mt, mb = _num(child.style.margin[0]), _num(child.style.margin[2])  # type: ignore[union-attr]
                cy += mt if pending is None else max(pending, mt)
                cy += self._block(child, x, cy, avail)
                pending = mb
            else:
                self._collect_inline(child, items)
        flush()
        if pending:
            cy += pending
        return cy

    def _block(self, node: Node, x: float, y: float, avail: float) -> float:
        """Layoutet ein Blockelement. y ist die Oberkante der Border-Box. Gibt deren Höhe zurück."""
        s: Style = node.style  # type: ignore[assignment]
        pt, pr, pb, pl = (float(v) for v in s.padding)
        bw = s.effective_border
        extra = pl + pr + 2 * bw
        ml_raw, mr_raw = s.margin[3], s.margin[1]
        ml, mr = _num(ml_raw), _num(mr_raw)

        if s.width is None:
            content_w = max(0.0, avail - ml - mr - extra)
        else:
            if isinstance(s.width, str):  # Prozentwert
                content_w = float(s.width[:-1]) / 100.0 * avail
            else:
                content_w = float(s.width)
            free = max(0.0, avail - (content_w + extra) - (0 if ml_raw == "auto" else ml) - (0 if mr_raw == "auto" else mr))
            if ml_raw == "auto" and mr_raw == "auto":
                ml = free / 2
            elif ml_raw == "auto":
                ml = free

        box_x = x + ml
        content_x = box_x + bw + pl
        content_y = y + bw + pt

        slot = len(self.cmds)
        self.cmds.append(None)  # Platzhalter: Hintergrund/Rahmen werden vor den Kindern gezeichnet

        if s.display == "list-item":
            marker = self._marker(node)
            mw = self.m.text_width(marker, s.font_size, s.bold)
            lh = s.font_size * s.line_height
            self.cmds.append(Text(content_x - mw - 8, content_y + (lh - s.font_size) / 2, marker, s.font_size, s.bold, s.color))

        inner = self._children(node, content_x, content_y, content_w)
        content_h = float(s.height) if s.height is not None else inner - content_y
        box_w = content_w + extra
        box_h = content_h + pt + pb + 2 * bw

        deco: list = []
        if s.background is not None:
            deco.append(Rect(box_x, y, box_w, box_h, s.background))
        if bw > 0:
            deco.append(Border(box_x, y, box_w, box_h, bw, s.border_color or s.color))
        self.cmds[slot : slot + 1] = deco
        return box_h

    def _marker(self, node: Node) -> str:
        parent = node.parent
        if parent is not None and parent.tag == "ol":
            lis = [c for c in parent.children if not c.is_text and c.style.display == "list-item"]  # type: ignore[union-attr]
            return f"{lis.index(node) + 1}."
        return "\u2022"

    # ------------------------------------------------------------------ Inline
    def _collect_inline(self, node: Node, items: list) -> None:
        if node.is_text:
            items.append(_Item("text", node.text, node.style, _link_href(node)))
            return
        if node.style.display == "none":  # type: ignore[union-attr]
            return
        if node.tag == "br":
            items.append(_Item("br", "", node.style))
            return
        for child in node.children:
            self._collect_inline(child, items)

    def _break_lines(self, items: list, avail: float) -> list[_Line]:
        lines: list[_Line] = []
        segs: list[_Seg] = []
        line_w = 0.0
        line_h = 0.0
        pending_space: float | None = None

        def finish(blank_height: float | None = None) -> None:
            nonlocal segs, line_w, line_h, pending_space
            if segs:
                lines.append(_Line(segs, line_w, line_h))
            elif blank_height is not None:
                lines.append(_Line([], 0.0, blank_height))
            segs, line_w, line_h, pending_space = [], 0.0, 0.0, None

        for item in items:
            style = item.style
            lh = style.font_size * style.line_height
            if item.kind == "br":
                finish(blank_height=lh)
                continue
            for tok in re.split(r"(\s+)", item.text):
                if not tok:
                    continue
                if tok.isspace():
                    if segs and pending_space is None:
                        pending_space = self.m.text_width(" ", style.font_size, style.bold)
                    continue
                w = self.m.text_width(tok, style.font_size, style.bold)
                if segs and line_w + (pending_space or 0.0) + w > avail + 1e-6:
                    finish()
                gap = pending_space or 0.0
                if segs and segs[-1].key == _style_key(style, item.href):
                    segs[-1].text += (" " if pending_space else "") + tok
                    segs[-1].width += gap + w
                else:
                    segs.append(_Seg(tok, style, w, gap, item.href))
                line_w += gap + w
                line_h = max(line_h, lh)
                pending_space = None
        finish()
        return lines

    def _lines(self, items: list, x: float, y: float, avail: float, align: str) -> float:
        lines = self._break_lines(items, avail)
        cy = y
        for line in lines:
            offset = {"left": 0.0, "center": (avail - line.width) / 2, "right": avail - line.width}.get(align, 0.0)
            lx = x + max(0.0, offset)
            for seg in line.segs:
                lx += seg.gap
                st = seg.style
                ty = cy + (line.height - st.font_size) / 2
                self.cmds.append(Text(lx, ty, seg.text, st.font_size, st.bold, st.color, seg.width, seg.href))
                if st.underline:
                    self.cmds.append(Rect(lx, ty + st.font_size * 1.0, seg.width, max(1.0, st.font_size / 16), st.color))
                lx += seg.width
            cy += line.height
        return cy - y
