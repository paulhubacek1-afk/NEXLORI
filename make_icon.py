"""Erzeugt packaging/nexlori.ico aus dem im Code gezeichneten Icon (vor dem PyInstaller-Lauf aufrufen)."""
from pathlib import Path

from nexlori.icon import save_ico

target = Path(__file__).with_name("nexlori.ico")
save_ico(str(target))
print(f"{target} ({target.stat().st_size} Bytes)")
