"""Datenschutz-Helfer für die eingebauten Nexlori-Add-ons (rein logisch, ohne Qt).

- ``strip_tracking_params``: entfernt bekannte Tracking-Parameter (utm_*, fbclid, gclid …) aus Links.
- ``upgrade_to_https``: wandelt http:// in https:// um (außer für lokale/interne Adressen).
- ``tabs_to_sleep``: wählt Tabs aus, die lange nicht benutzt wurden und Speicher freigeben dürfen.
"""
from __future__ import annotations

import ipaddress
from typing import Collection, Hashable, Mapping, TypeVar
from urllib.parse import unquote_plus, urlsplit, urlunsplit

TRACKING_PARAMS = frozenset({
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid", "msclkid", "yclid", "twclid", "ttclid",
    "igshid", "mc_cid", "mc_eid", "_ga", "_gl", "mkt_tok", "vero_id", "oly_anon_id", "oly_enc_id",
    "ref_src", "ref_url", "s_cid", "spm", "_hsenc", "_hsmi", "hsctatracking", "wickedid", "li_fat_id",
})
TRACKING_PREFIXES = ("utm_", "mtm_", "pk_", "piwik_")


def strip_tracking_params(url: str) -> str:
    """Entfernt Tracking-Parameter. Alle anderen Parameter bleiben unverändert (inkl. Reihenfolge)."""
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.query:
        return url
    kept: list[str] = []
    removed = False
    for pair in parts.query.split("&"):
        key = unquote_plus(pair.split("=", 1)[0]).lower()
        if key in TRACKING_PARAMS or key.startswith(TRACKING_PREFIXES):
            removed = True
            continue
        kept.append(pair)
    if not removed:
        return url
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(kept), parts.fragment))


def is_local_host(host: str) -> bool:
    """Lokale, private oder interne Hosts, für die kein HTTPS-Zwang gilt."""
    host = host.strip("[]").lower().rstrip(".")
    if not host or "." not in host and ":" not in host:
        return True  # localhost, Intranet-Namen ohne Punkt
    if host.endswith((".local", ".localhost", ".lan", ".internal", ".home.arpa")):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def upgrade_to_https(url: str) -> str | None:
    """https-Variante einer http-Adresse oder None, wenn nicht sinnvoll umgestellt werden kann."""
    parts = urlsplit(url)
    if parts.scheme.lower() != "http" or "@" in parts.netloc:
        return None
    host = parts.hostname or ""
    if not host or is_local_host(host):
        return None
    if parts.port not in (None, 80):
        return None  # https auf einem Sonderport ist nicht dasselbe Angebot
    netloc = f"[{host}]" if ":" in host else host
    return urlunsplit(("https", netloc, parts.path, parts.query, parts.fragment))


K = TypeVar("K", bound=Hashable)


def tabs_to_sleep(
    last_active: Mapping[K, float], now: float, minutes: int, exclude: Collection[K] = ()
) -> list[K]:
    """Tabs, die seit mindestens ``minutes`` Minuten nicht mehr aktiv waren (ohne ``exclude``)."""
    limit = max(1, int(minutes)) * 60
    skip = set(exclude)
    return [key for key, seen in last_active.items() if key not in skip and now - seen >= limit]
