# Nexlori

**Ein anpassbarer Browser für Gaming, Musik, Individualität und das echte Leben.**

Nexlori soll nicht einfach ein anderer Browser mit neuem Logo sein. Die Idee ist ein Browser mit eigener Identität, einer ruhigen und anpassbaren Oberfläche und Funktionen, die Rücksicht auf RAM, CPU, Akku und Datenverbrauch nehmen.

> **Projektstand:** Nexlori 1.3.0 baut auf Qt WebEngine 6.10+/Chromium auf. Sie enthält eine anpassbare Browserleiste, einstellbare Website-Themes, einen Theme-Shop, eingebaute Add-ons, uBlock Origin Lite, einen MV3-Add-on-Manager, Spotify-Mini-Player, verschlüsselten Passwort-Tresor, Einstellungen und einen Update-Mechanismus. Der Build durchläuft automatische Tests und einen Windows-EXE-Selbsttest. Nicht jede Website oder Erweiterung ist garantiert kompatibel.

## Die Grundidee

Die langfristige Vision ist eine eigenständige, ressourcenschonende Nexlori-Architektur. Damit heute bereits moderne Seiten laufen können, nutzt die ausführbare Browser-Oberfläche Qt WebEngine auf Chromium-Basis; der eigene kleine HTML/CSS-Renderer bleibt als Lern- und Testprojekt erhalten.

Eine Browser-Engine von Grund auf zu entwickeln, ist ein großes Vorhaben. Deshalb soll Nexlori transparent zeigen, welche Webstandards bereits funktionieren und welche noch fehlen, anstatt vollständige Kompatibilität zu versprechen, bevor sie tatsächlich getestet wurde.

## Geplante Funktionen

### Weniger Ressourcenverbrauch

- **Intelligente Tab-Verwaltung:** Inaktive Tabs sollen möglichst wenig CPU und Arbeitsspeicher benötigen.
- **Ressourcenschonender Modus:** Animationen, Hintergrundaktivitäten und automatische Medienwiedergabe sollen sich reduzieren lassen.
- **Akku-Modus:** Auf Laptops sollen unnötige Hintergrundaufgaben nach Möglichkeit reduziert werden.
- **Klare Kontrolle:** Eine übersichtliche Anzeige soll zeigen, welche Tabs besonders viele Ressourcen benötigen, sobald diese Messungen zuverlässig verfügbar sind.

### Gaming-Erkennung und Gaming-Modus

Nexlori soll erkennen können, wann auf dem Gerät gerade gespielt wird, und den Browser darauf einstellen.

- Bei erkanntem Spielstart kann Nexlori optional in einen Gaming-Modus wechseln.
- Unnötige Hintergrundaktivitäten und Animationen sollen reduziert werden.
- Benachrichtigungen können während des Spielens leiser gestellt oder pausiert werden.
- Nach dem Spielen soll Nexlori auf Wunsch wieder zu den normalen Einstellungen zurückkehren.

**Datenschutzprinzip:** Die Erkennung soll freiwillig, transparent und lokal erfolgen. Sie soll keine Spielaktivitäten an einen Server melden. Nutzerinnen und Nutzer müssen die Funktion jederzeit abschalten können. Die konkrete Erkennung hängt vom Betriebssystem und den später verfügbaren Schnittstellen ab.

### Datensparmodus: weniger unnötiger Internetverkehr

Nexlori soll Datenverbrauch reduzieren, ohne ungefragt wichtige Inhalte zu verändern.

- Automatische Medienwiedergabe standardmäßig vermeiden oder kontrollierbar machen.
- Bilder bei Bedarf in einer niedrigeren Qualität laden.
- Tracker und unnötige Drittanbieter-Anfragen nach Möglichkeit blockieren.
- Hintergrundladen und Vorabladen von Seiten kontrollierbar machen.
- Zwischenspeicherung sinnvoll nutzen und den Datenverbrauch verständlich anzeigen.
- Einfache Schalter für den normalen Modus und einen besonders sparsamen Modus anbieten.

