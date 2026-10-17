"""Theme-Shop-Oberfläche: Themes ansehen, installieren, anwenden und wieder entfernen."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .core.theme_shop import ShopError, ShopTheme, ThemeStore, fetch_catalog
from .core.themes import Theme


def swatch_pixmap(theme: Theme, width: int = 56, height: int = 32) -> QPixmap:
    """Kleine Farbvorschau: Hintergrund, Streifen und Akzent."""
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(theme.bg))
    painter = QPainter(pixmap)
    colors = list(theme.stripes) or [theme.accent]
    band = height // 3
    step = width / len(colors)
    for index, color in enumerate(colors):
        painter.fillRect(QRect(round(index * step), 0, round(step) + 1, band), QColor(color))
    painter.fillRect(QRect(0, band, width, height - band), QColor(theme.surface))
    painter.setBrush(QColor(theme.accent))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRect(6, band + 6, width // 2, 6), 3, 3)
    painter.setBrush(QColor(theme.fg))
    painter.drawRoundedRect(QRect(6, band + 16, width - 18, 4), 2, 2)
    painter.setPen(QPen(QColor(theme.accent), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(0, 0, width - 1, height - 1)
    painter.end()
    return pixmap


class ThemePreview(QWidget):
    """Mini-Browser in den Farben des gewählten Themes."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._theme: Theme | None = None
        self.setMinimumSize(300, 190)

    def set_theme(self, theme: Theme | None) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self._theme
        if theme is None:
            painter.setPen(self.palette().text().color())
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Wähle links ein Theme aus")
            painter.end()
            return
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(theme.bg))
        title_h = 24
        painter.fillRect(0, 0, w, title_h, QColor(theme.surface))
        painter.setPen(QColor(theme.fg))
        painter.drawText(QRect(10, 0, w - 90, title_h), Qt.AlignmentFlag.AlignVCenter, "Nexlori")
        for index, label in enumerate(("–", "☐", "✕")):
            painter.drawText(QRect(w - 78 + index * 26, 0, 26, title_h), Qt.AlignmentFlag.AlignCenter, label)
        colors = list(theme.stripes) or [theme.accent, theme.accent]
        line_h = 4
        step = w / len(colors)
        for index, color in enumerate(colors):
            painter.fillRect(QRect(round(index * step), title_h, round(step) + 1, line_h), QColor(color))
        tab_y = title_h + line_h
        painter.fillRect(0, tab_y, w, 26, QColor(theme.surface))
        painter.fillRect(10, tab_y + 5, 110, 21, QColor(theme.bg))
        painter.fillRect(10, tab_y + 24, 110, 2, QColor(theme.accent))
        painter.setPen(QColor(theme.fg))
        painter.drawText(QRect(18, tab_y + 5, 100, 19), Qt.AlignmentFlag.AlignVCenter, "Startseite")
        bar_y = tab_y + 26
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.surface))
        painter.drawRoundedRect(QRect(w // 2 - 120, bar_y + 6, 240, 22), 11, 11)
        painter.setBrush(QColor(theme.accent))
        painter.drawEllipse(QRect(w // 2 - 110, bar_y + 13, 8, 8))
        painter.setPen(QColor(theme.fg))
        painter.drawText(QRect(w // 2 - 96, bar_y + 6, 210, 22), Qt.AlignmentFlag.AlignVCenter, "Suchen oder Webadresse eingeben")
        body_y = bar_y + 36
        painter.setPen(QColor(theme.fg))
        painter.drawText(QRect(16, body_y + 6, w - 32, 22), Qt.AlignmentFlag.AlignVCenter, theme.label)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.surface))
        painter.drawRoundedRect(QRect(16, body_y + 34, w - 32, 22), 6, 6)
        painter.drawRoundedRect(QRect(16, body_y + 62, (w - 32) * 3 // 5, 14), 6, 6)
        painter.setBrush(QColor(theme.accent))
        painter.drawRoundedRect(QRect(16, body_y + 88, 96, 26), 13, 13)
        painter.setPen(QColor(theme.bg))
        painter.drawText(QRect(16, body_y + 88, 96, 26), Qt.AlignmentFlag.AlignCenter, "Akzent")
        painter.end()


class CatalogWorker(QThread):
    """Lädt den Katalog im Hintergrund, damit die Oberfläche nicht einfriert."""

    loaded = Signal(object, int)
    failed = Signal(str)

    def run(self) -> None:
        try:
            themes, skipped = fetch_catalog()
        except ShopError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unerwarteter Fehler: {exc}")
        else:
            self.loaded.emit(themes, skipped)


class ThemeShopDialog(QDialog):
    def __init__(self, owner, parent=None):
        super().__init__(parent or owner)
        self.owner = owner
        self.store: ThemeStore = owner.theme_store
        self.items: dict[str, ShopTheme] = {}
        self._worker: CatalogWorker | None = None
        self.setWindowTitle("Nexlori · Theme-Shop")
        self.resize(860, 560)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Im Theme-Shop findest du zusätzliche Themes. Sie werden erst bei der Installation auf dein Gerät "
            "geladen und lassen sich jederzeit wieder entfernen. Ein Theme besteht nur aus Farben – es wird kein Code geladen.",
            self,
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        filters = QHBoxLayout()
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Themes suchen …")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        self.category = QComboBox(self)
        self.category.addItem("Alle Kategorien", "")
        self.category.currentIndexChanged.connect(self._apply_filter)
        self.only_installed = QComboBox(self)
        self.only_installed.addItems(["Alle", "Installiert", "Nicht installiert"])
        self.only_installed.currentIndexChanged.connect(self._apply_filter)
        self.refresh_button = QPushButton("Aktualisieren", self)
        self.refresh_button.clicked.connect(self.load_catalog)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.category)
        filters.addWidget(self.only_installed)
        filters.addWidget(self.refresh_button)
        root.addLayout(filters)

        body = QHBoxLayout()
        self.list = QListWidget(self)
        self.list.setIconSize(QSize(56, 32))
        self.list.setMinimumWidth(300)
        self.list.currentItemChanged.connect(self._selection_changed)
        self.list.itemDoubleClicked.connect(lambda _item: self._primary_action())
        body.addWidget(self.list, 2)

        side = QVBoxLayout()
        self.preview = ThemePreview(self)
        side.addWidget(self.preview, 1)
        self.title_label = QLabel("", self)
        self.title_label.setStyleSheet("font-size:16px;font-weight:600;")
        self.info_label = QLabel("", self)
        self.info_label.setWordWrap(True)
        side.addWidget(self.title_label)
        side.addWidget(self.info_label)
        buttons = QHBoxLayout()
        self.install_button = QPushButton("Installieren", self)
        self.install_button.clicked.connect(self.install_selected)
        self.apply_button = QPushButton("Anwenden", self)
        self.apply_button.clicked.connect(self.apply_selected)
        self.remove_button = QPushButton("Entfernen", self)
        self.remove_button.clicked.connect(self.remove_selected)
        for button in (self.install_button, self.apply_button, self.remove_button):
            buttons.addWidget(button)
        side.addLayout(buttons)
        body.addLayout(side, 3)
        root.addLayout(body, 1)

        self.status = QLabel("", self)
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close = QPushButton("Schließen", self)
        close.clicked.connect(self.accept)
        close_row.addWidget(close)
        root.addLayout(close_row)

        self._rebuild_items()
        self.load_catalog()

    # ------------------------------------------------------------------ Daten
    def load_catalog(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.refresh_button.setEnabled(False)
        self.status.setText("Katalog wird geladen …")
        worker = CatalogWorker(self.owner)  # Eltern = Hauptfenster: der Thread überlebt ein geschlossenes Dialogfenster
        worker.loaded.connect(self._catalog_loaded)
        worker.failed.connect(self._catalog_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _catalog_loaded(self, themes: list, skipped: int) -> None:
        self._worker = None
        self.refresh_button.setEnabled(True)
        self.items = {item.name: item for item in themes}
        categories = sorted({item.category for item in themes})
        self.category.blockSignals(True)
        current = self.category.currentData()
        self.category.clear()
        self.category.addItem("Alle Kategorien", "")
        for name in categories:
            self.category.addItem(name, name)
        index = self.category.findData(current)
        self.category.setCurrentIndex(max(0, index))
        self.category.blockSignals(False)
        note = f" ({skipped} ungültige Einträge übersprungen)" if skipped else ""
        self.status.setText(f"{len(themes)} Themes im Shop{note}.")
        self._rebuild_items()

    def _catalog_failed(self, message: str) -> None:
        self._worker = None
        self.refresh_button.setEnabled(True)
        self.status.setText(message + " Bereits installierte Themes stehen weiterhin zur Verfügung.")
        self._rebuild_items()

    def _rebuild_items(self) -> None:
        installed = self.store.installed()
        selected = self.current_name()
        entries: dict[str, ShopTheme] = dict(self.items)
        for name, (theme, rev) in installed.items():
            entries.setdefault(name, ShopTheme(theme=theme, category="Installiert", author="–", rev=rev))
        self._entries = entries
        self.list.blockSignals(True)
        self.list.clear()
        needle = self.search.text().strip().lower()
        category = self.category.currentData() or ""
        mode = self.only_installed.currentIndex()
        for name in sorted(entries, key=lambda n: (entries[n].category, entries[n].theme.label.lower())):
            item = entries[name]
            is_installed = name in installed
            if needle and needle not in item.theme.label.lower() and needle not in item.category.lower():
                continue
            if category and item.category != category:
                continue
            if mode == 1 and not is_installed:
                continue
            if mode == 2 and is_installed:
                continue
            suffix = ""
            if is_installed:
                suffix = "  ·  Update verfügbar" if installed[name][1] < item.rev else "  ·  installiert"
            row = QListWidgetItem(QIcon(swatch_pixmap(item.theme)), f"{item.theme.label}{suffix}\n{item.category}")
            row.setData(Qt.ItemDataRole.UserRole, name)
            self.list.addItem(row)
            if name == selected:
                self.list.setCurrentItem(row)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._selection_changed()

    def _apply_filter(self, *_args) -> None:
        self._rebuild_items()

    def current_name(self) -> str:
        row = self.list.currentItem()
        return str(row.data(Qt.ItemDataRole.UserRole)) if row is not None else ""

    # ------------------------------------------------------------------ Auswahl & Aktionen
    def _selection_changed(self, *_args) -> None:
        name = self.current_name()
        item = self._entries.get(name) if hasattr(self, "_entries") else None
        installed = self.store.installed()
        self.preview.set_theme(item.theme if item else None)
        if item is None:
            self.title_label.setText("")
            self.info_label.setText("")
            for button in (self.install_button, self.apply_button, self.remove_button):
                button.setEnabled(False)
            return
        is_installed = name in installed
        update = is_installed and installed[name][1] < item.rev and name in self.items
        self.title_label.setText(item.theme.label)
        details = [f"Kategorie: {item.category}", f"von {item.author}"]
        self.info_label.setText(" · ".join(details) + (f"\n{item.description}" if item.description else ""))
        self.install_button.setText("Aktualisieren" if update else "Installieren")
        self.install_button.setEnabled(name in self.items and (not is_installed or update))
        self.apply_button.setEnabled(is_installed)
        self.remove_button.setEnabled(is_installed)

    def _primary_action(self) -> None:
        if self.install_button.isEnabled():
            self.install_selected()
        elif self.apply_button.isEnabled():
            self.apply_selected()

    def install_selected(self) -> None:
        name = self.current_name()
        item = self.items.get(name)
        if item is None:
            return
        try:
            self.store.install(item)
        except ShopError as exc:
            QMessageBox.warning(self, "Theme-Shop", str(exc))
            return
        self.owner.rebuild_theme_menu()
        self.status.setText(f"„{item.theme.label}“ wurde installiert.")
        self._rebuild_items()

    def apply_selected(self) -> None:
        name = self.current_name()
        if name in self.store.installed():
            self.owner.set_theme(name)
            self.status.setText(f"Theme „{self._entries[name].theme.label}“ ist jetzt aktiv.")

    def remove_selected(self) -> None:
        name = self.current_name()
        if name not in self.store.installed():
            return
        label = self._entries[name].theme.label
        answer = QMessageBox.question(
            self, "Theme entfernen",
            f"„{label}“ von diesem Gerät entfernen? Du kannst es später erneut aus dem Shop laden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.owner.remove_installed_theme(name)
        except ShopError as exc:
            QMessageBox.warning(self, "Theme-Shop", str(exc))
            return
        self.status.setText(f"„{label}“ wurde entfernt.")
        self._rebuild_items()
