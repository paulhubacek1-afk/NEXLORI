"""Theme-Shop: Themes werden bei Bedarf geladen und liegen nur nach der Installation auf dem Gerät.

Der Katalog ist eine kleine JSON-Datei im GitHub-Repository (``NEXLORI/themes/catalog.json``).
Ein Theme besteht ausschließlich aus Farbwerten (``#RRGGBB``) und einem Namen – es gibt weder Code
noch CSS, das aus dem Netz nachgeladen wird. Jeder Eintrag wird streng geprüft:

- gültiger Name (a-z, 0-9, ``-``), der keines der eingebauten Themes überschreibt,
- gültige Farben, höchstens 12 Streifenfarben,
- Barrierefreiheit (WCAG-Kontrast) wie bei eigenen Themes.

Die Schicht ist bewusst frei von Qt, damit sie ohne Oberfläche getestet werden kann.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .themes import (
    BUILTIN_THEMES,
    Theme,
    accessibility_issues,
    register_installed_theme,
    unregister_installed_theme,
)

REPOSITORY = "paulhubacek1-afk/NEXLORI"
SHOP_CATALOG_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/main/NEXLORI/themes/catalog.json"
ALLOWED_HOSTS = frozenset({"raw.githubusercontent.com"})
MAX_CATALOG_BYTES = 512 * 1024
MAX_SHOP_THEMES = 400
MAX_INSTALLED_THEMES = 200
MAX_THEME_FILE_BYTES = 16 * 1024
_TEXT_RE = re.compile(r"^[^\x00-\x1f<>]{1,60}$")
_CATEGORY_RE = re.compile(r"^[A-Za-zÄÖÜäöüß0-9 &-]{1,24}$")
_NAME_RE = re.compile(r"^[a-z0-9-]{1,40}$")


class ShopError(RuntimeError):
    """Der Katalog konnte nicht geladen oder ein Theme nicht gespeichert werden."""


@dataclass(frozen=True)
class ShopTheme:
    theme: Theme
    category: str = "Sonstige"
    author: str = "Nexlori"
    rev: int = 1
    description: str = ""

    @property
    def name(self) -> str:
        return self.theme.name


def _clean_text(value: Any, default: str, limit: int = 60) -> str:
    if isinstance(value, str) and _TEXT_RE.match(value.strip()):
        return value.strip()[:limit]
    return default


def parse_shop_theme(entry: Any) -> ShopTheme:
    """Prüft einen Katalogeintrag und gibt das Theme zurück (``ValueError`` bei Problemen)."""
    if not isinstance(entry, dict):
        raise ValueError("Eintrag ist kein Objekt")
    name = entry.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValueError("ungültiger Name")
    if name in BUILTIN_THEMES:
        raise ValueError("überschreibt ein eingebautes Theme")
    stripes = entry.get("stripes", [])
    if not isinstance(stripes, list) or len(stripes) > 12 or any(not isinstance(c, str) for c in stripes):
        raise ValueError("ungültige Streifenfarben")
    label = _clean_text(entry.get("label"), name, 40)
    for key in ("bg", "surface", "fg", "accent"):
        if not isinstance(entry.get(key), str):
            raise ValueError(f"Farbe fehlt: {key}")
    theme = Theme(name, label, entry["bg"], entry["surface"], entry["fg"], entry["accent"], tuple(stripes))
    issues = accessibility_issues(theme)
    if issues:
        raise ValueError("nicht barrierearm: " + "; ".join(issues))
    category = entry.get("category", "Sonstige")
    if not isinstance(category, str) or not _CATEGORY_RE.match(category):
        category = "Sonstige"
    rev = entry.get("rev", 1)
    if not isinstance(rev, int) or isinstance(rev, bool) or not 1 <= rev <= 1_000_000:
        rev = 1
    return ShopTheme(
        theme=theme,
        category=category,
        author=_clean_text(entry.get("author"), "Unbekannt", 40),
        rev=rev,
        description=_clean_text(entry.get("description"), "", 120),
    )


def parse_catalog(raw: bytes | str) -> tuple[list[ShopTheme], int]:
    """Liest den Katalog. Ungültige Einträge werden übersprungen; Rückgabe: (Themes, Anzahl übersprungen)."""
    if isinstance(raw, bytes):
        if len(raw) > MAX_CATALOG_BYTES:
            raise ShopError("Der Theme-Katalog ist zu groß.")
        raw = raw.decode("utf-8")
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ShopError("Der Theme-Katalog ist beschädigt.") from exc
    if not isinstance(data, dict) or data.get("format") != 1 or not isinstance(data.get("themes"), list):
        raise ShopError("Der Theme-Katalog hat ein unbekanntes Format.")
    themes: list[ShopTheme] = []
    seen: set[str] = set()
    skipped = 0
    for entry in data["themes"][:MAX_SHOP_THEMES]:
        try:
            item = parse_shop_theme(entry)
        except ValueError:
            skipped += 1
            continue
        if item.name in seen:
            skipped += 1
            continue
        seen.add(item.name)
        themes.append(item)
    skipped += max(0, len(data["themes"]) - MAX_SHOP_THEMES)
    return themes, skipped


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    """Folgt Weiterleitungen nur auf erlaubte HTTPS-Hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        parts = urlsplit(newurl)
        if parts.scheme != "https" or (parts.hostname or "") not in ALLOWED_HOSTS:
            raise urllib.error.URLError("Weiterleitung auf einen nicht erlaubten Host blockiert")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "") not in ALLOWED_HOSTS:
        raise ShopError("Der Theme-Katalog darf nur von GitHub über HTTPS geladen werden.")


