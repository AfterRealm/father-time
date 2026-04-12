"""
Father Time — Session health checker.

Parses Claude Code JSONL transcripts to compute REAL context usage from token
counts, plus pulls rate-limit data from the Anthropic OAuth API. Designed to be
called by an agent (via the session-health and time-menu skills) or directly
from a terminal.

Compliant with agentskills.io "Designing scripts for agentic use" rules:
  - argparse-based --help documents the interface, flags, and exit codes
  - --format human|json supports both human-readable and structured output
  - Diagnostics go to stderr, data goes to stdout
  - Meaningful exit codes (see EXIT CODES section in --help)
  - No interactive prompts
  - --threshold validated as positive integer (no division-by-zero)

Shared helpers (OAuth, cache, formatting, pricing) live in _father_time_lib.py.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Make the shared lib importable regardless of cwd. Claude Code invokes scripts
# with `python "${CLAUDE_PLUGIN_ROOT}/scripts/script.py"` so cwd is the user's
# working directory, NOT the scripts/ directory. Add scripts/ to sys.path
# explicitly so the relative import works in any context.
sys.path.insert(0, str(Path(__file__).parent))

from _father_time_lib import (  # noqa: E402
    PROGRESS_BAR_LENGTH,
    SOURCE_LABELS,
    calc_session_cost,
    fetch_usage_with_fallback,
    format_reset,
    positive_int,
)

# ──────────────────────────────────────────────────────────────────────────
# Exit codes
# ──────────────────────────────────────────────────────────────────────────
EXIT_OK = 0
EXIT_NO_PROJECTS = 1
EXIT_NO_DATA = 2
EXIT_API_ERROR = 3
# 64+ reserved for argparse usage errors


# ──────────────────────────────────────────────────────────────────────────
# Project / session discovery
# ──────────────────────────────────────────────────────────────────────────
def find_claude_projects():
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return []
    return [d for d in base.iterdir() if d.is_dir()]


def find_current_session(project_dir):
    jsonls = list(project_dir.glob("*.jsonl"))
    if not jsonls:
        return None, 0
    jsonls.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    newest = jsonls[0]
    return newest, newest.stat().st_size


# ──────────────────────────────────────────────────────────────────────────
# Transcript analysis
# ──────────────────────────────────────────────────────────────────────────
def analyze_session(jsonl_path):
    """Parse JSONL to get real context usage from actual token counts."""
    try:
        text = jsonl_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"warn: could not read {jsonl_path.name}: {e}", file=sys.stderr)
        return None

    lines = text.split("\n")

    compaction_count = 0
    for line in lines:
        if "compact_boundary" not in line:
            continue
        try:
            entry = json.loads(line.strip())
            if entry.get("subtype") == "compact_boundary":
                compaction_count += 1
        except Exception:
            pass

    last_usage = None
    total_output = 0
    total_input = 0
    total_cache_read = 0
    total_cache_write = 0
    turns = 0
    model = "opus"

    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line.strip())
            msg = entry.get("message", {})
            if msg.get("model", ""):
                m = msg["model"].lower()
                if "opus" in m:
                    model = "opus"
                elif "sonnet" in m:
                    model = "sonnet"
                elif "haiku" in m:
                    model = "haiku"
            if msg.get("usage"):
                u = msg["usage"]
                total_output += u.get("output_tokens", 0)
                total_input += u.get("input_tokens", 0)
                total_cache_read += u.get("cache_read_input_tokens", 0)
                total_cache_write += u.get("cache_creation_input_tokens", 0)
                turns += 1
                last_usage = u
        except Exception:
            pass

    if not last_usage:
        return None

    uncached = last_usage.get("input_tokens", 0)
    cache_read = last_usage.get("cache_read_input_tokens", 0)
    cache_write = last_usage.get("cache_creation_input_tokens", 0)
    current_context = uncached + cache_read + cache_write

    return {
        "current_context": current_context,
        "cache_read": cache_read,
        "cache_write": cache_write,
        "total_output": total_output,
        "total_input": total_input,
        "total_cache_read": total_cache_read,
        "total_cache_write": total_cache_write,
        "turns": turns,
        "compactions": compaction_count,
        "model": model,
    }


def compaction_risk(pct):
    if pct < 30:
        return "Low"
    if pct < 60:
        return "Moderate"
    if pct < 80:
        return "High — consider checkpointing"
    return "Imminent — checkpoint NOW"


# ──────────────────────────────────────────────────────────────────────────
# Formatting (human mode only)
# ──────────────────────────────────────────────────────────────────────────
def format_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_usage_bar(label, pct, resets_at, label_width=15):
    filled = int(pct / 100 * PROGRESS_BAR_LENGTH)
    bar = "\u2588" * filled + "\u2591" * (PROGRESS_BAR_LENGTH - filled)
    return f"  {label:<{label_width}} [{bar}] {pct:.1f}%  (resets in {format_reset(resets_at)})"


# ──────────────────────────────────────────────────────────────────────────
# Output builders (record builder is shared by both formats)
# ──────────────────────────────────────────────────────────────────────────
def build_session_record(project, session_file, size, threshold, stats):
    """Build a per-session record. Always uses a `status` discriminator so JSON
    consumers can branch on `record["status"]` instead of probing for keys."""
    age = datetime.now().timestamp() - session_file.stat().st_mtime
    proj_name = project.name.replace("C--Users-mered-Desktop-", "").replace("-", " ")
    record = {
        "project": proj_name,
        "session_id": session_file.stem,
        "session_path": str(session_file),
        "size_bytes": size,
        "size_human": format_size(size),
        "last_activity_seconds_ago": int(age),
        "status": "ok" if stats else "no_data",
    }
    if stats:
        pct = (stats["current_context"] / threshold) * 100
        cost = calc_session_cost(stats, stats.get("model", "opus"))
        record.update({
            "current_context_tokens": stats["current_context"],
            "context_pct": round(pct, 2),
            "context_threshold": threshold,
            "compaction_risk": compaction_risk(pct),
            "compactions": stats["compactions"],
            "turns": stats["turns"],
            "cache_read_tokens": stats["cache_read"],
            "cache_write_tokens": stats["cache_write"],
            "total_input_tokens": stats["total_input"],
            "total_output_tokens": stats["total_output"],
            "total_cache_read_tokens": stats["total_cache_read"],
            "total_cache_write_tokens": stats["total_cache_write"],
            "estimated_cost_usd": round(cost, 4),
            "model": stats.get("model", "opus"),
        })
    else:
        record["error_message"] = "no usage data found"
    return record


def emit_human(sessions, rate_limits, current_only, rate_source=None):
    if current_only:
        print("=== Current Session ===\n")
    else:
        print("=== Session Health ===\n")

    for r in sessions:
        print(f"Project: {r['project']}")
        print(f"  Session: {r['session_id'][:12]}...jsonl")
        print(f"  JSONL: {r['size_human']}")
        age = r["last_activity_seconds_ago"]
        age_str = (
            "just now"
            if age < 60
            else f"{age // 3600}h {(age % 3600) // 60}m ago"
        )
        print(f"  Last activity: {age_str}")

        if r.get("status") != "ok":
            print(f"  ({r.get('error_message', 'no data')})\n")
            continue

        print(
            f"  Context: {format_tokens(r['current_context_tokens'])} / "
            f"{format_tokens(r['context_threshold'])} ({r['context_pct']:.0f}%)"
        )
        print(f"  Compaction risk: {r['compaction_risk']}")
        print(f"  Compactions so far: {r['compactions']}")
        print(f"  Turns: {r['turns']}")
        print(
            f"  Cache hit: {format_tokens(r['cache_read_tokens'])} read / "
            f"{format_tokens(r['cache_write_tokens'])} write"
        )
        print(
            f"  Total tokens: {format_tokens(r['total_input_tokens'])} in / "
            f"{format_tokens(r['total_output_tokens'])} out"
        )
        print(f"  Est. cost: ${r['estimated_cost_usd']:.2f} ({r['model']})")
        print()

    if rate_limits:
        source_label = SOURCE_LABELS.get(rate_source, rate_source or "?")
        print(f"=== Rate Limits ({source_label}) ===\n")
        five = rate_limits.get("five_hour")
        if five:
            print(format_usage_bar("Session (5h):", five.get("utilization", 0), five.get("resets_at")))
        seven = rate_limits.get("seven_day")
        if seven:
            print(format_usage_bar("Weekly (7d):", seven.get("utilization", 0), seven.get("resets_at")))
        opus = rate_limits.get("seven_day_opus")
        if opus:
            print(format_usage_bar("Opus (7d):", opus.get("utilization", 0), opus.get("resets_at")))
        print()


def emit_json(sessions, rate_limits, threshold, rate_limits_source):
    out = {
        "threshold": threshold,
        "sessions": sessions,
        "rate_limits": rate_limits or {},
        "rate_limits_source": rate_limits_source,
        "generated_at": datetime.now().astimezone().isoformat(),
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


# ──────────────────────────────────────────────────────────────────────────
# Argparse
# ──────────────────────────────────────────────────────────────────────────
def build_parser():
    parser = argparse.ArgumentParser(
        prog="session_health.py",
        description=(
            "Father Time session health checker. Reports current context usage, "
            "compaction risk, token totals, estimated cost, and rate limits for "
            "Claude Code sessions on disk."
        ),
        epilog=(
            "Exit codes:\n"
            "  0  success (data printed; if rate-limit API failed but session\n"
            "     data was found, exits 0 with a stderr warning)\n"
            "  1  no Claude projects found on disk (or filter matched none)\n"
            "  2  no parseable usage data in any session (and no rate limits)\n"
            "  3  rate-limit API error AND no session data AND no cache fallback\n"
            " 64+ argparse usage errors\n\n"
            "JSON output shape:\n"
            "  {\n"
            "    \"threshold\":          int,\n"
            "    \"sessions\":           [<session_record>, ...],\n"
            "    \"rate_limits\":        {five_hour, seven_day, seven_day_opus} | {},\n"
            "    \"rate_limits_source\": \"api\" | \"cache\" | \"stale_cache\" | \"no_token\" | \"api_failed\",\n"
            "    \"generated_at\":       ISO-8601 timestamp\n"
            "  }\n\n"
            "  Each session record always has these base fields:\n"
            "    {\n"
            "      \"project\":                   str,\n"
            "      \"session_id\":                str,\n"
            "      \"session_path\":              str,\n"
            "      \"size_bytes\":                int,\n"
            "      \"size_human\":                str,\n"
            "      \"last_activity_seconds_ago\": int,\n"
            "      \"status\":                    \"ok\" | \"no_data\"\n"
            "    }\n"
            "  When status == \"ok\", the record additionally has:\n"
            "    current_context_tokens, context_pct, context_threshold,\n"
            "    compaction_risk, compactions, turns, cache_read_tokens,\n"
            "    cache_write_tokens, total_input_tokens, total_output_tokens,\n"
            "    total_cache_read_tokens, total_cache_write_tokens,\n"
            "    estimated_cost_usd, model.\n"
            "  When status == \"no_data\", the record has `error_message` instead.\n"
            "  Branch on `status`, never type-check the record itself.\n\n"
            "Examples:\n"
            "  session_health.py --current\n"
            "  session_health.py --format json --current\n"
            "  session_health.py --threshold 800000\n"
            "  session_health.py 'command center'\n"
            "  session_health.py --format json --threshold 1000000 'waevera'\n"
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
        "--current",
        action="store_true",
        help="Only report on the most recently active project (skip the rest).",
    )
    parser.add_argument(
        "--threshold",
        type=positive_int,
        default=1_000_000,
        metavar="TOKENS",
        help="Context threshold in tokens used to compute the percentage and "
             "compaction risk. Must be > 0. Default: 1,000,000.",
    )
    parser.add_argument(
        "project_filter",
        nargs="?",
        default=None,
        help="Optional substring to filter projects by name (case-insensitive).",
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

    projects = find_claude_projects()
    if not projects:
        print("error: no Claude projects found on disk", file=sys.stderr)
        sys.exit(EXIT_NO_PROJECTS)

    if args.project_filter:
        projects = [p for p in projects if args.project_filter.lower() in str(p).lower()]
        if not projects:
            print(f"error: no projects matched filter '{args.project_filter}'", file=sys.stderr)
            sys.exit(EXIT_NO_PROJECTS)

    sorted_projects = sorted(projects, key=lambda p: p.stat().st_mtime, reverse=True)
    if args.current:
        sorted_projects = sorted_projects[:1]

    sessions = []
    any_data = False
    for project in sorted_projects:
        session_file, size = find_current_session(project)
        if not session_file:
            continue
        stats = analyze_session(session_file)
        if stats:
            any_data = True
        sessions.append(build_session_record(project, session_file, size, args.threshold, stats))

    rate_limits, rate_source = fetch_usage_with_fallback()
    api_failed = rate_limits is None

    # ── Decide exit code BEFORE emitting output for the failure cases.
    # Hard failure: no session data AND no rate-limit data → can't help anyone.
    # Branch the error message on rate_source so the user knows the actual cause
    # (no_token vs api_failed) instead of getting a generic "API unavailable".
    if not any_data and api_failed:
        if rate_source == "no_token":
            print(
                "error: no session data found and no OAuth token "
                "(log into Claude Code first)",
                file=sys.stderr,
            )
        else:
            print(
                "error: no session data found and rate-limit API unavailable; "
                "nothing to report",
                file=sys.stderr,
            )
        sys.exit(EXIT_API_ERROR)

    if not any_data and not rate_limits:
        # Rate-limit data came back empty (e.g. cache had stale empty result)
        print("error: no parseable usage data in any session", file=sys.stderr)
        sys.exit(EXIT_NO_DATA)

    # Emit the output we have. Partial success is success.
    if args.format == "json":
        emit_json(sessions, rate_limits, args.threshold, rate_source)
    else:
        emit_human(sessions, rate_limits, args.current, rate_source)

    # Soft failure: rate-limit data missing but session data exists.
    # Still success exit, but warn so the agent/user knows part of the report is incomplete.
    if api_failed and any_data:
        if rate_source == "no_token":
            print(
                "warn: no OAuth token; rate-limit data unavailable, "
                "report contains session data only",
                file=sys.stderr,
            )
        else:
            print(
                "warn: rate-limit API unavailable; report contains session data only",
                file=sys.stderr,
            )

    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
