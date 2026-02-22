---
phase: 15-tracking-page-overhaul
plan: 01
subsystem: web-ui
tags: [ux, routing, local-area, berlin-default, rename, tracking-page]

# Dependency graph
requires:
  - phase: 09-ux-polish-branding
    provides: Per-user local_area_id/local_area_name stored in database; db.update_user_local_area() exists
  - phase: 14-observability-monitoring
    provides: Stable production app to improve UX on

provides:
  - Berlin set as default local area for all new user signups
  - Persistent area widget on /tracking page; no warning card needed
  - POST /api/user/local-area endpoint for inline area saves
  - /rules → /tracking rename with 301 redirect for old bookmarks

affects:
  - Any future UX work on the tracking/rules page
  - New-user onboarding (Berlin default means dashboard is non-empty from first login)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Area widget pattern: compact single-row display + inline search panel toggle (no page reload)
    - Auto-save pattern: result click → POST JSON → update DOM (reuse for other inline-save widgets)

key-files:
  modified:
    - ra-tracker/ra_tracker/database.py
    - ra-tracker/ra_tracker/web/routes.py
    - ra-tracker/ra_tracker/web/templates/rules.html
    - ra-tracker/ra_tracker/web/templates/base.html
    - ra-tracker/ra_tracker/web/templates/dashboard.html

key-decisions:
  - "Berlin area ID = 34 (confirmed via RAClient.search_areas('berlin') at implementation time)"
  - "/api/rules/add JSON endpoint kept as-is (not renamed) — only form-based routes renamed to /tracking/*"
  - "No migration needed — existing null-area users handled gracefully by widget showing 'No area set'"
  - "301 redirect /rules → /tracking for permanent bookmark/SEO safety"

# Metrics
duration: 1 commit
completed: 2026-02-22
---

# Phase 15 Plan 01: Tracking Page Overhaul Summary

**Berlin set as default area for new signups; yellow warning card replaced by persistent area widget with inline search and auto-save; /rules page renamed to /tracking with 301 redirect preserved.**

## Performance

- **Completed:** 2026-02-22
- **Files modified:** 5
- **Commit:** `ae4d07f`

## Accomplishments

- New users now have `local_area_id=34` (Berlin) and `local_area_name="Berlin"` set at registration — dashboard is non-empty from first login
- Compact area widget replaces the yellow "Set your local region" warning card at the top of the tracking page; always visible, non-alarming
- Widget shows current area name; "Change" reveals inline search using existing `/api/search/areas` endpoint; selecting a result auto-saves via `POST /api/user/local-area` and updates the display without page reload
- New `POST /api/user/local-area` endpoint added to routes.py; delegates to existing `db.update_user_local_area()`
- All `/rules` form routes renamed to `/tracking` (add, toggle, notify-mode, dashboard-mode, delete)
- `GET /rules` returns 301 → `/tracking` (preserves old bookmarks)
- Nav links in base.html updated to `/tracking` with `startswith('/tracking')` active check (covers sub-paths)
- Dashboard "Add Rules" button renamed to "Add Tracking" and points to `/tracking`
- Page title and `<h1>` updated: "Tracking - Rave Tracker" / "Tracking"

## Files Modified

- `ra-tracker/ra_tracker/database.py` — `create_user()`: both PostgreSQL and SQLite INSERT statements now include `local_area_id=34, local_area_name="Berlin"`
- `ra-tracker/ra_tracker/web/routes.py` — Added `POST /api/user/local-area`; renamed all `/rules/*` routes to `/tracking/*`; added `/rules` → `/tracking` 301 redirect
- `ra-tracker/ra_tracker/web/templates/rules.html` — Removed warning card; added area widget HTML/CSS/JS; updated title, h1, all form actions
- `ra-tracker/ra_tracker/web/templates/base.html` — Desktop and mobile nav: href + text + active-path condition
- `ra-tracker/ra_tracker/web/templates/dashboard.html` — "Add Rules" → "Add Tracking" link

## Deviations from Plan

None.

## Verification

1. ✅ New user registration sets `local_area_id=34`, `local_area_name="Berlin"` in DB
2. ✅ `/tracking` shows area widget with area name; no yellow warning card
3. ✅ "Change" reveals search; selecting area auto-saves and updates widget without reload
4. ✅ `/rules` redirects 301 → `/tracking`
5. ✅ Nav "Tracking" link active on `/tracking` page
6. ✅ Add/delete/toggle rules work (form actions point to `/tracking/…`)
7. ✅ Dashboard "Add Tracking" navigates to `/tracking`

---
*Phase: 15-tracking-page-overhaul*
*Completed: 2026-02-22*
