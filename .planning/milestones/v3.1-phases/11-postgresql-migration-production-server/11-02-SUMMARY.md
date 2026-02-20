---
phase: 11-postgresql-migration-production-server
plan: 02
subsystem: server
tags: [gunicorn, uvicorn, health-check, scheduler, production]
dependency-graph:
  requires:
    - dual-mode-database-support
  provides:
    - production-server-infrastructure
    - scheduler-process-separation
    - health-endpoint
  affects:
    - deployment-configuration
    - process-management
tech-stack:
  added:
    - gunicorn>=23.0.0
  patterns:
    - Gunicorn with UvicornWorker for multi-process ASGI
    - Separate scheduler process via --scheduler-only flag
    - /health endpoint with database connectivity check
    - Procfile for hosting platform process declarations
key-files:
  created:
    - ra-tracker/Procfile: Web (gunicorn) and scheduler process declarations
  modified:
    - ra-tracker/ra_tracker/main.py: Added --scheduler-only mode
    - ra-tracker/ra_tracker/web/app.py: Added /health endpoint, load_dotenv for gunicorn mode
    - ra-tracker/requirements.txt: Added gunicorn>=23.0.0
decisions:
  - Gunicorn with UvicornWorker (not standalone uvicorn) for multi-process serving
  - Scheduler as separate process via --scheduler-only (prevents 4x duplicate APScheduler jobs)
  - /health endpoint is public (no auth, no CSRF) for load balancer access
  - Graceful shutdown via gunicorn --graceful-timeout 30
metrics:
  duration: 5 minutes
  tasks-completed: 2
  files-modified: 4
  files-created: 1
  completed-at: 2026-02-16T20:00:00Z
---

# Phase 11 Plan 02: Production Server Infrastructure Summary

**One-liner:** Gunicorn with uvicorn workers, separated scheduler process, /health endpoint with DB check, and Procfile for deployment platforms.

## What Was Built

Added production server infrastructure: multi-worker ASGI serving, scheduler process separation, health monitoring, and deployment configuration.

### Task 1: Add --scheduler-only mode and gunicorn support

**Files Modified:**
- `ra-tracker/requirements.txt`: Added `gunicorn>=23.0.0`
- `ra-tracker/ra_tracker/main.py`:
  - Added `--scheduler-only` argument to argparse
  - Scheduler-only mode: starts scheduler, blocks with signal.pause() (Unix) or sleep loop (Windows)
  - Existing `--no-scheduler` and `--fetch-only` modes preserved

**Files Created:**
- `ra-tracker/Procfile`:
  - `web:` gunicorn with uvicorn workers, configurable PORT and WEB_CONCURRENCY
  - `scheduler:` python -m ra_tracker.main --scheduler-only
  - Graceful shutdown: --graceful-timeout 30, --timeout 60

**Commit:** da49337

### Task 2: Add /health endpoint with database connectivity check

**Files Modified:**
- `ra-tracker/ra_tracker/web/app.py`:
  - Added `GET /health` endpoint (public, no auth/CSRF)
  - Runs `SELECT 1` against database via get_connection()
  - Returns 200 `{"status": "healthy", "database": "connected"}` on success
  - Returns 503 `{"status": "unhealthy", "database": "disconnected", "error": "..."}` on failure
  - Added `load_dotenv()` call in create_app() for gunicorn mode (bypasses main.py)

**Commit:** 0c1812a

## Deviations from Plan

None - plan executed as written.

## Testing & Verification

- `--scheduler-only` flag present in main.py argparse
- signal.pause() blocking for Unix, sleep loop for Windows
- Procfile contains both web: and scheduler: declarations
- /health endpoint defined with SELECT 1 database check
- gunicorn>=23.0.0 in requirements.txt
- load_dotenv() called in create_app()

## Self-Check: PASSED

All artifacts verified present and functional.
