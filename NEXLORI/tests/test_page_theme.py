from nexlori.core.themes import BUILTIN_THEMES, combine_themes, page_theme_css
from nexlori.core.settings import Settings
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


def test_page_theme_css_does_not_override_website_styles():
    css = page_theme_css(BUILTIN_THEMES["gothic"])
    assert ":root" in css
    assert "--nexlori-page-bg" in css
    assert "color-scheme: dark" in css
    assert "!important" not in css
    assert "*:not(" not in css
    assert "background-color:" not in css


def test_combined_themes_keep_base_readability_and_mix_colours():
    base = BUILTIN_THEMES["dunkel"]
    combo = combine_themes(["dunkel", "pride-trans", "cyberpunk", "pride-bi"])
    assert combo.name == "theme-mix"
    assert combo.bg == base.bg
    assert combo.surface == base.surface
    assert combo.fg == base.fg
    assert combo.accent == base.accent
    assert len(combo.stripes) >= 4
    assert BUILTIN_THEMES["pride-trans"].stripes[0] in combo.stripes
    assert BUILTIN_THEMES["pride-bi"].stripes[-1] in combo.stripes


def test_theme_combination_rejects_more_than_four_themes():
    try:
        combine_themes(["dunkel", "pride-trans", "pride-bi", "cyberpunk", "gothic"])
    except ValueError as exc:
        assert "vier" in str(exc)
    else:
        raise AssertionError("more than four themes should be rejected")


def test_settings_accept_up_to_three_additional_themes():
    settings = Settings(theme="dunkel", theme_mix=["pride-trans", "cyberpunk", "pride-bi"])
    assert not settings.problems()
    settings.theme_mix.append("gothic")
    assert any("theme_mix" in problem for problem in settings.problems())
