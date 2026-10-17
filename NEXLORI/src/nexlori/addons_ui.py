"""Add-on-Zentrale: eingebaute Nexlori-Add-ons und Zugang zu Browser-Erweiterungen (Manifest V3)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .core.builtin_addons import ADDONS, is_enabled

_KIND_LABEL = {
    "script": "Wirkt auf Webseiten",
    "engine": "Arbeitet im Browser",
    "action": "Befehl im Menü „Werkzeuge“",
}


class AddonsDialog(QDialog):
    def __init__(self, owner, parent=None):
        super().__init__(parent or owner)
        self.owner = owner
        self.setWindowTitle("Nexlori · Add-ons")
        self.resize(720, 600)
        root = QVBoxLayout(self)
        tabs = QTabWidget(self)
        root.addWidget(tabs, 1)
        tabs.addTab(self._builtin_tab(), "Nexlori-Add-ons")
        tabs.addTab(self._extensions_tab(), "Browser-Erweiterungen")

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close = QPushButton("Schließen", self)
        close.clicked.connect(self.accept)
        close_row.addWidget(close)
        root.addLayout(close_row)

    def _builtin_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        intro = QLabel(
            "Diese Add-ons sind fest in Nexlori eingebaut. Sie laufen vollständig auf deinem Gerät, "
            "senden keine Daten und brauchen keine Installation. Änderungen wirken sofort; "
            "bei geöffneten Seiten genügt einmal Neuladen.",
            page,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(scroll)
        column = QVBoxLayout(inner)
        column.setContentsMargins(0, 6, 8, 6)
        column.setSpacing(12)
        self.checks: dict[str, QCheckBox] = {}
        for addon in ADDONS:
            box = QCheckBox(addon.label, inner)
            box.setStyleSheet("font-weight:600;")
            box.setChecked(is_enabled(self.owner.settings.builtin_addons, addon.id))
            box.toggled.connect(lambda checked, aid=addon.id: self.owner.set_builtin_addon(aid, checked))
            self.checks[addon.id] = box
            description = QLabel(addon.description, inner)
            description.setWordWrap(True)
            description.setContentsMargins(26, 0, 0, 0)
            meta = _KIND_LABEL[addon.kind] + (f"  ·  {addon.hint}" if addon.hint else "")
            meta_label = QLabel(meta, inner)
            meta_label.setContentsMargins(26, 0, 0, 0)
            meta_label.setEnabled(False)
            column.addWidget(box)
            column.addWidget(description)
            column.addWidget(meta_label)
            if addon.id == "tab-sleep":
                row = QHBoxLayout()
                row.setContentsMargins(26, 0, 0, 0)
                row.addWidget(QLabel("Schlafen legen nach", inner))
                minutes = QSpinBox(inner)
                minutes.setRange(2, 240)
                minutes.setSuffix(" Minuten")
                minutes.setValue(int(self.owner.settings.tab_sleep_minutes))
                minutes.valueChanged.connect(self.owner.set_tab_sleep_minutes)
                row.addWidget(minutes)
                row.addStretch(1)
                column.addLayout(row)
        column.addStretch(1)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)
        return page

    def _extensions_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        text = QLabel(
            "Zusätzlich zu den eingebauten Add-ons kann Nexlori Chrome-kompatible Erweiterungen "
            "(Manifest V3) verwenden – zum Beispiel uBlock Origin Lite, das bereits enthalten ist. "
            "Installiere nur Erweiterungen aus Quellen, denen du vertraust.",
            page,
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        button = QPushButton("Browser-Erweiterungen verwalten …", page)
        button.setEnabled(getattr(self.owner, "extension_manager", None) is not None)
        button.clicked.connect(self.owner.show_extensions_manager)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        if not button.isEnabled():
            layout.addWidget(QLabel("Erweiterungen erfordern Qt WebEngine 6.10 oder neuer.", page))
        layout.addStretch(1)
        return page
