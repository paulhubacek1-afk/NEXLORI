"""Kommandozeile: `python -m nexlori render seite.html seite.png` bzw. `python -m nexlori themes`."""
from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexlori", description="Nexlori – experimenteller Prototyp")
    sub = parser.add_subparsers(dest="cmd", required=True)

    render = sub.add_parser("render", help="HTML-Datei mit dem eigenen Renderer als PNG ausgeben")
    render.add_argument("input", help="HTML-Datei (UTF-8)")
    render.add_argument("output", help="Ziel-PNG")
    render.add_argument("--width", type=int, default=800, help="Viewport-Breite in px (Standard: 800)")

    sub.add_parser("themes", help="Eingebaute Themes mit Kontrastprüfung auflisten")

    gui = sub.add_parser("gui", help="Browser-Fenster öffnen")
    gui.add_argument("url", nargs="*", help="Adresse oder Suchbegriff (optional)")

    args = parser.parse_args(argv)
    if args.cmd == "gui":
        from .gui_main import main as gui_main

        return gui_main(args.url)
    if args.cmd == "render":
        from .engine import render_html

        source = Path(args.input).read_text(encoding="utf-8")
        image = render_html(source, args.width).to_image()
        image.save(args.output)
        print(f"{args.output}: {image.width}x{image.height}px")
        return 0

    from .core.themes import BUILTIN_THEMES, accessibility_issues

    exit_code = 0
    for theme in BUILTIN_THEMES.values():
        issues = accessibility_issues(theme)
        status = "OK" if not issues else "; ".join(issues)
        print(f"{theme.name:18} {theme.label:32} {status}")
        exit_code |= bool(issues)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
