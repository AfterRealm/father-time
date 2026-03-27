"""
Father Time — Time injection hook.
Runs on every UserPromptSubmit. Outputs current time, session duration,
and peak hour status for Claude's context.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

def get_local_time():
    """Get current local time with timezone info."""
    now = datetime.now().astimezone()
    return now

def get_peak_status(now):
    """Check if current time falls within Anthropic's peak hours.
    Peak: weekdays 5am-11am PT / 8am-2pm ET / 1pm-7pm GMT.
    Returns status string and minutes until peak ends/starts.
    """
    # Convert to PT (UTC-7 standard, UTC-8 daylight — use UTC-7 for PDT which is most of the year)
    utc_now = now.astimezone(timezone.utc)

    # Try to detect PT offset — PDT is UTC-7 (Mar-Nov), PST is UTC-8 (Nov-Mar)
    # Approximate: if month is 3-10, assume PDT (UTC-7), otherwise PST (UTC-8)
    month = utc_now.month
    if 3 <= month <= 10:
        pt_offset = timedelta(hours=-7)  # PDT
    else:
        pt_offset = timedelta(hours=-8)  # PST

    pt_now = utc_now + pt_offset
    pt_hour = pt_now.hour
    pt_weekday = pt_now.weekday()  # 0=Monday, 6=Sunday

    is_weekday = pt_weekday < 5
    is_peak_hour = 5 <= pt_hour < 11
    is_peak = is_weekday and is_peak_hour

    if is_peak:
        mins_left = (11 - pt_hour) * 60 - pt_now.minute
        return "PEAK", mins_left, pt_now.strftime("%I:%M %p PT")
    else:
        if is_weekday and pt_hour < 5:
            mins_until = (5 - pt_hour) * 60 - pt_now.minute
        elif is_weekday and pt_hour >= 11:
            # Next peak is tomorrow 5am PT (or Monday if Friday)
            if pt_weekday == 4:  # Friday
                mins_until = ((5 + 24 * 2) - pt_hour) * 60 - pt_now.minute + 24 * 60
            else:
                mins_until = (5 + 24 - pt_hour) * 60 - pt_now.minute
        else:
            # Weekend — next peak is Monday 5am PT
            days_until_monday = (7 - pt_weekday) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            mins_until = days_until_monday * 24 * 60 - pt_hour * 60 - pt_now.minute + 5 * 60
        return "OFF-PEAK", mins_until, pt_now.strftime("%I:%M %p PT")

def get_session_duration():
    """Calculate session duration from the session start file."""
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", "")
    start_file = os.path.join(data_dir, "session_start.txt") if data_dir else ""

    if start_file and os.path.exists(start_file):
        try:
            with open(start_file, 'r') as f:
                start_ts = float(f.read().strip())
            elapsed = datetime.now().timestamp() - start_ts
            hours = int(elapsed // 3600)
            mins = int((elapsed % 3600) // 60)
            if hours > 0:
                return f"{hours}h {mins}m"
            return f"{mins}m"
        except Exception:
            pass
    return None

def main():
    now = get_local_time()

    # Time string
    time_str = now.strftime("%A, %B %d %Y at %I:%M %p %Z")

    # Peak status
    peak_status, mins_delta, pt_time = get_peak_status(now)

    if peak_status == "PEAK":
        hours_left = mins_delta // 60
        mins_left = mins_delta % 60
        if hours_left > 0:
            peak_msg = f"PEAK HOURS — {hours_left}h {mins_left}m remaining (ends 11am PT). Session limits drain faster."
        else:
            peak_msg = f"PEAK HOURS — {mins_left}m remaining. Almost off-peak."
    else:
        hours_until = mins_delta // 60
        mins_until = mins_delta % 60
        if hours_until > 24:
            days = hours_until // 24
            peak_msg = f"Off-peak. Next peak in ~{days} days (Monday 5am PT)."
        elif hours_until > 0:
            peak_msg = f"Off-peak. Next peak in {hours_until}h {mins_until}m."
        else:
            peak_msg = f"Off-peak. Next peak in {mins_until}m."

    # Session duration
    duration = get_session_duration()
    duration_msg = f" | Session: {duration}" if duration else ""

    # Output
    output = f"Current time: {time_str} | {pt_time} | {peak_msg}{duration_msg}"
    print(output)

if __name__ == "__main__":
    main()
