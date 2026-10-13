"""Seitenabruf (nur http/https) mit Größen- und Zeitlimits.

TLS und Zertifikatsprüfung übernimmt die Standardbibliothek (`ssl`) mit dem Zertifikatsspeicher des
Betriebssystems – es wird keine eigene Kryptografie geschrieben. Eine fehlgeschlagene Prüfung wird NIE
umgangen. Es werden keine Cookies gespeichert oder gesendet.
"""
from __future__ import annotations

import re
import socket
import ssl
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit

USER_AGENT = "Nexlori/0.1 (+https://github.com/paulhubacek1-afk/NEXLORI)"
MAX_BYTES = 3 * 1024 * 1024
TIMEOUT = 15.0
HTML_TYPES = ("text/html", "application/xhtml+xml")


class FetchError(Exception):
    """Fehler mit einer für Menschen lesbaren Meldung (wird als Fehlerseite angezeigt)."""


@dataclass(frozen=True)
class FetchResult:
    url: str  # Endadresse nach Weiterleitungen
    status: int
    content_type: str
    text: str
    truncated: bool = False


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    """Folgt Weiterleitungen nur zu http/https (kein ftp:, file: usw.)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme.lower() not in ("http", "https"):
            raise FetchError(f"Weiterleitung auf ein nicht erlaubtes Ziel blockiert: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def make_opener(*, use_system_proxy: bool = True) -> urllib.request.OpenerDirector:
    handlers: list = [urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(context=ssl.create_default_context()), _SafeRedirects()]
    if not use_system_proxy:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def safe_url(url: str) -> str:
    """Macht eine eingegebene Adresse abrufbar (IDN-Hostnamen, Sonderzeichen) und entfernt Zugangsdaten."""
    try:
        parts = urlsplit(url.strip())
        host = (parts.hostname or "").encode("idna").decode("ascii")
        port = parts.port
    except (ValueError, UnicodeError) as exc:
        raise FetchError("Die Adresse ist ungültig.") from exc
    if not host:
        raise FetchError("Die Adresse enthält keinen Servernamen.")
    if ":" in host:
        host = f"[{host}]"
    netloc = host + (f":{port}" if port else "")
    path = quote(parts.path, safe="/%:@!$&'()*+,;=~-._") or "/"
    query = quote(parts.query, safe="=&%+/:@!$'()*,;~-._?")
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


_META_CHARSET = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?\s*([\w.:-]+)", re.IGNORECASE)


def decode_body(raw: bytes, header_charset: str | None) -> str:
    charset = header_charset
    if not charset:
        m = _META_CHARSET.search(raw[:2048])
        charset = m.group(1).decode("ascii", "ignore") if m else "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _read_limited(resp, max_bytes: int) -> tuple[bytes, bool]:
    raw = resp.read(max_bytes + 1)
    if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            raw = decoder.decompress(raw, max_bytes + 1)  # max_length begrenzt auch Zip-Bomben
        except zlib.error as exc:
            raise FetchError("Die Antwort des Servers konnte nicht entpackt werden.") from exc
    return raw[:max_bytes], len(raw) > max_bytes


def fetch_url(
    url: str,
    *,
    timeout: float = TIMEOUT,
    max_bytes: int = MAX_BYTES,
    use_system_proxy: bool = True,
) -> FetchResult:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https"):
        raise FetchError(f"Das Adressschema „{parts.scheme or '?'}“ wird nicht unterstützt.")
    request = urllib.request.Request(
        safe_url(url),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5,*/*;q=0.1",
            "Accept-Language": "de,en;q=0.7",
            "Accept-Encoding": "gzip",
        },
    )
    try:
        resp = make_opener(use_system_proxy=use_system_proxy).open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:  # 4xx/5xx: der Server liefert oft eine lesbare Fehlerseite
        resp = exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ssl.SSLCertVerificationError):
            raise FetchError("Das Sicherheitszertifikat der Seite konnte nicht geprüft werden. Die Seite wird aus Sicherheitsgründen nicht geladen.") from exc
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise FetchError("Zeitüberschreitung: Der Server hat nicht rechtzeitig geantwortet.") from exc
        if isinstance(reason, socket.gaierror):
            raise FetchError("Der Servername konnte nicht gefunden werden. Prüfe die Adresse und deine Internetverbindung.") from exc
        raise FetchError(f"Der Server ist nicht erreichbar ({reason}).") from exc
    except (socket.timeout, TimeoutError) as exc:
        raise FetchError("Zeitüberschreitung: Der Server hat nicht rechtzeitig geantwortet.") from exc
    except (ssl.SSLError, OSError) as exc:
        raise FetchError(f"Verbindungsfehler ({exc}).") from exc

    with resp:
        status = getattr(resp, "status", None) or getattr(resp, "code", 200)
        ctype = resp.headers.get_content_type()
        if ctype not in HTML_TYPES and not ctype.startswith("text/"):
            raise FetchError(f"Der Inhaltstyp „{ctype}“ wird noch nicht unterstützt (keine Bilder, PDFs oder Downloads).")
        try:
            raw, truncated = _read_limited(resp, max_bytes)
        except (socket.timeout, TimeoutError) as exc:
            raise FetchError("Zeitüberschreitung beim Laden der Seite.") from exc
        text = decode_body(raw, resp.headers.get_content_charset())
        return FetchResult(resp.geturl() if hasattr(resp, "geturl") else url, int(status), ctype, text, truncated)
