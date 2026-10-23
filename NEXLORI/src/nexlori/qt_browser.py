"""Nexlori's Chromium-based browser UI.

The legacy renderer is kept for educational rendering tests; real pages are rendered by Qt WebEngine.
"""
from __future__ import annotations

import io
import json
import os
import platform
import re
import sys
import time
from html import escape as html_escape
from pathlib import Path
from urllib.parse import urlsplit

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import (
    QFile, QIODevice, QObject, QEventLoop, QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRect,
    QStringListModel, QThread, QTimer, QUrl, QUrlQuery, Qt, Signal, Slot, qVersion,
)
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPalette, QPen, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QCompleter,
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
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QSystemTrayIcon,
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
from PySide6.QtWebChannel import QWebChannel

from . import __version__
from .browser import normalize_input
from .core.settings import Settings, canonical_search_url, default_settings_path
from .animations import AccentLine, Motion, animate_progress, cascade_in, crossfade
from .core.builtin_addons import ADDONS, build_addons_script, is_enabled, reader_script
from .core.privacy import strip_tracking_params, tabs_to_sleep, upgrade_to_https
from .core.theme_shop import ShopError, ThemeStore, default_theme_dir
from .core.themes import (
    BUILTIN_THEMES, Theme, all_themes, combine_themes, get_theme, installed_theme_names, is_known_theme,
    relative_luminance,
)
from .links import DISCORD_URL, FEEDBACK_EMAIL, PROJECT_LINKS, REPOSITORY_URL
from .tabstrip import TabStrip
from .titlebar import DialogThemer, ResizeFrame, TitleBar, apply_native_titlebar_colors
from .web_safety import addons_page_html, home_network_page_html, normalize_home_target
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
SEARCH_PROVIDERS = {
    "DuckDuckGo": "https://duckduckgo.com/?q={}",
    "Google": "https://www.google.com/search?q={}",
    "Bing": "https://www.bing.com/search?q={}",
    "Ecosia": "https://www.ecosia.org/search?q={}",
}


def _qt_app_icon(theme: Theme | None = None) -> QIcon:
    """Create the application icon from the active theme palette."""
    from .icon import make_icon

    image = make_icon(256, theme=theme)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return QIcon(pixmap)


def _mix_hex(first: str, second: str, ratio: float) -> str:
    """Mischt zwei #RRGGBB-Farben (ratio=0 -> first, ratio=1 -> second)."""
    a, b = QColor(first), QColor(second)
    return "#{:02X}{:02X}{:02X}".format(
        round(a.red() + (b.red() - a.red()) * ratio),
        round(a.green() + (b.green() - a.green()) * ratio),
        round(a.blue() + (b.blue() - a.blue()) * ratio),
    )


def _theme_gradient(theme: Theme) -> str:
    colors = theme.stripes or (theme.accent,)
    if len(colors) < 2:
        colors = (colors[0], colors[0])  # Qt braucht mindestens zwei Stopps für einen Verlauf
    stops = []
    for index, color in enumerate(colors):
        position = index / max(1, len(colors) - 1)
        stops.append(f"stop:{position:.3f} {color}")
    return "qlineargradient(x1:0, y1:0, x2:1, y2:0, " + ", ".join(stops) + ")"


