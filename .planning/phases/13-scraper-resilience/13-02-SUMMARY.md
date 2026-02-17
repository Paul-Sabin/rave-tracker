---
phase: 13-scraper-resilience
plan: 02
subsystem: scraper-resilience
tags: [circuit-breaker, error-logging, fetch-pipeline, scheduler-integration]
dependency_graph:
  requires:
    - ra-tracker/ra_tracker/api/circuit_breaker.py (from 13-01)
    - ra-tracker/ra_tracker/api/ra_client.py with IPBlockedException (from 13-01)
  provides:
    - Circuit breaker-integrated fetch pipeline
    - Scraper health log database table and methods
    - Scheduler circuit breaker awareness
  affects:
    - All scheduled and manual fetch operations
    - Database schema (new scraper_health_log table)
    - Admin dashboard (circuit breaker status available)
tech_stack:
  added:
    - scraper_health_log table (SQLite: AUTOINCREMENT, PostgreSQL: SERIAL)
  patterns:
    - Circuit breaker pre-flight checks in fetch pipeline
    - Error logging with circuit breaker state correlation
    - Fetch cycle success/failure recording
    - 30-day log retention with daily cleanup
key_files:
  created: []
  modified:
    - ra-tracker/ra_tracker/database.py (+90 lines: table schema, 3 methods)
    - ra-tracker/ra_tracker/services/fetcher.py (+62 lines, -9 lines)
    - ra-tracker/ra_tracker/scheduler/jobs.py (+29 lines)
decisions:
  - "Log all scraper errors with circuit breaker state for correlation analysis"
  - "IPBlockedException re-raised from fetch_for_rule to abort entire cycle in fetch_all_rules"
  - "Circuit breaker success/failure recording in fetch_all_rules (not scheduler)"
  - "Scraper health log cleanup integrated into daily purge_expired_accounts job"
  - "get_scheduler_status() includes full circuit breaker state for admin dashboard"
metrics:
  duration: "3m 42s"
  tasks_completed: 2
  files_created: 0
  files_modified: 3
  commits: 2
  completed_at: "2026-02-17T20:28:47Z"
---

# Phase 13 Plan 02: Fetch Pipeline Circuit Breaker Integration Summary

**One-liner:** Circuit breaker-aware fetch pipeline with database error logging and 30-day health log retention.

## What Was Built

Integrated the circuit breaker into the fetch pipeline at both fetcher and scheduler levels, with comprehensive error logging to a new database table:

1. **Database schema changes** (`database.py`):
   - Added `scraper_health_log` table to both SCHEMA (SQLite) and PG_SCHEMA (PostgreSQL)
   - Table tracks: timestamp, status_code, error_message, error_type, circuit_breaker_state, rule_target
   - Indexed on timestamp DESC for efficient recent error queries
   - Three new methods:
     - `log_scraper_error()`: Insert error records with circuit breaker state
     - `get_recent_scraper_errors(limit=10)`: Retrieve recent errors for admin dashboard
     - `cleanup_old_scraper_logs(days=30)`: Delete logs older than 30 days

2. **Fetcher integration** (`fetcher.py`):
   - `fetch_all_rules()` checks `circuit_breaker.should_allow_fetch()` before starting
   - Returns empty dict if circuit breaker is OPEN (with warning log)
   - `fetch_for_rule()` catches `IPBlockedException` specifically:
     - Logs to database with status_code=403, error_type='HTTP'
     - Re-raises exception to abort entire fetch cycle
   - Other exceptions logged with status_code=None, error_type='EXCEPTION'
   - Returns empty list for non-blocking errors
   - Successful fetch cycle calls `circuit_breaker.record_success()`
   - Failed fetch cycle (IPBlockedException) calls `circuit_breaker.record_failure()`

3. **Scheduler integration** (`jobs.py`):
   - `fetch_and_notify()` checks circuit breaker at start (before DB/config access)
   - Returns early if circuit breaker is OPEN, logs cooldown remaining time
   - Per-rule exception handler logs errors to database with circuit breaker state
   - `purge_expired_accounts()` now calls `cleanup_old_scraper_logs(days=30)` daily
   - `get_scheduler_status()` includes full circuit breaker state dict:
     - state, failure_count, last_success/failure timestamps
     - cooldown_duration, cooldown_remaining, error_count_since_success

## Deviations from Plan

None - plan executed exactly as written.

## Key Decisions Made

1. **Error logging location**: Decided to log errors in both `fetch_for_rule()` and scheduler's per-rule handler. This provides redundancy and captures errors from different code paths (direct fetcher usage vs scheduled fetches).

2. **Circuit breaker recording location**: Placed success/failure recording in `fetch_all_rules()` (not scheduler) so that manual admin fetches also respect and update circuit breaker state.

3. **Cleanup job placement**: Integrated scraper log cleanup into existing `purge_expired_accounts()` daily job rather than creating a separate job. Simpler scheduler configuration with no functional difference.

