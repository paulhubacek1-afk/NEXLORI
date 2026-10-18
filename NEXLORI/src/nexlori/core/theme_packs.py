"""Downloadable and portable Nexlori theme packs (data only; no remote code)."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

from .theme_shop import ShopError, ShopTheme, parse_shop_theme

REPOSITORY = "paulhubacek1-afk/NEXLORI"
PACK_BASE_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/main/NEXLORI/themes/packs/"
PACK_CATALOG_URL = PACK_BASE_URL + "catalog.json"
PACK_CATALOG_PATH = f"/{REPOSITORY}/main/NEXLORI/themes/packs/catalog.json"
MAX_PACK_CATALOG_BYTES = 256 * 1024
MAX_PACK_BYTES = 512 * 1024
MAX_PACKS = 50
MAX_PACK_THEMES = 200
_NAME_RE = re.compile(r"^[a-z0-9-]{1,40}$")
_TEXT_RE = re.compile(r"^[^\x00-\x1f<>]{1,160}$")


@dataclass(frozen=True)
class ThemePackInfo:
    name: str
    label: str
    description: str
    url: str


@dataclass(frozen=True)
class ThemePack:
    name: str
    label: str
    description: str
    themes: tuple[ShopTheme, ...]


def _text(value: Any, *, limit: int, default: str = "") -> str:
    if not isinstance(value, str):
        return default
    value = value.strip()
    if not value or len(value) > limit or not _TEXT_RE.fullmatch(value):
        return default
    return value


def _check_url(url: str, *, catalog: bool = False) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "raw.githubusercontent.com" or parts.username or parts.password:
        raise ShopError("Theme-Packs dürfen nur von GitHub über HTTPS geladen werden.")
    if parts.query or parts.fragment or parts.port not in (None, 443):
        raise ShopError("Die Theme-Pack-Adresse enthält unerlaubte Zusätze.")
    if catalog:
        if parts.path != PACK_CATALOG_PATH:
            raise ShopError("Der Theme-Pack-Katalog hat eine unerlaubte Adresse.")
        return
    prefix = f"/{REPOSITORY}/main/NEXLORI/themes/packs/"
    filename = parts.path[len(prefix):] if parts.path.startswith(prefix) else ""
    if not filename.endswith(".nxthemepack") or not _NAME_RE.fullmatch(filename[:-len(".nxthemepack")]):
        raise ShopError("Die Theme-Pack-Datei hat eine unerlaubte Adresse.")


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl, catalog=urlsplit(newurl).path == PACK_CATALOG_PATH)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_pack_catalog(raw: bytes | str) -> tuple[list[ThemePackInfo], int]:
    if isinstance(raw, bytes):
        if len(raw) > MAX_PACK_CATALOG_BYTES:
            raise ShopError("Der Theme-Pack-Katalog ist zu groß.")
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ShopError("Der Theme-Pack-Katalog ist nicht gültiges UTF-8.") from exc
    elif len(raw.encode("utf-8")) > MAX_PACK_CATALOG_BYTES:
        raise ShopError("Der Theme-Pack-Katalog ist zu groß.")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ShopError("Der Theme-Pack-Katalog enthält ungültiges JSON.") from exc
    if not isinstance(data, dict) or data.get("format") != 1 or not isinstance(data.get("packs"), list):
        raise ShopError("Der Theme-Pack-Katalog hat ein ungültiges Format.")
    parsed: list[ThemePackInfo] = []
    seen: set[str] = set()
    skipped = 0
    for entry in data["packs"][:MAX_PACKS]:
        try:
            if not isinstance(entry, dict):
                raise ValueError("kein Objekt")
            name = entry.get("name")
            if not isinstance(name, str) or not _NAME_RE.fullmatch(name) or name in seen:
                raise ValueError("ungültiger oder doppelter Name")
            label = _text(entry.get("label"), limit=60)
            description = _text(entry.get("description", ""), limit=160, default="Kein Beschreibungstext.")
            url = entry.get("url")
            expected_url = PACK_BASE_URL + name + ".nxthemepack"
            if not label or not isinstance(url, str) or url != expected_url:
                raise ValueError("ungültige Metadaten oder Adresse")
            _check_url(url)
            parsed.append(ThemePackInfo(name, label, description or "Kein Beschreibungstext.", url))
            seen.add(name)
        except (ValueError, ShopError):
            skipped += 1
    skipped += max(0, len(data["packs"]) - MAX_PACKS)
    return parsed, skipped


def _read_url(
    url: str,
    *,
    max_bytes: int,
    timeout: float,
    opener: Callable[..., Any] | None,
    catalog: bool = False,
) -> bytes:
    _check_url(url, catalog=catalog)
    request = urllib.request.Request(
        url, headers={"User-Agent": "Nexlori-ThemePacks", "Accept": "application/json"}
    )
    open_url = opener or urllib.request.build_opener(_SafeRedirects()).open
    try:
        with open_url(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ShopError("Theme-Pack oder Katalog wurde nicht gefunden.") from exc
        raise ShopError(f"GitHub hat den Theme-Pack-Download mit HTTP {exc.code} abgelehnt.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ShopError("Der Theme-Pack-Server ist nicht erreichbar. Prüfe deine Internetverbindung.") from exc
    if len(raw) > max_bytes:
        raise ShopError("Die angeforderte Theme-Pack-Datei ist zu groß.")
    return raw


def fetch_pack_catalog(
    url: str = PACK_CATALOG_URL,
    timeout: float = 8.0,
    opener: Callable[..., Any] | None = None,
) -> tuple[list[ThemePackInfo], int]:
    raw = _read_url(url, max_bytes=MAX_PACK_CATALOG_BYTES, timeout=timeout, opener=opener, catalog=True)
    return parse_pack_catalog(raw)


def parse_theme_pack(raw: bytes | str) -> ThemePack:
    if isinstance(raw, bytes):
        if len(raw) > MAX_PACK_BYTES:
            raise ShopError("Das Theme-Pack ist zu groß.")
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ShopError("Das Theme-Pack ist nicht gültiges UTF-8.") from exc
    elif len(raw.encode("utf-8")) > MAX_PACK_BYTES:
        raise ShopError("Das Theme-Pack ist zu groß.")
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ShopError("Das Theme-Pack enthält ungültiges JSON.") from exc
    if not isinstance(data, dict) or data.get("format") != 1:
        raise ShopError("Das Theme-Pack hat ein ungültiges Format.")
    name = data.get("name")
    label = _text(data.get("label"), limit=60)
    description = _text(data.get("description", ""), limit=160, default="Kein Beschreibungstext.")
    entries = data.get("themes")
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name) or not label:
        raise ShopError("Name oder Titel des Theme-Packs ist ungültig.")
    if not isinstance(entries, list) or not entries or len(entries) > MAX_PACK_THEMES:
        raise ShopError(f"Ein Theme-Pack muss zwischen 1 und {MAX_PACK_THEMES} Themes enthalten.")
    parsed: list[ShopTheme] = []
    seen: set[str] = set()
    for entry in entries:
        try:
            item = parse_shop_theme(entry)
        except (ValueError, TypeError, KeyError) as exc:
            raise ShopError(f"Ein Theme im Pack ist ungültig: {exc}") from exc
        if item.name in seen:
            raise ShopError(f"Das Theme „{item.name}“ steht doppelt im Pack.")
        parsed.append(item)
        seen.add(item.name)
    return ThemePack(name, label, description or "Kein Beschreibungstext.", tuple(parsed))


def fetch_theme_pack(
    info: ThemePackInfo,
    timeout: float = 10.0,
    opener: Callable[..., Any] | None = None,
) -> ThemePack:
    expected = PACK_BASE_URL + info.name + ".nxthemepack"
    if info.url != expected:
        raise ShopError("Die Adresse des Theme-Packs stimmt nicht mit seinem Katalogeintrag überein.")
    raw = _read_url(info.url, max_bytes=MAX_PACK_BYTES, timeout=timeout, opener=opener)
    pack = parse_theme_pack(raw)
    if pack.name != info.name:
        raise ShopError("Der Inhalt des Theme-Packs stimmt nicht mit dem Katalogeintrag überein.")
    return pack


def serialize_theme_pack(name: str, label: str, description: str, themes: list[ShopTheme]) -> str:
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ShopError("Der Packname darf nur Kleinbuchstaben, Zahlen und Bindestriche enthalten.")
    if not _text(label, limit=60) or not isinstance(description, str) or (description and not _TEXT_RE.fullmatch(description.strip())):
        raise ShopError("Packtitel oder Beschreibung enthält ungültige Zeichen.")
    if not themes or len(themes) > MAX_PACK_THEMES:
        raise ShopError(f"Es müssen zwischen 1 und {MAX_PACK_THEMES} Themes exportiert werden.")
    entries = []
    seen: set[str] = set()
    for item in themes:
        if not isinstance(item, ShopTheme) or item.name in seen:
            raise ShopError("Die Theme-Liste ist ungültig oder enthält doppelte Namen.")
        entries.append({
            **item.theme.to_dict(),
            "category": item.category, "author": item.author, "rev": item.rev, "description": item.description,
        })
        seen.add(item.name)
    raw = json.dumps(
        {"format": 1, "name": name, "label": label.strip(), "description": description.strip(), "themes": entries},
        indent=2, ensure_ascii=False,
    )
    parse_theme_pack(raw)
    return raw + "\n"
