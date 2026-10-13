"""Baut Nexlori.exe (unter Windows) bzw. die Programmdatei der aktuellen Plattform mit PyInstaller.

Aufruf (im Projektordner):
    pip install -e ".[gaming]" pyinstaller
    python packaging/make_icon.py        # optional, erzeugt das Icon
    python packaging/build_exe.py        # Ergebnis: dist/Nexlori.exe
"""
import sys
from pathlib import Path

import PyInstaller.__main__

root = Path(__file__).resolve().parent.parent
args = [
    "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "Nexlori",
    "--paths", str(root / "src"),
    "--collect-submodules", "nexlori",
    # Pillows Tk-Anbindung wird nicht automatisch erkannt; ohne sie stürzt die EXE beim Start ab
    # (der Selbsttest `Nexlori.exe --selftest` prüft genau das).
    "--hidden-import", "PIL.ImageTk",
    "--hidden-import", "PIL._tkinter_finder",
    "--distpath", str(root / "dist"),
    "--workpath", str(root / "build"),
    "--specpath", str(root / "build"),
]
icon = root / "packaging" / "nexlori.ico"
if sys.platform == "win32" and icon.exists():
    args += ["--icon", str(icon)]
args.append(str(root / "packaging" / "nexlori_gui.py"))
PyInstaller.__main__.run(args)
