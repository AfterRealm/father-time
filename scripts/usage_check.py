"""
Father Time — Usage check.

Fetches real rate-limit data from the Anthropic OAuth API. Returns 5-hour
session, 7-day weekly, and Opus-specific utilization with reset timers and
a burn-rate forecast. Caches results for 5 minutes to avoid hammering the API.

Compliant with agentskills.io "Designing scripts for agentic use" rules:
  - argparse-based --help documents the interface, flags, and exit codes
  - --format human|json supports both human-readable and structured output
  - Diagnostics go to stderr, data goes to stdout
  - Meaningful exit codes (see EXIT CODES section in --help)
  - No interactive prompts
  - Forecast fields always return a consistent dict shape with a `status` key
    (no polymorphic string-or-dict ambiguity for JSON consumers)

Shared helpers (OAuth, cache, formatting) live in _father_time_lib.py.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Make the shared lib importable regardless of cwd.
sys.path.insert(0, str(Path(__file__).parent))

from _father_time_lib import (  # noqa: E402
    FIVE_HOUR_WINDOW_MINUTES,
    PROGRESS_BAR_LENGTH,
    SEVEN_DAY_WINDOW_HOURS,
    SOURCE_LABELS,
    fetch_usage_with_fallback,
    format_reset,
)

# ──────────────────────────────────────────────────────────────────────────
# Exit codes
# ──────────────────────────────────────────────────────────────────────────
EXIT_OK = 0
EXIT_NO_TOKEN = 1
EXIT_API_FAILED = 2
# 64+ reserved for argparse usage errors


# ──────────────────────────────────────────────────────────────────────────
# Forecast computation (data-only, no formatting)
# ──────────────────────────────────────────────────────────────────────────
# Forecast field shape (consistent across both window types):
#
#   {
#     "status": "ok" | "reached" | "unlikely_before_reset" | "idle" | "no_data",
#     "minutes_to_full": int | None,   # only set when status == "ok"
#     "hours_to_full":   float | None, # only set when status == "ok"
#   }
#
# Status meanings:
#   - "ok"                     — burn rate computed; field has minutes/hours_to_full
#   - "reached"                — utilization is at or past 100%
#   - "unlikely_before_reset"  — at current pace, won't hit 100% before window resets
#   - "idle"                   — utilization is exactly 0%, no burn rate to forecast
#   - "no_data"                — API returned nothing for this window (or parse error)
#
# Agents always see the same keys. Branch on `status`, never type-check the field.
def _empty_forecast_field():
    return {"status": "no_data", "minutes_to_full": None, "hours_to_full": None}


def _idle_forecast_field():
    return {"status": "idle", "minutes_to_full": None, "hours_to_full": None}


def compute_forecast(data):
    forecast = {
        "session_5h": _empty_forecast_field(),
        "weekly_7d": _empty_forecast_field(),
        "burn_rate_pct_per_day": None,
        "budget_remaining_pct": None,
        "days_to_weekly_reset": None,
    }

    # ── 5-hour window
    five = data.get("five_hour")
    if five is not None:
        pct = five.get("utilization", 0)
        resets_at = five.get("resets_at")
        if pct == 0:
            forecast["session_5h"] = _idle_forecast_field()
        elif pct < 0:
            # Garbage from API; treat as no_data
            pass
        elif resets_at:
            try:
                reset_dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
                now = datetime.now(reset_dt.tzinfo)
                remaining_min = max(0, (reset_dt - now).total_seconds() / 60)
                if pct >= 100:
                    forecast["session_5h"] = {
                        "status": "reached",
                        "minutes_to_full": 0,
                        "hours_to_full": 0.0,
                    }
                elif remaining_min > 0:
                    elapsed_min = FIVE_HOUR_WINDOW_MINUTES - remaining_min
                    if elapsed_min > 0:
                        rate_per_min = pct / elapsed_min
                        if rate_per_min > 0:
                            mins_to_full = (100 - pct) / rate_per_min
                            if mins_to_full < remaining_min:
                                forecast["session_5h"] = {
                                    "status": "ok",
                                    "minutes_to_full": int(mins_to_full),
                                    "hours_to_full": round(mins_to_full / 60, 2),
                                }
                            else:
                                forecast["session_5h"] = {
                                    "status": "unlikely_before_reset",
                                    "minutes_to_full": None,
                                    "hours_to_full": None,
                                }
            except Exception:
                pass

    # ── 7-day window
    seven = data.get("seven_day")
    if seven is not None:
        pct = seven.get("utilization", 0)
        resets_at = seven.get("resets_at")
        if pct == 0:
            # User hasn't burned anything yet — emit explicit zeros so JSON
            # consumers can distinguish "0% used" from "data missing"
            forecast["weekly_7d"] = _idle_forecast_field()
            forecast["burn_rate_pct_per_day"] = 0.0
            forecast["budget_remaining_pct"] = 100.0
            if resets_at:
                try:
                    reset_dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
                    now = datetime.now(reset_dt.tzinfo)
                    remaining_hours = max(0, (reset_dt - now).total_seconds() / 3600)
                    forecast["days_to_weekly_reset"] = round(remaining_hours / 24, 2)
                except Exception:
                    pass
        elif pct < 0:
            # Garbage from API; treat as no_data
            pass
        elif resets_at:
            try:
                reset_dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
                now = datetime.now(reset_dt.tzinfo)
                remaining_hours = max(0, (reset_dt - now).total_seconds() / 3600)
                elapsed_hours = SEVEN_DAY_WINDOW_HOURS - remaining_hours
                if pct >= 100:
                    forecast["weekly_7d"] = {
                        "status": "reached",
                        "minutes_to_full": 0,
                        "hours_to_full": 0.0,
                    }
                elif elapsed_hours > 0:
                    rate_per_hour = pct / elapsed_hours
                    if rate_per_hour > 0:
                        hours_to_full = (100 - pct) / rate_per_hour
                        if hours_to_full > remaining_hours:
                            forecast["weekly_7d"] = {
                                "status": "unlikely_before_reset",
                                "minutes_to_full": None,
                                "hours_to_full": None,
                            }
                        else:
                            forecast["weekly_7d"] = {
                                "status": "ok",
                                "minutes_to_full": int(hours_to_full * 60),
                                "hours_to_full": round(hours_to_full, 2),
                            }

                # Burn-rate metrics (only meaningful when pct > 0; the pct == 0
                # branch above populates these explicitly with zero/full values)
                days_elapsed = elapsed_hours / 24
                if days_elapsed > 0:
                    forecast["burn_rate_pct_per_day"] = round(pct / days_elapsed, 2)
                    forecast["budget_remaining_pct"] = round(100 - pct, 2)
                    forecast["days_to_weekly_reset"] = round(remaining_hours / 24, 2)
            except Exception:
                pass

    return forecast


# ──────────────────────────────────────────────────────────────────────────
# Output (human + JSON)
# ──────────────────────────────────────────────────────────────────────────
def _bar_line(label, slot):
    if not slot:
        print(f"{label}  no data")
        return
    pct = slot.get("utilization", 0)
    filled = int(pct / 100 * PROGRESS_BAR_LENGTH)
    bar = "\u2588" * filled + "\u2591" * (PROGRESS_BAR_LENGTH - filled)
    print(f"{label}  [{bar}] {pct:.1f}%")
    print(f"  Resets in: {format_reset(slot.get('resets_at'))}")


def _human_forecast_line(label, field):
    status = field["status"]
    if status == "reached":
        print(f"  {label}: REACHED")
    elif status == "unlikely_before_reset":
        print(f"  {label}: unlikely to hit before reset")
    elif status == "idle":
        print(f"  {label}: idle (0% used, no burn rate to forecast)")
    elif status == "ok":
        m = field["minutes_to_full"]
        if m is None:
            return
        h = m // 60
        mm = m % 60
        if h >= 24:
            d = h // 24
            hh = h % 24
            print(f"  {label}: ~{d}d {hh}h until full at current pace")
        elif h > 0:
            print(f"  {label}: ~{h}h {mm}m until full at current pace")
        else:
            print(f"  {label}: ~{mm}m until full at current pace")
    # status == "no_data" → print nothing


def emit_human(data, forecast, source=None):
    """Print the human-readable report.

    Uses the same SOURCE_LABELS lookup as session_health.py so freshness
    UX is consistent across the plugin. Includes cache age detail when
    available because usage_check is the canonical "how fresh is my data"
    tool.
    """
    source_label = SOURCE_LABELS.get(source, source or "?")
    from_cache = data.get("_from_cache")
    cache_age = data.get("_cache_age", 0)
    if from_cache:
        print(f"=== Rate Limits ({source_label}, {cache_age}s old) ===\n")
    else:
        print(f"=== Rate Limits ({source_label}) ===\n")

    _bar_line("Session (5h):", data.get("five_hour"))
    _bar_line("Weekly (7d): ", data.get("seven_day"))
    opus = data.get("seven_day_opus")
    if opus:
        _bar_line("Opus (7d):   ", opus)

    print("\n=== Forecast ===\n")
    _human_forecast_line("Session limit", forecast["session_5h"])
    _human_forecast_line("Weekly limit", forecast["weekly_7d"])

    if forecast.get("burn_rate_pct_per_day") is not None:
        print(
            f"\n  Burn rate: {forecast['burn_rate_pct_per_day']:.1f}%/day "
            f"({forecast['budget_remaining_pct']:.0f}% budget left, "
            f"{forecast['days_to_weekly_reset']:.1f} days to reset)"
        )


def emit_json(data, forecast):
    out = {
        "fetched_at": datetime.now().astimezone().isoformat(),
        "from_cache": bool(data.get("_from_cache")),
        "cache_age_seconds": data.get("_cache_age") if data.get("_from_cache") else None,
        "five_hour": data.get("five_hour"),
        "seven_day": data.get("seven_day"),
        "seven_day_opus": data.get("seven_day_opus"),
        "forecast": forecast,
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


# ──────────────────────────────────────────────────────────────────────────
# Argparse
# ──────────────────────────────────────────────────────────────────────────
def build_parser():
    parser = argparse.ArgumentParser(
        prog="usage_check.py",
        description=(
            "Father Time usage checker. Fetches Anthropic rate-limit data "
            "(session 5h, weekly 7d, Opus 7d) plus a burn-rate forecast. "
            "Caches results for 5 minutes to avoid API hammering."
        ),
        epilog=(
            "Exit codes:\n"
            "  0  success\n"
            "  1  no OAuth token found (not logged into Claude Code?)\n"
            "  2  API fetch failed AND no cache fallback available\n"
            " 64+ argparse usage errors\n\n"
            "JSON forecast field shape:\n"
            "  Each forecast field (session_5h, weekly_7d) is always an object\n"
            "  with the same keys:\n"
            "    {\n"
            "      \"status\": \"ok\" | \"reached\" | \"unlikely_before_reset\" | \"idle\" | \"no_data\",\n"
            "      \"minutes_to_full\": int | null,\n"
            "      \"hours_to_full\":   float | null\n"
            "    }\n"
            "  Status meanings:\n"
            "    ok                    — burn rate computed; minutes/hours_to_full set\n"
            "    reached               — utilization >= 100%\n"
            "    unlikely_before_reset — won't hit 100% before window resets\n"
            "    idle                  — 0% used, no burn rate to forecast\n"
            "    no_data               — API returned nothing for this window\n"
            "  Branch on `status`, never type-check the field itself.\n\n"
            "Examples:\n"
            "  usage_check.py\n"
            "  usage_check.py --refresh\n"
            "  usage_check.py --format json\n"
            "  usage_check.py --refresh --format json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--format",
        choices=["human", "json"],
        default="human",
        help="Output format. 'human' (default) prints a formatted report. "
             "'json' emits a structured object on stdout for programmatic consumption.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force a fresh fetch from the API, ignoring the cache.",
    )
    return parser


def main():
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = build_parser()
    args = parser.parse_args()

    # Single source of truth: lib's fetch_usage_with_fallback handles
    # cache → API → stale-cache → no-token-fallback. We map source labels
    # to exit codes for distinct failure reporting.
    data, source = fetch_usage_with_fallback(force_refresh=args.refresh)
    if data is None:
        if source == "no_token":
            print(
                "error: no OAuth token found — make sure you're logged into Claude Code",
                file=sys.stderr,
            )
            sys.exit(EXIT_NO_TOKEN)
        # source == "api_failed"
        print(
            "error: usage API failed and no cache fallback available",
            file=sys.stderr,
        )
        sys.exit(EXIT_API_FAILED)

    forecast = compute_forecast(data)

    if args.format == "json":
        emit_json(data, forecast)
    else:
        emit_human(data, forecast, source)

    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
