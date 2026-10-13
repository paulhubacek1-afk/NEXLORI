# Kompatibilitätsübersicht (Prototyp 0.2.0)

Ehrlich und überprüfbar: ✅ = implementiert **und** durch Tests abgedeckt · 🟡 = teilweise ·
❌ = nicht unterstützt (wird ignoriert oder fällt auf einen einfachen Ersatz zurück).

Diese Übersicht beschreibt den Prototyp. Es wird **keine** Konformität zu WHATWG/W3C-Standards behauptet;
die Web Platform Tests werden noch nicht ausgeführt. Getestet wurde mit selbst geschriebenen Seiten und einem lokalen
Testserver – **nicht gegen reale Webseiten**. Rückmeldungen, welche Seiten wie aussehen, sind willkommen.

## HTML

| Merkmal | Status | Hinweis / Test |
|---|---|---|
| Elemente, Attribute (quoted/unquoted), Text, Kommentare, Doctype | ✅ | `tests/test_dom.py` |
| Zeichenreferenzen (`&amp;`, `&auml;`, `&#228;` …) | ✅ | über die Entity-Tabelle der Standardbibliothek |
| Void-/selbstschließende Elemente | ✅ | |
| Implizite End-Tags für `<p>` und `<li>` | ✅ | andere implizite End-Tags (Tabellen, `dd`/`dt`, `option` …) ❌ |
| Fehlertoleranz (verwaiste End-Tags, unbeendete Elemente) | 🟡 | einfache Strategie, nicht der WHATWG-Algorithmus |
| `<script>`/`<style>` als Rohtext lesen | ✅ | Skripte werden **nicht** ausgeführt ❌ |
| `<style>`-Blöcke | ✅ | `<link rel="stylesheet">` ❌ (kein Netzwerk) |
| Bilder, Audio/Video, Canvas, SVG, iframes | ❌ | werden nicht dargestellt |
| `hidden`-Attribut; `video`, `audio`, `canvas`, `svg`, `iframe`, `object`, `select`, `textarea` | ✅ | werden ausgeblendet (`tests/test_engine_browser_features.py`) |
| Tabellen | 🟡 | Zeilen und Zellen erscheinen als Blöcke untereinander, kein Spaltenlayout |
| Formulare/Eingabeelemente | ❌ | Felder und Schaltflächen ohne Funktion |
| `<hr>`, `<center>`, `<small>`, `<dl>`/`<dd>` | ✅ | einfache Standarddarstellung |
| Links (`<a href>`) | ✅ | anklickbar; nur `http`, `https` und interne Seiten; `javascript:`, `mailto:`, `data:` und Verweise von Webseiten auf `file:` werden blockiert |
| `<pre>` / Leerraum erhalten | ❌ | Leerraum wird immer kollabiert |
| Zeichenkodierung | ✅ | aus HTTP-Header oder `<meta charset>`, sonst UTF-8; ungültige Bytes werden ersetzt |

## CSS

