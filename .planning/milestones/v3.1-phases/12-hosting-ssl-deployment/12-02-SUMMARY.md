---
phase: 12-hosting-ssl-deployment
plan: 02
subsystem: deployment
tags: [infrastructure, railway, postgresql, migration, production]
dependency_graph:
  requires:
    - "12-01: Railway deployment configuration (Dockerfile, railway.json)"
    - "11-03: SQLite-to-PostgreSQL migration tooling"
    - "11-01: Dual-mode database layer"
  provides:
    - "Live production application on Railway"
    - "PostgreSQL database with migrated data (5,032 rows)"
    - "Auto-deploy pipeline from GitHub main branch"
  affects:
    - "12-03: Custom domain & SSL (builds on running deployment)"
tech_stack:
  added:
    - Railway web service (production)
    - Railway PostgreSQL (production database)
    - Railway scheduler service (background jobs)
  patterns:
    - _PgConnectionWrapper for psycopg2 C extension compatibility
    - DictCursor for dual index/key row access
    - _parse_date/_parse_datetime helpers for type-safe date handling
    - _true_val/_false_val helpers for boolean literal compatibility
key_files:
  created: []
  modified:
    - ra-tracker/ra_tracker/database.py
decisions:
  - decision: "Use DATABASE_PUBLIC_URL instead of private networking"
    rationale: "Railway private networking DNS (postgres.railway.internal) fails to resolve; known platform issue"
    alternatives: "Private networking (lower latency, no egress fees) - blocked by DNS resolution"
  - decision: "Create _PgConnectionWrapper class instead of monkey-patching psycopg2 connections"
    rationale: "Source-compiled psycopg2 C extension objects don't allow attribute assignment"
    alternatives: "psycopg2-binary (allows monkey-patching but has libpq/libssl conflicts)"
  - decision: "Use DictCursor instead of RealDictCursor"
    rationale: "DictCursor supports both row['col'] and row[0] access; RealDictCursor only supports dict access"
    alternatives: "Rewrite all fetchone()[0] patterns to use column names (too many changes)"
metrics:
  duration: "~4h"
  completed: "2026-02-15"
  tasks_completed: 3
  commits: 6
---

# Phase 12 Plan 02: Railway Deployment & Data Migration Summary

**One-liner:** Deployed Rave Tracker to Railway with PostgreSQL, migrated 5,032 rows from SQLite, and fixed 5 PostgreSQL compatibility bugs discovered in production.

## Overview

Deployed the application to Railway (web + scheduler services), migrated all data from local SQLite to Railway PostgreSQL, and resolved a chain of PostgreSQL compatibility issues that only manifest with source-compiled psycopg2 and real PostgreSQL (not caught in local SQLite testing).

## Tasks Completed

### Task 1: Create hosting account and configure production environment (checkpoint:human-action)
**Status:** Complete

User actions completed:
- Created Railway account with web service and PostgreSQL database
- Configured environment variables (SECRET_KEY, BASE_URL, BREVO_SMTP_*, TELEGRAM_BOT_TOKEN)
- Web URL: https://rave-tracker-production.up.railway.app
- PostgreSQL provisioned and accessible

**Issue encountered:** Railway's reference variable `${{prolific-dedication.DATABASE_URL}}` showed empty. Resolved by manually setting DATABASE_URL to the public PostgreSQL URL.

**Issue encountered:** Railway private networking DNS (`postgres.railway.internal`) fails to resolve. Switched to DATABASE_PUBLIC_URL (public endpoint).

### Task 2: Run data migration (auto)
**Status:** Complete

Migration results (via `scripts/migrate_sqlite_to_pg.py`):
- users: 10 rows
- rules: 39 rows
- events: 191 rows
- event_artists: 4,225 rows
- event_promoters: 221 rows
- event_rules: 252 rows
- notifications: 19 rows
- sessions: 6 rows
- telegram_link_codes: 1 row
- audit_logs: 68 rows
- **Total: 5,032 rows across 10 tables**
- All SERIAL sequences reset correctly
- Row count verification passed for all tables

### Task 3: Verify production functionality (checkpoint:human-verify)
**Status:** Complete

