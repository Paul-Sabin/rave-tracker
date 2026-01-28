# Phase 3: Multi-Tenant Access - Research

**Researched:** 2026-01-28
**Domain:** FastAPI Multi-Tenant Authorization, User-Scoped Data Access, Admin Routes
**Confidence:** HIGH

## Summary

This phase scopes data access to the logged-in user. Rules and notifications become user-specific while events remain globally shared. The existing codebase has strong foundations: users table with `is_admin` flag, sessions with `require_auth` dependency, and `user_id` columns already added to rules/notifications tables (nullable for legacy data). The key work is modifying database queries to filter by `user_id`, updating route handlers to pass user context, and creating admin-only routes for oversight.

Key findings:
- FastAPI dependency injection already provides `require_auth` that returns the authenticated `User` object - this is the foundation for scoping
- Database queries need `WHERE user_id = ?` clauses added to `get_all_rules()`, `get_upcoming_events()`, etc.
- Admin routes should use a separate `require_admin` dependency that checks `user.is_admin`
- Events table has no `user_id` - intentionally shared globally (MULTI-04), but `event_rules` links events to user-owned rules
- Legacy data migration (assign to first user) is already implemented in `create_user()` - just need dashboard message

**Primary recommendation:** Add `user_id` parameters to existing database methods, create `require_admin` dependency, build `/admin/*` routes for view-only rule oversight.

## Standard Stack

The established libraries/tools for this domain:

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | current | Web framework with dependency injection | Already handles auth via `require_auth` |
| SQLite | stdlib | Database with user_id columns | Foreign keys already in place |
| Jinja2 | current | Templates | Can conditionally show admin links |

### Supporting (No New Dependencies Needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| secrets | stdlib | Already used for session tokens | Compare digest for auth |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQL WHERE clauses | Row Level Security (RLS) | RLS requires PostgreSQL, SQLite doesn't support it |
| Manual admin check | Permission library (casbin) | Overkill for binary admin/non-admin |
| APIRouter prefix | Separate admin app | Unnecessary complexity for few admin routes |

**No additional packages required.** Everything needed is already in the codebase.

## Architecture Patterns

### Recommended Project Structure
```
ra_tracker/
├── web/
│   ├── auth.py             # Add require_admin dependency
│   ├── routes.py           # Update existing routes with user scoping
│   ├── admin.py            # NEW: Admin-only routes (/admin/*)
│   └── templates/
│       ├── base.html       # Add admin nav link (conditional on user.is_admin)
│       ├── dashboard.html  # Add legacy data message
│       ├── admin/          # NEW: Admin templates
│       │   ├── rules.html  # View all users' rules (read-only)
│       │   └── users.html  # View registered users
├── database.py             # Update queries with user_id filtering
```

### Pattern 1: User-Scoped Database Queries
**What:** Add user_id parameter to existing query methods
**When to use:** All queries for rules, notifications, stats

```python
# Source: Existing database.py pattern + multi-tenant best practices
def get_all_rules(self, user_id: Optional[int] = None) -> List[Rule]:
    """Get all rules, optionally filtered by user."""
    with self.get_connection() as conn:
        if user_id is not None:
            cursor = conn.execute(
                "SELECT * FROM rules WHERE user_id = ? ORDER BY rule_type, target_name",
                (user_id,)
            )
        else:
            cursor = conn.execute("SELECT * FROM rules ORDER BY rule_type, target_name")
        return [self._row_to_rule(row) for row in cursor.fetchall()]

def get_active_rules(self, user_id: Optional[int] = None) -> List[Rule]:
    """Get active rules for a user."""
    with self.get_connection() as conn:
        if user_id is not None:
            cursor = conn.execute(
                "SELECT * FROM rules WHERE is_active = 1 AND user_id = ? ORDER BY rule_type, target_name",
                (user_id,)
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM rules WHERE is_active = 1 ORDER BY rule_type, target_name"
            )
        return [self._row_to_rule(row) for row in cursor.fetchall()]
```

### Pattern 2: Admin-Only Dependency
**What:** Create `require_admin` dependency that extends `require_auth`
**When to use:** All `/admin/*` routes

```python
# Source: FastAPI official dependency patterns
from fastapi import Depends, HTTPException, status

async def require_admin(user: User = Depends(require_auth)) -> User:
    """Require admin privileges. Returns 403 Forbidden for non-admins."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user
```

### Pattern 3: Admin Router with Prefix
**What:** Separate APIRouter for admin routes with `/admin` prefix
**When to use:** Grouping all admin functionality

