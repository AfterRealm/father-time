---
name: peak-hours
description: Check if you're in Anthropic's peak throttling window. Shows status for any timezone. Use when asking about peak hours, rate limits, or best time to work.
---

# Peak Hours Check

Show the user their current peak hour status with timezone-aware information.

## Anthropic Peak Hours
**Weekdays only: 5:00 AM – 11:00 AM Pacific Time**

During peak hours, 5-hour session limits drain faster. Weekly limits unchanged.

## Timezone Table

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

## What to Show

1. Current time in user's timezone
2. Current time in PT
3. **PEAK** or **OFF-PEAK** status
4. Time remaining until status changes
5. Recommendation: heavy work now, or defer?

## Recommendations

**During peak:**
- Defer token-heavy operations (large code generation, deep research, multi-file refactors)
- Good time for: quick questions, small edits, planning, reading docs
- "You're in peak hours — session limits drain faster. Save heavy work for after [end time in their TZ]."

**Off-peak:**
- All clear for heavy work
- "Off-peak — go hard. You have until [peak start in their TZ] before throttling kicks in."

**Weekends:**
- No peak hours at all
- "Weekend — no peak throttling. Work freely."
