"""Tab-Verwaltung mit Ruhezustands-Richtlinie und ehrlichem Ressourcenbericht.

Die Messwerte (RAM/CPU) liefert später die Engine. Bis dahin sind sie optional;
der Bericht weist nicht gemessene Tabs ausdrücklich als solche aus.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .modes import PerformanceProfile


@dataclass
class Tab:
    id: int
    url: str
    last_active: float
    memory_mb: float | None = None
    cpu_percent: float | None = None
    audible: bool = False
    pinned: bool = False
    suspended: bool = False


@dataclass
class ResourceReport:
    measured: list[Tab] = field(default_factory=list)  # absteigend nach RAM
    unmeasured: list[Tab] = field(default_factory=list)

    @property
    def total_memory_mb(self) -> float:
        return sum(t.memory_mb or 0.0 for t in self.measured)


class TabManager:
    def __init__(self) -> None:
        self.tabs: dict[int, Tab] = {}
        self.active_id: int | None = None
        self._next_id = 1

    def open(self, url: str, now: float, activate: bool = True) -> Tab:
        tab = Tab(self._next_id, url, now)
        self._next_id += 1
        self.tabs[tab.id] = tab
        if activate or self.active_id is None:
            self.activate(tab.id, now)
        return tab

    def close(self, tab_id: int) -> None:
        self.tabs.pop(tab_id, None)
        if self.active_id == tab_id:
            self.active_id = next(iter(self.tabs), None)

    def activate(self, tab_id: int, now: float) -> Tab:
        tab = self.tabs[tab_id]
        if self.active_id is not None and self.active_id in self.tabs:
            self.tabs[self.active_id].last_active = now
        tab.suspended = False  # aufwecken
        tab.last_active = now
        self.active_id = tab_id
        return tab

    def update_measurements(self, tab_id: int, memory_mb: float | None, cpu_percent: float | None) -> None:
        tab = self.tabs[tab_id]
        tab.memory_mb, tab.cpu_percent = memory_mb, cpu_percent

    def plan_suspend(self, now: float, sleep_after_s: int | None) -> list[Tab]:
        """Tabs, die schlafen gelegt werden dürfen: inaktiv, nicht angeheftet, ohne Ton."""
        if sleep_after_s is None:
            return []
        return [
            t for t in self.tabs.values()
            if t.id != self.active_id and not t.pinned and not t.audible and not t.suspended
            and now - t.last_active >= sleep_after_s
        ]

    def apply_policy(self, now: float, profile: PerformanceProfile) -> list[int]:
        ids = []
        for tab in self.plan_suspend(now, profile.tab_sleep_after_s):
            tab.suspended = True
            tab.memory_mb, tab.cpu_percent = None, None  # Ruhende Tabs: Messung veraltet
            ids.append(tab.id)
        return ids

    def resource_report(self) -> ResourceReport:
        report = ResourceReport()
        for tab in self.tabs.values():
            (report.measured if tab.memory_mb is not None or tab.cpu_percent is not None else report.unmeasured).append(tab)
        report.measured.sort(key=lambda t: (t.memory_mb or 0.0, t.cpu_percent or 0.0), reverse=True)
        return report
