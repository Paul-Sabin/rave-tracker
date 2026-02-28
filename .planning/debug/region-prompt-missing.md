---
status: diagnosed
trigger: "The region selection prompt card does not appear on the rules page for a newly registered user who has no local area configured."
created: 2026-02-10T00:00:00Z
updated: 2026-02-10T00:15:00Z
symptoms_prefilled: true
goal: find_root_cause_only
---

## Current Focus

hypothesis: CONFIRMED - Config is global/singleton, not per-user. All users share the same config which has Berlin (ID 34) set by default
test: Verified config.yaml has local_area_id: 34 hardcoded
expecting: This is the root cause - need per-user local area storage
next_action: Document root cause and propose fix

## Symptoms

expected: When a user has no local area configured, the rules page should show a yellow prompt card suggesting they set their region (mentions Berlin) with a link to settings. The prompt should be non-blocking (user can scroll past).
actual: The region selection prompt card does not appear on the rules page for a newly registered user who has no local area configured.
errors: None reported
reproduction: Register new user, navigate to rules page without configuring local area
started: Present in current codebase

## Eliminated

## Evidence

- timestamp: 2026-02-10T00:05:00Z
  checked: ra-tracker/ra_tracker/web/routes.py lines 101-129
  found: rules_page route passes has_local_area to template as bool(config.user.local_area_id) and local_area_name as config.user.local_area_name
  implication: If config.user.local_area_id has any truthy value (including empty string or 0), has_local_area could be incorrectly True

- timestamp: 2026-02-10T00:06:00Z
  checked: ra-tracker/ra_tracker/web/templates/rules.html lines 8-24
  found: Template checks {% if not has_local_area %} to show yellow prompt card with Berlin suggestion and link to /settings
  implication: Template logic is correct - if has_local_area is False, prompt should appear. Problem must be in how has_local_area is computed

- timestamp: 2026-02-10T00:10:00Z
  checked: ra-tracker/ra_tracker/config.py lines 38-41
  found: UserConfig dataclass has local_area_id: Optional[int] = None and local_area_name: str = "" as defaults
  implication: Config itself has correct defaults (None), but config is loaded from YAML and is global

- timestamp: 2026-02-10T00:12:00Z
  checked: ra-tracker/config.yaml lines 27-29
  found: Config file has "user: local_area_id: 34, local_area_name: Berlin" hardcoded
  implication: ROOT CAUSE FOUND - config.yaml is a GLOBAL configuration file shared across all users, not per-user. The developer (who uses Berlin) has their local area hardcoded, so ALL users see has_local_area=True

- timestamp: 2026-02-10T00:15:00Z
  checked: ra-tracker/ra_tracker/database.py lines 91-102 (users table schema) and lines 231-246 (User dataclass)
  found: User table and User dataclass do NOT have local_area_id or local_area_name columns/fields
  implication: Confirms architectural mismatch - local area preferences are stored globally in config instead of per-user in database

## Resolution

root_cause: The application uses a global config.yaml file for user preferences (local_area_id, local_area_name) instead of per-user database storage. The config.yaml file has Berlin (ID 34) hardcoded, which is shared across ALL users. When routes.py computes has_local_area = bool(config.user.local_area_id), it's checking the GLOBAL config (which has 34), not the individual user's preference. Every user sees has_local_area=True regardless of whether they've personally set a region.

Architecture problem: Config is meant for application-level settings (server config, API keys), but user.local_area_id is a USER PREFERENCE that should be stored per-user in the database, not globally in config.yaml.

Required changes:
1. Add local_area_id and local_area_name columns to User table in database
2. Update routes.py to read from user object instead of config
3. Update settings page to save to database instead of config.yaml
4. Remove user.local_area_id from config.yaml (keep only system-wide settings)
5. Migrate existing config value to admin user if needed

fix:
verification:
files_changed: []
