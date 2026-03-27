"""
Father Time — Usage check.
Fetches real rate limit data from the Anthropic OAuth API.
Returns session (5-hour), weekly (7-day), and Opus-specific utilization.
"""
import os
import sys
import json

# Fix Windows encoding for Unicode output
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime


def get_oauth_token():
    """Find the OAuth token from Claude's credential files."""
    home = Path.home()
    paths = [
        home / ".claude" / ".credentials.json",
        home / ".claude" / "credentials.json",
    ]
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        paths.append(Path(appdata) / "claude" / "credentials.json")

    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            token = data.get("claudeAiOauth", {}).get("accessToken")
            if token:
                return token
        except Exception:
            continue
    return None


def fetch_usage(token):
    """Hit the Anthropic usage API and return parsed data."""
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-code/2.0.32",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error: API returned {e.code}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def format_reset(resets_at):
    """Format a reset timestamp into a readable string."""
    if not resets_at:
        return "unknown"
    try:
        reset_dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        now = datetime.now(reset_dt.tzinfo)
        delta = reset_dt - now
        total_minutes = int(delta.total_seconds() / 60)
        if total_minutes < 0:
            return "resetting soon"
        hours = total_minutes // 60
        minutes = total_minutes % 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return resets_at


def main():
    token = get_oauth_token()
    if not token:
        print("Error: No OAuth token found. Make sure you're logged into Claude Code.")
        sys.exit(1)

    data = fetch_usage(token)
    if not data:
        print("Error: Could not fetch usage data.")
        sys.exit(1)

    print("=== Rate Limits ===\n")

    # Session (5-hour)
    five = data.get("five_hour")
    if five:
        pct = five.get("utilization", 0)
        resets = format_reset(five.get("resets_at"))
        bar_len = 20
        filled = int(pct / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"Session (5h):  [{bar}] {pct:.1f}%")
        print(f"  Resets in: {resets}")
    else:
        print("Session (5h):  no data")

    # Weekly (7-day)
    seven = data.get("seven_day")
    if seven:
        pct = seven.get("utilization", 0)
        resets = format_reset(seven.get("resets_at"))
        bar_len = 20
        filled = int(pct / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"Weekly (7d):   [{bar}] {pct:.1f}%")
        print(f"  Resets in: {resets}")
    else:
        print("Weekly (7d):   no data")

    # Opus (7-day)
    opus = data.get("seven_day_opus")
    if opus:
        pct = opus.get("utilization", 0)
        resets = format_reset(opus.get("resets_at"))
        bar_len = 20
        filled = int(pct / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"Opus (7d):     [{bar}] {pct:.1f}%")
        print(f"  Resets in: {resets}")

    # Output raw JSON for debugging if --json flag passed
    if "--json" in sys.argv:
        print(f"\nRaw: {json.dumps(data, indent=2)}")


if __name__ == "__main__":
    main()
