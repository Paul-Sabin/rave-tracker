# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-10)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** Phase 11 - PostgreSQL Migration & Production Server

## Current Position

Phase: 11 of 14 (PostgreSQL Migration & Production Server)
Plan: 3 of 3 in current phase
Status: Phase complete
Last activity: 2026-02-14 - Completed 11-03 Data Migration Tools & Environment Documentation

Progress: [█████░░░░░] 71% (30/42 total plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 30 (phases 1-11)
- Average duration (v3.0): 8h 4m (3 plans)
- Total execution time (v3.0): 24h 12m

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

**Recent Trend:**
v3.0 milestone starting - velocity tracking begins with Phase 10

*Velocity tracking starts with v3.0 milestone*
| Phase 10 P01 | 24h | 3 tasks | 4 files |
| Phase 11 P01 | 8m | 2 tasks | 3 files |
| Phase 11 P03 | 4m | 2 tasks | 3 files |

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

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 10 (Environment & Secrets):**
- RESOLVED: All secrets externalized to environment variables with startup validation
- RESOLVED: All exposed secrets rotated to new values (bot token, SMTP password, SECRET_KEY)

**Phase 11 (PostgreSQL Migration):**
- RESOLVED: All 93 SQL queries converted to dual-mode syntax (? for SQLite, %s for PostgreSQL)
- RESOLVED: Connection pooling configured for multi-worker deployment
- All 15 Python modules using database.py need query verification against PostgreSQL
- APScheduler must be separated from web workers to prevent 4x duplicate jobs

**Phase 12 (Hosting):**
- Hosting provider selection needed (Railway vs Render vs Fly.io)
- Cloud IP blocking severity unknown (ra.co's rate limiting policies for data center IPs)

## Session Continuity

Last session: 2026-02-14
Stopped at: Completed 11-03-PLAN.md (Data Migration Tools & Environment Documentation)
Resume file: None
Next: Phase 11 complete - proceed to Phase 12 (Hosting & Deployment)
