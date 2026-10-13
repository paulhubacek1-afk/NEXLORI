# NEXLORI

Nexlori ist ein Browser-Prototyp mit Chromium-WebEngine, Tabs, Lesezeichen, Downloads und anpassbaren Themes. Der frühere eigene HTML/CSS-Renderer bleibt für Lern- und Render-Tests erhalten.

**Der eigentliche Python-Prototyp liegt im Ordner [NEXLORI/](NEXLORI/).** Die ausführliche Dokumentation, Kompatibilitätsübersicht und Entwicklungsanleitung befinden sich in [NEXLORI/README.md](NEXLORI/README.md).

## Windows-EXE herunterladen

1. Öffne [GitHub Actions](https://github.com/paulhubacek1-afk/NEXLORI/actions/workflows/build-windows.yml).
2. Öffne den erfolgreich abgeschlossenen Lauf **Windows-EXE**.
3. Lade unter **Artifacts** die Datei **Nexlori-Windows-x64** herunter.
4. Entpacke die ZIP-Datei und starte die Datei Nexlori.exe. Die Datei Nexlori.exe.sha256 enthält die Prüfsumme.

Der Build läuft bei Änderungen am Hauptprojekt, vor dem Zusammenführen eines Pull Requests und kann unter **Actions → Windows-EXE → Run workflow** manuell gestartet werden. Bei Versions-Tags wie v0.2.0 erstellt der Workflow zusätzlich ein GitHub-Release.

## Wichtiger Hinweis

Nexlori nutzt nun Chromium-WebEngine, daher funktionieren die meisten modernen Websites mit JavaScript, CSS, Bildern und Formularen. Einzelne Dienste können trotzdem spezielle DRM-Komponenten benötigen oder eingebettete Browser blockieren. Die Version bleibt ein Entwicklungsstand; verwende sie nicht für Online-Banking oder andere sensible Seiten.

Siehe [Funktionsstand und Einschränkungen](NEXLORI/README.md) für Details.
