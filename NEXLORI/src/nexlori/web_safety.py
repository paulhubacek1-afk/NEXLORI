"""Local safety helpers and self-contained HTML pages for Nexlori."""
from __future__ import annotations

import html
import ipaddress
import re
from urllib.parse import urlsplit


# URL-level protection. This is deliberately local and does not upload browsing history.
_BLOCKED_HOSTS = (
    "pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com", "redtube.com",
    "youporn.com", "tube8.com", "spankbang.com", "beeg.com", "brazzers.com",
    "chaturbate.com", "stripchat.com", "livejasmin.com", "myfreecams.com",
    "sex.com", "hentaihaven.xxx", "nhentai.net", "rule34.xxx", "e621.net",
    "gelbooru.com", "danbooru.donmai.us",
)
_ADULT_TOKEN = re.compile(
    r"(?:^|[./?&#=_+%-])(?:porn|hentai|nsfw|xxx|erotic|adult-content|adultvideo|"
    r"camgirl|sexcam|sexvideo|rule34|booru|onlyfans)(?:$|[./?&#=_+%-])",
    re.IGNORECASE,
)
_KNOWN_LOCAL_HOSTS = {
    "fritz.box", "router.lan", "router.home", "homeassistant.local",
    "home-assistant.local", "nas.local", "synology.local", "printer.local",
}


