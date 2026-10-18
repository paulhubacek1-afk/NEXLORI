from nexlori.default_browser import default_browser_settings_uri, register_windows_browser


def test_default_browser_opens_windows_settings_uri():
    assert default_browser_settings_uri().startswith("ms-settings:defaultapps")


def test_source_mode_never_registers_python_as_the_browser():
    assert register_windows_browser(None) is False
