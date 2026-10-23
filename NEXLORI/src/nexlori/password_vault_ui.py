"""Password manager dialogs for Nexlori. Secrets are only shown after vault unlock."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .password_vault import PasswordVault, VaultError, generate_password


class EntryDialog(QDialog):
    def __init__(self, parent=None, *, default_site: str = "", default_username: str = "", default_password: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Passwort speichern")
        self.setMinimumWidth(460)
        form = QFormLayout(self)

        self.site = QLineEdit(default_site, self)
        self.username = QLineEdit(default_username, self)
        self.password = QLineEdit(default_password, self)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        show_password = QCheckBox("Passwort anzeigen", self)
        show_password.toggled.connect(
            lambda checked: self.password.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        password_row = QHBoxLayout()
        password_row.addWidget(self.password, 1)
        generate = QPushButton("Generieren", self)
        generate.clicked.connect(lambda: self.password.setText(generate_password()))
        password_row.addWidget(generate)
        password_widget = QWidget(self)
        password_widget.setLayout(password_row)

        self.notes = QLineEdit(self)
        self.notes.setPlaceholderText("Optional")
        form.addRow("Website / App", self.site)
        form.addRow("Benutzername / E-Mail", self.username)
        form.addRow("Passwort", password_widget)
        form.addRow("", show_password)
        form.addRow("Notiz", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _accept_if_valid(self) -> None:
        if not self.site.text().strip() or not self.username.text().strip() or not self.password.text():
            QMessageBox.warning(self, "Felder fehlen", "Website, Benutzername und Passwort sind Pflichtfelder.")
            return
        self.accept()

    def value(self) -> dict[str, str]:
        return {
            "site": self.site.text().strip(),
            "username": self.username.text().strip(),
            "password": self.password.text(),
            "notes": self.notes.text().strip(),
        }


def _open_vault(parent, path: Path) -> PasswordVault | None:
    vault = PasswordVault(path)
    if not vault.initialized:
        master, ok = QInputDialog.getText(
            parent,
            "Passwort-Tresor einrichten",
            "Neue Master-Passphrase (mindestens 12 Zeichen):",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None
        confirm, ok = QInputDialog.getText(
            parent,
            "Master-Passphrase bestätigen",
            "Master-Passphrase erneut eingeben:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None
        if master != confirm:
            QMessageBox.warning(parent, "Passphrase", "Die beiden Eingaben stimmen nicht überein.")
            return None
        try:
            vault.create(master)
        except (VaultError, OSError) as exc:
            QMessageBox.warning(parent, "Tresor", str(exc))
            return None
        QMessageBox.information(
            parent,
            "Tresor erstellt",
            "Dein Tresor wurde verschlüsselt gespeichert. Vergiss die Master-Passphrase nicht: "
            "Sie lässt sich nicht zurücksetzen und Nexlori kann den Tresor ohne sie nicht öffnen.",
        )
        return vault

    for _attempt in range(3):
        master, ok = QInputDialog.getText(
            parent,
            "Passwort-Tresor entsperren",
            "Master-Passphrase eingeben:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return None
        try:
            vault.unlock(master)
            return vault
        except VaultError as exc:
            QMessageBox.warning(parent, "Tresor gesperrt", str(exc))
    return None


class PasswordVaultDialog(QDialog):
    def __init__(self, vault: PasswordVault, parent=None, default_site: str = ""):
        super().__init__(parent)
        self.vault = vault
        self.default_site = default_site
        self.setWindowTitle("Nexlori · Passwortmanager")
        self.resize(760, 450)
        root = QVBoxLayout(self)
        info = QLabel(
            "Lokal verschlüsselt · Passwörter werden nicht automatisch in Websites eingefügt. "
            "Wähle einen Eintrag, um Benutzernamen oder Passwort in die Zwischenablage zu kopieren.",
            self,
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Website / App", "Benutzername", "ID"])
        self.table.setColumnHidden(2, True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        add = QPushButton("＋ Eintrag", self)
        add.clicked.connect(self.add_entry)
        copy_user = QPushButton("Benutzername kopieren", self)
        copy_user.clicked.connect(self.copy_username)
        copy_pass = QPushButton("Passwort kopieren", self)
        copy_pass.clicked.connect(self.copy_password)
        delete = QPushButton("Löschen", self)
        delete.clicked.connect(self.delete_entry)
        close = QPushButton("Sperren und schließen", self)
        close.clicked.connect(self.accept)
        for button in (add, copy_user, copy_pass, delete, close):
            buttons.addWidget(button)
        root.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        entries = self.vault.entries()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry.get("site", "")))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("username", "")))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("id", "")))
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def _selected_entry(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Eintrag auswählen", "Wähle zuerst einen Eintrag aus.")
            return None
        entry_id = self.table.item(rows[0].row(), 2).text()
        return next((x for x in self.vault.entries() if x.get("id") == entry_id), None)

    def add_entry(self) -> None:
        dialog = EntryDialog(self, default_site=self.default_site)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.vault.add_entry(**dialog.value())
        except (VaultError, OSError) as exc:
            QMessageBox.warning(self, "Eintrag konnte nicht gespeichert werden", str(exc))
            return
        self.refresh()

    def copy_username(self) -> None:
        entry = self._selected_entry()
        if entry:
            self._copy_secret(entry.get("username", ""), "Benutzername")

    def copy_password(self) -> None:
        entry = self._selected_entry()
        if entry:
            self._copy_secret(entry.get("password", ""), "Passwort")

    def _copy_secret(self, value: str, label: str) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(value)
        QMessageBox.information(self, "Kopiert", f"{label} wurde kopiert. Die Zwischenablage wird nach 30 Sekunden geleert, sofern du sie nicht inzwischen geändert hast.")
        def clear_if_unchanged() -> None:
            if clipboard.text() == value:
                clipboard.clear()
        QTimer.singleShot(30_000, clear_if_unchanged)

    def delete_entry(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        confirm = QMessageBox.question(
            self, "Eintrag löschen",
            f"Den Eintrag für {entry.get('site', 'diese Website')} unwiderruflich löschen?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.vault.delete_entry(entry["id"])
        except (VaultError, OSError) as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        self.refresh()


def save_login_credentials(parent, path: str | Path, *, site: str, username: str, password: str) -> bool:
    """Offer a form-submitted login for the encrypted vault; never save without explicit confirmation."""
    vault = _open_vault(parent, Path(path))
    if vault is None:
        return False
    try:
        dialog = EntryDialog(
            parent, default_site=site, default_username=username, default_password=password
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        try:
            vault.add_entry(**dialog.value())
        except (VaultError, OSError) as exc:
            QMessageBox.warning(parent, "Passwort konnte nicht gespeichert werden", str(exc))
            return False
        QMessageBox.information(parent, "Passwort gespeichert", "Die Zugangsdaten wurden verschlüsselt in deinem lokalen Nexlori-Tresor gespeichert.")
        return True
    finally:
        vault.lock()


def open_password_manager(parent, path: str | Path, *, default_site: str = "") -> None:
    vault = _open_vault(parent, Path(path))
    if vault is None:
        return
    dialog = PasswordVaultDialog(vault, parent, default_site=default_site)
    try:
        dialog.exec()
    finally:
        vault.lock()
