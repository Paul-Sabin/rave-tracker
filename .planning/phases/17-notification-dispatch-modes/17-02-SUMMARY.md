---
phase: 17-notification-dispatch-modes
plan: 02
subsystem: scheduler
tags: [apscheduler, cron, notifications, digest, jobs, sqlite, postgresql]

# Dependency graph
requires:
  - phase: 17-notification-dispatch-modes
    provides: queue_event_for_digest, get_queued_digest_events, mark_digest_sent DB methods; queued_for_digest column
  - phase: 16-settings-page-split
    provides: fetch_times, notification_mode, digest_time config fields in SchedulerConfig
provides:
  - CronTrigger-based fetch schedule from fetch_times list (fallback to IntervalTrigger when empty)
  - fetch_and_notify() mode-conditional dispatch: daily_digest queues, upon_fetch sends immediately
  - send_daily_digest() job: collects queued events per user, sends batched notifications, marks sent
  - get_rules_for_event_and_user(event_id, user_id) DB method for digest job rule lookup
affects: [phase-18-endpoint-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CronTrigger scheduling from HH:MM config list — one job per time, plus canonical 'fetch_and_notify' alias for first slot"
    - "notification_mode guard in fetch_and_notify(): if/else on 'daily_digest' vs default upon_fetch"
    - "Digest job reads distinct user_ids directly via SQL, then per-user event load + notify + mark_sent"

key-files:
  created: []
  modified:
    - ra-tracker/ra_tracker/scheduler/jobs.py
    - ra-tracker/ra_tracker/database.py

key-decisions:
  - "send_daily_digest() uses db.get_event(event_id) (existing method) instead of a new get_event_by_id alias — avoids redundancy"
  - "Canonical 'fetch_and_notify' job id preserved by adding an alias job for first fetch_time — ensures get_next_fetch_time() still works"
  - "get_rules_for_event_and_user added to database.py as Rule 2 (missing critical) — digest job requires it to build events_with_rules for notify_users_for_events_async"
  - "digest job queries distinct user_ids directly in SQL rather than loading all queued rows — more efficient at scale"

patterns-established:
  - "Digest send lifecycle: fetch -> queue_event_for_digest -> send_daily_digest at digest_time -> mark_digest_sent"
  - "CronTrigger fallback: if fetch_times non-empty use CronTrigger per slot, else use IntervalTrigger (legacy compat)"

requirements-completed: [SETT-12, SETT-13, SETT-14]

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 17 Plan 02: Notification Dispatch Modes — Scheduler Summary

**CronTrigger fetch schedule and two notification dispatch modes wired end-to-end: upon_fetch sends immediately, daily_digest queues to notifications table and sends batched at configured digest_time**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23T07:16:00Z
- **Completed:** 2026-02-23T07:19:36Z
- **Tasks:** 2 auto tasks (checkpoint pending human verification)
- **Files modified:** 2

## Accomplishments
- `start_scheduler()` migrated from IntervalTrigger to CronTrigger: schedules one job per `fetch_times` entry, falls back to IntervalTrigger when list is empty
- `fetch_and_notify()` now checks `notification_mode`: "daily_digest" queues events via `db.queue_event_for_digest()` per user, "upon_fetch" sends immediately (existing behaviour preserved)
- `send_daily_digest()` job added: queries users with queued events, loads event objects, calls `notify_users_for_events_async`, marks sent via `mark_digest_sent()`
- `start_scheduler()` registers `send_daily_digest` as a daily CronTrigger job at `digest_time`
- `get_rules_for_event_and_user(event_id, user_id)` added to `database.py` — joins event_rules+rules to return per-user matched rules for a given event

## Task Commits

Each task was committed atomically:

1. **Task 1+2: CronTrigger schedule + mode dispatch + send_daily_digest** - `19921b0` (feat)
2. **Task 2 (Part C): get_rules_for_event_and_user DB method** - `d7150a9` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified
- `ra-tracker/ra_tracker/scheduler/jobs.py` - CronTrigger scheduling in start_scheduler(), mode-conditional dispatch in fetch_and_notify(), new send_daily_digest() function
- `ra-tracker/ra_tracker/database.py` - Added get_rules_for_event_and_user() method

## Decisions Made
- Used existing `db.get_event(event_id)` in `send_daily_digest()` instead of adding a `get_event_by_id` alias — the method already exists with identical semantics.
- The canonical `"fetch_and_notify"` job ID is preserved by adding an extra alias job for the first fetch_time slot. This keeps `get_next_fetch_time()` working without changes.
- `get_rules_for_event_and_user` was added to database.py as a Rule 2 (missing critical functionality) deviation — the send_daily_digest job requires it, and it did not exist.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added get_rules_for_event_and_user to database.py**
- **Found during:** Task 2 (Part C — DB helper methods)
- **Issue:** Plan said "add if they don't exist" — `get_event_by_id` maps to existing `get_event()`, but `get_rules_for_event_and_user` was absent
- **Fix:** Added `get_rules_for_event_and_user(event_id, user_id)` using `_row_to_rule` pattern matching the codebase conventions
- **Files modified:** `ra-tracker/ra_tracker/database.py`
- **Verification:** All module imports pass, method present and syntactically correct
- **Committed in:** `d7150a9` (feat)

**2. [Rule 1 - Adaptation] Used db.get_event() instead of db.get_event_by_id()**
- **Found during:** Task 2 (Part B — send_daily_digest implementation)
- **Issue:** Plan specified `db.get_event_by_id(event_id)` but `get_event(event_id)` already exists with identical semantics
- **Fix:** Called `db.get_event(event_id)` directly — no alias needed
- **Files modified:** `ra-tracker/ra_tracker/scheduler/jobs.py`
- **Verification:** Function operates correctly, import checks pass

---

**Total deviations:** 2 auto-handled (1 missing critical added, 1 method name adaptation)
**Impact on plan:** Both necessary for correct digest operation. No scope creep.

## Issues Encountered
- None — all verifications passed first try.

## User Setup Required
None - no external service configuration required. Changes are backward-compatible: when `fetch_times` is empty the scheduler falls back to `IntervalTrigger` as before.

## Next Phase Readiness
- Phase 17 is complete pending human verification of checkpoint (both dispatch modes end-to-end)
- After checkpoint approval, Phase 18 (Endpoint Hardening) can proceed
- DB schema and scheduler jobs are fully wired; the admin settings UI (Phase 16) already writes the config values these jobs read

---
*Phase: 17-notification-dispatch-modes*
*Completed: 2026-02-23*
