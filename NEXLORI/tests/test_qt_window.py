"""Tests des kompletten Browserfensters (Chromium). Opt-in: NEXLORI_GUI_TESTS=1 python -m pytest tests/test_qt_window.py

Sie starten eine echte Qt-WebEngine-Instanz und brauchen die Chromium-Systembibliotheken; deshalb laufen sie nicht
automatisch in jeder Umgebung.
"""
import os
from pathlib import Path

import pytest

if os.environ.get("NEXLORI_GUI_TESTS") != "1":
    pytest.skip("GUI-Tests sind abgeschaltet (NEXLORI_GUI_TESTS=1 setzen)", allow_module_level=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

from PySide6.QtCore import QEventLoop, QPoint, QTimer, QUrl  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEnginePermission  # noqa: E402
from PySide6.QtWidgets import QApplication, QTabWidget  # noqa: E402

from nexlori import qt_browser as qb  # noqa: E402
from nexlori.core import theme_shop  # noqa: E402
from nexlori.core.settings import Settings  # noqa: E402
from nexlori.core.themes import _INSTALLED_THEMES  # noqa: E402


def pump(ms=200):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication(["nexlori-test"])
    application.setStyle("Fusion")
    return application


@pytest.fixture()
def window(app, tmp_path):
    _INSTALLED_THEMES.clear()
    settings = Settings()
    settings.auto_update_check = False
    settings.animations = "off"
    win = qb.NexloriWindow(settings, tmp_path / "settings.json", None, self_test=True)
    win.show()
    pump()
    yield win
    win.close()
    pump()
    _INSTALLED_THEMES.clear()


def y_of(win, widget):
    return widget.mapTo(win, QPoint(0, 0)).y()


def test_tabs_and_search_bar_are_above_the_web_page(window):
    view = window.current_view()
    if window.title_bar is not None:
        assert window.tabs.bar.parentWidget() is window.title_bar.tabs_host
        assert not window.tab_row_widget.isVisible()
        assert y_of(window, window.title_bar) <= y_of(window, window.tabs.bar)
    else:
        assert y_of(window, window.tab_row_widget) < y_of(window, window.toolbar_widget)
    assert y_of(window, window.toolbar_widget) < y_of(window, view)
    assert not window.findChildren(QTabWidget)


def test_search_bar_uses_the_configured_width(window):
    assert window.address.width() == window.settings.toolbar_search_width  # vorher: fest ca. 220 px
    window.resize(900, 700)
    pump()
    assert 260 <= window.address.width() <= window.settings.toolbar_search_width
    toolbar = window.toolbar_widget
    center = window.address.mapTo(toolbar, QPoint(0, 0)).x() + window.address.width() / 2
    assert abs(center - toolbar.width() / 2) < toolbar.width() * 0.1       # annähernd mittig


def test_status_bar_lives_inside_the_frame(window):
    assert window.statusBar() is window._status_bar
    assert window.statusBar().parentWidget() is not window


def test_typing_is_not_overwritten_by_url_changes(window):
    window.activateWindow()
    window.address.setFocus()
    pump()
    QTest.keyClicks(window.address, "wetter")
    assert window.address.hasFocus() and window.address.isModified()
    window._on_url_changed(window.current_view(), QUrl("https://example.org/weitergeleitet"))
    assert window.address.text() == "wetter"                      # Eingabe bleibt erhalten
    window.address.clearFocus()
    window._on_url_changed(window.current_view(), QUrl("https://example.org/weitergeleitet"))
    assert window.address.text() == "https://example.org/weitergeleitet"


def test_security_icon_follows_the_url(window):
    for url, kind in (("https://example.org/", "secure"), ("http://example.org/", "insecure"), ("file:///tmp/a.html", "internal")):
        window._on_url_changed(window.current_view(), QUrl(url))
        assert window.address._security_kind == kind


def test_escape_restores_the_address(window):
    view = window.current_view()
    view._nexlori_start = False
    window.address.setText("halb getippt")
    window._restore_address()
    assert window.address.text() == view.url().toString()


def test_theme_change_updates_title_bar_and_frame(window):
    window.set_theme("pride-trans")
    assert window.theme.name == "pride-trans"
    assert window.theme.surface in window.styleSheet() and "QWidget#titleBar" in window.styleSheet()
    assert window.resize_frame._border.name().upper() == window.theme.accent.upper()
    assert window.accent_line._colors == tuple(window.theme.stripes)


def test_single_colour_theme_gradient_has_two_stops(window):
    assert qb._theme_gradient(window.theme).count("stop:") >= 2


def test_html_fullscreen_hides_and_restores_chrome(window):
    class Request:
        def __init__(self, on):
            self.on = on

        def accept(self):
            pass

        def toggleOn(self):
            return self.on

    window._on_fullscreen_requested(Request(True))
    pump()
    assert window.isFullScreen() and not window.toolbar_widget.isVisible() and not window.title_bar.isVisible()
    window._on_fullscreen_requested(Request(False))
    pump()
    assert not window.isFullScreen() and window.toolbar_widget.isVisible() and window.title_bar.isVisible()


def test_navigation_rewrite_addons(window):
    page = window.current_view().page()
    link, typed, redirect = (
        QWebEnginePage.NavigationType.NavigationTypeLinkClicked,
        QWebEnginePage.NavigationType.NavigationTypeTyped,
        QWebEnginePage.NavigationType.NavigationTypeRedirect,
    )
    window.settings.builtin_addons.update({"clean-urls": True, "https-first": False})
    assert window.rewrite_navigation(page, QUrl("https://example.org/a?utm_source=x&id=7"), link) == "https://example.org/a?id=7"
    assert window.rewrite_navigation(page, QUrl("http://example.org/"), typed) is None
    window.settings.builtin_addons.update({"clean-urls": False, "https-first": True})
    assert window.rewrite_navigation(page, QUrl("http://example.org/a"), typed) == "https://example.org/a"
    assert page._https_origin == "http://example.org/a"
    assert window.rewrite_navigation(page, QUrl("http://192.168.0.2/"), typed) is None
    assert window.rewrite_navigation(page, QUrl("http://example.org/"), redirect) is None
    window._http_allowed_hosts.add("example.org")
    assert window.rewrite_navigation(page, QUrl("http://example.org/b"), typed) is None


def test_addon_toggle_updates_script_and_tools_menu(window):
    assert window._addons_script is None
    window.set_builtin_addon("night-light", True)
    assert window._addons_script is not None and "night-light" in window._addons_script.sourceCode()
    window.set_builtin_addon("night-light", False)
    assert window._addons_script is None
    window.set_builtin_addon("reader", False)
    assert all(not a.isEnabled() for a in window.tools_menu.actions() if "PDF" not in a.text() and "Screenshot" not in a.text())


def test_tab_sleep_marks_and_wakes_tabs(window):
    first = window.current_view()
    first._nexlori_start = False                 # Startseiten werden nie schlafen gelegt
    window.new_tab(start_page=False, url="about:blank")
    pump()
    window.settings.builtin_addons["tab-sleep"] = True
    window.settings.tab_sleep_minutes = 2
    window._tab_activity[first] = 0.0            # sehr lange nicht benutzt
    window._sleep_tick()
    pump()
    assert first.page().lifecycleState() == QWebEnginePage.LifecycleState.Discarded
    assert window.tabs.tabText(window.tabs.indexOf(first)).startswith("💤")
    window.tabs.setCurrentIndex(window.tabs.indexOf(first))
    pump()
    assert first.page().lifecycleState() == QWebEnginePage.LifecycleState.Active
    assert not window.tabs.tabText(window.tabs.indexOf(first)).startswith("💤")


def test_memory_saver_spares_current_tab_and_can_sleep_background_tabs(window):
    first = window.current_view()
    first._nexlori_start = False
    window._tab_activity[first] = 0.0
    window.settings.memory_saver = True
    window._sleep_tick()                         # der aktive Tab bleibt trotz Speichersparmodus wach
    assert first.page().lifecycleState() == QWebEnginePage.LifecycleState.Active
    second = window.new_tab(start_page=False, url="about:blank")
    pump()
    window._tab_activity[first] = 0.0
    window._tab_activity[second] = __import__("time").monotonic()
    window._sleep_tick()                         # der alte Hintergrund-Tab wird entladen
    assert first.page().lifecycleState() == QWebEnginePage.LifecycleState.Discarded
    assert second.page().lifecycleState() == QWebEnginePage.LifecycleState.Active


def test_theme_shop_dialog_install_apply_remove(window, tmp_path, monkeypatch):
    from nexlori import theme_shop_ui
    catalog = Path(__file__).resolve().parent.parent / "themes" / "catalog.json"
    themes, skipped = theme_shop.parse_catalog(catalog.read_bytes())
    monkeypatch.setattr(theme_shop_ui, "fetch_catalog", lambda: (themes, skipped))
    monkeypatch.setattr(qb.QMessageBox, "question", staticmethod(lambda *a, **k: qb.QMessageBox.StandardButton.Yes))
    dialog = theme_shop_ui.ThemeShopDialog(window, window)
    dialog.show()
    pump(600)
    assert dialog.list.count() == len(themes) >= 40
    dialog.search.setText("nord")
    pump()
    assert dialog.current_name() == "nord"
    dialog.install_selected()
    assert "nord" in window.theme_store.installed()
    assert "nord" in window.theme_actions                 # Menü wurde neu aufgebaut
    dialog.apply_selected()
    assert window.settings.theme == "nord"
    dialog.remove_selected()
    assert window.settings.theme == "dunkel" and window.theme_store.installed() == {}
    dialog.close()


def test_closing_window_releases_pages_before_profile(window, capfd):
    window.new_tab(start_page=False, url="about:blank")
    pump()
    window.close()
    pump(300)
    captured = capfd.readouterr()
    assert "WebEnginePage still not deleted" not in captured.out + captured.err


# ------------------------------------------------------------------ Startseite, Discord-Button, interne Links
import json  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402

from nexlori.links import DISCORD_URL  # noqa: E402


def click_selector(window, selector: str) -> None:
    """Klickt mit der echten Maus auf ein Element (Chromium blockiert Navigationen auf eigene Schemata ohne Nutzergeste)."""
    view = window.current_view()
    box = []
    js = ("(()=>{const e=document.querySelector(\"%s\");e.scrollIntoView({block:'center'});"
          "const r=e.getBoundingClientRect();return JSON.stringify([r.x+r.width/2,r.y+r.height/2]);})()") % selector
    view.page().runJavaScript(js, box.append)
    pump(300)
    x, y = json.loads(box[0])
    QTest.mouseClick(view.focusProxy() or view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(x), int(y)))
    pump(600)


