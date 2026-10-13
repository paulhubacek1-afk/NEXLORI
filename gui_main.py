"""Einstiegspunkt für die Fenster-App (und den Selbsttest, den die CI gegen die gebaute .exe ausführt)."""
from __future__ import annotations

import sys

from . import __version__


def selftest(out_path: str | None = None) -> int:
    """Prüft ohne Bedienung, dass Renderer, Schriften und Tk in dieser Installation funktionieren."""
    try:
        from .browser import load_page
        from .engine import paint
        from .engine.fonts import default_metrics
        from .engine.layout import Text

        page = load_page("about:start")
        layout = page.document.layout(800, default_metrics())
        image = paint(layout, page.document.background)
        texts = [c for c in layout.commands if isinstance(c, Text)]
        if page.error or image.width != 800 or image.height < 300 or len(texts) < 10:
            return 2
    except Exception as exc:  # noqa: BLE001
        _write(out_path, f"FEHLER Renderer: {type(exc).__name__}: {exc}")
        return 2
    try:
        import tkinter as tk

        from PIL import ImageTk

        root = tk.Tk()
        root.withdraw()
        # Genau der Aufruf, den die Seitenansicht braucht: schlägt fehl, wenn Pillows Tk-Anbindung nicht mitgebündelt wurde.
        ImageTk.PhotoImage(image.crop((0, 0, 64, 64)), master=root)
        root.update_idletasks()
        root.destroy()
    except Exception as exc:  # noqa: BLE001
        _write(out_path, f"FEHLER Tk: {type(exc).__name__}: {exc}")
        return 3
    _write(out_path, f"OK Nexlori {__version__} ({len(texts)} Textelemente, {image.width}x{image.height})")
    return 0


def _write(path: str | None, text: str) -> None:
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--selftest"]:
        return selftest(argv[1] if len(argv) > 1 else None)
    if argv[:1] in (["--version"], ["-V"]):
        print(f"Nexlori {__version__}")
        return 0
    from .gui import run

    return run(argv)
