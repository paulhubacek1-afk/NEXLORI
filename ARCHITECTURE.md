# Architektur (Stand: Prototyp 0.2.0)

Nexlori ist ein Entwicklungsprojekt. Dieses Dokument beschreibt, **was heute existiert** und
**wie es später wachsen soll** – und trennt beides bewusst.

## Was der Prototyp ist (und nicht ist)

Der Code unter `src/nexlori/` ist ein **experimenteller, in Python geschriebener Prototyp** mit Fenster-Oberfläche
(Tkinter), der als `Nexlori.exe` gebaut werden kann. Er dient dazu, die Architektur zu validieren, Datenflüsse
festzulegen und Verhalten testbar zu machen, bevor eine performante, sichere Engine in einer Systemsprache entsteht.
Er ist **kein Alltagsbrowser**: kein JavaScript, keine Bilder, keine Cookies/Logins, keine Prozess-Isolation.

Nicht verwendet werden (und nicht geplant): Chromium, Edge, Electron, CEF, WebView2.
Abhängigkeiten: **Pillow** (Zeichnen, Schriften, Anzeige in Tk), **Tkinter** (Fenster; Teil von Python) und die
Entity-Tabelle der Python-Standardbibliothek (`html.unescape`). TLS und Zertifikatsprüfung kommen aus der
Standardbibliothek (`ssl`, `urllib`). Optional: `psutil` für die lokale Prozesserkennung.

## Schichten

```
┌──────────────────────────────────────────────────────────────┐
│ gui.py        Fenster: Tabs · Adressleiste · Menü · Ansicht  │
├──────────────────────────────────────────────────────────────┤
│ browser.py    Sitzung: Adresseingabe · Verlauf · Seite laden │
├───────────────────────────────┬──────────────────────────────┤
│ core/   Browser-Logik         │ net.py  http/https-Abruf     │
│ modes · tabs · datasaver ·    │ (TLS über ssl/Betriebssystem)│
│ gaming · media · themes ·     │                              │
│ settings                      │                              │
├───────────────────────────────┴──────────────────────────────┤
│ engine/  Rendering: dom → css → layout → paint               │
├──────────────────────────────────────────────────────────────┤
│ Sandbox · Prozess-Isolation · Updates  (noch nicht vorhanden)│
└──────────────────────────────────────────────────────────────┘
```

**Threads:** Seiten laden und Layout laufen in Daemon-Threads, Ergebnisse kommen über eine Queue zurück in den
Tk-Thread (Tk wird nur dort angefasst). Ein hängender Abruf kann das Beenden nie blockieren. Schriftobjekte und
`Document.layout` sind durch Sperren geschützt.

**Anzeige:** Tk zeigt nur den sichtbaren Ausschnitt an. `paint(layout, top=…, height=…)` zeichnet genau diesen
Ausschnitt; lange Seiten bleiben dadurch schnell und speicherschonend.

**Ruhezustand:** Inaktive Tabs geben beim Schlafenlegen ihr Dokument und Layout frei und laden beim Zurückwechseln neu.

### `engine/` – von HTML zum Bild

| Schritt | Modul | Aufgabe |
|---|---|---|
| 1 | `dom.py` | Eigener Tokenizer + DOM-Aufbau (Teilmenge des HTML-Parsings) |
| 2 | `css.py` | CSS-Parser, Selektoren, Kaskade (UA → Autor → inline, Spezifität, `!important`), berechnete Stile |
| 3 | `layout.py` | Block-/Inline-Fluss, Zeilenumbruch, Margin-Kollaps zwischen Geschwistern → **Display-Liste** (`Rect`, `Border`, `Text`) |
| 4 | `paint.py` | Display-Liste → Pillow-Bitmap |

Das Layout kennt Pillow nicht: Textbreiten kommen über das Interface `Metrics`. Dadurch ist das Layout
mit einer deterministischen Ersatz-Metrik (`MonospaceMetrics`) exakt testbar. Die Display-Liste ist die
Schnittstelle zu einem späteren GPU-/Fenster-Painter.

### `net.py`, `browser.py`, `gui.py`

| Modul | Aufgabe | Wichtige Entwurfsentscheidung |
|---|---|---|
| `net.py` | Seiten per `http`/`https` laden | Nur diese Schemata, Weiterleitungen nur dorthin; Größen-/Zeitlimits; gzip mit Zip-Bomben-Schutz; **keine Cookies**; fehlgeschlagene Zertifikatsprüfung wird nie umgangen |
| `browser.py` | Adresseingabe (Adresse/Datei/Suche), Link-Auflösung, Seiten laden, Verlauf, Tabs | Fehler werden zu Fehlerseiten, nie zu Abstürzen; `javascript:`/`mailto:`/`data:` und Verweise von Webseiten auf `file:` werden blockiert |
| `gui.py` | Fenster (Tkinter), Tastenkürzel, Menü | Keine Fachlogik in der Oberfläche: Modi, Verlauf und Ruhezustand liegen in `core/` und `browser.py` und sind ohne Display testbar |
| `gui_main.py` | Einstiegspunkt, `--selftest` | Der Selbsttest läuft in der CI gegen die **gebaute EXE** und prüft Renderer, Schriften, Tk und Pillows Tk-Anbindung |