```python
# Source: FastAPI bigger applications documentation
from fastapi import APIRouter, Depends

# In admin.py
admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],  # All routes require admin
)

@admin_router.get("/rules")
async def admin_view_rules(request: Request, user: User = Depends(require_admin)):
    """View all users' rules (read-only)."""
    db = get_db()
    all_rules = db.get_all_rules()  # No user_id filter
    # Group by user for display
    ...

# In app.py
app.include_router(admin_router)
```

### Pattern 4: User-Scoped Event Visibility
**What:** Events are shared, but matched_rules should only show user's rules
**When to use:** Dashboard event display

```python
# Source: Context decisions - users only see events matching THEIR rules
def get_upcoming_events_for_user(self, user_id: int) -> List[Event]:
    """Get upcoming events that match the user's rules."""
    with self.get_connection() as conn:
        # Get events that have at least one rule belonging to this user
        cursor = conn.execute("""
            SELECT DISTINCT e.* FROM events e
            JOIN event_rules er ON e.id = er.event_id
            JOIN rules r ON er.rule_id = r.id
            WHERE r.user_id = ? AND e.date >= ?
            ORDER BY e.date, e.start_time
        """, (user_id, date.today().isoformat()))

        events = []
        for row in cursor.fetchall():
            event = self._row_to_event(row)
            # Get ONLY this user's matched rules for the event
            event.matched_rules = self._get_user_matched_rules(conn, event.id, user_id)
            events.append(event)
        return events

def _get_user_matched_rules(self, conn, event_id: int, user_id: int) -> List[Rule]:
    """Get rules matching an event that belong to a specific user."""
    cursor = conn.execute("""
        SELECT r.* FROM rules r
        JOIN event_rules er ON r.id = er.rule_id
        WHERE er.event_id = ? AND r.user_id = ?
    """, (event_id, user_id))
    return [self._row_to_rule(row) for row in cursor.fetchall()]
```

### Pattern 5: Rule Ownership Verification
**What:** Before edit/delete, verify rule belongs to current user
**When to use:** All rule modification endpoints

```python
# Source: Multi-tenant security best practices
def get_rule_for_user(self, rule_id: int, user_id: int) -> Optional[Rule]:
    """Get a rule only if it belongs to the specified user."""
    with self.get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id)
        )
        row = cursor.fetchone()
        return self._row_to_rule(row) if row else None

# In routes.py
@router.post("/rules/{rule_id}/delete")
async def delete_rule(rule_id: int, user: User = Depends(require_auth)):
    db = get_db()
    rule = db.get_rule_for_user(rule_id, user.id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete_rule(rule_id)
    return RedirectResponse(url="/rules", status_code=303)
```

### Pattern 6: Legacy Data Dashboard Message
**What:** Show message when user has inherited legacy data
**When to use:** Dashboard on first load after registration

The legacy data is assigned in `create_user()` when first user registers. To show the message:

```python
# Option 1: Count legacy rules (those created before user.created_at)
# Option 2: Flag in session/flash message (simpler, one-time)
# Recommendation: Use query approach - no extra state needed

def count_legacy_rules(self, user_id: int) -> int:
    """Count rules that were migrated to this user (existed before account)."""
    with self.get_connection() as conn:
        user = self.get_user_by_id(user_id)
        if not user or not user.created_at:
            return 0
        cursor = conn.execute(
            "SELECT COUNT(*) FROM rules WHERE user_id = ? AND created_at < ?",
            (user_id, user.created_at.isoformat())
        )
        return cursor.fetchone()[0]
```

### Anti-Patterns to Avoid
- **Filtering in Python instead of SQL:** Always use `WHERE user_id = ?` in queries, not post-fetch filtering
- **Trusting client-provided user_id:** Always get user_id from `require_auth` dependency, never from request body/params
- **Forgetting ownership check on mutations:** Delete/update must verify rule.user_id matches current user
- **Showing other users' data in error messages:** "Rule not found" not "Rule belongs to another user"
- **Admin routes without admin check:** All `/admin/*` must use `require_admin` dependency

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Admin check | Custom middleware | `require_admin` dependency | FastAPI DI pattern, cleaner |
| Route grouping | Manual prefix in each route | `APIRouter(prefix="/admin")` | Built-in, consistent |
| User from request | Parse cookies manually | `Depends(require_auth)` | Already implemented, secure |
| Event-rule linking | Join in Python | SQL JOIN in database | Performance, correctness |
| Cascade delete | Manual deletion | ON DELETE CASCADE | Already in schema |

**Key insight:** The existing codebase has all the building blocks. The work is connecting them with proper user scoping, not building new infrastructure.

## Common Pitfalls

### Pitfall 1: Forgetting User Scope in API Endpoints
**What goes wrong:** `/api/rules/check` or `/api/status` leaks data from other users
**Why it happens:** Only updating HTML routes, missing API endpoints
**How to avoid:** Audit ALL routes in routes.py, add user_id filtering to each
**Warning signs:** Can see stats/data from other accounts via browser dev tools

