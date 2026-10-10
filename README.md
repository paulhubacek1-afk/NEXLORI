# Noctra Browser

**Ein eigenständiger, ressourcenschonender Browser für Gaming, Musik, Individualität und das echte Leben.**

Noctra Browser soll nicht einfach ein anderer Browser mit neuem Logo sein. Die Idee ist ein Browser mit eigener Identität, einer ruhigen und anpassbaren Oberfläche und Funktionen, die Rücksicht auf RAM, CPU, Akku und Datenverbrauch nehmen.

> **Wichtig zum Projektstand:** Noctra ist derzeit ein Entwicklungsprojekt. Die Funktionen in dieser README beschreiben die Vision und Roadmap; sie sind noch nicht automatisch bereits implementiert oder einsatzbereit.

## Die Grundidee

Noctra soll eine **eigene Browser-Engine** erhalten. Das Projekt soll nicht einfach Microsoft Edge, Chromium, Electron, CEF oder WebView2 umverpacken. Ziel ist eine eigenständige Architektur, die schrittweise entwickelt und getestet wird. Sicherheit, Web-Kompatibilität und Standards sollen dabei von Anfang an berücksichtigt werden.

Eine Browser-Engine von Grund auf zu entwickeln, ist ein großes Vorhaben. Deshalb soll Noctra transparent zeigen, welche Webstandards bereits funktionieren und welche noch fehlen, anstatt vollständige Kompatibilität zu versprechen, bevor sie tatsächlich getestet wurde.

## Geplante Funktionen

### Weniger Ressourcenverbrauch

- **Intelligente Tab-Verwaltung:** Inaktive Tabs sollen möglichst wenig CPU und Arbeitsspeicher benötigen.
- **Ressourcenschonender Modus:** Animationen, Hintergrundaktivitäten und automatische Medienwiedergabe sollen sich reduzieren lassen.
- **Akku-Modus:** Auf Laptops sollen unnötige Hintergrundaufgaben nach Möglichkeit reduziert werden.
- **Klare Kontrolle:** Eine übersichtliche Anzeige soll zeigen, welche Tabs besonders viele Ressourcen benötigen, sobald diese Messungen zuverlässig verfügbar sind.

### Gaming-Erkennung und Gaming-Modus

Noctra soll erkennen können, wann auf dem Gerät gerade gespielt wird, und den Browser darauf einstellen.

- Bei erkanntem Spielstart kann Noctra optional in einen Gaming-Modus wechseln.
- Unnötige Hintergrundaktivitäten und Animationen sollen reduziert werden.
- Benachrichtigungen können während des Spielens leiser gestellt oder pausiert werden.
- Nach dem Spielen soll Noctra auf Wunsch wieder zu den normalen Einstellungen zurückkehren.

**Datenschutzprinzip:** Die Erkennung soll freiwillig, transparent und lokal erfolgen. Sie soll keine Spielaktivitäten an einen Server melden. Nutzerinnen und Nutzer müssen die Funktion jederzeit abschalten können. Die konkrete Erkennung hängt vom Betriebssystem und den später verfügbaren Schnittstellen ab.

### Datensparmodus: weniger unnötiger Internetverkehr

Noctra soll Datenverbrauch reduzieren, ohne ungefragt wichtige Inhalte zu verändern.

- Automatische Medienwiedergabe standardmäßig vermeiden oder kontrollierbar machen.
- Bilder bei Bedarf in einer niedrigeren Qualität laden.
- Tracker und unnötige Drittanbieter-Anfragen nach Möglichkeit blockieren.
- Hintergrundladen und Vorabladen von Seiten kontrollierbar machen.
- Zwischenspeicherung sinnvoll nutzen und den Datenverbrauch verständlich anzeigen.
- Einfache Schalter für den normalen Modus und einen besonders sparsamen Modus anbieten.

Einige Seiten funktionieren mit blockierten Skripten oder Trackern möglicherweise nicht richtig. Deshalb soll der Schutz anpassbar bleiben. Noctra soll außerdem offen erklären, welche Einsparungen tatsächlich gemessen wurden, statt unbelegte Prozentwerte zu versprechen.

### Musik-Popups und Mediensteuerung

Musik soll nicht jedes Mal den ganzen Bildschirm übernehmen müssen.

- Ein kleines, frei platzierbares Musik-Popup mit Wiedergabe, Pause und Titelsprüngen.
- Schneller Zugriff auf Medien, die in unterstützten Tabs abgespielt werden.
- Einstellbare Position, Größe und Sichtbarkeit des Popups.
- Auf Wunsch dezente Benachrichtigungen beim Titelwechsel.
- Eine Möglichkeit, das Popup vollständig auszuschalten.

Die Bedienung soll nur mit unterstützten Medienquellen funktionieren und keine Musikdienste ohne deren Zustimmung oder Schnittstellen nachahmen.

### LGBTQ+-Themes und persönliche Gestaltung

Noctra soll ein Browser sein, in dem Menschen ihre Persönlichkeit zeigen können.

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

## Roadmap

- [ ] Projektstruktur und technische Architektur dokumentieren
- [ ] Zielplattform und erste unterstützte Webstandards festlegen
- [ ] Eigenständigen, experimentellen Rendering-Prototyp entwickeln
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

**Noctra Browser – dein Browser, deine Ressourcen, dein Stil.**