Verification results:
- Health endpoint: 200 with database connected
- Login: Works with existing credentials
- Dashboard: Loads with migrated events
- Rules page: Loads correctly (HTTP 200)
- Settings page: Loads correctly (HTTP 200)
- Auto-deploy: Git push triggers Railway rebuild

## Deviations from Plan

### Critical: Plan referenced Render, deployed on Railway
- **Issue:** Plan 12-02 was pre-written referencing Render, but 12-01 selected Railway
- **Resolution:** Adapted all instructions to Railway equivalents at execution time
- **Impact:** Service names, URLs, and configuration steps all differed

### Auto-fixed Issues (5 production bugs)

**1. psycopg2 C extension doesn't support monkey-patching**
- **Commit:** `d4acd24`
- **Issue:** `conn.execute = ...` fails on source-compiled psycopg2 C extension connections
- **Fix:** Created `_PgConnectionWrapper` class that wraps raw connection and provides `execute()`/`executemany()` methods with DictCursor

**2. _PgConnectionWrapper missing cursor() method**
- **Commit:** `191a6ec`
- **Issue:** `init_schema()` calls `conn.cursor()` directly, wrapper didn't expose it
- **Fix:** Added `cursor()` method to wrapper class

**3. RealDictCursor doesn't support index access**
- **Commit:** `e0fcbc1`
- **Issue:** `fetchone()[0]` pattern fails with RealDictCursor (OrderedDict, no integer indexing)
- **Fix:** Switched all cursor factories to `DictCursor` (supports both `row["col"]` and `row[0]`)

**4. 42 SQL queries missing f-string prefix**
- **Commit:** `39a4aaa`
- **Issue:** Strings containing `{self.ph}` lacked `f` prefix, sending literal `{self.ph}` to PostgreSQL
- **Fix:** Added `f` prefix to all 42 affected query strings

**5. Raw fromisoformat() calls on native date/datetime objects**
- **Commit:** `5e8403e`
- **Issue:** PostgreSQL returns native `datetime.date`/`datetime.datetime` objects; `date.fromisoformat()` expects strings
- **Fix:** Replaced all raw `fromisoformat()` calls with `_parse_date()`/`_parse_datetime()` helpers that handle both types

**6. Boolean literal incompatibility**
- **Commit:** `a9f9c0e`
- **Issue:** `is_active = 1` fails on PostgreSQL BOOLEAN columns (expects TRUE/FALSE)
- **Fix:** Replaced hardcoded `= 1` with `= {self._true_val}` helper

## Key Decisions

1. **Public DB URL over private networking:** Railway private DNS unreliable; accepted egress fee trade-off
2. **Wrapper class over monkey-patching:** C extension limitation requires wrapping, not patching
3. **DictCursor over RealDictCursor:** Backward-compatible with both access patterns

## Technical Notes

**PostgreSQL compatibility gap:**
The dual-mode database layer (Phase 11) was tested against SQLite only. Production PostgreSQL exposed 6 compatibility issues across 3 categories:
- **Driver differences:** psycopg2 C extension behavior vs sqlite3 module
- **Type system:** Native date objects vs ISO strings, BOOLEAN vs INTEGER
- **String interpolation:** f-string requirement for `{self.ph}` placeholder resolution

These issues were invisible in local development because SQLite is more permissive.

**Debug artifacts cleaned:**
- Removed test user `debugtest@test.com` (id 11) created during production debugging

## Verification

**Plan success criteria:**
- Application accessible at Railway URL and responds to HTTP requests
- Web workers serve dashboard and all routes correctly
- Scheduler process running (visible in Railway logs)
- PostgreSQL database provisioned with data migrated from SQLite
- Git push to main triggers automatic redeployment
- /health endpoint returns 200 with database: connected

## Self-Check: PASSED

```
Health: 200 (database connected)
Login: Working (audit logs show auth.login_success)
Dashboard: 200 (events displayed)
Rules: 200
Settings: 200
Migration: 5,032 rows verified across 10 tables
Auto-deploy: Confirmed (6 commits deployed via git push)
```
