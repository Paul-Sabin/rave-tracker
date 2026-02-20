---
phase: 14-observability-monitoring
plan: 01
subsystem: infra
tags: [sentry, logtail, better-stack, structured-logging, json-logging, correlation-id, request-tracing, fastapi, asgi]

# Dependency graph
requires:
  - phase: 12-hosting-ssl-deployment
    provides: Production FastAPI app on Railway with gunicorn+uvicorn worker setup
  - phase: 13-scraper-resilience
    provides: Final scraper and scheduler implementation to monitor

provides:
  - Structured JSON logging with request_id correlation field in every log line
  - X-Request-ID response header on every HTTP request (uuid4 hex, 32 chars)
  - Sentry error tracking with FastAPI auto-integration and request_id tag on errors
  - Better Stack log shipping via non-blocking QueueHandler+QueueListener
  - Sentry user context (user_id, email) bound per request via auth dependency
  - Graceful degradation when SENTRY_DSN / LOGTAIL_SOURCE_TOKEN not configured

affects:
  - future phases requiring log querying or error debugging in production
  - any phase adding new auth flows (should call set_sentry_user)

# Tech tracking
tech-stack:
  added:
    - asgi-correlation-id>=4.3.0 (request ID generation and propagation)
    - python-json-logger>=3.0.0 (JSON log formatter, v4.0.0 installed)
    - sentry-sdk>=2.0.0 (error tracking with FastAPI auto-integration)
    - logtail-python>=0.2.10 (Better Stack log handler)
  patterns:
    - CorrelationIdFilter on all log handlers ensures request_id in every log record
    - QueueHandler+QueueListener for non-blocking log shipping (avoids blocking web workers)
    - init_sentry() called before FastAPI app creation (required for ASGI auto-integration)
    - Middleware ordering: CorrelationIdMiddleware added last (processed first as outermost)
    - set_sentry_user in auth dependency + clear_sentry_user in HTTP middleware (bind/clear per request)
    - atexit.register(listener.stop) + explicit lifespan stop for graceful shutdown

key-files:
  created:
    - ra-tracker/ra_tracker/observability/__init__.py
    - ra-tracker/ra_tracker/observability/logging_config.py
    - ra-tracker/ra_tracker/observability/sentry_config.py
  modified:
    - ra-tracker/requirements.txt
    - ra-tracker/ra_tracker/config.py
    - ra-tracker/ra_tracker/web/app.py
    - ra-tracker/ra_tracker/main.py
    - ra-tracker/ra_tracker/web/auth.py

key-decisions:
  - "python-json-logger v3+ uses pythonjsonlogger.json (not pythonjsonlogger.jsonlogger) - plan explicitly called this out"
  - "CorrelationIdMiddleware added AFTER CSRFMiddleware in code (FastAPI reverse order = outermost)"
  - "init_sentry() called before FastAPI app creation in create_app() for auto-integration to work"
  - "QueueHandler+QueueListener for non-blocking Better Stack shipping (avoids blocking web workers)"
  - "Sentry user context bound in get_current_user() auth dependency, cleared in HTTP middleware"
  - "enable_logs=False in Sentry init (logs go to Better Stack, not Sentry)"
  - "traces_sample_rate=0.1 (10% performance tracing) to avoid Sentry quota exhaustion"
  - "Graceful degradation: empty SENTRY_DSN = no Sentry; empty LOGTAIL_SOURCE_TOKEN = stdout only"

patterns-established:
  - "Request ID pattern: CorrelationIdMiddleware generates X-Request-ID header; CorrelationIdFilter injects it into every log"
  - "Observability init pattern: Sentry before app, logging in lifespan, both initialized from config.observability"
  - "User context pattern: set in auth dependency, clear in HTTP middleware (per-request lifecycle)"

# Metrics
duration: 4min
completed: 2026-02-20
---

# Phase 14 Plan 01: Structured Logging and Sentry Error Tracking Summary

**Structured JSON logging with X-Request-ID correlation headers, Sentry error tracking with user context, and non-blocking Better Stack log shipping via QueueHandler — all wired into the FastAPI lifespan with graceful degradation when tokens are absent.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-20T18:03:22Z
- **Completed:** 2026-02-20T18:07:42Z
- **Tasks:** 2
- **Files modified:** 7 (5 modified, 3 created)

## Accomplishments

