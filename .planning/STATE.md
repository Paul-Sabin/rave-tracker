# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** v3.3 — Phase 17: Notification Dispatch Modes

## Current Position

Phase: 17 of 18 (Notification Dispatch Modes) — IN PROGRESS (awaiting human checkpoint)
Plan: 2/2 — 17-02 auto tasks complete; checkpoint pending human verification
Status: 17-02 auto tasks done; CronTrigger schedule + mode dispatch + digest job wired. Awaiting human verify checkpoint.
Last activity: 2026-02-23 — 17-02 executed; scheduler dispatch modes implemented

Progress: [██████████] 44/44 total plans (v3.3: 3/5 done)

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
| 17. Notification Dispatch Modes | 1/2 (17-02 checkpoint pending) | v3.3 |
| 18. Endpoint Hardening | 0/1 | v3.3 |

**Recent Trend:**
Phase 16 completed in 2 plans — clean split of settings into personal (/settings) and system (/admin/settings).
Phase 17 started — 17-01 extends notifications DB schema for digest mode queue lifecycle.

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
- 17-01: queue_event_for_digest uses rule_id=0 + UNIQUE(event_id, rule_id) for dedup — same pattern as add_event_notification
- 17-01: has_event_notification unchanged — broad SELECT covers both queued and sent records, preventing double-queuing in digest mode
- 17-02: send_daily_digest uses db.get_event() (existing) not get_event_by_id — avoids redundant alias
- 17-02: canonical 'fetch_and_notify' job id preserved as alias for first fetch_time slot — get_next_fetch_time() still works
- 17-02: get_rules_for_event_and_user added to database.py — joins event_rules+rules, filtered by event_id+user_id

### Pending Todos

None.

### Blockers/Concerns

- Phase 17 (Notification Dispatch Modes) requires DB schema changes (queued vs sent state on notifications); verify column additions work on Railway PostgreSQL via init_schema()
- Phase 17: APScheduler CronTrigger replaces interval-based scheduling — fetch_times config key (added in 16-02) is ready for CronTrigger use
- 16-02 checkpoint (Task 3): human verification APPROVED — all 6 tests passed, /admin/settings fully verified

## Session Continuity

Last session: 2026-02-23
Stopped at: 17-02-PLAN.md checkpoint — auto tasks complete, awaiting human-verify checkpoint
Resume file: None
Next: Human verify checkpoint for 17-02 (both dispatch modes end-to-end), then Phase 18 (Endpoint Hardening)
