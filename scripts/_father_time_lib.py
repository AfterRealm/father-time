"""
Father Time — shared library.

Code reused between session_health.py and usage_check.py:
  - OAuth token discovery
  - Anthropic usage API fetch
  - Usage cache (5-minute TTL, shared file)
  - Time/duration formatting
  - Model pricing table + cost calculation
  - argparse type validators

Both scripts add their parent directory to sys.path and import from this
module, so the shared code lives in one place and bug fixes happen once.
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────
def _read_plugin_version():
    """Read the plugin version from .claude-plugin/plugin.json at module load.

    Falls back to 'unknown' if the file is missing or unreadable. This keeps
    the User-Agent string in sync with the actual plugin version automatically
    so we don't ship stale strings like the previous 'claude-code/2.0.32' bug.
    """
    try:
        plugin_json = Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"
        return json.loads(plugin_json.read_text(encoding="utf-8")).get("version", "unknown")
    except Exception:
        return "unknown"


VERSION = _read_plugin_version()
USER_AGENT = f"father-time/{VERSION} (claude-code-compatible)"

CACHE_MAX_AGE_SECONDS = 300       # 5-minute usage cache TTL
FIVE_HOUR_WINDOW_MINUTES = 300    # Anthropic's 5-hour rate-limit window
SEVEN_DAY_WINDOW_HOURS = 168      # Anthropic's 7-day rate-limit window
PROGRESS_BAR_LENGTH = 20

# Human-readable labels for fetch_usage_with_fallback() source values.
# Both session_health.py and usage_check.py import this so freshness UX is
# consistent across the plugin.
SOURCE_LABELS = {
    "api":         "live",
    "cache":       "cached",
    "stale_cache": "stale cache",
    "no_token":    "no OAuth token",
    "api_failed":  "API failed",
}

# Pricing per 1M tokens. Single source of truth — both session_health.py and
# any future cost-related script should import this rather than redefining.
#
# UPDATE THIS DICT WHEN ANTHROPIC CHANGES PRICING. Bump LAST_VERIFIED below
# when you do, so future readers can tell at a glance whether the table is
# current. Source: https://platform.claude.com/docs/en/about-claude/pricing
#
# Pricing reflects the current Claude 4.x generation:
#   - Opus    = Claude Opus 4.7 / 4.6 ($5 input / $25 output / $0.50 cache read / $6.25 cache write 5m — 4.7 and 4.6 share per-token pricing)
#   - Sonnet  = Claude Sonnet 4.6     ($3 input / $15 output / $0.30 cache read / $3.75 cache write 5m)
#   - Haiku   = Claude Haiku 4.5      ($1 input / $5  output / $0.10 cache read / $1.25 cache write 5m)
#
# Note: Opus 4.7 uses a new tokenizer that can use up to 35% more tokens for the
# same text vs. prior models. Cost-per-token is identical; cost-per-task may be
# slightly higher on 4.7 due to the token count difference.
#
# cache_write is the 5-minute ephemeral tier (1.25x input price). The 1-hour
# tier (2x input price) isn't tracked because Father Time's cost calculations
# only need the standard 5-minute write rate.
MODEL_PRICING_LAST_VERIFIED = "2026-04-17"
MODEL_PRICING = {
    "opus":   {"input": 5.00, "cache_read": 0.50, "cache_write": 6.25, "output": 25.00},
    "sonnet": {"input": 3.00, "cache_read": 0.30, "cache_write": 3.75, "output": 15.00},
    "haiku":  {"input": 1.00, "cache_read": 0.10, "cache_write": 1.25, "output":  5.00},
}


# ──────────────────────────────────────────────────────────────────────────
# argparse helpers
# ──────────────────────────────────────────────────────────────────────────
def positive_int(value):
    """argparse type validator: int > 0."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"must be an integer, got {value!r}")
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {n}")
    return n


