"""Einstellungen mit datenschutzfreundlichen Voreinstellungen. Es gibt bewusst kein Telemetrie-Feld."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .datasaver import SaverLevel
from .media import CORNERS, SIZES
from .modes import Mode
from .builtin_addons import ADDON_IDS, default_states
from .themes import BUILTIN_THEMES, is_known_theme
from .adblock import FILTER_LIST_IDS, normalize_host

TOOLBAR_ICONS = ("home", "bookmark", "shield", "spotify", "page_theme", "theme")


DEFAULT_SEARCH_URL = "https://duckduckgo.com/?q={}"


def canonical_search_url(template: str) -> str:
    """Normalize legacy search templates so all Nexlori search fields use one provider URL."""
    value = template.strip() if isinstance(template, str) else DEFAULT_SEARCH_URL
    return DEFAULT_SEARCH_URL if value == "https://html.duckduckgo.com/html/?q={}" else value


@dataclass
class Settings:
    theme: str = "dunkel"
    theme_mix: list[str] = field(default_factory=list)  # bis zu sieben zusätzliche Themes zur Basis
    mode: str = Mode.NORMAL.value
    saver_level: str = SaverLevel.NORMAL.value
    block_trackers: bool = True
    autoplay: str = "block"  # "block" | "allow"
    gaming_detection: bool = False  # freiwillig: standardmäßig AUS
    gaming_auto_switch: bool = False
    gaming_auto_restore: bool = True
    custom_games: list[str] = field(default_factory=list)
    popup_enabled: bool = True
    popup_corner: str = "bottom-right"
    popup_size: str = "small"
    notify_track_change: bool = False
    site_allowlist: list[str] = field(default_factory=list)
    search_url: str = DEFAULT_SEARCH_URL  # {} wird durch die Suchanfrage ersetzt
    page_zoom: float = 1.0  # zusätzlich zur Bildschirmskalierung
    adapt_page_theme: bool = False  # standardmäßig kein CSS-Eingriff in fremde Websites
    pride_favorites: list[str] = field(default_factory=lambda: ["pride-gay", "pride-trans", "pride-regenbogen"])
    toolbar_search_width: int = 560
    toolbar_icon_size: int = 18
    toolbar_visible_icons: list[str] = field(
        default_factory=lambda: ["home", "bookmark", "shield", "spotify", "page_theme", "theme"]
    )
    auto_update_check: bool = True
    auto_update_install: bool = True  # geprüfte Updates im Hintergrund laden und beim Beenden installieren
    adblock_enabled: bool = True  # Nexlori Shield: eingebauter Werbe- und Trackerblocker
    adblock_cosmetic: bool = True  # Werbeflächen per CSS ausblenden, YouTube-Werbung überspringen
    adblock_allowlist: list[str] = field(default_factory=list)  # Websites, auf denen Shield pausiert
    adblock_lists: list[str] = field(default_factory=lambda: ["pgl"])
    memory_saver: bool = True  # entlädt inaktive Tabs, um RAM freizugeben
    ubol_enabled: bool = False
    allow_web_popups: bool = False
    background_on_close: bool = True  # Schließen blendet ins Tray aus; Nexlori bleibt im Hintergrund aktiv
    block_nsfw: bool = True  # lokaler URL-Filter, standardmäßig aktiv
    extensions_enabled: dict[str, bool] = field(default_factory=lambda: {"ublock-origin-lite": False})
    animations: str = "full"  # "full" | "reduced" | "off"
    custom_titlebar: bool = True  # eigene Titelleiste in Theme-Farben (False = Windows-Standardleiste)
    builtin_addons: dict[str, bool] = field(default_factory=default_states)
    tab_sleep_minutes: int = 15

    def problems(self) -> list[str]:
        out = []
        if not is_known_theme(self.theme):
            out.append(f"theme: unbekannt ({self.theme!r})")
        if not isinstance(self.theme_mix, list) or len(self.theme_mix) > 7:
            out.append("theme_mix: höchstens sieben zusätzliche Themes erwartet")
        elif (
            any(not is_known_theme(name) or name == self.theme for name in self.theme_mix)
            or len([name for name in self.theme_mix if isinstance(name, str)])
            != len(set(name for name in self.theme_mix if isinstance(name, str)))
        ):
            out.append("theme_mix: nur eindeutige, vorhandene Themes zusätzlich zur Basis erlaubt")

        if self.mode not in {m.value for m in Mode}:
            out.append(f"mode: unbekannt ({self.mode!r})")
        if self.saver_level not in {s.value for s in SaverLevel}:
            out.append(f"saver_level: unbekannt ({self.saver_level!r})")
        if self.autoplay not in ("block", "allow"):
            out.append(f"autoplay: 'block' oder 'allow' erwartet ({self.autoplay!r})")
        if self.popup_corner not in CORNERS:
            out.append(f"popup_corner: unbekannt ({self.popup_corner!r})")
        if self.popup_size not in SIZES:
            out.append(f"popup_size: unbekannt ({self.popup_size!r})")
        if not (self.search_url.startswith("https://") and self.search_url.count("{}") == 1):
            out.append("search_url: muss mit https:// beginnen und genau einmal {} enthalten")
        if not isinstance(self.page_zoom, (int, float)) or not 0.5 <= self.page_zoom <= 3.0:
            out.append("page_zoom: zwischen 0.5 und 3.0 erwartet")
        if not isinstance(self.adapt_page_theme, bool):
            out.append("adapt_page_theme: true oder false erwartet")
        if not isinstance(self.pride_favorites, list) or len(self.pride_favorites) > 3:
            out.append("pride_favorites: höchstens drei Theme-Namen erwartet")
        elif any(not isinstance(name, str) or not name.startswith("pride-") or name not in BUILTIN_THEMES for name in self.pride_favorites):
            out.append("pride_favorites: nur vorhandene Pride-Themes sind erlaubt")
        if not isinstance(self.toolbar_search_width, int) or not 360 <= self.toolbar_search_width <= 1000:
            out.append("toolbar_search_width: zwischen 360 und 1000 erwartet")
        if not isinstance(self.toolbar_icon_size, int) or not 14 <= self.toolbar_icon_size <= 30:
            out.append("toolbar_icon_size: zwischen 14 und 30 erwartet")
        valid_icons = set(TOOLBAR_ICONS)
        if (
            not isinstance(self.toolbar_visible_icons, list)
            or len(set(self.toolbar_visible_icons)) != len(self.toolbar_visible_icons)
            or any(icon not in valid_icons for icon in self.toolbar_visible_icons)
        ):
            out.append("toolbar_visible_icons: ungültige oder doppelte Icons")
        for field_name in (
            "auto_update_check", "auto_update_install", "memory_saver", "ubol_enabled", "allow_web_popups",
            "background_on_close", "block_nsfw", "adblock_enabled", "adblock_cosmetic",
        ):
            if not isinstance(getattr(self, field_name), bool):
                out.append(f"{field_name}: true oder false erwartet")
        if (
            not isinstance(self.extensions_enabled, dict)
            or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in self.extensions_enabled.items())
        ):
            out.append("extensions_enabled: erwartet wird ein Wörterbuch aus Add-on-Namen und booleschem Status")
        if (
            not isinstance(self.adblock_allowlist, list)
            or len(self.adblock_allowlist) > 500
            or any(not isinstance(h, str) or not normalize_host(h) or len(h) > 253 for h in self.adblock_allowlist)
        ):
            out.append("adblock_allowlist: erwartet wird eine Liste von Hostnamen")
        if (
            not isinstance(self.adblock_lists, list)
            or any(item not in FILTER_LIST_IDS for item in self.adblock_lists)
            or len(set(self.adblock_lists)) != len(self.adblock_lists)
        ):
            out.append("adblock_lists: nur bekannte, eindeutige Filterlisten erlaubt")
        if self.animations not in ("full", "reduced", "off"):
            out.append(f"animations: 'full', 'reduced' oder 'off' erwartet ({self.animations!r})")
        if not isinstance(self.custom_titlebar, bool):
            out.append("custom_titlebar: true oder false erwartet")
        if (
            not isinstance(self.builtin_addons, dict)
            or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in self.builtin_addons.items())
            or any(key not in ADDON_IDS for key in self.builtin_addons)
        ):
            out.append("builtin_addons: erwartet wird ein Wörterbuch aus bekannten Add-on-IDs und booleschem Status")
        if (
            not isinstance(self.tab_sleep_minutes, int)
            or isinstance(self.tab_sleep_minutes, bool)
            or not 2 <= self.tab_sleep_minutes <= 240
        ):
            out.append("tab_sleep_minutes: zwischen 2 und 240 erwartet")
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}  # unbekannte Schlüssel ignorieren
        # uBlock Origin Lite nutzt eine Chrome-WebExtensions-API, die Qt WebEngine
        # nicht vollständig bereitstellt. Alte Profile daher sicher deaktivieren.
        legacy_ubol_enabled = values.get("ubol_enabled", False)
        if isinstance(legacy_ubol_enabled, bool):
            values["ubol_enabled"] = False
        extension_states = values.get("extensions_enabled")
        if isinstance(extension_states, dict) and all(
            isinstance(state, bool) for state in extension_states.values()
        ):
            extension_states = dict(extension_states)
            extension_states["ublock-origin-lite"] = False
            values["extensions_enabled"] = extension_states
        if isinstance(values.get("builtin_addons"), dict):
            # Neue Add-ons erhalten ihre Standardwerte, unbekannte (z. B. aus einer neueren Version) fallen weg.
            merged = default_states()
            merged.update({k: v for k, v in values["builtin_addons"].items() if k in ADDON_IDS})
            values["builtin_addons"] = merged
        icons = values.get("toolbar_visible_icons")
        if isinstance(icons, list) and "adblock_enabled" not in data and "shield" not in icons:
            # Einstellungen aus Versionen vor 1.4: den neuen Shield-Knopf einmalig einblenden.
            values["toolbar_visible_icons"] = [*icons, "shield"]
        settings = cls(**values)
        problems = settings.problems()
        if problems:
            raise ValueError("; ".join(problems))
        return settings

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        path = Path(path)
        if not path.exists():
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def load_lenient(cls, path: str | Path) -> "Settings":
        """Wie ``load``, aber ein nicht mehr vorhandenes Theme (z. B. aus dem Shop entfernt) setzt nicht alles zurück."""
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Einstellungsdatei ist kein JSON-Objekt")
        if not is_known_theme(data.get("theme", "dunkel")):
            data["theme"] = "dunkel"
        mix = data.get("theme_mix")
        if isinstance(mix, list):
            data["theme_mix"] = list(dict.fromkeys(
                n for n in mix if is_known_theme(n) and n != data.get("theme", "dunkel")
            ))[:7]
        return cls.from_dict(data)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def default_settings_path() -> Path:
    """Windows: %APPDATA%\\Nexlori\\settings.json, sonst ~/.config/nexlori/settings.json."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "Nexlori" / "settings.json"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "nexlori" / "settings.json"
