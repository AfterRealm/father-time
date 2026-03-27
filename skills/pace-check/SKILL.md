---
name: pace-check
description: Estimate rate limit usage and forecast when you'll hit session limits. Use when asking about rate limits, pacing, token usage, or how much runway you have left.
model: haiku
---

# Pace Check — Rate Limit Forecasting

Help the user understand their rate limit consumption and plan accordingly.

## How Anthropic Limits Work

- **5-hour rolling window**: session limits reset on a rolling basis
- **Weekly limit**: overall cap that doesn't change
- **Peak hours** (weekdays 5am-11am PT): 5-hour limits drain faster
- **Off-peak**: normal drain rate
- **Tier matters**: Free < Pro < Max (Max gets priority allocation)

## What to Estimate

Claude Code doesn't expose exact token counters, but we can estimate based on:

1. **Session duration** — from session_start.txt
2. **Prompt frequency** — how often the user is prompting (from conversation pace)
3. **Work type** — heavy (code gen, multi-file edits, agent spawning) vs light (questions, small edits)
4. **Peak multiplier** — during peak, limits drain ~1.5-2x faster

## Response Format

```
Session: [duration]
Mode: [PEAK / OFF-PEAK]
Estimated pace: [light / moderate / heavy]
Runway: [rough estimate of comfortable remaining time]
Suggestion: [actionable advice]
```

## Pace Categories

**Light** (mostly questions, reading, small edits):
- Off-peak: 8-12+ hours of comfortable use
- Peak: 4-6 hours

**Moderate** (mix of generation and questions, some agent use):
- Off-peak: 4-8 hours
- Peak: 2-4 hours

**Heavy** (constant code gen, multi-file refactors, lots of agents, large context):
- Off-peak: 2-4 hours
- Peak: 1-2 hours

## Tips to Share

- Switch to Sonnet for routine tasks (`/model sonnet`) — uses fewer tokens per response
- Use `/compact` to reduce context size
- Shift heavy work to off-peak hours
- Max tier users are less affected by peak throttling but not immune
- If rate limited: wait 15-30 minutes, limits roll over continuously

## Important

Never make the user anxious about usage. Frame it as helpful information, not a countdown clock. "You're doing great, here's your runway" not "WARNING: you're burning through tokens."
