"""Freiwillige, rein lokale Gaming-Erkennung.

Datenschutz: Standardmäßig AUS. Solange sie aus ist, wird die Prozessliste nicht einmal gelesen.
Es gibt keinen Netzwerkzugriff; Ergebnisse verlassen das Gerät nicht. Die Prozessquelle ist
austauschbar (Betriebssystem-spezifisch), Polling steuert der Aufrufer (keine versteckten Threads).
"""
from __future__ import annotations

from typing import Callable, Iterable

# Beispiele, bewusst klein und vom Nutzer erweiterbar (Einstellungen: custom_games).
EXAMPLE_GAME_PROCESSES = frozenset({
    "cs2.exe", "gta5.exe", "eldenring.exe", "rocketleague.exe",
    "fortniteclient-win64-shipping.exe", "valorant-win64-shipping.exe", "league of legends.exe",
})


def psutil_process_source() -> Callable[[], Iterable[str]]:
    """Prozessnamen via psutil (optional). Ohne psutil: leere Liste = keine Erkennung."""
    try:
        import psutil
    except ImportError:
        return lambda: []

    def source() -> Iterable[str]:
        return [p.info["name"] for p in psutil.process_iter(["name"]) if p.info.get("name")]

    return source


class GamingDetector:
    def __init__(
        self,
        process_source: Callable[[], Iterable[str]] | None = None,
        game_names: Iterable[str] = EXAMPLE_GAME_PROCESSES,
        *,
        enabled: bool = False,
        enter_after: int = 2,
        exit_after: int = 3,
    ):
        self._source = process_source or psutil_process_source()
        self.game_names = {n.lower() for n in game_names}
        self._enabled = enabled
        self.enter_after, self.exit_after = enter_after, exit_after
        self.active = False
        self._hits = 0
        self._misses = 0
        self._listeners: list[Callable[[bool], None]] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    def subscribe(self, callback: Callable[[bool], None]) -> None:
        self._listeners.append(callback)

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False
        self._reset(notify=True)

    def _reset(self, notify: bool) -> None:
        was_active = self.active
        self.active, self._hits, self._misses = False, 0, 0
        if notify and was_active:
            self._emit()

    def _emit(self) -> None:
        for cb in list(self._listeners):
            cb(self.active)

    def poll(self) -> bool:
        """Einmal prüfen. Mit Hysterese, damit kurzes Flackern keinen Moduswechsel auslöst."""
        if not self._enabled:
            return False
        running = {str(n).lower() for n in self._source()}
        if running & self.game_names:
            self._hits, self._misses = self._hits + 1, 0
            if not self.active and self._hits >= self.enter_after:
                self.active = True
                self._emit()
        else:
            self._misses, self._hits = self._misses + 1, 0
            if self.active and self._misses >= self.exit_after:
                self.active = False
                self._emit()
        return self.active
