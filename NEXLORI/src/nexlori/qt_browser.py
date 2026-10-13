"""Nexlori's Chromium-based browser UI.

The legacy renderer is kept for educational rendering tests; real pages are rendered by Qt WebEngine.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import QEventLoop, QPoint, QTimer, QUrl, Qt
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from .browser import normalize_input
from .core.settings import Settings, default_settings_path
from .core.themes import BUILTIN_THEMES, Theme, page_theme_css

APP_NAME = "Nexlori"
APP_VERSION = "0.3.0"


def _theme_gradient(theme: Theme) -> str:
    colors = theme.stripes or (theme.accent,)
    stops = []
    for index, color in enumerate(colors):
        position = index / max(1, len(colors) - 1)
        stops.append(f"stop:{position:.3f} {color}")
    return "qlineargradient(x1:0, y1:0, x2:1, y2:0, " + ", ".join(stops) + ")"


def _start_page(theme: Theme) -> str:
    colors = ", ".join(theme.stripes or (theme.accent,))
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nexlori · Startseite</title>
<style>
:root {{ color-scheme: {'light' if theme.name in {'hell','ruhig'} else 'dark'}; }}
* {{ box-sizing:border-box }}
body {{ margin:0; min-height:100vh; background:{theme.bg}; color:{theme.fg}; font:16px 'Segoe UI',sans-serif;
 display:grid; place-items:center; }}
main {{ width:min(760px,92vw); padding:52px 0; }}
.mark {{ display:inline-block; color:{theme.accent}; font-size:13px; font-weight:800; letter-spacing:.24em; }}
h1 {{ margin:12px 0 8px; font-size:clamp(38px,7vw,66px); letter-spacing:-.055em; }}
p {{ color:{theme.fg}; opacity:.76; line-height:1.6; }}
.bar {{ display:flex; gap:10px; background:{theme.surface}; border:1px solid {theme.accent}66; border-radius:19px; padding:9px; margin:28px 0; }}
input {{ flex:1; min-width:0; border:0; outline:0; padding:13px; background:transparent; color:{theme.fg}; font:inherit; }}
button {{ background:{theme.accent}; color:{theme.bg}; border:0; border-radius:13px; padding:0 20px; font-weight:700; cursor:pointer; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }}
a.tile {{ text-decoration:none; color:{theme.fg}; display:block; border:1px solid {theme.surface}; border-radius:15px; padding:18px; background:{theme.surface}; }}
a.tile:hover {{ border-color:{theme.accent}; transform:translateY(-1px); }}
small {{ display:block; opacity:.65; margin-top:7px; }}
.foot {{ font-size:12px; margin-top:28px; opacity:.56; }}
.stripe {{ height:4px; border-radius:5px; background:linear-gradient(90deg,{colors}); margin-bottom:30px; }}
</style></head><body><main><div class="stripe"></div><span class="mark">NEXLORI / BROWSER</span>
<h1>Das Web. Auf deine Art.</h1><p>Dein Browser für das offene Web, mit Themes, die zu dir passen.</p>
<form class="bar" id="search"><input id="query" autocomplete="off" autofocus placeholder="Suchen oder Webadresse eingeben" aria-label="Suchen oder Webadresse eingeben"><button type="submit">Los</button></form>
<div class="tiles">
<a class="tile" href="https://www.wikipedia.org/">Wissen<small>Wikipedia</small></a>
<a class="tile" href="https://www.youtube.com/">Video<small>YouTube</small></a>
<a class="tile" href="https://github.com/">Entwickeln<small>GitHub</small></a>
<a class="tile" href="https://www.duckduckgo.com/">Privat suchen<small>DuckDuckGo</small></a>
</div><div class="foot">Nexlori · Chromium-WebEngine · Deine Themes, deine Einstellungen.</div>
<script>
document.getElementById('search').addEventListener('submit', function(e) {{
 e.preventDefault(); const q=document.getElementById('query').value.trim(); if(!q) return;
 const looksLikeUrl=/^(https?:\\/\\/|file:\\/\\/)/i.test(q) || (/^[^\\s]+\\.[^\\s]+$/.test(q) && !q.includes(' '));
 location.href=looksLikeUrl?(q.match(/^[a-z]+:\\/\\//i)?q:'https://'+q):'https://duckduckgo.com/?q='+encodeURIComponent(q);
}});
</script></main></body></html>"""


