# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-10)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** Phase 14 - Observability & Monitoring (ALL PLANS COMPLETE - v3.1 milestone)

## Current Position

Phase: 14 of 14 (Observability & Monitoring)
Plan: 3 of 3 in current phase (complete)
Status: Phase 14 complete - All observability & monitoring plans done
Last activity: 2026-02-20 - Completed 14-03 (Scraper Failure Alerts via Telegram)

Progress: [██████████] 100% (39/42 total plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 39 (phases 1-13 + 14-01 + 14-02 + 14-03)
- Average duration (v3.0): 4h 18m (9 plans)
- Total execution time (v3.0): 38h 42m

**By Phase:**

| Phase | Plans | Milestone |
|-------|-------|-----------|
| 1. Database Foundation | 2/2 | v2.0 |
| 2. Authentication System | 3/3 | v2.0 |
| 3. Multi-Tenant Access Control | 4/4 | v2.0 |
| 4. User Notification Delivery | 3/3 | v2.0 |
| 5. Audit Foundation & CSRF | 2/2 | v2.1 |
| 6. Email Verification & Login | 3/3 | v2.1 |
| 7. Password Management | 3/3 | v2.1 |
| 8. Account Lifecycle & Admin UI | 3/3 | v2.1 |
| 9. UX Polish & Branding | 3/3 | v2.2 |
| 10. Environment & Secrets Cleanup | 1/1 | v3.0 |
| 11. PostgreSQL Migration & Production Server | 3/3 | v3.0 |
| 12. Hosting & SSL Deployment | 3/3 | v3.0 |
| 13. Scraper Resilience | 3/3 | v3.0 |
| 14. Observability & Monitoring | 3/3 | v3.1 |

**Recent Trend:**
v3.0 milestone starting - velocity tracking begins with Phase 10

*Velocity tracking starts with v3.0 milestone*
| Phase 10 P01 | 24h | 3 tasks | 4 files |
| Phase 11 P01 | 8m | 2 tasks | 3 files |
| Phase 11 P03 | 4m | 2 tasks | 3 files |
| Phase 12 P01 | 4h 3m | 2 tasks | 5 files |
| Phase 12 P02 | ~4h | 3 tasks | 1 file |
| Phase 12 P03 | ~30m | 2 tasks | 0 files |
| Phase 13 P01 | 3m | 2 tasks | 3 files |
| Phase 13 P02 | 3m 42s | 2 tasks | 3 files |
| Phase 13 P03 | 35m | 3 tasks | 7 files |
| Phase 14 P01 | 4m | 2 tasks | 8 files |
| Phase 14 P02 | 5m | 2 tasks | 4 files |
| Phase 14 P03 | 3m | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v2.2: User-facing rebrand only (keep ra-tracker/ra_tracker internally, avoid churn)
- v2.2: Per-user local area in DB (user preferences in database, not global config)
- v3.0: PostgreSQL for production (migrating from SQLite)
- [Phase 10-01]: Use empty strings in config.yaml instead of \ placeholders (YAML doesn't expand variables)
- [Phase 10-01]: Validate only actual secrets (bot token, secret key, SMTP password), not identifiers
- [Phase 11-01]: Use psycopg2 (not psycopg2-binary) to avoid libpq/libssl conflicts
- [Phase 11-01]: Use {self.ph} property for dual-mode SQL placeholder resolution
- [Phase 11-03]: Use Python script instead of pgloader for Windows compatibility and full control over type conversions
- [Phase 11-03]: Embed PG_SCHEMA in migration script for self-contained execution
- [Phase 12-01]: Railway selected as hosting provider (usage-based pricing, Railpack builds)
- [Phase 12-01]: Use Docker builder (not Nixpacks) for explicit psycopg2 control
- [Phase 12-01]: Force-add railway.json and runtime.txt (gitignored by *.json/*.txt rules)
- [Phase 12-02]: Use DATABASE_PUBLIC_URL (private networking DNS unreliable on Railway)
- [Phase 12-02]: _PgConnectionWrapper class for psycopg2 C extension compatibility
- [Phase 12-02]: DictCursor over RealDictCursor (supports both dict and index access)
- [Phase 12-03]: Custom domain ravetracker.whotrustswho.com with auto-SSL via Railway
- [Phase 13-01]: Use fake-useragent library for real browser UA strings (Chrome, Firefox, Safari 100+)
- [Phase 13-01]: Rotate User-Agent every 5-10 requests (random interval) to appear more human
- [Phase 13-01]: 403 raises IPBlockedException immediately (no retry) - distinct from rate limiting
- [Phase 13-01]: Circuit breaker is in-memory singleton (resets on app restart per user decision)
- [Phase 13]: Circuit breaker pre-flight checks prevent fetch cycles when OPEN state
- [Phase 13]: Scraper health logs retained for 30 days with daily cleanup in purge job
- [Phase 13-03]: Silent degradation UX - users see no indication of scraper issues
- [Phase 13-03]: Admin-only fetch control via dedicated /admin/scraper-status page
- [Phase 13-03]: Force fetch bypasses circuit breaker via circuit_breaker.force_close()
- [Phase 13-03]: Run force fetch in background thread to avoid blocking UI
- [Phase 14-01]: python-json-logger v3+ uses pythonjsonlogger.json (not pythonjsonlogger.jsonlogger)
- [Phase 14-01]: CorrelationIdMiddleware added after CSRFMiddleware (FastAPI reverse order = outermost)
- [Phase 14-01]: init_sentry() called before FastAPI app creation for ASGI auto-integration
- [Phase 14-01]: QueueHandler+QueueListener for non-blocking Better Stack log shipping
- [Phase 14-01]: Sentry user bound in get_current_user() auth dep, cleared in HTTP middleware
- [Phase 14-01]: enable_logs=False in sentry_sdk.init() - logs go to Better Stack, not Sentry
- [Phase 14-01]: Graceful degradation when SENTRY_DSN/LOGTAIL_SOURCE_TOKEN not configured
- [Phase 14-02]: Pass circuit_breaker_state as parameter to complete_scraper_fetch() to avoid circular import (database.py importing from api.circuit_breaker)
- [Phase 14-02]: get_last_fetch_time() queries DB as primary source (365-day window), falls back to in-memory for DB outage resilience
- [Phase 14-02]: complete_scraper_fetch() called at ALL exit paths in fetch_and_notify (success, failure, no-rules, circuit-breaker-skipped)
- [Phase 14]: Singleton scraper_alert_state table (id=1 CHECK constraint) ensures exactly one alert state row survives restarts
- [Phase 14]: SKIPPED fetch status (circuit breaker open) counts toward failure threshold for alerting
- [Phase 14]: ScraperAlerter reads all state from DB on every call — no in-memory state, consistent across gunicorn workers

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 10 (Environment & Secrets):**
- RESOLVED: All secrets externalized to environment variables with startup validation
- RESOLVED: All exposed secrets rotated to new values (bot token, SMTP password, SECRET_KEY)

**Phase 11 (PostgreSQL Migration):**
- RESOLVED: All 93 SQL queries converted to dual-mode syntax (? for SQLite, %s for PostgreSQL)
- RESOLVED: Connection pooling configured for multi-worker deployment
- RESOLVED: APScheduler separated from web workers via --scheduler-only mode
- RESOLVED: Migration tooling created (Python script, sequence reset SQL)

**Phase 12 (Hosting):**
- RESOLVED: Railway selected as hosting provider
- RESOLVED: Application deployed and verified (dashboard, login, rules, settings all working)
- RESOLVED: 5,032 rows migrated from SQLite to PostgreSQL (all tables verified)
- RESOLVED: 6 PostgreSQL compatibility bugs fixed (wrapper, cursor, f-strings, dates, booleans)
- Railway requires third-party backup template (no native PostgreSQL backups)
- Cloud IP blocking severity unknown (ra.co's rate limiting policies for data center IPs)

**Phase 13 (Scraper Resilience):**
- RESOLVED: Complete - exponential backoff, UA rotation, circuit breaker, health logging, admin monitoring
- Users experience silent degradation (no fetch errors shown)
- Admins have full visibility and control via /admin/scraper-status

**Phase 14 (Observability):**
- RESOLVED: scraper_fetch_log persists fetch cycles to DB (fixes "Last Successful Fetch: Never" across workers)
- RESOLVED: Telegram admin alerts fire after 3 consecutive failures with silence and recovery notification
- NOTE: scraper_alert_state and scraper_fetch_log tables added to schema; Railway DB will auto-create via init_schema() on next restart

## Session Continuity

Last session: 2026-02-20
Stopped at: Completed Phase 14 Plan 03 (Scraper Failure Alerts via Telegram) — Phase 14 and v3.1 milestone complete
Resume file: None
Next: All phases complete