### Pitfall 2: Rule Existence Check Without User Scope
**What goes wrong:** `rule_exists()` returns True even if rule belongs to another user
**Why it happens:** Check prevents "duplicate" rules globally instead of per-user
**How to avoid:** Add user_id to `rule_exists()` query
**Warning signs:** "Already tracking" when you've never added that artist

```python
# BAD - global check
def rule_exists(self, rule_type: str, target_id: int) -> bool:
    ...

# GOOD - user-scoped check
def rule_exists(self, rule_type: str, target_id: int, user_id: int) -> bool:
    with self.get_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM rules WHERE rule_type = ? AND target_id = ? AND user_id = ?",
            (rule_type, target_id, user_id)
        )
        return cursor.fetchone() is not None
```

### Pitfall 3: Events Without User's Rules
**What goes wrong:** Dashboard shows events but no "matched by" badges
**Why it happens:** Getting all events, but only user's rules - no matches found
**How to avoid:** Only fetch events that match user's rules (JOIN through event_rules)
**Warning signs:** Events visible but matched_rules list is empty

### Pitfall 4: Admin Sees Other Users' UI Elements
**What goes wrong:** Admin viewing rules page sees edit/delete buttons for other users' rules
**Why it happens:** Admin view template reuses normal rules template
**How to avoid:** Create separate read-only admin template, or conditionally hide actions
**Warning signs:** Admin can click delete on rules they shouldn't modify

### Pitfall 5: Scheduler Breaks with User Scoping
**What goes wrong:** Background event fetcher stops working
**Why it happens:** Scheduler jobs don't run with a user context
**How to avoid:** Scheduler fetches events for ALL active rules (no user filter), event_rules table links them
**Warning signs:** "No user in context" errors in scheduler logs

### Pitfall 6: Notification History Leaks Between Users
**What goes wrong:** User sees notifications for another user's rule matches
**Why it happens:** Notifications table not filtered by user_id
**How to avoid:** Filter notifications query by user_id (already has user_id column)
**Warning signs:** Notification count includes events user doesn't have rules for

## Code Examples

Verified patterns from official sources and codebase analysis:

### Updated add_rule with User Assignment
```python
# Source: Existing database.py pattern + multi-tenant scoping
@router.post("/rules/add")
async def add_rule(
    request: Request,
    user: User = Depends(require_auth),
    rule_type: str = Form(...),
    target_id: int = Form(...),
    target_name: str = Form(...),
):
    """Add a new tracking rule assigned to current user."""
    db = get_db()

    # Check for duplicate FOR THIS USER
    if db.rule_exists(rule_type, target_id, user.id):
        return RedirectResponse(url="/rules", status_code=303)

    rule = Rule(
        id=None,
        rule_type=rule_type,
        target_id=target_id,
        target_name=target_name,
        is_active=True,
        user_id=user.id,  # Assign to current user
    )

    db.add_rule(rule, user_id=user.id)
    return RedirectResponse(url="/rules", status_code=303)
```

### User-Scoped Dashboard Query
```python
# Source: SQLite JOIN patterns + context decisions
def get_events_matching_user_rules(self, user_id: int) -> dict:
    """Get upcoming events that match user's rules, grouped by date."""
    with self.get_connection() as conn:
        today = date.today().isoformat()

        # Get events matching user's active rules
        cursor = conn.execute("""
            SELECT DISTINCT e.* FROM events e
            INNER JOIN event_rules er ON e.id = er.event_id
            INNER JOIN rules r ON er.rule_id = r.id
            WHERE r.user_id = ? AND r.is_active = 1 AND e.date >= ?
            ORDER BY e.date, e.start_time
        """, (user_id, today))

        events = []
        for row in cursor.fetchall():
            event = self._row_to_event(row)
            # Load artists, promoters (shared data)
            event.artists = self._get_event_artists(conn, event.id)
            event.promoters = self._get_event_promoters(conn, event.id)
            # Load ONLY this user's matched rules
            event.matched_rules = self._get_user_matched_rules(conn, event.id, user_id)
            events.append(event)

        return events
```

### Admin Rules View (Read-Only)
```python
# Source: FastAPI bigger applications docs + context decisions
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

admin_router = APIRouter(prefix="/admin", tags=["admin"])

@admin_router.get("/rules", response_class=HTMLResponse)
async def admin_view_all_rules(request: Request, user: User = Depends(require_admin)):
    """Admin view: All users' rules (read-only)."""
    templates = get_templates(request)
    db = get_db()

    # Get all rules with user info
    all_rules = db.get_all_rules_with_users()  # New method

    # Get all users for context
    all_users = db.get_all_users()

    return templates.TemplateResponse(
        "admin/rules.html",
        {
            "request": request,
            "user": user,
            "all_rules": all_rules,
            "all_users": all_users,
        },
    )
```

