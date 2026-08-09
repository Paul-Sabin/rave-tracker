---
gsd_state_version: 1.0
milestone: v3.4
milestone_name: Onboarding & Welcome
status: executing
last_updated: "2026-08-09T13:30:00.000Z"
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 7
  completed_plans: 1
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** v3.4 Onboarding & Welcome — Phase 19 complete, Phase 20 next

## Current Position

Phase: 20 of 23 (Wizard Routes) - IN PROGRESS
Plan: 20-01 Task 1 (code) complete and pushed; Task 2 (human-verify checkpoint on deployed app) pending
Status: Blocked on deployment health — checkpoint requires the live app
Last activity: 2026-08-09 — health check after 5-month gap; fixed dependency breakage (see Decisions)

Progress: [#░░░░░░░░░] 1/7 plans (v3.4)

## Performance Metrics

**Velocity:**
- Total plans completed: 47 (phases 1-18)
- Average duration (v3.x): ~15m per plan

**By Phase:**

| Phase | Plans | Milestone |
|-------|-------|-----------|
| 1-14 | 34/34 | v2.0-v3.1 |
| 15. Tracking Page UX | 1/1 | v3.2 |
| 16. Settings Page Split | 2/2 | v3.3 |
| 17. Notification Dispatch Modes | 2/2 | v3.3 |
| 18. Endpoint Hardening | 1/1 | v3.3 |
| Phase 19-database-foundation P01 | 10 | 2 tasks | 1 files |

## Accumulated Context

### Decisions

All decisions logged in PROJECT.md Key Decisions table.

Recent decisions affecting v3.4:
- URL-based step state (no per-step DB persistence) — only onboarding_completed boolean needed
- GDPR: notification toggles must be unchecked for new users regardless of DB default
- Existing-user backfill: UPDATE WHERE local_area_id IS NOT NULL OR telegram_chat_id IS NOT NULL
- Wizard gates on BOTH email_verified AND NOT onboarding_completed
- No new dependencies — vanilla JS + Tailwind v4 CDN + @keyframes handles all wizard UI
- [Phase 19-database-foundation]: Migration 14+14b use two-step pattern (ADD COLUMN then UPDATE backfill) for onboarding_completed column
- [Phase 19-database-foundation]: Backfill: UPDATE WHERE local_area_id IS NOT NULL OR telegram_chat_id IS NOT NULL marks existing configured users as already onboarded
- [2026-08-09 health check]: requirements.txt had open-ended `>=` pins; fresh installs pulled starlette 1.x which removed the old TemplateResponse(name, context) signature, breaking every template-rendering page (500). Fixed by capping fastapi<0.116 / starlette<1.0 / python-telegram-bot<21 / apscheduler<4. Proper fix (migrate 44 TemplateResponse call sites to the new request-first signature, then unpin) deferred — candidate for a future phase or todo.

### Pending Todos

- Migrate 44 TemplateResponse call sites (routes.py, admin.py, app.py) to starlette's request-first signature, then relax the fastapi/starlette version caps.
- Verify Telegram bot and email delivery still work after the 5-month gap (tokens/credentials may have expired).

### Blockers/Concerns

- Railway PostgreSQL unreachable as of 2026-08-09 (/health reports "server closed the connection unexpectedly" for interchange.proxy.rlwy.net:13775). Web service runs but DB-backed pages fail. Needs Railway dashboard: check Postgres service status and that DATABASE_URL matches current credentials. If Postgres was recreated, user data may need restoring from backup.
- Phase 21 dependency: Ravemonger image asset (WebP + PNG) is pending from user. Template can be built with placeholder img first.
- Phase 21 dependency: Confirm base.html has a {% block nav %} override point before step 1 template work.

## Session Continuity

Last session: 2026-08-09 (previous: 2026-03-01)
Stopped at: Plan 20-01 Task 1 done; Task 2 checkpoint pending deployment health
Resume file: None
Next: Restore Railway Postgres, then run 20-01 Task 2 checkpoint (8 verification steps on deployed app)