def is_nsfw_url(url: str) -> bool:
    """Return True for known adult domains and explicit URL path/query markers."""
    try:
        parts = urlsplit(str(url).strip())
        host = (parts.hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    if not host:
        return False
    if any(host == domain or host.endswith("." + domain) for domain in _BLOCKED_HOSTS):
        return True
    searchable = host + parts.path + "?" + parts.query
    return bool(_ADULT_TOKEN.search(searchable))


def normalize_home_target(value: str) -> str:
    """Validate and normalize a LAN device address without allowing credentials or public hosts."""
    value = str(value).strip()
    if not value or len(value) > 320 or any(ch.isspace() for ch in value):
        raise ValueError("Bitte eine lokale Geräteadresse ohne Leerzeichen eingeben.")
    if "://" not in value:
        value = "http://" + value
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"}:
        raise ValueError("Nur lokale HTTP- oder HTTPS-Geräteadressen sind erlaubt.")
    if parts.username or parts.password or not parts.hostname:
        raise ValueError("Die Geräteadresse ist ungültig.")
    host = parts.hostname.casefold().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ValueError("Die IP-Adresse ist nicht als lokales Heimnetz-Ziel erkennbar.")
    elif host not in _KNOWN_LOCAL_HOSTS and not host.endswith((".local", ".lan", ".home", ".internal")):
        raise ValueError("Erlaubt sind private IP-Adressen sowie .local, .lan, .home oder bekannte Router-Namen.")
    if parts.port is not None and not 1 <= parts.port <= 65535:
        raise ValueError("Der Port muss zwischen 1 und 65535 liegen.")
    netloc = host + (f":{parts.port}" if parts.port else "")
    path = parts.path or "/"
    return parts._replace(netloc=netloc, path=path, fragment="").geturl()


def _palette(theme) -> dict[str, str]:
    return {
        "bg": theme.bg, "surface": theme.surface, "fg": theme.fg,
        "accent": theme.accent, "stripes": ", ".join(theme.stripes or (theme.accent,)),
    }


def _shell(theme, title: str, body: str, *, animation: bool = True) -> str:
    p = _palette(theme)
    animation_css = """
@keyframes rise { from { opacity:0; transform:translateY(12px) } to { opacity:1; transform:translateY(0) } }
.card { animation:rise .36s ease-out both; }
a,button,.card { transition:transform .18s ease,border-color .18s ease,background .18s ease; }
a:hover,button:hover { transform:translateY(-2px); }
""" if animation else ""
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · Nexlori</title>
<style>
:root {{ color-scheme: {'light' if p['bg'].upper() in ('#FFFFFF','#F4F1EA') else 'dark'}; }}
* {{ box-sizing:border-box }}
body {{ margin:0; min-height:100vh; overflow-x:hidden; background:{p['bg']}; color:{p['fg']}; font:16px 'Segoe UI',sans-serif; }}
.top {{ height:5px; background:linear-gradient(90deg,{p['stripes']}); background-size:200% 100%; animation:flow 10s ease-in-out infinite alternate; }}
@keyframes flow {{ from {{ background-position:0 0 }} to {{ background-position:100% 0 }} }}
main {{ width:min(920px,92vw); margin:0 auto; padding:42px 0 54px; }}
.eyebrow {{ color:{p['accent']}; text-transform:uppercase; letter-spacing:.18em; font-size:11px; font-weight:800; }}
h1 {{ margin:12px 0 9px; font-size:clamp(32px,5vw,54px); line-height:1.06; letter-spacing:-.04em; }}
p {{ opacity:.84; line-height:1.65; }}
.card {{ border:1px solid {p['accent']}55; background:{p['surface']}; border-radius:18px; padding:20px; margin:14px 0; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-top:20px; }}
.tile {{ display:block; color:{p['fg']}; text-decoration:none; border:1px solid {p['surface']}; background:{p['surface']}; padding:18px; border-radius:16px; }}
.tile:hover {{ border-color:{p['accent']}; }}
a.button,button {{ display:inline-flex; align-items:center; justify-content:center; min-height:42px; margin:4px 6px 4px 0; padding:10px 16px; border-radius:12px; border:1px solid {p['accent']}80; background:{p['accent']}; color:{p['bg']}; text-decoration:none; font:700 14px 'Segoe UI',sans-serif; cursor:pointer; }}
a.secondary,button.secondary {{ background:transparent; color:{p['fg']}; border-color:{p['accent']}55; }}
input,select {{ min-width:0; width:100%; padding:12px 13px; border-radius:11px; border:1px solid {p['accent']}70; color:{p['fg']}; background:{p['bg']}; font:inherit; }}
label {{ display:block; font-size:13px; opacity:.85; margin:12px 0 5px; }}
.muted,small {{ opacity:.67; font-size:13px; line-height:1.55; }}
.icon {{ color:{p['accent']}; font-size:24px; margin-bottom:8px; }}
footer {{ margin-top:28px; opacity:.55; font-size:12px; }}
{animation_css}
@media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ animation:none !important; transition:none !important; scroll-behavior:auto !important; }} }}
</style></head><body><div class="top"></div><main>{body}<footer>Nexlori · Lokale Seite · Deine Daten bleiben auf deinem Gerät</footer></main></body></html>"""


def error_page_html(theme, kind: str, url: str, detail: str = "") -> str:
    """Distinct, privacy-friendly error pages; offline mode includes a tiny offline game."""
    target = html.escape(url, quote=True)
    detail_html = f"<p class='muted'>{html.escape(detail[:320])}</p>" if detail else ""
    pages = {
        "offline": ("Keine Verbindung", "Du bist offline", "Nexlori erreicht das Internet gerade nicht. Deine offenen Tabs bleiben erhalten."),
        "dns": ("Adresse nicht gefunden", "Diese Adresse wurde nicht gefunden", "Der Domainname konnte nicht aufgelöst werden. Prüfe die Schreibweise oder deine Verbindung."),
        "certificate": ("Sicherheitsprüfung fehlgeschlagen", "Verbindung nicht sicher", "Das Zertifikat der Website konnte nicht sicher bestätigt werden. Öffne die Seite nicht, wenn du dem Zertifikat nicht vertraust."),
        "not-found": ("Seite nicht gefunden", "Diese Seite existiert nicht", "Der Server hat die angeforderte Seite nicht gefunden (HTTP 404)."),
        "server": ("Serverfehler", "Die Website hat ein Problem", "Der Server konnte die Anfrage nicht bearbeiten. Versuche es später erneut."),
        "blocked": ("Inhalt blockiert", "Nexlori hat diese Adresse blockiert", "Diese Adresse passt zu Nexloris lokalem NSFW-Schutz. Du kannst zurück oder zur Startseite gehen."),
        "connection": ("Verbindung fehlgeschlagen", "Website nicht erreichbar", "Die Verbindung wurde abgebrochen oder der Server antwortet nicht."),
        "generic": ("Seitenfehler", "Die Seite konnte nicht geladen werden", "Nexlori konnte den Seiteninhalt nicht öffnen."),
    }
    title, heading, desc = pages.get(kind, pages["generic"])
    game = ""
    if kind == "offline":
        game = """
