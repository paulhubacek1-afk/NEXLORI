"""Encrypted local password vault. Master passwords are never written to disk."""
from __future__ import annotations

import base64
import json
import os
import secrets
import string
import tempfile
import uuid
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_FORMAT_VERSION = 1
_KDF_ITERATIONS = 600_000
_MAX_VAULT_BYTES = 5 * 1024 * 1024


class VaultError(ValueError):
    """A vault is invalid, locked, or could not be decrypted."""


def derive_key(master_password: str, salt: bytes) -> bytes:
    if not isinstance(master_password, str) or len(master_password) < 12:
        raise VaultError("Die Master-Passphrase muss mindestens 12 Zeichen lang sein.")
    if len(salt) < 16:
        raise VaultError("Der Tresor-Salt ist ungültig.")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=_KDF_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))


def generate_password(length: int = 20) -> str:
    if not 12 <= length <= 128:
        raise ValueError("Die Passwortlänge muss zwischen 12 und 128 liegen.")
    groups = (string.ascii_lowercase, string.ascii_uppercase, string.digits, "!@#$%&*+-_=.?")
    chars = [secrets.choice(group) for group in groups]
    alphabet = "".join(groups)
    chars.extend(secrets.choice(alphabet) for _ in range(length - len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


class PasswordVault:
    """Encrypted vault session: encrypted file plus a key retained only in memory."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._key: bytes | None = None
        self._salt: bytes | None = None
        self._entries: list[dict[str, Any]] = []
        self._token: bytes | None = None
        if self.path.exists():
            self._read_header()

    @property
    def initialized(self) -> bool:
        return self.path.exists()

    @property
    def unlocked(self) -> bool:
        return self._key is not None

    def _read_header(self) -> None:
        try:
            if self.path.stat().st_size > _MAX_VAULT_BYTES:
                raise VaultError("Die Tresordatei ist unerwartet groß.")
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") != _FORMAT_VERSION:
                raise VaultError("Diese Tresor-Version wird nicht unterstützt.")
            salt = base64.b64decode(data["salt"], validate=True)
            token = data["token"].encode("ascii")
            if len(salt) < 16 or not token:
                raise VaultError("Die Tresordatei ist beschädigt.")
        except VaultError:
            raise
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise VaultError("Die Tresordatei konnte nicht gelesen werden.") from exc
        self._salt, self._token = salt, token

    def create(self, master_password: str) -> None:
        if self.initialized:
            raise VaultError("Es existiert bereits ein Passwort-Tresor.")
        salt = secrets.token_bytes(16)
        key = derive_key(master_password, salt)
        token = Fernet(key).encrypt(b"[]")
        self._salt, self._token = salt, token
        self._key = key
        self._entries = []
        self._write(token)

    def unlock(self, master_password: str) -> None:
        if self._salt is None or self._token is None:
            self._read_header()
        assert self._salt is not None and self._token is not None
        key = derive_key(master_password, self._salt)
        try:
            plain = Fernet(key).decrypt(self._token)
            entries = json.loads(plain.decode("utf-8"))
            if not isinstance(entries, list) or any(not isinstance(x, dict) for x in entries):
                raise VaultError("Der Inhalt des Tresors hat ein ungültiges Format.")
        except InvalidToken as exc:
            raise VaultError("Master-Passphrase ist falsch oder der Tresor ist beschädigt.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VaultError("Der verschlüsselte Tresorinhalt ist ungültig.") from exc
        self._key, self._entries = key, entries

    def lock(self) -> None:
        self._key = None
        self._entries = []

    def entries(self) -> list[dict[str, Any]]:
        self._require_unlocked()
        return [dict(entry) for entry in self._entries]

    def add_entry(self, site: str, username: str, password: str, notes: str = "") -> str:
        self._require_unlocked()
        site, username = site.strip(), username.strip()
        if not site or not username or not password:
            raise VaultError("Website, Benutzername und Passwort sind Pflichtfelder.")
        entry_id = uuid.uuid4().hex
        self._entries.append({
            "id": entry_id,
            "site": site[:2048],
            "username": username[:1024],
            "password": password[:4096],
            "notes": notes[:4096],
        })
        self._save()
        return entry_id

    def delete_entry(self, entry_id: str) -> bool:
        self._require_unlocked()
        for index, entry in enumerate(self._entries):
            if entry.get("id") == entry_id:
                del self._entries[index]
                self._save()
                return True
        return False

    def _require_unlocked(self) -> None:
        if self._key is None:
            raise VaultError("Der Passwort-Tresor ist gesperrt.")

    def _save(self) -> None:
        self._require_unlocked()
        assert self._key is not None
        payload = json.dumps(self._entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        token = Fernet(self._key).encrypt(payload)
        self._write(token)
        self._token = token

    def _write(self, token: bytes) -> None:
        assert self._salt is not None
        data = json.dumps({
            "version": _FORMAT_VERSION,
            "kdf": "PBKDF2-HMAC-SHA256",
            "iterations": _KDF_ITERATIONS,
            "salt": base64.b64encode(self._salt).decode("ascii"),
            "token": token.decode("ascii"),
        }, indent=2).encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".vault-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if os.name != "nt":
                os.chmod(temp_path, 0o600)
            os.replace(temp_path, self.path)
            if os.name != "nt":
                os.chmod(self.path, 0o600)
        except BaseException:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
