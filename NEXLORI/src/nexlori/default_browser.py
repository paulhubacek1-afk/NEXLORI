"""Windows per-user browser registration; Windows itself controls the final default-app choice."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def register_windows_browser(executable: str | None = None) -> bool:
    """Register Nexlori for HTTP/HTTPS and HTML files without changing UserChoice."""
    if os.name != "nt":
        return False
    if executable is None:
        if not getattr(sys, "frozen", False):
            return False  # niemals versehentlich Python selbst als Browser registrieren
        executable = sys.executable
    import winreg

    exe = str(Path(executable).resolve())
    if not exe.lower().endswith(".exe"):
        # In source mode register the Python launcher only if explicitly requested; avoid a broken association.
        return False
    classes = r"Software\Classes"
    prog_ids = {
        "NexloriHTML": {"description": "Nexlori HTML Document", "extensions": (".htm", ".html")},
        "NexloriURL": {"description": "Nexlori URL", "extensions": ()},
    }
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, classes, 0, winreg.KEY_WRITE) as root:
        for prog_id, data in prog_ids.items():
            with winreg.CreateKeyEx(root, prog_id, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, data["description"])
                with winreg.CreateKeyEx(key, "DefaultIcon", 0, winreg.KEY_WRITE) as icon_key:
                    winreg.SetValueEx(icon_key, None, 0, winreg.REG_SZ, f'"{exe}",0')
                with winreg.CreateKeyEx(key, r"shell\open\command", 0, winreg.KEY_WRITE) as command_key:
                    winreg.SetValueEx(command_key, None, 0, winreg.REG_SZ, f'"{exe}" "%1"')
                if prog_id == "NexloriURL":
                    winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    caps_path = r"Software\Nexlori\Capabilities"
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, caps_path, 0, winreg.KEY_WRITE) as caps:
        winreg.SetValueEx(caps, "ApplicationName", 0, winreg.REG_SZ, "Nexlori")
        winreg.SetValueEx(caps, "ApplicationDescription", 0, winreg.REG_SZ, "Nexlori Web Browser")
        winreg.SetValueEx(caps, "ApplicationIcon", 0, winreg.REG_SZ, f'"{exe}",0')
        with winreg.CreateKeyEx(caps, "FileAssociations", 0, winreg.KEY_WRITE) as files:
            winreg.SetValueEx(files, ".htm", 0, winreg.REG_SZ, "NexloriHTML")
            winreg.SetValueEx(files, ".html", 0, winreg.REG_SZ, "NexloriHTML")
        with winreg.CreateKeyEx(caps, "URLAssociations", 0, winreg.KEY_WRITE) as urls:
            winreg.SetValueEx(urls, "http", 0, winreg.REG_SZ, "NexloriURL")
            winreg.SetValueEx(urls, "https", 0, winreg.REG_SZ, "NexloriURL")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\RegisteredApplications", 0, winreg.KEY_WRITE) as apps:
        winreg.SetValueEx(apps, "Nexlori", 0, winreg.REG_SZ, caps_path)
    return True


def default_browser_settings_uri() -> str:
    """Return the supported Settings URI; the user must confirm the default browser in Windows."""
    return "ms-settings:defaultapps?registeredAppUser=Nexlori"
