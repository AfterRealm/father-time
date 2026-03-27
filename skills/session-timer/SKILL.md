---
name: session-timer
description: Check how long the current session has been running. Use when asking about session length, duration, or whether it's time to checkpoint.
---

# Session Timer

Show the user how long their current Claude Code session has been active.

## How It Works

The `SessionStart` hook writes a timestamp to `${CLAUDE_PLUGIN_DATA}/session_start.txt` when the session begins. The `UserPromptSubmit` hook calculates elapsed time on every prompt and includes it in the time injection.

## What to Show

1. **Session duration** — hours and minutes since session start
2. **Checkpoint suggestion** — if over 2 hours, suggest checkpointing state
3. **Context health** — longer sessions use more context. After 3+ hours, suggest `/compact` if context is getting heavy.

## Response Format

Short and direct:
- "Session: 1h 23m. No action needed."
- "Session: 3h 45m. Consider checkpointing or compacting if things feel sluggish."
- "Session: 6h+. Marathon territory. Your context might benefit from a `/compact`."

## Milestone Nudges (Optional)

If the user has been going for a while, a brief note is fine:
- **2 hours**: "2 hours in. Good checkpoint moment if you want to save state."
- **4 hours**: "4 hours. Your context window is holding up but a checkpoint preserves your progress."
- **6+ hours**: "6+ hours. Legendary session. Checkpoint highly recommended."

These are suggestions, not demands. Never block the user from working.
