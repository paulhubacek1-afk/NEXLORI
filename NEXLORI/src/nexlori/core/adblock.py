"""Nexlori Shield – eingebauter Werbe- und Trackerblocker.

Der Blocker arbeitet unabhängig von Browser-Erweiterungen direkt auf Netzwerkebene:
Qt WebEngine fragt für jede Unterressource (Skripte, Bilder, Frames, XHR …) nach, und
``AdBlocker.should_block`` entscheidet anhand von Domainlisten und wenigen URL-Regeln.
Zusätzlich blendet ein kosmetischer Filter typische Werbeflächen per CSS aus.

Alles läuft lokal. Optionale Filterlisten werden nur über HTTPS von festen, bekannten
Quellen geladen, streng geprüft und als reine Domainliste gespeichert – es wird nie
fremder Code ausgeführt.

Dieses Modul hat bewusst keine Qt-Abhängigkeit, damit es vollständig testbar bleibt.
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

# --------------------------------------------------------------------------- eingebaute Regeln
# Kuratierte Liste bekannter Werbe-, Tracking- und Telemetrie-Domains. Subdomains werden
# automatisch mit erfasst (``ads.example.com`` passt auf ``example.com``).
BUILTIN_DOMAINS: frozenset[str] = frozenset({
    # Google-Werbung und -Messung
    "doubleclick.net", "googlesyndication.com", "googleadservices.com", "google-analytics.com",
    "googletagservices.com", "googletagmanager.com", "adservice.google.com", "adservice.google.de",
    "adservice.google.at", "adservice.google.ch", "pagead2.googlesyndication.com", "imasdk.googleapis.com",
    "2mdn.net", "admob.com", "app-measurement.com", "ssl.google-analytics.com",
    # Große Werbebörsen und SSPs
    "adnxs.com", "adsrvr.org", "adform.net", "adition.com", "advertising.com", "amazon-adsystem.com",
    "aniview.com", "appnexus.com", "bidswitch.net", "casalemedia.com", "contextweb.com", "criteo.com",
    "criteo.net", "districtm.io", "emxdgt.com", "gumgum.com", "indexww.com", "lijit.com",
    "media.net", "openx.net", "outbrain.com", "pubmatic.com", "rubiconproject.com", "sharethrough.com",
    "smartadserver.com", "sonobi.com", "spotxchange.com", "springserve.com", "taboola.com",
    "teads.tv", "triplelift.com", "yieldmo.com", "33across.com", "adcolony.com", "adroll.com",
    "adsafeprotected.com", "adzerk.net", "applovin.com", "bidr.io", "connatix.com", "doubleverify.com",
    "e-planning.net", "exponential.com", "flashtalking.com", "inmobi.com", "ad.yieldmanager.com",
    "moatads.com", "mookie1.com", "nativo.com", "revcontent.com", "mgid.com", "zemanta.com",
    "unrulymedia.com", "vidazoo.com", "yieldlab.net", "stroeer.io", "adscale.de", "ligatus.com",
    "mediasmart.io", "seedtag.com", "improvedigital.com", "adhese.com", "adtech.de", "adup-tech.com",
    "plista.com", "orbidder.otto.de", "ad4mat.de", "uimserv.net", "adalliance.io", "ad-srv.net",
    "propellerads.com", "popads.net", "popcash.net", "adsterra.com", "exoclick.com", "juicyads.com",
    "trafficjunky.net", "hilltopads.net", "clickadu.com", "admaven.com", "onclickads.net",
    "yandexadexchange.net", "an.yandex.ru", "adfox.ru", "ads.yahoo.com", "gemini.yahoo.com",
    "ads.linkedin.com", "ads-api.tiktok.com", "ads.twitter.com", "ads-twitter.com", "static.ads-twitter.com",
    "ads.pinterest.com", "ads.reddit.com", "bat.bing.com", "ads.microsoft.com",
    # Tracking, Analyse, Session-Recording
    "scorecardresearch.com", "quantserve.com", "quantcount.com", "chartbeat.com", "chartbeat.net",
    "hotjar.com", "hotjar.io", "mouseflow.com", "crazyegg.com", "fullstory.com", "luckyorange.com",
    "clarity.ms", "newrelic.com", "nr-data.net", "segment.io", "segment.com", "mixpanel.com",
    "amplitude.com", "heap.io", "heapanalytics.com", "kissmetrics.com", "optimizely.com",
    "krxd.net", "bluekai.com", "demdex.net", "omtrdc.net", "everesttech.net", "exelator.com",
    "agkn.com", "rlcdn.com", "tapad.com", "adsymptotic.com", "crwdcntrl.net", "eyeota.net",
    "lotame.com", "addthis.com", "sharethis.com", "id5-sync.com", "liadm.com", "zeotap.com",
    "ioam.de", "xiti.com", "atinternet.com", "etracker.com", "etracker.de", "webtrekk.net",
    "wt-safetag.com", "mpnrs.com", "emetriq.de", "nuggad.net", "adclear.net", "intelliad.de",
    "branch.io", "app.link", "adjust.com", "appsflyer.com", "kochava.com", "singular.net",
    "connect.facebook.net", "pixel.facebook.com", "an.facebook.com", "analytics.tiktok.com",
    "analytics.twitter.com", "px.ads.linkedin.com", "snap.licdn.com", "sc-static.net",
    "tr.snapchat.com", "ct.pinterest.com", "analytics.pinterest.com", "pixel.wp.com", "stats.wp.com",
    "yandex.ru/metrika", "mc.yandex.ru", "metrika.yandex.ru", "matomo.cloud", "statcounter.com",
    "histats.com", "clicky.com", "static.getclicky.com", "parsely.com", "cdn.permutive.com",
    "permutive.com", "permutive.app", "tiqcdn.com", "tealiumiq.com", "ensighten.com",
    "trustarc.com", "evidon.com", "adobedtm.com", "assets.adobedtm.com", "pippio.com",
    "cxense.com", "sessioncam.com", "inspectlet.com", "smartlook.com", "logrocket.io", "logrocket.com",
    # Telemetrie und Fingerprinting
    "fingerprintjs.com", "fpjs.io", "browser-intake-datadoghq.com", "sentry-cdn.com",
    "iesnare.com", "threatmetrix.com", "online-metrix.net", "siftscience.com",
})

# Werbe- und Tracking-Pfade auf Domains, die auch nützliche Inhalte ausliefern.
_PATH_RULES: tuple[tuple[str, str], ...] = (
    ("youtube.com", "/api/stats/ads"),
    ("youtube.com", "/pagead/"),
    ("youtube.com", "/ptracking"),
    ("youtube.com", "/get_midroll_"),
    ("google.com", "/pagead/"),
    ("google.com", "/ads/"),
    ("facebook.com", "/tr"),
    ("facebook.com", "/plugins/"),
    ("reddit.com", "/api/v2/pixel"),
    ("linkedin.com", "/px/"),
    ("twitter.com", "/i/adsct"),
    ("x.com", "/i/adsct"),
)

# Typische Werbecontainer. Nur eindeutige Selektoren, damit keine Inhalte verschwinden.
COSMETIC_SELECTORS: tuple[str, ...] = (
    "ins.adsbygoogle", ".adsbygoogle", "[id^='google_ads_iframe']", "[id^='div-gpt-ad']",
    "[data-google-query-id]", "iframe[src*='doubleclick.net']", "iframe[src*='googlesyndication']",
    "iframe[id^='google_ads']", "[data-ad-slot]", "[data-ad-unit]", "[data-adunit]",
    "[id^='taboola-']", ".trc_related_container", ".OUTBRAIN", "[data-widget-id^='outbrain']",
    "[class*='taboola']", "[id^='ad-slot']", "[id^='adslot']", ".ad-slot", ".adslot",
    ".ad-container", ".ad-wrapper", ".ad-banner", ".ad-leaderboard", ".advertisement",
    "[aria-label='Advertisement']", "[aria-label='Anzeige']", ".sponsored-ad",
    "amp-ad", "amp-embed[type='taboola']", "amp-sticky-ad",
    # YouTube
    "ytd-ad-slot-renderer", "ytd-promoted-sparkles-web-renderer", "ytd-promoted-video-renderer",
    "ytd-display-ad-renderer", "ytd-in-feed-ad-layout-renderer", "ytd-banner-promo-renderer",
    "ytd-statement-banner-renderer", "ytd-video-masthead-ad-v3-renderer", "#masthead-ad",
    "#player-ads", ".ytp-ad-overlay-container", ".ytp-ad-image-overlay", ".ytd-companion-slot-renderer",
    "ytd-engagement-panel-section-list-renderer[target-id='engagement-panel-ads']",
)

# --------------------------------------------------------------------------- Filterlisten
@dataclass(frozen=True)
class FilterList:
    id: str
    label: str
    url: str
    description: str
    default: bool


FILTER_LISTS: tuple[FilterList, ...] = (
    FilterList(
        "pgl", "Peter Lowe's Ad and tracking server list",
        "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0&mimetype=plaintext",
        "Kompakte, seit Jahren gepflegte Liste von Werbe- und Trackingservern.", True,
    ),
    FilterList(
        "stevenblack", "StevenBlack Unified Hosts",
        "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
        "Sehr umfangreiche Liste gegen Werbung, Tracking und Schadsoftware (mehr Schutz, etwas mehr RAM).", False,
    ),
)
FILTER_LIST_IDS = frozenset(item.id for item in FILTER_LISTS)
LIST_REFRESH_SECONDS = 4 * 24 * 3600
MAX_LIST_BYTES = 8 * 1024 * 1024
MAX_LIST_DOMAINS = 250_000

_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_NEVER_BLOCK = frozenset({
    "localhost", "localhost.localdomain", "local", "broadcasthost", "0.0.0.0",
    "github.com", "githubusercontent.com", "raw.githubusercontent.com", "pgl.yoyo.org",
})


def normalize_host(value: str) -> str:
    return str(value or "").strip().casefold().rstrip(".")


def host_of(url: str) -> str:
    try:
        return normalize_host(urlsplit(str(url)).hostname or "")
    except ValueError:
        return ""


def _suffixes(host: str) -> Iterable[str]:
    labels = host.split(".")
    for index in range(len(labels) - 1):
        yield ".".join(labels[index:])


def parse_filter_list(text: str) -> set[str]:
    """Liest Hosts-Dateien (``0.0.0.0 domain``), reine Domainlisten und ``||domain^``-Regeln."""
    domains: set[str] = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("!") or line.startswith("["):
            continue
        if line.startswith("||"):
            body = line[2:]
            if not body.endswith("^") or any(ch in body[:-1] for ch in "/*$^|"):
                continue
            candidate = body[:-1]
        else:
            parts = line.split()
            if len(parts) >= 2 and parts[0] in {"0.0.0.0", "127.0.0.1", "::", "::1"}:
                candidate = parts[1]
            elif len(parts) == 1:
                candidate = parts[0]
            else:
                continue
        candidate = normalize_host(candidate)
        if candidate in _NEVER_BLOCK or not _DOMAIN_RE.match(candidate):
            continue
        domains.add(candidate)
        if len(domains) >= MAX_LIST_DOMAINS:
            break
    return domains


# --------------------------------------------------------------------------- Blocker
class AdBlocker:
    """Thread-sichere Entscheidung, ob eine Unterressource blockiert wird.

    ``should_block`` wird von Qt auf dem Netzwerk-Thread aufgerufen, deshalb sind alle
    veränderlichen Zustände durch eine Sperre geschützt und die Prüfung kommt mit wenigen
    Set-Abfragen aus.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        allowlist: Iterable[str] = (),
        extra_domains: Iterable[str] = (),
    ) -> None:
        self._lock = threading.Lock()
        self.enabled = bool(enabled)
        self._allowlist = {normalize_host(h) for h in allowlist if normalize_host(h)}
        self._domains: frozenset[str] = BUILTIN_DOMAINS | frozenset(extra_domains)
        self._blocked_by_site: dict[str, int] = {}
        self._blocked_total = 0

    # ------------------------------------------------------------- Konfiguration
    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.enabled = bool(enabled)

    def set_extra_domains(self, domains: Iterable[str]) -> None:
        merged = BUILTIN_DOMAINS | frozenset(domains)
        with self._lock:
            self._domains = merged

    def set_allowlist(self, hosts: Iterable[str]) -> None:
        with self._lock:
            self._allowlist = {normalize_host(h) for h in hosts if normalize_host(h)}

    @property
    def domain_count(self) -> int:
        return len(self._domains)

    def is_allowlisted(self, site_host: str) -> bool:
        host = normalize_host(site_host)
        if not host:
            return False
        allow = self._allowlist
        return host in allow or any(suffix in allow for suffix in _suffixes(host))

    # ------------------------------------------------------------- Entscheidung
    def match_reason(self, url: str) -> str | None:
        """``"domain"`` oder ``"path"``, wenn die URL auf einer Block-Regel steht, sonst ``None``."""
        try:
            parts = urlsplit(str(url))
        except ValueError:
            return None
        if parts.scheme not in {"http", "https", "ws", "wss"}:
            return None
        host = normalize_host(parts.hostname or "")
        if not host:
            return None
        domains = self._domains
        if host in domains or any(suffix in domains for suffix in _suffixes(host)):
            return "domain"
        path = parts.path or "/"
        first_segment = path.lstrip("/").split("/", 1)[0]
        if first_segment and any(f"{suffix}/{first_segment}" in domains for suffix in (host, *_suffixes(host))):
            return "path"
        for rule_host, rule_path in _PATH_RULES:
            if host == rule_host or host.endswith("." + rule_host):
                # Prefix rules ending in / or _ intentionally match variable IDs.
                # Other rules must end on a path boundary (e.g. /tr, not /travel).
                if rule_path.endswith(("/", "_")):
                    matched = path.startswith(rule_path)
                else:
                    matched = path == rule_path or path.startswith(rule_path + "/")
                if matched:
                    return "path"
        return None

    def matches(self, url: str) -> bool:
        return self.match_reason(url) is not None

    def should_block(self, url: str, first_party_url: str = "") -> bool:
        if not self.enabled:
            return False
        site = host_of(first_party_url)
        if site and self.is_allowlisted(site):
            return False
        reason = self.match_reason(url)
        if reason is None:
            return False
        request_host = host_of(url)
        # Eine Seite, die selbst auf einer Domainliste steht, darf ihre eigenen Dateien laden,
        # sonst funktioniert ein bewusst geöffneter Link nicht. Pfad-Regeln gelten trotzdem.
        if reason == "domain" and site and (
            request_host == site or request_host.endswith("." + site) or site.endswith("." + request_host)
        ):
            return False
        with self._lock:
            self._blocked_total += 1
            key = site or "unbekannt"
            self._blocked_by_site[key] = self._blocked_by_site.get(key, 0) + 1
        return True

    # ------------------------------------------------------------- Statistik
    def blocked_for_site(self, site_host: str) -> int:
        with self._lock:
            return self._blocked_by_site.get(normalize_host(site_host), 0)

    @property
    def blocked_total(self) -> int:
        with self._lock:
            return self._blocked_total

    def reset_site(self, site_host: str) -> None:
        with self._lock:
            self._blocked_by_site.pop(normalize_host(site_host), None)


