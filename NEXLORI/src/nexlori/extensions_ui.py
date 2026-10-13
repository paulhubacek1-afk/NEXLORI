"""MV3 browser add-on manager for Nexlori's Qt WebEngine profile."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .extension_utils import (
    ExtensionPackageError,
    extension_key_from_name,
    extension_name_from_info,
    inspect_extension_package,
    is_builtin_extension,
  )

_MORE_ADDON_SOURCES = (
    ("Dark Reader", "https://github.com/darkreader/darkreader/releases"),
    ("SponsorBlock", "https://github.com/ajayyy/SponsorBlock/releases"),
    ("ClearURLs", "https://github.com/ClearURLs/Addon/releases"),
)


class ExtensionsDialog(QDialog):
    """Enable, disable, remove and import trusted-by-user Manifest V3 packages."""

    def __init__(self, owner, parent=None):
        super().__init__(parent or owner)
        self.owner = owner
        self.manager = owner.extension_manager
        self.setWindowTitle("Nexlori · Add-ons")
        self.resize(760, 520)
        root = QVBoxLayout(self)

        intro = QLabel(
            "uBlock Origin Lite ist in Nexlori enthalten und standardmäßig aktiviert. "
            "Weitere Chrome-kompatible Erweiterungen können als Manifest-V3-ZIP oder entpackter Ordner "
            "installiert werden. Prüfe Herausgeber und Berechtigungen vor jeder Installation.",
            self,
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Add-on", "Version", "Status", "Aktiv"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(3, False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 220)
        self.table.setColumnWidth(3, 70)
        root.addWidget(self.table, 1)

        row1 = QHBoxLayout()
        install_zip = QPushButton("ZIP installieren …", self)
        install_zip.clicked.connect(self.install_zip)
        install_folder = QPushButton("Ordner installieren …", self)
        install_folder.clicked.connect(self.install_folder)
        self.remove_button = QPushButton("Add-on entfernen", self)
        self.remove_button.clicked.connect(self.remove_selected)
        refresh_button = QPushButton("Aktualisieren", self)
        refresh_button.clicked.connect(self.refresh)
        for button in (install_zip, install_folder, self.remove_button, refresh_button):
            row1.addWidget(button)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        sources = QPushButton("Weitere Add-on-Projekte öffnen", self)
        sources.clicked.connect(self.open_sources)
        close = QPushButton("Schließen", self)
        close.clicked.connect(self.accept)
        row2.addWidget(sources)
        row2.addStretch(1)
        row2.addWidget(close)
        root.addLayout(row2)

        self.manager.installFinished.connect(lambda *_: self.refresh())
        self.manager.uninstallFinished.connect(lambda *_: self.refresh())
        self.manager.loadFinished.connect(lambda *_: self.refresh())
        self.manager.unloadFinished.connect(lambda *_: self.refresh())
        self.refresh()

    def _extensions(self) -> list[Any]:
        try:
            return [extension for extension in self.manager.extensions()
                    if not is_builtin_extension(extension_name_from_info(extension))]
        except (AttributeError, RuntimeError):
            return []

    def refresh(self) -> None:
        extensions = self._extensions()
        self.table.setRowCount(len(extensions))
        for row, extension in enumerate(extensions):
            name = extension_name_from_info(extension)
            version = self._version(extension)
            loaded = bool(extension.isLoaded())
            enabled = bool(extension.isEnabled())
            error = str(extension.error() or "")
            state = (
                "Aktiv" if enabled else
                ("Deaktiviert" if loaded else "Nicht geladen")
            )
            if error:
                state = "Fehler: " + error[:120]
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, str(extension.id()))
            name_item.setToolTip(str(extension.description() or name))
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(version))
            self.table.setItem(row, 2, QTableWidgetItem(state))
            checkbox = QCheckBox(self.table)
            checkbox.setChecked(enabled)
            checkbox.setEnabled(loaded and not error)
            checkbox.setToolTip("Diese Erweiterung aktivieren oder deaktivieren")
            checkbox.toggled.connect(
                lambda checked, extension_id=str(extension.id()): self._toggle(extension_id, checked)
            )
            cell = QHBoxLayout()
            cell.setContentsMargins(0, 0, 0, 0)
            cell.addStretch(1)
            cell.addWidget(checkbox)
            cell.addStretch(1)
            host = self.table.cellWidget(row, 3)
            if host is not None:
                host.deleteLater()
            from PySide6.QtWidgets import QWidget
            cell_host = QWidget(self.table)
            cell_host.setLayout(cell)
            self.table.setCellWidget(row, 3, cell_host)
        self.table.resizeRowsToContents()
        self.remove_button.setEnabled(bool(extensions))

    @staticmethod
    def _version(extension: Any) -> str:
        # ExtensionInfo intentionally does not expose the manifest's version on every Qt patch.
        try:
            path = Path(str(extension.path()))
            manifest_path = path / "manifest.json"
            if manifest_path.is_file():
                import json
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                return str(manifest.get("version") or "–")
        except (OSError, ValueError, TypeError):
            pass
        return "–"

    def _find(self, extension_id: str):
        return next((x for x in self._extensions() if str(x.id()) == extension_id), None)

    def _toggle(self, extension_id: str, enabled: bool) -> None:
        extension = self._find(extension_id)
        if extension is None:
            self.refresh()
            return
        try:
            self.owner.set_extension_enabled(extension, enabled)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Add-on", f"Der Status konnte nicht geändert werden: {exc}")
        self.refresh()

    def _install_path(self, path: str) -> None:
        if not path:
            return
        try:
            details = inspect_extension_package(path)
        except ExtensionPackageError as exc:
            QMessageBox.warning(self, "Add-on nicht unterstützt", str(exc))
            return
        permissions = details.get("permissions") or []
        permission_text = ", ".join(permissions[:25]) if permissions else "Keine expliziten Berechtigungen im Manifest angegeben"
        if len(permissions) > 25:
            permission_text += f" … und {len(permissions) - 25} weitere"
        warning = (
            f"Add-on: {details['name']}\nVersion: {details.get('version') or 'unbekannt'}\n\n"
            f"Angeforderte Berechtigungen: {permission_text}\n\n"
            "Browser-Erweiterungen können Inhalte der von dir geöffneten Websites lesen oder verändern. "
            "Installiere nur Add-ons aus Quellen, denen du vertraust. Soll die Installation fortgesetzt werden?"
        )
        if QMessageBox.question(
            self, "Add-on-Berechtigungen prüfen", warning,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.manager.installExtension(str(Path(path).resolve()))
            self.owner.statusBar().showMessage(f"Installation gestartet: {details['name']}", 4000)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Installation fehlgeschlagen", str(exc))

    def install_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chrome-kompatibles MV3-Add-on auswählen", str(Path.home() / "Downloads"),
            "Extension-ZIP (*.zip)",
        )
        self._install_path(path)

    def install_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Entpackten Add-on-Ordner auswählen", str(Path.home() / "Downloads")
        )
        self._install_path(path)

    def _selected_extension(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Add-on auswählen", "Wähle zuerst ein Add-on aus.")
            return None
        item = self.table.item(rows[0].row(), 0)
        return self._find(str(item.data(Qt.ItemDataRole.UserRole)))

    def remove_selected(self) -> None:
        extension = self._selected_extension()
        if extension is None:
            return
        name = str(extension.name() or "dieses Add-on")
        key = extension_key_from_name(name)
        if key == "ublock-origin-lite":
            QMessageBox.information(
                self, "uBlock Origin Lite",
                "uBlock Origin Lite gehört zur Nexlori-Standardausstattung. Du kannst es hier deaktivieren, "
                "aber nicht versehentlich aus der Installation entfernen.",
            )
            return
        if QMessageBox.question(
            self, "Add-on entfernen",
            f"„{name}“ aus Nexlori entfernen? Das Add-on wird nicht gelöscht, falls andere Programme dieselben Dateien verwenden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.manager.uninstallExtension(extension)
            self.owner.settings.extensions_enabled.pop(key, None)
            self.owner._save_settings()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Add-on", f"Das Add-on konnte nicht entfernt werden: {exc}")

    def open_sources(self) -> None:
        text = (
            "Wähle eine offizielle Projektseite. Nicht jede dort angebotene Datei ist ein Qt-kompatibles "
            "Manifest-V3-Paket. Importiere nur ZIPs, deren manifest.json auf oberster Ebene liegt."
        )
        QMessageBox.information(self, "Weitere Add-ons", text)
        menu = QMenu(self)
        for name, url in _MORE_ADDON_SOURCES:
            action = menu.addAction(f"{name} – offizielle Releases")
            action.triggered.connect(lambda _checked=False, target=url: QDesktopServices.openUrl(QUrl(target)))
        menu.exec(self.mapToGlobal(self.rect().center()))
