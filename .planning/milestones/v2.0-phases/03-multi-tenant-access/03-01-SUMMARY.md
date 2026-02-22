---
phase: 03-multi-tenant-access
plan: 01
subsystem: database
tags: [multi-tenant, user-scoping, sqlite, data-isolation]

dependency-graph:
  requires: [01-01, 02-01]
  provides: [user-scoped-database-methods]
  affects: [03-02, 03-03]

tech-stack:
  added: []
  patterns: [user-scoped-queries, ownership-verification, sql-joins]

key-files:
  created: []
  modified:
    - ra-tracker/ra_tracker/database.py

decisions:
  - id: 03-01-01
    description: "Optional user_id parameters maintain backward compatibility"
    rationale: "Scheduler needs to query all rules without user context; None = all users"
  - id: 03-01-02
    description: "Events remain shared, scoping via event_rules JOIN"
    rationale: "Multiple users can see same event if their rules match; matched_rules filtered per-user"
  - id: 03-01-03
    description: "_row_to_rule helper method to DRY up Rule construction"
    rationale: "Rule construction appeared in 6+ methods; centralizes user_id inclusion"

metrics:
  duration: 4 minutes
  completed: 2026-01-28
---

# Phase 03 Plan 01: User-Scoped Database Methods Summary

**One-liner:** User-scoped database queries with optional user_id filtering, ownership verification via get_rule_for_user, and per-user stats/events methods.

## What Was Built

Extended the database.py module with user-scoping capabilities for multi-tenant data isolation:

### Task 1: User-Scoped Rule Methods
- Added `_row_to_rule(row)` helper to DRY up Rule construction with user_id
- Updated `get_all_rules(user_id: Optional[int] = None)` - filters by user or returns all
- Updated `get_active_rules(user_id: Optional[int] = None)` - same pattern
- Updated `rule_exists(rule_type, target_id, user_id: Optional[int] = None)` - per-user duplicate check
- Added `get_rule_for_user(rule_id, user_id)` - ownership verification before mutations
- Updated `get_rule()` to include user_id via _row_to_rule

### Task 2: User-Scoped Events and Stats
- Added `get_upcoming_events_for_user(user_id)`:
  - Uses JOIN through event_rules to find events matching user's rules
  - matched_rules filtered to only user's rules
  - Artists/promoters remain shared (not user-scoped)
- Added `get_user_stats(user_id)`:
  - active_rules: count of user's active rules
  - upcoming_events: count of events matching user's rules
  - notifications_sent: count for user's rules
- Added `count_legacy_data(user_id)`:
  - Returns rules/notifications that existed before user's account
  - For dashboard welcome message
- Updated `add_notification` to accept optional user_id parameter

## Key Patterns Established

### User Scoping with Optional Parameters
```python
def get_all_rules(self, user_id: Optional[int] = None) -> List[Rule]:
    if user_id is not None:
        cursor = conn.execute("... WHERE user_id = ?", (user_id,))
    else:
        cursor = conn.execute("...")  # All rules for scheduler/admin
```

### Ownership Verification
```python
def get_rule_for_user(self, rule_id: int, user_id: int) -> Optional[Rule]:
    cursor = conn.execute(
        "SELECT * FROM rules WHERE id = ? AND user_id = ?",
        (rule_id, user_id)
    )
    # Returns None if rule doesn't exist OR belongs to different user
```

### Events Scoped via Rules
```python
# Events linked to user's rules via JOIN
SELECT DISTINCT e.* FROM events e
INNER JOIN event_rules er ON e.id = er.event_id
INNER JOIN rules r ON er.rule_id = r.id
WHERE r.user_id = ? AND e.date >= ?
```

## Integration Points

### For Route Handlers (03-02)
- `get_all_rules(user.id)` - user's rules page
- `get_rule_for_user(rule_id, user.id)` - before edit/delete
- `rule_exists(type, id, user.id)` - per-user duplicate check
- `get_upcoming_events_for_user(user.id)` - dashboard events
- `get_user_stats(user.id)` - dashboard statistics

### For Scheduler (unchanged)
- `get_active_rules()` without user_id - fetches all users' rules
- `get_all_rules()` without user_id - admin view

## Commits

| Hash | Message |
|------|---------|
| 6b56038 | feat(03-01): add user_id parameter to rule methods |
| b7345d7 | feat(03-01): add user-scoped event and stats methods |

## Deviations from Plan

None - plan executed exactly as written.

## Testing Performed

1. Python syntax check: Module loads successfully
2. Unit tests verified:
   - get_all_rules with user_id returns only user's rules
   - rule_exists with user_id allows different users to track same artist
   - get_rule_for_user returns None for wrong user (ownership verification)
   - get_active_rules with user_id filters correctly
   - get_upcoming_events_for_user returns events via event_rules JOIN
   - get_user_stats returns per-user counts
   - add_notification stores user_id

## Next Plan Readiness

03-02-PLAN.md (Route Handler Updates) can now:
- Call database methods with user.id from require_auth
- Use get_rule_for_user for ownership verification before mutations
- Update dashboard to use get_user_stats and get_upcoming_events_for_user