<div class="card"><h2>Offline-Run</h2><p class="muted">Drücke Leertaste, Pfeil nach oben oder tippe auf das Spielfeld, um zu springen.</p>
<canvas id="game" width="820" height="180" style="display:block;width:100%;height:auto;border-radius:12px;background:rgba(127,127,127,.08);touch-action:manipulation" aria-label="Offline-Spiel"></canvas>
<p id="score" class="muted">Punkte: 0 · Bestwert nur für diese Runde</p>
<button id="restart" class="secondary" type="button">Neu starten</button></div>
<script>
(() => {
 const canvas=document.getElementById('game'), ctx=canvas.getContext('2d'), scoreNode=document.getElementById('score');
 if(!ctx) return;
 let playerY=0, velocity=0, obstacles=[], frame=0, score=0, running=true, best=0;
 const ground=145;
 function reset(){playerY=0;velocity=0;obstacles=[];frame=0;score=0;running=true;loop();}
 function jump(){if(playerY===0){velocity=-10.5;}}
 function tick(){
   ctx.clearRect(0,0,canvas.width,canvas.height); ctx.strokeStyle=getComputedStyle(document.body).color;ctx.globalAlpha=.4;
   ctx.beginPath();ctx.moveTo(0,ground+17);ctx.lineTo(canvas.width,ground+17);ctx.stroke();ctx.globalAlpha=1;
   velocity+=.48;playerY=Math.min(0,playerY+velocity);if(playerY===0)velocity=0;
   ctx.fillStyle=getComputedStyle(document.body).color;ctx.fillRect(64,ground+playerY-25,22,25);
   if(frame%78===0)obstacles.push({x:canvas.width+10,h:18+Math.random()*20});
   obstacles.forEach(o=>{o.x-=5.2;ctx.fillRect(o.x,ground+17-o.h,14,o.h);});
   obstacles=obstacles.filter(o=>o.x>-20);score+=1;frame++;
   const hit=obstacles.some(o=>o.x<83&&o.x+14>64&&ground+playerY>ground+17-o.h);
   if(hit){running=false;ctx.fillText('Runde beendet · Neustart drücken',canvas.width/2-100,62);best=Math.max(best,score);scoreNode.textContent='Punkte: '+score+' · Bestwert: '+best;return;}
   scoreNode.textContent='Punkte: '+score+' · Bestwert: '+Math.max(best,score);
 }
 function loop(){if(!running)return;tick();requestAnimationFrame(loop);}
 window.addEventListener('keydown',e=>{if(e.code==='Space'||e.code==='ArrowUp'){e.preventDefault();jump();}});
 canvas.addEventListener('pointerdown',jump);document.getElementById('restart').addEventListener('click',reset);loop();
})();
</script>"""
    body = f"""<span class="eyebrow">Nexlori · {html.escape(title)}</span><h1>{html.escape(heading)}</h1>
<p>{html.escape(desc)}</p>{detail_html}<div class="card"><div class="muted">Adresse</div><strong>{target}</strong></div>
<a class="button" href="nexlori://browser/retry?url={target}">Erneut versuchen</a>
<a class="button secondary" href="nexlori://browser/home">Zur Startseite</a>{game}"""
    return _shell(theme, title, body)


def addons_page_html(theme) -> str:
    body = """<span class="eyebrow">Nexlori · Erweiterungen</span><h1>Dein Browser. Deine Add-ons.</h1>
