import json
import urllib.error
from pathlib import Path

import pytest

from nexlori.core import theme_shop
from nexlori.core.settings import Settings
from nexlori.core.theme_shop import (
    ShopError, ThemeStore, fetch_catalog, parse_catalog, parse_shop_theme,
)
from nexlori.core.themes import (
    BUILTIN_THEMES, _INSTALLED_THEMES, all_themes, combine_themes, get_theme, is_known_theme,
)

CATALOG_FILE = Path(__file__).resolve().parent.parent / "themes" / "catalog.json"


def entry(**overrides):
    data = {
        "name": "test-theme", "label": "Testtheme", "category": "Dunkel", "author": "Tester", "rev": 1,
        "bg": "#101010", "surface": "#202020", "fg": "#F0F0F0", "accent": "#66CCFF",
        "stripes": ["#66CCFF", "#FF66CC"],
    }
    data.update(overrides)
    return data


def catalog_bytes(*entries):
    return json.dumps({"format": 1, "themes": list(entries)}).encode("utf-8")


@pytest.fixture(autouse=True)
def clean_registry():
    _INSTALLED_THEMES.clear()
    yield
    _INSTALLED_THEMES.clear()


# ------------------------------------------------------------------ Katalogdatei im Repository
def test_repository_catalog_is_valid():
    themes, skipped = parse_catalog(CATALOG_FILE.read_bytes())
    assert skipped == 0
    assert len(themes) >= 40
    names = [t.name for t in themes]
    assert len(names) == len(set(names))
    assert not set(names) & set(BUILTIN_THEMES)


# ------------------------------------------------------------------ Einträge prüfen
def test_valid_entry_is_parsed():
    item = parse_shop_theme(entry())
    assert item.name == "test-theme" and item.category == "Dunkel" and item.theme.accent == "#66CCFF"


@pytest.mark.parametrize("bad", [
    entry(name="dunkel"),                       # überschreibt eingebautes Theme
    entry(name="../evil"),                      # Pfadtrick
    entry(name="Gross"),                        # nur a-z0-9-
    entry(name="x" * 41),                       # zu lang
    entry(bg="red"),                            # keine Hex-Farbe
    entry(accent="#12345"),                     # zu kurz
    entry(stripes=["#000000"] * 13),            # zu viele Streifen
    entry(stripes=["nicht-hex"]),
    entry(fg="#777777", bg="#808080"),          # Kontrast zu gering
    "kein objekt",
])
def test_invalid_entries_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_shop_theme(bad)


def test_missing_color_is_rejected():
    data = entry()
    del data["surface"]
    with pytest.raises(ValueError):
        parse_shop_theme(data)


def test_odd_metadata_falls_back_to_safe_defaults():
    item = parse_shop_theme(entry(category="<script>", author="<b>x</b>", rev=-5, label="Hallo\x00Welt"))
    assert item.category == "Sonstige" and item.author == "Unbekannt" and item.rev == 1
    assert item.theme.label == item.name  # Steuerzeichen im Label -> Name als Ersatz


def test_catalog_skips_invalid_and_duplicates():
    raw = catalog_bytes(entry(), entry(name="zwei"), entry(name="dunkel"), entry(), {"x": 1})
    themes, skipped = parse_catalog(raw)
    assert [t.name for t in themes] == ["test-theme", "zwei"]
    assert skipped == 3


@pytest.mark.parametrize("raw", [b"{kaputt", b'{"format": 2, "themes": []}', b'{"format": 1}', b"[]"])
def test_broken_catalog_raises(raw):
    with pytest.raises(ShopError):
        parse_catalog(raw)


def test_oversized_catalog_raises():
    with pytest.raises(ShopError):
        parse_catalog(b" " * (theme_shop.MAX_CATALOG_BYTES + 1))


# ------------------------------------------------------------------ Netzwerk (ohne echte Verbindung)
class FakeResponse:
    def __init__(self, data: bytes):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, limit=-1):
        return self.data if limit < 0 else self.data[:limit]


def test_fetch_uses_only_https_github_hosts():
    for url in ("http://raw.githubusercontent.com/x/catalog.json", "https://evil.example/catalog.json",
                "file:///etc/passwd", "https://raw.githubusercontent.com.evil.example/x"):
        with pytest.raises(ShopError):
            fetch_catalog(url, opener=lambda *a, **k: FakeResponse(b""))


def test_fetch_returns_themes():
    themes, skipped = fetch_catalog(opener=lambda *a, **k: FakeResponse(catalog_bytes(entry())))
    assert [t.name for t in themes] == ["test-theme"] and skipped == 0