def cosmetic_css(selectors: Iterable[str] = COSMETIC_SELECTORS) -> str:
    joined = ",\n".join(selectors)
    return f"{joined} {{ display: none !important; visibility: hidden !important; }}"


def build_cosmetic_script(*, allowlisted_hosts: Iterable[str] = ()) -> str:
    """JavaScript, das den kosmetischen Filter einfügt und YouTube-Videowerbung überspringt."""
    css = json.dumps(cosmetic_css())
    allow = json.dumps(sorted({normalize_host(h) for h in allowlisted_hosts if normalize_host(h)}))
    return f"""
(() => {{
  if (window.__nexloriShield) return;
  window.__nexloriShield = true;
  const host = (location.hostname || '').toLowerCase();
  const allow = {allow};
  if (allow.some(a => host === a || host.endsWith('.' + a))) return;
  const start = () => {{
    const root = document.documentElement;
    if (!root) {{
      document.addEventListener('DOMContentLoaded', start, {{ once: true }});
      return;
    }}
    const style = document.createElement('style');
    style.id = 'nexlori-shield-css';
    style.textContent = {css};
    (document.head || root).appendChild(style);
    if (!/(^|\\.)youtube\\.com$/.test(host)) return;
    const skip = () => {{
      const player = document.querySelector('.html5-video-player');
      const button = document.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button');
      if (button) button.click();
      if (player && player.classList.contains('ad-showing')) {{
        const video = player.querySelector('video');
        if (video && isFinite(video.duration) && video.duration > 0) {{
          video.muted = true;
          video.currentTime = Math.max(0, video.duration - 0.1);
        }}
      }}
    }};
    new MutationObserver(skip).observe(root, {{ subtree: true, childList: true, attributes: true, attributeFilter: ['class'] }});
    setInterval(skip, 700);
  }};
  start();
}})();
"""


