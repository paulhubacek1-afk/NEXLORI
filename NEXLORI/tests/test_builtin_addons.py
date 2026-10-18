import re
import shutil
import subprocess

import pytest

from nexlori.core import builtin_addons as ba
from nexlori.core.settings import Settings


def test_addon_registry_is_consistent():
    ids = [a.id for a in ba.ADDONS]
    assert len(ids) == len(set(ids)) >= 10
    assert all(a.kind in {"script", "engine", "action"} for a in ba.ADDONS)
    assert all(a.label and a.description for a in ba.ADDONS)
    for addon in ba.ADDONS:
        if addon.kind == "script":
            assert addon.id in ba._JS, f"{addon.id} hat kein Skript"
    assert set(ba.default_states()) == set(ids)


def test_page_modifying_addons_are_opt_in_by_default():
    defaults = ba.default_states()
    for addon in ba.ADDONS:
        if addon.kind == "script":
            assert defaults[addon.id] is False, f"{addon.id} darf nicht still Webseiten verändern"
    assert defaults["clean-urls"] is True


def test_no_script_when_nothing_enabled():
    assert ba.build_addons_script(ba.default_states(), accent="#112233", bg="#000000") == ""


def test_script_contains_only_enabled_addons():
    script = ba.build_addons_script({"night-light": True, "scroll-top": True}, accent="#112233", bg="#000000")
    assert "night-light" in script and "scroll-top" in script
    assert "dark-pages" not in script and "cookie-banners" not in script
    assert "__ACCENT__" not in script and "__BG__" not in script and "__COOKIE_SELECTORS__" not in script
    assert "#112233" in script


def test_script_only_runs_in_top_frame():
    script = ba.build_addons_script({"night-light": True}, accent="#112233", bg="#000000")
    assert "window.top !== window" in script


@pytest.mark.parametrize("bad", ["red", "#12345", "#GGGGGG", "'; alert(1); '", ""])
def test_colors_are_validated_to_prevent_script_injection(bad):
    with pytest.raises(ValueError):
        ba.build_addons_script({"night-light": True}, accent=bad, bg="#000000")
    with pytest.raises(ValueError):
        ba.reader_script(bg="#000000", fg="#ffffff", accent=bad)


def test_reader_script_is_filled_and_sanitises_content():
    script = ba.reader_script(bg="#101010", fg="#eeeeee", accent="#66ccff")
    assert "__" not in re.sub(r"__close", "", script)
    assert "#101010" in script and "#66ccff" in script
    assert "startsWith('on')" in script          # Event-Handler-Attribute werden entfernt
    assert "attachShadow" in script              # Seitenstile dringen nicht in den Lesemodus
    assert "no-article" in script


def _all_scripts():
    everything = {a.id: True for a in ba.ADDONS}
    yield "alle", ba.build_addons_script(everything, accent="#66ccff", bg="#101010")
    for addon in ba.ADDONS:
        if addon.kind == "script":
            yield addon.id, ba.build_addons_script({addon.id: True}, accent="#66ccff", bg="#101010")
    yield "reader", "(function(){ return " + ba.reader_script(bg="#101010", fg="#eeeeee", accent="#66ccff").strip().rstrip(";") + "; })();"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js nicht installiert")
@pytest.mark.parametrize("name, source", list(_all_scripts()))
def test_generated_javascript_has_valid_syntax(name, source, tmp_path):
    path = tmp_path / f"{name}.js"
    path.write_text(source, encoding="utf-8")
    result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_cookie_selectors_do_not_hide_normal_content():
    selectors = ba._COOKIE_SELECTORS
    assert all(len(s) > 4 for s in selectors)
    assert not any(s in {"body", "html", "main", "div", "#content", "[role='dialog']"} for s in selectors)


# ------------------------------------------------------------------ Einstellungen
def test_settings_validate_addon_fields():
    s = Settings()
    assert s.problems() == []
    for bad in ({"builtin_addons": {"gibt-es-nicht": True}}, {"builtin_addons": {"reader": "ja"}},
                {"builtin_addons": []}, {"tab_sleep_minutes": 1}, {"tab_sleep_minutes": 500},
                {"tab_sleep_minutes": True}, {"animations": "wild"}, {"custom_titlebar": "ja"}):
        broken = Settings()
        for key, value in bad.items():
            setattr(broken, key, value)
        assert broken.problems(), bad


def test_old_settings_files_get_new_defaults():
    loaded = Settings.from_dict({"theme": "hell", "builtin_addons": {"reader": False, "unbekannt": True}})
    assert loaded.builtin_addons["reader"] is False
    assert loaded.builtin_addons["clean-urls"] is True and "unbekannt" not in loaded.builtin_addons
    assert Settings.from_dict({"theme": "hell"}).animations == "full"
    assert Settings.from_dict({"theme": "hell"}).custom_titlebar is True


def test_memory_saver_is_enabled_by_default_and_can_be_disabled():
    assert Settings().memory_saver is True
    settings = Settings(memory_saver=False)
    assert settings.problems() == []
    assert Settings.from_dict({"theme": "dunkel"}).memory_saver is True
