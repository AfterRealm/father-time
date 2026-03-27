---
name: daily-brief
description: Get a morning briefing with peak hour status, schedule outlook, and work recommendations for the day. Use at the start of a new day or when asking for a daily summary.
model: sonnet
---

# Daily Briefing

Provide a concise start-of-day briefing to help the user plan their Claude Code usage.

## What to Include

### 1. Time Check
- Current time in user's timezone
- What day of the week it is
- Weekend or weekday

### 2. Peak Hour Status
- Are we currently in peak hours?
- When does the next peak window start/end?
- Optimal work windows for today

### 3. Schedule Outlook

**Weekday template:**
```
Today's Peak: [start] – [end] in your timezone
Right now: [PEAK/OFF-PEAK]
Best heavy-work windows: Before [peak start] and after [peak end]
```

**Weekend template:**
```
No peak throttling today. Work freely all day.
```

### 4. Activity Pattern Insight
Read `${CLAUDE_PLUGIN_DATA}/activity_patterns.json` and note:
- "You typically start around [time] on [weekday]s"
- "You've been averaging [N] sessions per week"
- Any notable patterns (night owl, morning person, weekend warrior)

### 5. Work Recommendation
Based on current time + peak status:
- If it's pre-peak: "You have [N hours] before peak starts. Good time for heavy work."
- If it's peak: "Peak hours active. Light work recommended, or wait [N hours] for off-peak."
- If it's post-peak: "Peak is over. Clear for heavy work until tomorrow."
- If it's late night: "Deep off-peak. Best time for marathon sessions."

## Response Format

Keep it tight — this should be a quick glance, not a report:

```
Good [morning/afternoon/evening]. [Day], [Date].

[PEAK/OFF-PEAK] — [status detail]
Heavy work window: [optimal times]
You usually work [pattern insight].

[One-line recommendation]
```
