"""Experimenteller Rendering-Prototyp: HTML -> DOM -> Stile -> Layout -> Bitmap."""
from __future__ import annotations

import threading
from dataclasses import dataclass

from .css import Rule, compute_styles, parse_stylesheet
from .dom import Node, parse_html
from .fonts import default_metrics
from .layout import Layout, LayoutEngine, Metrics
from .paint import paint

__all__ = ["Document", "RenderResult", "render_html", "parse_html", "paint"]


class Document:
    """Geparste Seite. Parsen und Stilberechnung sind breitenunabhängig; nur das Layout hängt von Breite und Zoom ab."""

    def __init__(self, dom: Node, sheets: list[list[Rule]]):
        self.dom = dom
        self._sheets = sheets
        self._zoom = 1.0
        self._layout_key: tuple[int, float] | None = None
        self._layout: Layout | None = None
        self._lock = threading.RLock()  # Layout läuft in Hintergrund-Threads
        compute_styles(dom, sheets)

    @classmethod
    def from_html(cls, source: str) -> "Document":
        dom = parse_html(source)
        css = "\n".join(node.text_content() for node in dom.find_all("style"))
        return cls(dom, [parse_stylesheet(css)])

    @property
    def title(self) -> str:
        titles = self.dom.find_all("title")
        return " ".join(titles[0].text_content().split()) if titles else ""

    @property
    def background(self) -> tuple[int, int, int]:
        """Der Hintergrund von <html> bzw. <body> färbt – wie im Browser – die ganze Fläche."""
        for tag in ("html", "body"):
            for el in self.dom.find_all(tag):
                bg = el.style.background  # type: ignore[union-attr]
                if bg is not None:
                    return bg
        return (255, 255, 255)

    def layout(self, width: float, metrics: Metrics | None = None, zoom: float = 1.0) -> Layout:
        key = (round(width), zoom)
        with self._lock:
            if self._layout is not None and self._layout_key == key:
                return self._layout
            if zoom != self._zoom:
                compute_styles(self.dom, self._sheets, zoom)
                self._zoom = zoom
            self._layout = LayoutEngine(metrics or default_metrics(), width).layout(self.dom)
            self._layout_key = key
            return self._layout


@dataclass
class RenderResult:
    dom: Node
    layout: Layout
    background: tuple[int, int, int]

    def to_image(self):
        return paint(self.layout, self.background)


def render_html(source: str, width: int = 800, metrics: Metrics | None = None) -> RenderResult:
    doc = Document.from_html(source)
    return RenderResult(doc.dom, doc.layout(width, metrics), doc.background)
