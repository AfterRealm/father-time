"""
Father Time — Update checker.
Compares installed plugin version against latest GitHub release.
Runs on SessionStart to notify users of available updates.
"""
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

REPO = "AfterRealm/father-time"
GITHUB_API = f"https://api.github.com/repos/{REPO}/releases/latest"


def get_installed_version():
    """Read version from the installed plugin.json."""
    # Try CLAUDE_PLUGIN_ROOT first, then relative path
    import os
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if plugin_root:
        p = Path(plugin_root) / ".claude-plugin" / "plugin.json"
    else:
        p = Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("version", "0.0.0")
    except Exception:
        return None


def get_latest_version():
    """Fetch latest release tag from GitHub."""
    req = urllib.request.Request(
        GITHUB_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "father-time-plugin",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            # Strip leading 'v' if present
            return tag.lstrip("v") if tag else None
    except Exception:
        return None


def version_tuple(v):
    """Convert version string to comparable tuple."""
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0, 0, 0)


def main():
    installed = get_installed_version()
    if not installed:
        return  # Can't determine installed version, skip silently

    latest = get_latest_version()
    if not latest:
        return  # Can't reach GitHub, skip silently

    if version_tuple(latest) > version_tuple(installed):
        print(f"Father Time update available: v{installed} -> v{latest}")
        print(f"Run: claude plugin update \"father-time@afterrealm-plugins\"")
    # If up to date, print nothing — no noise


if __name__ == "__main__":
    main()
