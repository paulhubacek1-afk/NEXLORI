# NEXLORI 1.1.0

Nexlori ist ein anpassbarer Windows-Browser auf Basis von Qt WebEngine/Chromium. Die erste offizielle Version enthält Themes, einen Add-on-Manager mit uBlock Origin Lite, einen Spotify-Mini-Player, einen verschlüsselten Passwort-Tresor und automatische Updates.

## Windows-Download

- **Empfohlen:** [GitHub Releases](https://github.com/paulhubacek1-afk/NEXLORI/releases) öffnen und `Nexlori-Setup.exe` starten. Der Installer erstellt ein Desktop-Symbol mit Nexlori-Icon und einen Startmenü-Eintrag.
- **Portable Version:** `Nexlori.exe` direkt starten.
- **Prüfsumme:** `Nexlori.exe.sha256` enthält die SHA-256-Prüfsumme der portablen EXE.

## Enthaltene Funktionen

- Theme-Galerie über GitHub Pages mit direkter Theme-Aktivierung aus Nexlori.
- Elf zusätzliche Themes und themeabhängige Windows-Titelleiste.
- Sichtbarer Status des uBlock-Origin-Lite-Werbeblockers in der Browserleiste.

- Chromium-WebEngine für moderne Websites, JavaScript, CSS, Bilder und Formulare.
- Anpassbare Suchleiste, Icon-Größe, sichtbare Schnellzugriffe und Suchmaschine.
- Website-Themes mit optionalem CSS bei jedem neuen Dokument.
- 60 Pride-Farbwelten und drei persönliche Favoriten.
- uBlock Origin Lite als standardmäßig aktivierbares Manifest-V3-Add-on sowie ein Manager für weitere kompatible Erweiterungen.
- Einstellungen für Themes, Add-ons, Pop-ups, Zoom und automatische Update-Prüfung.
- Spotify-Mini-Player, Lesezeichen, Verlauf, Downloads, Seitensuche und Zoom.
- Verschlüsselter Passwort-Tresor und Passwortgenerator.
- HTTPS-Update-Download mit SHA-256-Prüfung; stabile Releases werden automatisch erstellt.

Der Installer erzeugt das Desktop-Symbol sofort bei der Installation. Bei selbstständigen Builds kann Windows eine SmartScreen-Warnung zeigen, weil die EXE derzeit nicht digital signiert ist.

**Hinweis:** Qt WebEngine unterstützt nur Manifest V3, daher wird uBlock Origin Lite verwendet. Nicht jede Website oder jedes Add-on funktioniert im eingebetteten Browser. Der Passwortmanager füllt Zugangsdaten noch nicht automatisch in Websites ein und wurde nicht unabhängig sicherheitszertifiziert.

## Feedback

Fehler, Anliegen und Verbesserungen bitte über [GitHub Issues](https://github.com/paulhubacek1-afk/NEXLORI/issues/new) oder per E-Mail an [nexlori-browser@gmx.at](mailto:nexlori-browser@gmx.at) melden.

Die ausführliche Projektdokumentation steht in [NEXLORI/README.md](NEXLORI/README.md), Änderungsnotizen in [NEXLORI/CHANGELOG.md](NEXLORI/CHANGELOG.md).