class AddressBar(QLineEdit):
    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


class BrowserPage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, owner: "NexloriWindow", parent: QWidget):
        super().__init__(profile, parent)
        self.owner = owner

    def createWindow(self, _window_type):  # noqa: N802
        # Open target=_blank, window.open and similar links in a Nexlori tab.
        view = self.owner.new_tab(start_page=False, activate=True)
        return view.page()

    def acceptNavigationRequest(self, url: QUrl, navigation_type, is_main_frame: bool) -> bool:  # noqa: N802
        if url.scheme().lower() in {"mailto", "tel"}:
            QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)


class NexloriWindow(QMainWindow):
    def __init__(
        self,
        settings: Settings,
        settings_path: Path,
        start_url: str | None = None,
        *,
        self_test: bool = False,
    ):
        super().__init__()
        self.settings = settings
        self.settings_path = settings_path
        self.storage_dir = settings_path.parent / "web-profile"
        self.cache_dir = self.storage_dir / "cache"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.bookmarks_path = settings_path.parent / "bookmarks.json"
        self.bookmarks = self._load_bookmarks()
        self._closing = False
        self._self_test = self_test
        self.theme = BUILTIN_THEMES.get(settings.theme, BUILTIN_THEMES["dunkel"])

        self.profile = QWebEngineProfile("Nexlori", self)
        self.profile.setPersistentStoragePath(str(self.storage_dir))
        self.profile.setCachePath(str(self.cache_dir))
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        self.profile.downloadRequested.connect(self._download_requested)

        self.setWindowTitle("Nexlori")
        self.resize(1240, 820)
        self.setMinimumSize(760, 480)
        self._build_ui()
        self._apply_browser_theme()
        self._bind_shortcuts()
        view = self.new_tab(start_page=start_url is None, activate=True)
        if start_url:
            self.navigate_view(view, start_url)

    def _build_ui(self) -> None:
        root = QWidget(self)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.accent_line = QWidget(root)
        self.accent_line.setFixedHeight(4)
        outer.addWidget(self.accent_line)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(7, 5, 7, 0)
        tab_row.setSpacing(6)
        self.tabs = QTabWidget(root)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_current_changed)
        tab_row.addWidget(self.tabs, 1)

        self.new_tab_button = QToolButton(root)
        self.new_tab_button.setText("+")
        self.new_tab_button.setToolTip("Neuer Tab (Strg+T)")
        self.new_tab_button.setObjectName("newTabButton")
        self.new_tab_button.clicked.connect(lambda: self.new_tab())
        tab_row.addWidget(self.new_tab_button)
        tab_widget = QWidget(root)
        tab_widget.setLayout(tab_row)
        outer.addWidget(tab_widget)

        toolbar = QWidget(root)
        toolbar.setObjectName("toolbar")
        nav = QHBoxLayout(toolbar)
        nav.setContentsMargins(12, 9, 12, 10)
        nav.setSpacing(6)

        self.back_button = self._tool("←", "Zurück", self.go_back)
        self.forward_button = self._tool("→", "Vorwärts", self.go_forward)
        self.reload_button = self._tool("⟳", "Neu laden", self.reload_current)
        self.home_button = self._tool("⌂", "Startseite", self.go_home)
        for button in (self.back_button, self.forward_button, self.reload_button, self.home_button):
            nav.addWidget(button)

        self.address = AddressBar(toolbar)
        self.address.setObjectName("addressBar")
        self.address.setPlaceholderText("Suchen oder Webadresse eingeben")
        self.address.setClearButtonEnabled(True)
        self.address.setMinimumHeight(42)
        self.address.returnPressed.connect(self.navigate_address)
        nav.addWidget(self.address, 1)

        self.bookmark_button = self._tool("☆", "Lesezeichen hinzufügen/entfernen", self.toggle_bookmark)
        nav.addWidget(self.bookmark_button)
        self.page_theme_button = QToolButton(toolbar)
        self.page_theme_button.setText("Aa")
        self.page_theme_button.setToolTip("Webseite an das aktive Theme anpassen")
        self.page_theme_button.setCheckable(True)
        self.page_theme_button.setChecked(self.settings.adapt_page_theme)
        self.page_theme_button.toggled.connect(self.toggle_page_theme)
        self.page_theme_button.setObjectName("pageThemeButton")
        nav.addWidget(self.page_theme_button)

        self.theme_button = self._tool("✦", "Theme auswählen", self.show_theme_menu)
        nav.addWidget(self.theme_button)
        self.more_button = self._tool("⋮", "Nexlori-Menü", self.show_more_menu)
        nav.addWidget(self.more_button)
        outer.addWidget(toolbar)

        self.find_bar = QWidget(root)
        find_layout = QHBoxLayout(self.find_bar)
        find_layout.setContentsMargins(14, 2, 14, 7)
        find_layout.setSpacing(8)
        find_layout.addWidget(QLabel("Auf Seite suchen"))
        self.find_input = QLineEdit(self.find_bar)
        self.find_input.setPlaceholderText("Suchtext")
        self.find_input.returnPressed.connect(self.find_next)
        find_layout.addWidget(self.find_input, 1)
        prev_btn = self._tool("↑", "Vorheriges Ergebnis", self.find_previous)
        next_btn = self._tool("↓", "Nächstes Ergebnis", self.find_next)
        close_btn = self._tool("×", "Suche schließen", self.hide_find)
        find_layout.addWidget(prev_btn)
        find_layout.addWidget(next_btn)
        find_layout.addWidget(close_btn)
        self.find_bar.hide()
        outer.addWidget(self.find_bar)

        self.progress = QProgressBar(root)
        self.progress.setObjectName("loadProgress")
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        outer.addWidget(self.progress)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Nexlori · Chromium-WebEngine")
        self._build_theme_menu()
        self._build_more_menu()

    def _tool(self, label: str, tip: str, callback) -> QToolButton:
        button = QToolButton(self)
        button.setText(label)
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def _build_theme_menu(self) -> None:
        self.theme_menu = QMenu(self)
        self.theme_menu.setTitle("Theme")
        self.theme_actions: dict[str, QAction] = {}
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        groups = (
            ("Basis", [n for n in ("hell", "dunkel", "ruhig", "hochkontrast") if n in BUILTIN_THEMES]),
            ("Pride", [n for n in BUILTIN_THEMES if n.startswith("pride-")]),
            ("Weitere Looks", [n for n in BUILTIN_THEMES if n not in {"hell", "dunkel", "ruhig", "hochkontrast"} and not n.startswith("pride-")]),
        )
        for label, names in groups:
            if not names:
                continue
            submenu = self.theme_menu.addMenu(label)
            for name in names:
                theme = BUILTIN_THEMES[name]
                action = QAction(theme.label, self)
                action.setCheckable(True)
                action.setChecked(name == self.settings.theme)
                self.theme_action_group.addAction(action)
                self.theme_actions[name] = action
                action.triggered.connect(lambda _checked=False, n=name: self.set_theme(n))
                submenu.addAction(action)

    def _build_more_menu(self) -> None:
        self.more_menu = QMenu(self)
        self.more_menu.addAction("Neuer Tab", self.new_tab, QKeySequence("Ctrl+T"))
        self.more_menu.addAction("Lesezeichen", self.show_bookmarks_menu, QKeySequence("Ctrl+Shift+B"))
        self.more_menu.addAction("Verlauf dieser Sitzung", self.show_history_menu)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Downloads-Ordner öffnen", self.open_download_folder)
        self.more_menu.addAction("Webseite neu laden", self.reload_current, QKeySequence("F5"))
        self.more_menu.addAction("Theme auswählen", self.show_theme_menu)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Über Nexlori", self.show_about)
        self.more_menu.addAction("Beenden", self.close, QKeySequence("Alt+F4"))

    def _bind_shortcuts(self) -> None:
        shortcuts = (
            ("Ctrl+T", lambda: self.new_tab()),
            ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+L", self.focus_address),
            ("Ctrl+R", self.reload_current),
            ("F5", self.reload_current),
            ("Alt+Left", self.go_back),
            ("Alt+Right", self.go_forward),
            ("Alt+Home", self.go_home),
            ("Ctrl+F", self.show_find),
            ("Ctrl+D", self.toggle_bookmark),
            ("Ctrl+Plus", lambda: self.change_zoom(0.1)),
            ("Ctrl+Minus", lambda: self.change_zoom(-0.1)),
            ("Ctrl+0", lambda: self.set_zoom(1.0)),
        )
        self._shortcuts = []
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _apply_browser_theme(self) -> None:
        theme = self.theme
        self.setStyleSheet(f"""
QMainWindow, QWidget {{ background:{theme.bg}; color:{theme.fg}; }}
QWidget#toolbar {{ background:{theme.bg}; }}
QTabWidget::pane {{ border:0; background:{theme.bg}; }}
QTabBar {{ background:{theme.surface}; }}
QTabBar::tab {{ background:{theme.surface}; color:{theme.fg}; border:1px solid transparent;
 border-top-left-radius:10px; border-top-right-radius:10px; padding:10px 13px; margin-right:3px; min-width:90px; }}
QTabBar::tab:selected {{ background:{theme.bg}; border-color:{theme.surface}; border-bottom:2px solid {theme.accent}; }}
QTabBar::tab:hover {{ background:{theme.bg}; }}
QToolButton {{ color:{theme.fg}; background:transparent; border:0; border-radius:12px; min-width:34px; min-height:34px; padding:3px; font-size:17px; }}
QToolButton:hover {{ background:{theme.surface}; }}
QToolButton:pressed, QToolButton:checked {{ background:{theme.surface}; color:{theme.accent}; }}
QToolButton#newTabButton {{ font-size:21px; min-width:36px; min-height:36px; }}
QLineEdit {{ background:{theme.surface}; color:{theme.fg}; selection-background-color:{theme.accent}; selection-color:{theme.bg}; border:1px solid {theme.surface}; border-radius:16px; padding:9px 15px; }}
QLineEdit:focus {{ border:1px solid {theme.accent}; }}
QLineEdit#addressBar {{ font-size:14px; }}
QMenu {{ background:{theme.surface}; color:{theme.fg}; border:1px solid {theme.accent}; padding:5px; }}
QMenu::item {{ padding:7px 26px 7px 12px; border-radius:7px; }}
QMenu::item:selected {{ background:{theme.bg}; color:{theme.accent}; }}
QProgressBar#loadProgress {{ border:0; background:{theme.surface}; }}
QProgressBar#loadProgress::chunk {{ background:{theme.accent}; }}
QStatusBar {{ background:{theme.surface}; color:{theme.fg}; }}
QStatusBar::item {{ border:0; }}
QLabel {{ background:transparent; }}
""")
        self.accent_line.setStyleSheet(f"background:{_theme_gradient(theme)};")
        self.tabs.setStyleSheet(f"QTabWidget::pane {{ border:0; background:{theme.bg}; }}")
        self.statusBar().setStyleSheet(f"QStatusBar {{ background:{theme.surface}; color:{theme.fg}; }}")
    def set_theme(self, name: str) -> None:
        if name not in BUILTIN_THEMES:
            return
        self.theme = BUILTIN_THEMES[name]
        self.settings.theme = name
        self._apply_browser_theme()
        for action_name, action in self.theme_actions.items():
            action.setChecked(action_name == name)
        self._save_settings()
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if isinstance(view, QWebEngineView):
                view.page().setBackgroundColor(self._qt_color(self.theme.bg))
                self.apply_page_theme(view)
                if getattr(view, "_nexlori_start", False):
                    view.setHtml(_start_page(self.theme), QUrl("about:blank"))
        self.statusBar().showMessage(f"Theme: {self.theme.label}", 2500)

    @staticmethod
    def _qt_color(value: str):
        from PySide6.QtGui import QColor
        return QColor(value)

    def _build_page_theme_script(self, enabled: bool) -> str:
        css = page_theme_css(self.theme)
        css_literal = json.dumps(css)
        return f"""(() => {{
const id = 'nexlori-theme-user-style';
window.__nexloriThemeConfig = {{enabled:{str(enabled).lower()}, css:{css_literal}}};
const remove = () => {{ const old = document.getElementById(id); if (old) old.remove(); }};
const ensure = () => {{
  const config = window.__nexloriThemeConfig;
  if (!document.documentElement) return;
  if (!config.enabled) {{ remove(); return; }}
  let style = document.getElementById(id);
  if (!style) {{
    style = document.createElement('style');
    style.id = id;
    (document.head || document.documentElement).appendChild(style);
  }}
  if (style.textContent !== config.css) style.textContent = config.css;
}};
ensure();
if (!window.__nexloriThemeObserver) {{
  const observer = new MutationObserver(() => {{
    const config = window.__nexloriThemeConfig;
    if (config && config.enabled && !document.getElementById(id)) ensure();
  }});
  if (document.documentElement) observer.observe(document.documentElement, {{childList:true, subtree:true}});
  window.__nexloriThemeObserver = observer;
}}
}})();"""

    def apply_page_theme(self, view: QWebEngineView) -> None:
        # An injected user stylesheet changes colours; Qt WebEngine continues to run the original website.
        view.page().runJavaScript(self._build_page_theme_script(self.settings.adapt_page_theme))

    def toggle_page_theme(self, enabled: bool) -> None:
        self.settings.adapt_page_theme = bool(enabled)
        self._save_settings()
        self.page_theme_button.setToolTip(
            "Webseiten-Theme ist an" if enabled else "Webseiten-Theme ist aus"
        )
        view = self.current_view()
        if view:
            self.apply_page_theme(view)

    def new_tab(
        self,
        url: str | None = None,
        *,
        start_page: bool = True,
        activate: bool = True,
    ) -> QWebEngineView:
        view = QWebEngineView(self.tabs)
        page = BrowserPage(self.profile, self, view)
        view.setPage(page)
        view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        view.settings().setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, True)
        view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        view.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        view.setZoomFactor(self.settings.page_zoom)
        view.page().setBackgroundColor(self._qt_color(self.theme.bg))
        view.titleChanged.connect(lambda title, w=view: self._update_tab_title(w, title))
        view.urlChanged.connect(lambda url, w=view: self._on_url_changed(w, url))
        view.loadStarted.connect(lambda w=view: self._load_started(w))
        view.loadProgress.connect(lambda value, w=view: self._load_progress(w, value))
        view.loadFinished.connect(lambda ok, w=view: self._load_finished(w, ok))
        view.page().linkHovered.connect(self._on_link_hovered)
        index = self.tabs.addTab(view, "Neuer Tab")
        if activate:
            self.tabs.setCurrentIndex(index)
        if start_page:
            view._nexlori_start = True
            view.setHtml(_start_page(self.theme), QUrl("about:blank"))
        elif url:
            view._nexlori_start = False
            view.setUrl(QUrl(url))
        else:
            view._nexlori_start = False
            view.setUrl(QUrl("about:blank"))
        if activate:
            self.focus_address()
        return view

    def current_view(self) -> QWebEngineView | None:
        view = self.tabs.currentWidget()
        return view if isinstance(view, QWebEngineView) else None

    def close_tab(self, index: int) -> None:
        if index < 0 or index >= self.tabs.count():
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if widget:
            widget.deleteLater()
        if self.tabs.count() == 0:
            self.new_tab()
        self._update_navigation_state()

    def _on_current_changed(self, _index: int) -> None:
        view = self.current_view()
        if view:
            self._on_url_changed(view, view.url())
            self._update_bookmark_button()
        self._update_navigation_state()

    def _update_tab_title(self, view: QWebEngineView, title: str) -> None:
        index = self.tabs.indexOf(view)
        if index < 0:
            return
        title = title.strip() or ("Nexlori · Startseite" if getattr(view, "_nexlori_start", False) else "Neuer Tab")
        self.tabs.setTabText(index, title[:26] + ("…" if len(title) > 26 else ""))
        if index == self.tabs.currentIndex():
            self.setWindowTitle(f"{title} — Nexlori")
            self._update_bookmark_button()

    def _on_url_changed(self, view: QWebEngineView, url: QUrl) -> None:
        url_text = url.toString()
        if url_text and url_text != "about:blank":
            # The start page may navigate through its own search form or links.
            view._nexlori_start = False
        if view is self.current_view():
            if getattr(view, "_nexlori_start", False) and url_text == "about:blank":
                self.address.clear()
            else:
                self.address.setText(url_text)
            self._update_navigation_state()
            self._update_bookmark_button()

    def _load_started(self, view: QWebEngineView) -> None:
        if view is self.current_view():
            self.progress.setValue(0)
            self.progress.show()
            self.statusBar().showMessage("Seite wird geladen …")

    def _load_progress(self, view: QWebEngineView, value: int) -> None:
        if view is self.current_view():
            self.progress.setValue(value)
            if value >= 100:
                self.progress.hide()

    def _load_finished(self, view: QWebEngineView, ok: bool) -> None:
        if view is self.current_view():
            self.progress.hide()
            self.statusBar().showMessage(
                "Geladen" if ok else "Seite konnte nicht vollständig geladen werden", 3500
            )
        self.apply_page_theme(view)
        if getattr(view, "_nexlori_start", False) and view.url().toString() == "about:blank":
            index = self.tabs.indexOf(view)
            if index >= 0:
                self.tabs.setTabText(index, "Nexlori · Startseite")

    def _on_link_hovered(self, url: str) -> None:
        if url:
            self.statusBar().showMessage(url)
        else:
            self.statusBar().showMessage("Nexlori · Chromium-WebEngine")

    def _update_navigation_state(self) -> None:
        view = self.current_view()
        enabled = view is not None
        self.back_button.setEnabled(enabled and view.history().canGoBack())
        self.forward_button.setEnabled(enabled and view.history().canGoForward())
        self.reload_button.setEnabled(enabled)
        self.home_button.setEnabled(enabled)

    def navigate_address(self) -> None:
        text = self.address.text().strip()
        if not text:
            self.go_home()
            return
        target = normalize_input(text, self.settings.search_url)
        scheme = urlsplit(target).scheme.lower()
        if scheme in {"javascript", "data", "vbscript"}:
            self.statusBar().showMessage("Dieses Adressschema wird aus Sicherheitsgründen nicht direkt geöffnet.", 4500)
            return
        view = self.current_view()
        if view is not None:
            self.navigate_view(view, target)

    def navigate_view(self, view: QWebEngineView, url: str) -> None:
        if url.lower() in {"about:start", "nexlori:start"}:
            view._nexlori_start = True
            view.setHtml(_start_page(self.theme), QUrl("about:blank"))
            return
        view._nexlori_start = False
        view.setUrl(QUrl(url))

    def go_back(self) -> None:
        view = self.current_view()
        if view and view.history().canGoBack():
            view.back()

    def go_forward(self) -> None:
        view = self.current_view()
        if view and view.history().canGoForward():
            view.forward()

    def reload_current(self) -> None:
        view = self.current_view()
        if view is None:
            return
        if getattr(view, "_nexlori_start", False) and view.url().toString() == "about:blank":
            view.setHtml(_start_page(self.theme), QUrl("about:blank"))
        else:
            view.reload()

    def go_home(self) -> None:
        view = self.current_view()
        if view:
            view._nexlori_start = True
            view.setHtml(_start_page(self.theme), QUrl("about:blank"))
            index = self.tabs.indexOf(view)
            if index >= 0:
                self.tabs.setTabText(index, "Nexlori · Startseite")

    def focus_address(self) -> None:
        self.address.setFocus()
        self.address.selectAll()

    def show_find(self) -> None:
        self.find_bar.show()
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_find(self) -> None:
        view = self.current_view()
        if view:
            view.findText("")
        self.find_bar.hide()
        if view:
            view.setFocus()

    def find_next(self) -> None:
        view = self.current_view()
        if view and self.find_input.text():
            view.findText(self.find_input.text())

    def find_previous(self) -> None:
        view = self.current_view()
        if view and self.find_input.text():
            view.findText(self.find_input.text(), QWebEnginePage.FindFlag.FindBackward)

    def set_zoom(self, value: float) -> None:
        self.settings.page_zoom = min(3.0, max(0.5, round(value, 2)))
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if isinstance(view, QWebEngineView):
                view.setZoomFactor(self.settings.page_zoom)
        self._save_settings()
        self.statusBar().showMessage(f"Zoom: {self.settings.page_zoom:.0%}", 2200)

    def change_zoom(self, delta: float) -> None:
        self.set_zoom(self.settings.page_zoom + delta)

    def toggle_bookmark(self) -> None:
        view = self.current_view()
        if not view or getattr(view, "_nexlori_start", False):
            self.statusBar().showMessage("Die Startseite wird nicht als Lesezeichen gespeichert.", 2500)
            return
        url = view.url().toString()
        if not url or url == "about:blank":
            return
        match = next((item for item in self.bookmarks if item.get("url") == url), None)
        if match:
            self.bookmarks.remove(match)
            message = "Lesezeichen entfernt"
        else:
            self.bookmarks.append({"title": view.title() or url, "url": url})
            message = "Lesezeichen gespeichert"
        self._save_bookmarks()
        self._update_bookmark_button()
        self.statusBar().showMessage(message, 2200)

    def _update_bookmark_button(self) -> None:
        view = self.current_view()
        url = view.url().toString() if view else ""
        saved = any(item.get("url") == url for item in self.bookmarks)
        self.bookmark_button.setText("★" if saved else "☆")

    def _load_bookmarks(self) -> list[dict[str, str]]:
        try:
            data = json.loads(self.bookmarks_path.read_text(encoding="utf-8"))
            return [x for x in data if isinstance(x, dict) and x.get("url")]
        except (OSError, ValueError, TypeError):
            return []

    def _save_bookmarks(self) -> None:
        try:
            self.bookmarks_path.parent.mkdir(parents=True, exist_ok=True)
            self.bookmarks_path.write_text(json.dumps(self.bookmarks, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            self.statusBar().showMessage("Lesezeichen konnten nicht gespeichert werden.", 3500)

    def show_bookmarks_menu(self) -> None:
        menu = QMenu(self)
        if not self.bookmarks:
            action = menu.addAction("Noch keine Lesezeichen")
            action.setEnabled(False)
        else:
            for item in self.bookmarks:
                action = menu.addAction(item.get("title", item["url"]))
                action.setToolTip(item["url"])
                action.triggered.connect(lambda _checked=False, u=item["url"]: self.open_bookmark(u))
        menu.addSeparator()
        menu.addAction("Aktuelle Seite als Lesezeichen", self.toggle_bookmark)
        menu.exec(self.more_button.mapToGlobal(QPoint(0, self.more_button.height())))

    def show_history_menu(self) -> None:
        menu = QMenu(self)
        view = self.current_view()
        entries = []
        if view:
            history = view.history()
            items = history.items()
            entries = [(item.title() or item.url().toString(), item.url().toString()) for item in items[-20:]]
        if not entries:
            action = menu.addAction("Noch kein Verlauf")
            action.setEnabled(False)
        else:
            for title, url in reversed(entries):
                action = menu.addAction(title[:60])
                action.setToolTip(url)
                action.triggered.connect(lambda _checked=False, u=url: self.open_bookmark(u))
        menu.exec(self.more_button.mapToGlobal(QPoint(0, self.more_button.height())))

    def open_bookmark(self, url: str) -> None:
        view = self.current_view()
        if view:
            self.navigate_view(view, url)

    def show_theme_menu(self) -> None:
        self.theme_menu.exec(self.theme_button.mapToGlobal(QPoint(0, self.theme_button.height())))

    def show_more_menu(self) -> None:
        self.more_menu.exec(self.more_button.mapToGlobal(QPoint(0, self.more_button.height())))

    def _download_requested(self, download: QWebEngineDownloadRequest) -> None:
        suggested = download.suggestedFileName() or "download"
        initial = str(Path.home() / "Downloads" / suggested)
        filename, _ = QFileDialog.getSaveFileName(self, "Download speichern", initial)
        if not filename:
            download.cancel()
            return
        target = Path(filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        download.setDownloadDirectory(str(target.parent))
        download.setDownloadFileName(target.name)
        download.accept()
        self.statusBar().showMessage(f"Download gestartet: {target.name}", 3500)

    def open_download_folder(self) -> None:
        path = Path.home() / "Downloads"
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "Über Nexlori",
            "<h3>Nexlori</h3><p>Dein Web. Dein Look.</p>"
            "<p>Chromium-WebEngine für moderne Websites, mit lokalen Themes und ohne Nexlori-Telemetrie.</p>"
            "<p>Die Darstellung einer Website kann durch das optionale Theme-CSS verändert werden.</p>",
        )

    def _save_settings(self) -> None:
        try:
            self.settings.save(self.settings_path)
        except (OSError, ValueError):
            self.statusBar().showMessage("Einstellungen konnten nicht gespeichert werden.", 3000)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_settings()
        self._save_bookmarks()
        super().closeEvent(event)


def _selftest_webengine() -> tuple[bool, str]:
    """Run a tiny local-page and JavaScript check against the packaged WebEngine."""
    app = QApplication.instance() or QApplication(["Nexlori-selftest"])
    # An off-the-record profile keeps this packaging check isolated from the user's real profile.
    profile = QWebEngineProfile(app)
    page = QWebEnginePage(profile, app)
    loop = QEventLoop()
    result: dict[str, object] = {"ok": False, "title": ""}

    def on_loaded(ok: bool) -> None:
        if not ok:
            result["error"] = "local HTML did not load"
            loop.quit()
            return
        page.runJavaScript(
            "document.title + '|' + (typeof Promise) + '|' + document.querySelector('#works').textContent",
            lambda value: (result.update({"ok": value == "Nexlori Engine Test|function|works", "title": str(value)}), loop.quit()),
        )

    page.loadFinished.connect(on_loaded)
    QTimer.singleShot(15000, loop.quit)
    page.setHtml("<!doctype html><html><head><title>Nexlori Engine Test</title></head><body><p id='works'>works</p></body></html>")
    loop.exec()
    page.deleteLater()
    profile.deleteLater()
    app.processEvents()
    if not result.get("ok"):
        return False, str(result.get("error") or result.get("title") or "WebEngine JavaScript test timed out")
    return True, str(result["title"])


def run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--webengine-selftest"]:
        try:
            ok, detail = _selftest_webengine()
            print(("OK " if ok else "FEHLER ") + detail)
            return 0 if ok else 5
        except Exception as exc:  # noqa: BLE001
            print(f"FEHLER WebEngine: {type(exc).__name__}: {exc}")
            return 5

    settings_path = default_settings_path()
    try:
        settings = Settings.load(settings_path)
    except (ValueError, OSError):
        settings = Settings()

    app = QApplication.instance() or QApplication([APP_NAME])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Nexlori")
    app.setStyle("Fusion")
    start_url = None
    if argv:
        start_url = normalize_input(" ".join(arg for arg in argv if not arg.startswith("-")), settings.search_url)
    window = NexloriWindow(settings, settings_path, start_url)
    window.show()
    return app.exec()