### Database Method: Get All Rules With User Info
```python
# Source: SQLite JOIN for admin view
def get_all_rules_with_users(self) -> List[dict]:
    """Get all rules with owner information (for admin view)."""
    with self.get_connection() as conn:
        cursor = conn.execute("""
            SELECT r.*, u.display_name as owner_name, u.email as owner_email
            FROM rules r
            LEFT JOIN users u ON r.user_id = u.id
            ORDER BY u.display_name, r.rule_type, r.target_name
        """)
        return [dict(row) for row in cursor.fetchall()]

def get_all_users(self) -> List[User]:
    """Get all registered users (for admin view)."""
    with self.get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        )
        return [self._row_to_user(row) for row in cursor.fetchall()]
```

### Conditional Admin Link in Navigation
```html
<!-- Source: Jinja2 conditional rendering -->
<!-- In base.html navigation -->
{% if user and user.is_admin %}
<a href="/admin/rules" class="px-4 py-2 min-h-11 flex items-center rounded hover:bg-border transition-colors {% if request.url.path.startswith('/admin') %}bg-border{% endif %}">
    Admin
</a>
{% endif %}
```

### Legacy Data Dashboard Message
```html
<!-- Source: Context decision - show message about migrated data -->
{% if legacy_count and legacy_count > 0 %}
<div class="alert alert-info">
    <strong>Welcome!</strong> {{ legacy_count }} rule{{ 's' if legacy_count != 1 else '' }}
    and {{ legacy_notifications }} notification{{ 's' if legacy_notifications != 1 else '' }}
    from the previous setup have been assigned to your account.
</div>
{% endif %}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Global queries | User-scoped queries | Multi-tenant standard | Data isolation |
| Admin middleware | FastAPI dependency | FastAPI 0.x | Cleaner, testable |
| Separate admin app | APIRouter prefix | FastAPI routing | Single deployment |
| Manual FK check | Database FK constraints | SQLite 3.6.19+ | Integrity guarantee |

**Deprecated/outdated:**
- **Flask-Login patterns:** FastAPI uses dependency injection, not Flask-style decorators
- **Session-stored user scope:** Get user from auth dependency each request, not session

## Open Questions

Things that couldn't be fully resolved:

1. **Stats should be user-scoped?**
   - What we know: Dashboard shows "upcoming events", "active rules", "notifications sent"
   - What's unclear: Should these be per-user or global?
   - Recommendation: Per-user (user's rules, user's events, user's notifications) - aligns with isolation principle

2. **Scheduler needs to fetch for all users**
   - What we know: Background job fetches events - can't have user context
   - What's unclear: How to efficiently fetch for all users' rules?
   - Recommendation: Scheduler fetches all active rules regardless of user, populates shared events table. User scoping happens at query time via event_rules JOIN.

3. **Admin notification access**
   - What we know: Admin can view rules (read-only)
   - What's unclear: Can admin see notification history?
   - Recommendation: Start with rules-only admin view per context decisions, add notification viewing if needed later

## Sources

### Primary (HIGH confidence)
- [FastAPI Dependencies in Path Operations](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/) - Admin dependency pattern
- [FastAPI Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/) - APIRouter prefix pattern
- [SQLite Foreign Key Support](https://sqlite.org/foreignkeys.html) - CASCADE delete, FK enforcement
- Existing codebase: `database.py`, `auth.py`, `routes.py` - Implementation patterns

### Secondary (MEDIUM confidence)
- [FastAPI Multi-Tenant Discussion](https://github.com/fastapi/fastapi/discussions/7564) - Community patterns
- [Building Multi-Tenant Systems with FastAPI](https://medium.com/@nicholasikiroma/building-a-secure-multi-tenant-knowledge-management-system-with-fastapi-and-permit-io-26bebdeb5bd4) - General architecture
- [SQLite Query Optimization](https://moldstud.com/articles/p-optimize-sqlite-queries-for-maximum-efficiency-proven-techniques-and-best-practices) - Index usage for user_id filters

### Tertiary (LOW confidence)
- Various blog posts on multi-tenant data isolation (patterns validated against official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies, extending existing patterns
- Architecture: HIGH - FastAPI patterns well-documented, codebase already has foundations
- Pitfalls: HIGH - Common multi-tenant security issues are well-known
- Admin routes: MEDIUM - Simpler than full RBAC, but need to ensure read-only

**Research date:** 2026-01-28
**Valid until:** 2026-02-28 (30 days - stable patterns, no library updates expected)