@pytest.fixture()
def start_window(window):
    pump(2500)  # Startseite fertig laden lassen
    return window


def test_start_page_has_discord_button_that_opens_the_invite(start_window, monkeypatch):
    visible = []
    start_window.current_view().page().runJavaScript(
        "(()=>{const r=document.querySelector('a.cta').getBoundingClientRect();return r.bottom <= innerHeight;})()", visible.append)
    pump(300)
    assert visible == [True]                      # Button ist ohne Scrollen sichtbar
    opened = []
    monkeypatch.setattr(qb.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString()) or True))
    click_selector(start_window, "a.cta")
    assert opened == [DISCORD_URL]


def test_discord_entry_in_menu(window, monkeypatch):
    opened = []
    monkeypatch.setattr(qb.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toString()) or True))
    entry = [a for a in window.more_menu.actions() if "Discord" in a.text()]
    assert len(entry) == 1
    entry[0].trigger()
    assert opened == [DISCORD_URL]


def test_start_page_tiles_work(start_window, monkeypatch):
    window = start_window
    called = []
    monkeypatch.setattr(window, "show_settings", lambda: called.append("settings"))
    click_selector(window, "a[href='nexlori://settings']")
    assert called == ["settings"]
    click_selector(window, "a[href='nexlori://addons']")
    assert window.address.text() == "nexlori://addons"
    assert window.current_view()._nexlori_internal == "nexlori://addons"
    title = []
    window.current_view().page().runJavaScript("document.body.innerText", title.append)
    pump(300)
    assert "Nexlori-Add-ons" in title[0]
    window.go_home()
    pump(1500)
    click_selector(window, "a[href='nexlori://home-network']")
    assert window.address.text() == "nexlori://home-network"