def fetch_catalog(
    url: str = SHOP_CATALOG_URL,
    timeout: float = 8.0,
    opener: Callable[..., Any] | None = None,
) -> tuple[list[ShopTheme], int]:
    """Lädt und prüft den Katalog. ``opener`` ist nur für Tests gedacht."""
    _check_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "Nexlori-ThemeShop", "Accept": "application/json"})
    open_url = opener or urllib.request.build_opener(_SafeRedirects()).open
    try:
        with open_url(request, timeout=timeout) as response:
            raw = response.read(MAX_CATALOG_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ShopError("Der Theme-Katalog wurde nicht gefunden (noch nicht veröffentlicht?).") from exc
        raise ShopError(f"Der Theme-Shop antwortet mit Fehler {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ShopError("Der Theme-Shop ist nicht erreichbar. Prüfe deine Internetverbindung.") from exc
    return parse_catalog(raw)


class ThemeStore:
    """Installierte Shop-Themes: je Theme eine kleine JSON-Datei im Nexlori-Profilordner."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _path(self, name: str) -> Path:
        if not _NAME_RE.match(name):
            raise ShopError("Ungültiger Theme-Name.")
        return self.directory / f"{name}.json"

    def installed(self) -> dict[str, tuple[Theme, int]]:
        """Alle gültigen installierten Themes: Name -> (Theme, Version)."""
        result: dict[str, tuple[Theme, int]] = {}
        if not self.directory.is_dir():
            return result
        for path in sorted(self.directory.glob("*.json"))[:MAX_INSTALLED_THEMES]:
            try:
                if path.stat().st_size > MAX_THEME_FILE_BYTES:
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                item = parse_shop_theme(data["theme"])
                if item.name != path.stem:
                    continue
                rev = data.get("rev", item.rev)
                result[item.name] = (item.theme, rev if isinstance(rev, int) else item.rev)
            except (OSError, ValueError, KeyError, TypeError):
                continue  # beschädigte oder manipulierte Datei: ignorieren
        return result

    def load_into_registry(self) -> list[str]:
        """Macht alle installierten Themes in Nexlori verfügbar (beim Programmstart aufrufen)."""
        names = []
        for name, (theme, _rev) in self.installed().items():
            try:
                register_installed_theme(theme)
                names.append(name)
            except ValueError:
                continue
        return names

    def install(self, item: ShopTheme) -> None:
        if len(self.installed()) >= MAX_INSTALLED_THEMES and item.name not in self.installed():
            raise ShopError("Es sind bereits zu viele Themes installiert.")
        payload = {
            "format": 1,
            "rev": item.rev,
            "theme": {
                **item.theme.to_dict(),
                "category": item.category, "author": item.author, "rev": item.rev, "description": item.description,
            },
        }
        path = self._path(item.name)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2, ensure_ascii=False)
                os.replace(tmp, path)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise
        except OSError as exc:
            raise ShopError("Das Theme konnte nicht gespeichert werden.") from exc
        register_installed_theme(item.theme)

    def remove(self, name: str) -> bool:
        path = self._path(name)
        unregister_installed_theme(name)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise ShopError("Das Theme konnte nicht entfernt werden.") from exc


def default_theme_dir(settings_path: Path) -> Path:
    return Path(settings_path).parent / "themes"
