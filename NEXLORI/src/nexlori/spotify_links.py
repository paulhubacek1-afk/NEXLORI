"""Pure Spotify URL normalisation helpers, intentionally independent of Qt."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

_SPOTIFY_TYPES = {"track", "album", "playlist", "episode", "show", "artist"}


def normalize_spotify_url(value: str) -> str:
    value = value.strip()
    if not value:
        return "https://open.spotify.com/"
    if not re.match(r"^https://", value, re.IGNORECASE):
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme.lower() != "https" or (parts.hostname or "").lower() not in {
        "open.spotify.com", "www.open.spotify.com"
    }:
        raise ValueError("Bitte einen gültigen Spotify-Link von https://open.spotify.com einfügen.")
    path = parts.path.rstrip("/")
    segments = [segment for segment in path.split("/") if segment]
    if segments and segments[0] == "embed":
        if len(segments) < 2 or segments[1] not in _SPOTIFY_TYPES:
            raise ValueError("Dieser Spotify-Einbettungstyp wird nicht unterstützt.")
        return f"https://open.spotify.com{path}"
    if len(segments) >= 2 and segments[0] in _SPOTIFY_TYPES:
        kind, item_id = segments[0], segments[1]
        if not re.fullmatch(r"[A-Za-z0-9]{10,64}", item_id):
            raise ValueError("Der Spotify-Link enthält keine gültige Inhalts-ID.")
        return f"https://open.spotify.com/embed/{kind}/{item_id}?utm_source=generator"
    return "https://open.spotify.com/"
