# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** v3.3 Settings Split — Phase 16: Settings Page Split

## Current Position

Phase: 16 of 18 (Settings Page Split)
Plan: 2/2 — 16-02 tasks complete; awaiting human-verify checkpoint (Task 3)
Status: In progress — checkpoint pending
Last activity: 2026-02-22 — 16-02 auto tasks complete (/admin/settings created)

Progress: [██████████] 43/43 total plans (v3.3: 2/5 done)

## Performance Metrics

**Velocity:**
- Total plans completed: 42 (phases 1-16 auto tasks)
- Average duration (v3.x): ~15m per plan
- Total execution time (v3.x): varies

**By Phase:**

| Phase | Plans | Milestone |
|-------|-------|-----------|
| 1-14 | 34/34 | v2.0-v3.1 |
| 15. Tracking Page UX | 1/1 | v3.2 |
| 16. Settings Page Split | 2/2 | v3.3 |
| 17. Notification Dispatch Modes | 0/2 | v3.3 |
| 18. Endpoint Hardening | 0/1 | v3.3 |

**Recent Trend:**
Phase 16 completed in 2 plans — clean split of settings into personal (/settings) and system (/admin/settings).

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v3.2: Area widget on /tracking replaces settings page detour — Local Area removed from /settings
- v3.3: Fetch schedule changes from interval to specific times of day (APScheduler CronTrigger)
- v3.3: Notification mode is system-wide admin policy, not per-user preference
- v3.3: No scheduler status on /admin/settings — already covered by /admin/scraper-status
- v3.3: Daily digest queues events at fetch time, sends at configured daily time per user
- 16-01: save_settings POST now redirects immediately — system config moves to /admin/settings in 16-02
- 16-01: mask_token() removed; get_scheduler_status retained (used by /api/status)
- 16-02: SchedulerConfig load() uses safe field-by-field get() for backward compat with old config.yaml
- 16-02: Bot token update guarded — only updates if submitted value contains no asterisks
- 16-02: fetch_times stored as list of HH:MM strings; validated by regex on save, malformed entries discarded
- 16-02: notification_mode validated against allowlist before persisting to config

### Pending Todos

None.

### Blockers/Concerns

- Phase 17 (Notification Dispatch Modes) requires DB schema changes (queued vs sent state on notifications); verify column additions work on Railway PostgreSQL via init_schema()
- Phase 17: APScheduler CronTrigger replaces interval-based scheduling — fetch_times config key (added in 16-02) is ready for CronTrigger use
- 16-02 checkpoint (Task 3): human verification still pending — admin must test /admin/settings end-to-end

## Session Continuity

Last session: 2026-02-22
Stopped at: 16-02 checkpoint:human-verify — Tasks 1+2 committed; awaiting manual verification of /admin/settings
Resume file: None
Next: Verify 16-02 checkpoint, then execute Phase 17
