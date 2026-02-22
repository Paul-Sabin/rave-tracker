# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** v3.3 Settings Split — Phase 16: Settings Page Split

## Current Position

Phase: 16 of 18 (Settings Page Split)
Plan: 1/2 — 16-01 complete
Status: In progress
Last activity: 2026-02-22 — 16-01 complete (settings page stripped to personal-only)

Progress: [██████████] 42/43 total plans (v3.3: 1/5 done)

## Performance Metrics

**Velocity:**
- Total plans completed: 41 (phases 1-15)
- Average duration (v3.x): ~15m per plan
- Total execution time (v3.x): varies

**By Phase:**

| Phase | Plans | Milestone |
|-------|-------|-----------|
| 1-14 | 34/34 | v2.0-v3.1 |
| 15. Tracking Page UX | 1/1 | v3.2 |
| 16. Settings Page Split | 1/2 | v3.3 |
| 17. Notification Dispatch Modes | 0/2 | v3.3 |
| 18. Endpoint Hardening | 0/1 | v3.3 |

**Recent Trend:**
Phase 15 completed in single plan — compact, focused delivery.

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

### Pending Todos

None.

### Blockers/Concerns

- Phase 17 (Notification Dispatch Modes) requires DB schema changes (queued vs sent state on notifications); verify column additions work on Railway PostgreSQL via init_schema()
- Phase 17: APScheduler CronTrigger replaces interval-based scheduling — existing fetch_interval config key will be superseded; confirm config migration path

## Session Continuity

Last session: 2026-02-22
Stopped at: Completed 16-01-PLAN.md — /settings page split to personal-only content
Resume file: None
Next: Execute 16-02 (create /admin/settings with system config sections)
