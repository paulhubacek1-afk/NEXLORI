import hashlib

import pytest

import urllib.error

from nexlori.updater import UpdateError, check_for_update, download_verified_update, find_update, version_tuple


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



def test_update_check_reports_github_rate_limit(monkeypatch):
    def rate_limited(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://api.github.com/repos/example/releases",
            403,
            "rate limited",
            {"Retry-After": "30"},
            None,
        )

    monkeypatch.setattr("urllib.request.urlopen", rate_limited)
    with pytest.raises(UpdateError, match="begrenzt gerade Update-Anfragen") as exc:
        check_for_update("1.0.0")
    assert "30 Sekunden" in str(exc.value)


def test_update_check_rejects_oversized_release_response(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size):
            return b"x" * size

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
    with pytest.raises(UpdateError, match="unerwartet groß"):
        check_for_update("1.0.0")


# ------------------------------------------------------------------ automatische Installation (1.4)
from nexlori.updater import (  # noqa: E402
    PENDING_MANIFEST, can_self_update, discard_pending_update, pending_update, start_windows_self_update,
)


def _stage(monkeypatch, tmp_path, version="9.9.9"):
    payload = b"MZ" + (b"Nexlori pending binary " * 60_000)
    expected = hashlib.sha256(payload).hexdigest()

    def fake_download(url, target, **kwargs):
        if url.endswith(".sha256"):
            target.write_text(f"{expected}  Nexlori.exe\n", encoding="ascii")
        else:
            target.write_bytes(payload)

    monkeypatch.setattr("nexlori.updater._download", fake_download)
    return download_verified_update(release(version), tmp_path)


def test_verified_download_records_pending_manifest(monkeypatch, tmp_path):
    staged = _stage(monkeypatch, tmp_path)
    assert (tmp_path / PENDING_MANIFEST).exists()
    pending = pending_update(tmp_path, "1.4.0")
    assert pending["version"] == "9.9.9"
    assert pending["path"] == str(staged)
    assert pending["url"].startswith("https://")


def test_pending_update_is_discarded_once_installed(monkeypatch, tmp_path):
    _stage(monkeypatch, tmp_path, version="1.4.0")
    assert pending_update(tmp_path, "1.4.0") is None
    assert not (tmp_path / PENDING_MANIFEST).exists()
    assert not (tmp_path / "Nexlori.exe.pending").exists()


def test_tampered_pending_update_is_never_installed(monkeypatch, tmp_path):
    staged = _stage(monkeypatch, tmp_path)
    staged.write_bytes(b"MZ" + b"evil" * 400_000)
    assert pending_update(tmp_path, "1.4.0") is None
    assert not staged.exists()


def test_missing_or_broken_manifest_cleans_up(tmp_path):
    (tmp_path / "Nexlori.exe.pending").write_bytes(b"x")
    assert pending_update(tmp_path, "1.0.0") is None
    assert not (tmp_path / "Nexlori.exe.pending").exists()
    (tmp_path / PENDING_MANIFEST).write_text("{}", encoding="utf-8")
    assert pending_update(tmp_path, "1.0.0") is None
    discard_pending_update(tmp_path)


def test_self_update_is_only_possible_for_the_frozen_windows_exe(tmp_path):
    assert can_self_update(tmp_path / "Nexlori.exe") is False  # Tests laufen nicht als gefrorene EXE
    assert start_windows_self_update(tmp_path / "x", "https://example.test", target_exe=tmp_path / "Nexlori.exe") is False
