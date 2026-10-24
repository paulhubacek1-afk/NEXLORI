"""Update discovery, checksum-verified downloads and Windows self-update handoff."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPOSITORY = "paulhubacek1-afk/NEXLORI"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
PENDING_MANIFEST = "pending-update.json"
PERIODIC_CHECK_SECONDS = 6 * 3600
MAX_EXE_BYTES = 400 * 1024 * 1024
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+]build[.-](\d+))?$", re.IGNORECASE)
HASH_PATTERN = re.compile(r"^\s*([0-9a-fA-F]{64})\s+Nexlori\.exe\s*$", re.MULTILINE)


class UpdateError(RuntimeError):
    """An update could not be checked, downloaded, or verified."""


def version_tuple(value: str) -> tuple[int, int, int, int]:
    """Compare stable versions and monotonically increasing CI builds of the same version."""
    match = VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Ungültige Versionsnummer: {value!r}")
    major, minor, patch, build = match.groups()
    return int(major), int(minor), int(patch), int(build or 0)


def find_update(current_version: str, releases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the newest non-draft published release with both expected assets."""
    current = version_tuple(current_version)
    candidates = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag = str(release.get("tag_name", ""))
        try:
            version = version_tuple(tag)
        except ValueError:
            continue
        assets = release.get("assets") or []
        names = {str(asset.get("name")) for asset in assets if isinstance(asset, dict)}
        if {"Nexlori.exe", "Nexlori.exe.sha256"} <= names and version > current:
            candidates.append((version, release))
    if not candidates:
        return None
    _, selected = max(candidates, key=lambda item: item[0])
    return selected