Einige Seiten funktionieren mit blockierten Skripten oder Trackern möglicherweise nicht richtig. Deshalb soll der Schutz anpassbar bleiben. Nexlori soll außerdem offen erklären, welche Einsparungen tatsächlich gemessen wurden, statt unbelegte Prozentwerte zu versprechen.

### Musik-Popups und Mediensteuerung

Musik soll nicht jedes Mal den ganzen Bildschirm übernehmen müssen.

- Ein kleines, frei platzierbares Musik-Popup mit Wiedergabe, Pause und Titelsprüngen.
- Schneller Zugriff auf Medien, die in unterstützten Tabs abgespielt werden.
- Einstellbare Position, Größe und Sichtbarkeit des Popups.
- Auf Wunsch dezente Benachrichtigungen beim Titelwechsel.
- Eine Möglichkeit, das Popup vollständig auszuschalten.

Die Bedienung soll nur mit unterstützten Medienquellen funktionieren und keine Musikdienste ohne deren Zustimmung oder Schnittstellen nachahmen.

### LGBTQ+-Themes und persönliche Gestaltung

Nexlori soll ein Browser sein, in dem Menschen ihre Persönlichkeit zeigen können.

- LGBTQ+-Themes, darunter verschiedene Pride-Farbwelten.
- Frei einstellbare Akzentfarben, Hintergründe und Tab-Designs.
- Ruhige, kontrastreiche und dunkle Designs.
- Eigene Themes und Profile, die sich schnell wechseln lassen.
- Keine Pflicht, persönliche Angaben zur Identität zu machen.

### Eine angenehme, zugängliche Oberfläche

- Eine übersichtliche Bedienung ohne unnötige Pop-ups.
- Wahlweise eine ruhige Oberfläche mit wenigen Ablenkungen.
- Anpassbare Animationen, Kontraste, Schriftgrößen und Tastaturbedienung.
- Klare Sprache und nachvollziehbare Einstellungen.
- Datenschutzfreundliche Voreinstellungen und möglichst wenig Telemetrie.

## Leitlinien

1. **Eigenständig:** Die langfristige Vision ist eine eigene Engine und keine umbenannte Chromium- oder Edge-Version.
2. **Ressourcenschonend:** RAM, CPU, Akku und Datenverkehr sollen sparsam eingesetzt werden.
3. **Privatsphäre zuerst:** Gaming-Erkennung und Nutzungsdaten sollen lokal und freiwillig bleiben, wo immer möglich.
4. **Inklusiv:** Themes und Bedienung sollen unterschiedliche Menschen und Bedürfnisse berücksichtigen.
5. **Ehrlich:** Funktionen und Web-Kompatibilität werden erst dann als fertig bezeichnet, wenn sie implementiert und getestet wurden.
6. **Sicher:** Sicherheitsgrenzen, Updates und Schutz vor schädlichen Webseiten sind Voraussetzung für einen öffentlichen Browser.

## Projektstand der Umsetzung

Stand: **Nexlori 1.0.0**. Die Windows-Anwendung nutzt Qt WebEngine 6.10+/Chromium für JavaScript, moderne CSS-Layouts, Bilder, Formulare, Cookies und Local Storage. Einzelne Webseiten können trotzdem spezielle DRM-Komponenten benötigen oder eingebettete Browser blockieren.

### Nexlori für Windows herunterladen

Der Workflow **Windows-EXE** testet den Quellcode, baut die portable Anwendung, startet den EXE-Selbsttest und erstellt ein Installationsprogramm:

- **Installer (empfohlen):** `Nexlori-Setup.exe` installiert Nexlori für den aktuellen Windows-Benutzer und erstellt standardmäßig ein Desktop-Symbol sowie einen Eintrag im Startmenü. Beide verwenden das eingebaute Nexlori-Icon.
- **Portable Version:** `Nexlori.exe` kann direkt aus einem beliebigen Ordner gestartet werden.
- **Prüfsumme:** `Nexlori.exe.sha256` ermöglicht die SHA-256-Prüfung der portablen EXE.

