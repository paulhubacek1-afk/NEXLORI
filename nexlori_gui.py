"""Einstiegsskript für PyInstaller (baut Nexlori.exe)."""
import sys

from nexlori.gui_main import main

if __name__ == "__main__":
    sys.exit(main())