| Merkmal | Status | Hinweis / Test |
|---|---|---|
| Selektoren: Typ, Klasse, ID, `*`, Liste, Nachfahre, Kind (`>`) | ✅ | `tests/test_css.py` |
| Pseudoklassen/-elemente, Attributselektoren, `+`/`~` | ❌ | Regel wird verworfen |
| Kaskade: UA → Autor → `style`-Attribut, Spezifität, Reihenfolge, `!important` | ✅ | |
| Vererbung (Farbe, Schrift, Ausrichtung, Zeilenhöhe) | ✅ | |
| `@media`, `@import`, `@font-face`, `var()`, `calc()`, `inherit`/`initial` | ❌ | `@`-Regeln werden übersprungen |
| Einheiten `px`, `em`, `rem`, `pt` | ✅ | `%` nur bei `width` und `font-size` |
| `display`: `block`, `inline`, `list-item`, `none` | ✅ | `inline-block` wird wie `inline` behandelt |
| `color`, `background`/`background-color` | ✅ | Farben: Name (Grundfarben), `#rgb`, `#rrggbb`, `rgb()` |
| `font-size`, `font-weight` (fett/normal) | ✅ | feste Schriftfamilie, kein Kursiv, keine Zwischenstufen |
| `text-align` (`left`/`center`/`right`), `text-decoration: underline`, `line-height` | ✅ | `justify` ❌ |
| `margin`, `padding` (Kurzform und je Seite), `margin: auto` horizontal | ✅ | |
| `border` | 🟡 | einheitlich auf allen Seiten, alle Stile werden durchgezogen gezeichnet |
| `width`, `height` | 🟡 | `box-sizing` ist immer `content-box`; kein `min-`/`max-` |
| `float`, `position`, `flex`, `grid`, `overflow`, `z-index`, `opacity` | ❌ | Seiten, die darauf aufbauen, sehen anders aus |
| `font-family`, `font-style`, `text-transform`, `letter-spacing`, `vertical-align` | ❌ | |
| `border-radius`, `box-shadow`, Verläufe, `background-image` | ❌ | |
| Animationen, Übergänge | ❌ | |

## Layout und Darstellung

| Merkmal | Status | Hinweis / Test |
|---|---|---|
| Block-Fluss, vertikales Stapeln | ✅ | `tests/test_layout.py` |
| Zeilenumbruch an Leerzeichen, `<br>`, überlange Wörter | ✅ | kein Silbentrennen, keine bidirektionalen Texte, kein CJK-Umbruch |
| Margin-Kollaps | 🟡 | nur zwischen benachbarten Geschwistern, nicht Eltern/Kind |
| Listenmarker (`•`, `1.`) | ✅ | nur `ul`/`ol`, keine `list-style`-Varianten |
| Inline-Elemente mit eigenem Padding/Margin/Hintergrund | ❌ | werden ignoriert |
| Rechtecke, Rahmen, Text, Unterstreichung zeichnen | ✅ | `tests/test_paint_cli.py` |
| Canvas-Hintergrund aus `html`/`body` | ✅ | |

## Zoom und Bildschirmskalierung

| Merkmal | Status | Hinweis / Test |
|---|---|---|
| Seitenzoom (Strg + Mausrad / `+` / `-` / `0`) | ✅ | skaliert alle absoluten Längen und Schriften; `tests/test_engine_browser_features.py` |
| Windows-Bildschirmskalierung (125 %, 150 % …) | 🟡 | wird beim Start übernommen; nicht auf allen Monitor-Konstellationen getestet (kein Wechsel zwischen Monitoren zur Laufzeit) |

## Netzwerk

| Merkmal | Status | Hinweis / Test |
|---|---|---|
| `http` / `https` laden | ✅ | `tests/test_net.py` (gegen lokalen Testserver) |
| Zertifikatsprüfung | ✅ | durch `ssl` mit dem Zertifikatsspeicher des Betriebssystems; bei Fehlern wird **nie** fortgefahren |
| Weiterleitungen | ✅ | nur zu `http`/`https` |
| `gzip`-Kompression | ✅ | Entpacken mit Größenlimit (Schutz vor Zip-Bomben) |
| Größenlimit (3 MB), Zeitlimit (15 s) | ✅ | Seite wird gekürzt bzw. Fehlerseite angezeigt |
| Fehlerseiten des Servers (404 usw.) | ✅ | werden dargestellt, Status steht in der Statuszeile |
| Nicht-HTML-Inhalte (Bilder, PDFs, Downloads) | ❌ | verständliche Fehlermeldung |
| Cookies, Logins, HTTP-Cache, HTTP/2, Proxys mit Anmeldung | ❌ | Cookies werden bewusst nicht gespeichert |
| Externe Stylesheets, Bilder, Skripte | ❌ | es wird nur das HTML-Dokument selbst geladen |
