---
phase: 03-multi-tenant-access
plan: 02
subsystem: web-routes
tags: [multi-tenant, user-scoping, fastapi, route-handlers, ownership-verification]

dependency-graph:
  requires: [03-01]
  provides: [user-scoped-route-handlers]
  affects: [03-03]

tech-stack:
  added: []
  patterns: [ownership-verification, user-id-injection, user-scoped-queries]

key-files:
  created: []
  modified:
    - ra-tracker/ra_tracker/web/routes.py
    - ra-tracker/ra_tracker/web/templates/dashboard.html

decisions:
  - id: 03-02-01
    description: "Ownership verification returns 404, not 403"
    rationale: "Never reveal if rule exists for another user (security best practice)"
  - id: 03-02-02
    description: "Legacy data welcome message with dismiss button"
    rationale: "Inform first user about inherited data, one-time dismissable"
  - id: 03-02-03
    description: "All rule mutations verify ownership before action"
    rationale: "Prevent IDOR vulnerabilities via URL manipulation"

metrics:
  duration: 6 minutes
  completed: 2026-01-29
---

# Phase 03 Plan 02: Route Handler Updates Summary

**One-liner:** Route handlers now pass user.id to database methods, verify rule ownership before mutations, and display legacy data welcome message.

## What Was Built

Updated all web routes to implement multi-tenant data isolation at the route level.

### Task 1: User-Scoped Dashboard and Rules Page

**Dashboard route (`/`):**
- Changed `get_upcoming_events()` to `get_upcoming_events_for_user(user.id)`
- Changed `get_all_rules()` to `get_all_rules(user_id=user.id)`
- Changed `get_stats()` to `get_user_stats(user.id)`
- Added `legacy_data = db.count_legacy_data(user.id)` for welcome message
- Passes `legacy_data` to template context

**Rules page route (`/rules`):**
- Changed `get_all_rules()` to `get_all_rules(user_id=user.id)`
- User only sees their own rules to manage

**Dashboard template:**
- Added legacy data welcome message component
- Styled as info alert with Tailwind (blue-50 background, blue-400 border)
- Includes dismiss button with 44px touch target
- Only displays if legacy_data.rules > 0 or legacy_data.notifications > 0

### Task 2: User-Scoped Rule Mutations and API Endpoints

**Rule creation:**
- `add_rule()`: Uses `rule_exists(type, id, user_id=user.id)` and `add_rule(rule, user_id=user.id)`
- `api_add_rule()`: Same changes, error message updated to "You are already tracking this"

**Rule mutations with ownership verification:**
- `toggle_rule()`: Uses `get_rule_for_user(rule_id, user.id)` before mutation
- `set_notify_mode()`: Uses `get_rule_for_user(rule_id, user.id)` before mutation
- `delete_rule()`: Uses `get_rule_for_user(rule_id, user.id)` before deletion
- All return 404 if rule not found OR doesn't belong to user (never reveals ownership)

**API endpoints:**
- `api_check_rule()`: Uses `rule_exists(type, id, user_id=user.id)` for per-user duplicate check
- `get_status()`: Uses `get_user_stats(user.id)` for user-scoped statistics

## Key Patterns Established

### Ownership Verification Pattern
```python
@router.post("/rules/{rule_id}/delete")
async def delete_rule(rule_id: int, user: User = Depends(require_auth)):
    db = get_db()
    rule = db.get_rule_for_user(rule_id, user.id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete_rule(rule_id)
    return RedirectResponse(url="/rules", status_code=303)
```

### User-Scoped Query Pattern
```python
events = db.get_upcoming_events_for_user(user.id)
rules = db.get_all_rules(user_id=user.id)
stats = db.get_user_stats(user.id)
```

### Per-User Duplicate Check Pattern
```python
if db.rule_exists(rule_type, target_id, user_id=user.id):
    return RedirectResponse(url="/rules", status_code=303)
db.add_rule(rule, user_id=user.id)
```

## Integration Points

### From 03-01 Database Methods Used
- `get_upcoming_events_for_user(user_id)` - dashboard events
- `get_all_rules(user_id=user_id)` - user's rules
- `get_user_stats(user_id)` - user statistics
- `count_legacy_data(user_id)` - legacy data count
- `get_rule_for_user(rule_id, user_id)` - ownership verification
- `rule_exists(type, id, user_id=user_id)` - per-user duplicate check
- `add_rule(rule, user_id=user_id)` - rule assignment

### For 03-03 Admin Routes
Admin will need different patterns:
- View all rules: `get_all_rules()` without user_id
- View all users: New `get_all_users()` method
- Read-only access to other users' data

## Commits

| Hash | Message |
|------|---------|
| dcb97df | feat(03-02): user-scoped dashboard and rules page queries |
| 9d9f59f | feat(03-02): user-scoped rule mutations and API endpoints |

## Deviations from Plan

None - plan executed exactly as written.

## Testing Performed

1. Python syntax verification: Module loads successfully
2. Source code inspection verified:
   - dashboard() uses get_upcoming_events_for_user, get_all_rules(user_id=), get_user_stats, count_legacy_data
   - rules_page() uses get_all_rules(user_id=)
   - add_rule() uses rule_exists with user_id, add_rule with user_id
   - toggle_rule() uses get_rule_for_user for ownership verification
   - set_notify_mode() uses get_rule_for_user for ownership verification
   - delete_rule() uses get_rule_for_user for ownership verification
   - api_add_rule() uses rule_exists and add_rule with user_id
   - api_check_rule() uses rule_exists with user_id
   - get_status() uses get_user_stats

## Next Plan Readiness

03-03-PLAN.md (Admin Routes) can now:
- Build on the user-scoped route pattern
- Add require_admin dependency for admin-only routes
- Create /admin/* routes for viewing all users' rules (read-only)
- Use get_all_rules() without user_id for admin view
