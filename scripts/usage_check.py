"""
Father Time — Usage check.
Fetches real rate limit data from the Anthropic OAuth API.
Returns session (5-hour), weekly (7-day), and Opus-specific utilization.
Caches results to avoid API rate limits. Use --refresh to force a fresh fetch.
"""
import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
import time

# Fix Windows encoding for Unicode output
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

CACHE_MAX_AGE = 300  # 5 minutes


def get_cache_path():
    """Get the cache file path in plugin data dir or fallback to temp."""
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return Path(plugin_data) / "usage_cache.json"
    return Path.home() / ".claude" / "usage_cache.json"


def read_cache():
    """Read cached usage data if fresh enough."""
    cache_path = get_cache_path()
    try:
        if not cache_path.exists():
            return None
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        age = time.time() - data.get("fetched_at", 0)
        if age < CACHE_MAX_AGE:
            data["_from_cache"] = True
            data["_cache_age"] = int(age)
            return data
    except Exception:
        pass
    return None


def write_cache(data):
    """Write usage data to cache file."""
    cache_path = get_cache_path()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        data["fetched_at"] = time.time()
        cache_path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


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
    force_refresh = "--refresh" in sys.argv

    # Try cache first (unless --refresh)
    data = None
    from_cache = False
    if not force_refresh:
        cached = read_cache()
        if cached:
            data = cached
            from_cache = True

    # Fetch from API if no cache
    if not data:
        token = get_oauth_token()
        if not token:
            print("Error: No OAuth token found. Make sure you're logged into Claude Code.")
            sys.exit(1)

        data = fetch_usage(token)
        if data:
            write_cache(data)
        else:
            # API failed — try stale cache as fallback
            stale = read_cache() if not force_refresh else None
            if not stale:
                # Try reading cache ignoring age
                cache_path = get_cache_path()
                try:
                    stale = json.loads(cache_path.read_text(encoding="utf-8"))
                    stale["_from_cache"] = True
                    stale["_cache_age"] = int(time.time() - stale.get("fetched_at", 0))
                except Exception:
                    stale = None
            if stale:
                data = stale
                from_cache = True
                print("(API unavailable — showing cached data)\n", file=sys.stderr)
            else:
                print("Error: Could not fetch usage data.")
                sys.exit(1)

    # Header
    if from_cache:
        age = data.get("_cache_age", 0)
        print(f"=== Rate Limits === (cached {age}s ago)\n")
    else:
        print("=== Rate Limits === (live)\n")

    # Session (5-hour)
    five = data.get("five_hour")
    if five:
        pct = five.get("utilization", 0)
        resets = format_reset(five.get("resets_at"))
        bar_len = 20
        filled = int(pct / 100 * bar_len)
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
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
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
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
        bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
        print(f"Opus (7d):     [{bar}] {pct:.1f}%")
        print(f"  Resets in: {resets}")

    # Output raw JSON for debugging if --json flag passed
    if "--json" in sys.argv:
        print(f"\nRaw: {json.dumps(data, indent=2)}")


if __name__ == "__main__":
    main()
