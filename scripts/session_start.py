"""
Father Time — Session start hook.
Records the session start timestamp and logs activity for pattern tracking.
"""
import os
import json
from datetime import datetime
from pathlib import Path

def main():
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    if not data_dir:
        print("Session timer: no CLAUDE_PLUGIN_DATA available")
        return

    os.makedirs(data_dir, exist_ok=True)

    # Record session start time
    start_file = os.path.join(data_dir, "session_start.txt")
    with open(start_file, 'w') as f:
        f.write(str(datetime.now().timestamp()))

    # Log activity pattern
    patterns_file = os.path.join(data_dir, "activity_patterns.json")
    patterns = []
    if os.path.exists(patterns_file):
        try:
            with open(patterns_file, 'r') as f:
                patterns = json.load(f)
        except Exception:
            patterns = []

    now = datetime.now().astimezone()
    patterns.append({
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "weekday": now.strftime("%A"),
        "hour": now.hour,
    })

    # Keep last 200 entries
    patterns = patterns[-200:]

    with open(patterns_file, 'w') as f:
        json.dump(patterns, f, indent=2)

    print(f"Session started at {now.strftime('%I:%M %p %Z')}")

if __name__ == "__main__":
    main()
