---
name: session-health
description: Check your current session's health — real context usage from JSONL token data, compaction proximity, session weight, and rate limit status. Use when asking about session size, compaction, context window, or rate limits.
---

# Session Health Check

Show the user real session health data — not estimates. Parse actual token counts from the JSONL transcript.

## How to Get Real Data

Run the session health script:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/session_health.py"
```

For a specific project:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/session_health.py" "project-name-fragment"
```

To override the compaction threshold (default 1M):
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/session_health.py" --threshold 800000
```

Combined:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/session_health.py" --threshold 800000 "project-name-fragment"
```

The script parses JSONL transcripts and reads actual `usage` blocks from API responses to get:
- **Real context usage** — `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` from the last assistant turn = actual context window size
- **JSONL file size** — total transcript weight
- **Compaction count** — how many `compact_boundary` markers exist
- **Turn count** — total assistant responses
- **Cache efficiency** — cache read vs write tokens
- **Total tokens** — cumulative input and output across the session

## How Context Is Calculated

The JSONL contains usage data on every assistant message:
```json
"usage": {
  "input_tokens": 42,
  "output_tokens": 1500,
  "cache_read_input_tokens": 450000,
  "cache_creation_input_tokens": 2000
}
```

**Real context size = input_tokens + cache_read + cache_creation** from the last turn. This is the actual number of tokens sent to the API, which equals the current context window usage.

The default context window is 1M (Opus 4.6), but compaction may trigger earlier depending on the user's settings.

- **context_pct = real_context / threshold × 100**
- Default threshold: 1,000,000 tokens
- Users can specify their compaction threshold via `--threshold`

No guessing. No heuristics. Real numbers from the API.

## Compaction Threshold

Different users have different compaction thresholds. If the user tells you their compaction threshold (e.g., "my compaction is at 800K"), pass it via the `--threshold` flag. If they don't specify, use the default (1M).

Ask the user for their threshold if the percentages seem off or if they mention their numbers don't match.

## Compaction Risk

| Context % | Risk | Action |
|-----------|------|--------|
| < 30% | Low | All clear |
| 30-60% | Moderate | Healthy, keep going |
| 60-80% | High | Consider checkpointing |
| 80%+ | Imminent | Checkpoint NOW, compaction incoming |

## Response Format

```
Session Health:
  JSONL: [size]
  Context: [tokens] / [threshold] ([pct]%)
  Compaction risk: [Low / Moderate / High / Imminent]
  Compactions so far: [count]
  Turns: [count]
  Cache: [read] read / [write] write
  Peak status: [PEAK / OFF-PEAK]

[Recommendation if anything needs attention]
```

## When to Warn

- **Context > 70%**: "Checkpoint your progress — compaction is approaching."
- **Context > 85%**: "Compaction is imminent. Checkpoint NOW."
- **0 compactions + high context**: "First compaction hasn't happened yet — after it fires, older context will be summarized."
- **Multiple compactions**: "This session has compacted [N] times. Context is being managed but consider starting fresh for complex new work."
- **Everything healthy**: "Session looks good. Carry on."
