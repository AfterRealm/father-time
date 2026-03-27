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
    """Shared cache path — same location CC terminal uses."""
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

    # Forecast section
    print("\n=== Forecast ===\n")
    five = data.get("five_hour")
    if five and five.get("utilization", 0) > 0:
        pct = five["utilization"]
        resets_at = five.get("resets_at")
        if resets_at:
            try:
                reset_dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
                now = datetime.now(reset_dt.tzinfo)
                remaining_min = max(0, (reset_dt - now).total_seconds() / 60)
                # How long until 100% at current burn rate
                if pct < 100 and remaining_min > 0:
                    # Rate: pct% used in (300 - remaining_min) minutes
                    elapsed_min = 300 - remaining_min  # 5h window = 300 min
                    if elapsed_min > 0:
                        rate_per_min = pct / elapsed_min
                        mins_to_full = (100 - pct) / rate_per_min if rate_per_min > 0 else float('inf')
                        if mins_to_full < 300:
                            h = int(mins_to_full) // 60
                            m = int(mins_to_full) % 60
                            if h > 0:
                                print(f"  Session limit: ~{h}h {m}m until full at current pace")
                            else:
                                print(f"  Session limit: ~{m}m until full at current pace")
                        else:
                            print(f"  Session limit: unlikely to hit before reset")
                elif pct >= 100:
                    print(f"  Session limit: REACHED — resets in {format_reset(resets_at)}")
            except Exception:
                pass

    seven = data.get("seven_day")
    if seven and seven.get("utilization", 0) > 0:
        pct = seven["utilization"]
        resets_at = seven.get("resets_at")
        if resets_at:
            try:
                reset_dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
                now = datetime.now(reset_dt.tzinfo)
                remaining_hours = max(0, (reset_dt - now).total_seconds() / 3600)
                total_hours = 168  # 7 days
                elapsed_hours = total_hours - remaining_hours
                if elapsed_hours > 0 and pct < 100:
                    rate_per_hour = pct / elapsed_hours
                    hours_to_full = (100 - pct) / rate_per_hour if rate_per_hour > 0 else float('inf')
                    days = int(hours_to_full) // 24
                    hours = int(hours_to_full) % 24
                    if hours_to_full > remaining_hours:
                        print(f"  Weekly limit: unlikely to hit before reset")
                    elif days > 0:
                        print(f"  Weekly limit: ~{days}d {hours}h until full at current pace")
                    else:
                        print(f"  Weekly limit: ~{hours}h until full at current pace")
                elif pct >= 100:
                    print(f"  Weekly limit: REACHED — resets in {format_reset(resets_at)}")
            except Exception:
                pass

    # Burn rate for subscription users
    if seven and seven.get("utilization", 0) > 0:
        pct = seven["utilization"]
        resets_at = seven.get("resets_at")
        if resets_at:
            try:
                reset_dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
                now = datetime.now(reset_dt.tzinfo)
                remaining_hours = max(0, (reset_dt - now).total_seconds() / 3600)
                total_hours = 168
                elapsed_hours = total_hours - remaining_hours
                days_elapsed = elapsed_hours / 24
                days_remaining = remaining_hours / 24
                if days_elapsed > 0:
                    daily_rate = pct / days_elapsed
                    budget_remaining = 100 - pct
                    print(f"\n  Burn rate: {daily_rate:.1f}%/day ({budget_remaining:.0f}% budget left, {days_remaining:.1f} days to reset)")
            except Exception:
                pass

    # Output raw JSON for debugging if --json flag passed
    if "--json" in sys.argv:
        print(f"\nRaw: {json.dumps(data, indent=2)}")


if __name__ == "__main__":
    main()
