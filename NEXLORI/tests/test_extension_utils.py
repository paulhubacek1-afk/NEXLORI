import json
import zipfile

import pytest

from nexlori.extension_utils import (
    ExtensionPackageError,
    extension_key_from_name,
    inspect_extension_package,
)


def _write_zip(path, manifest, *, extra=None, localized=None):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        if localized:
            archive.writestr("_locales/en/messages.json", json.dumps(localized))
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return path


def test_extension_name_key_recognizes_ublock_lite():
    assert extension_key_from_name("uBlock Origin Lite") == "ublock-origin-lite"
    assert extension_key_from_name("Dark Reader") == "dark-reader"


def test_manifest_v3_zip_is_inspected(tmp_path):
    path = _write_zip(
        tmp_path / "demo.zip",
        {
            "manifest_version": 3,
            "name": "Demo Add-on",
            "version": "1.2.3",
            "description": "Test extension",
            "permissions": ["storage", "tabs"],
            "host_permissions": ["https://example.com/*"],
        },
    )
    info = inspect_extension_package(path)
    assert info["name"] == "Demo Add-on"
    assert info["version"] == "1.2.3"
    assert info["manifest_version"] == 3
    assert set(info["permissions"]) == {"storage", "tabs", "https://example.com/*"}


def test_localized_manifest_name_is_resolved(tmp_path):
    path = _write_zip(
        tmp_path / "localized.zip",
        {
            "manifest_version": 3,
            "name": "__MSG_extName__",
            "default_locale": "en",
            "version": "1.0.0",
        },
        localized={"extName": {"message": "uBlock Origin Lite"}},
    )
    assert inspect_extension_package(path)["name"] == "uBlock Origin Lite"


def test_manifest_v2_is_rejected(tmp_path):
    path = _write_zip(
        tmp_path / "v2.zip",
        {"manifest_version": 2, "name": "Old extension", "version": "1.0"},
    )
    with pytest.raises(ExtensionPackageError, match="Manifest V3"):
        inspect_extension_package(path)


def test_zip_with_path_traversal_is_rejected(tmp_path):
    path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"manifest_version": 3, "name": "Bad", "version": "1"}))
        archive.writestr("../escape.txt", "not safe")
    with pytest.raises(ExtensionPackageError, match="unsicheren Dateipfad"):
        inspect_extension_package(path)


def test_zip_without_root_manifest_is_rejected(tmp_path):
    path = tmp_path / "nested.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("folder/manifest.json", json.dumps({"manifest_version": 3, "name": "Nested", "version": "1"}))
    with pytest.raises(ExtensionPackageError, match="Hauptverzeichnis"):
        inspect_extension_package(path)
