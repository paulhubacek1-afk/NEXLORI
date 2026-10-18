"""A compact Spotify popup using Nexlori's shared Chromium profile."""
from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
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

        self.view = QWebEngineView(self)
        page = QWebEnginePage(profile, self.view)
        self.view.setPage(page)
        page_settings = self.view.settings()
        page_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        page_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        page_settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        page_settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        try:
            page.setAudioMuted(False)
        except AttributeError:
            pass  # ältere Qt-Versionen erlauben die Audio-Stummschaltung nicht explizit
        self.status = QLabel(
            "Melde dich bei Spotify an und starte die Wiedergabe direkt im Player. "
            "Bei fehlendem Ton auch den Windows-Lautstärkemixer prüfen.", self
        )
        self.status.setWordWrap(True)
        try:
            page.recentlyAudibleChanged.connect(self._audio_state_changed)
        except AttributeError:
            pass
        self.view.loadFinished.connect(self._load_finished)
        self.view.load(QUrl("https://open.spotify.com/"))
        root.addWidget(self.view, 1)
        root.addWidget(self.status)

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
        self.view.setUrl(QUrl(target))

    def _load_finished(self, ok: bool) -> None:
        self.status.setText(
            "Spotify-Seite geladen. Starte die Wiedergabe direkt in Spotify; bei fehlendem Ton den "
            "Windows-Lautstärkemixer prüfen." if ok else
            "Spotify konnte den Inhalt nicht laden. Prüfe den Link, die Anmeldung oder die Netzwerkverbindung."
        )
        if ok:
            try:
                self.view.page().setAudioMuted(False)
            except AttributeError:
                pass

    def _audio_state_changed(self, audible: bool) -> None:
        if audible:
            self.status.setText("Spotify gibt Audio wieder.")
        elif self.view.url().host() == "open.spotify.com":
            self.status.setText("Wiedergabe starten. Wenn kein Ton kommt, den Windows-Lautstärkemixer prüfen.")
