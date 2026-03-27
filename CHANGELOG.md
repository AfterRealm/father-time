# Changelog

All notable changes to Father Time are documented here.

## [1.6.0] — 2026-03-27

### Added
- **Compaction warning hook** — runs on every prompt, warns at 60%, 75%, and 85% context usage before you get surprise-compacted
- **Update checker hook** — checks for new plugin versions on session start, shows upgrade command if outdated
- **Session cost estimate** — estimated API cost per session based on detected model and real token counts
- **Rate limit forecasting** — predicts when you'll hit session/weekly limits at current pace
- **Subscription burn rate** — daily burn percentage and remaining weekly budget
- **Context budget skill** — estimate token cost of files before reading, with Opus/Sonnet/Haiku price comparison
- `.gitignore` for `__pycache__/`

### Changed
- Session health output now includes `Est. cost` line with detected model
- Usage check output now includes `Forecast` section with time-to-limit predictions
- Time menu adds "Context Budget" option under Session submenu

## [1.5.0] — 2026-03-27

### Added
- Usage data caching (5-minute TTL) — prevents API rate limit collisions
- `--refresh` flag on usage_check.py to force a fresh API call
- Refresh button in pace check menu after showing cached results
- Rate limit bars now appear inline in session health output
- Shared cache file (`~/.claude/usage_cache.json`) — other tools can read/write the same cache

### Fixed
- 429 errors when multiple tools poll the usage API simultaneously

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