def _start_page(
    theme: Theme,
    search_url: str,
    pride_mode: bool = False,
    bookmarks: list[dict[str, str]] | None = None,
) -> str:
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
    bookmark_items = []
    for item in bookmarks or []:
        url = str(item.get("url", "")).strip()
        if not url.lower().startswith(("https://", "http://")):
            continue
        title = html_escape(str(item.get("title") or url)[:80])
        safe_url = html_escape(url, quote=True)
        bookmark_items.append(
            f'<a class="bookmark-chip" href="{safe_url}" title="{safe_url}"><span class="bookmark-star">☆</span><span>{title}</span></a>'
        )
    bookmark_markup = "".join(bookmark_items) or '<div class="empty-bookmarks">Noch keine Lesezeichen. Speichere eine Seite mit ☆ in der Browserleiste.</div>'
    project_markup = "".join(
        f'<a class="project-card" href="{html_escape(str(project["url"]), quote=True)}" target="_self">'
        f'<span class="project-icon">{html_escape(str(project.get("icon", "↗")))}</span>'
        f'<strong>{html_escape(str(project["title"]))}</strong>'
        f'<small>{html_escape(str(project.get("description", "")))}</small></a>'
        for project in PROJECT_LINKS
    )
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
a.tile:focus-visible, a.cta:focus-visible, button:focus-visible {{ outline:2px solid {theme.accent}; outline-offset:3px; }}
.tile-icon {{ transition:transform .24s ease,color .24s ease; }}
a.tile:hover .tile-icon {{ transform:translateY(-2px) rotate(-5deg) scale(1.1); }}
.community {{ margin:20px 0 22px; display:flex; justify-content:center; }}
a.cta {{ display:inline-flex; align-items:center; gap:10px; text-decoration:none; font-weight:600; color:{theme.bg}; background:{theme.accent}; padding:12px 24px; border-radius:999px; transition:transform .2s ease,box-shadow .2s ease; }}
a.cta:hover {{ transform:translateY(-2px); box-shadow:0 10px 26px {theme.accent}55; }}
.tile-icon {{ display:block; color:{theme.accent}; font-size:22px; margin-bottom:9px; }}
small {{ display:block; opacity:.68; margin-top:7px; line-height:1.45; }}
.foot {{ font-size:12px; margin-top:28px; opacity:.56; }}
.section-title {{ display:flex; align-items:center; justify-content:space-between; gap:12px; font-size:17px; letter-spacing:-.02em; margin:0 0 12px; }}
.bookmarks-section {{ margin:25px 0 28px; }}
.bookmark-list {{ display:flex; flex-wrap:wrap; gap:9px; }}
.bookmark-chip {{ display:inline-flex; align-items:center; gap:8px; max-width:100%; padding:9px 13px; background:{theme.surface}; color:{theme.fg}; border:1px solid {theme.surface}; border-radius:13px; text-decoration:none; font-size:13px; transition:transform .18s ease,border-color .18s ease; }}
.bookmark-chip:hover {{ border-color:{theme.accent}; transform:translateY(-2px); }}
.bookmark-star {{ color:{theme.accent}; font-size:16px; }}
.empty-bookmarks {{ opacity:.65; font-size:13px; padding:8px 0; }}
.projects-section {{ margin-top:29px; }}
.project-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; }}
.project-card {{ display:block; color:{theme.fg}; background:{theme.surface}; border:1px solid {theme.surface}; border-radius:16px; padding:16px; text-decoration:none; transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease; }}
.project-card:hover {{ border-color:{theme.accent}; transform:translateY(-3px); box-shadow:0 10px 26px {theme.accent}18; }}
.project-icon {{ display:block; color:{theme.accent}; font-size:22px; margin-bottom:9px; }}
@keyframes page-enter {{ from {{ opacity:0; transform:translateY(9px); }} to {{ opacity:1; transform:translateY(0); }} }}
@keyframes tile-enter {{ from {{ opacity:0; transform:translateY(10px); }} to {{ opacity:1; transform:translateY(0); }} }}
@keyframes stripe-flow {{ from {{ background-position:0 0; }} to {{ background-position:100% 0; }} }}
{pride_css}
@media (prefers-reduced-motion:reduce) {{ *,*::before,*::after {{ animation:none !important; transition:none !important; }} }}
</style></head><body>{pride_visuals}<main><div class="stripe"></div><span class="mark">NEXLORI / BROWSER</span>
<h1>Das Web. Auf deine Art.</h1><p class="intro">Ein Browser, der sich deinem Stil anpasst – mit persönlicher Farbwelt, ruhiger Oberfläche und lokalem Schutz.</p>{pride_pill}
<form class="bar" id="search"><input id="query" autocomplete="off" autofocus placeholder="Suchen oder Webadresse eingeben" aria-label="Suchen oder Webadresse eingeben"><button type="submit">Los ↗</button></form>
<section class="bookmarks-section"><h2 class="section-title">Deine Lesezeichen</h2><div class="bookmark-list">{bookmark_markup}</div></section>
<div class="community"><a class="cta" href="nexlori://community/discord" title="Nexlori-Community auf Discord">💬 Discord-Community beitreten</a></div>
<div class="tiles">
<a class="tile" href="https://www.wikipedia.org/"><span class="tile-icon">⌕</span><strong>Wissen</strong><small>Wikipedia</small></a>
<a class="tile" href="https://www.youtube.com/"><span class="tile-icon">▶</span><strong>Video</strong><small>YouTube</small></a>
<a class="tile" href="https://github.com/"><span class="tile-icon">⌘</span><strong>Entwickeln</strong><small>GitHub</small></a>
<a class="tile" href="nexlori://addons"><span class="tile-icon">＋</span><strong>Add-ons</strong><small>Erweiterungen entdecken und verwalten</small></a>
<a class="tile" href="nexlori://home-network"><span class="tile-icon">⌂</span><strong>Heimnetz</strong><small>Router, NAS, Drucker und Smart Home</small></a>
<a class="tile" href="nexlori://settings"><span class="tile-icon">✦</span><strong>Dein Nexlori</strong><small>Themes, Suchmaschine und Einstellungen</small></a>
</div><section class="projects-section"><h2 class="section-title">Meine Online-Projekte</h2><div class="project-grid">{project_markup}</div></section><div class="foot">Nexlori · Chromium-WebEngine · Schutz und Einstellungen bleiben lokal.</div>
<script>
const template = {search_template};
document.getElementById('search').addEventListener('submit', function(e) {{
 e.preventDefault(); const q=document.getElementById('query').value.trim(); if(!q) return;
 const looksLikeUrl=/^(https?:\\/\\/|file:\\/\\/)/i.test(q) || (/^[^\\s]+\\.[^\\s]+$/.test(q) && !q.includes(' '));
 location.href=looksLikeUrl?(q.match(/^[a-z]+:\\/\\//i)?q:'https://'+q):template.replace("{{}}",encodeURIComponent(q));
}});
</script></main></body></html>"""

def _line_icon(kind: str, color: str) -> QIcon:
    """Kleine, selbst gezeichnete Symbole in Theme-Farbe (Schloss, Warnung, Nexlori-Punkt, Löschen)."""
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint = QColor(color)
    if kind in ("secure", "insecure"):
        painter.setPen(QPen(paint, 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRect(9 if kind == "secure" else 14, 3, 14, 18), 0, 180 * 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(paint)
        painter.drawRoundedRect(QRect(6, 13, 20, 15), 3, 3)
    elif kind == "internal":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(paint)
        painter.drawEllipse(QRect(9, 9, 14, 14))
    elif kind == "clear":
        painter.setPen(QPen(paint, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(10, 10, 22, 22)
        painter.drawLine(22, 10, 10, 22)
    painter.end()
    return QIcon(pixmap)


def _security_kind(url_text: str) -> str | None:
    lowered = url_text.lower()
    if lowered.startswith("https://"):
        return "secure"
    if lowered.startswith("http://"):
        return "insecure"
    if lowered.startswith(("about:", "file:", "nexlori:")):
        return "internal"
    return None


class AddressBar(QLineEdit):
    """Such-/Adressleiste mit Sicherheitssymbol, Löschknopf in Theme-Farbe und Chrome-ähnlichem Markieren."""

    escapePressed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._icon_color = "#888888"
        self._security_kind: str | None = None
        self._security_action = self.addAction(QIcon(), QLineEdit.ActionPosition.LeadingPosition)
        self._security_action.setVisible(False)
        self._clear_action = self.addAction(QIcon(), QLineEdit.ActionPosition.TrailingPosition)
        self._clear_action.setToolTip("Eingabe löschen")
        self._clear_action.setVisible(False)
        self._clear_action.triggered.connect(lambda _checked=False: (self.clear(), self.setFocus()))
        self.textChanged.connect(lambda text: self._clear_action.setVisible(bool(text)))

    def set_icon_color(self, color: str) -> None:
        self._icon_color = color
        self._clear_action.setIcon(_line_icon("clear", color))
        self.set_security(self._security_kind)

    def set_security(self, kind: str | None) -> None:
        self._security_kind = kind
        if kind is None:
            self._security_action.setVisible(False)
            return
        color = "#E8A33D" if kind == "insecure" else self._icon_color
        self._security_action.setIcon(_line_icon(kind, color))
        self._security_action.setToolTip({
            "secure": "Verbindung ist verschlüsselt (HTTPS)",
            "insecure": "Nicht verschlüsselt (HTTP) – gib hier keine Passwörter ein",
            "internal": "Interne Seite oder lokale Datei",
        }[kind])
        self._security_action.setVisible(True)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        was_focused = self.hasFocus()
        super().mousePressEvent(event)
        if not was_focused and event.button() == Qt.MouseButton.LeftButton:
            self.selectAll()  # erster Klick markiert alles, danach wird normal der Cursor gesetzt

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        if event.reason() != Qt.FocusReason.MouseFocusReason:
            QTimer.singleShot(0, self.selectAll)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.escapePressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


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


class CredentialCaptureBridge(QObject):
    """Small page-scoped bridge used only after a secure login form is submitted."""

    def __init__(self, owner: "NexloriWindow", view: QWebEngineView):
        super().__init__(view)
        self.owner = owner
        self.view = view

    @Slot(str, str)
    def offerCredentials(self, username: str, password: str) -> None:  # noqa: N802
        self.owner._offer_save_credentials(self.view, str(username), str(password))


class BrowserPage(QWebEnginePage):
    def __init__(self, profile: QWebEngineProfile, owner: "NexloriWindow", parent: QWidget):
        super().__init__(profile, parent)
        self.owner = owner
        self._https_origin: str | None = None  # ursprüngliche http-Adresse, solange der https-Versuch läuft

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
        if url.scheme().lower() == "nexlori":
            # Interne Links der Startseite und der Nexlori-Seiten (Einstellungen, Add-ons, Heimnetz, Discord …)
            if is_main_frame:
                internal = QUrl(url)
                QTimer.singleShot(0, lambda: self.owner.handle_internal_url(self, internal))
            return False
        if is_main_frame and url.scheme().lower() in {"http", "https"}:
            target = self.owner.rewrite_navigation(self, url, navigation_type)
            if target is not None:
                QTimer.singleShot(0, lambda: self.setUrl(QUrl(target)))
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
        self.settings.search_url = canonical_search_url(settings.search_url)
        self.settings_path = settings_path
        self.custom_titlebar = bool(settings.custom_titlebar)
        if self.custom_titlebar:
            # Rahmenloses Fenster: Titelleiste, Größenänderung und Verschieben übernimmt Nexlori (siehe titlebar.py).
            self.setWindowFlags(
                Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowMinMaxButtonsHint | Qt.WindowType.WindowSystemMenuHint
            )
        self.motion = Motion(settings.animations)
        self.theme_store = ThemeStore(default_theme_dir(settings_path))
        self.theme_store.load_into_registry()
        self._html_fullscreen = False
        self._http_allowed_hosts: set[str] = set()
        self._fullscreen_restore = "normal"
        self._first_show = True
        self._tab_activity: dict[QWebEngineView, float] = {}
        self._addons_script: QWebEngineScript | None = None
        self.storage_dir = settings_path.parent / "web-profile"
        self.cache_dir = self.storage_dir / "cache"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.bookmarks_path = settings_path.parent / "bookmarks.json"
        self.bookmarks = self._load_bookmarks()
        self._closing = False
        self._force_exit = False
        self._credential_prompt_open = False
        self._devtools_window = None
        self._devtools_view = None
        self.tray_icon: QSystemTrayIcon | None = None
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
        self.profile.setHttpCacheMaximumSize(96 * 1024 * 1024)
        self.profile.downloadRequested.connect(self._download_requested)
        self._page_theme_script = None
        self._refresh_page_theme_script()
        self._refresh_addons_script()
        self._refresh_password_capture_script()
        try:
            self.extension_manager = self.profile.extensionManager()
            self.extension_manager.installFinished.connect(self._on_extension_installed)
            self.extension_manager.loadFinished.connect(lambda *_: self._sync_extension_states())
        except AttributeError:
            self.extension_manager = None

        self.setWindowTitle("Nexlori")
        self.setWindowIcon(_qt_app_icon(self.theme))
        self.resize(1240, 820)
        self.setMinimumSize(760, 480)
        self._build_ui()
        self._setup_tray()
        self._apply_browser_theme()
        self._bind_shortcuts()
        self._start_tab_sleep_timer()
        view = self.new_tab(start_page=start_url is None, activate=True)
        if start_url:
            self.navigate_view(view, start_url)
        # Netzwerk-/Erweiterungsarbeit verzögert starten, damit das Browserfenster zuerst bedienbar ist.
        QTimer.singleShot(3200, self._ensure_default_extension)
        if self.settings.auto_update_check:
            QTimer.singleShot(10000, self._start_silent_update_check)

    def _render_start_page(self) -> str:
        """Build the start page with the latest saved bookmarks."""
        return _start_page(self.theme, self.settings.search_url, bookmarks=self.bookmarks)

    def _setup_tray(self) -> None:
        """Keep Nexlori available from the Windows notification area while its window is hidden."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return
        tray = QSystemTrayIcon(self.windowIcon(), self)
        tray.setToolTip(f"Nexlori {APP_VERSION}")
        menu = QMenu(self)
        menu.addAction("Nexlori öffnen", self._show_from_tray)
        menu.addAction("Neuer Tab", lambda: (self._show_from_tray(), self.new_tab()))
        menu.addSeparator()
        menu.addAction("Entwicklerwerkzeuge", self.show_developer_tools)
        menu.addAction("Browser-Informationen", self.show_browser_information)
        menu.addSeparator()
        menu.addAction("Beenden", self.quit_application)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        self.tray_icon = tray
        tray.show()

    def _tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal() if self.isMinimized() else self.show()
        self.raise_()
        self.activateWindow()
        view = self.current_view()
        if view is not None:
            view.setFocus()

    def quit_application(self) -> None:
        """Explicit tray-menu exit bypasses close-to-tray and stops the application."""
        self._force_exit = True
        if self.tray_icon is not None:
            self.tray_icon.hide()
        self.close()
        QApplication.quit()

    def _build_ui(self) -> None:
        root = QWidget(self)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar: TitleBar | None = None
        if self.custom_titlebar:
            self.title_bar = TitleBar(self)
            self.title_bar.set_icon(self.windowIcon())
            outer.addWidget(self.title_bar)

        self.accent_line = AccentLine(root, 4)
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

        # Tab-Leiste und Seitenstapel sind getrennt: Die Leiste sitzt hier oben, die Webseiten ganz unten
        # unter der Suchleiste (früher lag die Suchleiste dadurch unter der Webseite).
        self.tabs = TabStrip(self)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_current_changed)
        tab_row.addWidget(self.tabs.bar, 1)
        self.tab_row_widget = QWidget(root)
        self.tab_row_widget.setLayout(tab_row)
        if self.title_bar is not None:
            tab_row.removeWidget(self.new_tab_button)
            tab_row.removeWidget(self.tabs.bar)
            self.title_bar.set_tab_widgets(self.new_tab_button, self.tabs.bar)
            # The old container is kept for fullscreen bookkeeping, but must never paint over the page.
            self.tab_row_widget.hide()
        else:
            outer.addWidget(self.tab_row_widget)

        self.tab_row_widget.setObjectName("tabRow")
        toolbar = QWidget(root)
        toolbar.setObjectName("toolbar")
        self.toolbar_widget = toolbar
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
        self.address.setMinimumHeight(42)
        self.address.setMinimumWidth(260)
        self.address.setMaximumWidth(self.settings.toolbar_search_width)
        self.address.returnPressed.connect(self.navigate_address)
        self.address.escapePressed.connect(self._restore_address)
        # Hoher Streckfaktor: Die Leiste füllt den freien Platz bis zur gewählten Maximalbreite
        # (vorher blieb sie bei ca. 220 px stehen, egal wie breit das Fenster oder die Einstellung war).
        nav.addWidget(self.address, 100)
        nav.addStretch(1)
        self._build_address_completer()

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
        outer.addWidget(self.tabs.stack, 1)

        # Eigene Statusleiste innerhalb des Rahmens, damit der Größenänderungs-Rand rundum gleich bleibt.
        self._status_bar = QStatusBar(root)
        self._status_bar.setSizeGripEnabled(False)
        outer.addWidget(self._status_bar)

        self.resize_frame: ResizeFrame | None = None
        if self.custom_titlebar:
            self.resize_frame = ResizeFrame(self, root)
            self.setCentralWidget(self.resize_frame)
        else:
            self.setCentralWidget(root)
        self.statusBar().showMessage("Nexlori · Chromium-WebEngine")
        self._apply_toolbar_preferences()
        self._build_theme_menu()
        self._build_more_menu()

    def statusBar(self) -> QStatusBar:  # noqa: N802
        """Die Statusleiste liegt im eigenen Layout (siehe _build_ui) statt am Fensterrand."""
        bar = getattr(self, "_status_bar", None)
        return bar if bar is not None else super().statusBar()

    def _tool(self, label: str, tip: str, callback) -> QToolButton:
        button = QToolButton(self)
        button.setText(label)
        button.setToolTip(tip)
        button.setAutoRaise(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def rebuild_theme_menu(self) -> None:
        """Nach Installation/Entfernen eines Shop-Themes das Menü neu aufbauen."""
        self.theme_menu.clear()
        self._build_theme_menu()

    def _build_theme_menu(self) -> None:
        if not hasattr(self, "theme_menu"):
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
            ("Aus dem Theme-Shop", installed_theme_names()),
        )
        for label, names in groups:
            if not names:
                continue
            submenu = self.theme_menu.addMenu(label)
            for name in names:
                self._add_theme_action(submenu, name)
        self.theme_menu.addSeparator()
        self.theme_menu.addAction("Theme-Shop …", self.show_theme_shop)
        self.theme_menu.addAction("Themes kombinieren …", self.edit_theme_mix)
        self.theme_menu.addAction("Drei Pride-Favoriten auswählen …", self.edit_pride_favorites)

    def _add_theme_action(self, menu: QMenu, name: str) -> None:
        theme = get_theme(name)
        if theme is None:
            return
        # The same theme can appear in both favourites and the full collection.
        action = QAction(theme.label, self, checkable=True)
        action.setChecked(name == self.settings.theme)
        action.triggered.connect(lambda _checked=False, n=name: self.set_theme(n))
        menu.addAction(action)
        self.theme_action_group.addAction(action)
        self._theme_action_copies.setdefault(name, []).append(action)
        self.theme_actions.setdefault(name, action)

    def edit_theme_mix(self) -> None:
        """Let the user combine the base theme with up to seven additional palettes."""
        dialog = QDialog(self)
        dialog.setWindowTitle('Themes kombinieren')
        dialog.resize(500, 600)
        layout = QVBoxLayout(dialog)
        note = QLabel(
            'Das aktive Theme bleibt die Basis für Hintergrund und Text. '
            'Wähle bis zu sieben weitere Themes dazu. Alle gewählten Themes erscheinen '
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
            count.setText(f"{selected_count}/8 Themes ausgewählt")

        def changed(checked: bool, own_name: str) -> None:
            if checked and sum(1 for checkbox in checks.values() if checkbox.isChecked()) > 8:
                checks[own_name].blockSignals(True)
                checks[own_name].setChecked(False)
                checks[own_name].blockSignals(False)
                QMessageBox.information(
                    dialog, 'Maximal acht Themes',
                    'Du kannst die Basis mit höchstens sieben weiteren Themes kombinieren.',
                )
            update_count()

        for name, theme in all_themes().items():
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
                    view.setHtml(self._render_start_page(), QUrl('about:blank'))
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
        for label, url in SEARCH_PROVIDERS.items():
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
        self._refresh_open_start_pages()
        self._save_settings()
        self._apply_toolbar_preferences()
        self.statusBar().showMessage("Deine Browserleiste wurde angepasst.", 3000)

    def open_feedback_email(self) -> None:
        QDesktopServices.openUrl(QUrl(f"mailto:{FEEDBACK_EMAIL}?subject=Nexlori%20-%20Anliegen%20oder%20Verbesserung"))

    def open_discord(self) -> None:
        QDesktopServices.openUrl(QUrl(DISCORD_URL))

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
        self.more_menu.addAction("Nexlori-Add-ons …", self.show_addons_center)
        self.tools_menu = self.more_menu.addMenu("Werkzeuge")
        developer_menu = self.more_menu.addMenu("Entwickler")
        developer_menu.addAction("Entwicklerwerkzeuge (F12)", self.show_developer_tools, QKeySequence("F12"))
        developer_menu.addAction("Browser-Informationen", self.show_browser_information)
        developer_menu.addAction("Nexlori-Datenordner öffnen", self.open_data_folder)
        self.more_menu.addAction("Theme-Shop …", self.show_theme_shop)
        self.more_menu.addAction("Als Standardbrowser festlegen …", self.set_as_default_browser)
        self.more_menu.addAction("Einstellungen", self.show_settings, QKeySequence("Ctrl+,"))
        self.more_menu.addAction("Browserleiste anpassen …", self.customize_toolbar)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Downloads-Ordner öffnen", self.open_download_folder)
        self.more_menu.addAction("Webseite neu laden", self.reload_current, QKeySequence("F5"))
        self.more_menu.addAction("Theme auswählen", self.show_theme_menu)
        self.more_menu.addAction("Nach Updates suchen", self.check_for_updates)
        self.more_menu.addSeparator()
        self.more_menu.addAction("💬 Discord-Community beitreten …", self.open_discord)
        self.more_menu.addAction("Feedback per E-Mail …", self.open_feedback_email)
        self.more_menu.addAction("Verbesserung auf GitHub melden …", self.open_feedback_github)
        self.more_menu.addSeparator()
        self.more_menu.addAction("Über Nexlori", self.show_about)
        self.more_menu.addAction("Beenden", self.close, QKeySequence("Alt+F4"))
        self._refresh_tools_menu()

    def _bind_shortcuts(self) -> None:
        shortcuts = (
            ("Ctrl+T", lambda: self.new_tab()),
            ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+L", self.focus_address),
            ("Alt+D", self.focus_address),
            ("F6", self.focus_address),
            ("Ctrl+P", lambda: self._run_tool("pdf-export")),
            ("Ctrl+Alt+R", lambda: self._run_tool("reader")),
            ("Ctrl+Alt+S", lambda: self._run_tool("screenshot")),
            ("Ctrl+=", lambda: self.change_zoom(0.1)),
            ("Ctrl+R", self.reload_current),
            ("F5", self.reload_current),
            ("Alt+Left", self.go_back),
            ("Alt+Right", self.go_forward),
            ("Alt+Home", self.go_home),
            ("Ctrl+F", self.show_find),
            ("Ctrl+D", self.toggle_bookmark),
            ("Ctrl+Shift+M", self.show_spotify_popup),
            ("Ctrl+Shift+P", self.show_password_manager),
            ("F12", self.show_developer_tools),
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
        muted = _mix_hex(theme.fg, theme.surface, 0.45)
        close_icons = self._write_tab_close_icons(theme)
        close_css = (
            f'QTabBar::close-button {{ image:url("{close_icons[0]}"); subcontrol-position:right; border-radius:7px; padding:3px; }}\n'
            f'QTabBar::close-button:hover {{ image:url("{close_icons[1]}"); background:{theme.surface}; }}\n'
            if close_icons else ""
        )
        self.setStyleSheet(close_css + f"""
QMainWindow, QWidget {{ background:{theme.bg}; color:{theme.fg}; }}
QWidget#toolbar {{ background:{theme.bg}; }}
QWidget#tabRow {{ background:{theme.surface}; }}
QWidget#titleBar {{ background:{theme.surface}; }}
QWidget#titleTabsHost {{ background:{theme.surface}; }}
QLabel#titleText {{ color:{theme.fg}; background:transparent; font-size:12px; }}
QToolButton#titleButton, QToolButton#titleCloseButton {{ background:transparent; color:{theme.fg}; border:0; border-radius:0;
 min-width:46px; max-width:46px; min-height:42px; max-height:42px; padding:0; font-size:13px; }}
QToolButton#titleButton:hover {{ background:{theme.bg}; color:{theme.accent}; }}
QToolButton#titleCloseButton:hover {{ background:#E81123; color:#FFFFFF; }}
QTabBar {{ background:{theme.surface}; }}
QTabBar::tab {{ background:{theme.surface}; color:{theme.fg}; border:1px solid transparent;
 border-top-left-radius:9px; border-top-right-radius:9px; padding:5px 9px; margin-right:2px; min-width:68px; max-height:30px; }}
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
QMenu::item:disabled {{ color:{muted}; }}
QProgressBar#loadProgress {{ border:0; background:{theme.surface}; }}
QProgressBar#loadProgress::chunk {{ background:{theme.accent}; }}
QStatusBar {{ background:{theme.surface}; color:{theme.fg}; }}
QStatusBar::item {{ border:0; }}
QLabel {{ background:transparent; }}
QPushButton {{ background:{theme.surface}; color:{theme.fg}; border:1px solid {theme.surface}; border-radius:10px; padding:7px 16px; }}
QPushButton:hover {{ border-color:{theme.accent}; }}
QPushButton:pressed {{ background:{theme.bg}; }}
QPushButton:disabled {{ color:{muted}; }}
""")
        palette = QPalette()
        for role, color in (
            (QPalette.ColorRole.Window, theme.bg), (QPalette.ColorRole.WindowText, theme.fg),
            (QPalette.ColorRole.Base, theme.surface), (QPalette.ColorRole.AlternateBase, theme.bg),
            (QPalette.ColorRole.Text, theme.fg), (QPalette.ColorRole.Button, theme.surface),
            (QPalette.ColorRole.ButtonText, theme.fg), (QPalette.ColorRole.Highlight, theme.accent),
            (QPalette.ColorRole.HighlightedText, theme.bg), (QPalette.ColorRole.ToolTipBase, theme.surface),
            (QPalette.ColorRole.ToolTipText, theme.fg), (QPalette.ColorRole.PlaceholderText, muted),
            (QPalette.ColorRole.Link, theme.accent),
        ):
            palette.setColor(role, QColor(color))
        self.setPalette(palette)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(palette)  # Dialoge und Menüs sind eigene Fenster und erben die Fensterpalette nicht
        self.accent_line.set_theme(theme)
        self.accent_line.set_flow(self.motion.continuous and self.isVisible())
        self.statusBar().setStyleSheet(f"QStatusBar {{ background:{theme.surface}; color:{theme.fg}; }}")
        self.address.set_icon_color(theme.fg)
        self._completer.popup().setStyleSheet(
            f"QListView {{ background:{theme.surface}; color:{theme.fg}; border:1px solid {theme.accent}; padding:4px; }}"
            f"QListView::item {{ padding:6px 10px; border-radius:6px; }}"
            f"QListView::item:selected {{ background:{theme.bg}; color:{theme.accent}; }}"
        )
        if self.resize_frame is not None:
            self.resize_frame.set_colors(theme.surface, theme.accent)
        try:
            icon = _qt_app_icon(theme)
            self.setWindowIcon(icon)
            if self.title_bar is not None:
                self.title_bar.set_icon(icon)
        except Exception:  # noqa: BLE001 - das Icon ist rein kosmetisch
            pass
        if not self.custom_titlebar and self.isVisible():
            apply_native_titlebar_colors(self, theme)

    def _write_tab_close_icons(self, theme: Theme) -> tuple[str, str] | None:
        """Zeichnet die Schließen-Symbole der Tabs in Theme-Farben und gibt (normal, hover) als Pfade zurück."""
        try:
            folder = self.settings_path.parent / "ui"
            folder.mkdir(parents=True, exist_ok=True)
            paths = []
            for name, color in (("tab-close", theme.fg), ("tab-close-hover", theme.accent)):
                target = folder / f"{name}.png"
                _line_icon("clear", color).pixmap(32, 32).save(str(target), "PNG")
                paths.append(target.as_posix())
            return paths[0], paths[1]
        except OSError:
            return None

    def _chrome_region(self) -> QRect:
        """Bereich über der Webseite (Titel, Tabs, Suchleiste) – nur dieser wird beim Theme-Wechsel überblendet."""
        top = self.tabs.stack.mapTo(self, QPoint(0, 0)).y()
        return QRect(0, 0, self.width(), max(0, top))

    def set_theme(self, name: str) -> None:
        if not is_known_theme(name):
            return
        self.settings.theme = name
        self.settings.theme_mix = []
        self.theme = combine_themes([self.settings.theme])
        # Update the profile-level stylesheet too, so pages opened later receive the new theme.
        self._refresh_page_theme_script()
        self._refresh_addons_script()
        crossfade(self, self._chrome_region(), self._apply_browser_theme, self.motion)
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
                    view.setHtml(self._render_start_page(), QUrl("about:blank"))
                elif getattr(view, "_nexlori_internal", None):
                    self._show_internal_page(view, view._nexlori_internal)
        self.statusBar().showMessage(f"Theme: {self.theme.label}", 2500)

    @staticmethod
    def _qt_color(value: str):
        from PySide6.QtGui import QColor
        return QColor(value)

    def _build_page_theme_script(self, enabled: bool) -> str:
        return build_page_theme_script(self.theme, enabled)

    def _refresh_password_capture_script(self) -> None:
        """Install a form-submit watcher only on secure top-level pages."""
        scripts = self.profile.scripts()
        existing = getattr(self, "_password_capture_script", None)
        if existing is not None:
            try:
                scripts.remove(existing)
            except (RuntimeError, TypeError):
                pass
        resource = QFile(":/qtwebchannel/qwebchannel.js")
        if not resource.open(QIODevice.OpenModeFlag.ReadOnly):
            self._password_capture_script = None
            return
        try:
            channel_source = bytes(resource.readAll()).decode("utf-8", errors="replace")
        finally:
            resource.close()
        watcher = r"""
(function () {
  if (location.protocol !== "https:" || window.__nexloriPasswordCaptureInstalled) return;
  window.__nexloriPasswordCaptureInstalled = true;
  if (typeof QWebChannel !== "function" || !window.qt || !qt.webChannelTransport) return;
  new QWebChannel(qt.webChannelTransport, function (channel) {
    const bridge = channel.objects.nexloriCredentials;
    if (!bridge || typeof bridge.offerCredentials !== "function") return;
    document.addEventListener("submit", function (event) {
      if (window.__nexloriBypassLoginCapture) {
        window.__nexloriBypassLoginCapture = false;
        return;
      }
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) return;
      const passwordField = form.querySelector('input[type="password"]');
      if (!passwordField || !passwordField.value) return;
      const userFields = Array.from(form.querySelectorAll(
        'input[autocomplete="username"], input[type="email"], input[name*="user" i], ' +
        'input[id*="user" i], input[name*="login" i], input[id*="login" i], ' +
        'input[name*="email" i], input[id*="email" i], input[type="text"]'
      ));
      const userField = userFields.find(function (field) {
        return field !== passwordField && field.value && field.value.trim();
      });
      if (!userField) return;
      let action;
      try { action = new URL(form.action || location.href, location.href); } catch (_) { return; }
      if (action.origin !== location.origin) return;
      event.preventDefault();
      window.__nexloriPendingForm = form;
      window.__nexloriPendingSubmitter = event.submitter || null;
      window.__nexloriResumePendingLogin = function () {
        const pending = window.__nexloriPendingForm;
        const submitter = window.__nexloriPendingSubmitter;
        window.__nexloriPendingForm = null;
        window.__nexloriPendingSubmitter = null;
        window.__nexloriResumePendingLogin = null;
        if (!pending) return;
        window.__nexloriBypassLoginCapture = true;
        try {
          if (submitter && submitter.form === pending) pending.requestSubmit(submitter);
          else pending.requestSubmit();
        } catch (_) {
          pending.submit();
        }
      };
      bridge.offerCredentials(String(userField.value).slice(0, 1024), String(passwordField.value).slice(0, 4096));
    }, true);
  });
})();
"""
        script = QWebEngineScript()
        script.setName("NexloriPasswordSavePrompt")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(False)
        script.setSourceCode(channel_source + "\n" + watcher)
        scripts.insert(script)
        self._password_capture_script = script

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
        view = QWebEngineView(self.tabs.stack)
        page = BrowserPage(self.profile, self, view)
        view.setPage(page)
        channel = QWebChannel(page)
        credential_bridge = CredentialCaptureBridge(self, view)
        channel.registerObject("nexloriCredentials", credential_bridge)
        page.setWebChannel(channel)
        view._nexlori_webchannel = channel
        view._nexlori_credential_bridge = credential_bridge
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
        view.page().fullScreenRequested.connect(self._on_fullscreen_requested)
        view.page().pdfPrintingFinished.connect(self._on_pdf_finished)
        view._nexlori_loading = False
        self._tab_activity[view] = time.monotonic()
        index = self.tabs.addTab(view, "Neuer Tab")
        if activate:
            self.tabs.setCurrentIndex(index)
        if start_page:
            view._nexlori_start = True
            view.setHtml(self._render_start_page(), QUrl("about:blank"))
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
        if self._html_fullscreen:
            self._set_html_fullscreen(False)
        self.tabs.removeTab(index)
        if widget:
            self._tab_activity.pop(widget, None)
            if getattr(self, "_active_view", None) is widget:
                self._active_view = None
            widget.deleteLater()
        if self.tabs.count() == 0:
            self.new_tab()
        self._update_navigation_state()

    def _on_current_changed(self, _index: int) -> None:
        if self._html_fullscreen:
            self._set_html_fullscreen(False)
        now = time.monotonic()
        previous = getattr(self, "_active_view", None)
        if previous is not None and previous in self._tab_activity:
            self._tab_activity[previous] = now  # ab jetzt zählt die Zeit im Hintergrund
        view = self.current_view()
        self._active_view = view
        if view:
            self._tab_activity[view] = now
            self._wake_view(view)
            self._on_url_changed(view, view.url())
            self._update_bookmark_button()
            self.setWindowTitle(f"{view.title()} — Nexlori" if view.title() else "Nexlori")
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
            view._nexlori_internal = None
        if view is self.current_view():
            internal = getattr(view, "_nexlori_internal", None)
            if getattr(view, "_nexlori_start", False) and url_text == "about:blank":
                self.address.clear()
                self.address.set_security(None)
            elif internal and url_text == "about:blank":
                self.address.setText(internal)
                self.address.setModified(False)
                self.address.set_security("internal")
            else:
                # Während der Nutzer gerade tippt, darf eine Weiterleitung den Text nicht überschreiben.
                if not (self.address.hasFocus() and self.address.isModified()):
                    self.address.setText(url_text)
                    self.address.setModified(False)
                self.address.set_security(_security_kind(url_text))
            self._update_navigation_state()
            self._update_bookmark_button()

    def _load_started(self, view: QWebEngineView) -> None:
        view._nexlori_loading = True
        if view is self.current_view():
            self.progress.setValue(0)
            self.progress.show()
            self.statusBar().showMessage("Seite wird geladen …")

    def _load_progress(self, view: QWebEngineView, value: int) -> None:
        if view is self.current_view():
            animate_progress(self.progress, value, self.motion)
            if value >= 100:
                QTimer.singleShot(self.motion.ms(220) + 40, self._hide_progress_if_done)

    def _hide_progress_if_done(self) -> None:
        if self.progress.value() >= 100:
            self.progress.hide()

    def _load_finished(self, view: QWebEngineView, ok: bool) -> None:
        view._nexlori_loading = False
        page = view.page()
        origin = getattr(page, "_https_origin", None)
        if origin and view.url().scheme().lower() == "https":
            page._https_origin = None
            if not ok:
                QTimer.singleShot(0, lambda: self._offer_http_fallback(view, origin))
        if ok:
            self._remember_visit(view)
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

    def _refresh_open_start_pages(self) -> None:
        """Refresh already-open internal start pages after search-provider changes."""
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if (
                isinstance(view, QWebEngineView)
                and getattr(view, "_nexlori_start", False)
                and view.url().toString() == "about:blank"
            ):
                view.setHtml(self._render_start_page(), QUrl("about:blank"))

    def navigate_view(self, view: QWebEngineView, url: str) -> None:
        if url.lower() in {"about:start", "nexlori:start"}:
            view._nexlori_start = True
            view.setHtml(self._render_start_page(), QUrl("about:blank"))
            return
        view._nexlori_start = False
        view._nexlori_internal = None
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
        if getattr(view, "_nexlori_internal", None) and view.url().toString() == "about:blank":
            self._show_internal_page(view, view._nexlori_internal)
        elif getattr(view, "_nexlori_start", False) and view.url().toString() == "about:blank":
            view.setHtml(self._render_start_page(), QUrl("about:blank"))
        else:
            view.reload()

    def go_home(self) -> None:
        view = self.current_view()
        if view:
            view._nexlori_start = True
            view._nexlori_internal = None
            view.setHtml(self._render_start_page(), QUrl("about:blank"))
            index = self.tabs.indexOf(view)
            if index >= 0:
                self.tabs.setTabText(index, "Nexlori · Startseite")

    def _restore_address(self) -> None:
        """Esc in der Adressleiste: Eingabe verwerfen und die aktuelle Adresse wieder anzeigen."""
        view = self.current_view()
        if view is None:
            return
        url_text = view.url().toString()
        is_start = getattr(view, "_nexlori_start", False) and url_text == "about:blank"
        internal = getattr(view, "_nexlori_internal", None)
        self.address.setText("" if is_start else (internal or url_text) if url_text == "about:blank" else url_text)
        self.address.setModified(False)
        view.setFocus()

    def _build_address_completer(self) -> None:
        self._visited: dict[str, str] = {}
        self._suggestion_model = QStringListModel(self)
        completer = QCompleter(self._suggestion_model, self.address)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(8)
        completer.activated[str].connect(self._suggestion_chosen)
        self.address.setCompleter(completer)
        self._completer = completer
        self._refresh_suggestions()

    def _refresh_suggestions(self) -> None:
        """Vorschläge: Lesezeichen und in dieser Sitzung besuchte Seiten (nur im Arbeitsspeicher)."""
        urls: list[str] = []
        for item in self.bookmarks:
            urls.append(str(item.get("url", "")))
        urls.extend(reversed(list(self._visited)))
        unique = list(dict.fromkeys(u for u in urls if u))
        self._suggestion_model.setStringList(unique[:400])

    def _remember_visit(self, view: QWebEngineView) -> None:
        url = view.url().toString()
        if not url.lower().startswith(("http://", "https://")):
            return
        self._visited.pop(url, None)
        self._visited[url] = view.title()
        while len(self._visited) > 300:
            self._visited.pop(next(iter(self._visited)))
        self._refresh_suggestions()

    def _suggestion_chosen(self, text: str) -> None:
        self.address.setText(text)
        self.navigate_address()

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
        self._refresh_suggestions()
        self._refresh_open_start_pages()
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

    def show_extensions_manager(self, initial: str | None = None) -> None:
        if self.extension_manager is None:
            QMessageBox.warning(
                self, "Add-ons nicht verfügbar",
                "Browser-Erweiterungen erfordern Qt WebEngine 6.10 oder neuer.",
            )
            return
        try:
            from .extensions_ui import ExtensionsDialog
            dialog = ExtensionsDialog(self, self)
            if initial == "zip":
                QTimer.singleShot(0, dialog.install_zip)
            elif initial == "folder":
                QTimer.singleShot(0, dialog.install_folder)
            dialog.exec()
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
        background = QCheckBox("Beim Schließen in den Infobereich minimieren (Nexlori bleibt aktiv)", dialog)
        background.setChecked(self.settings.background_on_close)
        background.setToolTip("Klicke im Nexlori-Symbol im Infobereich auf „Beenden“, um den Browser vollständig zu schließen.")

        zoom = QDoubleSpinBox(dialog)
        zoom.setRange(0.5, 3.0)
        zoom.setSingleStep(0.1)
        zoom.setSuffix("×")
        zoom.setValue(float(self.settings.page_zoom))

        memory_saver = QCheckBox("Inaktive Tabs automatisch entladen (spart RAM)", dialog)
        memory_saver.setChecked(self.settings.memory_saver)
        search_engine = QComboBox(dialog)
        providers = SEARCH_PROVIDERS
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

        animations = QComboBox(dialog)
        for label, value in (("Voll – fließende Farben und weiche Übergänge", "full"),
                             ("Reduziert – nur kurze Übergänge", "reduced"), ("Aus", "off")):
            animations.addItem(label, value)
        animations.setCurrentIndex(max(0, animations.findData(self.settings.animations)))
        titlebar = QCheckBox("Eigene Titelleiste in Theme-Farben (Neustart nötig)", dialog)
        titlebar.setChecked(self.settings.custom_titlebar)
        form.addRow("Animationen", animations)
        form.addRow("Speicher", memory_saver)
        form.addRow("Fenster", titlebar)
        form.addRow("Website-Farben", theme_css)
        form.addRow("Werbe- und Trackerschutz", ubol)
        form.addRow("Updates", updates)
        form.addRow("Pop-ups", popups)
        form.addRow("Hintergrundbetrieb", background)
        form.addRow("Standard-Zoom", zoom)
        form.addRow("Suchmaschine", search_engine)
        root.addLayout(form)

        actions = QHBoxLayout()
        addons = QPushButton("Add-ons …", dialog)
        addons.clicked.connect(lambda: (dialog.accept(), QTimer.singleShot(0, self.show_addons_center)))
        shop = QPushButton("Theme-Shop …", dialog)
        shop.clicked.connect(lambda: (dialog.accept(), QTimer.singleShot(0, self.show_theme_shop)))
        toolbar = QPushButton("Browserleiste anpassen …", dialog)
        toolbar.clicked.connect(lambda: (dialog.accept(), QTimer.singleShot(0, self.customize_toolbar)))
        default_browser = QPushButton("Standardbrowser …", dialog)
        default_browser.clicked.connect(lambda: (dialog.accept(), QTimer.singleShot(0, self.set_as_default_browser)))
        actions.addWidget(addons)
        actions.addWidget(shop)
        actions.addWidget(toolbar)
        actions.addWidget(default_browser)
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
        self.settings.memory_saver = memory_saver.isChecked()
        self.settings.allow_web_popups = popups.isChecked()
        self.settings.background_on_close = background.isChecked()
        self.settings.page_zoom = float(zoom.value())
        self.settings.search_url = canonical_search_url(str(search_engine.currentData()))
        self.settings.extensions_enabled["ublock-origin-lite"] = self.settings.ubol_enabled
        self.settings.animations = str(animations.currentData())
        self.motion = Motion(self.settings.animations)
        self.accent_line.set_flow(self.motion.continuous)
        titlebar_changed = titlebar.isChecked() != self.settings.custom_titlebar
        self.settings.custom_titlebar = titlebar.isChecked()
        self._refresh_page_theme_script()
        self._sync_extension_states()
        self._refresh_open_start_pages()
        self._save_settings()
        for index in range(self.tabs.count()):
            view = self.tabs.widget(index)
            if isinstance(view, QWebEngineView):
                view.setZoomFactor(self.settings.page_zoom)
                self.apply_page_theme(view)
        self.statusBar().showMessage("Einstellungen gespeichert.", 3000)
        if titlebar_changed:
            QMessageBox.information(
                self, "Titelleiste",
                "Die Änderung der Titelleiste wird nach dem nächsten Start von Nexlori wirksam.",
            )

    def set_as_default_browser(self) -> None:
        """Register Nexlori with Windows and open the system-controlled default-app chooser."""
        if os.name != "nt":
            QMessageBox.information(self, "Standardbrowser", "Diese Funktion wird derzeit nur unter Windows unterstützt.")
            return
        executable = sys.executable if getattr(sys, "frozen", False) else None
        try:
            from .default_browser import default_browser_settings_uri, register_windows_browser
            if not register_windows_browser(executable):
                QMessageBox.information(
                    self, "Standardbrowser",
                    "Bitte starte die installierte Nexlori-Windows-Version. Danach kannst du Nexlori hier als "
                    "Standardbrowser auswählen.",
                )
                return
            QDesktopServices.openUrl(QUrl(default_browser_settings_uri()))
            QMessageBox.information(
                self, "Standardbrowser",
                "Die Windows-Einstellungen wurden geöffnet. Wähle dort Nexlori für HTTP- und HTTPS-Links aus "
                "und bestätige die Auswahl. Windows muss die Änderung selbst bestätigen.",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Standardbrowser", f"Nexlori konnte nicht registriert werden: {exc}")

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
            "<p>Updates werden von GitHub Releases bezogen und vor dem Ersetzen der EXE per SHA-256 geprüft.</p>"
            f'<p>💬 <a href="{DISCORD_URL}">Nexlori auf Discord</a></p>',
        )

    # ------------------------------------------------------------------ Interne nexlori://-Links
    def _internal_page_html(self, label: str) -> str | None:
        if label == "nexlori://addons":
            return addons_page_html(self.theme)
        if label == "nexlori://home-network":
            return home_network_page_html(self.theme)
        return None

    def _show_internal_page(self, view: QWebEngineView, label: str) -> None:
        html = self._internal_page_html(label)
        if html is None:
            return
        view._nexlori_start = False
        view._nexlori_internal = label
        view.setHtml(html, QUrl("about:blank"))
        if view is self.current_view():
            self.address.setText(label)
            self.address.setModified(False)
            self.address.set_security("internal")

    def handle_internal_url(self, page: QWebEnginePage, url: QUrl) -> None:
        """Verarbeitet nexlori://-Links. Sie werden nur von Nexlori-eigenen Seiten angenommen, nie von Webseiten."""
        view = QWebEngineView.forPage(page)
        trusted = view is not None and (
            getattr(view, "_nexlori_start", False) or getattr(view, "_nexlori_internal", None)
        ) and view.url().toString() in ("", "about:blank")
        if not trusted:
            self.statusBar().showMessage("Interne Nexlori-Links funktionieren nur auf Nexlori-Seiten.", 4000)
            return
        route = (url.host() + url.path()).rstrip("/")
        query = QUrlQuery(url)
        if route == "settings":
            self.show_settings()
        elif route == "addons":
            self._show_internal_page(view, "nexlori://addons")
        elif route == "addons/builtin":
            self.show_addons_center()
        elif route in ("addons/manage", "addons/install-zip", "addons/install-folder"):
            self.show_extensions_manager({"addons/install-zip": "zip", "addons/install-folder": "folder"}.get(route))
        elif route == "home-network":
            self._show_internal_page(view, "nexlori://home-network")
        elif route == "home-network/open":
            try:
                target = normalize_home_target(query.queryItemValue("target", QUrl.ComponentFormattingOption.FullyDecoded))
            except ValueError as exc:
                self.statusBar().showMessage(str(exc), 6000)
                return
            self.navigate_view(view, target)
        elif route == "browser/home":
            self.go_home()
        elif route == "browser/retry":
            target = query.queryItemValue("url", QUrl.ComponentFormattingOption.FullyDecoded)
            if urlsplit(target).scheme.lower() in {"http", "https"}:
                self.navigate_view(view, target)
        elif route == "community/discord":
            self.open_discord()
        else:
            self.statusBar().showMessage("Unbekannter Nexlori-Link.", 4000)

    # ------------------------------------------------------------------ Navigation: Saubere Links & HTTPS bevorzugen
    def rewrite_navigation(self, page: QWebEnginePage, url: QUrl, navigation_type) -> str | None:
        """Gibt eine geänderte Zieladresse zurück, wenn ein Add-on (Saubere Links, HTTPS bevorzugen) eingreift."""
        kinds = QWebEnginePage.NavigationType
        if navigation_type not in (kinds.NavigationTypeLinkClicked, kinds.NavigationTypeTyped):
            return None
        text = url.toString()
        target = text
        addons = self.settings.builtin_addons
        if is_enabled(addons, "clean-urls"):
            target = strip_tracking_params(target)
        if (
            is_enabled(addons, "https-first")
            and url.scheme().lower() == "http"
            and (url.host() or "").lower() not in self._http_allowed_hosts
        ):
            upgraded = upgrade_to_https(target)
            if upgraded:
                page._https_origin = target
                target = upgraded
        return target if target != text else None

    def _offer_http_fallback(self, view: QWebEngineView, origin: str) -> None:
        if self.tabs.indexOf(view) < 0 or self._closing:
            return
        host = urlsplit(origin).hostname or origin
        answer = QMessageBox.question(
            self, "HTTPS nicht verfügbar",
            f"„{host}“ unterstützt kein HTTPS oder ist nicht erreichbar.\n\n"
            "Seite trotzdem unverschlüsselt (HTTP) öffnen? Eingaben auf dieser Seite könnten von Dritten mitgelesen werden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._http_allowed_hosts.add(host.lower())
            view.setUrl(QUrl(origin))

    # ------------------------------------------------------------------ Eingebaute Add-ons
    def _refresh_addons_script(self) -> None:
        """Setzt das Skript aller aktiven Seiten-Add-ons neu (wird bei jedem neuen Dokument eingesetzt)."""
        scripts = self.profile.scripts()
        if self._addons_script is not None:
            try:
                scripts.remove(self._addons_script)
            except (RuntimeError, TypeError):
                pass
            self._addons_script = None
        source = build_addons_script(self.settings.builtin_addons, accent=self.theme.accent, bg=self.theme.bg)
        if not source:
            return
        script = QWebEngineScript()
        script.setName("NexloriAddons")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
        script.setRunsOnSubFrames(False)
        script.setSourceCode(source)
        scripts.insert(script)
        self._addons_script = script

    def set_builtin_addon(self, addon_id: str, enabled: bool) -> None:
        self.settings.builtin_addons[addon_id] = bool(enabled)
        self._save_settings()
        self._refresh_addons_script()
        self._refresh_tools_menu()
        addon = next((a for a in ADDONS if a.id == addon_id), None)
        view = self.current_view()
        if addon is not None and addon.kind == "script" and view is not None and not getattr(view, "_nexlori_start", False):
            view.reload()
        if addon_id == "tab-sleep" and not enabled:
            for index in range(self.tabs.count()):
                widget = self.tabs.widget(index)
                if isinstance(widget, QWebEngineView):
                    self._wake_view(widget)

    def set_tab_sleep_minutes(self, minutes: int) -> None:
        self.settings.tab_sleep_minutes = int(minutes)
        self._save_settings()

    def show_addons_center(self) -> None:
        from .addons_ui import AddonsDialog
        AddonsDialog(self, self).exec()

    def _refresh_tools_menu(self) -> None:
        self.tools_menu.clear()
        labels = {"reader": "Lesemodus", "pdf-export": "Seite als PDF speichern …", "screenshot": "Screenshot speichern …"}
        shortcuts = {"reader": "Ctrl+Alt+R", "pdf-export": "Ctrl+P", "screenshot": "Ctrl+Alt+S"}
        added = 0
        for addon_id, label in labels.items():
            if is_enabled(self.settings.builtin_addons, addon_id):
                self.tools_menu.addAction(label, lambda a=addon_id: self._run_tool(a), QKeySequence(shortcuts[addon_id]))
                added += 1
        if not added:
            action = self.tools_menu.addAction("Keine Werkzeuge aktiv (siehe Nexlori-Add-ons)")
            action.setEnabled(False)

    def _run_tool(self, addon_id: str) -> None:
        if not is_enabled(self.settings.builtin_addons, addon_id):
            return
        {"reader": self.reader_mode, "pdf-export": self.save_page_pdf, "screenshot": self.save_screenshot}[addon_id]()

    def _tool_view(self) -> QWebEngineView | None:
        view = self.current_view()
        if view is None or getattr(view, "_nexlori_start", False) or view.url().toString() in ("", "about:blank"):
            self.statusBar().showMessage("Öffne zuerst eine Webseite.", 3000)
            return None
        return view

    def reader_mode(self) -> None:
        view = self._tool_view()
        if view is None:
            return
        script = reader_script(bg=self.theme.bg, fg=self.theme.fg, accent=self.theme.accent)
        view.page().runJavaScript(script, self._reader_result)

    def _reader_result(self, result) -> None:
        if result == "no-article":
            self.statusBar().showMessage("Auf dieser Seite wurde kein Artikel erkannt.", 3500)

    @staticmethod
    def _safe_file_stem(title: str, fallback: str) -> str:
        stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", title).strip(" ._")[:80]
        return stem or fallback

    def save_page_pdf(self) -> None:
        view = self._tool_view()
        if view is None:
            return
        stem = self._safe_file_stem(view.title(), "Seite")
        initial = str(Path.home() / "Downloads" / f"{stem}.pdf")
        filename, _ = QFileDialog.getSaveFileName(self, "Seite als PDF speichern", initial, "PDF-Dateien (*.pdf)")
        if not filename:
            return
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        view.page().printToPdf(filename)
        self.statusBar().showMessage("PDF wird erstellt …", 3000)

    def _on_pdf_finished(self, path: str, ok: bool) -> None:
        name = Path(path).name
        self.statusBar().showMessage(
            f"PDF gespeichert: {name}" if ok else "Das PDF konnte nicht erstellt werden.", 5000
        )

    def save_screenshot(self) -> None:
        view = self._tool_view()
        if view is None:
            return
        pixmap = view.grab()
        if pixmap.isNull():
            self.statusBar().showMessage("Der Screenshot konnte nicht erstellt werden.", 4000)
            return
        stem = self._safe_file_stem(view.title(), "Screenshot")
        initial = str(Path.home() / "Downloads" / f"{stem}.png")
        filename, _ = QFileDialog.getSaveFileName(self, "Screenshot speichern", initial, "PNG-Bilder (*.png)")
        if not filename:
            return
        if not filename.lower().endswith(".png"):
            filename += ".png"
        ok = pixmap.save(filename, "PNG")
        self.statusBar().showMessage(
            f"Screenshot gespeichert: {Path(filename).name}" if ok else "Der Screenshot konnte nicht gespeichert werden.", 5000
        )

    # ------------------------------------------------------------------ Tabs schlafen legen
    def _start_tab_sleep_timer(self) -> None:
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setInterval(60_000)
        self._sleep_timer.timeout.connect(self._sleep_tick)
        self._sleep_timer.start()

    def _sleep_tick(self) -> None:
        now = time.monotonic()
        current = self.current_view()
        if current is not None:
            self._tab_activity[current] = now
        if not (self.settings.memory_saver or is_enabled(self.settings.builtin_addons, "tab-sleep")) or self._closing:
            return
        skip = {
            view for view in self._tab_activity
            if view is current or getattr(view, "_nexlori_start", False) or getattr(view, "_nexlori_loading", False)
            or self.tabs.indexOf(view) < 0 or view.page().recentlyAudible()
        }
        for view in tabs_to_sleep(self._tab_activity, now, self.settings.tab_sleep_minutes, skip):
            self._sleep_view(view)

    def _sleep_view(self, view: QWebEngineView) -> None:
        page = view.page()
        if page.lifecycleState() == QWebEnginePage.LifecycleState.Discarded:
            return
        page.setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
        index = self.tabs.indexOf(view)
        if index >= 0 and not self.tabs.tabText(index).startswith("💤"):
            self.tabs.setTabText(index, "💤 " + self.tabs.tabText(index))

    def _wake_view(self, view: QWebEngineView) -> None:
        page = view.page()
        if page.lifecycleState() != QWebEnginePage.LifecycleState.Active:
            page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
        index = self.tabs.indexOf(view)
        if index >= 0 and self.tabs.tabText(index).startswith("💤"):
            self._update_tab_title(view, view.title())

    # ------------------------------------------------------------------ Vollbild (z. B. YouTube-Videos)
    def _on_fullscreen_requested(self, request) -> None:
        request.accept()
        self._set_html_fullscreen(bool(request.toggleOn()))

    def _set_html_fullscreen(self, on: bool) -> None:
        if on == self._html_fullscreen:
            return
        self._html_fullscreen = on
        chrome = [
            self.title_bar, self.accent_line, self.tab_row_widget, self.toolbar_widget, self.find_bar,
            self.progress, self._status_bar,
        ]
        if on:
            self._fullscreen_restore = "max" if self.isMaximized() else "normal"
            self._chrome_visibility = {id(w): w.isVisible() for w in chrome if w is not None}
            for widget in chrome:
                if widget is not None:
                    widget.hide()
            self.showFullScreen()
        else:
            for widget in chrome:
                if widget is not None and getattr(self, "_chrome_visibility", {}).get(id(widget), True):
                    widget.show()
            if self._fullscreen_restore == "max":
                self.showMaximized()
            else:
                self.showNormal()
        self._sync_window_state()

    # ------------------------------------------------------------------ Theme-Shop
    def show_theme_shop(self) -> None:
        from .theme_shop_ui import ThemeShopDialog
        ThemeShopDialog(self, self).exec()

    def remove_installed_theme(self, name: str) -> None:
        """Entfernt ein Shop-Theme; ist es aktiv oder Teil einer Kombination, wird vorher auf „Dunkel“ gewechselt."""
        if name == self.settings.theme or name in self.settings.theme_mix:
            self.set_theme("dunkel")
        self.theme_store.remove(name)
        self.settings.pride_favorites = [n for n in self.settings.pride_favorites if n != name]
        self.rebuild_theme_menu()
        self._save_settings()

    # ------------------------------------------------------------------ Fensterzustand
    def _sync_window_state(self) -> None:
        if not hasattr(self, "accent_line"):
            return
        if self.title_bar is not None:
            self.title_bar.set_maximized(self.isMaximized())
        if self.resize_frame is not None:
            self.resize_frame.set_resizable(not (self.isMaximized() or self.isFullScreen()))

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_window_state()
        elif event.type() == QEvent.Type.ActivationChange and hasattr(self, "accent_line"):
            self.accent_line.pause(not self.isActiveWindow())

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.accent_line.set_flow(self.motion.continuous)
            cascade_in([self.title_bar, self.tabs.bar if self.title_bar is not None else self.tab_row_widget, self.toolbar_widget], self.motion)
        if not self.custom_titlebar:
            apply_native_titlebar_colors(self, self.theme)

    def _release_web_views(self) -> None:
        """Seiten vor dem Profil freigeben (verhindert „Release of profile requested but WebEnginePage still not deleted“)."""
        for index in range(self.tabs.count() - 1, -1, -1):
            view = self.tabs.widget(index)
            self.tabs.removeTab(index)
            if isinstance(view, QWebEngineView):
                page = view.page()
                view.setPage(None)
                page.deleteLater()
                view.deleteLater()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._closing = True
        self._sleep_timer.stop()
        self.accent_line.pause(True)
        self._save_settings()
        self._save_bookmarks()
        self._release_web_views()
        super().closeEvent(event)

    def _save_settings(self) -> None:
        try:
            self.settings.save(self.settings_path)
        except (OSError, ValueError):
            self.statusBar().showMessage("Einstellungen konnten nicht gespeichert werden.", 3000)



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


def _write_smoke_progress(stage: str) -> None:
    """Write GUI-startup checkpoints for the Windows packaging smoke test only."""
    progress_path = os.environ.get("NEXLORI_SMOKE_PROGRESS")
    if not progress_path:
        return
    try:
        with Path(progress_path).open("a", encoding="utf-8") as handle:
            handle.write(stage + "\\n")
    except OSError:
        pass


def run(argv: list[str] | None = None) -> int:
    _write_smoke_progress("entrypoint")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--webengine-selftest"]:
        try:
            ok, detail = _selftest_webengine()
            print(("OK " if ok else "FEHLER ") + detail)
            return 0 if ok else 5
        except Exception as exc:  # noqa: BLE001
            print(f"FEHLER WebEngine: {type(exc).__name__}: {exc}")
            return 5

    _write_smoke_progress("before-settings")
    settings_path = default_settings_path()
    # Installierte Shop-Themes müssen bekannt sein, bevor die Einstellungen geprüft werden.
    ThemeStore(default_theme_dir(settings_path)).load_into_registry()
    _write_smoke_progress("themes-loaded")
    try:
        settings = Settings.load_lenient(settings_path)
    except (ValueError, OSError):
        settings = Settings()

    _write_smoke_progress("before-qapplication")
    app = QApplication.instance() or QApplication([APP_NAME])
    _write_smoke_progress("qapplication-created")
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Nexlori")
    app.setWindowIcon(_qt_app_icon())
    app.setStyle("Fusion")
    _write_smoke_progress("application-configured")
    start_url = None
    if argv:
        start_url = normalize_input(" ".join(arg for arg in argv if not arg.startswith("-")), settings.search_url)
    _write_smoke_progress("before-window-constructor")
    window = NexloriWindow(settings, settings_path, start_url)
    _write_smoke_progress("window-constructed")
    app.installEventFilter(DialogThemer(lambda: window.theme, app))
    window.show()
    _write_smoke_progress("window-shown")
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
