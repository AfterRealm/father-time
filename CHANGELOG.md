# Changelog

All notable changes to Father Time are documented here.

## [1.4.0] — 2026-03-27

### Fixed
- Removed `model:` field from all 8 skills — skills were forcing Haiku/Sonnet model switches, which likely caused premature context compaction by switching to a 200K context window mid-session

## [1.3.0] — 2026-03-27

### Added
- `usage_check.py` script — fetches real rate limit data from the Anthropic OAuth API
- Session (5h), weekly (7d), and Opus utilization with progress bars and reset countdowns

### Changed
- Pace check skill now uses real API data instead of estimates
- Time menu pace check section updated to run usage script
- Agent definition rate limit section updated to run usage script

## [1.2.0] — 2026-03-27

### Added
- Interactive `/father-time:time-menu` skill with AskUserQuestion menus
- Two-level drill-down: top category (Session / Time & Pacing / Work Patterns) then specific capability
- `marketplace.json` for plugin distribution via `claude plugin marketplace add`
- `--threshold` flag on `session_health.py` for configurable compaction thresholds

### Fixed
- `session-health/skill.md` renamed to `SKILL.md` (case consistency)
- Added missing `model: haiku` to time-menu frontmatter

### Changed
- Session health script now calculates context % against user-specified threshold (default 1M)
- Agent definition updated with CLAUDE.md override instructions and sonnet model
- README and PROMO updated with marketplace install instructions

## [1.1.0] — 2026-03-27

### Changed
- Renamed `/father-time:menu` skill to `/father-time:time-menu`
- Version bump to refresh plugin cache

## [1.0.0] — 2026-03-27

### Added
- Initial release
- Time injection hook — current time, peak status, and session duration on every prompt
- Session start hook — records timestamp and logs activity patterns
- 7 skills: peak-hours, session-timer, daily-brief, pace-check, focus-mode, activity-patterns, session-health
- Father Time agent definition for standalone sessions
- `session_health.py` — parses JSONL transcripts for real context usage data
- Peak hour awareness for 10 timezones
- Activity pattern tracking (last 200 sessions)
