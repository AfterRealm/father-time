---
name: activity-patterns
description: Analyze your work patterns over time — when you typically work, peak vs off-peak usage, night owl detection. Use when asking about work habits, schedule patterns, or optimal work times.
---

# Activity Patterns

Analyze the user's Claude Code usage patterns over time to provide personalized scheduling insights.

## Data Source

Read `${CLAUDE_PLUGIN_DATA}/activity_patterns.json` — an array of session start records:

```json
[
  {"date": "2026-03-26", "time": "22:15", "weekday": "Wednesday", "hour": 22},
  {"date": "2026-03-27", "time": "08:10", "weekday": "Thursday", "hour": 8}
]
```

The SessionStart hook appends an entry each time a new session begins. Max 200 entries retained.

## Analysis to Perform

### Time Distribution
- Count sessions by hour of day (0-23)
- Find the peak activity hours
- Identify dead hours (when they never work)

### Day Distribution
- Sessions per weekday
- Weekday vs weekend ratio
- Most active day of the week

### Pattern Classification

Based on the data, classify the user:

| Pattern | Criteria |
|---------|----------|
| **Night Owl** | >50% of sessions between 8pm-4am |
| **Early Bird** | >50% of sessions between 5am-10am |
| **Business Hours** | >50% of sessions between 9am-5pm |
| **All-Hours** | No dominant time block |
| **Weekend Warrior** | >30% of sessions on weekends |

### Peak Hour Overlap
- What percentage of their sessions fall during peak hours?
- Are they naturally avoiding peak, or hitting it head-on?
- Personalized recommendation based on their actual pattern

## Response Format

```
Activity Profile: [N] sessions analyzed over [date range]

Schedule: [Night Owl / Early Bird / Business Hours / All-Hours]
Most active: [day of week] at [hour range]
Least active: [day/hour]
Peak hour overlap: [X]% of your sessions hit peak hours

[Insight]: [Personalized observation, e.g., "You naturally work off-peak —
your night schedule dodges throttling completely."]

[Recommendation]: [Actionable advice based on pattern]
```

## Privacy Note

Activity patterns are stored locally in `${CLAUDE_PLUGIN_DATA}`. Nothing is sent anywhere. The data stays on the user's machine and is only used to provide personalized scheduling insights.
