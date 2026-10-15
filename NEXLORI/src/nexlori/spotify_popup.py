"""A compact Spotify popup using Nexlori's shared Chromium profile."""
from __future__ import annotations

import json

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from .spotify_links import normalize_spotify_url

class SpotifyPopup(QDialog):
    """Small detachable player; it shares the browser profile so the user can sign in themselves."""

    def __init__(self, profile, parent=None):
        super().__init__(parent, Qt.WindowType.Tool)
        self.setWindowTitle("Nexlori · Spotify Mini-Player")
        self.resize(430, 690)
        self.setMinimumSize(340, 420)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        heading = QLabel("SPOTIFY · MINI-PLAYER", self)
        heading.setStyleSheet("font-weight:800; letter-spacing:1px;")
        header.addWidget(heading, 1)
        self.always_on_top = QCheckBox("Immer oben", self)
        self.always_on_top.toggled.connect(self._toggle_always_on_top)
        header.addWidget(self.always_on_top)
        root.addLayout(header)

        entry_row = QHBoxLayout()
        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("Spotify-Link zu Track, Album oder Playlist")
        self.url_input.returnPressed.connect(self.load_spotify)
        entry_row.addWidget(self.url_input, 1)
        load_btn = QPushButton("Laden", self)
        load_btn.clicked.connect(self.load_spotify)
        entry_row.addWidget(load_btn)
        root.addLayout(entry_row)

        quick_row = QHBoxLayout()
        home_btn = QPushButton("Spotify öffnen", self)
        home_btn.clicked.connect(lambda: self.view.setUrl(QUrl("https://open.spotify.com/")))
        quick_row.addWidget(home_btn)
        root.addLayout(quick_row)

        media_heading = QLabel("MEDIEN AUS DEM AKTIVEN BROWSER-TAB", self)
        media_heading.setStyleSheet("font-weight:800; letter-spacing:.6px;")
        root.addWidget(media_heading)
        self.media_status = QLabel("Wechsle zu einem Tab mit Audio oder Video, um ihn hier zu steuern.", self)
        self.media_status.setWordWrap(True)
        root.addWidget(self.media_status)

        media_controls = QHBoxLayout()
        media_back = QPushButton("−10 s", self)
        media_back.setToolTip("Aktives Tab-Medium 10 Sekunden zurück")
        media_back.clicked.connect(lambda: self._control_browser_media("seek", -10))
        self.media_play_pause = QPushButton("▶ / ⏸", self)
        self.media_play_pause.setToolTip("Wiedergabe im aktiven Browser-Tab umschalten")
        self.media_play_pause.clicked.connect(lambda: self._control_browser_media("toggle"))
        media_forward = QPushButton("+10 s", self)
        media_forward.setToolTip("Aktives Tab-Medium 10 Sekunden vor")
        media_forward.clicked.connect(lambda: self._control_browser_media("seek", 10))
        media_controls.addWidget(media_back)
        media_controls.addWidget(self.media_play_pause)
        media_controls.addWidget(media_forward)
        media_controls.addWidget(QLabel("Lautstärke", self))
        self.media_volume = QSlider(Qt.Orientation.Horizontal, self)
        self.media_volume.setRange(0, 100)
        self.media_volume.setValue(80)
        self.media_volume.setToolTip("Lautstärke der Audio-/Video-Elemente im aktiven Browser-Tab")
        self.media_volume.valueChanged.connect(self._set_browser_media_volume)
        media_controls.addWidget(self.media_volume, 1)
        root.addLayout(media_controls)

        self.view = QWebEngineView(self)
        self.view.setPage(QWebEnginePage(profile, self.view))
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self.view.load(QUrl("https://open.spotify.com/"))
        root.addWidget(self.view, 1)
        self._media_status_timer = QTimer(self)
        self._media_status_timer.setInterval(1800)
        self._media_status_timer.timeout.connect(self._refresh_browser_media_status)
        self._media_status_timer.start()

        self.status = QLabel("Tipp: Füge einen Spotify-Track- oder Playlist-Link ein.", self)
        self.status.setWordWrap(True)
        root.addWidget(self.status)

    def _active_browser_view(self):
        """Return Nexlori's current page, not the Spotify page embedded in this popup."""
        parent = self.parentWidget()
        getter = getattr(parent, "current_view", None)
        return getter() if callable(getter) else None

    def _control_browser_media(self, action: str, amount: int = 0) -> None:
        view = self._active_browser_view()
        if view is None:
            self.media_status.setText("Kein aktiver Browser-Tab verfügbar.")
            return
        action_json = json.dumps(action)
        script = f"""(() => {{
const media = Array.from(document.querySelectorAll('audio,video'));
if (!media.length) return JSON.stringify({{ok:false, reason:'none'}});
const action = {action_json};
if (action === 'toggle') {{
  const playing = media.some(m => !m.paused && !m.ended);
  for (const m of media) {{
    if (playing) m.pause();
    else {{ const result = m.play(); if (result && result.catch) result.catch(() => {{}}); }}
  }}
  return JSON.stringify({{ok:true, playing:!playing, count:media.length}});
}}
if (action === 'seek') {{
  for (const m of media) {{
    if (Number.isFinite(m.duration)) m.currentTime = Math.max(0, Math.min(m.duration, m.currentTime + (${amount})));
  }}
}}
return JSON.stringify({{ok:true, playing:media.some(m => !m.paused && !m.ended), count:media.length}});
}})()"""
        view.page().runJavaScript(script, self._media_command_finished)

    def _media_command_finished(self, result) -> None:
        try:
            data = json.loads(result) if isinstance(result, str) else {}
        except (TypeError, ValueError):
            data = {}
        if not data.get("ok"):
            self.media_status.setText("Im aktiven Tab wurden keine direkt steuerbaren Audio-/Video-Elemente gefunden.")
            return
        self.media_status.setText(
            f"Browsermedien: {data.get('count', 0)} Element(e) · "
            + ("Wiedergabe läuft" if data.get("playing") else "pausiert")
        )

    def _set_browser_media_volume(self, value: int) -> None:
        view = self._active_browser_view()
        if view is None:
            return
        volume = max(0, min(100, int(value))) / 100
        script = f"""(() => {{
const media = Array.from(document.querySelectorAll('audio,video'));
for (const m of media) {{ m.volume = {volume}; m.muted = {str(value == 0).lower()}; }}
return media.length;
}})()"""
        view.page().runJavaScript(script)

    def _refresh_browser_media_status(self) -> None:
        if not self.isVisible():
            return
        view = self._active_browser_view()
        if view is None:
            self.media_status.setText("Kein aktiver Browser-Tab verfügbar.")
            self.media_play_pause.setEnabled(False)
            return
        script = """(() => {
const media = Array.from(document.querySelectorAll('audio,video'));
return JSON.stringify({title:document.title || 'Aktiver Tab', count:media.length,
 playing:media.some(m => !m.paused && !m.ended)});
})()"""
        view.page().runJavaScript(script, self._browser_media_status_received)

    def _browser_media_status_received(self, result) -> None:
        try:
            data = json.loads(result) if isinstance(result, str) else {}
        except (TypeError, ValueError):
            data = {}
        if not data.get("count"):
            self.media_status.setText("Keine direkt steuerbaren Audio-/Video-Elemente im aktiven Tab.")
            self.media_play_pause.setEnabled(False)
            return
        self.media_play_pause.setEnabled(True)
        title = str(data.get("title") or "Aktiver Tab")[:60]
        self.media_status.setText(
            f"{title} · {data['count']} Medien-Element(e) · "
            + ("Wiedergabe läuft" if data.get("playing") else "pausiert")
        )

    def _toggle_always_on_top(self, enabled: bool) -> None:
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if visible:
            self.show()

    def load_spotify(self) -> None:
        try:
            target = normalize_spotify_url(self.url_input.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Spotify-Link", str(exc))
            return
        self.status.setText("Spotify wird geladen …")
        try:
            self.view.loadFinished.disconnect(self._load_finished)
        except (RuntimeError, TypeError):
            pass
        self.view.loadFinished.connect(self._load_finished)
        self.view.setUrl(QUrl(target))

    def _load_finished(self, ok: bool) -> None:
        self.status.setText(
            "Spotify-Inhalt geladen." if ok else
            "Spotify konnte den Inhalt nicht laden. Prüfe den Link, die Anmeldung oder die Netzwerkverbindung."
        )
        try:
            self.view.loadFinished.disconnect(self._load_finished)
        except (RuntimeError, TypeError):
            pass
