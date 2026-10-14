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
        digest = hashlib.sha256()
        with downloaded.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        if not hmac.compare_digest(actual, expected):
            raise UpdateError("Die Prüfsumme passt nicht zur EXE. Das Update wurde verworfen.")
        staged = destination / "Nexlori.exe.pending"
        staged.unlink(missing_ok=True)
        downloaded.replace(staged)
    if staged.stat().st_size < 1024 * 1024:
        staged.unlink(missing_ok=True)
        raise UpdateError("Die EXE ist unerwartet klein. Das Update wurde verworfen.")
    return staged


def start_windows_self_update(
    staged_exe: str | Path,
    release_url: str,
    *,
    target_exe: str | Path | None = None,
) -> bool:
    """Start a helper which waits for Nexlori to exit, replaces its EXE and relaunches it."""
    target = Path(target_exe or sys.executable).resolve()
    staged = Path(staged_exe).resolve()
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    if not target.exists() or not staged.exists() or target.name.lower() != "nexlori.exe":
        raise UpdateError("Der Selbst-Updater kann diese Programmdatei nicht sicher ersetzen.")

    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    update_dir = local / "Nexlori" / "updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    log_path = update_dir / "update.log"
    script = update_dir / "apply-update.ps1"
    script.write_text(
        r"""param(
  [int]$ProcessId,
  [string]$TargetPath,
  [string]$SourcePath,
  [string]$LogPath,
  [string]$ReleaseUrl
)
$ErrorActionPreference = 'Stop'
try {
  try { Wait-Process -Id $ProcessId -ErrorAction SilentlyContinue } catch {}
  $nextPath = $TargetPath + '.new'
  Copy-Item -LiteralPath $SourcePath -Destination $nextPath -Force
  Move-Item -LiteralPath $nextPath -Destination $TargetPath -Force
  Add-Content -LiteralPath $LogPath -Value ("{0:o} Update erfolgreich installiert." -f (Get-Date))
  Remove-Item -LiteralPath $SourcePath -Force -ErrorAction SilentlyContinue
  Start-Process -FilePath $TargetPath
} catch {
  Add-Content -LiteralPath $LogPath -Value ("{0:o} Update fehlgeschlagen: {1}" -f (Get-Date), $_.Exception.Message)
  try { Start-Process -FilePath $ReleaseUrl } catch {}
  try {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
      "Nexlori konnte sich nicht automatisch aktualisieren. Die Release-Seite wurde geöffnet. Fehlerdetails: " + $_.Exception.Message,
      "Nexlori-Update", "OK", "Warning"
    ) | Out-Null
  } catch {}
}
""",
        encoding="utf-8",
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden", "-File", str(script),
                "-ProcessId", str(os.getpid()),
                "-TargetPath", str(target),
                "-SourcePath", str(staged),
                "-LogPath", str(log_path),
                "-ReleaseUrl", release_url,
            ],
            close_fds=True,
            creationflags=creationflags,
        )
    except OSError as exc:
        raise UpdateError("Der Windows-Updater konnte nicht gestartet werden.") from exc
    return True
