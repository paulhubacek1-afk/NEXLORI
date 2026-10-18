import json
from pathlib import Path

import pytest

from nexlori.core.theme_packs import (
    PACK_BASE_URL, ThemePackInfo, fetch_pack_catalog, fetch_theme_pack, parse_pack_catalog,
    parse_theme_pack, serialize_theme_pack, PACK_CATALOG_URL,
)
from nexlori.core.theme_shop import ShopError

PACK_DIR = Path(__file__).resolve().parent.parent / "themes" / "packs"
CATALOG_PATH = PACK_DIR / "catalog.json"


class FakeResponse:
    def __init__(self, data: bytes):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=-1):
        return self.data if limit < 0 else self.data[:limit]


def test_repository_theme_pack_catalog_and_files_are_valid():
    packs, skipped = parse_pack_catalog(CATALOG_PATH.read_bytes())
    assert skipped == 0
    assert {p.name for p in packs} == {"neon-night", "soft-pastel", "gemstones"}
    for info in packs:
        assert info.url == PACK_BASE_URL + info.name + ".nxthemepack"
        parsed = parse_theme_pack((PACK_DIR / f"{info.name}.nxthemepack").read_bytes())
        assert parsed.name == info.name
        assert len(parsed.themes) == 5


def test_catalog_skips_untrusted_urls_and_duplicate_names():
    data = {"format": 1, "packs": [
        {"name": "bad", "label": "Bad", "description": "test", "url": "https://evil.example/bad.nxthemepack"},
        {"name": "good", "label": "Good", "description": "test", "url": PACK_BASE_URL + "good.nxthemepack"},
        {"name": "good", "label": "Duplicate", "description": "test", "url": PACK_BASE_URL + "good.nxthemepack"},
    ]}
    packs, skipped = parse_pack_catalog(json.dumps(data))
    assert [p.name for p in packs] == ["good"]
    assert skipped == 2


def test_catalog_download_and_pack_download_can_be_tested_offline():
    catalog_raw = CATALOG_PATH.read_bytes()
    info_list, _ = parse_pack_catalog(catalog_raw)
    info = info_list[0]
    payload = (PACK_DIR / f"{info.name}.nxthemepack").read_bytes()
    packs, skipped = fetch_pack_catalog(opener=lambda *_a, **_k: FakeResponse(catalog_raw))
    assert skipped == 0 and packs[0] == info
    loaded = fetch_theme_pack(info, opener=lambda *_a, **_k: FakeResponse(payload))
    assert loaded.name == info.name and len(loaded.themes) == 5
    with pytest.raises(ShopError):
        fetch_pack_catalog(url="https://evil.example/catalog.json", opener=lambda *_a, **_k: FakeResponse(b"{}"))
    assert PACK_CATALOG_URL.endswith("/catalog.json")


def test_pack_serialization_round_trip_and_duplicate_rejection():
    pack = parse_theme_pack((PACK_DIR / "neon-night.nxthemepack").read_bytes())
    raw = serialize_theme_pack("portable-pack", "Portable Pack", "Locally exported colors.", list(pack.themes))
    restored = parse_theme_pack(raw)
    assert restored.name == "portable-pack"
    assert [item.name for item in restored.themes] == [item.name for item in pack.themes]
    first = pack.themes[0]
    duplicate_entry = {
        **first.theme.to_dict(), "category": first.category, "author": first.author,
        "rev": first.rev, "description": first.description,
    }
    bad = json.dumps({"format": 1, "name": "dupe", "label": "Duplicate", "themes": [duplicate_entry, duplicate_entry]})
    with pytest.raises(ShopError, match="doppelt"):
        parse_theme_pack(bad)


def test_theme_pack_rejects_invalid_format_and_oversized_files():
    with pytest.raises(ShopError, match="Format"):
        parse_theme_pack('{"format":2}')
    from nexlori.core.theme_packs import MAX_PACK_BYTES
    with pytest.raises(ShopError, match="zu groß"):
        parse_theme_pack(b" " * (MAX_PACK_BYTES + 1))
