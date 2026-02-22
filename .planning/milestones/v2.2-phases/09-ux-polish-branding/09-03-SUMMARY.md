---
phase: 09-ux-polish-branding
plan: 03
subsystem: database, ui
tags: [sqlite, per-user-settings, local-area, region-prompt, gap-closure]

# Dependency graph
requires:
  - phase: 09-02
    provides: "Region prompt card UI on rules page"
provides:
  - "Per-user local area storage in database"
  - "Independent local area preferences per user"
  - "Yellow region prompt shows for users without local area configured"
affects: [future-user-preferences, multi-tenant-settings]

# Tech tracking
tech-stack:
  added: []
  patterns: ["per-user preferences in database instead of global config"]

key-files:
  created: []
  modified:
    - ra-tracker/ra_tracker/database.py
    - ra-tracker/ra_tracker/web/routes.py
    - ra-tracker/ra_tracker/web/templates/settings.html

key-decisions:
  - "Local area preferences stored per-user in database (users.local_area_id/local_area_name columns)"
  - "Scheduler continues using config.yaml for global notification area filter (system-wide default)"
  - "Existing admin user Berlin value intentionally not migrated (user must re-set via settings)"

patterns-established:
  - "User preferences stored in database, not global config"
  - "Config.yaml reserved for application-level settings only"

# Metrics
duration: 3 min
completed: 2026-02-10
---

# Phase 09 Plan 03: Per-User Local Area Storage Summary

**Per-user local area columns added to users table with migrations, routes updated to read from user object, region prompt now appears correctly for unconfigured users**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-10T22:12:48Z
- **Completed:** 2026-02-10T22:16:17Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added local_area_id and local_area_name columns to users table (migrations 11 and 12)
- Updated all 6 User construction sites to include new fields
- Dashboard and rules page now read local area from user object instead of global config
- Settings page saves local area to user database record
- Yellow region prompt card now appears for users without local area configured
- Independent local area settings per user (multi-tenant support)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add per-user local_area columns to database and User model** - `a6ae320` (feat)
2. **Task 2: Update routes and templates to use per-user local area** - `4fa01e6` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified
- `ra-tracker/ra_tracker/database.py` - Added local_area_id/local_area_name fields to User dataclass, migrations 11-12, updated 6 User construction sites, added update_user_local_area method
- `ra-tracker/ra_tracker/web/routes.py` - Dashboard and rules_page read from user object, save_settings writes to database, removed config.user.local_area reads
- `ra-tracker/ra_tracker/web/templates/settings.html` - Display local area from user object instead of config

## Decisions Made
- **Per-user storage:** Local area preferences moved from global config.yaml to per-user database columns. This allows independent local area settings for each user in multi-tenant mode.
- **Scheduler unchanged:** The scheduler's fetch_and_notify() continues using config.user.local_area_id as a system-wide default for notification filtering. This is appropriate for single-instance deployment and can be refactored to per-user in a future phase if needed.
- **No migration of existing value:** The Berlin value in config.yaml was intentionally not migrated to the existing admin user's database record. The admin user will need to re-set their local area via settings (one-time action). The config.yaml value remains as a system-wide default for the scheduler.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all database migrations ran successfully, app started without errors, and per-user local area storage works as expected.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 9 complete. All 3 plans for UX Polish & Branding milestone v2.2 are now complete:
- 09-01: Rebranded to "Rave Tracker"
- 09-02: Dashboard UX improvements and region guidance
- 09-03: Per-user local area storage (gap closure)

System ready for deployment. Users with no local area configured will see the yellow region prompt card on the rules page, guiding them to configure their preferred region in settings.

## Self-Check: PASSED

All files created/modified exist:
- FOUND: ra-tracker/ra_tracker/database.py
- FOUND: ra-tracker/ra_tracker/web/routes.py
- FOUND: ra-tracker/ra_tracker/web/templates/settings.html

All commits exist:
- FOUND: a6ae320 (Task 1)
- FOUND: 4fa01e6 (Task 2)

---
*Phase: 09-ux-polish-branding*
*Completed: 2026-02-10*
