---
gsd_state_version: 1.0
milestone: v3.4
milestone_name: Onboarding & Welcome
status: executing
last_updated: "2026-08-23T00:30:00.000Z"
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 11
  completed_plans: 2
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Users never miss events from artists, venues, or promoters they care about
**Current focus:** v3.4 Onboarding & Welcome, Phases 19 and 20 complete, Phase 21 next

## Current Position

Phase: 20.1 (Production Email Delivery, INSERTED) - READY TO EXECUTE
Plan: 20-01 COMPLETE. Both tasks done and verified twice over, 26 pytest tests locally and 8/8 checkpoint steps against the deployed app.
Status: Phase 20.1 planned and verified. 4 plans in 2 waves; the plan checker passed on the first pass with no blockers. Wave 1 (plans 01, 02, 03) is autonomous and parallel-safe, zero file overlap. Wave 2 (plan 04) is a release gate with two human checkpoints, because setting Railway and Brevo dashboard variables cannot be automated.
Last activity: 2026-08-23 – planned Phase 20.1 (research, pattern mapping, planning, verification)

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

### Roadmap Evolution

- Phase 20.1 inserted after Phase 20: Production Email Delivery (URGENT). Verification emails are not delivered in production; because all flows share services/email_sender.py this also breaks password reset, event notifications, and deletion/recovery confirmations. Inserted 2026-08-22.

### Phase 20.1 planning decisions

- Root cause confirmed against Railway's official docs: Railway blocks outbound SMTP (25/465/587/2525) and recommends HTTPS transactional email APIs. The fix is to switch to Brevo's HTTP API via the existing `use_api` path, not to repair SMTP.
- Brevo's SMTP key and API key are different credential types. `email_sender.py` falls back from `api_key` to `password` in two places (lines 92 and 133), which would 401 silently; both are fixed in plan 20.1-01.
- Five call sites discard the boolean returned by the send functions: routes.py 716, 790, 850, 898 (verification) and 1022 (password reset). All five are fixed in plan 20.1-02.
- Password reset keeps its enumeration-safe behaviour: it gains a `password.reset_send_failed` audit event but its user-facing message stays byte-identical across success, send failure, and unknown address. Changing it would confirm an account exists.
- Fixing `is_email_configured()` makes `BREVO_API_KEY` load-bearing: `EMAIL_USE_API=true` with no key disables email silently rather than erroring. This is the intended fail-safe, so the Railway config step is genuinely blocking. Executors are explicitly forbidden from adding a fallback.
- The SMTP path is kept as the documented local-dev fallback, not removed.
- Not planned, open for a later decision: adding an explicit connection timeout to the SMTP path so it fails fast instead of hanging ~127s. Only affects local dev, but the hang is a plausible explanation for why nothing reached Sentry, since gunicorn's 120s worker timeout may have killed the worker before the except block logged.

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
Next: /gsd-execute-phase 20.1. Wave 1's three plans run in parallel and are autonomous. Wave 2 needs you in the Brevo and Railway dashboards to create an API key and set EMAIL_USE_API plus BREVO_API_KEY on both the web and scheduler services.