# ──────────────────────────────────────────────────────────────────────────
# Cost calculation
# ──────────────────────────────────────────────────────────────────────────
def calc_session_cost(stats, model="opus"):
    """Estimate session cost from token totals using MODEL_PRICING."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["opus"])
    cost = 0.0
    cost += (stats["total_input"] / 1_000_000) * pricing["input"]
    cost += (stats["total_cache_read"] / 1_000_000) * pricing["cache_read"]
    cost += (stats["total_cache_write"] / 1_000_000) * pricing["cache_write"]
    cost += (stats["total_output"] / 1_000_000) * pricing["output"]
    return cost


# ──────────────────────────────────────────────────────────────────────────
# Time formatting
# ──────────────────────────────────────────────────────────────────────────
def format_reset(resets_at):
    """Format an ISO timestamp into a 'Xh Ym' relative string."""
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


# ──────────────────────────────────────────────────────────────────────────
# Usage cache (shared file with the Claude Code terminal)
# ──────────────────────────────────────────────────────────────────────────
def get_cache_path():
    return Path.home() / ".claude" / "usage_cache.json"


def read_usage_cache(allow_stale=False):
    """Return cached usage data if fresh enough, or always when allow_stale=True."""
    cache_path = get_cache_path()
    try:
        if not cache_path.exists():
            return None
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        age = int(time.time() - data.get("fetched_at", 0))
        if allow_stale or age < CACHE_MAX_AGE_SECONDS:
            data["_from_cache"] = True
            data["_cache_age"] = age
            return data
    except Exception:
        pass
    return None


def write_usage_cache(data):
    """Persist usage data to the shared cache file. Strips in-memory markers."""
    cache_path = get_cache_path()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        clean = {k: v for k, v in data.items() if not k.startswith("_")}
        clean["fetched_at"] = time.time()
        cache_path.write_text(json.dumps(clean), encoding="utf-8")
    except Exception as e:
        print(f"warn: failed to write usage cache: {e}", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────────
# OAuth + API
# ──────────────────────────────────────────────────────────────────────────
def get_oauth_token():
    """Find the OAuth access token from any of the known credential locations."""
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


def fetch_usage_from_api(token):
    """Hit the Anthropic OAuth usage endpoint. Returns parsed dict or None on failure.

    Distinguishes HTTP errors (4xx/5xx) from network/parse failures via stderr
    diagnostics, but always returns None on failure so callers can decide whether
    to fall back to cache or exit with an error.
    """
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"error: usage API returned HTTP {e.code}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"error: usage API network failure: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"error: usage API fetch failed: {e}", file=sys.stderr)
        return None


def fetch_usage_with_fallback(force_refresh: bool = False):
    """Cache → API → stale cache. Returns (data, source_label).

    When force_refresh=True:
      - the fresh cache check is skipped (we go straight to the API)
      - on no-token failure, we DO NOT fall back to stale cache. Returning stale
        data when the user explicitly asked for fresh data would be misleading.
      - on API failure (with valid token), stale cache fallback still applies
        because the user wanted fresh data and the network couldn't deliver,
        so a warning + stale data beats nothing.

    Source labels:
        cache         — fresh cache hit (only when force_refresh=False)
        api           — live fetch from API, cached for next call
        stale_cache   — API failed, fell back to expired cache
        no_token      — no OAuth credential found anywhere
        api_failed    — API failed AND no cache fallback available

    Callers can map source labels to exit codes for distinct failure modes.
    """
    if not force_refresh:
        cached = read_usage_cache()
        if cached:
            return cached, "cache"

    token = get_oauth_token()
    if not token:
        if force_refresh:
            # User explicitly asked for fresh data; do NOT silently return stale.
            # They need to know the OAuth token is missing so they can fix it.
            return None, "no_token"
        # Implicit fetch (no --refresh): stale cache is better than nothing.
        stale = read_usage_cache(allow_stale=True)
        if stale:
            print("warn: no OAuth token; using stale cache", file=sys.stderr)
            return stale, "stale_cache"
        return None, "no_token"

    fresh = fetch_usage_from_api(token)
    if fresh:
        write_usage_cache(fresh)
        return fresh, "api"

    stale = read_usage_cache(allow_stale=True)
    if stale:
        print("warn: API unavailable, falling back to stale cache", file=sys.stderr)
        return stale, "stale_cache"
    return None, "api_failed"
