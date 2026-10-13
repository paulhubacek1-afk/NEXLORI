"""Download and verify the official uBlock Origin Lite MV3 package for Nexlori builds."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "2026.1012.1545"
URL = f"https://github.com/uBlockOrigin/uBOL-home/releases/download/{VERSION}/uBOLite_{VERSION}.chromium.zip"
EXPECTED_SHA256 = "73909c8f26d608b00a99f446192630868bea4f947ba293c29bbd18ae948d903b"
LICENSE_URL = "https://raw.githubusercontent.com/uBlockOrigin/uBOL-home/master/LICENSE"
MAX_BYTES = 20 * 1024 * 1024


def download(url: str, destination: Path, limit: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Nexlori-Build/1.0"})
    data = bytearray()
    with urllib.request.urlopen(request, timeout=45) as response:
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > limit:
                raise RuntimeError(f"Download überschreitet das Größenlimit: {url}")
    if not data:
        raise RuntimeError(f"Leerer Download: {url}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return bytes(data)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    vendor = root / "src" / "nexlori" / "vendor"
    zip_path = vendor / "ubol.zip"
    license_path = vendor / "UBOL-LICENSE.txt"
    with tempfile.TemporaryDirectory(prefix="nexlori-ubol-") as temporary:
        temporary_path = Path(temporary)
        temporary_zip = temporary_path / "ubol.zip"
        payload = download(URL, temporary_zip, MAX_BYTES)
        actual = hashlib.sha256(payload).hexdigest()
        if actual.lower() != EXPECTED_SHA256:
            raise RuntimeError(f"uBlock Origin Lite Prüfsumme stimmt nicht: {actual}")
        with zipfile.ZipFile(temporary_zip) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names:
                raise RuntimeError("Das offizielle uBOL-Archiv hat kein manifest.json im Hauptverzeichnis.")
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("manifest_version") != 3:
                raise RuntimeError("Die heruntergeladene uBOL-Erweiterung ist nicht Manifest V3.")
            manifest_name = str(manifest.get("name", ""))
            localized = manifest_name
            if manifest_name.startswith("__MSG_") and manifest_name.endswith("__"):
                key = manifest_name[6:-2]
                locale = str(manifest.get("default_locale") or "en")
                messages_path = f"_locales/{locale}/messages.json"
                if messages_path in names:
                    messages = json.loads(archive.read(messages_path).decode("utf-8"))
                    localized = str(messages.get(key, {}).get("message", manifest_name))
            if "ublock" not in localized.casefold() and "ubol" not in localized.casefold():
                raise RuntimeError("Die Add-on-Metadaten stimmen nicht mit uBlock Origin Lite überein.")
        license_temp = temporary_path / "LICENSE"
        license_text = download(LICENSE_URL, license_temp, 200 * 1024)
        if b"GNU GENERAL PUBLIC LICENSE" not in license_text:
            raise RuntimeError("Die uBOL-Lizenzdatei konnte nicht verifiziert werden.")
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temporary_zip, zip_path)
        shutil.copy2(license_temp, license_path)
    print(f"uBlock Origin Lite {VERSION}: SHA-256 verifiziert, Manifest V3 geprüft.")
    print(f"Bundle: {zip_path} ({zip_path.stat().st_size} Bytes)")
    print(f"Lizenz: {license_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
