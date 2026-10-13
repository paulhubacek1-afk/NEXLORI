"""Helpers for safe, user-approved Manifest V3 browser extensions."""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

UBOLITE_VERSION = "2026.1012.1545"
UBOLITE_URL = (
    "https://github.com/uBlockOrigin/uBOL-home/releases/download/"
    f"{UBOLITE_VERSION}/uBOLite_{UBOLITE_VERSION}.chromium.zip"
)
UBOLITE_SHA256 = "73909c8f26d608b00a99f446192630868bea4f947ba293c29bbd18ae948d903b"
MAX_EXTENSION_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_EXTENSION_UNPACKED_BYTES = 300 * 1024 * 1024
MAX_EXTENSION_FILES = 12000
MAX_MANIFEST_BYTES = 2 * 1024 * 1024


class ExtensionPackageError(ValueError):
    """A user-selected browser extension is unsupported or malformed."""


def extension_key_from_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(name).casefold()).strip("-")
    if "ublock" in normalized and "lite" in normalized:
        return "ublock-origin-lite"
    return normalized[:100] or "unnamed-extension"


def bundled_ubolite_path() -> Path | None:
    """Find the verified extension bundled by the Windows build workflow."""
    candidates = [
        Path(__file__).resolve().parent / "vendor" / "ubol.zip",
        Path(getattr(sys, "_MEIPASS", "")) / "nexlori" / "vendor" / "ubol.zip",
        Path(__file__).resolve().parents[2] / "packaging" / "vendor" / "ubol.zip",
    ]
    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_size <= MAX_EXTENSION_ARCHIVE_BYTES:
                return candidate
        except OSError:
            continue
    return None


def _localized_name(manifest: dict[str, Any], base: Path | None, archive: zipfile.ZipFile | None) -> str:
    raw = str(manifest.get("name") or "").strip()
    match = re.fullmatch(r"__MSG_(\\w+)__", raw)
    if not match:
        return raw or "Unbenannte Erweiterung"
    locale = str(manifest.get("default_locale") or "en")
    relative = f"_locales/{locale}/messages.json"
    try:
        if archive is not None:
            payload = archive.read(relative)
        elif base is not None:
            payload = (base / relative).read_bytes()
        else:
            return raw
        if len(payload) > MAX_MANIFEST_BYTES:
            return raw
        messages = json.loads(payload.decode("utf-8"))
        value = messages.get(match.group(1), {}).get("message")
        return str(value or raw).strip()
    except (OSError, KeyError, ValueError, UnicodeDecodeError, zipfile.BadZipFile, AttributeError):
        return raw


def inspect_extension_package(path: str | Path) -> dict[str, Any]:
    """Validate a ZIP or unpacked extension before giving it to Qt's extension manager.

    Qt WebEngine currently supports Manifest V3 only. ZIPs must have manifest.json
    at their archive root; unsafe archive paths and oversized packages are rejected.
    """
    source = Path(path).expanduser()
    if not source.exists():
        raise ExtensionPackageError("Der Add-on-Pfad existiert nicht.")

    archive: zipfile.ZipFile | None = None
    base: Path | None = None
    manifest_bytes: bytes
    try:
        if source.is_dir():
            base = source.resolve()
            manifest_path = base / "manifest.json"
            if not manifest_path.is_file():
                raise ExtensionPackageError("Im ausgewählten Ordner fehlt manifest.json.")
            if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
                raise ExtensionPackageError("manifest.json ist größer als erlaubt.")
            manifest_bytes = manifest_path.read_bytes()
        else:
            if source.suffix.casefold() != ".zip":
                raise ExtensionPackageError("Bitte eine ZIP-Datei oder einen entpackten Add-on-Ordner auswählen.")
            if source.stat().st_size > MAX_EXTENSION_ARCHIVE_BYTES:
                raise ExtensionPackageError("Die ZIP-Datei ist größer als 100 MB.")
            try:
                archive = zipfile.ZipFile(source, "r")
            except (OSError, zipfile.BadZipFile) as exc:
                raise ExtensionPackageError("Die ZIP-Datei ist ungültig oder beschädigt.") from exc
            infos = archive.infolist()
            if len(infos) > MAX_EXTENSION_FILES:
                raise ExtensionPackageError("Das Add-on enthält zu viele Dateien.")
            expanded = sum(info.file_size for info in infos)
            if expanded > MAX_EXTENSION_UNPACKED_BYTES:
                raise ExtensionPackageError("Das entpackte Add-on wäre größer als erlaubt.")
            for info in infos:
                member = PurePosixPath(info.filename.replace("\\", "/"))
                if member.is_absolute() or ".." in member.parts:
                    raise ExtensionPackageError("Die ZIP enthält einen unsicheren Dateipfad.")
            manifest_info = next(
                (info for info in infos if info.filename == "manifest.json" and not info.is_dir()),
                None,
            )
            if manifest_info is None:
                raise ExtensionPackageError(
                    "In der ZIP muss manifest.json direkt im Hauptverzeichnis liegen."
                )
            if manifest_info.file_size > MAX_MANIFEST_BYTES:
                raise ExtensionPackageError("manifest.json ist größer als erlaubt.")
            manifest_bytes = archive.read(manifest_info)
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ExtensionPackageError("manifest.json enthält kein gültiges JSON.") from exc
        if not isinstance(manifest, dict):
            raise ExtensionPackageError("manifest.json muss ein JSON-Objekt sein.")
        if manifest.get("manifest_version") != 3:
            raise ExtensionPackageError(
                "Nexlori unterstützt derzeit nur Manifest-V3-Add-ons. Manifest V2 wird nicht geladen."
            )
        name = _localized_name(manifest, base, archive)
        if not name or len(name) > 250:
            raise ExtensionPackageError("Der Add-on-Name ist ungültig.")
        permissions: list[str] = []
        for field in ("permissions", "optional_permissions", "host_permissions", "optional_host_permissions"):
            values = manifest.get(field, [])
            if isinstance(values, list):
                permissions.extend(str(value) for value in values if isinstance(value, str))
        return {
            "name": name,
            "description": str(manifest.get("description") or "")[:500],
            "manifest_version": 3,
            "version": str(manifest.get("version") or ""),
            "permissions": sorted(set(permissions)),
            "path": str(source.resolve()),
        }
    except ExtensionPackageError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ExtensionPackageError(f"Das Add-on konnte nicht geprüft werden: {exc}") from exc
    finally:
        if archive is not None:
            archive.close()
