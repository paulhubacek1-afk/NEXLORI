"""GUI-Tests: laufen nur, wenn Tkinter und ein Display vorhanden sind (z. B. Windows-CI oder xvfb-run)."""
import time

import pytest

tk = pytest.importorskip("tkinter")
pytest.importorskip("PIL.ImageTk")

from nexlori.core.modes import Mode  # noqa: E402
from nexlori.core.settings import Settings  # noqa: E402


def pump(app, cond, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        app.root.update()
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def make_app(tmp_path):
    created = []

    def factory(settings=None, url="about:test", geometry="900x620"):
        from nexlori.gui import NexloriApp

        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("kein Display verfügbar")
        root.geometry(geometry)
        app = NexloriApp(root, settings or Settings(), tmp_path / "settings.json", url)
        created.append(root)
        root.update()
        return app

    yield factory
    for root in created:
        try:
            root.destroy()
        except tk.TclError:
            pass


def loaded(app, title=None):
    st = app.active
    return st is not None and st.layout is not None and st.page is not None and (title is None or st.page.title == title)


def click(app, x, y, state=0):
    app.canvas.event_generate("<Button-1>", x=int(x), y=int(y), state=state)
    app.root.update()


def link_pos(app):
    st = app.active
    link = st.links[0]
    st.scroll = max(0.0, link.y - 150)
    app._redraw()
    return link.x + 3, link.y - st.scroll + 3


def test_page_is_loaded_laid_out_and_painted(make_app):
    app = make_app()
    assert pump(app, lambda: loaded(app, "Nexlori Testseite") and app._last_image is not None)
    img = app._last_image
    assert len({img.getpixel((x, y)) for x in range(0, img.width, 7) for y in range(0, img.height, 7)}) > 5
    assert "Nexlori Testseite" in app.root.title()
    assert app.var_url.get() == "about:test"
    assert app.session.history[app.active_id].entries == ["about:test"]


def test_clicking_a_link_navigates_and_back_forward_work(make_app):
    app = make_app()
    assert pump(app, lambda: loaded(app, "Nexlori Testseite"))
    click(app, *link_pos(app))
    assert pump(app, lambda: loaded(app, "Nexlori"))
    assert app.var_url.get() == "about:start"
    app.cmd_back()
    assert pump(app, lambda: loaded(app, "Nexlori Testseite"))
    app.cmd_forward()
    assert pump(app, lambda: loaded(app, "Nexlori"))
    assert app.session.history[app.active_id].entries == ["about:test", "about:start"]


def test_ctrl_click_opens_background_tab(make_app):
    app = make_app()
    assert pump(app, lambda: loaded(app))
    first = app.active_id
    click(app, *link_pos(app), state=0x4)
    assert pump(app, lambda: len(app.states) == 2 and all(s.page for s in app.states.values()))
    assert app.active_id == first
    other = [i for i in app.states if i != first][0]
    assert app.states[other].page.title == "Nexlori"


def test_tabs_open_switch_and_close(make_app):
    app = make_app()
    assert pump(app, lambda: loaded(app))
    first = app.active_id
    app.cmd_new_tab()
    assert len(app.states) == 2 and app.active_id != first
    assert pump(app, lambda: loaded(app, "Nexlori"))
    app.select_tab(first)
    assert pump(app, lambda: loaded(app, "Nexlori Testseite"))
    app.close_tab(first)
    assert list(app.states) != [first] and len(app.states) == 1
    assert pump(app, lambda: loaded(app, "Nexlori"))


def test_address_bar_loads_local_files_and_blocks_dangerous_schemes(make_app, tmp_path):
    app = make_app()
    page = tmp_path / "meine seite.html"
    page.write_text("<title>Lokal ä</title><p>Hallo</p>", encoding="utf-8")
    app.var_url.set(str(page))
    app._on_enter()
    assert pump(app, lambda: loaded(app, "Lokal ä"))
    app.var_url.set("javascript:alert(1)")
    app._on_enter()
    assert pump(app, lambda: loaded(app, "Fehler") and app.active.page.error)


def test_sleeping_tabs_free_memory_and_wake_on_select(make_app):
    app = make_app(Settings(mode="eco"))
    assert pump(app, lambda: loaded(app))
    first = app.active_id
    second = app.new_tab("about:start", activate=False)
    assert pump(app, lambda: app.states[second].page is not None)
    app.session.tabs.tabs[second].last_active = time.monotonic() - 1000
    app._tick_sleep()
    assert app.session.tabs.tabs[second].suspended
    assert app.states[second].page.document is None and app.states[second].layout is None
    assert app.active_id == first and not app.session.tabs.tabs[first].suspended
    app.select_tab(second)
    assert pump(app, lambda: loaded(app, "Nexlori"))
    assert app.states[second].page.document is not None


def test_zoom_changes_layout_and_is_saved(make_app, tmp_path):
    app = make_app()
    assert pump(app, lambda: loaded(app))
    before = app.active.layout.height
    app.change_zoom(+0.5)
    assert app.settings.page_zoom == 1.5
    assert pump(app, lambda: app.active.layout_key is not None and app.active.layout_key[1] == app.zoom and app.active.layout.height > before)
    app.change_zoom(None)
    assert app.settings.page_zoom == 1.0
    assert '"page_zoom": 1.0' in (tmp_path / "settings.json").read_text(encoding="utf-8")


def test_window_resize_triggers_relayout(make_app):
    app = make_app(geometry="900x620")
    assert pump(app, lambda: loaded(app))
    width = app.active.layout_key[0]
    app.root.geometry("640x500")
    assert pump(app, lambda: app.active.layout_key is not None and app.active.layout_key[0] < width and app.active.layout is not None)


def test_theme_and_mode_changes_are_applied_and_persisted(make_app, tmp_path):
    app = make_app()
    app.set_theme("pride-trans")
    assert app.root.cget("bg").lower() == "#15131a"
    app.set_mode(Mode.BATTERY)
    assert "Akku" in app.var_mode.get()
    saved = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert '"theme": "pride-trans"' in saved and '"mode": "battery"' in saved


def test_gaming_detection_is_opt_in_and_switches_mode(make_app):
    app = make_app()
    assert not app.detector.enabled and app.settings.gaming_detection is False
    app.var_gaming.set(True)
    app.toggle_gaming()
    app.var_autoswitch.set(True)
    app.toggle_autoswitch()
    assert app.detector.enabled
    app.detector._source = lambda: ["CS2.exe"]
    app.detector.enter_after = 1
    app.detector.poll()
    assert pump(app, lambda: app.session.modes.mode is Mode.GAMING)
    assert "Gaming" in app.var_mode.get()
    app.var_gaming.set(False)
    app.toggle_gaming()
    assert pump(app, lambda: app.session.modes.mode is Mode.NORMAL)


def test_blocked_link_targets_show_a_message_instead_of_navigating(make_app):
    app = make_app()
    assert pump(app, lambda: loaded(app))
    st = app.active
    import dataclasses

    st.links = [dataclasses.replace(st.links[0], href="javascript:alert(1)")]
    click(app, *link_pos(app))
    assert "nicht geöffnet" in app.var_status.get()
    assert app.session.history[app.active_id].entries == ["about:test"]
