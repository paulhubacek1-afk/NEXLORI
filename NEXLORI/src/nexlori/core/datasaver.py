"""Datensparmodus: Anfragen-Filter und ehrliche Einsparungs-Buchführung.

Es werden ausschließlich GEMESSENE Bytes als Einsparung ausgewiesen. Ist die Größe einer
blockierten Anfrage unbekannt, wird sie gezählt, aber nicht in Bytes eingerechnet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlsplit


class SaverLevel(str, Enum):
    OFF = "off"
    NORMAL = "normal"
    STRICT = "strict"


class ResourceType(str, Enum):
    DOCUMENT = "document"
    SCRIPT = "script"
    STYLESHEET = "stylesheet"
    IMAGE = "image"
    MEDIA = "media"
    FONT = "font"
    XHR = "xhr"
    PREFETCH = "prefetch"
    OTHER = "other"


class Action(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    DEGRADE = "degrade"  # z. B. Bild in niedrigerer Qualität laden


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


# Kleine Beispiel-Liste bekannter Tracking-/Werbe-Domains. Nicht vollständig; später austauschbar.
TRACKER_DOMAINS = frozenset({
    "google-analytics.com", "googletagmanager.com", "doubleclick.net", "googlesyndication.com",
    "adservice.google.com", "connect.facebook.net", "facebook.net", "hotjar.com",
    "scorecardresearch.com", "criteo.com", "taboola.com", "outbrain.com", "adnxs.com",
    "amazon-adsystem.com", "quantserve.com",
})
_TWO_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu"}


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def site_of(host: str) -> str:
    """Näherung an 'registrierbare Domain' (ohne Public-Suffix-Liste; siehe docs)."""
    parts = host.split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in _TWO_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def is_tracker(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in TRACKER_DOMAINS)


@dataclass
class DataSaver:
    level: SaverLevel = SaverLevel.NORMAL
    block_trackers: bool = True
    autoplay_allowed: bool = False
    site_allowlist: set[str] = field(default_factory=set)  # Seiten (Hostnamen), für die nichts gefiltert wird

    def decide(self, url: str, rtype: ResourceType, page_url: str, *, autoplay: bool = False) -> Decision:
        host, page_host = host_of(url), host_of(page_url)
        if self.level is SaverLevel.OFF:
            return Decision(Action.ALLOW, "Datensparmodus aus")
        if site_of(page_host) in {site_of(h) for h in self.site_allowlist} or page_host in self.site_allowlist:
            return Decision(Action.ALLOW, "Seite steht auf der Ausnahmeliste")
        third_party = site_of(host) != site_of(page_host)
        if third_party and self.block_trackers and is_tracker(host):
            return Decision(Action.BLOCK, "Tracker")
        if rtype is ResourceType.PREFETCH and (self.level is SaverLevel.STRICT or third_party):
            return Decision(Action.BLOCK, "Vorabladen")
        if rtype is ResourceType.MEDIA and autoplay and not self.autoplay_allowed:
            return Decision(Action.BLOCK, "Automatische Wiedergabe")
        if self.level is SaverLevel.STRICT:
            if rtype is ResourceType.IMAGE:
                return Decision(Action.DEGRADE, "Niedrigere Bildqualität")
            if third_party and rtype in (ResourceType.SCRIPT, ResourceType.FONT, ResourceType.XHR):
                return Decision(Action.BLOCK, "Drittanbieter (strikt)")
        return Decision(Action.ALLOW, "")


@dataclass
class SavingsLedger:
    blocked_requests: int = 0
    measured_bytes: int = 0
    unmeasured_requests: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)

    def record(self, decision: Decision, size_bytes: int | None) -> None:
        if decision.action is Action.ALLOW:
            return
        self.blocked_requests += 1
        self.by_reason[decision.reason] = self.by_reason.get(decision.reason, 0) + 1
        if size_bytes is None:
            self.unmeasured_requests += 1
        else:
            self.measured_bytes += max(0, size_bytes)

    def summary(self) -> str:
        text = f"{self.blocked_requests} Anfragen eingeschränkt, {self.measured_bytes / 1024:.1f} KB gemessen eingespart"
        if self.unmeasured_requests:
            text += f"; bei {self.unmeasured_requests} Anfragen war die Größe unbekannt (nicht eingerechnet)"
        return text