### `core/` – Verhalten der Funktionen aus der README

| Modul | Funktion | Wichtige Entwurfsentscheidung |
|---|---|---|
| `modes.py` | Normal / Ressourcenschonend / Akku / Gaming als `PerformanceProfile` | Gaming überlagert den Basismodus und kehrt (auf Wunsch) zurück |
| `tabs.py` | Ruhezustand inaktiver Tabs, Ressourcenbericht | Aktive, angeheftete und tonausgebende Tabs schlafen nie; nicht gemessene Tabs werden als „nicht gemessen“ ausgewiesen statt zu raten |
| `datasaver.py` | Anfragen-Filter (Tracker, Autoplay, Vorabladen, strikt) + Einsparungsbuch | Es zählen nur **gemessene** Bytes; Ausnahmeliste je Seite, weil Blockieren Seiten kaputt machen kann |
| `gaming.py` | Lokale, freiwillige Spieleerkennung | Standard **aus**; solange aus, wird die Prozessliste nicht gelesen; Hysterese gegen Flackern; kein Netzwerkcode |
| `media.py` | Musik-Popup-Modell und Steuerung | Es werden nur Quellen mit Steuerschnittstelle akzeptiert; Popup vollständig abschaltbar |
| `themes.py` | 4 Basis- und 7 Pride-Themes, eigene Themes | Jedes Theme wird gegen WCAG-Kontrast (4,5:1 Text / 3:1 Bedienelemente) geprüft; eigene Themes unter dem Minimum werden abgelehnt |
| `settings.py` | Einstellungen als JSON | Datenschutzfreundliche Voreinstellungen; **es gibt kein Telemetrie-Feld** (per Test abgesichert) |

## Sicherheit und Datenschutz – ehrlicher Stand

Heute ist der Prototyp kein Sicherheitsprodukt und darf **nicht** für nicht vertrauenswürdige Webinhalte
eingesetzt werden. Voraussetzungen für einen öffentlichen Browser, die noch fehlen:

1. **Netzwerkschicht** – *teilweise vorhanden*: TLS und Zertifikatsprüfung laufen über `ssl` und den Zertifikatsspeicher
   des Betriebssystems (Kryptografie wird nicht selbst geschrieben). Es fehlen Cookies/Logins, Cache und eine eigene
   Richtlinie für Unterressourcen.
2. **Prozess-Isolation / Sandbox**: Rendering in eigenen Prozessen mit minimalen Rechten.
3. **Update-Mechanismus** für Sicherheitsfixes.
4. **Schutz vor schädlichen Seiten** (z. B. Safe-Browsing-ähnliche Listen, lokal prüfbar).
5. **Sicherheitsprüfung** des Parsers (Fuzzing), weil Parser die typische Angriffsfläche sind.

Datenschutz ist dagegen schon im Prototyp verankert: keine Telemetrie, Gaming-Erkennung opt-in und lokal,
Themes ohne Angaben zur Person.

## Offene Entscheidungen (bitte bewusst treffen)

- **Sprache der echten Engine** (z. B. Rust oder C++). Der Python-Prototyp ist nicht für Performance gedacht;
  die Tests und die Display-Listen-Schnittstelle lassen sich aber als Spezifikation weiterverwenden.
- **Zielplattform(en)** und Fenster-/GPU-Technik.
- **Scope von JavaScript**: Eine eigene JS-Engine ist ein Projekt für sich; Alternativen müssen zur Leitlinie
  „eigenständig“ passen und offen dokumentiert werden.

## Tests

`pytest` führt alle Tests aus (CI: `.github/workflows/tests.yml`). Die Engine wird über die Display-Liste getestet,
die Kernlogik über reine Funktionen/Objekte mit injizierten Quellen (Prozessliste, Medienquelle) –
so läuft alles ohne Betriebssystem-Abhängigkeit. Die Fenster-Tests (`tests/test_gui.py`) brauchen ein Display und werden sonst übersprungen (Windows-CI; lokal z. B. `xvfb-run -a pytest`). Welche Webstandards unterstützt sind, steht in
[`COMPATIBILITY.md`](COMPATIBILITY.md).

## Windows-EXE

`packaging/build_exe.py` ruft PyInstaller (`--onefile --windowed`) auf; der Workflow `.github/workflows/build-windows.yml`
führt auf einem Windows-Runner nacheinander aus: Tests → Icon erzeugen → EXE bauen → **Selbsttest der EXE** →
SHA-256-Prüfsumme → Artefakt (bei einem `v*`-Tag zusätzlich ein GitHub-Release). Das Icon wird aus `nexlori/icon.py`
gezeichnet, es liegt keine Binärdatei im Repository. Die EXE ist unsigniert (SmartScreen-Hinweis beim ersten Start).
