---
phase: 14-observability-monitoring
plan: "04"
subsystem: infra
tags: [python-json-logger, starlette, middleware, structured-logging, observability]

# Dependency graph
requires:
  - phase: 14-observability-monitoring
    provides: JSON logging with CorrelationIdFilter and ra_tracker logger hierarchy

provides:
  - AccessLogMiddleware that emits HTTP method, path, status_code, duration_ms as structured JSON fields per request
  - OBS-01 gap closure: HTTP status codes now appear as top-level fields in JSON log output

affects: [deployment, log analysis, Better Stack log queries]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - BaseHTTPMiddleware subclass for structured per-request HTTP access logging
    - Middleware ordering: AccessLogMiddleware first (innermost) so CorrelationId is set before logging

key-files:
  created:
    - ra-tracker/ra_tracker/observability/access_log_middleware.py
  modified:
    - ra-tracker/ra_tracker/web/app.py

key-decisions:
  - "AccessLogMiddleware added first (innermost) so it runs after CorrelationIdMiddleware assigns request_id and captures the final response status_code"
  - "Skip /health and /static/* paths to suppress load balancer and static asset noise"
  - "uvicorn.access remains at WARNING — AccessLogMiddleware replaces uvicorn access logs with cleaner structured output"
  - "query string included in extra only when non-empty to reduce log verbosity"

patterns-established:
  - "Structured access logging: logger.info(message, extra={method, path, status_code, duration_ms}) — extra fields become top-level JSON keys via python-json-logger"
  - "Logger inherits from ra_tracker hierarchy (ra_tracker.access) to pick up JSON formatter and CorrelationIdFilter automatically"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-02-20
---

# Phase 14 Plan 04: HTTP Access Log Middleware Summary

**Starlette BaseHTTPMiddleware that emits structured JSON access logs with method, path, status_code, and duration_ms as discrete fields, closing the OBS-01 verification gap for HTTP status codes in the structured log stream**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-20T19:04:34Z
- **Completed:** 2026-02-20T19:07:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Created `access_log_middleware.py` with `AccessLogMiddleware` (35 lines) inheriting from `BaseHTTPMiddleware`
- Logger `ra_tracker.access` inherits JSON formatter, CorrelationIdFilter, and Better Stack handler from the `ra_tracker` logger hierarchy — no additional logging config needed
- Registered `AccessLogMiddleware` first in `create_app()` so it runs innermost: CorrelationId is already set when the log line fires, ensuring `request_id` is always populated
- HTTP status codes now appear as discrete `status_code` JSON fields — OBS-01 gap closed

## Task Commits

Each task was committed atomically:

1. **Task 1: Create AccessLogMiddleware and register in FastAPI app** - `49b0c3b` (feat)

**Plan metadata:** _(to be added after final commit)_

## Files Created/Modified

- `ra-tracker/ra_tracker/observability/access_log_middleware.py` - BaseHTTPMiddleware that logs per-request structured data (method, path, status_code, duration_ms), skipping /health and /static
- `ra-tracker/ra_tracker/web/app.py` - Added AccessLogMiddleware import and registration as first middleware (innermost execution order)

## Decisions Made

- AccessLogMiddleware is added first (innermost) rather than last — this ensures the final response status_code is captured after all other middleware has processed, and CorrelationId is already set
- `/health` and `/static` skipped to suppress load balancer health check spam and static asset noise
- `uvicorn.access` remains at WARNING — the new middleware produces cleaner structured output, making uvicorn's plain-text access logs redundant
- Query string only included in `extra` when non-empty, keeping concise logs for parameterless requests

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The middleware is wired automatically when the app starts.

## Next Phase Readiness

Phase 14 is fully complete. All observability and monitoring goals are met:
- Structured JSON logs with request IDs (Phase 14-01)
- Scraper fetch cycle persistence to DB (Phase 14-02)
- Telegram admin alerts on scraper failures (Phase 14-03)
- HTTP status codes in structured log stream (Phase 14-04, OBS-01 gap closed)

v3.1 milestone is complete. All 4 plans in Phase 14 delivered.

---
*Phase: 14-observability-monitoring*
*Completed: 2026-02-20*
