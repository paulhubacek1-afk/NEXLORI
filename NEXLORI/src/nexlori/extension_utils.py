"""Helpers for safe, user-approved Manifest V3 browser extensions."""
from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

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


def is_builtin_extension(name: str) -> bool:
    """Identify Chromium's built-in PDF/helper extensions so settings never disable them."""
    key = extension_key_from_name(name)
    return "pdf-viewer" in key or "chromium-pdf" in key or "hangouts" in key


def _localized_name(manifest: dict[str, Any], base: Path | None, archive: zipfile.ZipFile | None) -> str:
    raw = str(manifest.get("name") or "").strip()
    match = re.fullmatch(r"__MSG_(\w+)__", raw)
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


def extension_name_from_info(extension: Any) -> str:
    """Resolve localized names from an installed Qt extension's manifest."""
    name = str(extension.name() or "").strip()
    try:
        base = Path(str(extension.path()))
        manifest_path = base / "manifest.json"
        if manifest_path.is_file() and manifest_path.stat().st_size <= MAX_MANIFEST_BYTES:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest, dict):
                localized = _localized_name(manifest, base, None)
                if localized and not localized.startswith("__MSG_"):
                    return localized
    except (AttributeError, OSError, ValueError, TypeError, UnicodeDecodeError):
        pass
    return name or "Unbenannte Erweiterung"


def extension_key_from_info(extension: Any) -> str:
    """Get a stable identity even when the manifest uses Chrome's __MSG_*__ names."""
    return extension_key_from_name(extension_name_from_info(extension))


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
        if extension_key_from_name(name) == "ublock-origin-lite":
            raise ExtensionPackageError(
                "uBlock Origin Lite wird von der aktuellen Qt-WebEngine-Erweiterungs-API nicht zuverlässig "
                "unterstützt. Verwende stattdessen Nexlori Shield; andere kompatible Manifest-V3-Add-ons "
                "können weiterhin installiert werden."
            )
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


def unpack_extension_package(path: str | Path, destination: str | Path) -> Path:
    """Return a validated unpacked MV3 extension directory for Qt WebEngine.

    QWebEngineExtensionManager.installExtension expects a directory containing
    manifest.json, not the ZIP file used by Nexlori's package manager. Extract
    into a fresh sibling directory, validate paths, then atomically replace the
    cached copy so interrupted extraction cannot leave a partial extension.
    """
    source = Path(path).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    details = inspect_extension_package(source)
    if source.is_dir():
        return source
    if source.suffix.casefold() != ".zip":
        raise ExtensionPackageError("Das Add-on muss als ZIP oder entpackter Ordner vorliegen.")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".extracting")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    try:
        with zipfile.ZipFile(source, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_EXTENSION_FILES:
                raise ExtensionPackageError("Das Add-on enthält zu viele Dateien.")
            expanded = sum(info.file_size for info in infos)
            if expanded > MAX_EXTENSION_UNPACKED_BYTES:
                raise ExtensionPackageError("Das entpackte Add-on wäre größer als erlaubt.")
            root = temporary.resolve()
            for info in infos:
                member = PurePosixPath(info.filename.replace("\\", "/"))
                if member.is_absolute() or ".." in member.parts:
                    raise ExtensionPackageError("Die ZIP enthält einen unsicheren Dateipfad.")
                # Reject Unix symlinks; extensions should only contain ordinary files/directories.
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ExtensionPackageError("Die ZIP enthält einen nicht erlaubten symbolischen Link.")
                output = (temporary / Path(*member.parts)).resolve()
                if not output.is_relative_to(root):
                    raise ExtensionPackageError("Die ZIP enthält einen unsicheren Dateipfad.")
                if info.is_dir():
                    output.mkdir(parents=True, exist_ok=True)
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info, "r") as incoming, output.open("wb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
        manifest = temporary / "manifest.json"
        if not manifest.is_file():
            raise ExtensionPackageError("In der ZIP fehlt manifest.json im Hauptverzeichnis.")
        inspect_extension_package(temporary)
        if target.exists():
            shutil.rmtree(target)
        temporary.replace(target)
        return target
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        raise
