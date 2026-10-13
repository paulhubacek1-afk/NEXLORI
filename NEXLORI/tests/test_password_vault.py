import json

import pytest

from nexlori.password_vault import PasswordVault, VaultError, generate_password


def test_vault_encrypts_entries_and_roundtrips(tmp_path):
    path = tmp_path / "vault.json"
    vault = PasswordVault(path)
    vault.create("A-long-test-passphrase-2026!")
    vault.add_entry("https://example.com", "elias@example.com", "s3cret-password", "private note")

    raw = path.read_text(encoding="utf-8")
    assert "s3cret-password" not in raw
    assert "elias@example.com" not in raw
    assert "private note" not in raw
    assert json.loads(raw)["version"] == 1

    reopened = PasswordVault(path)
    reopened.unlock("A-long-test-passphrase-2026!")
    entries = reopened.entries()
    assert len(entries) == 1
    assert entries[0]["site"] == "https://example.com"
    assert entries[0]["username"] == "elias@example.com"
    assert entries[0]["password"] == "s3cret-password"
    assert entries[0]["notes"] == "private note"


def test_wrong_master_password_is_rejected(tmp_path):
    path = tmp_path / "vault.json"
    PasswordVault(path).create("correct-horse-battery-staple")
    reopened = PasswordVault(path)
    with pytest.raises(VaultError, match="falsch"):
        reopened.unlock("incorrect-master-passphrase")
    assert not reopened.unlocked


def test_vault_requires_unlock_and_prevents_duplicate_creation(tmp_path):
    path = tmp_path / "vault.json"
    vault = PasswordVault(path)
    with pytest.raises(VaultError, match="gesperrt"):
        vault.entries()
    vault.create("A-long-test-passphrase-2026!")
    with pytest.raises(VaultError, match="bereits"):
        vault.create("another-long-master-password")


def test_vault_delete_entry_and_lock(tmp_path):
    path = tmp_path / "vault.json"
    vault = PasswordVault(path)
    vault.create("A-long-test-passphrase-2026!")
    entry_id = vault.add_entry("example.com", "user", "password")
    assert vault.delete_entry(entry_id)
    assert vault.entries() == []
    assert not vault.delete_entry("missing")
    vault.lock()
    assert not vault.unlocked
    with pytest.raises(VaultError):
        vault.entries()


def test_password_generator_has_reasonable_length_and_variety():
    password = generate_password(32)
    assert len(password) == 32
    assert any(c.islower() for c in password)
    assert any(c.isupper() for c in password)
    assert any(c.isdigit() for c in password)
    assert any(not c.isalnum() for c in password)
    with pytest.raises(ValueError):
        generate_password(5)
