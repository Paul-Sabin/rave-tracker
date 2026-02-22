---
phase: 08-account-lifecycle-admin-audit
plan: 01
subsystem: database
tags: [soft-delete, purge, audit, cron, sqlite]

# Dependency graph
requires:
  - phase: 05-audit-foundation-csrf-protection
    provides: Audit logging infrastructure (audit_logs table, log_audit_event helper)
provides:
  - deleted_at and scheduled_purge_at columns on users table
  - soft_delete_user, recover_user, hard_delete_user database methods
  - get_users_pending_purge method for cron job
  - anonymize_audit_logs_for_user method for GDPR compliance
  - purge_expired_accounts daily cron job at 3 AM UTC
  - log_audit_event_direct helper for background jobs
affects:
  - 08-02 (delete account routes will use soft_delete_user)
  - 08-03 (recovery routes will use recover_user)
  - 08-04 (audit log UI will show anonymized entries)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Soft delete with deleted_at timestamp (not boolean) for grace period"
    - "scheduled_purge_at stored in DB (not calculated at query time)"
    - "APScheduler CronTrigger for daily background job"
    - "Audit log anonymization: NULL user_id + anonymized flag in details"
    - "SHA256 hash (first 8 chars) for anonymized correlation"

key-files:
  created: []
  modified:
    - ra-tracker/ra_tracker/database.py
    - ra-tracker/ra_tracker/scheduler/jobs.py
    - ra-tracker/ra_tracker/web/audit.py

key-decisions:
  - "UTC timestamps for all soft delete operations (avoid timezone confusion)"
  - "Deletion order: event_rules -> notifications -> rules -> sessions -> telegram_link_codes -> user"
  - "Anonymize audit logs BEFORE hard delete (preserve user context for log)"
  - "3 AM UTC for purge job (off-peak hours)"

patterns-established:
  - "log_audit_event_direct for background job audit logging (no Request object)"
  - "User dataclass includes deleted_at and scheduled_purge_at Optional[datetime] fields"
  - "All User-returning methods now include soft delete fields"

# Metrics
duration: 12min
completed: 2026-02-08
---

# Phase 8 Plan 1: Soft Delete Infrastructure Summary

**SQLite soft delete columns with 30-day grace period and daily purge cron job using APScheduler CronTrigger**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-08
- **Completed:** 2026-02-08
- **Tasks:** 3/3
- **Files modified:** 3

## Accomplishments

- Added Migration 10 with deleted_at and scheduled_purge_at columns to users table
- Added deleted_at and scheduled_purge_at fields to User dataclass
- Updated all User-returning methods to include soft delete fields
- Implemented soft_delete_user and recover_user for grace period management
- Implemented get_users_pending_purge for finding accounts past grace period
- Implemented anonymize_audit_logs_for_user for GDPR-compliant data retention
- Implemented hard_delete_user with foreign key-safe deletion order
- Implemented is_user_deleted for login flow detection
- Added log_audit_event_direct helper for background job audit logging
- Added purge_expired_accounts daily cron job running at 3 AM UTC
- Registered purge job in start_scheduler with CronTrigger

## Task Commits

Each task was committed atomically:

1. **Task 1: Add soft delete columns and migration** - `b34af5d` (feat)
2. **Task 2: Add soft delete database methods** - `51578cb` (feat)
3. **Task 3: Add daily purge cron job** - `079528c` (feat)

## Files Created/Modified

- `ra-tracker/ra_tracker/database.py` - Migration 10, User dataclass fields, 6 soft delete methods, updated User-returning methods
- `ra-tracker/ra_tracker/scheduler/jobs.py` - purge_expired_accounts job, CronTrigger registration
- `ra-tracker/ra_tracker/web/audit.py` - log_audit_event_direct helper

## Decisions Made

- **UTC everywhere:** All soft delete timestamps use datetime.utcnow() for consistency
- **Timestamp over boolean:** Using deleted_at timestamp (not boolean) enables grace period calculation
- **Store scheduled date:** scheduled_purge_at stored in DB rather than calculated (avoids race conditions)
- **Anonymization approach:** NULL user_id + anonymized=1 flag + 8-char SHA256 hash of original user_id
- **Deletion order:** Delete child records first to avoid FK constraint violations

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added telegram_link_codes to hard_delete_user**

- **Found during:** Task 2
- **Issue:** Plan didn't mention deleting telegram_link_codes when hard deleting user
- **Fix:** Added DELETE FROM telegram_link_codes WHERE user_id = ? in deletion sequence
- **Files modified:** ra-tracker/ra_tracker/database.py
- **Commit:** 51578cb

## Issues Encountered

None - plan executed as written with minor enhancement for complete FK cleanup.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Soft delete infrastructure ready for delete account UI (08-02)
- Recovery detection ready for login flow modification (08-02/08-03)
- Purge job will run automatically once scheduler starts
- Audit log anonymization tested and working

---
*Phase: 08-account-lifecycle-admin-audit*
*Completed: 2026-02-08*
