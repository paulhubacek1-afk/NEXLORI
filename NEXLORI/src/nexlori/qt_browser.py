"""Nexlori's Chromium-based browser UI.

The legacy renderer is kept for educational rendering tests; real pages are rendered by Qt WebEngine.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import QEventLoop, QEasingCurve, QPoint, QPropertyAnimation, QThread, QTimer, QUrl, QUrlQuery, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QGraphicsOpacityEffect,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineSettings,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from . import __version__
from .browser import normalize_input
from .core.settings import Settings, default_settings_path
from .core.themes import BUILTIN_THEMES, Theme, combine_themes, relative_luminance
from .default_browser import default_browser_settings_uri, register_windows_browser
from .web_safety import addons_page_html, error_page_html, home_network_page_html, is_nsfw_url, normalize_home_target
from .extension_utils import (
    bundled_ubolite_path,
    unpack_extension_package,
    extension_key_from_info,
    extension_key_from_name,
    extension_name_from_info,
    is_builtin_extension,
  )
from .page_theme import build_page_theme_script

APP_NAME = "Nexlori"
APP_VERSION = __version__
FEEDBACK_EMAIL = "nexlori-browser@gmx.at"
REPOSITORY_URL = "https://github.com/paulhubacek1-afk/NEXLORI"


def _qt_app_icon(theme: Theme | None = None) -> QIcon:
    """Create the application icon from the active theme palette."""
    from .icon import make_icon

    image = make_icon(256, theme=theme)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return QIcon(pixmap)


def _theme_gradient(theme: Theme) -> str:
    colors = theme.stripes or (theme.accent,)
    stops = []
    for index, color in enumerate(colors):
        position = index / max(1, len(colors) - 1)
        stops.append(f"stop:{position:.3f} {color}")
    return "qlineargradient(x1:0, y1:0, x2:1, y2:0, " + ", ".join(stops) + ")"


def _start_page(theme: Theme, search_url: str, pride_mode: bool = False) -> str:
    """A polished, theme-aware private start page; its animations never affect normal websites."""
    colors = ", ".join(theme.stripes or (theme.accent,))
    search_template = json.dumps(search_url, ensure_ascii=False)
    pride_visuals = (
        '<div class="pride-glow glow-a" aria-hidden="true"></div>'
        '<div class="pride-glow glow-b" aria-hidden="true"></div>'
        '<div class="pride-glow glow-c" aria-hidden="true"></div>'
        if pride_mode else ""
    )
    pride_css = """
.pride-glow { position:fixed; z-index:0; width:38vw; height:38vw; min-width:230px; min-height:230px;
  border-radius:50%; filter:blur(55px); opacity:.16; pointer-events:none; animation:pride-drift 17s ease-in-out infinite alternate; }