- Every HTTP request now carries a unique `X-Request-ID` response header (uuid4 hex, 32 chars)
- All `ra_tracker` logs emit structured JSON with `timestamp`, `level`, `logger`, `message`, `request_id` fields in production
- Sentry SDK initialized before FastAPI app creation for full ASGI auto-integration; user context (id, email) bound per authenticated request
- Better Stack log shipping via non-blocking `QueueHandler`+`QueueListener` — web workers never block on remote log writes
- `ObservabilityConfig` dataclass in config.py with `SENTRY_DSN`, `LOGTAIL_SOURCE_TOKEN`, `ENVIRONMENT`, `LOG_LEVEL` env var loading
- App gracefully runs without any observability credentials (stdout-only JSON logging, no Sentry, no Better Stack)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create observability module with logging config, Sentry init, and dependencies** - `70135d3` (feat)
2. **Task 2: Wire observability into FastAPI app lifecycle and request pipeline** - `31989d5` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `ra-tracker/ra_tracker/observability/__init__.py` - Module init
- `ra-tracker/ra_tracker/observability/logging_config.py` - `setup_logging()`: JSON formatter, CorrelationIdFilter, QueueHandler for Better Stack
- `ra-tracker/ra_tracker/observability/sentry_config.py` - `init_sentry()`, `set_sentry_user()`, `clear_sentry_user()` helpers
- `ra-tracker/requirements.txt` - Added asgi-correlation-id, python-json-logger, sentry-sdk, logtail-python
- `ra-tracker/ra_tracker/config.py` - Added `ObservabilityConfig` dataclass + env var loading in `Config.load()`
- `ra-tracker/ra_tracker/web/app.py` - Sentry init, CorrelationIdMiddleware, lifespan logging setup, bind_user_context middleware
- `ra-tracker/ra_tracker/main.py` - `setup_logging()` delegates to observability module with env var fallbacks
- `ra-tracker/ra_tracker/web/auth.py` - `get_current_user()` calls `set_sentry_user()` after successful auth

## Decisions Made

- `python-json-logger` v3+ changed module path: use `pythonjsonlogger.json.JsonFormatter` not `pythonjsonlogger.jsonlogger.JsonFormatter`
- `CorrelationIdMiddleware` added after `CSRFMiddleware` in code — FastAPI processes middleware in reverse order so it becomes outermost (generates request ID before any other middleware)
- `init_sentry()` called before `app = FastAPI(...)` in `create_app()` — required for Sentry's ASGI auto-integration to hook in
- `QueueHandler`+`QueueListener` used for Better Stack (not direct handler) — keeps web workers non-blocking during log writes
- Sentry user set in auth dependency (`get_current_user`) and cleared in HTTP middleware (`bind_user_context`) — request-scoped lifecycle
- `enable_logs=False` in `sentry_sdk.init()` — logs go exclusively to Better Stack, not duplicated to Sentry
- `traces_sample_rate=0.1` — 10% performance tracing to stay within Sentry quota

## Deviations from Plan

None - plan executed exactly as written. The `=1.5.0`, `=3.0.0`, `=4.3.0` stray files from a malformed first pip install attempt were cleaned up (deviation Rule 3 - blocking issue).

## Issues Encountered

- Stray files (`=1.5.0`, `=3.0.0`, `=4.3.0`) created in `ra-tracker/` by a pip install command with `>=` being parsed as shell operators. Cleaned up before commit. Subsequent install used properly quoted arguments.

## User Setup Required

**External services require manual configuration before observability features activate in production:**

### Sentry

1. Create a Sentry project at sentry.io -> Create Project -> Python -> FastAPI
2. Copy the DSN from Settings -> Client Keys
3. Add to Railway environment: `SENTRY_DSN=https://...@sentry.io/...`

### Better Stack (Logtail)

1. Create a Better Stack account at logs.betterstack.com
2. Go to Sources -> Create source -> Select "Python"
3. Copy the source token
4. Add to Railway environment: `LOGTAIL_SOURCE_TOKEN=<token>`

### Other env vars (optional)

- `ENVIRONMENT=production` (default: "production")
- `LOG_LEVEL=INFO` (default: "INFO")

Both services are optional — app runs in stdout-only JSON mode without them.

## Next Phase Readiness

- Structured logging foundation is in place for Plans 02 and 03 (health checks and performance monitoring)
- `request_id` field in logs enables correlation with Sentry errors for production debugging
- Sentry and Better Stack integration is conditional — Plan 02 can add uptime monitoring independently
- No blockers

## Self-Check: PASSED

All created files verified on disk:
- FOUND: ra-tracker/ra_tracker/observability/__init__.py
- FOUND: ra-tracker/ra_tracker/observability/logging_config.py
- FOUND: ra-tracker/ra_tracker/observability/sentry_config.py
- FOUND: .planning/phases/14-observability-monitoring/14-01-SUMMARY.md

All task commits verified in git log:
- FOUND: 70135d3 (Task 1 - observability module)
- FOUND: 31989d5 (Task 2 - wiring into app lifecycle)

---
*Phase: 14-observability-monitoring*
*Completed: 2026-02-20*
