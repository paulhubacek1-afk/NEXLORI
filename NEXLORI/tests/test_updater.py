import hashlib

import pytest

from nexlori.updater import UpdateError, download_verified_update, find_update, version_tuple


def release(version, *, draft=False, prerelease=False, include_assets=True):
    assets = []
    if include_assets:
        assets = [
            {"name": "Nexlori.exe", "browser_download_url": "https://example.test/Nexlori.exe"},
            {"name": "Nexlori.exe.sha256", "browser_download_url": "https://example.test/Nexlori.exe.sha256"},
        ]
    return {
        "tag_name": f"v{version}",
        "draft": draft,
        "prerelease": prerelease,
        "html_url": f"https://github.com/paulhubacek1-afk/NEXLORI/releases/tag/v{version}",
        "body": "Release notes",
        "assets": assets,
    }


def test_version_parser_and_ordering():
    assert version_tuple("v1.2.3") == (1, 2, 3, 0)
    assert version_tuple("0.4.0") > version_tuple("0.3.9")
    assert version_tuple("0.5.0-build.42") > version_tuple("0.5.0-build.41")
    assert version_tuple("0.5.1") > version_tuple("0.5.0-build.999")
    with pytest.raises(ValueError):
        version_tuple("latest")


def test_find_update_selects_newest_complete_non_draft_release():
    found = find_update("0.3.0", [
        release("0.8.0", draft=True),
        release("0.5.0", include_assets=False),
        release("0.4.1"),
        release("0.4.0"),
    ])
    assert found["tag_name"] == "v0.4.1"


def test_no_newer_update_returns_none():
    assert find_update("0.4.0", [release("0.3.9"), release("0.4.0")]) is None

def test_prerelease_builds_are_never_offered_as_stable_updates():
    assert find_update("1.0.0", [
        release("1.0.0-build.99", prerelease=True),
        release("1.0.0"),
    ]) is None
    update = find_update("1.0.0", [release("1.0.1-build.100", prerelease=True), release("1.0.1")])
    assert update["tag_name"] == "v1.0.1"


def test_verified_download_accepts_valid_sha256(monkeypatch, tmp_path):
    payload = b"MZ" + (b"Nexlori test binary " * 55_000)
    expected = hashlib.sha256(payload).hexdigest()

    def fake_download(url, target, **kwargs):
        if url.endswith(".sha256"):
            target.write_text(f"{expected}  Nexlori.exe\n", encoding="ascii")
        else:
            target.write_bytes(payload)

    monkeypatch.setattr("nexlori.updater._download", fake_download)
    result = download_verified_update(release("0.4.0"), tmp_path)
    assert result.name == "Nexlori.exe.pending"
    assert result.read_bytes() == payload


def test_verified_download_rejects_hash_mismatch(monkeypatch, tmp_path):
    def fake_download(url, target, **kwargs):
        if url.endswith(".sha256"):
            target.write_text(f"{'0' * 64}  Nexlori.exe\n", encoding="ascii")
        else:
            target.write_bytes(b"MZ" + b"x" * (1024 * 1024))

    monkeypatch.setattr("nexlori.updater._download", fake_download)
    with pytest.raises(UpdateError, match="Prüfsumme"):
        download_verified_update(release("0.4.0"), tmp_path)


def test_missing_release_assets_are_rejected(tmp_path):
    with pytest.raises(UpdateError, match="fehlen"):
        download_verified_update(release("0.4.0", include_assets=False), tmp_path)
