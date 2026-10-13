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

    def problems(self) -> list[str]:
        out = []
        if self.theme not in BUILTIN_THEMES:
            out.append(f"theme: unbekannt ({self.theme!r})")
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
