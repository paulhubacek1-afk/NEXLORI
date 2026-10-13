"""A compact Spotify popup using Nexlori's shared Chromium profile."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from PySide6.QtCore import QPoint, QUrl, Qt
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
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView


_SPOTIFY_TYPES = {"track", "album", "playlist", "episode", "show", "artist"}


def normalize_spotify_url(value: str) -> str:
    value = value.strip()
    if not value:
        return "https://open.spotify.com/"
    if not re.match(r"^https://", value, re.IGNORECASE):
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme.lower() != "https" or (parts.hostname or "").lower() not in {
        "open.spotify.com", "www.open.spotify.com"
    }:
        raise ValueError("Bitte einen Link von https://open.spotify.com einfügen.")
    path = parts.path.rstrip("/")
    segments = [segment for segment in path.split("/") if segment]
    if segments and segments[0] == "embed":
        if len(segments) < 2 or segments[1] not in _SPOTIFY_TYPES:
            raise ValueError("Dieser Spotify-Einbettungstyp wird nicht unterstützt.")
        return f"https://open.spotify.com{path}"
    if len(segments) >= 2 and segments[0] in _SPOTIFY_TYPES:
        kind, item_id = segments[0], segments[1]
        if not re.fullmatch(r"[A-Za-z0-9]{10,64}", item_id):
            raise ValueError("Der Spotify-Link enthält keine gültige Inhalts-ID.")
        return f"https://open.spotify.com/embed/{kind}/{item_id}?utm_source=generator"
    return "https://open.spotify.com/"


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
        self.view.setPage(QWebEnginePage(profile, self.view))
        self.view.settings().setAttribute(
            self.view.settings().WebAttribute.JavascriptEnabled, True
        )
        self.view.load(QUrl("https://open.spotify.com/"))
        root.addWidget(self.view, 1)

        self.status = QLabel("Tipp: Füge einen Spotify-Track- oder Playlist-Link ein.", self)
        self.status.setWordWrap(True)
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
        self.view.loadFinished.connect(self._load_finished)

    def _load_finished(self, ok: bool) -> None:
        self.status.setText(
            "Spotify-Inhalt geladen." if ok else
            "Spotify konnte den Inhalt nicht laden. Prüfe den Link, die Anmeldung oder die Netzwerkverbindung."
        )
        try:
            self.view.loadFinished.disconnect(self._load_finished)
        except (RuntimeError, TypeError):
            pass