def check_for_update(current_version: str, timeout: float = 8.0) -> dict[str, Any] | None:
    request = urllib.request.Request(
        RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Nexlori-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise UpdateError("Die Release-Antwort von GitHub ist unerwartet groß.")
            data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            suffix = f" Versuche es in {retry_after} Sekunden erneut." if retry_after and retry_after.isdigit() else " Versuche es später erneut."
            raise UpdateError("GitHub begrenzt gerade Update-Anfragen." + suffix) from exc
        if exc.code == 404:
            raise UpdateError("Die GitHub-Release-API wurde nicht gefunden. Prüfe die Repository-Adresse.") from exc
        raise UpdateError(f"GitHub hat die Update-Suche mit HTTP {exc.code} abgelehnt.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError("GitHub ist gerade nicht erreichbar. Prüfe deine Internetverbindung.") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise UpdateError("GitHub hat eine ungültige Antwort geliefert.") from exc
    if not isinstance(data, list):
        raise UpdateError("Die Release-Liste von GitHub ist ungültig.")
    release = find_update(current_version, data)
    if release is None:
        return None
    return {
        "tag": str(release["tag_name"]),
        "version": str(release["tag_name"]).removeprefix("v"),
        "url": str(release.get("html_url") or f"https://github.com/{REPOSITORY}/releases"),
        "body": str(release.get("body") or ""),
        "published_at": str(release.get("published_at") or ""),
        "assets": [
            {"name": str(a.get("name")), "url": str(a.get("browser_download_url"))}
            for a in release.get("assets", [])
            if isinstance(a, dict)
            and a.get("name") in {"Nexlori.exe", "Nexlori.exe.sha256"}
            and a.get("browser_download_url")
        ],
    }


def _download(url: str, target: Path, *, timeout: float = 35.0, max_bytes: int = MAX_EXE_BYTES) -> None:
    if not url.startswith("https://"):
        raise UpdateError("Das Update wurde von einer unsicheren Download-Adresse angeboten.")
    request = urllib.request.Request(url, headers={"User-Agent": "Nexlori-Updater"})
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, target.open("wb") as output:
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise UpdateError("Die Update-Datei ist größer als erlaubt.")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UpdateError("Die Update-Datei ist größer als erlaubt.")
                output.write(chunk)
    except UpdateError:
        target.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        target.unlink(missing_ok=True)
        raise UpdateError("Die Update-Datei konnte nicht heruntergeladen werden.") from exc
    if total == 0:
        target.unlink(missing_ok=True)
        raise UpdateError("GitHub hat eine leere Update-Datei geliefert.")


def download_verified_update(release: dict[str, Any], destination_dir: str | Path) -> Path:
    """Download the EXE and verify it against that release's SHA-256 sidecar."""
    # check_for_update returns a normalized release; accepting GitHub's raw key as well keeps helpers testable.
    assets = {
        item.get("name"): (item.get("url") or item.get("browser_download_url"))
        for item in release.get("assets", [])
        if isinstance(item, dict)
    }
    exe_url, hash_url = assets.get("Nexlori.exe"), assets.get("Nexlori.exe.sha256")
    if not exe_url or not hash_url:
        raise UpdateError("Dem Release fehlen Nexlori.exe oder die SHA-256-Prüfsumme.")
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nexlori-update-") as temp:
        temp_dir = Path(temp)
        hash_file = temp_dir / "Nexlori.exe.sha256"
        _download(str(hash_url), hash_file, max_bytes=4096)
        sidecar = hash_file.read_text(encoding="ascii", errors="strict")
        match = HASH_PATTERN.fullmatch(sidecar.strip())
        if not match:
            raise UpdateError("Die SHA-256-Prüfsumme hat ein ungültiges Format.")
        expected = match.group(1).lower()
        downloaded = temp_dir / "Nexlori.exe"
        _download(str(exe_url), downloaded)
        actual = _sha256_file(downloaded)
        if not hmac.compare_digest(actual, expected):
            raise UpdateError("Die Prüfsumme passt nicht zur EXE. Das Update wurde verworfen.")
        staged = destination / "Nexlori.exe.pending"
        staged.unlink(missing_ok=True)
        downloaded.replace(staged)
    if staged.stat().st_size < 1024 * 1024:
        staged.unlink(missing_ok=True)
        raise UpdateError("Die EXE ist unerwartet klein. Das Update wurde verworfen.")
    version = str(release.get("version") or str(release.get("tag_name", "")).removeprefix("v"))
    _write_manifest(destination, {
        "version": version,
        "sha256": expected,
        "file": staged.name,
        "url": str(release.get("url") or release.get("html_url") or RELEASES_PAGE),
    })
    return staged


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(directory: Path, data: dict[str, str]) -> None:
    path = directory / PENDING_MANIFEST
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def discard_pending_update(update_dir: str | Path) -> None:
    directory = Path(update_dir)
    (directory / PENDING_MANIFEST).unlink(missing_ok=True)
    (directory / "Nexlori.exe.pending").unlink(missing_ok=True)


def pending_update(update_dir: str | Path, current_version: str) -> dict[str, str] | None:
    """Return a verified, still-newer staged update or clean up stale leftovers.

    The staged EXE is hashed again, so a file that changed on disk after the
    download is never installed.
    """
    directory = Path(update_dir)
    manifest = directory / PENDING_MANIFEST
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        (directory / "Nexlori.exe.pending").unlink(missing_ok=True)
        return None
    try:
        staged = directory / str(data["file"])
        newer = version_tuple(str(data["version"])) > version_tuple(current_version)
        expected = str(data["sha256"]).lower()
    except (KeyError, TypeError, ValueError):
        discard_pending_update(directory)
        return None
    if not newer or staged.name != "Nexlori.exe.pending" or not staged.is_file():
        discard_pending_update(directory)
        return None
    if not hmac.compare_digest(_sha256_file(staged), expected):
        discard_pending_update(directory)
        return None
    return {"version": str(data["version"]), "path": str(staged), "url": str(data.get("url") or RELEASES_PAGE)}


def can_self_update(target_exe: str | Path | None = None) -> bool:
    """True only for the frozen Windows EXE that Nexlori may replace in place."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    target = Path(target_exe or sys.executable)
    return target.name.lower() == "nexlori.exe" and target.exists()


_APPLY_SCRIPT = r"""param(
  [int]$ProcessId,
  [string]$TargetPath,
  [string]$SourcePath,
  [string]$ManifestPath,
  [string]$LogPath,
  [string]$ReleaseUrl,
  [int]$Relaunch = 1
)
$ErrorActionPreference = 'Stop'
function Log([string]$text) { Add-Content -LiteralPath $LogPath -Value ("{0:o} {1}" -f (Get-Date), $text) }
try {
  # Wait for the Python process and for the PyInstaller bootloader that still holds the EXE.
  try { Wait-Process -Id $ProcessId -Timeout 90 -ErrorAction SilentlyContinue } catch {}
  $nextPath = $TargetPath + '.new'
  $backupPath = $TargetPath + '.old'
  Copy-Item -LiteralPath $SourcePath -Destination $nextPath -Force
  $replaced = $false
  for ($attempt = 1; $attempt -le 60 -and -not $replaced; $attempt++) {
    try {
      if (Test-Path -LiteralPath $backupPath) { Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue }
      if (Test-Path -LiteralPath $TargetPath) { Move-Item -LiteralPath $TargetPath -Destination $backupPath -Force }
      Move-Item -LiteralPath $nextPath -Destination $TargetPath -Force
      $replaced = $true
    } catch {
      if ((-not (Test-Path -LiteralPath $TargetPath)) -and (Test-Path -LiteralPath $backupPath)) {
        Move-Item -LiteralPath $backupPath -Destination $TargetPath -Force -ErrorAction SilentlyContinue
      }
      Start-Sleep -Milliseconds 500
    }
  }
  if (-not $replaced) { throw "Die Programmdatei war nach 30 Sekunden noch gesperrt." }
  Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $SourcePath -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $ManifestPath -Force -ErrorAction SilentlyContinue
  Log "Update erfolgreich installiert."
  if ($Relaunch -eq 1) { Start-Process -FilePath $TargetPath }
} catch {
  Log ("Update fehlgeschlagen: " + $_.Exception.Message)
  Remove-Item -LiteralPath ($TargetPath + '.new') -Force -ErrorAction SilentlyContinue
  if ($Relaunch -eq 1) {
    try { Start-Process -FilePath $TargetPath } catch {}
    try { Start-Process -FilePath $ReleaseUrl } catch {}
  }
}
"""


def start_windows_self_update(
    staged_exe: str | Path,
    release_url: str,
    *,
    target_exe: str | Path | None = None,
    relaunch: bool = True,
) -> bool:
    """Start a helper which waits for Nexlori to exit, replaces its EXE and optionally relaunches it."""
    target = Path(target_exe or sys.executable).resolve()
    staged = Path(staged_exe).resolve()
    if not can_self_update(target):
        return False
    if not staged.exists():
        raise UpdateError("Der Selbst-Updater kann diese Programmdatei nicht sicher ersetzen.")
    if not release_url.startswith("https://"):
        release_url = RELEASES_PAGE

    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    update_dir = local / "Nexlori" / "updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    log_path = update_dir / "update.log"
    script = update_dir / "apply-update.ps1"
    # UTF-8 with BOM so Windows PowerShell 5.1 reads the German messages correctly.
    script.write_text(_APPLY_SCRIPT, encoding="utf-8-sig")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden", "-File", str(script),
                "-ProcessId", str(os.getpid()),
                "-TargetPath", str(target),
                "-SourcePath", str(staged),
                "-ManifestPath", str(staged.parent / PENDING_MANIFEST),
                "-LogPath", str(log_path),
                "-ReleaseUrl", release_url,
                "-Relaunch", "1" if relaunch else "0",
            ],
            close_fds=True,
            creationflags=creationflags,
        )
    except OSError as exc:
        raise UpdateError("Der Windows-Updater konnte nicht gestartet werden.") from exc
    return True
