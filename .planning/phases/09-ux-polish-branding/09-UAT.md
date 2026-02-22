---
status: diagnosed
phase: 09-ux-polish-branding
source: 09-01-SUMMARY.md, 09-02-SUMMARY.md
started: 2026-02-10T12:00:00Z
updated: 2026-02-10T12:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Navigation shows Rave Tracker branding
expected: The navigation bar displays "Rave Tracker" as the app name/logo. Page titles in the browser tab also say "Rave Tracker".
result: pass

### 2. Dashboard toggle labels
expected: The dashboard filter toggles show "Global events" and "Local only" (not "All Areas" or "{region} only").
result: pass

### 3. Legacy welcome banner removed
expected: The dashboard does NOT show any banner about migrated rules or notifications from a previous setup. The dashboard loads cleanly with just events and filters.
result: pass

### 4. Region prompt on rules page (no local area)
expected: If you have no local area configured, the rules page shows a yellow prompt card suggesting you set your region (mentions Berlin as suggestion) with a link to settings. You can scroll past it to create rules without setting a region.
result: issue
reported: "No prompt card appears when I register as a new user and go to the rule page and set my first new rule."
severity: major

### 5. RA references preserved
expected: Event listings still show "View on RA" links and "RA Pick" badges where applicable. These are NOT rebranded to "Rave Tracker".
result: pass

### 6. Telegram bot says Rave Tracker
expected: Telegram bot messages (link instructions, welcome, errors) reference "Rave Tracker" instead of "RA Tracker".
result: pass

## Summary

total: 6
passed: 5
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Rules page shows yellow region prompt card when no local area configured"
  status: failed
  reason: "User reported: No prompt card appears when I register as a new user and go to the rule page and set my first new rule."
  severity: major
  test: 4
  root_cause: "has_local_area reads from global config.yaml (which has Berlin hardcoded) instead of per-user database field. All users see has_local_area=True regardless of their own settings."
  artifacts:
    - path: "ra-tracker/ra_tracker/web/routes.py"
      issue: "Lines 126-127 read local_area from global config, not user object"
    - path: "ra-tracker/config.yaml"
      issue: "Lines 27-29 hardcode Berlin for all users"
    - path: "ra-tracker/ra_tracker/database.py"
      issue: "User table/model lacks local_area_id and local_area_name fields"
  missing:
    - "Per-user local_area_id and local_area_name columns in users table"
    - "Routes should read local_area from user object, not global config"
    - "Settings save should write to user record, not config.yaml"
  debug_session: ".planning/debug/region-prompt-missing.md"