def test_internal_pages_survive_theme_change_and_reload(start_window):
    window = start_window
    view = window.current_view()
    window._show_internal_page(view, "nexlori://addons")
    pump(800)
    window.set_theme("hell")
    pump(800)
    window.reload_current()
    pump(800)
    assert view._nexlori_internal == "nexlori://addons" and window.address.text() == "nexlori://addons"


def test_websites_cannot_trigger_internal_links(window):
    called = []
    window.show_settings = lambda: called.append(1)
    view = window.current_view()
    view._nexlori_start = False
    view._nexlori_internal = None
    window.handle_internal_url(view.page(), QUrl("nexlori://settings"))
    window.handle_internal_url(view.page(), QUrl("nexlori://community/discord"))
    assert called == []
    assert "nur auf Nexlori-Seiten" in window.statusBar().currentMessage()


def test_home_network_open_validates_targets(window):
    view = window.current_view()
    view._nexlori_start = True
    window.handle_internal_url(view.page(), QUrl("nexlori://home-network/open?target=http%3A%2F%2Fevil.example%2F"))
    assert "lokal" in window.statusBar().currentMessage().lower() or "Heimnetz" in window.statusBar().currentMessage() \
        or "erlaubt" in window.statusBar().currentMessage().lower()
    window.handle_internal_url(view.page(), QUrl("nexlori://browser/retry?url=javascript%3Aalert(1)"))
    assert view._nexlori_start is True  # wurde nicht navigiert



def test_site_microphone_permission_requires_explicit_consent(window, monkeypatch):
    class Permission:
        def __init__(self):
            self.result = None

        def isValid(self):
            return True

        def origin(self):
            return QUrl("https://meet.example/")

        def permissionType(self):
            return QWebEnginePermission.PermissionType.MediaAudioCapture

        def grant(self):
            self.result = "granted"

        def deny(self):
            self.result = "denied"

    request = Permission()
    monkeypatch.setattr(
        qb.QMessageBox, "question",
        staticmethod(lambda *args, **kwargs: qb.QMessageBox.StandardButton.Yes),
    )
    window._handle_site_permission(request)
    assert request.result == "granted"


def test_site_geolocation_permission_is_denied_by_default(window, monkeypatch):
    class Permission:
        def __init__(self):
            self.result = None

        def isValid(self):
            return True

        def origin(self):
            return QUrl("https://example.test/")

        def permissionType(self):
            return QWebEnginePermission.PermissionType.Geolocation

        def grant(self):
            self.result = "granted"

        def deny(self):
            self.result = "denied"

    request = Permission()
    monkeypatch.setattr(
        qb.QMessageBox, "question",
        staticmethod(lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Unexpected permission prompt"))),
    )
    window._handle_site_permission(request)
    assert request.result == "denied"
