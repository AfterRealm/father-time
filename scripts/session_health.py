"""
Father Time — Session health checker.
Parses JSONL transcripts to get REAL context usage, token counts, and compaction history.
Usage: python session_health.py [project_path_filter]
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

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

def main():
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

if __name__ == "__main__":
    main()
