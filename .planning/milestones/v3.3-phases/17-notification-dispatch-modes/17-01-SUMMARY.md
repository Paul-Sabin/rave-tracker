---
phase: 17-notification-dispatch-modes
plan: 01
subsystem: database
tags: [sqlite, postgresql, notifications, digest, schema-migration]

# Dependency graph
requires:
  - phase: 16-settings-page-split
    provides: notification_mode config field validated and persisted in admin/settings
provides:
  - queued_for_digest column in notifications table (SCHEMA + PG_SCHEMA + Migration 13)
  - Database.queue_event_for_digest(event_id, user_id) — idempotent queue insert
  - Database.get_queued_digest_events(user_id) — retrieve pending digest event_ids
  - Database.mark_digest_sent(event_ids, user_id) — mark queued records as sent
affects: [17-02-scheduler-dispatch-modes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Boolean column added to both SCHEMA (SQLite) and PG_SCHEMA (PostgreSQL) in tandem"
    - "Migration appended as Migration 13 for existing database upgrades"
    - "_true_val/_false_val properties used for boolean literal compatibility"
    - "INSERT OR IGNORE (SQLite) / ON CONFLICT DO NOTHING (PostgreSQL) for idempotent inserts"

key-files:
  created: []
  modified:
    - ra-tracker/ra_tracker/database.py

key-decisions:
  - "SQLite SCHEMA notifications table updated to include user_id column (was only added via migration 5 previously) — aligns base schema with migrated state"
  - "queue_event_for_digest uses rule_id=0 (same as add_event_notification) for per-event dedup via UNIQUE(event_id, rule_id)"
  - "has_event_notification unchanged — returns True for any row with matching event_id, covering both queued and sent records"

patterns-established:
  - "Digest queue lifecycle: queue_event_for_digest -> get_queued_digest_events -> mark_digest_sent"
  - "queued_for_digest=True + sent_at IS NULL = pending; queued_for_digest=False + sent_at set = sent"

requirements-completed: [SETT-13]

# Metrics
duration: 8min
completed: 2026-02-23
---

# Phase 17 Plan 01: Notification Dispatch Modes — DB Schema Summary

**notifications table extended with queued_for_digest boolean column and three new Database methods providing the digest queue lifecycle API**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-23T07:11:31Z
- **Completed:** 2026-02-23T07:19:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `queued_for_digest BOOLEAN DEFAULT 0/FALSE` to notifications table in SCHEMA (SQLite), PG_SCHEMA (PostgreSQL), and MIGRATIONS (Migration 13)
- Implemented `Database.queue_event_for_digest(event_id, user_id)` — idempotent insert using INSERT OR IGNORE / ON CONFLICT DO NOTHING
- Implemented `Database.get_queued_digest_events(user_id)` — returns list of event_ids with queued_for_digest=True and sent_at IS NULL
- Implemented `Database.mark_digest_sent(event_ids, user_id)` — sets sent_at and clears queued_for_digest flag for a list of event_ids

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend notifications schema and add digest queue DB methods** - `e28501b` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified
- `ra-tracker/ra_tracker/database.py` - Added queued_for_digest column to SCHEMA/PG_SCHEMA/MIGRATIONS, added three digest queue methods

## Decisions Made
- SQLite SCHEMA notifications table was updated to also include `user_id INTEGER` (which was previously only added via Migration 5). This keeps the base schema definition in sync with the fully-migrated state — consistent with how PG_SCHEMA already included all migrated columns.
- `queue_event_for_digest` uses `rule_id=0` to leverage the existing `UNIQUE(event_id, rule_id)` constraint for deduplication, matching the pattern of `add_event_notification`.
- `has_event_notification` left unchanged — its broad `SELECT 1 WHERE event_id = ?` query naturally covers both queued and sent records, preventing double-queuing in digest mode.

## Deviations from Plan

None - plan executed exactly as written. `_false_val` property already existed in the Database class, no additional definition needed.

## Issues Encountered
- Config validation requires env vars (TELEGRAM_BOT_TOKEN, SECRET_KEY, BREVO_SMTP_PASSWORD) even for SQLite-only tests. Resolved by passing dummy env vars in the verification command.

## User Setup Required
None - no external service configuration required. Migration 13 will run automatically on next startup via `init_schema()`.

## Next Phase Readiness
- Phase 17 Plan 02 (scheduler dispatch modes) can now call `queue_event_for_digest`, `get_queued_digest_events`, and `mark_digest_sent` from jobs.py
- DB schema changes are backward-compatible: new column defaults to 0/FALSE, existing rows unaffected

---
*Phase: 17-notification-dispatch-modes*
*Completed: 2026-02-23*
