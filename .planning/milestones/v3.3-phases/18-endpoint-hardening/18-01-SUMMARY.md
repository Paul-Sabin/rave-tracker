---
phase: 18-endpoint-hardening
plan: 01
subsystem: auth
tags: [fastapi, admin, authorization, guard, redirect]

requires:
  - phase: 16-settings-page-split
    provides: Split of /settings (personal) and /admin/settings (system) — guard targets established

provides:
  - Server-side admin guards on POST /settings/save and POST /settings/test-telegram
  - Redirect for non-admin GET /admin/settings to /settings
  - Flash message display on /settings for blocked redirects

affects: []

tech-stack:
  added: []
  patterns: [inline is_admin check + logger.warning pattern for admin-only routes]

key-files:
  created: []
  modified:
    - ra-tracker/ra_tracker/web/routes.py
    - ra-tracker/ra_tracker/web/admin.py
    - ra-tracker/ra_tracker/web/templates/settings.html

key-decisions:
  - "GET /admin/settings for non-admin redirects to /settings (not 403) — better UX"
  - "POST /settings/save non-admin redirect uses playful flash: 'The ravemonger will handle system settings.'"
  - "POST /settings/test-telegram non-admin returns JSON 403 (AJAX endpoint — no redirect)"
  - "Blocked attempts logged at WARNING with user_id, endpoint, and UTC timestamp"
  - "GET /admin/settings uses require_auth (not require_admin) so redirect can be applied inline"

patterns-established:
  - "Admin guard pattern: require_auth + inline is_admin check + logger.warning + redirect/403"

requirements-completed:
  - SETT-15
  - SETT-16

duration: ~30min
completed: 2026-02-28
---

# Plan 18-01: Server-side Admin Guards Summary

**Admin endpoint hardening: POST /settings/save and POST /settings/test-telegram reject non-admins server-side; GET /admin/settings redirects non-admins to /settings**

## Performance

- **Duration:** ~30 min
- **Completed:** 2026-02-28
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint)
- **Files modified:** 3

## Accomplishments
- POST /settings/save: non-admin redirected to /settings with flash message (no config saved)
- POST /settings/test-telegram: non-admin receives JSON 403, no Telegram message sent
- GET /admin/settings: non-admin redirected to /settings (clean UX, not raw 403)
- Flash message support added to /settings page
- All blocked attempts logged with user_id + endpoint + UTC timestamp

## Task Commits

1. **Task 1: Harden POST /settings/save and POST /settings/test-telegram** - `b1d28dd` (feat)
2. **Task 2: Redirect non-admin GET /admin/settings** - `60322b1` (feat)
3. **Task 3: Human verify checkpoint** — approved 2026-02-28

## Files Created/Modified
- `ra-tracker/ra_tracker/web/routes.py` — Admin guards on both POST endpoints; message param + flash_message on GET /settings
- `ra-tracker/ra_tracker/web/admin.py` — GET /admin/settings uses require_auth + inline is_admin redirect
- `ra-tracker/ra_tracker/web/templates/settings.html` — Flash message display block added

## Decisions Made
- GET /admin/settings redirects to /settings rather than 403 — avoids exposing that the route exists to non-admins while giving clean UX
- POST /settings/test-telegram stays as JSON 403 since it's an AJAX endpoint (no redirect)
- Flash message phrasing: "The ravemonger will handle system settings." — consistent with project tone

## Deviations from Plan
None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
Phase 18 is the final phase of v3.3. All endpoint hardening complete. v3.3 milestone ready for completion.

---
*Phase: 18-endpoint-hardening*
*Completed: 2026-02-28*