# --------------------------------------------------------------------------- Listen-Speicher
class FilterListError(RuntimeError):
    pass


class FilterListStore:
    """Speichert heruntergeladene Filterlisten als geprüfte Domainlisten im Profilordner."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.path = self.directory / "filterlists.json"

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def domains(self, list_ids: Iterable[str]) -> set[str]:
        data = self._read()
        merged: set[str] = set()
        for list_id in list_ids:
            entry = data.get(list_id)
            if isinstance(entry, dict) and isinstance(entry.get("domains"), list):
                merged.update(
                    d for d in entry["domains"]
                    if isinstance(d, str) and d not in _NEVER_BLOCK and _DOMAIN_RE.match(d)
                )
        return merged

    def info(self) -> dict[str, dict]:
        data = self._read()
        out = {}
        for item in FILTER_LISTS:
            entry = data.get(item.id) if isinstance(data.get(item.id), dict) else {}
            fetched = entry.get("fetched", 0)
            if isinstance(fetched, bool) or not isinstance(fetched, (int, float)) or not math.isfinite(fetched):
                fetched = 0
            out[item.id] = {
                "fetched": float(fetched),
                "count": len(entry.get("domains", [])) if isinstance(entry.get("domains"), list) else 0,
            }
        return out

    def needs_refresh(self, list_ids: Iterable[str], *, now: float | None = None) -> list[str]:
        now = time.time() if now is None else now
        info = self.info()
        stale = []
        for list_id in list_ids:
            if list_id not in FILTER_LIST_IDS:
                continue
            fetched = info.get(list_id, {}).get("fetched", 0)
            if not fetched or fetched > now or now - fetched > LIST_REFRESH_SECONDS:
                stale.append(list_id)
        return stale

    def store(self, list_id: str, domains: set[str], *, now: float | None = None) -> None:
        if list_id not in FILTER_LIST_IDS:
            raise FilterListError(f"Unbekannte Filterliste: {list_id}")
        data = self._read()
        clean_domains = {
            normalize_host(domain)
            for domain in domains
            if isinstance(domain, str)
            and normalize_host(domain) not in _NEVER_BLOCK
            and _DOMAIN_RE.fullmatch(normalize_host(domain))
        }
        data[list_id] = {
            "fetched": time.time() if now is None else now,
            "domains": sorted(clean_domains),
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, separators=(",", ":"))
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def download_filter_list(list_id: str, *, timeout: float = 20.0) -> set[str]:
    """Lädt eine bekannte Filterliste über HTTPS und gibt nur gültige Domains zurück."""
    item = next((entry for entry in FILTER_LISTS if entry.id == list_id), None)
    if item is None:
        raise FilterListError(f"Unbekannte Filterliste: {list_id}")
    if not item.url.startswith("https://"):
        raise FilterListError("Filterlisten werden nur über HTTPS geladen.")
    request = urllib.request.Request(item.url, headers={"User-Agent": "Nexlori-Shield/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_LIST_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise FilterListError(f"{item.label} konnte nicht geladen werden.") from exc
    if len(raw) > MAX_LIST_BYTES:
        raise FilterListError(f"{item.label} ist größer als erlaubt.")
    domains = parse_filter_list(raw.decode("utf-8", errors="replace"))
    if len(domains) < 50:
        raise FilterListError(f"{item.label} enthält unerwartet wenige Einträge und wurde verworfen.")
    return domains
