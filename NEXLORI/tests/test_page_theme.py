from nexlori.core.themes import BUILTIN_THEMES
from nexlori.page_theme import build_page_theme_script


def test_page_theme_script_injects_css_after_dom_is_ready():
    script = build_page_theme_script(BUILTIN_THEMES["gothic"], True)
    assert "nexlori-theme-user-style" in script
    assert "MutationObserver" in script
    assert "enabled:true" in script
    assert BUILTIN_THEMES["gothic"].bg in script


def test_disabled_page_theme_script_removes_previous_style():
    script = build_page_theme_script(BUILTIN_THEMES["pride-gay"], False)
    assert "enabled:false" in script
    assert "old.remove()" in script
    assert "pride" not in script.lower() or "nexlori" in script.lower()
