from nexlori.core.themes import BUILTIN_THEMES, page_theme_css


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


def test_gallery_theme_links_only_accept_known_builtin_themes():
    from nexlori.qt_browser import gallery_theme_slug

    assert gallery_theme_slug("nexlori-theme://apply/gothic") == "gothic"
    assert gallery_theme_slug("nexlori-theme://apply/pride-gay") == "pride-gay"
    assert gallery_theme_slug("https://example.com/apply/gothic") is None
    assert gallery_theme_slug("nexlori-theme://apply/does-not-exist") is None
    assert gallery_theme_slug("nexlori-theme://other/gothic") is None
    assert gallery_theme_slug("nexlori-theme://apply/../../settings") is None


def test_new_gallery_themes_are_available():
    expected = {
        "midnight-purple", "neon-green", "galaxy", "volcano", "monochrome",
        "bubblegum", "citrus", "ice-blue", "coffee-light", "retro-wave", "ocean-light",
    }
    assert expected <= set(BUILTIN_THEMES)
    for name in expected:
        assert BUILTIN_THEMES[name].label
