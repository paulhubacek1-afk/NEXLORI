from nexlori.core.themes import BUILTIN_THEMES, page_theme_css
from nexlori.browser import compatible_webengine_user_agent


def test_requested_themes_are_available():
    assert {"gothic", "pride-gay", "cyberpunk", "forest", "ocean", "sakura", "mitternacht"} <= set(BUILTIN_THEMES)
    for name in ("gothic", "pride-gay", "cyberpunk", "forest", "ocean", "sakura"):
        assert BUILTIN_THEMES[name].label


def test_website_theme_css_uses_the_selected_palette():
    theme = BUILTIN_THEMES["gothic"]
    css = page_theme_css(theme)
    assert theme.bg in css
    assert theme.surface in css
    assert theme.fg in css
    assert theme.accent in css
    assert "color-scheme: dark" in css
    assert "--nexlori-page-bg" in css
    assert "--nexlori-page-surface" in css
    assert "--nexlori-page-text" in css


def test_website_theme_css_does_not_override_page_colours_or_surfaces():
    css = page_theme_css(BUILTIN_THEMES["gothic"])
    assert "*:not(img)" not in css
    assert '[class*="card" i]' not in css
    assert "!important" not in css
    assert "background-color:" not in css
    assert "a:visited" not in css


def test_website_theme_css_leaves_media_and_layout_intact():
    css = page_theme_css(BUILTIN_THEMES["pride-gay"])
    assert "display:none" not in css.replace(" ", "")
    assert "filter:" not in css
    assert "iframe" not in css
    assert "transform:" not in css

def test_page_theme_is_preserved_for_every_navigation():
    from nexlori.page_theme import build_page_theme_script

    script = build_page_theme_script(BUILTIN_THEMES["gothic"], True)
    assert "MutationObserver" in script
    assert "nexlori-theme-user-style" in script
    assert "enabled:true" in script
    disabled = build_page_theme_script(BUILTIN_THEMES["gothic"], False)
    assert "enabled:false" in disabled
    assert "old.remove()" in disabled



def test_compatible_user_agent_keeps_real_chromium_and_removes_qt_token():
    source = "Mozilla/5.0 AppleWebKit/537.36 QtWebEngine/6.12.0 Chrome/140.0.0.0 Safari/537.36"
    result = compatible_webengine_user_agent(source)
    assert "QtWebEngine/" not in result
    assert "Chrome/140.0.0.0" in result
    assert "AppleWebKit/537.36" in result
