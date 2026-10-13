# Nexlori – Änderungsprotokoll

## 1.0.1 – Startstabilität und Release-Prüfungen

- Der Windows-Build prüft zusätzlich, ob sich das tatsächliche Browserfenster öffnen lässt, statt nur interne Komponenten zu testen.
- Ein Startfehler, ein sofort beendeter Prozess oder ein fehlendes Fenster lässt den Release-Build jetzt fehlschlagen.
- Versionsnummer auf 1.0.1 für den korrigierten Build angehoben.


## 1.0.0 – Erste offizielle Windows-Version

- Chromium-basierter Browser mit Tabs, Adress-/Suchleiste, Lesezeichen, Verlauf, Downloads, Seitensuche und Zoom.
- Überarbeitete, anpassbare Browserleiste: Suchleistenbreite, Icon-Größe, sichtbare Schnellzugriffe und Suchmaschine.
- Website-Theme-CSS wird auf jedem Dokument bei DOM-Ready eingesetzt und kann in den Einstellungen abgeschaltet werden.
- 60 Pride-Farbwelten, darunter Gay, Trans, Bi, Pan, Asexuell, Aromantisch, Genderfluid, Intersex und weitere; drei Favoriten stehen im Theme-Menü bereit.
- uBlock Origin Lite wird als offizielles Manifest-V3-Add-on mitgeliefert und bei einem neuen Profil standardmäßig aktiviert. Der Schalter ist in Einstellungen und Add-on-Verwaltung verfügbar.
- Add-on-Manager für kompatible Manifest-V3-ZIP-Dateien und entpackte Ordner; Add-on-Berechtigungen werden vor dem Import angezeigt.
- Einstellungen für Seitenthemes, Werbe-/Trackerschutz, automatische Update-Prüfung, Pop-ups, Zoom und Suchmaschine.
- Spotify-Mini-Player, verschlüsselter Passwort-Tresor, Passwortgenerator und Feedback-Links.
- Windows-Setup erstellt ein Desktop-Symbol mit Nexlori-Icon und einen Startmenü-Eintrag.
- Automatische GitHub-Releases, Build-Prüfungen, EXE-Selbsttest und SHA-256-Prüfung für Updates.

### Hinweise

- Qt WebEngine unterstützt nur Manifest V3. Deshalb wird uBlock Origin Lite und nicht die separate Manifest-V2-Version von uBlock Origin eingebunden.
- Nicht jede Erweiterung ist kompatibel, und nicht jede Website funktioniert in einem eingebetteten Chromium-Browser.
- Der Passwortmanager füllt Zugangsdaten noch nicht automatisch in Websites ein.
- Der Browser und der lokale Passwortmanager wurden nicht unabhängig sicherheitszertifiziert.