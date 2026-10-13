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
    assert "a:visited" in css
    assert "textarea" in css


def test_website_theme_css_recolours_common_page_surfaces():
    css = page_theme_css(BUILTIN_THEMES["gothic"])
    assert "*:not(img)" in css
    assert '[class*="card" i]' in css
    assert "background-color: var(--nexlori-page-surface) !important" in css


def test_website_theme_css_leaves_media_and_layout_intact():
    css = page_theme_css(BUILTIN_THEMES["pride-gay"])
    assert "Images, video, canvas" in css
    assert "display:none" not in css.replace(" ", "")
    assert "filter:" not in css

def test_page_theme_is_preserved_for_every_navigation():
    from nexlori.page_theme import build_page_theme_script

    script = build_page_theme_script(BUILTIN_THEMES["gothic"], True)
    assert "MutationObserver" in script
    assert "nexlori-theme-user-style" in script
    assert "enabled:true" in script
    disabled = build_page_theme_script(BUILTIN_THEMES["gothic"], False)
    assert "enabled:false" in disabled
    assert "old.remove()" in disabled
