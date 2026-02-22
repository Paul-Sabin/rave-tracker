---
phase: 09-ux-polish-branding
plan: 02
subsystem: ui
tags:
  - ui
  - user-experience
  - region-selection
  - dashboard
dependency_graph:
  requires:
    - phase: 09-01
      provides: Rave Tracker brand identity
  provides:
    - Clear dashboard toggle labels
    - Region selection guidance for new users
  affects:
    - Dashboard filtering UX
    - Rules page onboarding flow
tech_stack:
  added: []
  patterns:
    - Progressive disclosure (region prompt only when needed)
    - Non-blocking guidance (users can skip region setup)
key_files:
  created: []
  modified:
    - ra-tracker/ra_tracker/web/templates/dashboard.html
    - ra-tracker/ra_tracker/web/templates/rules.html
    - ra-tracker/ra_tracker/web/routes.py
key_decisions:
  - Simple region prompt with Berlin suggestion (no auto-detection)
  - Non-blocking UX (users can create rules without region)
  - Removed legacy welcome banner (no longer relevant after v2 migration)
patterns_established:
  - "Clearer toggle labels: 'Global events' / 'Local only' instead of 'All Areas' / '{region} only'"
  - "Guidance prompts use yellow border (#ffc107) for attention without alarm"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  files_modified: 3
  commits: 2
  completed_date: 2026-02-09
---

# Phase 09 Plan 02: Dashboard UX Improvements and Region Guidance Summary

**One-liner:** Clearer dashboard toggle labels ("Global events" / "Local only"), removed legacy migration banner, and added region selection prompt on rules page with Berlin suggestion.

## What Was Built

Improved dashboard and rules page UX with clearer labeling and helpful guidance:

**Dashboard improvements (Task 1):**
- Updated filter toggle labels for clarity
  - "All Areas" → "Global events"
  - "{region} only" → "Local only"
- Removed legacy welcome banner
  - Deleted entire "Legacy Data Welcome Message" block (lines 20-37)
  - This banner was a one-time migration message from v1.0→v2.0 that is no longer relevant
- Filter functionality unchanged (only visible labels modified)

**Rules page guidance (Task 2):**
- Added region selection prompt for users without local area configured
- Yellow warning-style card (non-blocking, can scroll past)
- Suggests Berlin as default region
- Links to /settings where Local Area search already exists
- Added `has_local_area` and `local_area_name` to rules page template context
- Prompt only shows when `has_local_area` is False

## Performance

- **Duration:** 3 minutes
- **Started:** 2026-02-09T11:44:04Z
- **Completed:** 2026-02-09T11:47:10Z
- **Tasks:** 2/2 (100%)
- **Files modified:** 3

## Task Commits

1. **Task 1: Update dashboard toggle labels and remove legacy banner** - `b2d068d` (feat)
   - Changed toggle button text
   - Removed legacy data welcome banner
   - Verified with grep commands

2. **Task 2: Add region selection prompt to rules page** - `f5f2a61` (feat)
   - Updated routes.py to pass region config to template
   - Added yellow prompt card to rules.html
   - Verified imports work correctly

## Files Modified

**Templates (2 files):**
- `ra-tracker/ra_tracker/web/templates/dashboard.html` - Toggle labels updated, banner removed
- `ra-tracker/ra_tracker/web/templates/rules.html` - Region prompt added

**Routes (1 file):**
- `ra-tracker/ra_tracker/web/routes.py` - Added has_local_area and local_area_name to rules page context

## Decisions Made

**1. Simple region prompt without auto-detection**
- **Context:** Could auto-detect region from IP or browser, but adds complexity
- **Decision:** Simple prompt suggesting Berlin, links to existing settings page
- **Rationale:** Settings page already has full RA API integration for region search. This just guides users there.
- **Impact:** Cleaner implementation, no new API calls, leverages existing functionality

**2. Non-blocking UX**
- **Context:** Users without region can still create rules and use the app
- **Decision:** Show prompt but allow scrolling past to create rules
- **Rationale:** Region filtering is optional feature, not required for core functionality
- **Impact:** Better UX - users aren't blocked from using the app

**3. Remove legacy banner**
- **Context:** Banner showed "X rules and Y notifications from previous setup" after v1→v2 migration
- **Decision:** Remove entirely rather than hide with feature flag
- **Rationale:** v2 shipped weeks ago, migration complete, banner serves no purpose
- **Impact:** Cleaner dashboard, less visual noise

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All verification commands passed:

**Task 1 (Dashboard):**
1. ✅ `grep "Legacy Data Welcome" dashboard.html` → Zero matches
2. ✅ `grep "legacy_data" dashboard.html` → Zero matches
3. ✅ `grep "All Areas" dashboard.html` → Zero matches
4. ✅ `grep "Global events" dashboard.html` → 1 match
5. ✅ `grep "Local only" dashboard.html` → 1 match

**Task 2 (Rules page):**
1. ✅ `grep "has_local_area" routes.py` → 2 matches (dashboard + rules routes)
2. ✅ `grep "Berlin" rules.html` → 1 match
3. ✅ `grep "Set your local region" rules.html` → 1 match
4. ✅ `grep "has_local_area" rules.html` → 1 match
5. ✅ Application imports work without errors

## Issues Encountered

None - straightforward label updates and template additions.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for next plan (09-03 if exists) or phase completion.

**What's ready:**
- Dashboard has clear, intuitive toggle labels
- New users get guided to region setup without being blocked
- Legacy migration noise removed

**No blockers.**

## Self-Check

Verifying all claimed files and commits exist:

**Files verification:**
```bash
ls ra-tracker/ra_tracker/web/templates/dashboard.html  # ✓ EXISTS
ls ra-tracker/ra_tracker/web/templates/rules.html  # ✓ EXISTS
ls ra-tracker/ra_tracker/web/routes.py  # ✓ EXISTS
```

**Commits verification:**
```bash
git log --oneline | grep "b2d068d"  # ✓ FOUND
git log --oneline | grep "f5f2a61"  # ✓ FOUND
```

**Content verification:**
```bash
grep "Global events" ra-tracker/ra_tracker/web/templates/dashboard.html  # ✓ FOUND
grep "Local only" ra-tracker/ra_tracker/web/templates/dashboard.html  # ✓ FOUND
grep "Berlin" ra-tracker/ra_tracker/web/templates/rules.html  # ✓ FOUND
grep "has_local_area" ra-tracker/ra_tracker/web/routes.py  # ✓ FOUND (2 instances)
```

## Self-Check: PASSED

All files exist, all commits found, all content verified.

---

*Summary completed: 2026-02-09*
*Duration: 3 minutes*
*Tasks: 2/2 (100%)*
