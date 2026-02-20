---
phase: 14-observability-monitoring
plan: 03
subsystem: monitoring
tags: [telegram, alerting, sqlite, postgresql, admin, scraper, circuit-breaker]

# Dependency graph
requires:
  - phase: 14-02
    provides: "scraper_fetch_log, complete_scraper_fetch(), admin scraper status page"
  - phase: 13-scraper-resilience
    provides: "circuit_breaker singleton, scraper_health_log"
provides:
  - "scraper_alert_state singleton table in SQLite and PostgreSQL schemas"
  - "get_scraper_alert_state() / set_scraper_alert_sent() / update_consecutive_failures() / reset_consecutive_failures() DB methods"
  - "ScraperAlerter service: Telegram admin alerts after 3 consecutive failures with silence and recovery logic"
  - "Alert state integrated at all 3 fetch exit paths (SUCCESS, FAILURE, SKIPPED)"
  - "Admin dashboard: Consecutive Failures counter + Alert Status section in Current Status card"
affects:
  - future-admin-enhancements

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Singleton alert state table (id=1 enforced via CHECK constraint) for crash-safe state persistence"
    - "Alert silencing: alert_sent flag prevents duplicate alerts during extended outages"
    - "Non-blocking alerter: all check_and_alert() calls wrapped in try/except in jobs.py"
    - "asyncio.new_event_loop() pattern for synchronous Telegram sends from scheduler thread"

key-files:
  created:
    - ra-tracker/ra_tracker/services/scraper_alerter.py
  modified:
    - ra-tracker/ra_tracker/database.py
    - ra-tracker/ra_tracker/scheduler/jobs.py
    - ra-tracker/ra_tracker/web/admin.py
    - ra-tracker/ra_tracker/web/templates/admin/scraper_status.html

key-decisions:
  - "Singleton scraper_alert_state table (id=1 CHECK constraint) ensures exactly one state row survives restarts"
  - "Alert silencing via alert_sent boolean: alert fires once at threshold, stays silent until recovery clears it"
  - "SKIPPED status (circuit breaker open) counts as failure for alerting purposes"
  - "ScraperAlerter reads all state from DB on every call — no in-memory state"

patterns-established:
  - "Pattern: Wrap alerter calls in try/except at call sites — monitoring must never break the monitored system"
  - "Pattern: Recovery notification sent only if alert_sent=True — prevents spurious recovery messages"

# Metrics
duration: 3min
completed: 2026-02-20
---

# Phase 14 Plan 03: Scraper Failure Alerts Summary

**Telegram admin alerts fire after 3 consecutive scraper failures using DB-persisted singleton state, silence until recovery, and send recovery notification — all non-blocking with admin dashboard visibility**

## Performance

- **Duration:** 3 min 14s
- **Started:** 2026-02-20T18:19:52Z
- **Completed:** 2026-02-20T18:23:06Z
- **Tasks:** 2
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- Created `scraper_alert_state` singleton table in both SQLite SCHEMA and PostgreSQL PG_SCHEMA with CHECK (id=1) constraint
- Added 4 new database methods: `get_scraper_alert_state()`, `set_scraper_alert_sent()`, `update_consecutive_failures()`, `reset_consecutive_failures()`
- Created `ScraperAlerter` service: fires Telegram alert after 3 consecutive failures, silences until recovery, sends recovery notification when scraper resumes
- Wired `check_and_alert()` into all 3 fetch exit paths in `fetch_and_notify()` (SUCCESS, SKIPPED, FAILURE) — all wrapped in try/except
- Admin dashboard updated: Consecutive Failures counter (color-coded) + Alert Status section showing no-alert/warning/active-alert states

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scraper_alert_state table and ScraperAlerter service** - `5335dda` (feat)
2. **Task 2: Wire alerter into fetch pipeline and show alert state on dashboard** - `828cd9e` (feat)

**Plan metadata:** (docs commit pending)

## Files Created/Modified
- `ra-tracker/ra_tracker/services/scraper_alerter.py` - Created: ScraperAlerter class with check_and_alert(), _failure_message(), _recovery_message(), _send_telegram(); module-level singleton
- `ra-tracker/ra_tracker/database.py` - Added scraper_alert_state table to SQLite and PG schemas; added 4 alert state CRUD methods
- `ra-tracker/ra_tracker/scheduler/jobs.py` - Imported scraper_alerter; added check_and_alert calls at SKIPPED, SUCCESS, and FAILURE exit paths
- `ra-tracker/ra_tracker/web/admin.py` - Added alert_state = db.get_scraper_alert_state() and passed to template context
- `ra-tracker/ra_tracker/web/templates/admin/scraper_status.html` - Added Consecutive Failures grid item and Alert Status section to Current Status card

## Decisions Made
- **Singleton table with CHECK constraint:** `id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1)` enforces exactly one row. `INSERT OR IGNORE` (SQLite) / `ON CONFLICT DO NOTHING` (PG) ensures row exists after schema init. No race condition on startup.
- **SKIPPED counts as failure:** Circuit breaker open means scraper is not delivering data. Counts toward the failure threshold so admin is alerted during extended outages even without explicit exceptions.
- **No in-memory state in ScraperAlerter:** Every `check_and_alert()` call reads from DB. This means state is consistent across gunicorn workers (each worker can update/read independently).
- **alert_sent_at set to NULL on recovery:** Clean distinction between "currently alerting" (alert_sent=True, alert_sent_at set) and "recovered" (alert_sent=False, alert_sent_at=NULL).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. The `scraper_alert_state` table is created automatically via `init_schema()` on next app startup. Telegram alerts require `telegram.bot_token` and `telegram.chat_id` configured in config.yaml (already required for existing Telegram notifications). If these are not set, the alerter degrades gracefully and returns early.

## Next Phase Readiness
- Phase 14 complete: all 3 plans done (structured logging + Sentry, fetch persistence, scraper failure alerts)
- Observability & Monitoring milestone (v3.1) complete
- Production admin has full visibility: health metrics, fetch history, alert status, circuit breaker state

---
*Phase: 14-observability-monitoring*
*Completed: 2026-02-20*

## Self-Check: PASSED

All files verified present. All task commits verified in git history.
- FOUND: ra-tracker/ra_tracker/services/scraper_alerter.py
- FOUND: ra-tracker/ra_tracker/database.py
- FOUND: ra-tracker/ra_tracker/scheduler/jobs.py
- FOUND: ra-tracker/ra_tracker/web/admin.py
- FOUND: ra-tracker/ra_tracker/web/templates/admin/scraper_status.html
- FOUND: .planning/phases/14-observability-monitoring/14-03-SUMMARY.md
- FOUND: 5335dda (Task 1 commit)
- FOUND: 828cd9e (Task 2 commit)
