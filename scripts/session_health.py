"""
Father Time — Session health checker.
Parses JSONL transcripts to get REAL context usage, token counts, and compaction history.
Usage: python session_health.py [project_path_filter]
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

CACHE_MAX_AGE = 300  # 5 minutes

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

def analyze_session(jsonl_path):
    """Parse JSONL to get real context usage from actual token counts."""
    try:
        text = jsonl_path.read_text(encoding='utf-8')
    except Exception:
        return None

    lines = text.split('\n')

    # Find compaction boundaries
    compaction_count = 0
    last_compact_idx = 0
    for i, line in enumerate(lines):
        if 'compact_boundary' not in line:
            continue
        try:
            entry = json.loads(line.strip())
            if entry.get('subtype') == 'compact_boundary':
                compaction_count += 1
                last_compact_idx = i + 1
        except Exception:
            pass

    # Get usage from the last assistant message (= current context size)
    last_usage = None
    total_output = 0
    total_input = 0
    total_cache_read = 0
    total_cache_write = 0
    turns = 0

    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line.strip())
            if entry.get('message', {}).get('usage'):
                u = entry['message']['usage']
                total_output += u.get('output_tokens', 0)
                total_input += u.get('input_tokens', 0)
                total_cache_read += u.get('cache_read_input_tokens', 0)
                total_cache_write += u.get('cache_creation_input_tokens', 0)
                turns += 1
                last_usage = u
        except Exception:
            pass

    if not last_usage:
        return None

    # Current context = total input sent on last turn:
    # input_tokens (uncached) + cache_read + cache_creation = full context size
    uncached = last_usage.get('input_tokens', 0)
    cache_read = last_usage.get('cache_read_input_tokens', 0)
    cache_write = last_usage.get('cache_creation_input_tokens', 0)
    current_context = uncached + cache_read + cache_write

    # context_pct calculated by caller with user-specified threshold
    context_pct = None

    return {
        'current_context': current_context,
        'context_pct': context_pct,
        'cache_read': cache_read,
        'cache_write': cache_write,
        'total_output': total_output,
        'total_input': total_input,
        'total_cache_read': total_cache_read,
        'total_cache_write': total_cache_write,
        'turns': turns,
        'compactions': compaction_count,
    }

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

def compaction_risk(pct):
    if pct < 30: return "Low"
    if pct < 60: return "Moderate"
    if pct < 80: return "High — consider checkpointing"
    return "Imminent — checkpoint NOW"

def parse_args():
    """Parse CLI args: optional --threshold N and optional project filter."""
    threshold = 1_000_000
    project_filter = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--threshold' and i + 1 < len(args):
            threshold = int(args[i + 1])
            i += 2
        else:
            project_filter = args[i]
            i += 1
    return threshold, project_filter

def get_cache_path():
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return Path(plugin_data) / "usage_cache.json"
    return Path.home() / ".claude" / "usage_cache.json"

def read_usage_cache():
    cache_path = get_cache_path()
    try:
        if not cache_path.exists():
            return None
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        age = time.time() - data.get("fetched_at", 0)
        if age < CACHE_MAX_AGE:
            return data
        return None
    except Exception:
        return None

def read_stale_cache():
    cache_path = get_cache_path()
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None

def write_usage_cache(data):
    cache_path = get_cache_path()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        data["fetched_at"] = time.time()
        cache_path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass

def get_oauth_token():
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

def fetch_usage():
    """Fetch rate limit data — cache first, API fallback, stale cache last resort."""
    cached = read_usage_cache()
    if cached:
        return cached
    token = get_oauth_token()
    if not token:
        return read_stale_cache()
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
            data = json.loads(resp.read().decode())
            write_usage_cache(data)
            return data
    except Exception:
        return read_stale_cache()

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

def format_usage_bar(label, pct, resets_at, label_width=15):
    """Format a single usage bar line."""
    bar_len = 20
    filled = int(pct / 100 * bar_len)
    bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
    reset_str = format_reset(resets_at)
    return f"  {label:<{label_width}} [{bar}] {pct:.1f}%  (resets in {reset_str})"

def main():
    # Fix Windows encoding
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    projects = find_claude_projects()
    if not projects:
        print("No Claude projects found.")
        return

    threshold, project_filter = parse_args()
    if project_filter:
        projects = [p for p in projects if project_filter.lower() in str(p).lower()]

    print("=== Session Health ===\n")

    for project in sorted(projects, key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        session_file, size = find_current_session(project)
        if not session_file:
            continue

        age = datetime.now().timestamp() - session_file.stat().st_mtime
        age_str = f"{int(age // 3600)}h {int((age % 3600) // 60)}m ago" if age > 60 else "just now"
        proj_name = project.name.replace("C--Users-mered-Desktop-", "").replace("-", " ")

        stats = analyze_session(session_file)

        print(f"Project: {proj_name}")
        print(f"  Session: {session_file.name[:12]}...{session_file.suffix}")
        print(f"  JSONL: {format_size(size)}")
        print(f"  Last activity: {age_str}")

        if stats:
            pct = (stats['current_context'] / threshold) * 100
            print(f"  Context: {format_tokens(stats['current_context'])} / {format_tokens(threshold)} ({pct:.0f}%)")
            print(f"  Compaction risk: {compaction_risk(pct)}")
            print(f"  Compactions so far: {stats['compactions']}")
            print(f"  Turns: {stats['turns']}")
            print(f"  Cache hit: {format_tokens(stats['cache_read'])} read / {format_tokens(stats['cache_write'])} write")
            print(f"  Total tokens: {format_tokens(stats['total_input'])} in / {format_tokens(stats['total_output'])} out")
        else:
            print(f"  (no usage data found)")
        print()

    # Rate limits section
    usage = fetch_usage()
    if usage:
        print("=== Rate Limits ===\n")
        five = usage.get("five_hour")
        if five:
            print(format_usage_bar("Session (5h):", five.get("utilization", 0), five.get("resets_at")))
        seven = usage.get("seven_day")
        if seven:
            print(format_usage_bar("Weekly (7d):", seven.get("utilization", 0), seven.get("resets_at")))
        opus = usage.get("seven_day_opus")
        if opus:
            print(format_usage_bar("Opus (7d):", opus.get("utilization", 0), opus.get("resets_at")))
        print()

if __name__ == "__main__":
    main()
