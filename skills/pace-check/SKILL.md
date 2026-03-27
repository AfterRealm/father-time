---
name: pace-check
description: Check real rate limit usage from the Anthropic API — session (5-hour), weekly, and Opus utilization. Use when asking about rate limits, pacing, token usage, or how much runway you have left.
model: haiku
---

# Pace Check — Rate Limit Status

Show the user their real rate limit usage from the Anthropic API.

## How to Get Real Data

Run the usage check script:
```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/usage_check.py"
```

This fetches real utilization data from `api.anthropic.com/api/oauth/usage` using the user's OAuth token. It returns:
- **Session (5h)** — 5-hour rolling window utilization % and reset time
- **Weekly (7d)** — 7-day utilization % and reset time
- **Opus (7d)** — Opus-specific weekly utilization (if available)

## Response Format

Present the script output clearly. Add context based on the numbers:

```
Rate Limits:
  Session (5h):  [bar] XX% — resets in Xh Xm
  Weekly (7d):   [bar] XX% — resets in Xd Xh
  Opus (7d):     [bar] XX% — resets in Xd Xh
  Peak status:   [PEAK / OFF-PEAK]

[Recommendation based on current usage]
```

## How to Interpret

| Session % | Status | Advice |
|-----------|--------|--------|
| < 30% | Comfortable | Work freely |
| 30-60% | Moderate | Monitor, consider lighter work |
| 60-80% | High | Conserve — switch to Sonnet for routine tasks |
| 80%+ | Critical | Expect throttling soon, wait or do light work |

| Weekly % | Status | Advice |
|----------|--------|--------|
| < 50% | Fine | No concerns |
| 50-80% | Watch it | Pace over remaining days |
| 80%+ | Tight | Conserve until reset |

## Tips to Share When Usage is High

- Switch to Sonnet for routine tasks (`/model sonnet`) — uses fewer tokens
- Use `/compact` to reduce context size
- Shift heavy work to off-peak hours
- If rate limited: wait 15-30 minutes, limits roll over continuously

## Important

If the script fails with "No OAuth token found", the user needs to be logged into Claude Code. Never make the user anxious — frame it as helpful info, not a countdown clock.