4. **IPBlockedException handling flow**: Re-raise from `fetch_for_rule()` to `fetch_all_rules()` allows clean abort semantics. The exception is caught at the top level, logged, and used to record circuit breaker failure.

## Technical Implementation

**Fetch cycle circuit breaker flow:**
```python
# In fetch_all_rules()
if not circuit_breaker.should_allow_fetch():
    return {}  # Blocked by circuit breaker

try:
    for rule in rules:
        try:
            events = fetch_for_rule(rule)  # May raise IPBlockedException
        except IPBlockedException:
            fetch_succeeded = False
            break  # Abort cycle

    if fetch_succeeded:
        circuit_breaker.record_success()
    else:
        circuit_breaker.record_failure(error_info)
```

**Database schema (dual-mode):**
```sql
-- SQLite
CREATE TABLE scraper_health_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status_code INTEGER,
    error_message TEXT,
    error_type TEXT,
    circuit_breaker_state TEXT,
    rule_target TEXT
);

-- PostgreSQL
CREATE TABLE scraper_health_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ...
);
```

## Files Changed

**Modified:**
- `ra-tracker/ra_tracker/database.py` (+90 lines)
  - Added scraper_health_log table to SCHEMA and PG_SCHEMA
  - Added index: idx_scraper_health_timestamp
  - New methods: log_scraper_error(), get_recent_scraper_errors(), cleanup_old_scraper_logs()

- `ra-tracker/ra_tracker/services/fetcher.py` (+62, -9 lines)
  - Added imports: IPBlockedException, circuit_breaker
  - Modified fetch_all_rules(): circuit breaker pre-flight check, success/failure recording
  - Modified fetch_for_rule(): IPBlockedException catch and re-raise, error logging

- `ra-tracker/ra_tracker/scheduler/jobs.py` (+29 lines)
  - Added import: circuit_breaker
  - Modified fetch_and_notify(): circuit breaker pre-flight check with cooldown logging
  - Modified per-rule exception handler: database error logging
  - Modified purge_expired_accounts(): scraper log cleanup call
  - Modified get_scheduler_status(): circuit breaker state dict

## Testing & Verification

**Verified:**
- Database table creation: scraper_health_log exists in both SQLite and PostgreSQL schemas
- log_scraper_error() successfully inserts records
- get_recent_scraper_errors() retrieves records ordered by timestamp DESC
- Circuit breaker integration: Fetcher.fetch_all_rules() imports circuit_breaker
- Scheduler status: get_scheduler_status() includes 'circuit_breaker' key
- IPBlockedException properly imported in fetcher.py

**Backward compatibility:**
All existing fetch operations inherit circuit breaker protection automatically. No API changes to public methods.

## Next Steps

**Immediate:**
1. Plan 13-03: Admin dashboard integration
   - Scraper status panel displaying circuit breaker state
   - Recent error log display (last 10 errors)
   - Manual fetch button with circuit breaker bypass option
   - Configurable fetch schedule UI

**Future considerations:**
- Add metrics tracking for scraper uptime/error rates
- Consider circuit breaker state persistence across restarts (currently in-memory)
- Add admin notification when circuit breaker trips (email/Telegram)

## Self-Check: PASSED

**Files exist:**
- FOUND: ra-tracker/ra_tracker/database.py (modified)
- FOUND: ra-tracker/ra_tracker/services/fetcher.py (modified)
- FOUND: ra-tracker/ra_tracker/scheduler/jobs.py (modified)

**Schema verification:**
```bash
$ grep -n "scraper_health_log" ra-tracker/ra_tracker/database.py
144:CREATE TABLE IF NOT EXISTS scraper_health_log (
163:CREATE INDEX IF NOT EXISTS idx_scraper_health_timestamp ON scraper_health_log(timestamp DESC);
368:CREATE TABLE IF NOT EXISTS scraper_health_log (
390:CREATE INDEX IF NOT EXISTS idx_scraper_health_timestamp ON scraper_health_log(timestamp DESC);
2118:        """Log a scraper error to the health log.
2137:        """Get recent scraper errors from health log.
2150:        """Delete scraper health log entries older than specified days.
```

**Commits exist:**
- FOUND: 1685f90 (Task 1: scraper_health_log table and methods)
- FOUND: d12a434 (Task 2: circuit breaker integration)

**Integration test:**
```python
>>> from ra_tracker.services.fetcher import Fetcher
>>> from ra_tracker.api.circuit_breaker import circuit_breaker
>>> circuit_breaker.should_allow_fetch()
True
>>> from ra_tracker.scheduler.jobs import get_scheduler_status
>>> status = get_scheduler_status()
>>> 'circuit_breaker' in status
True
>>> status['circuit_breaker']['state']
'CLOSED'
```

All verifications passed. Plan executed successfully.