Öffne [GitHub Releases](https://github.com/paulhubacek1-afk/NEXLORI/releases) für veröffentlichte Versionen. Für jede stabile Version wird ein Versions-Tag wie `v1.0.0` gebaut; der Workflow hängt EXE, Prüfsumme und Installer an den Release. In der App lässt sich im Menü manuell nach Updates suchen. Beim Start prüft Nexlori im Hintergrund GitHub Releases. Vor einem automatischen Austausch muss das heruntergeladene Programm zur veröffentlichten SHA-256-Prüfsumme passen.

Die EXE ist nicht digital signiert. Windows kann deshalb beim ersten Start eine SmartScreen-Warnung anzeigen. Einstellungen liegen in `%APPDATA%\\Nexlori\\settings.json`; dein verschlüsselter Passwort-Tresor liegt separat im selben Nexlori-Konfigurationsordner.

### Was vorhanden ist

| Bereich | Stand |
|---|---|
| Browserleiste | Zentrierte, abgerundete Adress-/Suchleiste, einstellbare Breite, Icon-Größe und Schnellzugriffe; Lesezeichenliste direkt unter der Startseiten-Suche; neutrale Startseite ohne Projektwerbung |
| Tabs und Web | Tabs, Zurück/Vorwärts, Neu laden, Startseite, Lesezeichen, Verlauf, Seitensuche, Zoom und Download-Dialog auf Basis von Chromium |
| Themes | Basis-, Gothic-, Cyberpunk-, Wald-, Ozean-, Sakura-, Kaffee- und Mitternacht-Themes plus 60 Pride-Farbwelten für häufige Flaggen aus Gender-, Sexualitäts-, Romantik- und Ace-Spektrum. Drei Pride-Favoriten sind direkt auswählbar. |
| Website-Farben | Das lokale Theme-CSS wird bei jedem neuen Dokument bei DOM-Ready angewendet. Es bleibt optional und lässt sich in den Einstellungen abschalten; Webseiten können bestimmte Stile weiterhin selbst überschreiben. |
| Add-ons | uBlock Origin Lite ist standardmäßig installiert und aktiv. Der Add-on-Manager kann kompatible Manifest-V3-ZIPs und entpackte Ordner installieren, aktivieren, deaktivieren oder entfernen. |
| Spotify | Abtrennbarer Mini-Player mit Spotify-Weboberfläche und Link-Eingabe. Anmeldung und Wiedergabe richten sich nach Spotify und dem jeweiligen Konto. |
| Passwortmanager | Lokaler verschlüsselter Tresor mit Master-Passphrase und Passwortgenerator. Bei passenden HTTPS-Anmeldeformularen kann Nexlori nachfragen, ob der Nutzer die Zugangsdaten verschlüsselt speichern möchte. Ohne Zustimmung wird nicht gespeichert; automatisches Ausfüllen bleibt deaktiviert. |
| Hintergrundbetrieb | Optional beim Schließen im Windows-Infobereich weiterlaufen; über das Tray-Menü erneut öffnen oder vollständig beenden. Falls Windows keinen Infobereich bereitstellt, schließt Nexlori normal. |
| Entwickler | F12 öffnet Chromium-DevTools; separates Diagnosefenster mit Browser-/Engine-Version, Betriebssystem, Renderer-Prozess, Tabs, Profilpfaden und Schutzstatus. |
| Standardbrowser | In den Einstellungen „Standardbrowser“ wählen und anschließend die HTTP-/HTTPS-Zuordnung in den Windows-Einstellungen bestätigen. |
| Updates | Automatischer oder manueller Release-Check, Download über HTTPS, SHA-256-Prüfung und Windows-Selbstupdate. Stabile Releases werden automatisch erstellt; fortlaufende CI-Builds sind als Vorab-Releases markiert. |
| Feedback | [GitHub-Probleme und Verbesserungen](https://github.com/paulhubacek1-afk/NEXLORI/issues/new) oder E-Mail an [nexlori-browser@gmx.at](mailto:nexlori-browser@gmx.at). |

Nexlori 1.3.0 ist weiterhin nicht unabhängig sicherheitszertifiziert. Die Anmeldeerkennung ist ein Komfortmerkmal, keine Garantie, dass jedes Login-Formular erkannt wird. Automatisches Einfüllen von Passwörtern ist noch nicht aktiviert. Verwende ihn nicht als einzigen Passwortmanager für besonders sensible Konten oder Online-Banking. Qt WebEngine unterstützt derzeit Manifest-V3-Erweiterungen; deshalb wird uBlock Origin Lite und nicht die separate Manifest-V2-Version eingebunden. Siehe [Änderungsprotokoll](CHANGELOG.md).

### Entwickeln

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev,gaming]"
nexlori gui                                          # Fenster starten (optional mit Adresse)
nexlori render examples/hello.html examples/hello.png
pytest                                               # Fenster-Tests laufen nur mit Display (Windows oder xvfb-run)
pip install pyinstaller && python packaging/build_exe.py   # baut dist/Nexlori(.exe)
```

### Theme-Shop und eingebaute Add-ons (ab 1.1.0)

- **Theme-Shop:** zusätzliche Themes nach Bedarf installieren und wieder entfernen. Der Katalog liegt in `themes/catalog.json` und wird mit `python packaging/make_theme_catalog.py` erzeugt und geprüft (WCAG-Kontrast, gültige Namen, keine Überschneidung mit eingebauten Themes). Ein neues Theme besteht nur aus Farben und wird per Pull Request ergänzt.
- **Eingebaute Add-ons:** Dunkle Webseiten, Nachtlicht, Cookie-Banner ausblenden, Video-Geschwindigkeit, Nach-oben-Knopf, Saubere Links, HTTPS bevorzugen, Tabs schlafen legen, Lesemodus, PDF-Export und Screenshot. Sie laufen lokal und senden nichts.
- **Titelleiste in Theme-Farben** und einstellbare **Animationen** (Voll, Reduziert, Aus).
- **Community:** [Nexlori auf Discord](https://discord.com/invite/KM5m7s9GyK).

### GUI-Tests (optional, lokal)

Die Tests des kompletten Browserfensters starten Chromium und laufen deshalb nur auf Wunsch:
`NEXLORI_GUI_TESTS=1 python -m pytest tests/test_qt_window.py` (unter Linux zusätzlich `QT_QPA_PLATFORM=offscreen`).

## Roadmap

- [x] Projektstruktur und technische Architektur dokumentieren ([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md))
- [ ] Zielplattform und erste unterstützte Webstandards festlegen
- [x] Eigenständigen, experimentellen Rendering-Prototyp entwickeln (erste Stufe: Teilmenge von HTML/CSS → Bild)
- [ ] Netzwerkzugriff, Zertifikatsprüfung und Sicherheitskonzept entwerfen
- [ ] Messungen für RAM-, CPU- und Datenverbrauch integrieren
- [ ] Datenschutzfreundlichen Datensparmodus entwickeln
- [ ] Musik-Popup und Mediensteuerung umsetzen
- [ ] Freiwillige lokale Gaming-Erkennung erforschen
- [ ] LGBTQ+-Themes und barrierearme Oberflächen entwickeln
- [ ] Tests, Sicherheitsprüfungen und transparente Kompatibilitätsübersicht aufbauen

Die Reihenfolge kann sich während der Entwicklung ändern. Sicherheit und eine nachvollziehbare technische Grundlage haben Vorrang vor einer langen Feature-Liste.

## Mitmachen

Ideen, Fehlerberichte und Verbesserungsvorschläge sind willkommen. Bitte kennzeichne in Vorschlägen klar, ob es um eine bereits vorhandene Funktion oder um einen zukünftigen Wunsch geht.

**Nexlori – dein Browser, deine Ressourcen, dein Stil.**

### Webseiten-Themes

Mit der Schaltfläche **Aa** kannst du die Farben einer geöffneten Website an dein aktives Nexlori-Theme anpassen. Das lokale Stylesheet wird nur im Browser angewendet und nicht an die Website gesendet. Manche Seiten können dadurch anders aussehen; der Schalter lässt sich jederzeit deaktivieren.

Die Oberfläche bietet unter anderem Gothic, Cyberpunk, Kaffee, Wald, Ozean, Sakura, Mitternacht sowie Pride-Themes für Gay, Regenbogen, Trans, Bi, Pan, Lesben, Genderfluid, Nichtbinär, Asexuell, Aromantisch und Queer.
