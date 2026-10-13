"""Eigener HTML-Tokenizer und DOM-Aufbau.

Bewusst klein gehalten: Der Parser folgt NICHT dem vollständigen HTML-Parsing-Algorithmus
des WHATWG-Standards. Er deckt gut geformtes HTML sowie die häufigsten impliziten
End-Tags (<p>, <li>) ab. Siehe docs/COMPATIBILITY.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape  # nur die Entity-Tabelle der Standardbibliothek wird genutzt

VOID_ELEMENTS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)
RAW_TEXT_ELEMENTS = frozenset({"script", "style"})
# Block-Elemente, die ein noch offenes <p> implizit schließen.
CLOSES_P = frozenset(
    "address article aside blockquote div dl fieldset footer form h1 h2 h3 h4 h5 h6 "
    "header hr main nav ol p pre section table ul".split()
)

_START_RE = re.compile(
    r"<([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^\s\"'>/=]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'>]+))?)*)\s*(/?)>"
)
_END_RE = re.compile(r"</([a-zA-Z][a-zA-Z0-9-]*)\s*>")
_ATTR_RE = re.compile(r"([^\s\"'>/=]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'>]+)))?")


@dataclass(eq=False)
class Node:
    """Element (tag gesetzt) oder Textknoten (tag ist None)."""

    tag: str | None
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    parent: "Node | None" = None
    text: str = ""
    style: object | None = None  # wird von engine.css.compute_styles gesetzt

    @property
    def is_text(self) -> bool:
        return self.tag is None

    @property
    def classes(self) -> list[str]:
        return self.attrs.get("class", "").split()

    def append(self, child: "Node") -> None:
        child.parent = self
        self.children.append(child)

    def iter(self):
        """Tiefensuche in Dokumentreihenfolge (inklusive self)."""
        yield self
        for child in self.children:
            yield from child.iter()

    def find_all(self, tag: str) -> list["Node"]:
        return [n for n in self.iter() if n.tag == tag]

    def text_content(self) -> str:
        if self.is_text:
            return self.text
        return "".join(c.text_content() for c in self.children)

    def __repr__(self) -> str:  # pragma: no cover - nur für Debugging
        return f"Text({self.text!r})" if self.is_text else f"<{self.tag} {len(self.children)} children>"


def _parse_attrs(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for m in _ATTR_RE.finditer(raw):
        name = m.group(1).lower()
        value = next((g for g in m.groups()[1:] if g is not None), "")
        attrs.setdefault(name, unescape(value))
    return attrs


def parse_html(source: str) -> Node:
    """Wandelt HTML-Text in einen DOM-Baum. Wurzel ist ein Knoten mit tag '#document'."""
    root = Node("#document")
    stack: list[Node] = [root]
    i, n = 0, len(source)

    def add_text(text: str) -> None:
        if not text:
            return
        parent = stack[-1]
        if parent.children and parent.children[-1].is_text:
            parent.children[-1].text += text
        else:
            parent.append(Node(None, text=text))

    while i < n:
        if source[i] != "<":
            j = source.find("<", i)
            j = n if j == -1 else j
            add_text(unescape(source[i:j]))
            i = j
            continue
        if source.startswith("<!--", i):
            j = source.find("-->", i + 4)
            i = n if j == -1 else j + 3
            continue
        if source.startswith("<!", i) or source.startswith("<?", i):
            j = source.find(">", i)
            i = n if j == -1 else j + 1
            continue
        if source.startswith("</", i):
            m = _END_RE.match(source, i)
            if not m:
                add_text("<")
                i += 1
                continue
            tag = m.group(1).lower()
            for depth in range(len(stack) - 1, 0, -1):
                if stack[depth].tag == tag:
                    del stack[depth:]
                    break
            i = m.end()
            continue
        m = _START_RE.match(source, i)
        if not m:
            add_text("<")
            i += 1
            continue
        tag = m.group(1).lower()
        attrs = _parse_attrs(m.group(2))
        self_closing = bool(m.group(3))
        i = m.end()

        # implizite End-Tags
        if tag in CLOSES_P and stack[-1].tag == "p":
            stack.pop()
        if tag == "li":
            for depth in range(len(stack) - 1, 0, -1):
                if stack[depth].tag in ("ul", "ol"):
                    break
                if stack[depth].tag == "li":
                    del stack[depth:]
                    break

        el = Node(tag, attrs)
        stack[-1].append(el)
        if tag in RAW_TEXT_ELEMENTS and not self_closing:
            end = re.compile(r"</%s\s*>" % tag, re.IGNORECASE).search(source, i)
            stop = end.start() if end else n
            if stop > i:
                el.append(Node(None, text=source[i:stop], parent=el))
            i = end.end() if end else n
            continue
        if tag not in VOID_ELEMENTS and not self_closing:
            stack.append(el)
    return root
