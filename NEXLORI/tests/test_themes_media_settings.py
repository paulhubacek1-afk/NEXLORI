import json
from dataclasses import fields

import pytest

from nexlori.core.media import MediaController, MediaSession, PopupConfig
from nexlori.core.settings import Settings
from nexlori.core.themes import (
    BUILTIN_THEMES, Theme, accessibility_issues, contrast_ratio, custom_theme, hex_to_rgb,
)


# ------------------------------------------------------------------ Themes
def test_contrast_reference_values():
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast_ratio("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)
    assert contrast_ratio("#123456", "#123456") == pytest.approx(1.0)


def test_all_builtin_themes_meet_wcag_aa():
    assert len(BUILTIN_THEMES) >= 11
    for theme in BUILTIN_THEMES.values():
        assert accessibility_issues(theme) == [], theme.name


def test_pride_themes_are_present_with_flag_stripes():
    pride = [t for t in BUILTIN_THEMES.values() if t.name.startswith("pride-")]
    assert {t.name for t in pride} >= {"pride-regenbogen", "pride-trans", "pride-bi", "pride-pan"}
    assert all(len(t.stripes) >= 3 for t in pride)
    assert len(BUILTIN_THEMES["pride-regenbogen"].stripes) == 6

def test_pride_collection_includes_a_broad_range_of_identity_flags():
    pride = [t for t in BUILTIN_THEMES.values() if t.name.startswith("pride-")]
    assert len(pride) >= 35
    expected = {
        "pride-progress", "pride-intersex-progress", "pride-gay", "pride-mlm",
        "pride-trans", "pride-transmasc", "pride-transfem", "pride-genderfluid",
        "pride-genderqueer", "pride-agender", "pride-demiboy", "pride-demigirl",
        "pride-asexuell", "pride-aromantisch", "pride-aroace", "pride-polyamorie",
        "pride-sapphic", "pride-achillean", "pride-bear", "pride-ally",
    }
    assert expected <= set(BUILTIN_THEMES)


def test_custom_theme_rejects_low_contrast_and_bad_input():
    assert custom_theme("meins", "#101010", "#202020", "#F0F0F0", "#66CCFF").accent == "#66CCFF"
    with pytest.raises(ValueError, match="barrierearm"):
        custom_theme("grau", "#808080", "#808080", "#888888", "#8A8A8A")
    with pytest.raises(ValueError):
        custom_theme("x", "red", "#202020", "#F0F0F0", "#66CCFF")
    with pytest.raises(ValueError):
        custom_theme("Böser Name!", "#101010", "#202020", "#F0F0F0", "#66CCFF")
    assert hex_to_rgb("#0A0b0C") == (10, 11, 12)


def test_theme_roundtrip_through_json():
    theme = BUILTIN_THEMES["pride-pan"]
    assert Theme.from_dict(json.loads(json.dumps(theme.to_dict()))) == theme


# ------------------------------------------------------------------ Medien
class FakeSource:
    def __init__(self):
        self.log = []

    def play(self): self.log.append("play")
    def pause(self): self.log.append("pause")
    def next_track(self): self.log.append("next")
    def previous_track(self): self.log.append("prev")


def test_only_controllable_sources_are_accepted():
    mc = MediaController()
    with pytest.raises(ValueError):
        mc.register(MediaSession(1, "Dienst X"), None)
    assert mc.active is None and not mc.popup_visible
    assert mc.toggle_play() is False and mc.next() is False


def test_controls_reach_the_source():
    mc, src = MediaController(), FakeSource()
    mc.register(MediaSession(1, "Tab 1"), src)
    assert mc.popup_visible
    mc.toggle_play(); mc.toggle_play(); mc.next(); mc.previous()
    assert src.log == ["play", "pause", "next", "prev"]
    assert mc.active.playing is False


def test_popup_can_be_disabled_or_hidden_and_validates_config():
    mc = MediaController(PopupConfig(enabled=False))
    mc.register(MediaSession(1, "t"), FakeSource())
    assert not mc.popup_visible
    mc.popup.enabled, mc.popup.visible = True, False
    assert not mc.popup_visible
    with pytest.raises(ValueError):
        PopupConfig(corner="mitte")
    with pytest.raises(ValueError):
        PopupConfig(size="riesig")


def test_track_change_notification_is_opt_in():
    mc = MediaController()
    mc.register(MediaSession(1, "t"), FakeSource())
    assert mc.update_track(1, "Lied A", "Band") is None
    mc.popup.notify_on_track_change = True
    assert mc.update_track(1, "Lied B", "Band") == "Lied B – Band"
    assert mc.update_track(1, "Lied B", "Band") is None  # kein Wechsel
    assert mc.update_track(99, "x") is None


def test_unregister_falls_back_to_a_playing_session():
    mc = MediaController()
    s1, s2, s3 = MediaSession(1, "a"), MediaSession(2, "b", playing=True), MediaSession(3, "c")
    for s in (s1, s2, s3):
        mc.register(s, FakeSource())
    mc.unregister(3)
    assert mc.active is s2
    mc.unregister(2); mc.unregister(1)
    assert mc.active is None


# ------------------------------------------------------------------ Einstellungen
def test_privacy_friendly_defaults():
    s = Settings()
    assert s.gaming_detection is False and s.gaming_auto_switch is False
    assert s.block_trackers is True and s.autoplay == "block"
    assert s.problems() == []
    assert not any("telemetry" in f.name.lower() or "analytics" in f.name.lower() for f in fields(Settings))


def test_save_load_roundtrip_and_missing_file(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    assert Settings.load(path) == Settings()
    s = Settings(theme="pride-trans", mode="eco", custom_games=["meinspiel.exe"], site_allowlist=["bank.at"])
    s.save(path)
    assert Settings.load(path) == s
    assert not list(path.parent.glob("*.tmp"))


def test_toolbar_and_three_pride_favourites_are_validated_and_persisted(tmp_path):
    s = Settings()
    assert len(s.pride_favorites) == 3
    assert s.toolbar_search_width == 560
    assert s.toolbar_icon_size == 18
    assert s.problems() == []
    with pytest.raises(ValueError, match="höchstens drei"):
        Settings.from_dict({"pride_favorites": ["pride-gay", "pride-trans", "pride-bi", "pride-pan"]})
    with pytest.raises(ValueError, match="toolbar_search_width"):
        Settings.from_dict({"toolbar_search_width": 100})
    with pytest.raises(ValueError, match="toolbar_visible_icons"):
        Settings.from_dict({"toolbar_visible_icons": ["bookmark", "bookmark"]})
    path = tmp_path / "settings-test.json"
    s.toolbar_search_width = 720
    s.toolbar_icon_size = 22
    s.toolbar_visible_icons = ["spotify", "theme"]
    s.pride_favorites = ["pride-gay", "pride-progress", "pride-trans"]
    s.save(path)
    loaded = Settings.load(path)
    assert loaded.toolbar_search_width == 720
    assert loaded.toolbar_icon_size == 22
    assert loaded.toolbar_visible_icons == ["spotify", "theme"]
    assert loaded.pride_favorites == ["pride-gay", "pride-progress", "pride-trans"]
    path.unlink(missing_ok=True)


def test_invalid_values_are_rejected_and_unknown_keys_ignored():
    with pytest.raises(ValueError, match="theme"):
        Settings.from_dict({"theme": "gibt-es-nicht"})
    with pytest.raises(ValueError, match="autoplay"):
        Settings.from_dict({"autoplay": "vielleicht"})
    assert Settings.from_dict({"future_option": 1, "mode": "battery"}).mode == "battery"


def test_theme_combinations_support_eight_palettes_and_reject_nine():
    from nexlori.core.themes import combine_themes
    names = ["dunkel", "gothic", "cyberpunk", "forest", "ocean", "sakura", "mitternacht", "kaffee"]
    assert len(combine_themes(names).stripes) >= 8
    with pytest.raises(ValueError, match="höchstens acht"):
        combine_themes(names + ["aurora"])


def test_new_light_and_dark_looks_are_available():
    from nexlori.core.themes import is_light_theme

    light = {"papier", "himmelblau", "salbei", "flieder", "duene", "kirschbluete", "polarlicht-hell"}
    dark = {"fjord", "nachtfalter", "petrol", "terminal", "retrowelle", "vulkan", "tiefsee", "herbstlaub",
            "matcha", "oled", "bernstein", "sternennebel", "abendrot"}
    assert light | dark <= set(BUILTIN_THEMES)
    assert all(is_light_theme(BUILTIN_THEMES[name]) for name in light)
    assert not any(is_light_theme(BUILTIN_THEMES[name]) for name in dark)
    assert len(BUILTIN_THEMES) >= 100


def test_builtin_names_never_collide_with_theme_shop_catalog():
    from pathlib import Path

    catalog = Path(__file__).resolve().parents[1] / "themes" / "catalog.json"
    names = {item["name"] for item in json.loads(catalog.read_text(encoding="utf-8"))["themes"]}
    assert not names & set(BUILTIN_THEMES)
