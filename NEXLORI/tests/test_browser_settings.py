from nexlori.core.settings import DEFAULT_SEARCH_URL, Settings, canonical_search_url


def test_addon_and_browser_preferences_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings()
    assert settings.ubol_enabled is False
    assert settings.auto_update_check is True
    assert settings.allow_web_popups is False
    assert settings.background_on_close is True

    settings.ubol_enabled = False
    settings.auto_update_check = False
    settings.allow_web_popups = True
    settings.background_on_close = False
    settings.extensions_enabled = {
        "ublock-origin-lite": False,
        "dark-reader": True,
    }
    settings.save(path)

    saved = Settings.load(path)
    assert saved.ubol_enabled is False
    assert saved.auto_update_check is False
    assert saved.allow_web_popups is True
    assert saved.background_on_close is False
    assert saved.extensions_enabled == {
        "ublock-origin-lite": False,
        "dark-reader": True,
    }
    assert saved.problems() == []


def test_legacy_profiles_disable_unverified_ublock_lite():
    migrated = Settings.from_dict({
        "ubol_enabled": True,
        "extensions_enabled": {"ublock-origin-lite": True, "dark-reader": True},
    })
    assert migrated.ubol_enabled is False
    assert migrated.extensions_enabled == {
        "ublock-origin-lite": False,
        "dark-reader": True,
    }


def test_invalid_legacy_ublock_setting_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="ubol_enabled"):
        Settings.from_dict({"ubol_enabled": "yes"})


def test_invalid_extension_enabled_value_is_rejected():
    try:
        Settings.from_dict({"extensions_enabled": {"ublock-origin-lite": "yes"}})
    except ValueError as exc:
        assert "extensions_enabled" in str(exc)
    else:
        raise AssertionError("Invalid extension setting was accepted")


def test_legacy_duckduckgo_template_is_normalized():
    legacy = "https://html.duckduckgo.com/html/?q={}"
    assert canonical_search_url(legacy) == DEFAULT_SEARCH_URL
    assert Settings().search_url == DEFAULT_SEARCH_URL
    assert canonical_search_url("https://www.google.com/search?q={}") == "https://www.google.com/search?q={}"


def test_shield_and_auto_install_defaults():
    settings = Settings()
    assert settings.adblock_enabled is True
    assert settings.adblock_cosmetic is True
    assert settings.adblock_lists == ["pgl"]
    assert settings.auto_update_install is True
    assert "shield" in settings.toolbar_visible_icons
    assert settings.problems() == []


def test_old_settings_get_the_shield_button_once():
    migrated = Settings.from_dict({"toolbar_visible_icons": ["home", "theme"]})
    assert migrated.toolbar_visible_icons == ["home", "theme", "shield"]
    kept = Settings.from_dict({"toolbar_visible_icons": ["home"], "adblock_enabled": True})
    assert kept.toolbar_visible_icons == ["home"]


def test_invalid_shield_settings_are_rejected():
    import pytest

    with pytest.raises(ValueError, match="adblock_lists"):
        Settings.from_dict({"adblock_lists": ["unknown"]})
    with pytest.raises(ValueError, match="adblock_allowlist"):
        Settings.from_dict({"adblock_allowlist": [""]})
    with pytest.raises(ValueError, match="adblock_enabled"):
        Settings.from_dict({"adblock_enabled": "yes"})


def test_lenient_load_keeps_up_to_seven_mixed_themes(tmp_path):
    import json

    mix = ["hell", "ruhig", "gothic", "forest", "ocean", "sakura", "papier"]
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "dunkel", "theme_mix": mix}), encoding="utf-8")
    assert Settings.load_lenient(path).theme_mix == mix