<p>Installiere zusätzliche Erweiterungen aus ZIP-Dateien oder entpackten Ordnern. Nexlori unterstützt derzeit Chromium-Manifest-V3. Lies vor jeder Installation die angeforderten Berechtigungen.</p>
<div class="grid">
<a class="tile" href="nexlori://addons/install-zip"><div class="icon">＋</div><strong>ZIP installieren</strong><p class="muted">Ein Add-on-Paket von deinem Computer auswählen.</p></a>
<a class="tile" href="nexlori://addons/install-folder"><div class="icon">▣</div><strong>Ordner installieren</strong><p class="muted">Einen bereits entpackten Add-on-Ordner mit manifest.json auswählen.</p></a>
<a class="tile" href="nexlori://addons/manage"><div class="icon">⚙</div><strong>Installierte Add-ons</strong><p class="muted">Erweiterungen aktivieren, deaktivieren oder entfernen.</p></a>
</div>
<div class="card"><strong>Projektseiten</strong><p class="muted">Diese Quellen öffnen die Projektseite im Web. Nexlori installiert nichts automatisch; du musst das Paket selbst auswählen und bestätigen.</p>
<a class="button secondary" href="https://github.com/darkreader/darkreader/releases">Dark Reader</a>
<a class="button secondary" href="https://github.com/ajayyy/SponsorBlock/releases">SponsorBlock</a>
<a class="button secondary" href="https://github.com/ClearURLs/Addon/releases">ClearURLs</a>
</div>
<div class="card"><strong>Wichtig</strong><p class="muted">Erweiterungen können deine geöffneten Websites lesen oder verändern. Installiere nur Pakete, denen du vertraust. Manche Chrome-Web-Store-Erweiterungen sind mit Qt WebEngine nicht kompatibel.</p></div>"""
    return _shell(theme, "Add-ons", body)


def home_network_page_html(theme) -> str:
    body = """<span class="eyebrow">Nexlori · Heimnetz</span><h1>Deine Geräte zuhause.</h1>
<p>Öffne die Verwaltungsseite deines Routers, NAS, Druckers oder Smart-Home-Servers. Gib eine bekannte private IP-Adresse oder einen lokalen Gerätenamen ein. Nexlori scannt dein Netzwerk nicht automatisch.</p>
<div class="card"><form id="device-form">
<label for="scheme">Verbindung</label><select id="scheme"><option value="http://">HTTP</option><option value="https://">HTTPS</option></select>
<label for="host">Lokale Adresse</label><input id="host" autocomplete="off" placeholder="z. B. 192.168.178.1 oder nas.local" required>
<label for="port">Port (optional)</label><input id="port" inputmode="numeric" placeholder="leer lassen für Standard-Port">
<button type="submit">Gerät öffnen</button></form><p id="feedback" class="muted"></p></div>
<h2>Häufige Geräte</h2><div class="grid">
<a class="tile" href="nexlori://home-network/open?target=http%3A%2F%2Ffritz.box%2F"><div class="icon">⌁</div><strong>FRITZ!Box</strong><small>http://fritz.box</small></a>
<a class="tile" href="nexlori://home-network/open?target=http%3A%2F%2F192.168.178.1%2F"><div class="icon">⌂</div><strong>Router · 192.168.178.1</strong><small>Übliche lokale Router-Adresse</small></a>
<a class="tile" href="nexlori://home-network/open?target=http%3A%2F%2F192.168.0.1%2F"><div class="icon">⌂</div><strong>Router · 192.168.0.1</strong><small>Alternative lokale Router-Adresse</small></a>
<a class="tile" href="nexlori://home-network/open?target=http%3A%2F%2Fhomeassistant.local%2F"><div class="icon">⌘</div><strong>Home Assistant</strong><small>homeassistant.local</small></a>
<a class="tile" href="nexlori://home-network/open?target=http%3A%2F%2Fnas.local%2F"><div class="icon">▤</div><strong>NAS</strong><small>nas.local</small></a>
<a class="tile" href="nexlori://home-network/open?target=http%3A%2F%2Fprinter.local%2F"><div class="icon">▧</div><strong>Drucker</strong><small>printer.local</small></a>
</div><div class="card"><strong>Verbindung geht nicht?</strong><p class="muted">Geräte müssen im selben WLAN/LAN erreichbar sein. Manche Geräte verwenden einen anderen Namen, eine andere IP oder HTTPS. Schaue in der Router-App nach der Geräteadresse.</p></div>
<script>
document.getElementById('device-form').addEventListener('submit',e=>{
 e.preventDefault();let h=document.getElementById('host').value.trim(),p=document.getElementById('port').value.trim(),s=document.getElementById('scheme').value;
 if(!h||/\\s|@|\\/|#/.test(h)){document.getElementById('feedback').textContent='Bitte nur IP-Adresse oder lokalen Hostnamen eingeben.';return;}
 if(p && (!/^\\d{1,5}$/.test(p)||+p<1||+p>65535)){document.getElementById('feedback').textContent='Der Port muss zwischen 1 und 65535 liegen.';return;}
 const target=s+h+(p?':'+p:'')+'/';
 location.href='nexlori://home-network/open?target='+encodeURIComponent(target);
});
</script>"""
    return _shell(theme, "Heimnetz", body)
