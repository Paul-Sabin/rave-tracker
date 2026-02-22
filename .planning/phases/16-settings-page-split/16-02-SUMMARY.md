---
phase: 16-settings-page-split
plan: 02
subsystem: ui
tags: [fastapi, jinja2, admin, config, telegram, scheduler]

requires:
  - phase: 16-01-settings-page-split
    provides: /settings page stripped to personal-only content with admin link

provides:
  - GET /admin/settings — admin-only system configuration page (Telegram, scheduler, notification mode)
  - POST /admin/settings/save — persists config via config.save()
  - POST /admin/settings/test-telegram — AJAX Telegram test endpoint
  - SchedulerConfig.fetch_times, notification_mode, digest_time fields in config.py
  - admin/settings.html template (151 lines) with all required system config sections

affects:
  - 17-notification-dispatch-modes
  - 18-endpoint-hardening

tech-stack:
  added: []
  patterns:
    - "Admin settings page uses same GET/POST pattern as other admin routes with require_admin dependency"
    - "Config fields loaded with safe field-by-field assignment (sched_data.get()) to avoid TypeError on old configs"
    - "Bot token masked for display: first 5 + stars + last 5; unchanged if submitted form contains asterisks"
    - "Fetch times stored as list of HH:MM strings; comma-separated in UI, validated by regex on save"

key-files:
  created:
    - ra-tracker/ra_tracker/web/templates/admin/settings.html
  modified:
    - ra-tracker/ra_tracker/config.py
    - ra-tracker/ra_tracker/web/admin.py
    - ra-tracker/ra_tracker/web/templates/admin/scraper_status.html
    - ra-tracker/ra_tracker/web/templates/admin/audit_log.html
    - ra-tracker/ra_tracker/web/templates/admin/rules.html
    - ra-tracker/ra_tracker/web/templates/admin/users.html

key-decisions:
  - "SchedulerConfig load() replaced **kwargs unpacking with safe field-by-field get() to prevent TypeError on old config.yaml files missing new keys"
  - "Notification mode radio buttons with JS toggle for digest time field — only shown when daily_digest selected"
  - "Bot token update guarded: only updates if submitted value contains no asterisks (i.e. user typed new value)"
  - "fetch_times_str comma-separated input with server-side regex validation; malformed entries silently discarded"
  - "Test Admin Telegram is AJAX (not form POST) so page does not reload"
  - "flex-wrap added to all admin nav divs to prevent horizontal overflow on smaller screens"

patterns-established:
  - "Admin nav: Rules | Users | Audit Log | Scraper | Settings (consistent order, active page gets btn-primary)"

requirements-completed: [SETT-04, SETT-05, SETT-06, SETT-07, SETT-08, SETT-09, SETT-10, SETT-11]

duration: 2min
completed: 2026-02-22
---

# Phase 16 Plan 02: Admin Settings Page Summary

**Admin-only /admin/settings page with Telegram config, fetch schedule times, notification mode toggle, and masked bot token; SchedulerConfig extended with fetch_times/notification_mode/digest_time and backward-compatible load()**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T20:21:47Z
- **Completed:** 2026-02-22T20:24:31Z
- **Tasks:** 2/2 auto tasks complete (Task 3 is human-verify checkpoint — awaiting verification)
- **Files modified:** 7

## Accomplishments

- Extended SchedulerConfig with fetch_times (list), notification_mode, and digest_time fields; Config.load() now uses safe field-by-field assignment preventing TypeError on old config.yaml files
- Created /admin/settings page with all SETT-04 through SETT-11 requirements: masked bot token, admin chat ID, fetch times (HH:MM list), event horizon, notification mode radio (upon_fetch/daily_digest), conditional digest time, read-only DB info, and Test Admin Telegram AJAX button
- Added Settings nav link to all four existing admin templates (rules, users, audit_log, scraper_status) with flex-wrap for responsive layout

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend config.py with fetch_times, notification_mode, digest_time** - `280d9e0` (feat)
2. **Task 2: Add /admin/settings routes and create admin/settings.html template** - `b223c06` (feat)

## Files Created/Modified

- `ra-tracker/ra_tracker/config.py` - SchedulerConfig extended; load() uses safe get() for backward compat; save() writes new fields
- `ra-tracker/ra_tracker/web/admin.py` - Three new routes: GET /admin/settings, POST /admin/settings/save, POST /admin/settings/test-telegram
- `ra-tracker/ra_tracker/web/templates/admin/settings.html` - New 151-line admin settings template (created)
- `ra-tracker/ra_tracker/web/templates/admin/scraper_status.html` - Settings nav link added
- `ra-tracker/ra_tracker/web/templates/admin/audit_log.html` - Settings nav link added
- `ra-tracker/ra_tracker/web/templates/admin/rules.html` - Settings nav link added
- `ra-tracker/ra_tracker/web/templates/admin/users.html` - Settings nav link added

## Decisions Made

- Used field-by-field `sched_data.get()` in Config.load() rather than `SchedulerConfig(**data["scheduler"])` to ensure old config.yaml files without the new keys do not raise TypeError
- Bot token update guard: if submitted value contains `*`, it's the masked display value — skip update to avoid overwriting real token with masked string
- Fetch times parsed from comma-separated string with `re.match(r"^\d{2}:\d{2}$", t)` — malformed entries silently discarded rather than error
- notification_mode validated against allowlist `("upon_fetch", "daily_digest")` before saving
- Test Admin Telegram implemented as AJAX POST returning JSON, not a form submit, to keep the page state intact

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- Phase 17 (Notification Dispatch Modes): notification_mode and digest_time config fields are now present; Phase 17 can read them for dispatch logic
- Phase 17 will need DB schema changes (queue state on notifications) before digest mode can actually queue events
- Phase 18 (Endpoint Hardening): /admin/settings routes already use require_admin dependency; Phase 18 will audit other endpoints

---
*Phase: 16-settings-page-split*
*Completed: 2026-02-22*
