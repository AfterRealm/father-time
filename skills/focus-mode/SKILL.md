---
name: focus-mode
description: Start a focus timer for deep work sessions. Tracks elapsed time and optionally reminds about breaks. Use when the user wants to focus, start a timer, or do a pomodoro session.
---

# Focus Mode

A lightweight work timer for deep focus sessions. Opt-in, non-intrusive.

## How It Works

When invoked, start tracking a focus session:

1. Note the start time
2. User specifies duration (or default to 90 minutes — research-backed optimal focus block)
3. Claude notes the timer but does NOT interrupt the user's flow
4. If the user asks "how's my timer?" — report elapsed and remaining
5. When the timer expires, mention it naturally at the next prompt — don't force it

## Focus Presets

| Preset | Duration | Use Case |
|--------|----------|----------|
| pomodoro | 25 min | Short focused burst |
| deep-work | 90 min | Extended focus (default) |
| sprint | 45 min | Medium burst |
| marathon | 3 hours | Long haul |
| custom | user-specified | Whatever they want |

## Starting Focus Mode

When the user says things like:
- "start a focus timer"
- "pomodoro"
- "let's do 2 hours focused"
- "focus mode"

Respond:
```
Focus mode: [preset name] — [duration]
Started: [time]
Ends: [time]
I'll note when time's up. Get to work.
```

## During Focus

- Do NOT interrupt with timer updates unless asked
- If the user asks "timer?" or "how long?" — give a quick update
- At natural conversation breaks, if time has elapsed, mention it briefly

## When Timer Ends

At the next prompt after the timer expires:
```
Focus timer done — [duration] completed. [Optional: short encouragement].
```

That's it. One line. Don't make a big deal.

## Rules

- **Never force breaks** — some users hate break reminders. Only mention the timer ending.
- **Never guilt-trip** — if they work past the timer, that's fine. They're in flow.
- **Keep it light** — this is a tool, not a taskmaster.
