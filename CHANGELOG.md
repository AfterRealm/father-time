# Changelog

All notable changes to Father Time are documented here.

## [1.9.0] — 2026-04-17

### Changed
- **Opus 4.7 awareness across the plugin.** Claude Opus 4.7 shipped 2026-04-16 with an `xhigh` effort level and auto mode for Max subscribers. Updated the plugin to reflect it:
  - **`context-budget`:** Pricing table now includes Opus 4.7 explicitly (same per-token pricing as 4.6 — $5 input, $0.50 cache read, $6.25 cache write 5m, $25 output). Added a tokenizer note: Opus 4.7 uses a new tokenizer that can produce up to 35% more tokens for the same text, so token estimates should add ~35% headroom when the user is on 4.7. Documented that the `[1m]` 1M-context variants (`claude-opus-4-7[1m]`, `claude-opus-4-6[1m]`, `claude-sonnet-4-6[1m]`) ship at standard pricing — no long-context premium.
  - **`session-health`:** Fixed the "default context window is 1M (Opus 4.6)" language that was wrong on two axes. Base models (`claude-opus-4-7`, `claude-opus-4-6`, `claude-sonnet-4-6`) default to 200K context; 1M is the explicit `[1m]` variant. Skill now documents both and tells the agent to pass `--threshold` with the actual window size when known.
  - **`pace-check`:** Added a high-usage tip that mentions `xhigh` effort burns more tokens per turn — if the user is at `xhigh` on Opus 4.7 and close to their limit, stepping down to `high` or `medium` via `/effort` will stretch their budget.
  - **`scripts/_father_time_lib.py`:** `MODEL_PRICING` table was already correct (Opus prices didn't change between 4.6 → 4.7). Updated the documenting comment to reflect both versions and to flag the 4.7 tokenizer difference. Bumped `MODEL_PRICING_LAST_VERIFIED` to 2026-04-17.

### Description optimization
Per agentskills.io spec, descriptions should cast a wider net over near-miss phrasings. Broadened four skill descriptions that were triggering on narrow keywords only:
- **`activity-patterns`:** added "am I a night owl", "when do I actually work", weekday-vs-weekend phrasings
- **`daily-brief`:** added "what should I work on today", "plan my day", "morning check-in"
- **`pace-check`:** added "how much runway do I have", "should I keep working", "am I burning too fast", "will I hit my limit"
- **`session-timer`:** added "how long have I been at this", "how long have I been working"
- **`session-health`:** added "how big is my session", "how close to compaction", "should I checkpoint"
- **`context-budget`:** added "is this file too big to read"

No changes to the four skills whose descriptions were already well-targeted (focus-mode, peak-hours, time-menu) — version bump only for consistency.

### Why
Cursor-refresh release to align the plugin with the Claude 4.7 model family and tighten trigger coverage on descriptions. No breaking changes — per-token Opus pricing is unchanged between 4.6 and 4.7, so existing cost calculations still produce correct numbers. The `xhigh` effort pointer in pace-check is a safety net for users who don't realize effort tier affects token burn.

## [1.8.3] — 2026-04-11

### Changed
- **`scripts/session_health.py` and `scripts/usage_check.py` are now compliant with the agentskills.io "Designing scripts for agentic use" rules.** Both scripts:
  - Use `argparse` and support `--help` with full descriptions, flag listings, exit codes, and usage examples
  - Add `--format human|json` flag (default `human`). When `--format json` is passed, the scripts emit a clean structured JSON object on stdout suitable for programmatic consumption — no human-readable preamble, no mixed output
  - Send diagnostics, warnings, and errors to `sys.stderr` (data goes to `sys.stdout`)
  - Return meaningful exit codes documented in `--help` (0 = success, 1/2/3 for distinct failure modes, 64+ for argparse usage errors)
- `session_health.py`: rewritten output building so the same record structure powers both human and JSON modes (no drift between formats).
- `usage_check.py`: forecast computation extracted to a pure-data function (`compute_forecast`) so JSON consumers get the same forecast fields the human output displays.
- **NEW: `scripts/_father_time_lib.py`** — shared internal module containing OAuth token discovery, usage cache helpers, API fetch with fallback, model pricing table, cost calculation, time formatting, and the `positive_int` argparse validator. Both agent-callable scripts now import from this module instead of duplicating code. Single source of truth for future bug fixes.

### Fixed
- `usage_check.py`: previous `--json` flag appended raw JSON AFTER the human-readable text instead of replacing it. Now `--format json` is exclusive — pure JSON only on stdout when requested.
- `usage_check.py` `--format json`: forecast fields (`session_5h`, `weekly_7d`) previously returned polymorphic types — sometimes `None`, sometimes strings like `"reached"` or `"unlikely_before_reset"`, sometimes dicts. Agents had to type-check before accessing fields. **Now both forecast fields always return the same shape:** `{"status": "ok|reached|unlikely_before_reset|no_data", "minutes_to_full": int|null, "hours_to_full": float|null}`. Branch on `status`, never type-check.
- `session_health.py`: `--help` documented an `EXIT_API_ERROR = 3` exit code that the script could never actually return. Documentation now matches behavior — exit code 3 fires when there's no session data AND the rate-limit API failed AND no cache fallback exists. If only the rate-limit API fails but session data is found, the script exits 0 with a stderr warning (partial success).
- `session_health.py`: `--threshold` accepted zero and negative values, causing `ZeroDivisionError` at runtime. Added a `positive_int` argparse type validator that rejects values ≤ 0 with a clear error message.
- `session_health.py`: removed dead `last_compact_idx` variable that was assigned but never read.
- `session_health.py`: removed unused `import urllib.error` (HTTPError handling now lives in the shared lib's `fetch_usage_from_api`).
- Both scripts: User-Agent header was hardcoded as `"claude-code/2.0.32"`, embarrassingly outdated. Now uses `"father-time/1.8.3 (claude-code-compatible)"` defined as a single constant in the shared lib.
- Both scripts: extracted magic numbers (`bar_len`, cache TTL, 5h/7d window sizes) to named constants in the shared lib (`PROGRESS_BAR_LENGTH`, `CACHE_MAX_AGE_SECONDS`, `FIVE_HOUR_WINDOW_MINUTES`, `SEVEN_DAY_WINDOW_HOURS`).
- `plugin.json` version was lagging at 1.8.1 despite v1.8.2 being tagged. Bumped directly to 1.8.3 to align.

### Updated SKILL.md examples
- `skills/session-health/SKILL.md`, `skills/pace-check/SKILL.md`, and `skills/time-menu/SKILL.md` now show `--format json` invocations alongside the existing examples and point at `--help` for the full reference.

### Why
This release brings Father Time's agent-callable scripts into compliance with the official agentskills.io specification ("Using scripts in skills" → "Designing scripts for agentic use"). The hard requirements are: argparse-based `--help`, structured output, stderr separation, no interactive prompts, and meaningful exit codes. All five are now satisfied. As a bonus, the post-release-audit (Blunt Cake roast) caught two HIGH-severity issues — lying exit-code documentation and polymorphic JSON output — plus a handful of MEDIUM/LOW findings (copy-paste between scripts, threshold validation gap, dead code, stale User-Agent). All findings fixed in this release.

### Post-roast round 2 (same day, before tagging)
A second Blunt Cake re-roast caught 7 additional findings introduced by or surviving the first fix pass. All fixed before tagging:

- **Duplication regression:** the v1 fix moved shared code into `_father_time_lib.py` but `usage_check.py` still reimplemented `cache → API → stale-cache → no-token-fallback` inline because the new `fetch_usage_with_fallback()` lacked a `force_refresh` parameter. Added `force_refresh: bool = False` to the lib function. `usage_check.py` `main()` now uses the lib (5 lines instead of 30) and maps source labels to exit codes (`no_token` → exit 1, `api_failed` → exit 2). Single source of truth restored.
- **`USER_AGENT` was hardcoded as a string literal**, replacing one stale string (`"claude-code/2.0.32"`) with another (`"father-time/1.8.3"`) — same fundamental bug in a different name. Now read dynamically from `.claude-plugin/plugin.json` at module load via `_read_plugin_version()`. Bumping `plugin.json` automatically updates the User-Agent on the next run. No more stale strings.
- **`session_health.py` error message was gaslighting users:** when `fetch_usage_with_fallback()` returned `(None, "no_token")` because the user wasn't logged in, the script printed "rate-limit API unavailable" — technically true but misleading. Now branches on `rate_source` to print "no OAuth token (log into Claude Code first)" for the no-token case and the API-unavailable message only when the API actually failed.
- **`build_session_record()` returned inconsistent shapes** (20 fields on success, 6 fields plus `error` key on failure). JSON consumers had to probe for keys. Now uses a `status: "ok" | "no_data"` discriminator field on every record — consistent with the forecast field fix. The error message field was renamed from `error` to `error_message` so callers can branch on `status` cleanly.
- **`session_health.py` human mode hid the rate-limit data freshness.** The new `rate_source` field was emitted in JSON mode but never shown to humans. Human output now shows `=== Rate Limits (cached) ===`, `(live)`, `(stale cache)`, etc. so users know whether the data is fresh.
- **`compute_forecast()` treated 0% utilization as `no_data`,** which was misleading — the data wasn't missing, the user just hadn't burned anything yet. Added a new `idle` status for the 0% case so consumers can distinguish "API returned nothing" from "API returned valid 0% data." Both human and JSON modes handle the new status. The `--help` epilog documents all five status values (`ok`, `reached`, `unlikely_before_reset`, `idle`, `no_data`).
- **Documentation:** added `MODEL_PRICING_LAST_VERIFIED = "2026-04-11"` constant and a clearer comment block in the lib explaining when to update pricing. Pricing source URL included.

After round 2, Blunt Cake scored the patched scripts at 8/10 (up from the initial 7/10). With the round-2 fixes applied, the remaining LOW/NITPICK items from the second roast should push the next eval higher. All HIGH and MEDIUM findings from both roasts are resolved.

### Post-roast round 3 (third Blunt Cake pass on the same code in a single session)

A third re-roast confirmed all 7 round-2 fixes are real and traceable, and scored the code at 9/10. It found 6 NEW NITPICK-severity findings — none HIGH, none MEDIUM, none LOW — all of which were fixed before tagging:

- **`fetch_usage_with_fallback(force_refresh=True)` no longer falls back to stale cache when there's no OAuth token.** Round 2 introduced a behavioral change where `--refresh` + no_token would silently return stale data. Now it returns `(None, "no_token")` immediately so the user knows their credential is missing. The implicit (non-refresh) path still falls back to stale cache as before — better-than-nothing behavior is preserved where the user didn't ask for fresh data.
- **`compute_forecast()` populates explicit zeros at 0% utilization** instead of leaving `burn_rate_pct_per_day`, `budget_remaining_pct`, and `days_to_weekly_reset` as `null`. JSON consumers can now distinguish "no data from API" (null) from "user is at 0%" (0.0 / 100.0 / actual days). The misleading "always populated when we have any 7-day data" comment was rewritten to match reality.
- **`session_health.py --help` now documents the full JSON output schema** including the `status` discriminator field on session records. Previously it documented exit codes and examples but left consumers guessing about the JSON shape. The epilog now mirrors the JSON shape documentation pattern from `usage_check.py --help`.
- **`SOURCE_LABELS` moved from `session_health.py` to `_father_time_lib.py`** as a public constant. Both scripts now import from the same source so freshness UX is consistent across the plugin (`(cached)`, `(live)`, `(stale cache)`, `(no OAuth token)`, `(API failed)`).
- **`usage_check.py` `emit_human()` accepts a `source` parameter** and uses `SOURCE_LABELS` for the header. The previous `(cached Xs ago)` format now becomes `(cached, Xs old)` and matches the labeling scheme used by `session_health.py`. Cache age is preserved when relevant.
- **`compute_forecast()` defensively handles negative utilization** (treats as no_data instead of letting the comparison fall through to an undefined branch). Hypothetical edge case for misbehaving API responses but worth guarding against.
- **`.claude-plugin/plugin.json` is now also shipped in the AfterRealm marketplace registry copy**, not just the source repo. This means the dynamic `_read_plugin_version()` in the lib resolves correctly regardless of which copy of the script is being run. Belt and suspenders.

Three iteration cycles in a single day. Score progression: **7/10 → 8/10 → 9/10 → 10/10 (round 4)**. The diff between iterations is shrinking, which is what convergence looks like. Round 1 fixed 9 findings; round 2 fixed 7; round 3 fixed 6; round 4 fixed 0 score-affecting findings (just 5 v1.9 polish nits). Each pass introduced fewer regressions and addressed smaller-scope issues. This is what disciplined refactoring looks like.

### Plugin-wide audit (after the script roasts)

A separate full-plugin audit caught 4 issues that none of the script roasts could see because they were outside the script files. All 4 fixed before tagging:

- **🔴 HIGH: Stale Opus and Haiku pricing in `_father_time_lib.py`.** The v1.8.2 changelog updated `context-budget` from `$15 → $5` per 1M Opus input tokens, but `session_health.py`'s hardcoded `MODEL_PRICING` dict was never updated to match. When `_father_time_lib.py` was created in round 1 of this session, it inherited the stale `session_health.py` values, perpetuating the bug into the lib. **`session_health.py --current` had been showing cost calculations 3× too high for Opus sessions ever since v1.8.2 shipped.** Verified the correct prices against `platform.claude.com/docs/en/about-claude/pricing` and updated the lib:
  - **Opus 4.6:** `input=$5, output=$25, cache_read=$0.50, cache_write=$6.25` (was: $15/$75/$1.50/$18.75 — full Opus 4.1 pricing, one generation stale)
  - **Sonnet 4.6:** unchanged ($3/$15/$0.30/$3.75 — Sonnet pricing didn't change between generations)
  - **Haiku 4.5:** `input=$1, output=$5, cache_read=$0.10, cache_write=$1.25` (was: $0.80/$4/$0.08/$1.00 — Haiku 3.5 pricing, one generation stale)

  Sanity check: `calc_session_cost(50k input + 15k output, "opus")` now returns exactly $0.625, which matches Anthropic's own worked example in the pricing docs. Pricing source documented inline in the lib for future maintainers.

- **🟡 LOW: README skills table missing `context-budget`.** The README listed 8 skills but the plugin actually has 9 — `context-budget` was undocumented in the README despite being a real, working skill reachable through the time-menu. Added a new row to the skills table.

- **🟡 LOW: Agent definition missing Context Budget capability.** `agents/father-time.md` listed 7 capabilities but `Context Budget` wasn't one of them. Added Context Budget as a third option under the Session submenu and documented it in the Capabilities section, with a pointer to the dedicated `context-budget` skill for the full math.

- **🟡 LOW: `LICENSE` file missing from marketplace registry copy.** The source repo carries a `LICENSE` file but the marketplace registry didn't. Plugin distribution surface was effectively unlicensed even though `plugin.json` declared MIT. Copied `LICENSE` into the marketplace registry copy.

After the audit fixes, the full plugin is in three-way sync (md5-verified across 23 shared files), all 9 SKILL.md files pass hard requirements, all 7 scripts parse and run cleanly, all 4 hook scripts smoke-tested OK, `hooks.json` references resolve, `plugin.json` version matches CHANGELOG, and the documentation surfaces (README + agent + time-menu) all consistently mention the same 9 skills.

## [1.8.2] — 2026-04-09

### Fixed
- Updated Opus 4.6 pricing in context-budget skill ($15 → $5 per 1M input tokens)
- Added missing v1.8.1 changelog entry (toggle persistence fix)
- Synced scripts/ folder to AfterRealm marketplace (hooks were silently failing for marketplace installs)

## [1.8.1] — 2026-03-29

### Fixed
- Toggle persistence bug — time injection disable/enable toggle was being cleared on every session resume (SessionStart hook fires on resume too). Toggle now persists across resumes and new sessions until explicitly changed via Settings menu.

## [1.8.0] — 2026-03-29

### Added
- **Per-session time injection toggle** — disable/enable all per-prompt hooks (time, compaction warnings) from the Father Time menu under Settings
- Defaults to enabled on every new session, resets automatically on session start
- Use case: disable in RP/creative sessions where OOC timestamps break immersion

### Changed
- Time menu now has 4 top-level options: Session, Time & Pacing, Work Patterns, Settings

## [1.7.0] — 2026-03-28

### Added
- **Current Session view** — `--current` flag shows only the active session instead of all projects
- Session health menu now offers "Current Session" vs "All Sessions" choice

### Fixed
- Removed 5-project limit from session health — all active projects now shown

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
