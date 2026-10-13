"""Eingebaute Seiten (about:...) und Hilfsfunktionen zum Erzeugen von Anzeige-HTML."""
from __future__ import annotations

import html as _html

from . import __version__

_BASE_STYLE = """
<style>
  body { background: #ffffff; color: #1a1a1f; margin: 24px }
  h1 { color: #4533d6 }
  h2 { color: #333344 }
  a { color: #4533d6 }
  .hint { background: #f0f0f4; border: 1px solid #c9c9d6; padding: 8px 14px; margin: 14px 0 }
  .err { background: #fff0f0; border: 1px solid #d99; padding: 8px 14px; margin: 14px 0 }
</style>
"""

START_HTML = f"""<!doctype html><html><head><title>Nexlori</title>{_BASE_STYLE}</head><body>
<h1>Nexlori</h1>
<p>Willkommen bei Nexlori {__version__} &ndash; einem eigenständigen, ressourcenschonenden Browser
(Entwicklungsstand: <b>Prototyp</b>).</p>
<div class="hint"><b>Gut zu wissen:</b>
 Nexlori zeigt HTML und einfaches CSS. <b>JavaScript wird nicht ausgeführt</b> und <b>Bilder werden noch nicht
 geladen</b>. Viele moderne Webseiten sehen deshalb anders aus oder funktionieren nicht.</div>
<h2>Zum Ausprobieren</h2>
<ul>
<li><a href="about:test">Interne Testseite</a> (zeigt, was der eigene Renderer kann)</li>
<li><a href="https://example.org/">example.org</a></li>
<li><a href="https://de.wikipedia.org/">de.wikipedia.org</a></li>
<li><a href="https://github.com/paulhubacek1-afk/NEXLORI">Nexlori auf GitHub</a></li>
</ul>
<h2>Tastenkürzel</h2>
<ul>
<li>Strg+L: Adressleiste &middot; Strg+T: neuer Tab &middot; Strg+W: Tab schließen</li>
<li>F5: neu laden &middot; Alt+Pfeil links/rechts: zurück/vor</li>
<li>Strg+Mausrad oder Strg+Plus/Minus: Zoom &middot; Strg+0: Zoom zurücksetzen</li>
<li>Strg+Klick auf einen Link: in neuem Tab öffnen</li>
</ul>
<h2>Datenschutz und Sicherheit</h2>
<ul>
<li>Keine Telemetrie. Es werden keine Cookies gespeichert.</li>
<li>Die Gaming-Erkennung ist standardmäßig aus, läuft nur lokal und kann im Menü aktiviert werden.</li>
<li>Noch ohne Sandbox: <b>nicht für Online-Banking oder andere sensible Seiten verwenden.</b></li>
</ul>
</body></html>"""

TEST_HTML = f"""<!doctype html><html><head><title>Nexlori Testseite</title>
<style>
  body {{ background: #15131a; color: #f3f1f7; }}
  h1 {{ color: #ff8c00; }}
  .card {{ background: #201d28; border: 2px solid #5bcefa; padding: 12px 16px; margin: 16px 0; }}
  .center {{ text-align: center; }}
  a {{ color: #f5a9b8; }}
  .box {{ width: 300px; margin: 0 auto; background: #5bcefa; color: #15131a; padding: 8px; }}
</style></head><body>
<h1>Hallo Nexlori</h1>
<p>Dieser Absatz wird vom <b>eigenen Renderer</b> gezeichnet: HTML-Parser, CSS-Kaskade,
Block- und Inline-Layout &ndash; ohne Chromium, Electron oder WebView.</p>
<div class="card"><h3>Karte mit Rahmen</h3>
<p>Zeile eins<br>Zeile zwei mit <a href="about:start">Link zur Startseite</a> und <strong>fettem Text</strong>.</p></div>
<ul><li>Ressourcenschonend</li><li>Datensparsam</li><li>Individuell</li></ul>
<ol><li>Erster Punkt</li><li>Zweiter Punkt</li></ol>
<p class="center">Zentrierter Text</p>
<div class="box">Zentrierte Box mit fester Breite</div>
<p>Version {__version__}</p>
</body></html>"""

BLANK_HTML = "<!doctype html><html><head><title>Leere Seite</title></head><body></body></html>"

ABOUT_PAGES = {"about:start": START_HTML, "about:test": TEST_HTML, "about:blank": BLANK_HTML}


def error_html(url: str, message: str) -> str:
    return (
        f"<!doctype html><html><head><title>Fehler</title>{_BASE_STYLE}</head><body>"
        f"<h1>Die Seite konnte nicht geladen werden</h1>"
        f'<div class="err">{_html.escape(message)}</div>'
        f"<p>Adresse: {_html.escape(url)}</p>"
        f'<p><a href="about:start">Zur Startseite</a></p></body></html>'
    )


def text_to_html(text: str) -> str:
    """Reiner Text (text/plain) als einfache HTML-Seite; Zeilenumbrüche bleiben erhalten."""
    body = "<br>".join(_html.escape(line) for line in text.splitlines())
    return f"<!doctype html><html><body>{body}</body></html>"
