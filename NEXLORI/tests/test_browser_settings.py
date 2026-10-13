from nexlori.core.settings import Settings


def test_addon_and_browser_preferences_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings()
    assert settings.ubol_enabled is True
    assert settings.auto_update_check is True
    assert settings.allow_web_popups is False

    settings.ubol_enabled = False
    settings.auto_update_check = False
    settings.allow_web_popups = True
    settings.extensions_enabled = {
        "ublock-origin-lite": False,
        "dark-reader": True,
    }
    settings.save(path)

    saved = Settings.load(path)
    assert saved.ubol_enabled is False
    assert saved.auto_update_check is False
    assert saved.allow_web_popups is True
    assert saved.extensions_enabled == {
        "ublock-origin-lite": False,
        "dark-reader": True,
    }
    assert saved.problems() == []


def test_invalid_extension_enabled_value_is_rejected():
    try:
        Settings.from_dict({"extensions_enabled": {"ublock-origin-lite": "yes"}})
    except ValueError as exc:
        assert "extensions_enabled" in str(exc)
    else:
        raise AssertionError("Invalid extension setting was accepted")
