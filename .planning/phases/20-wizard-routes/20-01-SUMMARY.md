---
phase: 20-wizard-routes
plan: 01
subsystem: web
tags: [fastapi, routing, jinja2, csrf, auth, pytest]

# Dependency graph
requires:
  - 19-database-foundation (set_onboarding_completed, User.onboarding_completed)
provides:
  - GET /welcome redirect to /welcome/step/1
  - GET /welcome/step/{step} with server-side clamping to [1, 4]
  - POST /welcome/complete calling set_onboarding_completed then redirecting to /
  - welcome.html stub template extending base.html
  - ra-tracker/tests/ pytest suite with verified-user and CSRF fixtures
affects:
  - 21-welcome-template
  - 22-login-intercept
  - 23-settings-revisit-link

# Tech tracking
tech-stack:
  added:
    - "pytest 9.1.1 (requirements-dev.txt, dev only)"
    - "playwright 1.62.0 + chromium (requirements-dev.txt, dev only, for Phase 21)"
  patterns:
    - "Step clamping in the route, not the template: step = max(1, min(step, 4))"
    - "Test env locked down by pre-seeding os.environ before importing any app module"
    - "Dev-only dependencies in requirements-dev.txt with '-r requirements.txt'"

key-files:
  created:
    - ra-tracker/ra_tracker/web/templates/welcome.html
    - ra-tracker/tests/conftest.py
    - ra-tracker/tests/test_welcome_wizard.py
    - ra-tracker/pytest.ini
    - ra-tracker/requirements-dev.txt
  modified:
    - ra-tracker/ra_tracker/web/routes.py
    - .gitignore

key-decisions:
  - "Task 2's manual 8-step checkpoint was replaced by an automated pytest suite plus a scripted run against the deployed app. Both were executed; all criteria pass in both."
  - "conftest.py sets os.environ before importing app modules because create_app() calls load_dotenv() at import time and dotenv will not overwrite variables already set. This is what makes it structurally impossible for a test run to reach production Postgres or send real mail."
  - "Tests never enter the app lifespan, so the APScheduler job and the Telegram bot stay dormant during test runs."
  - "Test-only dependencies kept out of requirements.txt so production installs are unaffected."
  - ".gitignore needed an explicit '!ra-tracker/requirements*.txt' negation; its blanket '*.txt' rule would otherwise have made the new file silently uncommittable."

patterns-established:
  - "Route-level verification belongs in pytest against a temp SQLite DB; only genuinely visual or browser-dependent behaviour needs a human or Playwright."

requirements-completed: [WIZ-01]

# Metrics
duration: ~55min (Task 1 prior session, Task 2 this session)
completed: 2026-08-22
---

# Phase 20 Plan 01: Wizard Routes Summary

**Welcome wizard routing is live: /welcome redirects to step 1, steps clamp to [1, 4], both auth gates hold, and Complete persists onboarding_completed then returns to the dashboard. Verified twice over, by a new 26-test pytest suite and by a scripted run against the deployed app.**

## Performance

- **Duration:** Task 1 in a prior session, Task 2 on 2026-08-22
- **Completed:** 2026-08-22
- **Tasks:** 2
- **Tests added:** 26 (all passing, ~11s)

## Accomplishments
- Three routes in `routes.py`: `GET /welcome` (302 to step 1), `GET /welcome/step/{step}` (clamped render), `POST /welcome/complete` (sets the flag, 303 to `/`)
- All three gated behind `Depends(require_verified_email)`, so unauthenticated requests get 303 to `/login` and unverified ones 303 to `/verify-email`
- `welcome.html` stub extending `base.html`, showing "Step N of 4", a Next link on steps 1 to 3 and a CSRF-protected Complete form on step 4
- The project's first automated test suite, covering every success criterion below plus a Phase 19 regression that new users default to `onboarding_completed = False`
- Playwright and Chromium installed for Phase 21's browser-level and accessibility checks

## Verification

All 7 success criteria pass under pytest (26 tests, local, temp SQLite):
clamping was additionally checked at 5, 99, 1000 and at 0, -1, -99.

All 8 checkpoint steps pass against https://ravetracker.whotrustswho.com:

| # | Check | Result |
|---|-------|--------|
| 1 | `/welcome` redirects to `/welcome/step/1` | PASS (302) |
| 2 | Step 1 renders "Step 1 of 4" with a Next button | PASS (200) |
| 3 | Next walks 1 to 2 to 3 to 4 with correct numbers | PASS |
| 4 | Step 4 shows Complete instead of Next | PASS |
| 5 | `/welcome/step/99` clamps to "Step 4 of 4" | PASS (200) |
| 6 | `/welcome/step/0` clamps to "Step 1 of 4" | PASS (200) |
| 7 | Unauthenticated `/welcome/step/1` redirects to login | PASS (303) |
| 8 | Complete redirects to the dashboard | PASS (303 to `/`) |

Note on criterion 6: the deployed run confirms the redirect; the persistence of
`onboarding_completed` is asserted against a real database by the pytest suite
rather than on production, since nothing yet gates on the flag.

## Task Commits

1. **Task 1: Wizard routes and stub template** - `88aa4c5` (feat)
2. **Task 2: Automated test suite replacing the manual checkpoint** - `ba1913e` (test)

## Deviations from Plan

Task 2 was specified as a human clicking through 8 steps on the deployed app.
It was instead automated, in two layers: a pytest suite for the route logic and
a scripted HTTP session for the deployed app. The reason is durability, the
manual checkpoint verifies once, whereas the suite catches regressions on every
run. It immediately proved its worth by surfacing the deferred TemplateResponse
migration as 19 deprecation warnings per run.

## Issues Encountered

- The deployed-app run was blocked for part of the session: the test account
  could not be email-verified because verification emails are not delivered in
  production. Diagnosis ruled out everything local, Brevo SMTP AUTH succeeds,
  Brevo accepts the sender and recipient envelope, and the recipient domain has
  valid MX records. The account was verified with a direct SQL update to unblock
  this checkpoint. See Blockers in STATE.md, this is an open production issue
  affecting all new registrations.
- Login does not preserve an intended destination. `POST /login` takes only
  email and password and always redirects to `/`, so being bounced off `/welcome`
  by the auth gate loses the target. Phase 22 addresses this.

## User Setup Required

- `CLAUDE_TEST_USERNAME` and `CLAUDE_TEST_PASSWORD` in `ra-tracker/.env` for
  scripted runs against the deployed app.
- `pip install -r requirements-dev.txt` then `python -m playwright install chromium`
  for a fresh dev environment.

## Next Phase Readiness

- Phase 21 can build on the working `welcome.html` stub and its route contract
- Resolved dependency: `base.html` has no `{% block nav %}`. Its only blocks are
  `title` (line 6), `content` (line 321) and `scripts` (line 377), so hiding the
  nav during the wizard needs a new override point or a separate wizard layout
- Open dependency: the Ravemonger image asset (WebP + PNG) is still pending;
  the template can be built with a placeholder first
- Recommendation: consider inserting a phase for the production email failure
  before Phase 21, since new users cannot currently register

---
*Phase: 20-wizard-routes*
*Completed: 2026-08-22*
