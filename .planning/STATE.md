---
gsd_state_version: 1.0
milestone: v3.4
milestone_name: Onboarding & Welcome
status: executing
last_updated: "2026-08-22T21:20:00.000Z"
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 7
  completed_plans: 2
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** v3.4 Onboarding & Welcome, Phases 19 and 20 complete, Phase 21 next

## Current Position

Phase: 21 of 23 (Welcome Template) - NOT STARTED
Plan: 20-01 COMPLETE. Both tasks done and verified twice over, 26 pytest tests locally and 8/8 checkpoint steps against the deployed app.
Status: Phase 20 closed. Phase 21 (Welcome Template) is next, but consider inserting a phase for the production email failure first, since new users cannot currently register.
Last activity: 2026-08-22 – added the project's first automated test suite; diagnosed production email delivery

Progress: [##░░░░░░░░] 2/7 plans (v3.4)

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
- [2026-08-22]: Added the project's first test suite (ra-tracker/tests/). conftest.py pre-seeds os.environ before importing any app module, because create_app() calls load_dotenv() at import time and dotenv will not overwrite variables already set. That ordering is what makes it structurally impossible for a test run to reach production Postgres or send real mail. Tests never enter the app lifespan, so the scheduler and Telegram bot stay dormant.
- [2026-08-22]: Test-only dependencies live in requirements-dev.txt, not requirements.txt, so pytest and Playwright are never installed in production. Note .gitignore has a blanket *.txt rule; new .txt files need an explicit negation or they are silently uncommittable.
- [2026-08-09 health check]: requirements.txt had open-ended `>=` pins; fresh installs pulled starlette 1.x which removed the old TemplateResponse(name, context) signature, breaking every template-rendering page (500). Fixed by capping fastapi<0.116 / starlette<1.0 / python-telegram-bot<21 / apscheduler<4. Proper fix (migrate 44 TemplateResponse call sites to the new request-first signature, then unpin) deferred — candidate for a future phase or todo.

### Pending Todos

- Migrate 44 TemplateResponse call sites (routes.py, admin.py, app.py) to starlette's request-first signature, then relax the fastapi/starlette version caps. The new test suite surfaces these as 19 deprecation warnings on every run.
- Fix silent email-send failures: routes.py:850 discards the boolean returned by send_verification_email and logs auth.verification_sent regardless, so a failed send is invisible in both the UI and the audit log. The /verify-email/resend response claims success unconditionally.
- Verify Telegram delivery still works after the 5-month gap (bot token may have expired). Email is confirmed broken in production, see Blockers.
- Extend the test suite beyond the wizard: auth, CSRF, and the settings routes have no coverage. .planning/codebase/TESTING.md is now stale, it still states no test framework exists.

### Blockers/Concerns

- RESOLVED 2026-08-22: Railway PostgreSQL is reachable again, /health reports {"status":"healthy","database":"connected"}.
- PRODUCTION: verification emails are not delivered, so no new user can complete registration. Diagnosis on 2026-08-22 ruled out everything local: Brevo SMTP AUTH succeeds with the .env credentials, Brevo accepts MAIL FROM <ravetracker@whotrustswho.com> and RCPT TO the test address (250 for both, no message sent), and sabinwords.com has valid MX records. The failure is therefore prod-side, most likely Railway blocking outbound SMTP on port 587, or a stale BREVO_SMTP_PASSWORD in the Railway environment. Note config.py:67 already carries a use_api flag documented as "True = Brevo HTTP API (bypasses SMTP port blocks)", and RAILWAY.md documents only the SMTP variables, never EMAIL_USE_API or BREVO_API_KEY. Candidate fix: set EMAIL_USE_API=true and BREVO_API_KEY in Railway.
- Phase 21 dependency: Ravemonger image asset (WebP + PNG) is pending from user. Template can be built with placeholder img first.
- RESOLVED 2026-08-22: base.html has NO {% block nav %}. Its only blocks are title (line 6), content (line 321) and scripts (line 377). Hiding the nav during the wizard therefore needs a new override point added to base.html, or a separate wizard layout. Decide before Phase 21 template work.

## Session Continuity

Last session: 2026-08-22 (previous: 2026-08-09)
Stopped at: Plan 20-01 Task 1 done. Task 2's criteria are covered by automated tests; the deployed-app run is pending test-account verification.
Resume file: None
Next: Phase 21 (Welcome Template), or an inserted phase to fix production email delivery first. Before Phase 21 template work, decide how to hide the nav during the wizard, base.html has no {% block nav %}, and obtain the Ravemonger image asset.