.glow-a { left:-13vw; top:10vh; background:#ff3b8d; }
.glow-b { right:-12vw; top:22vh; background:#35c8ff; animation-delay:-5s; }
.glow-c { left:34vw; bottom:-27vw; background:#a56bff; animation-delay:-9s; }
@keyframes pride-drift { from { transform:translate3d(0,-2vh,0) scale(.92); } to { transform:translate3d(2vw,3vh,0) scale(1.08); } }
""" if pride_mode else ""
    pride_pill = '<span class="pride-pill">✦ Pride colours in motion</span>' if pride_mode else ""
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nexlori · Startseite</title>
<style>
:root {{ color-scheme: {'light' if relative_luminance(theme.bg) >= 0.5 else 'dark'}; }}
* {{ box-sizing:border-box }}
body {{ margin:0; min-height:100vh; overflow-x:hidden; background:{theme.bg}; color:{theme.fg}; font:16px 'Segoe UI',sans-serif; }}
main {{ position:relative; z-index:1; width:min(900px,92vw); margin:0 auto; padding:42px 0 36px; animation:page-enter .55s cubic-bezier(.2,.8,.2,1) both; }}
.stripe {{ height:5px; border-radius:5px; background:linear-gradient(90deg,{colors}); margin-bottom:32px; background-size:200% 100%; animation:stripe-flow 9s ease-in-out infinite alternate; }}
.mark {{ display:inline-block; color:{theme.accent}; font-size:12px; font-weight:800; letter-spacing:.22em; }}
h1 {{ margin:14px 0 8px; font-size:clamp(38px,6.5vw,68px); line-height:1.04; letter-spacing:-.055em; }}
p {{ color:{theme.fg}; opacity:.82; line-height:1.65; }}
.intro {{ max-width:650px; font-size:17px; }}
.pride-pill {{ display:inline-block; margin-top:14px; padding:7px 12px; border:1px solid {theme.accent}55; border-radius:100px; color:{theme.accent}; font-size:12px; }}
.bar {{ display:flex; gap:10px; background:{theme.surface}; border:1px solid {theme.accent}80; border-radius:20px; padding:9px; margin:28px 0 24px; box-shadow:0 16px 50px {theme.accent}16; transition:border-color .2s ease,transform .2s ease,box-shadow .2s ease; }}
.bar:focus-within {{ border-color:{theme.accent}; transform:translateY(-2px); box-shadow:0 18px 54px {theme.accent}25; }}
input {{ flex:1; min-width:0; border:0; outline:0; padding:13px; background:transparent; color:{theme.fg}; font:inherit; }}
button {{ background:{theme.accent}; color:{theme.bg}; border:0; border-radius:13px; padding:0 20px; font-weight:800; cursor:pointer; transition:transform .18s ease,filter .18s ease; }}
button:hover {{ transform:translateY(-1px); filter:brightness(1.08); }} button:active {{ transform:scale(.98); }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:12px; }}
a.tile {{ text-decoration:none; color:{theme.fg}; display:block; border:1px solid {theme.surface}; border-radius:17px; padding:19px; background:{theme.surface}; transition:transform .22s ease,border-color .22s ease,box-shadow .22s ease; animation:tile-enter .55s ease both; }}
a.tile:nth-child(2) {{ animation-delay:.05s; }} a.tile:nth-child(3) {{ animation-delay:.10s; }} a.tile:nth-child(4) {{ animation-delay:.15s; }} a.tile:nth-child(5) {{ animation-delay:.20s; }} a.tile:nth-child(6) {{ animation-delay:.25s; }}
a.tile:hover {{ border-color:{theme.accent}; transform:translateY(-4px); box-shadow:0 12px 30px {theme.accent}18; }}
.tile-icon {{ display:block; color:{theme.accent}; font-size:22px; margin-bottom:9px; }}
small {{ display:block; opacity:.68; margin-top:7px; line-height:1.45; }}
.foot {{ font-size:12px; margin-top:28px; opacity:.56; }}
@keyframes page-enter {{ from {{ opacity:0; transform:translateY(9px); }} to {{ opacity:1; transform:translateY(0); }} }}
@keyframes tile-enter {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:translateY(0); }} }}
@keyframes stripe-flow {{ from {{ background-position:0 0; }} to {{ background-position:100% 0; }} }}
{pride_css}
@media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ animation:none !important; transition:none !important; }} }}
</style></head><body>{pride_visuals}<main><div class="stripe"></div><span class="mark">NEXLORI / BROWSER</span>
<h1>Das Web. Auf deine Art.</h1><p class="intro">Ein Browser, der sich deinem Stil anpasst – mit persönlicher Farbwelt, ruhiger Oberfläche und lokalem Schutz.</p>{pride_pill}
<form class="bar" id="search"><input id="query" autocomplete="off" autofocus placeholder="Suchen oder Webadresse eingeben" aria-label="Suchen oder Webadresse eingeben"><button type="submit">Los ↗</button></form>
<div class="tiles">
<a class="tile" href="https://www.wikipedia.org/"><span class="tile-icon">⌕</span><strong>Wissen</strong><small>Wikipedia</small></a>
<a class="tile" href="https://www.youtube.com/"><span class="tile-icon">▶</span><strong>Video</strong><small>YouTube</small></a>
<a class="tile" href="https://github.com/"><span class="tile-icon">⌘</span><strong>Entwickeln</strong><small>GitHub</small></a>
<a class="tile" href="nexlori://addons"><span class="tile-icon">＋</span><strong>Add-ons</strong><small>Erweiterungen entdecken und verwalten</small></a>
<a class="tile" href="nexlori://home-network"><span class="tile-icon">⌂</span><strong>Heimnetz</strong><small>Router, NAS, Drucker und Smart Home</small></a>
<a class="tile" href="nexlori://settings"><span class="tile-icon">✦</span><strong>Dein Nexlori</strong><small>Themes, Suchmaschine und Einstellungen</small></a>
</div><div class="foot">Nexlori · Chromium-WebEngine · Schutz und Einstellungen bleiben lokal.</div>
<script>
const template = {search_template};
document.getElementById('search').addEventListener('submit', function(e) {{
 e.preventDefault(); const q=document.getElementById('query').value.trim(); if(!q) return;
 const looksLikeUrl=/^(https?:\/\/|file:\/\/)/i.test(q) || (/^[^\s]+\.[^\s]+$/.test(q) && !q.includes(' '));
 location.href=looksLikeUrl?(q.match(/^[a-z]+:\/\//i)?q:'https://'+q):template.replace("{{}}",encodeURIComponent(q));
}});
</script></main></body></html>"""

class AddressBar(QLineEdit):
    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


class UpdateWorker(QThread):
    """Runs update network requests away from the browser UI thread."""

    def __init__(self, task: str, *, release: dict | None = None, update_dir: Path | None = None, parent=None):
        super().__init__(parent)
        self.task = task
        self.release = release
        self.update_dir = update_dir
        self.result_data: dict = {"task": task}

    def run(self) -> None:
        try:
            from .updater import check_for_update, download_verified_update
            if self.task == "check":
                self.result_data["release"] = check_for_update(APP_VERSION)
            elif self.task == "download":
                if not self.release or self.update_dir is None:
                    raise RuntimeError("Update-Informationen fehlen.")
                self.result_data["path"] = str(download_verified_update(self.release, self.update_dir))
                self.result_data["release"] = self.release
            else:
                raise RuntimeError("Unbekannte Update-Aktion.")
        except Exception as exc:  # noqa: BLE001
            self.result_data["error"] = str(exc)


class BrowserPage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, owner: "NexloriWindow", parent: QWidget):
        super().__init__(profile, parent)
        self.owner = owner

    def createWindow(self, _window_type):  # noqa: N802
        # Website popups can be blocked or opened in a Nexlori tab from Settings.
        if not self.owner.settings.allow_web_popups:
            self.owner.statusBar().showMessage("Ein Website-Popup wurde durch Nexlori blockiert.", 3500)
            return None
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
        self._update_worker: UpdateWorker | None = None
        self._silent_update_check = True
        self._spotify_popup = None
        self.theme = combine_themes([settings.theme, *settings.theme_mix])

        self.profile = QWebEngineProfile("Nexlori", self)
        self.profile.setPersistentStoragePath(str(self.storage_dir))
        self.profile.setCachePath(str(self.cache_dir))
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        self.profile.downloadRequested.connect(self._download_requested)
        self._page_theme_script = None
        self._refresh_page_theme_script()
        try:
            self.extension_manager = self.profile.extensionManager()
            self.extension_manager.installFinished.connect(self._on_extension_installed)
            self.extension_manager.loadFinished.connect(lambda *_: self._sync_extension_states())
        except AttributeError:
            self.extension_manager = None

        self.setWindowTitle("Nexlori")
        self.setWindowIcon(_qt_app_icon())
        self.resize(1240, 820)
        self.setMinimumSize(760, 480)
        self._build_ui()
        self._apply_browser_theme()
        self._bind_shortcuts()
        view = self.new_tab(start_page=start_url is None, activate=True)
        if start_url:
            self.navigate_view(view, start_url)
        QTimer.singleShot(1200, self._ensure_default_extension)
        if self.settings.auto_update_check:
            QTimer.singleShot(2500, self._start_silent_update_check)

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
        # The tab-opening control stays on the left; the right side contains tabs only.
        self.new_tab_button = QToolButton(root)
        self.new_tab_button.setText("+")
        self.new_tab_button.setToolTip("Neuer Tab (Strg+T)")
        self.new_tab_button.setObjectName("newTabButton")
        self.new_tab_button.clicked.connect(lambda: self.new_tab())
        tab_row.addWidget(self.new_tab_button)

        self.tabs = QTabWidget(root)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_current_changed)
        tab_row.addWidget(self.tabs, 1)
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

        # Keep the address/search pill visually centered between the navigation and tool clusters.
        nav.addStretch(1)
        self.address = AddressBar(toolbar)
        self.address.setObjectName("addressBar")
        self.address.setPlaceholderText("Suchen oder Webadresse eingeben")
        self.address.setClearButtonEnabled(True)
        self.address.setMinimumHeight(42)
        self.address.setMinimumWidth(220)
        self.address.setMaximumWidth(self.settings.toolbar_search_width)
        self.address.returnPressed.connect(self.navigate_address)
        nav.addWidget(self.address, 0)
        nav.addStretch(1)

        self.bookmark_button = self._tool("☆", "Lesezeichen hinzufügen/entfernen", self.toggle_bookmark)
        nav.addWidget(self.bookmark_button)
        self.music_button = self._tool("♫", "Spotify Mini-Player", self.show_spotify_popup)
        nav.addWidget(self.music_button)
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
        self.toolbar_icons = {
            "home": self.home_button,
            "bookmark": self.bookmark_button,
            "spotify": self.music_button,
            "page_theme": self.page_theme_button,
            "theme": self.theme_button,
        }
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
        self._apply_toolbar_preferences()
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
        # A theme can occur in the three-favourites submenu and in the full list.
        # Let set_theme synchronise every copy rather than letting Qt uncheck duplicates.
        self.theme_action_group.setExclusive(False)
        self._theme_action_copies: dict[str, list[QAction]] = {}

        favourites = self.theme_menu.addMenu("Deine 3 Pride-Favoriten")
        chosen = [name for name in self.settings.pride_favorites if name in BUILTIN_THEMES]
        if not chosen:
            action = favourites.addAction("Noch keine Favoriten ausgewählt")
            action.setEnabled(False)
        for name in chosen:
            self._add_theme_action(favourites, name)
        favourites.addSeparator()
        favourites.addAction("Favoriten auswählen …", self.edit_pride_favorites)

        groups = (
            ("Basis", [n for n in ("hell", "dunkel", "ruhig", "hochkontrast") if n in BUILTIN_THEMES]),
            ("Alle Pride-Flaggen", [n for n in BUILTIN_THEMES if n.startswith("pride-")]),
            ("Weitere Looks", [n for n in BUILTIN_THEMES if n not in {"hell", "dunkel", "ruhig", "hochkontrast"} and not n.startswith("pride-")]),
        )
        for label, names in groups:
            if not names:
                continue
            submenu = self.theme_menu.addMenu(label)
            for name in names:
                self._add_theme_action(submenu, name)
        self.theme_menu.addSeparator()
        self.theme_menu.addAction("Themes kombinieren …", self.edit_theme_mix)
        self.theme_menu.addAction("Drei Pride-Favoriten auswählen …", self.edit_pride_favorites)

    def _add_theme_action(self, menu: QMenu, name: str) -> None:
        theme = BUILTIN_THEMES[name]
        # The same theme can appear in both favourites and the full collection.
        action = QAction(theme.label, self, checkable=True)
        action.setChecked(name == self.settings.theme)
        action.triggered.connect(lambda _checked=False, n=name: self.set_theme(n))
        menu.addAction(action)
        self.theme_action_group.addAction(action)
        self._theme_action_copies.setdefault(name, []).append(action)
        self.theme_actions.setdefault(name, action)

    def edit_theme_mix(self) -> None:
        """Let the user combine the base theme with up to three additional palettes."""
        dialog = QDialog(self)
        dialog.setWindowTitle('Themes kombinieren')
        dialog.resize(500, 600)
        layout = QVBoxLayout(dialog)
        note = QLabel(
            'Das aktive Theme bleibt die Basis für Hintergrund und Text. '
            'Wähle bis zu drei weitere Themes dazu. Alle gewählten Themes erscheinen '
            'gemeinsam im Farbstreifen; das Basis-Theme sorgt weiter für gut lesbaren Text.',
            dialog,
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        list_layout = QVBoxLayout(content)
        checks: dict[str, QCheckBox] = {}
        base_name = self.settings.theme
        selected_names = {base_name, *self.settings.theme_mix}
        count = QLabel('', dialog)

        def update_count() -> None:
            selected_count = sum(1 for checkbox in checks.values() if checkbox.isChecked())
            count.setText(f"{selected_count}/4 Themes ausgewählt")

        def changed(checked: bool, own_name: str) -> None:
            if checked and sum(1 for checkbox in checks.values() if checkbox.isChecked()) > 4:
                checks[own_name].blockSignals(True)
                checks[own_name].setChecked(False)
                checks[own_name].blockSignals(False)
                QMessageBox.information(
                    dialog, 'Maximal vier Themes',
                    'Du kannst die Basis mit höchstens drei weiteren Themes kombinieren.',
                )
            update_count()

        for name, theme in BUILTIN_THEMES.items():
            checkbox = QCheckBox(theme.label, content)
            checkbox.setChecked(name in selected_names)
            if name == base_name:
                checkbox.setEnabled(False)
                checkbox.setToolTip('Das aktive Theme bleibt die Basis für gut lesbaren Text.')
            checkbox.toggled.connect(lambda checked, n=name: changed(checked, n))
            checks[name] = checkbox
            list_layout.addWidget(checkbox)

        list_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        layout.addWidget(count)
        update_count()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.settings.theme_mix = [
            name for name, checkbox in checks.items()
            if name != self.settings.theme and checkbox.isChecked()
        ]
        self.theme = combine_themes([self.settings.theme, *self.settings.theme_mix])
        self._refresh_page_theme_script()
        self._apply_browser_theme()
        for action_name, actions in self._theme_action_copies.items():
            for action in actions:
                action.setChecked(action_name == self.settings.theme)
        self._save_settings()
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if isinstance(view, QWebEngineView):
                view.page().setBackgroundColor(self._qt_color(self.theme.bg))
                self.apply_page_theme(view)
                if getattr(view, '_nexlori_start', False):
                    view.setHtml(_start_page(self.theme, self.settings.search_url), QUrl('about:blank'))
        self.statusBar().showMessage(f"Themes kombiniert: {self.theme.label}", 3500)

    def edit_pride_favorites(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Deine drei Pride-Favoriten")
        dialog.resize(440, 520)
        layout = QVBoxLayout(dialog)
        note = QLabel("Wähle bis zu drei Pride-Flaggen für den Schnellzugriff im Theme-Menü.", dialog)
        note.setWordWrap(True)
        layout.addWidget(note)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        list_layout = QVBoxLayout(content)
        pride_names = [name for name in BUILTIN_THEMES if name.startswith("pride-")]
        checks: dict[str, QCheckBox] = {}
        initial = set(self.settings.pride_favorites)
        count = QLabel("", dialog)

        def update_count() -> None:
            selected_count = sum(1 for checkbox in checks.values() if checkbox.isChecked())
            count.setText(f"{selected_count}/3 ausgewählt")

        def changed(checked: bool, own_name: str) -> None:
            if checked and sum(1 for checkbox in checks.values() if checkbox.isChecked()) > 3:
                checks[own_name].blockSignals(True)
                checks[own_name].setChecked(False)
                checks[own_name].blockSignals(False)
                QMessageBox.information(dialog, "Maximal drei", "Du kannst genau bis zu drei Pride-Favoriten speichern.")
            update_count()

        for name in pride_names:
            checkbox = QCheckBox(BUILTIN_THEMES[name].label, content)
            checkbox.setChecked(name in initial)
            checkbox.toggled.connect(lambda checked, n=name: changed(checked, n))
            checks[name] = checkbox
            list_layout.addWidget(checkbox)
        list_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        layout.addWidget(count)
        update_count()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.pride_favorites = [name for name in pride_names if checks[name].isChecked()]
            self._save_settings()
            self._build_theme_menu()
            self.statusBar().showMessage("Pride-Favoriten gespeichert.", 2500)

    def _apply_toolbar_preferences(self) -> None:
        for name, button in self.toolbar_icons.items():
            button.setVisible(name in self.settings.toolbar_visible_icons)
        self.address.setMaximumWidth(self.settings.toolbar_search_width)
        self.address.setMinimumWidth(min(220, self.settings.toolbar_search_width))
        self._apply_browser_theme()

    def customize_toolbar(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Nexlori oben anpassen")
        dialog.setMinimumWidth(470)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Passe die zentrierte Suchleiste, die Icon-Größe und die sichtbaren Schnellzugriffe an. "
            "Das Seiten-Theme-CSS bleibt davon unberührt.",
            dialog,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        search_width = QSpinBox(dialog)
        search_width.setRange(360, 1000)
        search_width.setSingleStep(40)
        search_width.setSuffix(" px")
        search_width.setValue(self.settings.toolbar_search_width)
        form.addRow("Breite der Suchleiste", search_width)

        icon_size = QSpinBox(dialog)
        icon_size.setRange(14, 30)
        icon_size.setSuffix(" px")
        icon_size.setValue(self.settings.toolbar_icon_size)
        form.addRow("Icon-Größe", icon_size)

        search_engine = QComboBox(dialog)
        providers = {
            "DuckDuckGo": "https://duckduckgo.com/?q={}",
            "Google": "https://www.google.com/search?q={}",
            "Bing": "https://www.bing.com/search?q={}",
            "Ecosia": "https://www.ecosia.org/search?q={}",
        }
        for label, url in providers.items():
            search_engine.addItem(label, url)
        selected = search_engine.findData(self.settings.search_url)
        if selected < 0 and "duckduckgo" in self.settings.search_url.lower():
            selected = 0
        if selected >= 0:
            search_engine.setCurrentIndex(selected)
        form.addRow("Suchmaschine", search_engine)
        layout.addLayout(form)

        icon_group = QWidget(dialog)
        icon_layout = QVBoxLayout(icon_group)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.addWidget(QLabel("Schnellzugriffe anzeigen", icon_group))
        labels = {
            "home": "Startseite",
            "bookmark": "Lesezeichen",
            "spotify": "Spotify Mini-Player",
            "page_theme": "Website-Farben (Aa)",
            "theme": "Theme-Auswahl",
        }
        checks: dict[str, QCheckBox] = {}
        for name, label in labels.items():
            check = QCheckBox(label, icon_group)
            check.setChecked(name in self.settings.toolbar_visible_icons)
            checks[name] = check
            icon_layout.addWidget(check)
        layout.addWidget(icon_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.settings.toolbar_search_width = search_width.value()
        self.settings.toolbar_icon_size = icon_size.value()
        if search_engine.currentData():
            self.settings.search_url = str(search_engine.currentData())
        self.settings.toolbar_visible_icons = [
            name for name, check in checks.items() if check.isChecked()
        ]
        self._save_settings()
        self._apply_toolbar_preferences()
        self.statusBar().showMessage("Deine Browserleiste wurde angepasst.", 3000)

    def open_feedback_email(self) -> None:
        QDesktopServices.openUrl(QUrl(f"mailto:{FEEDBACK_EMAIL}?subject=Nexlori%20-%20Anliegen%20oder%20Verbesserung"))

    def open_feedback_github(self) -> None:
        QDesktopServices.openUrl(QUrl(f"{REPOSITORY_URL}/issues/new?title=Nexlori%20Feedback"))

    def _build_more_menu(self) -> None:
        self.more_menu = QMenu(self)
        self.more_menu.addAction("Neuer Tab", self.new_tab, QKeySequence("Ctrl+T"))
        self.more_menu.addAction("Lesezeichen", self.show_bookmarks_menu, QKeySequence("Ctrl+Shift+B"))
        self.more_menu.addAction("Verlauf dieser Sitzung", self.show_history_menu)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Spotify Mini-Player", self.show_spotify_popup, QKeySequence("Ctrl+Shift+M"))
        self.more_menu.addAction("Passwortmanager", self.show_password_manager, QKeySequence("Ctrl+Shift+P"))
        self.more_menu.addAction("Add-ons verwalten", self.show_extensions_manager)
        self.more_menu.addAction("Einstellungen", self.show_settings, QKeySequence("Ctrl+,"))
        self.more_menu.addAction("Browserleiste anpassen …", self.customize_toolbar)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Downloads-Ordner öffnen", self.open_download_folder)
        self.more_menu.addAction("Webseite neu laden", self.reload_current, QKeySequence("F5"))
        self.more_menu.addAction("Theme auswählen", self.show_theme_menu)
        self.more_menu.addAction("Nach Updates suchen", self.check_for_updates)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Feedback per E-Mail …", self.open_feedback_email)
        self.more_menu.addAction("Verbesserung auf GitHub melden …", self.open_feedback_github)
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
            ("Ctrl+Shift+M", self.show_spotify_popup),
            ("Ctrl+Shift+P", self.show_password_manager),
            ("Ctrl+,", self.show_settings),
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
        icon_px = self.settings.toolbar_icon_size
        self.setStyleSheet(f"""
QMainWindow, QWidget {{ background:{theme.bg}; color:{theme.fg}; }}
QWidget#toolbar {{ background:{theme.bg}; }}
QTabWidget::pane {{ border:0; background:{theme.bg}; }}
QTabBar {{ background:{theme.surface}; }}
QTabBar::tab {{ background:{theme.surface}; color:{theme.fg}; border:1px solid transparent;
 border-top-left-radius:10px; border-top-right-radius:10px; padding:10px 13px; margin-right:3px; min-width:90px; }}
QTabBar::tab:selected {{ background:{theme.bg}; border-color:{theme.surface}; border-bottom:2px solid {theme.accent}; }}
QTabBar::tab:hover {{ background:{theme.bg}; }}
QToolButton {{ color:{theme.fg}; background:transparent; border:0; border-radius:12px; min-width:{icon_px + 16}px; min-height:{icon_px + 16}px; padding:3px; font-size:{icon_px}px; }}
QToolButton:hover {{ background:{theme.surface}; }}
QToolButton:pressed, QToolButton:checked {{ background:{theme.surface}; color:{theme.accent}; }}
QToolButton#newTabButton {{ font-size:{icon_px + 3}px; min-width:{icon_px + 18}px; min-height:{icon_px + 18}px; }}
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
        self.settings.theme = name
        self.settings.theme_mix = []
        self.theme = combine_themes([self.settings.theme])
        # Update the profile-level stylesheet too, so pages opened later receive the new theme.
        self._refresh_page_theme_script()
        self._apply_browser_theme()
        for action_name, actions in self._theme_action_copies.items():
            for action in actions:
                action.setChecked(action_name == name)
        self._save_settings()
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if isinstance(view, QWebEngineView):
                view.page().setBackgroundColor(self._qt_color(self.theme.bg))
                self.apply_page_theme(view)
                if getattr(view, "_nexlori_start", False):
                    view.setHtml(_start_page(self.theme, self.settings.search_url), QUrl("about:blank"))
        self.statusBar().showMessage(f"Theme: {self.theme.label}", 2500)

    @staticmethod
    def _qt_color(value: str):
        from PySide6.QtGui import QColor
        return QColor(value)

    def _build_page_theme_script(self, enabled: bool) -> str:
        return build_page_theme_script(self.theme, enabled)

    def _refresh_page_theme_script(self) -> None:
        """Apply the selected stylesheet automatically to each newly created page document."""
        scripts = self.profile.scripts()
        if self._page_theme_script is not None:
            try:
                scripts.remove(self._page_theme_script)
            except (RuntimeError, TypeError):
                pass
        script = QWebEngineScript()
        script.setName("NexloriWebsiteTheme")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        # Pages often render their actual content in an iframe; theme those documents too.
        script.setRunsOnSubFrames(True)
        script.setSourceCode(self._build_page_theme_script(self.settings.adapt_page_theme))
        scripts.insert(script)
        self._page_theme_script = script

    def apply_page_theme(self, view: QWebEngineView) -> None:
        # The current page gets updated immediately; profile-level DocumentReady injection
        # applies the same stylesheet on future navigations as well.
        view.page().runJavaScript(self._build_page_theme_script(self.settings.adapt_page_theme))

    def toggle_page_theme(self, enabled: bool) -> None:
        self.settings.adapt_page_theme = bool(enabled)
        self._refresh_page_theme_script()
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
        view.page().renderProcessTerminated.connect(
            lambda status, exit_code, w=view: self._on_render_process_terminated(w, status, exit_code)
        )
        view.page().linkHovered.connect(self._on_link_hovered)
        index = self.tabs.addTab(view, "Neuer Tab")
        if activate:
            self.tabs.setCurrentIndex(index)
        if start_page:
            view._nexlori_start = True
            view.setHtml(_start_page(self.theme, self.settings.search_url), QUrl("about:blank"))
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

    def _on_render_process_terminated(self, view: QWebEngineView, status, exit_code: int) -> None:
        """Keep Nexlori open when a Chromium renderer process crashes or is killed."""
        if self.tabs.indexOf(view) < 0 or self._closing:
            return
        self.progress.hide()
        status_name = getattr(status, "name", str(status))
        self.statusBar().showMessage(
            f"Ein Tab wurde von Chromium beendet ({status_name}, Code {exit_code}). "
            "Nexlori bleibt geöffnet. Klicke auf „Neu laden“, um es erneut zu versuchen.",
            10000,
        )
        self.reload_button.setEnabled(True)

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
            view.setHtml(_start_page(self.theme, self.settings.search_url), QUrl("about:blank"))
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
            view.setHtml(_start_page(self.theme, self.settings.search_url), QUrl("about:blank"))
        else:
            view.reload()

    def go_home(self) -> None:
        view = self.current_view()
        if view:
            view._nexlori_start = True
            view.setHtml(_start_page(self.theme, self.settings.search_url), QUrl("about:blank"))
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

    def _ensure_default_extension(self) -> None:
        """Install the bundled official uBlock Origin Lite package for a fresh profile."""
        if self.extension_manager is None:
            self.statusBar().showMessage(
                "Add-ons benötigen Qt WebEngine 6.10 oder neuer.", 6000
            )
            return
        try:
            extensions = list(self.extension_manager.extensions())
        except (AttributeError, RuntimeError):
            extensions = []
        installed = any(
            extension_key_from_info(ext) == "ublock-origin-lite"
            and bool(ext.isInstalled())
            for ext in extensions
        )
        if installed:
            self._sync_extension_states()
            return
        package = bundled_ubolite_path()
        if package is None:
            self.statusBar().showMessage(
                "uBlock Origin Lite fehlt in diesem Build. Du kannst ein MV3-Add-on manuell installieren.",
                7000,
            )
            return
        try:
            # Qt WebEngine's extension API accepts an unpacked extension directory,
            # not the ZIP archive bundled with Nexlori. Unpack the already verified
            # archive into the persistent profile before calling the native API.
            extension_dir = self.storage_dir / "extensions" / "ublock-origin-lite"
            unpacked = unpack_extension_package(package, extension_dir)
            self.statusBar().showMessage("uBlock Origin Lite wird zum ersten Mal eingerichtet …", 6000)
            self.extension_manager.installExtension(str(unpacked))
        except Exception as exc:  # noqa: BLE001
            self.statusBar().showMessage(f"uBlock Origin Lite konnte nicht installiert werden: {exc}", 8000)

    def _on_extension_installed(self, extension) -> None:
        """Persist the requested state, then enable it after Qt leaves its install callback."""
        try:
            if not extension.isInstalled() or not extension.isLoaded():
                reason = str(extension.error() or "Erweiterung wurde nicht korrekt geladen.")
                self.statusBar().showMessage(f"Add-on-Installation fehlgeschlagen: {reason}", 8000)
                return
            name = extension_name_from_info(extension)
            key = extension_key_from_name(name)
            enabled = bool(self.settings.ubol_enabled) if key == "ublock-origin-lite" else True
            self.settings.extensions_enabled[key] = enabled
            if key == "ublock-origin-lite":
                self.settings.ubol_enabled = enabled
            self._save_settings()
            QTimer.singleShot(
                0,
                lambda ext=extension, state=enabled, label=name: self._activate_installed_extension(
                    ext, state, label
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self.statusBar().showMessage(f"Add-on konnte nicht vorbereitet werden: {exc}", 8000)

    def _activate_installed_extension(self, extension, enabled: bool, name: str) -> None:
        """Activate outside installFinished to avoid mutating Qt's manager during its callback."""
        try:
            if self.extension_manager is None or not extension.isLoaded():
                self.statusBar().showMessage(f"{name} ist geladen, aber noch nicht bereit.", 6000)
                return
            self.extension_manager.setExtensionEnabled(extension, bool(enabled))
            self.statusBar().showMessage(
                f"{name} wurde installiert und {'aktiviert' if enabled else 'deaktiviert'}.", 5000
            )
            QTimer.singleShot(200, self._sync_extension_states)
        except Exception as exc:  # noqa: BLE001
            self.statusBar().showMessage(f"{name} konnte nicht aktiviert werden: {exc}", 8000)

    def _sync_extension_states(self) -> None:
        """Restore each add-on's persisted enabled state; Qt loads installed extensions disabled."""
        if self.extension_manager is None:
            return
        try:
            for extension in self.extension_manager.extensions():
                if not extension.isLoaded():
                    continue
                extension_name = extension_name_from_info(extension)
                key = extension_key_from_name(extension_name)
                if not key or is_builtin_extension(extension_name):
                    continue
                if key == "ublock-origin-lite":
                    enabled = bool(self.settings.ubol_enabled)
                else:
                    enabled = bool(self.settings.extensions_enabled.get(key, False))
                if bool(extension.isEnabled()) != enabled:
                    self.extension_manager.setExtensionEnabled(extension, enabled)
        except (AttributeError, RuntimeError):
            return

    def set_extension_enabled(self, extension, enabled: bool) -> None:
        if self.extension_manager is None:
            raise RuntimeError("Qt WebEngine unterstützt in diesem Build keine Erweiterungen.")
        name = extension_name_from_info(extension)
        key = extension_key_from_name(name)
        self.extension_manager.setExtensionEnabled(extension, bool(enabled))
        self.settings.extensions_enabled[key] = bool(enabled)
        if key == "ublock-origin-lite":
            self.settings.ubol_enabled = bool(enabled)
        self._save_settings()
        self.statusBar().showMessage(f"{name}: {'aktiviert' if enabled else 'deaktiviert'}", 3000)

    def show_extensions_manager(self) -> None:
        if self.extension_manager is None:
            QMessageBox.warning(
                self, "Add-ons nicht verfügbar",
                "Browser-Erweiterungen erfordern Qt WebEngine 6.10 oder neuer.",
            )
            return
        try:
            from .extensions_ui import ExtensionsDialog
            ExtensionsDialog(self, self).exec()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Add-ons", f"Der Add-on-Manager konnte nicht geöffnet werden: {exc}")

    def show_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Nexlori · Einstellungen")
        dialog.setMinimumWidth(560)
        root = QVBoxLayout(dialog)
        intro = QLabel(
            "Hier verwaltest du Datenschutz, Website-Darstellung, Updates und das Verhalten von Nexlori.",
            dialog,
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        theme_css = QCheckBox("Website-Farbschema unterstützen (Website-CSS bleibt erhalten)", dialog)
        theme_css.setChecked(self.settings.adapt_page_theme)
        ubol = QCheckBox("uBlock Origin Lite aktivieren (Werbung und Tracker blockieren)", dialog)
        ubol.setChecked(self.settings.ubol_enabled)
        updates = QCheckBox("Beim Start automatisch nach Updates suchen", dialog)
        updates.setChecked(self.settings.auto_update_check)
        popups = QCheckBox("Website-Pop-ups und neue Fenster erlauben", dialog)
        popups.setChecked(self.settings.allow_web_popups)

        zoom = QDoubleSpinBox(dialog)
        zoom.setRange(0.5, 3.0)
        zoom.setSingleStep(0.1)
        zoom.setSuffix("×")
        zoom.setValue(float(self.settings.page_zoom))

        search_engine = QComboBox(dialog)
        providers = {
            "DuckDuckGo": "https://html.duckduckgo.com/html/?q={}",
            "Google": "https://www.google.com/search?q={}",
            "Bing": "https://www.bing.com/search?q={}",
            "Ecosia": "https://www.ecosia.org/search?q={}",
        }
        for label, template in providers.items():
            search_engine.addItem(label, template)
        selected = search_engine.findData(self.settings.search_url)
        if selected < 0:
            selected = next(
                (
                    i for i in range(search_engine.count())
                    if self.settings.search_url.startswith(str(search_engine.itemData(i)).split("{")[0])
                ),
                0,
            )
        search_engine.setCurrentIndex(max(0, selected))

        form.addRow("Website-Farben", theme_css)
        form.addRow("Werbe- und Trackerschutz", ubol)
        form.addRow("Updates", updates)
        form.addRow("Pop-ups", popups)
        form.addRow("Standard-Zoom", zoom)
        form.addRow("Suchmaschine", search_engine)
        root.addLayout(form)

        actions = QHBoxLayout()
        addons = QPushButton("Add-ons verwalten …", dialog)
        addons.clicked.connect(lambda: (dialog.accept(), QTimer.singleShot(0, self.show_extensions_manager)))
        toolbar = QPushButton("Browserleiste anpassen …", dialog)
        toolbar.clicked.connect(lambda: (dialog.accept(), QTimer.singleShot(0, self.customize_toolbar)))
        actions.addWidget(addons)
        actions.addWidget(toolbar)
        root.addLayout(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        root.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.settings.adapt_page_theme = theme_css.isChecked()
        self.settings.ubol_enabled = ubol.isChecked()
        self.settings.auto_update_check = updates.isChecked()
        self.settings.allow_web_popups = popups.isChecked()
        self.settings.page_zoom = float(zoom.value())
        self.settings.search_url = str(search_engine.currentData())
        self.settings.extensions_enabled["ublock-origin-lite"] = self.settings.ubol_enabled
        self._refresh_page_theme_script()
        self._sync_extension_states()
        self._save_settings()
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if isinstance(view, QWebEngineView):
                view.setZoomFactor(self.settings.page_zoom)
                self.apply_page_theme(view)
        self.statusBar().showMessage("Einstellungen gespeichert.", 3000)

    def show_spotify_popup(self) -> None:
        try:
            from .spotify_popup import SpotifyPopup
            if self._spotify_popup is None:
                self._spotify_popup = SpotifyPopup(self.profile, self)
                self._spotify_popup.destroyed.connect(lambda: setattr(self, "_spotify_popup", None))
            self._spotify_popup.show()
            self._spotify_popup.raise_()
            self._spotify_popup.activateWindow()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Spotify Mini-Player", f"Der Mini-Player konnte nicht geöffnet werden: {exc}")

    def show_password_manager(self) -> None:
        try:
            from .password_vault_ui import open_password_manager
            view = self.current_view()
            site = ""
            if view:
                current = view.url()
                if current.scheme() in {"http", "https"} and current.host():
                    site = f"{current.scheme()}://{current.host()}"
            open_password_manager(self, self.settings_path.parent / "password-vault.json", default_site=site)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Passwortmanager", f"Der Passwortmanager konnte nicht geöffnet werden: {exc}")

    def _start_silent_update_check(self) -> None:
        self._silent_update_check = True
        self._start_update_worker("check")

    def check_for_updates(self) -> None:
        self._silent_update_check = False
        self._start_update_worker("check")

    def _start_update_worker(self, task: str, release: dict | None = None) -> None:
        if self._update_worker is not None and self._update_worker.isRunning():
            self.statusBar().showMessage("Ein Update-Vorgang läuft bereits.", 3000)
            return
        update_dir = self.settings_path.parent / "updates"
        worker = UpdateWorker(task, release=release, update_dir=update_dir, parent=self)
        worker.finished.connect(self._on_update_worker_finished)
        self._update_worker = worker
        self.statusBar().showMessage("Suche nach Nexlori-Updates …" if task == "check" else "Update wird heruntergeladen und geprüft …")
        worker.start()

    def _on_update_worker_finished(self) -> None:
        worker = self._update_worker
        if worker is None:
            return
        data = dict(worker.result_data)
        self._update_worker = None
        worker.deleteLater()
        if data.get("error"):
            message = str(data["error"])
            self.statusBar().showMessage("Update-Vorgang fehlgeschlagen.", 5000)
            if not self._silent_update_check:
                QMessageBox.warning(self, "Nexlori-Update", message)
            return
        if data.get("task") == "check":
            release = data.get("release")
            if not release:
                self.statusBar().showMessage("Nexlori ist auf dem neuesten veröffentlichten Stand.", 4000)
                if not self._silent_update_check:
                    QMessageBox.information(self, "Nexlori-Update", f"Du verwendest Nexlori {APP_VERSION}. Es wurde kein neueres veröffentlichtes Release gefunden.")
                return
            notes = str(release.get("body") or "Keine Release-Notizen vorhanden.")
            details = (
                f"Version {release['version']} ist verfügbar. Du verwendest Nexlori {APP_VERSION}.\n\n"
                + notes[:1200]
                + "\n\nMöchtest du das Update herunterladen und die EXE aktualisieren?"
            )
            answer = QMessageBox.question(
                self, "Nexlori-Update verfügbar", details,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._start_update_worker("download", release)
            else:
                self.statusBar().showMessage(f"Nexlori {release['version']} ist verfügbar.", 5000)
            return
        if data.get("task") == "download":
            release = data.get("release") or {}
            try:
                from .updater import start_windows_self_update
                started = start_windows_self_update(str(data["path"]), str(release.get("url") or "https://github.com/paulhubacek1-afk/NEXLORI/releases"))
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Nexlori-Update", f"Der Download wurde geprüft, aber der Updater konnte nicht gestartet werden: {exc}")
                return
            if not started:
                QDesktopServices.openUrl(QUrl(str(release.get("url") or "https://github.com/paulhubacek1-afk/NEXLORI/releases")))
                QMessageBox.information(self, "Nexlori-Update", "Das Update wurde heruntergeladen und die Prüfsumme stimmt. Starte die Release-Seite, damit du die Windows-Version manuell installieren kannst.")
                return
            QMessageBox.information(self, "Nexlori-Update", "Update verifiziert. Nexlori wird geschlossen, aktualisiert und anschließend neu gestartet.")
            self.close()
            QApplication.quit()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "Über Nexlori",
            f"<h3>Nexlori {APP_VERSION}</h3><p>Dein Web. Dein Look.</p>"
            "<p>Chromium-WebEngine für moderne Websites, mit lokalen Themes, Spotify Mini-Player und einem verschlüsselten Passwortmanager.</p>"
            "<p>Updates werden von GitHub Releases bezogen und vor dem Ersetzen der EXE per SHA-256 geprüft.</p>",
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


def _selftest_ubol_package() -> tuple[bool, str]:
    """Verify the bundled uBlock Origin Lite archive without starting extension subprocesses.

    Qt WebEngine's extension runtime has native Chromium subprocesses; the EXE packaging
    smoke test must not install/enable extensions and then tear their profile down in the
    same short-lived test process. The package itself is hash-checked at build time and
    its manifest/identity are checked again here.
    """
    import hashlib

    from .extension_utils import UBOLITE_SHA256, bundled_ubolite_path, inspect_extension_package

    package = bundled_ubolite_path()
    if package is None:
        return False, "Das geprüfte uBlock-Origin-Lite-Paket fehlt."
    digest = hashlib.sha256()
    try:
        with package.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual.lower() != UBOLITE_SHA256.lower():
            return False, "SHA-256-Prüfsumme des eingebauten uBlock-Origin-Lite-Pakets stimmt nicht."
        details = inspect_extension_package(package)
        name = str(details.get("name") or "")
        if details.get("manifest_version") != 3 or "ublock" not in name.casefold():
            return False, "Das Paket ist keine gültige Manifest-V3-Version von uBlock Origin Lite."
        return True, f"{name} {details.get('version', '')} · Manifest V3 und SHA-256 geprüft"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"



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
    app.setWindowIcon(_qt_app_icon())
    app.setStyle("Fusion")
    start_url = None
    if argv:
        start_url = normalize_input(" ".join(arg for arg in argv if not arg.startswith("-")), settings.search_url)
    window = NexloriWindow(settings, settings_path, start_url)
    window.show()
    # CI runners may not expose a native interactive desktop/window handle.
    # A marker lets the Windows smoke test verify that construction reached show().
    smoke_marker = os.environ.get("NEXLORI_SMOKE_MARKER")
    if smoke_marker:
        try:
            Path(smoke_marker).write_text(
                f"shown={window.isVisible()}\\ntitle={window.windowTitle()}\\nsize={window.width()}x{window.height()}\\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"Nexlori smoke marker could not be written: {exc}", file=sys.stderr)
    return app.exec()
