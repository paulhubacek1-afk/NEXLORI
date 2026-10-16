# Nexlori – Änderungsprotokoll

## 1.1.0 – Theme-Shop, mehr Add-ons, Titelleiste in Theme-Farben, Animationen

### Neu
- **Theme-Shop** (Menü ⋮ → Theme-Shop, oder Theme-Menü ✦): 41 zusätzliche Themes (Dunkel, Neon, Natur, Edelstein, Hell, Kontrast). Themes werden erst bei der Installation geladen und liegen nur dann auf dem Gerät; sie lassen sich jederzeit entfernen. Ein Theme besteht nur aus Farben, es wird kein Code nachgeladen. Der Katalog (`themes/catalog.json`) wird nur von GitHub über HTTPS geladen und streng geprüft (Namen, Farben, WCAG-Kontrast).
- **11 eingebaute Nexlori-Add-ons** (Menü ⋮ → Nexlori-Add-ons): Dunkle Webseiten, Nachtlicht, Cookie-Banner ausblenden, Video-Geschwindigkeit, Nach-oben-Knopf, Saubere Links (Tracking-Parameter entfernen), HTTPS bevorzugen, Tabs schlafen legen, Lesemodus, Seite als PDF speichern, Screenshot. Alles läuft lokal; Add-ons, die Webseiten verändern, sind standardmäßig aus.
- **Titelleiste in Theme-Farben**: Die Nexlori-Fenster hat jetzt eine eigene Titelleiste mit Symbol, Titel und Fensterknöpfen in den Farben des aktiven Themes. In den Einstellungen lässt sich auf die Windows-Standardleiste zurückschalten (dann wird sie über DWM eingefärbt). Auch Dialoge bekommen auf Windows eine passende Titelleiste.
- **Animationen** (einstellbar: Voll, Reduziert, Aus): fließender Farbverlauf in der Akzentlinie, weicher Theme-Wechsel, gestaffeltes Einblenden der Leisten beim Start, gleitender Ladebalken.
- **Suchleisten-Vorschläge** aus Lesezeichen und den in dieser Sitzung besuchten Seiten (nur im Arbeitsspeicher, nichts wird gespeichert).
- **Sicherheitssymbol** in der Suchleiste (HTTPS / nicht verschlüsselt / interne Seite).
- **Discord-Button** auf der Startseite, im Menü ⋮ und im „Über Nexlori“-Dialog.

### Behoben
- **Die Suchleiste lag unten statt oben**: Die Adress-/Suchleiste befand sich unter der Webseite. Sie sitzt jetzt direkt unter den Tabs.
- **Die Suchleiste blieb bei etwa 220 px stehen** und ignorierte die Einstellung „Suchleistenbreite“. Sie füllt jetzt den Platz bis zur gewählten Breite.
- Die Adresse wurde während des Tippens durch Weiterleitungen überschrieben; Esc stellt die aktuelle Adresse wieder her; der erste Klick markiert die Adresse, weitere Klicks setzen den Cursor; der Löschknopf ist in Theme-Farbe lesbar.
- **HTML5-Vollbild** (z. B. YouTube-Vollbildknopf) tat nichts; es wird jetzt unterstützt.
- Beim Beenden erschien „Release of profile requested but WebEnginePage still not deleted“; Seiten werden jetzt vor dem Profil freigegeben.
- Farbleiste ohne Streifen (z. B. Hell/Dunkel) wurde mit einem ungültigen Ein-Punkt-Verlauf erzeugt.
- Die Startseiten-Kacheln **Add-ons, Heimnetz und Dein Nexlori** (nexlori://-Links) reagierten nicht. Interne Links werden jetzt verarbeitet, und zwar nur von Nexlori-eigenen Seiten, nie von Webseiten.
- Ein ungültiger Escape-Code in der Startseite löste eine Python-Warnung aus.
- Wurde ein installiertes Shop-Theme entfernt, setzte das früher die gesamten Einstellungen zurück; jetzt wird nur das Theme auf „Dunkel“ zurückgesetzt.

### Hinweise
- Der Theme-Shop braucht eine Internetverbindung und lädt den Katalog von `raw.githubusercontent.com`. Bereits installierte Themes funktionieren offline.
- Nicht angeschlossen sind weiterhin der lokale NSFW-Filter (`block_nsfw`), die internen Fehlerseiten (`error_page_html`) und die Registrierung als Windows-Standardbrowser (`register_windows_browser`): Sie sind im Code vorhanden, werden aber nirgends aufgerufen.

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