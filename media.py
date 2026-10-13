"""Musik-Popup und Mediensteuerung (Modell + Steuerlogik, noch ohne Oberfläche).

Gesteuert werden nur Quellen, die eine Steuerschnittstelle anbieten (z. B. Media Session API
eines Tabs). Es werden keine Musikdienste nachgeahmt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")
SIZES = ("small", "medium", "large")


class MediaSource(Protocol):
    def play(self) -> None: ...
    def pause(self) -> None: ...
    def next_track(self) -> None: ...
    def previous_track(self) -> None: ...


@dataclass
class MediaSession:
    tab_id: int
    source_name: str
    title: str = ""
    artist: str = ""
    playing: bool = False


@dataclass
class PopupConfig:
    enabled: bool = True
    visible: bool = True
    corner: str = "bottom-right"
    position: tuple[int, int] | None = None  # freie Position (x, y); überstimmt corner
    size: str = "small"
    notify_on_track_change: bool = False

    def __post_init__(self) -> None:
        if self.corner not in CORNERS:
            raise ValueError(f"corner muss eines von {CORNERS} sein")
        if self.size not in SIZES:
            raise ValueError(f"size muss eines von {SIZES} sein")


@dataclass
class MediaController:
    popup: PopupConfig = field(default_factory=PopupConfig)
    _sessions: dict[int, tuple[MediaSession, MediaSource]] = field(default_factory=dict)
    _active: int | None = None

    def register(self, session: MediaSession, source: MediaSource | None) -> None:
        if source is None:
            raise ValueError("Quelle bietet keine Steuerschnittstelle – sie wird nicht gesteuert")
        self._sessions[session.tab_id] = (session, source)
        self._active = session.tab_id

    def unregister(self, tab_id: int) -> None:
        self._sessions.pop(tab_id, None)
        if self._active == tab_id:
            playing = [s.tab_id for s, _ in self._sessions.values() if s.playing]
            self._active = playing[-1] if playing else next(iter(self._sessions), None)

    @property
    def active(self) -> MediaSession | None:
        return self._sessions[self._active][0] if self._active in self._sessions else None

    @property
    def popup_visible(self) -> bool:
        return self.popup.enabled and self.popup.visible and self.active is not None

    def _call(self, name: str) -> bool:
        if self._active not in self._sessions:
            return False
        getattr(self._sessions[self._active][1], name)()
        return True

    def toggle_play(self) -> bool:
        session = self.active
        if session is None:
            return False
        self._call("pause" if session.playing else "play")
        session.playing = not session.playing
        return True

    def next(self) -> bool:
        return self._call("next_track")

    def previous(self) -> bool:
        return self._call("previous_track")

    def update_track(self, tab_id: int, title: str, artist: str = "") -> str | None:
        """Aktualisiert Titel/Künstler. Gibt Benachrichtigungstext zurück, falls gewünscht."""
        entry = self._sessions.get(tab_id)
        if entry is None:
            return None
        session = entry[0]
        changed = title != session.title
        session.title, session.artist = title, artist
        if changed and title and self.popup.enabled and self.popup.notify_on_track_change:
            return f"{title} – {artist}" if artist else title
        return None
