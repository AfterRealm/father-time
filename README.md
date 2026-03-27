# Father Time — Time-Aware Agent for Claude Code

Claude Code doesn't know what time it is. Father Time fixes that.

A plugin that gives Claude persistent time awareness — peak hour warnings, session tracking, rate limit forecasting, activity pattern learning, focus timers, and daily briefings. Built for the post-throttle era.

## Why

On March 26, 2026, Anthropic announced adjusted session limits during peak hours. Your 5-hour session limits now drain faster on weekdays between 5am-11am PT. Father Time helps you work around that.

But it's more than peak hours. Claude has no concept of time between prompts. It doesn't know if you've been working for 10 minutes or 10 hours. It doesn't know if it's Monday morning or Saturday midnight. Father Time gives it that context on every single prompt.

## What's Included

### Hook: Time Injection
Every prompt is automatically injected with:
- Current local time with timezone
- Pacific Time reference
- Peak hour status (PEAK / OFF-PEAK) with countdown
- Session duration

### Agent: Father Time
A time-aware assistant that can answer questions about scheduling, pacing, and work patterns.

### Skills

| Skill | What It Does |
|-------|-------------|
| `/father-time:time-menu` | Interactive menu — pick from all capabilities below via a guided selector. |
| `/father-time:peak-hours` | Am I in Anthropic's throttle window? Full timezone table included. |
| `/father-time:session-timer` | How long has this session been running? Checkpoint suggestions at milestones. |
| `/father-time:daily-brief` | Morning briefing — peak status, schedule outlook, activity insights, work recommendations. |
| `/father-time:pace-check` | Rate limit forecasting. Estimates runway based on session duration and work intensity. |
| `/father-time:focus-mode` | Focus timer with presets (pomodoro 25m, deep-work 90m, sprint 45m, marathon 3h). Non-intrusive. |
| `/father-time:activity-patterns` | Analyze your work patterns over time. Night owl? Early bird? How much do you overlap with peak hours? |
| `/father-time:session-health` | Session JSONL size, context window usage estimate, compaction proximity, and rate limit status. |

## Peak Hours by Timezone

Anthropic's throttle window: **Weekdays 5:00 AM – 11:00 AM Pacific Time**

| Timezone | Peak Window |
|----------|------------|
| PT (Pacific) | 5:00 AM – 11:00 AM |
| MT (Mountain) | 6:00 AM – 12:00 PM |
| CT (Central) | 7:00 AM – 1:00 PM |
| ET (Eastern) | 8:00 AM – 2:00 PM |
| GMT/UTC | 1:00 PM – 7:00 PM |
| CET (Central Europe) | 2:00 PM – 8:00 PM |
| IST (India) | 6:30 PM – 12:30 AM |
| JST (Japan) | 10:00 PM – 4:00 AM |
| AEST (Australia East) | 11:00 PM – 5:00 AM |
| NZST (New Zealand) | 1:00 AM – 7:00 AM |

## Install

Add the marketplace and install:
```bash
claude plugin marketplace add AfterRealm/father-time
claude plugin install father-time
```

Then restart Claude Code. All skills will be available globally.

## Requirements

- Claude Code v2.1.78+
- Python 3 (for hook scripts)

## Token Cost

Father Time is nearly free to run.

| Component | Token Cost | When |
|-----------|-----------|------|
| Time injection hook | ~40 tokens/prompt | Every prompt (passive) |
| Skills | 300-800 tokens | Only when you invoke them |
| Agent | ~1,500 tokens | Only when spawned |
| Python scripts | 0 tokens | Run locally, no API calls |

**Passive cost:** ~40 tokens per prompt for the time/peak/session string. Over a 100-prompt session, that's ~4,000 tokens — **0.4% of a 1M context window**. Essentially invisible.

Skills and the agent only consume tokens when you explicitly call them. The hook scripts run as local Python processes with zero API cost.

## Privacy

All data stays local. Activity patterns are stored in `${CLAUDE_PLUGIN_DATA}` on your machine. Nothing is transmitted anywhere.

## License

MIT
