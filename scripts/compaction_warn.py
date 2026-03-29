"""
Father Time — Compaction warning.
Runs on UserPromptSubmit to warn when context usage is getting high.
Designed to be fast — only reads the tail of the JSONL to find the last usage block.
"""
import os
import sys
import json
from pathlib import Path


def find_active_session():
    """Find the most recently modified JSONL in any project."""
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return None
    newest = None
    newest_mtime = 0
    for project_dir in base.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl in project_dir.glob("*.jsonl"):
            mtime = jsonl.stat().st_mtime
            if mtime > newest_mtime:
                newest = jsonl
                newest_mtime = mtime
    return newest


def get_last_usage(jsonl_path):
    """Read the last usage block from JSONL — reads from end for speed."""
    try:
        size = jsonl_path.stat().st_size
        # Read last 50KB — enough to find the most recent usage block
        read_size = min(size, 50000)
        with open(jsonl_path, "r", encoding="utf-8") as f:
            if size > read_size:
                f.seek(size - read_size)
                f.readline()  # skip partial line
            lines = f.readlines()

        # Search backwards for last usage
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                usage = entry.get("message", {}).get("usage")
                if usage:
                    return usage
            except Exception:
                continue
    except Exception:
        pass
    return None


def main():
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    if data_dir and os.path.exists(os.path.join(data_dir, "time_inject_disabled")):
        return

    session = find_active_session()
    if not session:
        return

    usage = get_last_usage(session)
    if not usage:
        return

    # Calculate context size
    input_tokens = usage.get("input_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)
    context = input_tokens + cache_read + cache_write

    # Default threshold 1M
    threshold = 1_000_000
    pct = (context / threshold) * 100

    if pct >= 85:
        print(f"COMPACTION IMMINENT — context at {pct:.0f}% ({context:,} / {threshold:,} tokens). Checkpoint NOW!")
    elif pct >= 75:
        print(f"Context warning — {pct:.0f}% used ({context:,} / {threshold:,} tokens). Consider checkpointing soon.")
    elif pct >= 60:
        print(f"Context at {pct:.0f}% — getting up there. Keep an eye on it.")
    # Below 60%: silence


if __name__ == "__main__":
    main()
