"""Local safety helpers and self-contained HTML pages for Nexlori."""
from __future__ import annotations

import html
import ipaddress
import re
from urllib.parse import quote, urlsplit


import hashlib

# URL rules are stored as SHA-256 fingerprints so this protective filter does not publish adult URLs.
_BLOCKED_HOST_HASHES = {
    "f451a0ce975dbd22a62bd8204a25038ba485ac621a6f2fe2c605d7f3025c7a29",
    "fa5a46404fb6405a5107dd41215b6531cbf0c156c3c8d09aef8460453d5101b9",
    "702962ec26cb6add65eebab8e8ec9c1fa937ed45be43eaa066c2d344759259b2",
    "6eba6edf984bf767ab88553aed11872a8842cc576daee425e12fb16f6722ad06",
    "963b94895db566976842b60d68470314cd979a305236f0acbf26b4e79f8ca9bd",
    "ba3599f39957f1a964d65b05a918c3b0c9bd64e9bdfcb1f3b48b40322c781449",
    "7beb528080886e3d38c46de609f0f0ad4cb7a339bd6e481b7605f75bb706a0ad",
    "0eecab1c8a4bee409daa265178b82f9670cb3f9ff1f501514e5a4428aec082f7",
    "9c3ac886739d8082f36c7ff4aebfa90cdac43af0cc332a16a4d05829d1a792d7",
    "7620dd995ecc7f92f46ced87986711a7314bd1c1c8c34c836a1daddc629a4c19",
    "574cbb327570be709950a11ca67d412785ffa64724397f1d3d2ecca24ebf2685",
    "00a9e0b5a5eca3a4c5f308b1adb2a56e83993ba4c7d11caf083651243f1a703d",
    "61fa57c99de24326e6672e6be55ec05b832d476ef091433169bd7127174d6082",
    "4d13e80e6cd7863d836618a0ee08e9f4b66d28671b9ec942f2b648177e9f83e7",
    "fd48f662f2dede2af727058570e94c9078159b7de7f437113f44d8a5094f3906",
    "20f792540c24b15a3fae188dea9c2ce270e464578221abaafc6c8593bc23fa8a",
    "5bb896a5b7c0630c790724acde83a23c599076776cdb2b8ded7b0fa746b173a6",
    "3b3a641a4889558dce3b793971c66f4851970ae2485ee33045c7b0dbc0bb2cdf",
    "dae39b22e80aa4332bca37b5cda353c50a127e4994f54bde55f1d03de1d35c80",
    "f6ca1c7d5d00a2a3fb4ea2f7edfa0f96a6d09c11717f39facabad2d724f16fbb",
    "bdd57f59706828282d0776ec94909fba54e63e47d147dcecb4ccee2122a1df0c",
}
_BLOCKED_TOKEN_HASHES = {
    "8c5c04391361cbf4afd74c5ed8101ea4af881c4ee3b3df1d5b3716a19b1a834d",
    "6ccffa4977d4246ed9de8ad27693e9802b50d105aae43730d06f1dc840ca6df5",
    "c6603565c5159fbe846a53e991829d452a1546d41150c0d3c73ddbd7f476ee0d",
    "cd2eb0837c9b4c962c22d2ff8b5441b7b45805887f051d39bf133b583baf6860",
    "a3686065149555674b1b7a7d39e00f15d2f831a62b6a33d12f3a14b87c8d0c88",
    "f7996b82150661bf256d610980908773f5afdf48ea4bda18cf467d6a50e5651d",
    "a2f1be23c6705f8d24ff84fe5a0d0860b59bea93370af9880dc4abc3cd99efb4",
    "6a1434eef95646478ac638c61e8ffdc1d3aa77addafeba7490761026fb83b956",
    "c1ee0017af0a756518f3cb5488968eb15f424f80863bf4ea95b1fa9e0e60ef27",
    "83d112c07531d1db394b55a98956beadf08c383c108382fe57791092a8533a00",
    "796ee3d0b91c9715472cb5f982ee27c51fedfe5c6dd77502d1d82d423d9436b6",
    "774cdf7090cea5ec8cffd1461fa929bd200c501cb16997ebe6fb2c669763a015",
    "d516dbecbf6a8cb4d28185bdd60f8faf9c0ceb8e8eabfb987206795e87281310",
}

def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.casefold().encode("utf-8", errors="ignore")).hexdigest()

def is_nsfw_url(url: str) -> bool:
    """Block known adult-domain fingerprints and explicit marker tokens in URLs."""
    try:
        parts = urlsplit(str(url).strip())
        host = (parts.hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    if not host:
        return False
    labels = host.split('.')
    for index in range(len(labels)):
        if _fingerprint(".".join(labels[index:])) in _BLOCKED_HOST_HASHES:
            return True
    markers = re.split(r"[^a-z0-9-]+", host + "/" + parts.path + "?" + parts.query)
    return any(marker and _fingerprint(marker) in _BLOCKED_TOKEN_HASHES for marker in markers)

_KNOWN_LOCAL_HOSTS = {
    "fritz.box", "router.lan", "router.home", "homeassistant.local",
    "home-assistant.local", "nas.local", "synology.local", "printer.local",
}



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
    encoded_target = quote(url, safe="")
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
<a class="button" href="nexlori://browser/retry?url={encoded_target}">Erneut versuchen</a>
<a class="button secondary" href="nexlori://browser/home">Zur Startseite</a>{game}"""
    return _shell(theme, title, body)


def addons_page_html(theme) -> str:
    body = """<span class="eyebrow">Nexlori · Erweiterungen</span><h1>Dein Browser. Deine Add-ons.</h1>
<p>Installiere zusätzliche Erweiterungen aus ZIP-Dateien oder entpackten Ordnern. Nexlori unterstützt derzeit Chromium-Manifest-V3. Lies vor jeder Installation die angeforderten Berechtigungen.</p>
<div class="grid">
<a class="tile" href="nexlori://addons/builtin"><div class="icon">✦</div><strong>Nexlori-Add-ons</strong><p class="muted">Eingebaute Add-ons: dunkle Seiten, Lesemodus, Saubere Links und mehr.</p></a>
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
