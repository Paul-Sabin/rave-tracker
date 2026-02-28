---
phase: 16-settings-page-split
plan: 01
subsystem: ui
tags: [jinja2, fastapi, settings, admin, personal-settings]

# Dependency graph
requires:
  - phase: 15-tracking-page-ux
    provides: Local Area widget moved to /tracking (settings page no longer owns it)
provides:
  - Personal-only /settings page: Notification Preferences, Account Security, Delete Account
  - Conditional admin link card on /settings for admin users
  - Slimmed settings_page GET route (no admin context)
  - Slimmed save_settings POST route (redirects immediately, accepts no admin fields)
affects:
  - 16-02 (admin/settings page will receive the sections removed here)
  - 17-notification-dispatch-modes (Notification Preferences section remains on /settings)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Admin-only UI gated by {% if user.is_admin %} Jinja2 conditional"
    - "Template context carries only what the template needs — no leaking admin data to user views"

key-files:
  created: []
  modified:
    - ra-tracker/ra_tracker/web/routes.py
    - ra-tracker/ra_tracker/web/templates/settings.html

key-decisions:
  - "save_settings POST now redirects immediately with no form processing — all system config moves to /admin/settings in Plan 02"
  - "mask_token() helper removed — no longer needed in user-facing routes"
  - "get_scheduler_status import retained — still used by /api/status endpoint"

patterns-established:
  - "Personal settings page: only user, csrf_token, telegram_configured, email_configured in context"
  - "Admin link on personal settings uses border-color: var(--color-accent) card styling"

requirements-completed: [SETT-01, SETT-02, SETT-03]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 16 Plan 01: Settings Page Split Summary

**Stripped /settings to personal-only content (Notification Preferences, Account Security, Delete Account) and added a conditional admin link card for admin users pointing to /admin/settings**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T12:56:53Z
- **Completed:** 2026-02-22T12:58:53Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- settings_page GET route no longer passes `config`, `masked_token`, or `scheduler_status` to template
- save_settings POST handler stripped to a single redirect — no admin form fields accepted
- delete_account error re-render context cleaned to personal-only variables
- settings.html rewritten: four admin cards removed, conditional System Administration link card added
- All user-facing JS intact (Link Telegram modal, Test Notifications, Delete modal)
- Area search JS and Test Admin Telegram JS removed

## Task Commits

Each task was committed atomically:

1. **Task 1: Slim the /settings route handler in routes.py** - `d36188b` (feat)
2. **Task 2: Rewrite settings.html to personal-only sections with admin link** - `e3c41ac` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `ra-tracker/ra_tracker/web/routes.py` - Removed bot token masking, admin context vars, and all admin form processing from settings handlers
- `ra-tracker/ra_tracker/web/templates/settings.html` - Removed 4 admin cards and ~200 lines; added 10-line conditional admin link card

## Decisions Made
- `save_settings` POST immediately redirects with no processing — the handler will effectively become unused once /admin/settings is created in Plan 02, but keeping it avoids 404 until then.
- `mask_token()` helper function removed since it was only called from `delete_account` error re-render (now cleaned up).
- `get_scheduler_status` import retained — it is still used by the `/api/status` JSON endpoint; only removed from `settings_page` context.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- /settings page is now personal-only and clean
- Plan 16-02 can now create /admin/settings with the system config sections that were removed here
- The "Go to Admin Settings" link on /settings will resolve once 16-02 creates that route

---
*Phase: 16-settings-page-split*
*Completed: 2026-02-22*
