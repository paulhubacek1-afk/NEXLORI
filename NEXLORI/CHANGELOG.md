# Nexlori – Änderungsprotokoll

## 1.1.0 – Theme-Galerie, neue Looks und Werbeblocker-Status

- Neue Theme-Galerie auf GitHub Pages mit direkter Aktivierung aus Nexlori; es werden keine Theme-ZIP-Dateien in den Download-Ordner geschrieben.
- Elf zusätzliche Farbwelten: Mitternachtslila, Neon-Grün, Galaxie, Vulkan, Monochrom, Bubblegum, Zitrus, Eisblau, Café Creme, Retro Wave und Ozean Hell.
- Neues Schutzsymbol in der Browserleiste zeigt den Lade- und Aktivierungsstatus von uBlock Origin Lite und ermöglicht das Ein-/Ausschalten.
- Verbesserte Rückmeldung bei fehlendem uBlock-Paket und nach der Installation.
- Neues Tab-Plus an das rechte Ende der oberen Tab-Leiste versetzt.
- Native Windows-Titelleiste passt Hintergrund-, Text- und Rahmenfarbe an das aktive Nexlori-Theme an, sofern Windows die entsprechenden DWM-Attribute unterstützt.
- Cookie-Banner-Hilfe klickt nur eindeutig beschriftete Ablehnen- oder „nur notwendige Cookies“-Schaltflächen; sie akzeptiert nie allgemein alle Cookies und entfernt Banner nicht ohne Ablehnungsaktion.
- Inaktive Tabs werden nach einer einstellbaren Wartezeit eingefroren, wenn Qt dies als sicher empfiehlt. Tabs mit laufendem Audio und ladende Tabs werden geschont.
- Tracking-Parameter wie utm_*, fbclid und gclid werden aus eingegebenen Adressen und angeklickten Links entfernt.
- Erzwungener Chromium-Dunkelmodus für Webseiten, in den Einstellungen abschaltbar.
- Medien-Mini-Player ergänzt: Audio/Video aus dem aktiven Browser-Tab pausieren/fortsetzen, um 10 Sekunden springen und Lautstärke anpassen.
- Medienwiedergabe kann auf Nutzeraktionen beschränkt werden.
- Version auf 1.1.0 erhöht. Der Windows-Build und alle Tests müssen vor einem stabilen Release erfolgreich sein.

## 1.0.2 und frühere Versionen

Die bisherigen Versionen enthalten Chromium-WebEngine, Browser-Tabs, Such-/Adressleiste, Website-Theme-CSS, den MV3-Add-on-Manager, uBlock Origin Lite, Theme-Mischungen, Spotify-Mini-Player, einen verschlüsselten Passwort-Tresor, Update-Prüfung und den Windows-Installer.

### Hinweise

- Qt WebEngine unterstützt Manifest V3; nicht jede Erweiterung oder Website ist kompatibel.
- Der Werbeblocker kann Werbung und Tracker reduzieren, garantiert aber keine vollständige Blockierung auf jeder Website.
- Der Browser und der Passwortmanager wurden nicht unabhängig sicherheitszertifiziert.
