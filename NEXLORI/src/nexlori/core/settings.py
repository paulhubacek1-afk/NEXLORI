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
from .themes import BUILTIN_THEMES


@dataclass
class Settings:
    theme: str = "dunkel"
    theme_mix: list[str] = field(default_factory=list)  # bis zu drei zusätzliche Themes zur Basis
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
    search_url: str = "https://html.duckduckgo.com/html/?q={}"  # {} wird durch die Suchanfrage ersetzt
    page_zoom: float = 1.0  # zusätzlich zur Bildschirmskalierung
    adapt_page_theme: bool = True  # injiziert eine optionale, lokale Nutzer-Stylesheet in Websites
    pride_favorites: list[str] = field(default_factory=lambda: ["pride-gay", "pride-trans", "pride-regenbogen"])
    toolbar_search_width: int = 560
    toolbar_icon_size: int = 18
    toolbar_visible_icons: list[str] = field(
        default_factory=lambda: ["home", "bookmark", "spotify", "page_theme", "theme"]
    )
    auto_update_check: bool = True
    ubol_enabled: bool = True
    allow_web_popups: bool = False
    extensions_enabled: dict[str, bool] = field(default_factory=lambda: {"ublock-origin-lite": True})

    def problems(self) -> list[str]:
        out = []
        if self.theme not in BUILTIN_THEMES:
            out.append(f"theme: unbekannt ({self.theme!r})")
        if not isinstance(self.theme_mix, list) or len(self.theme_mix) > 3:
            out.append("theme_mix: höchstens drei zusätzliche Themes erwartet")
        elif (
            any(not isinstance(name, str) or name not in BUILTIN_THEMES or name == self.theme for name in self.theme_mix)
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
        valid_icons = {"home", "bookmark", "spotify", "page_theme", "theme"}
        if (
            not isinstance(self.toolbar_visible_icons, list)
            or len(set(self.toolbar_visible_icons)) != len(self.toolbar_visible_icons)
            or any(icon not in valid_icons for icon in self.toolbar_visible_icons)
        ):
            out.append("toolbar_visible_icons: ungültige oder doppelte Icons")
        for field_name in ("auto_update_check", "ubol_enabled", "allow_web_popups"):
            if not isinstance(getattr(self, field_name), bool):
                out.append(f"{field_name}: true oder false erwartet")
        if (
            not isinstance(self.extensions_enabled, dict)
            or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in self.extensions_enabled.items())
        ):
            out.append("extensions_enabled: erwartet wird ein Wörterbuch aus Add-on-Namen und booleschem Status")
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        settings = cls(**{k: v for k, v in data.items() if k in known})  # unbekannte Schlüssel ignorieren
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
