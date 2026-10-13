"""Leistungsmodi (Normal, Ressourcenschonend, Akku, Gaming) und deren Profile."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class Mode(str, Enum):
    NORMAL = "normal"
    ECO = "eco"  # ressourcenschonender Modus
    BATTERY = "battery"
    GAMING = "gaming"


@dataclass(frozen=True)
class PerformanceProfile:
    animations: bool
    throttle_background: bool  # Hintergrund-Timer/-Aktivität drosseln
    prefetch: bool
    notifications_muted: bool
    autoplay_forced_off: bool  # überstimmt die Autoplay-Einstellung der Nutzerin / des Nutzers
    tab_sleep_after_s: int | None  # None = Tabs nie automatisch schlafen legen


PROFILES: dict[Mode, PerformanceProfile] = {
    Mode.NORMAL: PerformanceProfile(True, False, True, False, False, 30 * 60),
    Mode.ECO: PerformanceProfile(False, True, False, False, True, 5 * 60),
    Mode.BATTERY: PerformanceProfile(False, True, False, False, True, 2 * 60),
    Mode.GAMING: PerformanceProfile(False, True, False, True, True, 60),
}


class ModeController:
    """Verwaltet den Basismodus und – optional – den automatischen Gaming-Modus.

    Der Gaming-Modus überlagert den Basismodus und wird nur aktiviert, wenn
    `gaming_auto_switch` eingeschaltet ist. Danach kehrt er (auf Wunsch) selbständig zurück.
    """

    def __init__(self, base: Mode = Mode.NORMAL, gaming_auto_switch: bool = False, auto_restore: bool = True):
        self.base = base
        self.gaming_auto_switch = gaming_auto_switch
        self.auto_restore = auto_restore
        self._gaming = False
        self._listeners: list[Callable[[Mode], None]] = []

    @property
    def mode(self) -> Mode:
        return Mode.GAMING if self._gaming else self.base

    @property
    def profile(self) -> PerformanceProfile:
        return PROFILES[self.mode]

    def subscribe(self, callback: Callable[[Mode], None]) -> None:
        self._listeners.append(callback)

    def _emit(self, before: Mode) -> None:
        if self.mode != before:
            for cb in list(self._listeners):
                cb(self.mode)

    def set_base(self, mode: Mode) -> None:
        before = self.mode
        self.base = mode
        self._emit(before)

    def on_gaming_change(self, active: bool) -> None:
        before = self.mode
        if active and self.gaming_auto_switch:
            self._gaming = True
        elif not active and self._gaming and self.auto_restore:
            self._gaming = False
        self._emit(before)

    def leave_gaming(self) -> None:
        before = self.mode
        self._gaming = False
        self._emit(before)
