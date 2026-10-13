# NEXLORI

Nexlori ist ein experimenteller Browser-Prototyp mit einer eigenen, kleinen HTML/CSS-Rendering-Engine, Tabs, Themes und ressourcenschonenden Modi.

**Der eigentliche Python-Prototyp liegt im Ordner [NEXLORI/](NEXLORI/).** Die ausführliche Dokumentation, Kompatibilitätsübersicht und Entwicklungsanleitung befinden sich in [NEXLORI/README.md](NEXLORI/README.md).

## Windows-EXE herunterladen

1. Öffne [GitHub Actions](../../actions/workflows/build-windows.yml).
2. Öffne den erfolgreich abgeschlossenen Lauf **Windows-EXE**.
3. Lade unter **Artifacts** die Datei **Nexlori-Windows-x64** herunter.
4. Entpacke die ZIP-Datei und starte die Datei Nexlori.exe. Die Datei Nexlori.exe.sha256 enthält die Prüfsumme.

Der Build läuft bei Änderungen am Hauptprojekt, vor dem Zusammenführen eines Pull Requests und kann unter **Actions → Windows-EXE → Run workflow** manuell gestartet werden. Bei Versions-Tags wie v0.2.0 erstellt der Workflow zusätzlich ein GitHub-Release.

## Wichtiger Hinweis

Nexlori ist noch **kein vollwertiger Alltagsbrowser**. Der eigene Renderer unterstützt derzeit nur einen Teil von HTML und CSS und führt kein JavaScript aus. Moderne Webseiten können deshalb unvollständig oder gar nicht funktionieren. Bitte verwende diese Entwicklungsfassung nicht für Online-Banking oder andere sensible Seiten.

Siehe [Funktionsstand und Einschränkungen](NEXLORI/README.md) für Details.
