"""Erzeugt und prüft ``themes/catalog.json`` für den Nexlori Theme-Shop.

Aufruf (im Projektordner):
    python packaging/make_theme_catalog.py

Jedes Theme wird mit denselben Regeln geprüft wie später in der App (WCAG-Kontrast, gültige Namen).
Schlägt eine Prüfung fehl, bricht das Skript ab und schreibt keine Datei.
Neue Themes: unten in ``THEMES`` ergänzen, ``rev`` erhöhen, wenn sich Farben eines Themes ändern.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nexlori.core.theme_shop import parse_shop_theme  # noqa: E402

# (name, label, kategorie, bg, surface, fg, accent, streifen, beschreibung)
THEMES = [
    # ---- Dunkel -------------------------------------------------------------------------------
    ("nord", "Nord", "Dunkel", "#2E3440", "#3B4252", "#ECEFF4", "#88C0D0", ("#5E81AC", "#81A1C1", "#88C0D0", "#8FBCBB"), "Kühle Polarfarben, ruhig und klar."),
    ("dracula", "Dracula", "Dunkel", "#282A36", "#343746", "#F8F8F2", "#BD93F9", ("#BD93F9", "#FF79C6", "#8BE9FD"), "Der Klassiker mit Violett und Pink."),
    ("monokai", "Monokai", "Dunkel", "#272822", "#3E3D32", "#F8F8F2", "#A6E22E", ("#F92672", "#FD971F", "#E6DB74", "#A6E22E", "#66D9EF", "#AE81FF"), "Bunte Akzente auf warmem Dunkelgrau."),
    ("gruvbox-dark", "Gruvbox Dunkel", "Retro", "#282828", "#3C3836", "#EBDBB2", "#FABD2F", ("#CC241D", "#D79921", "#98971A", "#458588", "#B16286"), "Warme Retro-Farben mit hohem Lesekomfort."),
    ("tokyo-night", "Tokyo Night", "Dunkel", "#1A1B26", "#24283B", "#C0CAF5", "#7AA2F7", ("#7AA2F7", "#BB9AF7", "#7DCFFF"), "Nächtliche Neonstadt in Blau und Violett."),
    ("catppuccin-mocha", "Catppuccin Mocha", "Dunkel", "#1E1E2E", "#313244", "#CDD6F4", "#CBA6F7", ("#F5C2E7", "#CBA6F7", "#89B4FA", "#94E2D5", "#A6E3A1"), "Sanfte Pastelltöne auf dunklem Grund."),
    ("rose-pine", "Rosé Pine", "Dunkel", "#191724", "#26233A", "#E0DEF4", "#EBBCBA", ("#EB6F92", "#F6C177", "#EBBCBA", "#31748F", "#9CCFD8", "#C4A7E7"), "Gedämpft, elegant, mit rosigem Akzent."),
    ("one-dark", "One Dark", "Dunkel", "#282C34", "#353B45", "#ABB2BF", "#61AFEF", ("#E06C75", "#D19A66", "#E5C07B", "#98C379", "#56B6C2", "#61AFEF", "#C678DD"), "Vertraut aus vielen Code-Editoren."),
    ("iceberg", "Eisberg", "Dunkel", "#161821", "#1E2132", "#C6C8D1", "#84A0C6", ("#84A0C6", "#89B8C2", "#B4BE82"), "Kühles Blaugrau, angenehm für lange Sitzungen."),
    ("obsidian", "Obsidian", "Dunkel", "#0D0D0F", "#1A1A1F", "#EDEDF2", "#C9A227", ("#3A2F0B", "#C9A227", "#F2D675"), "Tiefschwarz mit goldenem Akzent."),
    ("espresso", "Espresso", "Dunkel", "#1B1411", "#2B1F1A", "#F6EBDD", "#D9A066", ("#4B2E1E", "#8C5A3C", "#D9A066"), "Dunkle Röstung mit Karamell."),
    ("copper", "Kupfer", "Dunkel", "#17110E", "#28201B", "#F5E9E1", "#E08A5A", ("#8A4B2D", "#E08A5A", "#F2C4A0"), "Warmer Metallglanz."),
    ("moss", "Moos", "Natur", "#11160F", "#1E2A1A", "#EEF6E8", "#A3D977", ("#2C4A1F", "#6BA83A", "#A3D977"), "Frisches Grün auf Waldboden."),
    ("deep-sea", "Tiefsee", "Natur", "#06141F", "#0D2636", "#E3F6FF", "#3DD6D0", ("#0A3D62", "#1B7F9E", "#3DD6D0"), "Dunkles Wasser mit türkisem Leuchten."),
    ("sunset", "Sonnenuntergang", "Natur", "#1F1218", "#36202A", "#FFF1EA", "#FF8E6E", ("#FF4D6D", "#FF8E6E", "#FFC26B", "#FFE29A"), "Verlauf von Rot nach Goldgelb."),
    ("lava", "Lava", "Natur", "#1A0A0A", "#2E1210", "#FFEDE6", "#FF5A36", ("#7A0C0C", "#C21807", "#FF5A36", "#FFB000"), "Glühende Glut auf Basalt."),
    ("galaxy", "Galaxie", "Natur", "#0B0720", "#1A1240", "#EFEAFF", "#9B8CFF", ("#241B5A", "#5B3FD1", "#9B8CFF", "#FF8BD1"), "Sternennebel in Violett und Rosa."),
    # ---- Neon ---------------------------------------------------------------------------------
    ("neon-tokyo", "Neon Tokyo", "Neon", "#0B0B14", "#171726", "#F2F2FF", "#00F0FF", ("#FF2079", "#9D4EDD", "#00F0FF"), "Leuchtreklame im Regen."),
    ("synthwave", "Synthwave", "Neon", "#241B2F", "#34294F", "#F4EEFF", "#FF7EDB", ("#FF7EDB", "#B893CE", "#36F9F6", "#FEDE5D"), "80er-Retrowave in Pink und Cyan."),
    ("vaporwave", "Vaporwave", "Neon", "#1B1030", "#2B1B4D", "#F5EBFF", "#FF71CE", ("#FF71CE", "#B967FF", "#01CDFE", "#05FFA1", "#FFFB96"), "Pastellneon, glitzernd und verträumt."),
    ("matrix", "Matrix", "Neon", "#020B05", "#0B1F12", "#D6FFE0", "#00FF66", ("#003B1A", "#00A844", "#00FF66"), "Grüner Code-Regen."),
    ("cyber-lime", "Cyber Limette", "Neon", "#0C0F08", "#1A2110", "#F1FFD6", "#C6FF00", ("#6B8E00", "#C6FF00", "#F4FF81"), "Grelles Limettengrün auf Schwarz."),
    # ---- Edelstein ----------------------------------------------------------------------------
    ("amethyst", "Amethyst", "Edelstein", "#170F24", "#271A3F", "#F4ECFF", "#D19BFF", ("#5E2A8C", "#A55EEA", "#D19BFF"), "Violetter Kristall."),
    ("emerald", "Smaragd", "Edelstein", "#06180F", "#0F2E1E", "#E6FFF1", "#34D399", ("#065F46", "#10B981", "#34D399"), "Tiefgrün mit Glanz."),
    ("ruby", "Rubin", "Edelstein", "#1C0B10", "#331520", "#FFEAEF", "#FF6B8A", ("#7F1D3A", "#E11D48", "#FF6B8A"), "Leuchtendes Rot."),
    ("sapphire", "Saphir", "Edelstein", "#08142A", "#11264D", "#EAF2FF", "#6AA7FF", ("#1E3A8A", "#3B82F6", "#6AA7FF"), "Königsblau."),
    ("blood-moon", "Blutmond", "Dunkel", "#140709", "#26101A", "#FBE9EC", "#FF4D6A", ("#4A0D1A", "#9B1B30", "#FF4D6A"), "Düster mit rotem Schimmer."),
    # ---- Hell ---------------------------------------------------------------------------------
    ("paper", "Papier", "Hell", "#FBF8F1", "#EFE9DA", "#2A2723", "#8A4B14", ("#8A4B14", "#C98A3B", "#E7C27D"), "Cremeweiß wie gutes Schreibpapier."),
    ("solarized-light", "Solarized Hell", "Hell", "#FDF6E3", "#EEE8D5", "#073642", "#1F6FA8", ("#B58900", "#CB4B16", "#DC322F", "#6C71C4", "#268BD2", "#2AA198"), "Der Hell-Klassiker mit ruhigem Kontrast."),
    ("sky", "Himmel", "Hell", "#F3F9FF", "#E1EEFA", "#0F2236", "#1D6FD1", ("#1D6FD1", "#4DA3FF", "#A5D2FF"), "Klares Himmelblau."),
    ("mint-light", "Minze Hell", "Hell", "#F2FBF6", "#DFF2E8", "#10281B", "#1F7A4D", ("#1F7A4D", "#4CBF86", "#A8E6C5"), "Frisch und leicht."),
    ("blossom", "Blüte", "Hell", "#FFF5F8", "#FBE3EC", "#3A1626", "#B8326B", ("#B8326B", "#F06EA0", "#FFB6D0"), "Zartes Rosa."),
    ("lemon", "Zitrone", "Hell", "#FFFCEB", "#F7F0C8", "#2C2A10", "#7A6400", ("#7A6400", "#D9B800", "#FFE45C"), "Sonniges Gelb."),
    ("lilac", "Flieder", "Hell", "#F8F4FF", "#E9E0FA", "#2A1B45", "#6B3FD0", ("#6B3FD0", "#A07CF0", "#D2BFFF"), "Sanftes Violett."),
    ("apricot", "Aprikose", "Hell", "#FFF6F0", "#FBE5D8", "#3A1E12", "#B5501F", ("#B5501F", "#F08A55", "#FFC9A5"), "Warmes Orange."),
    ("latte", "Latte", "Hell", "#F7F1EA", "#E9DDCF", "#2D221A", "#8B5A33", ("#8B5A33", "#C49A6C", "#E8D2B4"), "Milchkaffee-Töne."),
    ("cloud", "Wolke", "Hell", "#F6F7F9", "#E6E9EE", "#1C2430", "#3B5BDB", ("#3B5BDB", "#748FFC", "#BAC8FF"), "Neutral, modern und aufgeräumt."),
    ("glacier", "Gletscher", "Hell", "#F1FAFB", "#DCEFF2", "#0E2A2F", "#0F7C8C", ("#0F7C8C", "#3DB9C9", "#A6E3EB"), "Eisiges Türkis."),
    ("sand", "Sand", "Hell", "#FAF5EA", "#EFE4CC", "#2E2614", "#946200", ("#946200", "#E0A526", "#F6D77C"), "Dünenfarben."),
    # ---- Kontrast -----------------------------------------------------------------------------
    ("kontrast-cyan", "Kontrast Cyan", "Kontrast", "#000000", "#0A0A0A", "#FFFFFF", "#00E5FF", (), "Maximaler Kontrast mit cyanfarbenem Akzent."),
    ("kontrast-hell", "Kontrast Hell", "Kontrast", "#FFFFFF", "#F2F2F2", "#000000", "#0033CC", (), "Schwarz auf Weiß mit kräftigem Blau."),
]


def build() -> dict:
    entries = []
    for name, label, category, bg, surface, fg, accent, stripes, description in THEMES:
        entry = {
            "name": name, "label": label, "category": category, "author": "Nexlori", "rev": 1,
            "description": description, "bg": bg, "surface": surface, "fg": fg, "accent": accent,
            "stripes": list(stripes),
        }
        parse_shop_theme(entry)  # wirft ValueError mit Begründung, wenn etwas nicht stimmt
        entries.append(entry)
    names = [e["name"] for e in entries]
    if len(names) != len(set(names)):
        raise ValueError("Doppelte Theme-Namen im Katalog")
    return {"format": 1, "themes": entries}


def main() -> int:
    try:
        catalog = build()
    except ValueError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1
    target = ROOT / "themes" / "catalog.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(catalog['themes'])} Themes nach {target.relative_to(ROOT)} geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