def test_fetch_reports_problems_in_plain_german():
    def not_found(*a, **k):
        raise urllib.error.HTTPError("u", 404, "nf", {}, None)

    def offline(*a, **k):
        raise urllib.error.URLError("kein Netz")

    with pytest.raises(ShopError, match="nicht gefunden"):
        fetch_catalog(opener=not_found)
    with pytest.raises(ShopError, match="nicht erreichbar"):
        fetch_catalog(opener=offline)
    with pytest.raises(ShopError, match="zu groß"):
        fetch_catalog(opener=lambda *a, **k: FakeResponse(b" " * (theme_shop.MAX_CATALOG_BYTES + 10)))


def test_redirects_to_other_hosts_are_blocked():
    handler = theme_shop._SafeRedirects()
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example/catalog.json")
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(None, None, 302, "Found", {}, "http://raw.githubusercontent.com/x")


# ------------------------------------------------------------------ Lokaler Speicher
def test_install_remove_roundtrip(tmp_path):
    store = ThemeStore(tmp_path / "themes")
    item = parse_shop_theme(entry())
    assert not is_known_theme("test-theme")
    store.install(item)
    assert (tmp_path / "themes" / "test-theme.json").is_file()
    assert is_known_theme("test-theme") and get_theme("test-theme") == item.theme
    assert "test-theme" in all_themes()
    assert store.installed()["test-theme"][1] == 1
    assert store.remove("test-theme") is True
    assert not is_known_theme("test-theme") and store.installed() == {}
    assert store.remove("test-theme") is False


def test_install_overwrites_older_revision(tmp_path):
    store = ThemeStore(tmp_path)
    store.install(parse_shop_theme(entry(rev=1)))
    store.install(parse_shop_theme(entry(rev=2, accent="#FFCC00")))
    theme, rev = store.installed()["test-theme"]
    assert rev == 2 and theme.accent == "#FFCC00"


def test_load_into_registry_after_restart(tmp_path):
    ThemeStore(tmp_path).install(parse_shop_theme(entry()))
    _INSTALLED_THEMES.clear()  # simuliert einen Neustart
    assert ThemeStore(tmp_path).load_into_registry() == ["test-theme"]
    assert is_known_theme("test-theme")
    assert combine_themes(["dunkel", "test-theme"]).stripes[-1] == "#FF66CC"


def test_tampered_or_broken_files_are_ignored(tmp_path):
    store = ThemeStore(tmp_path)
    store.install(parse_shop_theme(entry()))
    (tmp_path / "kaputt.json").write_text("{nope", encoding="utf-8")
    (tmp_path / "falscher-name.json").write_text(
        json.dumps({"format": 1, "theme": entry(name="anderer-name")}), encoding="utf-8")
    (tmp_path / "dunkel.json").write_text(json.dumps({"format": 1, "theme": entry(name="dunkel")}), encoding="utf-8")
    (tmp_path / "riesig.json").write_text(" " * (theme_shop.MAX_THEME_FILE_BYTES + 1), encoding="utf-8")
    assert list(store.installed()) == ["test-theme"]


def test_store_refuses_dangerous_names(tmp_path):
    store = ThemeStore(tmp_path)
    for name in ("../evil", "a/b", "", "UPPER", "x" * 50):
        with pytest.raises(ShopError):
            store.remove(name)


def test_builtin_themes_cannot_be_shadowed():
    from nexlori.core.themes import register_installed_theme
    with pytest.raises(ValueError):
        register_installed_theme(BUILTIN_THEMES["dunkel"])


# ------------------------------------------------------------------ Einstellungen mit Shop-Themes
def test_settings_accept_installed_theme_and_lenient_load_repairs_missing(tmp_path):
    ThemeStore(tmp_path / "themes").install(parse_shop_theme(entry()))
    settings = Settings(theme="test-theme")
    assert settings.problems() == []
    path = tmp_path / "settings.json"
    settings.save(path)
    assert Settings.load_lenient(path).theme == "test-theme"
    _INSTALLED_THEMES.clear()  # Theme wurde zwischenzeitlich entfernt
    with pytest.raises(ValueError):
        Settings.load(path)
    repaired = Settings.load_lenient(path)
    assert repaired.theme == "dunkel"


def test_lenient_load_keeps_other_settings(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "weg", "theme_mix": ["weg", "nord-gibt-es-nicht"], "page_zoom": 1.5}),
                    encoding="utf-8")
    loaded = Settings.load_lenient(path)
    assert loaded.theme == "dunkel" and loaded.theme_mix == [] and loaded.page_zoom == 1.5
