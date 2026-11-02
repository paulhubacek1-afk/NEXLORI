"""Browser-Sitzung ohne Oberfläche: Adresseingabe, Links, Seiten laden, Verlauf und Tabs mit Ruhezustand."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus, urldefrag, urljoin, urlsplit
from urllib.request import url2pathname

from .core.modes import Mode, ModeController
from .core.settings import Settings
from .core.tabs import TabManager
from .engine import Document
from .net import HTML_TYPES, MAX_BYTES, FetchError, FetchResult, decode_body, fetch_url
from .startpage import ABOUT_PAGES, error_html, text_to_html

_HOST_RE = re.compile(
    r"^(localhost|[\w-]+(\.[\w-]+)+|\d{1,3}(\.\d{1,3}){3}|\[[0-9a-fA-F:]+\])(:\d+)?$"
)
_LOCAL_RE = re.compile(r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)", re.IGNORECASE)
_PATH_RE = re.compile(r"^([A-Za-z]:[\\/]|/|\\\\|~)")


def compatible_webengine_user_agent(user_agent: str) -> str:
    """Remove the QtWebEngine token while preserving the actual Chromium version."""
    return re.sub(r"\s+QtWebEngine/[^\s]+", "", str(user_agent or "")).strip()


# ----------------------------------------------------------------------------- Adressen
def normalize_input(text: str, search_url: str) -> str:
    """Macht aus der Adressleisten-Eingabe eine Adresse: URL, lokale Datei oder Suchanfrage."""
    text = text.strip()
    if not text:
        return "about:blank"
    if text.lower().startswith("about:"):
        return text.lower()
    if _PATH_RE.match(text):
        path = Path(os.path.expanduser(text))
        if path.exists():
            return path.resolve().as_uri()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text) or re.match(r"^(javascript|data|vbscript|mailto|file):", text, re.I):
        return text
    host = re.split(r"[/?#]", text, maxsplit=1)[0]
    if " " in text or not _HOST_RE.match(host):
        return search_url.format(quote_plus(text))
    return f"{'http' if _LOCAL_RE.match(host) else 'https'}://{text}"


def resolve_link(base_url: str, href: str) -> str | None:
    """Zieladresse eines Links oder None, wenn sie nicht geöffnet werden soll (z. B. javascript:, mailto:)."""
    href = href.strip()
    if not href or href.startswith("#"):
        return None
    target = urldefrag(urljoin(base_url, href))[0]
    scheme = urlsplit(target).scheme.lower()
    if scheme in ("http", "https"):
        return target
    if scheme == "about" and base_url.startswith("about:"):
        return target
    if scheme == "file" and base_url.lower().startswith(("file:", "about:")):
        return target  # lokale Seiten dürfen lokal verlinken, Webseiten nie auf Dateien
    return None


# ----------------------------------------------------------------------------- Seiten
@dataclass
class Page:
    url: str
    title: str
    document: Document | None  # None = Ruhezustand (Speicher freigegeben)
    status: int | None = None
    error: bool = False
    note: str = ""  # z. B. „Seite wurde gekürzt“


def _is_html(ctype: str) -> bool:
    return ctype in HTML_TYPES


def _build(url: str, html: str, **kw) -> Page:
    doc = Document.from_html(html)
    return Page(url, doc.title or url, doc, **kw)


def error_page(url: str, message: str) -> Page:
    doc = Document.from_html(error_html(url, message))
    return Page(url, "Fehler", doc, error=True, note=message)


def _load_file(url: str) -> Page:
    parts = urlsplit(url)
    if parts.netloc not in ("", "localhost"):
        raise FetchError("Netzwerkpfade werden nicht geladen.")
    path = Path(url2pathname(parts.path))
    if not path.is_file():
        raise FetchError("Die Datei wurde nicht gefunden.")
    suffix = path.suffix.lower()
    if suffix not in (".html", ".htm", ".xhtml", ".txt"):
        raise FetchError(f"Der Dateityp „{suffix or 'ohne Endung'}“ wird nicht unterstützt.")
    raw = path.read_bytes()[: MAX_BYTES + 1]
    truncated = len(raw) > MAX_BYTES
    text = decode_body(raw[:MAX_BYTES], None)
    return _build(url, text_to_html(text) if suffix == ".txt" else text, note="Datei wurde gekürzt." if truncated else "")


def load_page(url: str, fetcher: Callable[[str], FetchResult] = fetch_url) -> Page:
    """Lädt eine Seite (blockierend – die Oberfläche ruft das in einem Hintergrund-Thread auf)."""
    try:
        scheme = urlsplit(url).scheme.lower()
        if scheme == "about":
            html = ABOUT_PAGES.get(url.lower())
            if html is None:
                raise FetchError("Diese interne Seite gibt es nicht.")
            return _build(url.lower(), html)
        if scheme == "file":
            return _load_file(url)
        if scheme in ("http", "https"):
            res = fetcher(url)
            html = res.text if _is_html(res.content_type) else text_to_html(res.text)
            note = "Die Seite war sehr groß und wurde gekürzt." if res.truncated else ""
            return _build(res.url, html, status=res.status, note=note)
        raise FetchError(f"Das Adressschema „{scheme or '?'}“ wird nicht unterstützt.")
    except FetchError as exc:
        return error_page(url, str(exc))
    except RecursionError:
        return error_page(url, "Die Seite ist zu tief verschachtelt, um sie darzustellen.")
    except Exception as exc:  # noqa: BLE001 - die Oberfläche darf nie wegen einer Seite abstürzen
        return error_page(url, f"Unerwarteter Fehler beim Darstellen der Seite ({type(exc).__name__}: {exc}).")


# ----------------------------------------------------------------------------- Verlauf / Sitzung
@dataclass
class History:
    entries: list[str] = field(default_factory=list)
    index: int = -1
    limit: int = 200

    @property
    def current(self) -> str | None:
        return self.entries[self.index] if 0 <= self.index < len(self.entries) else None

    @property
    def can_back(self) -> bool:
        return self.index > 0

    @property
    def can_forward(self) -> bool:
        return self.index < len(self.entries) - 1

    def visit(self, url: str) -> None:
        del self.entries[self.index + 1 :]
        self.entries.append(url)
        if len(self.entries) > self.limit:
            del self.entries[0]
        self.index = len(self.entries) - 1

    def replace(self, url: str) -> None:
        if self.current is None:
            self.visit(url)
        else:
            self.entries[self.index] = url

    def back(self) -> str | None:
        if not self.can_back:
            return None
        self.index -= 1
        return self.current

    def forward(self) -> str | None:
        if not self.can_forward:
            return None
        self.index += 1
        return self.current


class BrowserSession:
    """Tabs + Verlauf + Modus-Steuerung. Enthält keinerlei Oberflächencode."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.tabs = TabManager()
        self.history: dict[int, History] = {}
        self.modes = ModeController(
            Mode(self.settings.mode),
            gaming_auto_switch=self.settings.gaming_auto_switch,
            auto_restore=self.settings.gaming_auto_restore,
        )

    def open_tab(self, now: float, activate: bool = True) -> int:
        tab = self.tabs.open("", now, activate=activate)
        self.history[tab.id] = History()
        return tab.id

    def close_tab(self, tab_id: int) -> None:
        self.tabs.close(tab_id)
        self.history.pop(tab_id, None)

    def resolve_input(self, text: str) -> str:
        return normalize_input(text, self.settings.search_url)

    def commit(self, tab_id: int, url: str, *, push: bool = True) -> None:
        """Eine Seite wurde geladen: Verlauf und Tab-Adresse aktualisieren."""
        self.tabs.tabs[tab_id].url = url
        hist = self.history[tab_id]
        hist.visit(url) if push else hist.replace(url)

    def go_back(self, tab_id: int) -> str | None:
        return self.history[tab_id].back()

    def go_forward(self, tab_id: int) -> str | None:
        return self.history[tab_id].forward()

    def tick(self, now: float) -> list[int]:
        """Legt inaktive Tabs gemäß aktuellem Modus schlafen. Gibt die betroffenen Tab-IDs zurück."""
        return self.tabs.apply_policy(now, self.modes.profile)
